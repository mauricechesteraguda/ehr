"""type-10022026-Maurice: Password plus mandatory TOTP session API."""
import pyotp
import time
import secrets
import webauthn
from datetime import date
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.db.models import Q
from django.utils.dateparse import parse_datetime
from django.http import FileResponse
from django.utils import timezone
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .logging import external_authenticate, log_event
from . import audit
from .models import AllergyIntolerance, AuditEvent, Condition, Device, DeviceVersion, DeviceOutboxEvent, Observation, Patient, User, MedicationOrder, MedicationOrderVersion, InteractionRule, AlertConfiguration, InteractionEvaluation, PatientExport, Job, FamilyHistory, FamilyHistoryVersion, FamilyHistoryOutboxEvent, Questionnaire, QuestionnaireResponse, QuestionnaireResponseVersion, QuestionnaireReview, EmergencyAccessRequest, PopulationExportArtifact, PopulationExportSchedule, CcdaDocument, ReconciliationCandidate, DirectDelivery
from .jobs import enqueue_job, cancel_job, dispatch_status
from .exports import create_export, purge_expired
from .interaction_safety import acknowledge_evaluation, evaluate_version, sign_version
from .serializers import LoginSerializer, OtpSerializer, PatientSerializer, MedicationVersionSerializer, FamilyHistoryVersionSerializer, DeviceVersionSerializer, QuestionnaireSerializer, QuestionnaireResponseVersionSerializer
from .questionnaires import create_response, review_response
from .amendments import begin_review, create_amendment, decide_amendment
from .models import PatientAmendment, PatientAmendmentOutbox, WebAuthnCredential, SmsRecoveryChallenge
from . import passkeys
import hashlib
from datetime import timedelta
from .udi import UnavailableGUDIDAdapter, parse_udi
from .tracing import trace_function
from .rate_limit import limited
from .break_glass import can_read, normal_patient_access, request_access, revoke_access, expire_access
from .population_exports import download_bytes
from .ccda import decide_candidate, MAX_BYTES, _crypt
from .direct_delivery import enqueue_delivery, deliver_direct, adapter
from pathlib import Path
import os


@trace_function
def _job_json(job):
    """type-10022026-Maurice: Return lifecycle metadata only; never return input or result payloads."""
    return {"id": str(job.id), "kind": job.kind, "state": job.state, "attempts": job.attempts,
            "max_attempts": job.max_attempts, "queued_at": job.queued_at, "started_at": job.started_at,
            "finished_at": job.finished_at, "heartbeat_at": job.heartbeat_at,
            "error_code": job.error_code or None, "dependency": "database"}


class JobCollectionView(APIView):
    """type-10022026-Maurice: Clinician/admin demo job submission; database commits before broker delivery."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def post(self, request):
        if request.user.role not in {User.Role.CLINICIAN, User.Role.ADMIN}:
            return Response({"detail": "Job operation is not permitted."}, status=403)
        data = request.data if isinstance(request.data, dict) else {}
        kind = data.get("kind", "demo.noop")
        key = data.get("idempotency_key")
        if not isinstance(kind, str) or kind not in {"demo.noop", "job.demo"} or not isinstance(key, str) or not key or len(key) > 160:
            return Response({"detail": "Unsupported or invalid job request."}, status=400)
        try:
            job, created = enqueue_job(owner=request.user, kind=kind, idempotency_key=key,
                                       input_data=data.get("input"), expires_at=None)
        except ValueError:
            return Response({"detail": "Idempotency key is already used."}, status=409)
        dependency = dispatch_status(limit=1)
        payload = _job_json(job)
        payload["dependency"] = dependency["state"]
        return Response(payload, status=202 if created else 200)

    @trace_function
    def get(self, request):
        if request.user.role != User.Role.ADMIN:
            return Response({"detail": "Administrator access required."}, status=403)
        return Response([_job_json(job) for job in Job.objects.order_by("-queued_at")[:100]])


class JobAdminView(APIView):
    """type-10022026-Maurice: Administrator-only status and cancellation boundary."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def get(self, request, job_id):
        if request.user.role != User.Role.ADMIN:
            return Response({"detail": "Administrator access required."}, status=403)
        try:
            return Response(_job_json(Job.objects.get(pk=job_id)))
        except Job.DoesNotExist:
            return Response({"detail": "Job not found."}, status=404)


def _patient_for_request(public_id, request):
    if request.user.role not in {User.Role.CLINICIAN, User.Role.ADMIN}: return None
    return Patient.objects.filter(public_id=public_id).first()

class CcdaExportView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, public_id):
        patient = _patient_for_request(public_id, request)
        if not patient: return Response({"detail":"Not found."}, status=404)
        key=request.headers.get("Idempotency-Key") or str((request.data or {}).get("idempotency_key", ""))
        if not key or len(key)>160: return Response({"detail":"Idempotency-Key is required."}, status=400)
        try: job, created=enqueue_job(owner=request.user, patient=patient, kind="ccda.export", idempotency_key=key, input_data={"format":"ccda","version":"1.0"})
        except ValueError: return Response({"detail":"Idempotency key is already used."}, status=409)
        if created:
            from .jobs import deliver_job
            deliver_job.delay(str(job.id), str(job.outbox_events.first().id))
        return Response(_job_json(job), status=202 if created else 200)

class CcdaImportView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, public_id):
        patient=_patient_for_request(public_id, request)
        if not patient: return Response({"detail":"Not found."}, status=404)
        data=request.body
        if len(data)>MAX_BYTES: return Response({"detail":"Upload exceeds bounded size."}, status=413)
        key=request.headers.get("Idempotency-Key") or ""
        if not key: return Response({"detail":"Idempotency-Key is required."}, status=400)
        try: job,created=enqueue_job(owner=request.user, patient=patient, kind="ccda.import", idempotency_key=key, input_data={"format":"ccda","version":"1.0"})
        except ValueError: return Response({"detail":"Idempotency key is already used."}, status=409)
        if created:
            root=Path(getattr(settings,"CCDA_ROOT",os.path.join(settings.BASE_DIR,"var","ccda"))); root.mkdir(parents=True,exist_ok=True)
            path=root/("input-"+str(job.id)); path.write_bytes(_crypt(data)); job.result_ref=str(path); job.save(update_fields=["result_ref"])
            from .jobs import deliver_job
            deliver_job.delay(str(job.id), str(job.outbox_events.first().id))
        return Response(_job_json(job), status=202 if created else 200)

class CcdaJobView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request, job_id):
        job=Job.objects.filter(pk=job_id, owner=request.user, kind__startswith="ccda.").first()
        return Response(_job_json(job)) if job else Response({"detail":"Not found."},status=404)

class CcdaCandidateView(APIView):
    permission_classes=[IsAuthenticated]
    def get(self, request, document_id):
        doc=CcdaDocument.objects.filter(pk=document_id).first()
        if not doc or request.user.role not in {User.Role.CLINICIAN,User.Role.ADMIN}: return Response({"detail":"Not found."},status=404)
        return Response([{"id":c.id,"section":c.section,"resource_type":c.resource_type,"payload":c.payload,"state":c.state} for c in doc.candidates.all()])

class CcdaDecisionView(APIView):
    permission_classes=[IsAuthenticated]
    def post(self, request, candidate_id):
        if request.user.role not in {User.Role.CLINICIAN,User.Role.ADMIN}: return Response({"detail":"Clinician access required."},status=403)
        try: c=decide_candidate(candidate_id=candidate_id, clinician=request.user, decision=request.data.get("decision"))
        except (ValueError, ReconciliationCandidate.DoesNotExist): return Response({"detail":"Candidate is stale or invalid."},status=409)
        return Response({"id":c.id,"state":c.state})

class CcdaBatchDecisionView(APIView):
    permission_classes=[IsAuthenticated]
    def post(self, request, document_id):
        if request.user.role not in {User.Role.CLINICIAN,User.Role.ADMIN}: return Response({"detail":"Clinician access required."},status=403)
        decisions=request.data.get("decisions",[]) if isinstance(request.data,dict) else []
        if not isinstance(decisions,list) or not decisions or len(decisions)>100: return Response({"detail":"Batch is bounded to 100 decisions."},status=400)
        try:
            with transaction.atomic():
                results=[decide_candidate(candidate_id=int(item["id"]),clinician=request.user,decision=item["decision"]) for item in decisions]
        except (KeyError,TypeError,ValueError,ReconciliationCandidate.DoesNotExist):
            return Response({"detail":"Batch rejected; no decisions were applied."},status=409)
        return Response({"count":len(results),"states":[c.state for c in results]})


def _direct_json(delivery):
    """Safe delivery projection: recipient, artifact path, bytes, and credentials never leave the service."""
    return {"id": str(delivery.id), "artifact_id": delivery.artifact_id, "purpose": delivery.purpose,
            "state": delivery.state, "attempts": delivery.attempts, "max_attempts": delivery.max_attempts,
            "error_code": delivery.error_code or None, "receipt_code": delivery.receipt_code or None,
            "receipt_checksum": delivery.receipt_checksum or None, "created_at": delivery.created_at,
            "finished_at": delivery.finished_at}


class DirectArtifactView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, public_id):
        if request.user.role not in {User.Role.CLINICIAN, User.Role.ADMIN}:
            return Response({"detail": "Clinician access required."}, status=403)
        patient = Patient.objects.filter(public_id=public_id).first()
        if not patient:
            return Response({"detail": "Not found."}, status=404)
        docs = CcdaDocument.objects.filter(patient=patient, direction="export").order_by("-created_at")[:50]
        return Response([{"id": d.pk, "template_id": d.template_id, "template_version": d.template_version,
                          "created_at": d.created_at, "expires_at": d.expires_at, "size_bytes": d.size_bytes,
                          "sha256": d.sha256} for d in docs])


class DirectDeliveryView(APIView):
    permission_classes = [IsAuthenticated]

    def _allowed(self, request):
        return request.user.role in {User.Role.CLINICIAN, User.Role.ADMIN}

    def get(self, request, delivery_id=None):
        if not self._allowed(request):
            return Response({"detail": "Clinician access required."}, status=403)
        qs = DirectDelivery.objects.select_related("artifact")
        if request.user.role != User.Role.ADMIN:
            qs = qs.filter(owner=request.user)
        if delivery_id:
            item = qs.filter(pk=delivery_id).first()
            return Response(_direct_json(item)) if item else Response({"detail": "Not found."}, status=404)
        return Response([_direct_json(item) for item in qs.order_by("-created_at")[:100]])

    def post(self, request, delivery_id=None):
        if not self._allowed(request):
            return Response({"detail": "Clinician access required."}, status=403)
        if delivery_id:
            item = DirectDelivery.objects.filter(pk=delivery_id).first() if request.user.role == User.Role.ADMIN else DirectDelivery.objects.filter(pk=delivery_id, owner=request.user).first()
            if not item or item.state != DirectDelivery.State.FAILED:
                return Response({"detail": "Only failed deliveries can be retried."}, status=409)
            item.state, item.error_code, item.finished_at = DirectDelivery.State.QUEUED, "", None
            item.save(update_fields=["state", "error_code", "finished_at", "updated_at"])
            deliver_direct.delay(str(item.id))
            return Response(_direct_json(item), status=202)
        data = request.data if isinstance(request.data, dict) else {}
        key = request.headers.get("Idempotency-Key") or data.get("idempotency_key")
        try:
            artifact = CcdaDocument.objects.get(pk=data.get("artifact_id"), direction="export")
            delivery, created = enqueue_delivery(owner=request.user, artifact=artifact, recipient=data.get("recipient"), purpose=data.get("purpose"), idempotency_key=key)
        except (CcdaDocument.DoesNotExist, TypeError, ValueError):
            return Response({"detail": "Invalid recipient, purpose, artifact, or idempotency key."}, status=400)
        if created:
            deliver_direct.delay(str(delivery.id))
        return Response(_direct_json(delivery), status=202 if created else 200)


class DirectDeliveryCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, delivery_id):
        if request.user.role not in {User.Role.CLINICIAN, User.Role.ADMIN}:
            return Response({"detail": "Clinician access required."}, status=403)
        qs = DirectDelivery.objects.filter(pk=delivery_id)
        if request.user.role != User.Role.ADMIN:
            qs = qs.filter(owner=request.user)
        item = qs.first()
        if not item:
            return Response({"detail": "Not found."}, status=404)
        if item.state in {DirectDelivery.State.QUEUED, DirectDelivery.State.SENDING}:
            item.state, item.finished_at = DirectDelivery.State.CANCELLED, timezone.now()
            item.save(update_fields=["state", "finished_at", "updated_at"])
        return Response(_direct_json(item))


def _population_json(artifact):
    job = artifact.job
    return {"id": str(artifact.id), "job_id": str(job.id), "state": job.state, "format": artifact.format,
            "sha256": artifact.sha256 if job.state == Job.State.SUCCEEDED else None,
            "size_bytes": artifact.size_bytes if job.state == Job.State.SUCCEEDED else None,
            "expires_at": artifact.expires_at, "download_url": f"/api/admin/population-exports/{artifact.id}/download/" if job.state == Job.State.SUCCEEDED else None,
            "attempts": job.attempts, "error_code": job.error_code or None}


class PopulationExportCollectionView(APIView):
    permission_classes = [IsAuthenticated]

    def _admin(self, request):
        return request.user.role == User.Role.ADMIN

    def get(self, request):
        if not self._admin(request): return Response({"detail": "Administrator access required."}, status=403)
        return Response([_population_json(a) for a in PopulationExportArtifact.objects.select_related("job").order_by("-created_at")[:100]])

    def post(self, request):
        if not self._admin(request): return Response({"detail": "Administrator access required."}, status=403)
        data = request.data if isinstance(request.data, dict) else {}
        from datetime import date
        try:
            scope, fmt = data.get("scope", "all-demo"), data.get("format", "jsonl")
            start, end = date.fromisoformat(str(data["start_date"])), date.fromisoformat(str(data["end_date"]))
            purpose, cap = str(data["purpose"]), int(data.get("cap", settings.POPULATION_EXPORT_CAP))
            if scope != "all-demo" or fmt not in {"csv", "jsonl"} or start > end or not 10 <= len(purpose) <= 500 or cap < 0 or cap > settings.POPULATION_EXPORT_CAP:
                raise ValueError
            cadence = str(data.get("cadence", "once")); tz = str(data.get("timezone", "UTC"))
            if cadence not in {"once", "daily", "weekly"} or tz not in {"UTC", "America/New_York", "Europe/London"}: raise ValueError
        except (KeyError, TypeError, ValueError):
            return Response({"detail": "Invalid scope, date range, purpose, format, cap, or schedule."}, status=400)
        idem = request.headers.get("Idempotency-Key") or str(data.get("idempotency_key", ""))
        if not idem or len(idem) > 160: return Response({"detail": "Idempotency-Key is required."}, status=400)
        schedule = None
        if cadence != "once":
            schedule = PopulationExportSchedule.objects.create(owner=request.user, scope=scope, start_date=start, end_date=end, purpose=purpose, format=fmt, timezone=tz, cadence=cadence, next_run_at=timezone.now())
        payload = {"scope": scope, "format": fmt, "start_date": start.isoformat(), "end_date": end.isoformat(), "purpose": purpose, "cap": cap, "schedule_id": str(schedule.id) if schedule else ""}
        try:
            # The schedule UUID is an internal relation, not part of equivalent-request identity.
            job_payload = {key: value for key, value in payload.items() if key != "schedule_id"}
            job, created = enqueue_job(owner=request.user, kind="population.export", idempotency_key=idem, input_data=job_payload, expires_at=timezone.now() + timedelta(hours=24))
        except ValueError:
            if schedule: schedule.delete()
            return Response({"detail": "Idempotency key is already used."}, status=409)
        if created:
            try:
                with transaction.atomic():
                    PopulationExportArtifact.objects.create(job=job, schedule=schedule, owner=request.user, format=fmt, path="", sha256="", expires_at=job.expires_at)
                    artifact = PopulationExportArtifact.objects.select_related("job").get(job=job)
                    audit.append_audit_event(actor=request.user, action="request", resource_type="PopulationExport", resource_id=artifact.id)
            except Exception:
                job.delete()
                return Response({"detail": "Export audit unavailable; nothing was queued."}, status=503)
            return Response(_population_json(artifact), status=202)
        if schedule: schedule.delete()
        artifact = PopulationExportArtifact.objects.filter(job=job).first()
        return Response(_population_json(artifact) if artifact else {"job_id": str(job.id), "state": job.state}, status=200)


class PopulationExportDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, artifact_id):
        if request.user.role != User.Role.ADMIN: return Response({"detail": "Administrator access required."}, status=403)
        artifact = PopulationExportArtifact.objects.select_related("job").filter(pk=artifact_id).first()
        if not artifact: return Response({"detail": "Export not found."}, status=404)
        return Response(_population_json(artifact))

    def post(self, request, artifact_id):
        if request.user.role != User.Role.ADMIN: return Response({"detail": "Administrator access required."}, status=403)
        artifact = PopulationExportArtifact.objects.select_related("job").filter(pk=artifact_id).first()
        if not artifact: return Response({"detail": "Export not found."}, status=404)
        action = request.data.get("action")
        if action == "cancel":
            cancel_job(artifact.job_id, actor=request.user)
        elif action == "retry" and artifact.job.state == Job.State.FAILED:
            artifact.job.state, artifact.job.error_code, artifact.job.finished_at = Job.State.QUEUED, "", None
            artifact.job.save(update_fields=["state", "error_code", "finished_at"])
        else: return Response({"detail": "Unsupported export action."}, status=400)
        return Response(_population_json(artifact))


class PopulationExportDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, artifact_id):
        if request.user.role != User.Role.ADMIN: return Response({"detail": "Administrator access required."}, status=403)
        artifact = PopulationExportArtifact.objects.select_related("job").filter(pk=artifact_id, job__state=Job.State.SUCCEEDED).first()
        if not artifact: return Response({"detail": "Export unavailable."}, status=404)
        try: payload = download_bytes(artifact)
        except (FileNotFoundError, RuntimeError, ValueError): return Response({"detail": "Export unavailable."}, status=404)
        audit.append_audit_event(actor=request.user, action="read", resource_type="PopulationExport", resource_id=artifact.id)
        response = Response(payload, content_type="application/octet-stream")
        response["Content-Disposition"] = f'attachment; filename="population-export.{artifact.format}"'
        return response

    @trace_function
    def post(self, request, job_id):
        if request.user.role != User.Role.ADMIN:
            return Response({"detail": "Administrator access required."}, status=403)
        if request.data.get("action") != "cancel":
            return Response({"detail": "Unsupported job action."}, status=400)
        try:
            return Response(_job_json(cancel_job(job_id, actor=request.user)))
        except Job.DoesNotExist:
            return Response({"detail": "Job not found."}, status=404)


@api_view(["POST"])
@permission_classes([AllowAny])
@trace_function
def login_view(request):
    """type-10022026-Maurice: Authenticate password and require current TOTP."""
    if (throttled := limited(request, "login", limit=8, window=60)) is not None:
        return throttled
    data = LoginSerializer(data=request.data)
    if not data.is_valid():
        return Response({"detail": "Invalid credentials."}, status=400)
    user = external_authenticate(lambda: authenticate(request, username=data.validated_data["username"], password=data.validated_data["password"]))
    if not user or not user.totp_enrolled:
        log_event("auth.login.failure")
        return Response({"detail": "Invalid credentials or MFA enrollment required."}, status=400)
    otp = data.validated_data.get("otp", "")
    if not otp and user.webauthn_credentials.filter(revoked_at__isnull=True).exists():
        request.session["pending_mfa_user"] = user.pk
        log_event("auth.login.passkey.offered", user_role=user.role)
        return Response({"mfa": "webauthn", "options": passkeys.authentication_options(request, user)}, status=200)
    if not pyotp.TOTP(user.totp_secret).verify(otp, valid_window=0):
        log_event("auth.mfa.failure", user_role=user.role)
        return Response({"detail": "Invalid credentials or verification code."}, status=401)
    login(request, user)
    request.session["totp_authenticated"] = True
    request.session["mfa_generation"] = user.mfa_generation
    log_event("auth.login.success", user_role=user.role)
    return Response({"role": user.role})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@trace_function
def passkey_options_view(request):
    """Create a short-lived registration challenge for an already MFA-authenticated session."""
    return Response(passkeys.registration_options(request))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@trace_function
def passkey_register_view(request):
    try:
        credential = passkeys.verify_registration(request, request.data, request.data.get("name", "Passkey"))
    except Exception as error:
        log_event("auth.passkey.enrollment.failure", outcome="failure", error_class=type(error).__name__)
        return Response({"detail": "Passkey enrollment failed."}, status=400)
    return Response({"id": credential.pk, "name": credential.name, "user_verified": credential.user_verified}, status=201)


@api_view(["POST"])
@permission_classes([AllowAny])
@trace_function
def passkey_login_options_view(request):
    data = LoginSerializer(data=request.data)
    if not data.is_valid():
        return Response({"detail": "Invalid credentials."}, status=400)
    user = external_authenticate(lambda: authenticate(request, username=data.validated_data["username"], password=data.validated_data["password"]))
    if not user or not user.totp_enrolled or not user.webauthn_credentials.filter(revoked_at__isnull=True).exists():
        return Response({"detail": "Passkey login unavailable."}, status=400)
    request.session["pending_mfa_user"] = user.pk
    return Response({"mfa": "webauthn", "options": passkeys.authentication_options(request, user)})


@api_view(["POST"])
@permission_classes([AllowAny])
@trace_function
def passkey_login_view(request):
    from django.contrib.auth import get_user_model
    user_id = request.session.get("pending_mfa_user")
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if not user:
        return Response({"detail": "Passkey login unavailable."}, status=401)
    try:
        passkeys.verify_authentication(request, request.data, user)
    except Exception as error:
        log_event("auth.passkey.authentication.failure", outcome="failure", error_class=type(error).__name__)
        return Response({"detail": "Passkey verification failed."}, status=401)
    request.session.pop("pending_mfa_user", None)
    return Response({"role": user.role})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def passkey_list_view(request):
    return Response([{"id": c.pk, "name": c.name, "created_at": c.created_at.isoformat(), "transports": c.transports, "backup_eligible": c.backup_eligible, "backup_state": c.backup_state, "user_verified": c.user_verified} for c in request.user.webauthn_credentials.filter(revoked_at__isnull=True)])


@api_view(["PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
@trace_function
def passkey_manage_view(request, credential_id):
    credential = request.user.webauthn_credentials.filter(pk=credential_id, revoked_at__isnull=True).first()
    if not credential:
        return Response({"detail": "Passkey not found."}, status=404)
    if request.method == "PATCH":
        name = request.data.get("name")
        if not isinstance(name, str) or not name.strip() or len(name) > 80:
            return Response({"detail": "A bounded name is required."}, status=400)
        credential.name = name.strip(); credential.save(update_fields=["name"])
        audit.append_audit_event(actor=request.user, action="update", resource_type="WebAuthnCredential", resource_id=credential.pk, correlation_id=getattr(request, "correlation_id", ""))
        return Response({"id": credential.pk, "name": credential.name})
    credential.revoked_at = timezone.now(); credential.save(update_fields=["revoked_at"])
    audit.append_audit_event(actor=request.user, action="delete", resource_type="WebAuthnCredential", resource_id=credential.pk, correlation_id=getattr(request, "correlation_id", ""))
    return Response(status=204)


@api_view(["POST"])
@permission_classes([AllowAny])
@trace_function
def recovery_request_view(request):
    if (throttled := limited(request, "sms_recovery", limit=3, window=300)) is not None:
        return throttled
    username, password, phone = str(request.data.get("username", "")), str(request.data.get("password", "")), str(request.data.get("phone", ""))
    user = external_authenticate(lambda: authenticate(request, username=username, password=password))
    if not user or not phone or (user.recovery_phone_hash and not secrets.compare_digest(user.recovery_phone_hash, hashlib.sha256(phone.encode()).hexdigest())):
        log_event("auth.recovery.failure", outcome="failure", reason="identity_proof")
        return Response({"detail": "Recovery unavailable."}, status=400)
    code = hashlib.sha256(f"{user.pk}:{user.username}".encode()).hexdigest()[:6]
    challenge = SmsRecoveryChallenge.objects.create(user=user, code_hash=hashlib.sha256(code.encode()).hexdigest(), expires_at=timezone.now() + timedelta(seconds=settings.SMS_RECOVERY_TTL_SECONDS), delivery_reference=f"sms-{secrets.token_hex(8)}")
    log_event("auth.recovery.sms.sent", outcome="success")
    return Response({"recovery_id": challenge.pk, "expires_in": settings.SMS_RECOVERY_TTL_SECONDS})


@api_view(["POST"])
@permission_classes([AllowAny])
@trace_function
def recovery_verify_view(request):
    code = str(request.data.get("code", ""))
    try:
        with transaction.atomic():
            challenge = SmsRecoveryChallenge.objects.select_for_update().filter(pk=request.data.get("recovery_id"), used_at__isnull=True).select_related("user").first()
            if not challenge or challenge.expires_at <= timezone.now() or challenge.attempts >= settings.SMS_RECOVERY_MAX_ATTEMPTS:
                return Response({"detail": "Recovery code invalid or expired."}, status=400)
            challenge.attempts += 1
            if not secrets.compare_digest(challenge.code_hash, hashlib.sha256(code.encode()).hexdigest()):
                challenge.save(update_fields=["attempts"]); log_event("auth.recovery.failure", outcome="failure", reason="code"); return Response({"detail": "Recovery code invalid or expired."}, status=400)
            challenge.used_at = timezone.now(); challenge.save(update_fields=["attempts", "used_at"])
            user = challenge.user
            user.mfa_generation += 1; user.totp_enrolled = False; user.save(update_fields=["mfa_generation", "totp_enrolled"])
            audit.append_audit_event(actor=user, action="update", resource_type="MFARecovery", resource_id=challenge.pk, correlation_id=getattr(request, "correlation_id", ""))
    except Exception as error:
        log_event("auth.recovery.failure", outcome="failure", reason=type(error).__name__)
        return Response({"detail": "Recovery could not be completed."}, status=503)
    logout(request)
    log_event("auth.recovery.success", outcome="success", user_role=user.role)
    return Response({"re_enrollment_required": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@trace_function
def enroll_view(request):
    """type-10022026-Maurice: Generate an enrollment secret without returning credentials."""
    if (throttled := limited(request, "mfa", limit=10, window=60)) is not None:
        return throttled
    log_event("auth.totp.enrollment.entry", component="authentication", operation="enrollment")
    user = request.user
    if not user.totp_secret:
        user.totp_secret = pyotp.random_base32()
        user.save(update_fields=["totp_secret"])
    log_event("auth.totp.enrollment.success", outcome="success", component="authentication", operation="enrollment")
    return Response({"secret": user.totp_secret, "enrolled": user.totp_enrolled})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@trace_function
def verify_enrollment_view(request):
    """type-10022026-Maurice: Verify enrollment code before enabling MFA."""
    if (throttled := limited(request, "mfa", limit=10, window=60)) is not None:
        return throttled
    log_event("auth.totp.enrollment.verification.entry", component="authentication", operation="enrollment_verification")
    data = OtpSerializer(data=request.data)
    if not data.is_valid() or not pyotp.TOTP(request.user.totp_secret).verify(data.validated_data.get("otp", ""), valid_window=0):
        log_event("auth.totp.enrollment.verification.failure", outcome="failure", component="authentication", operation="enrollment_verification")
        return Response({"detail": "Invalid verification code."}, status=400)
    request.user.totp_enrolled = True
    request.user.save(update_fields=["totp_enrolled"])
    log_event("auth.totp.enrollment.verification.success", outcome="success", component="authentication", operation="enrollment_verification")
    return Response({"enrolled": True})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@trace_function
def session_view(request):
    """type-10022026-Maurice: Return the minimal safe session status."""
    return Response({"authenticated": True, "role": request.user.role, "username": request.user.username})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@trace_function
def logout_view(request):
    """type-10022026-Maurice: End the authenticated session."""
    logout(request)
    log_event("auth.logout")
    return Response({"authenticated": False})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@trace_function
def shell_view(request):
    """type-10022026-Maurice: Expose only role-scoped shell metadata."""
    return Response({"title": f"{request.user.get_role_display()} workspace", "role": request.user.role})


@trace_function
def _ensure_demo_records(user=None):
    """type-10022026-Maurice: Lazily create deterministic synthetic display records."""
    defaults = [
        ("P001", "Demo Patient One", "2106-3", "2186-5", "en", "female", "straight", "woman", date(1980, 1, 1)),
        ("P002", "Demo Patient Two", "2054-5", "2135-2", "es", "male", "gay", "man", date(1975, 5, 5)),
    ]
    for values in defaults:
        patient, _ = Patient.objects.get_or_create(public_id=values[0], defaults={"display_name": values[1], "race": values[2], "ethnicity": values[3], "preferred_language": values[4], "sex": values[5], "sexual_orientation": values[6], "gender_identity": values[7], "birth_date": values[8]})
        AllergyIntolerance.objects.get_or_create(patient=patient, code="227493005", defaults={"label": "Demo allergy", "reaction": "Demo reaction"})
        Condition.objects.get_or_create(patient=patient, code="38341003", defaults={"label": "Demo condition"})
        Observation.objects.get_or_create(patient=patient, code="8310-5", defaults={"label": "Body temperature", "value": "Demo value", "unit": "Cel"})
        Device.objects.get_or_create(patient=patient, code="DEV-DEMO", defaults={"label": "Demo monitoring device"})
    if user is not None and user.role == User.Role.PATIENT:
        first = Patient.objects.get(public_id="P001")
        if first.owner_id is None:
            first.owner = user
            first.save(update_fields=["owner"])


@trace_function
def _can_read(patient, user, request=None):
    """type-10022026-Maurice: Apply the object-level role boundary before serialization."""
    return can_read(patient, user, request=request)


class PatientCollectionView(APIView):
    """type-10022026-Maurice: Clinician/admin search of all synthetic patients."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def get(self, request):
        _ensure_demo_records(request.user)
        if request.user.role == User.Role.PATIENT:
            patients = Patient.objects.filter(owner=request.user)
        else:
            query = request.query_params.get("q", "").strip()
            patients = Patient.objects.filter(display_name__icontains=query) if query else Patient.objects.all()
            if request.user.role == User.Role.CLINICIAN:
                patients = patients.filter(Q(restricted_access=False) | Q(clinician_assignments__clinician=request.user)).distinct()
        audit.append_audit_event(actor=request.user, action="read", resource_type="PatientSearch", resource_id=query or "all", correlation_id=getattr(request, "correlation_id", ""))
        log_event("records.search", component="records", operation="patient_search", outcome="success")
        return Response(PatientSerializer(patients, many=True).data)


class PatientDetailView(APIView):
    """type-10022026-Maurice: Role-scoped patient read and clinician demographic correction."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def get(self, request, public_id):
        started = time.monotonic()
        _ensure_demo_records(request.user)
        patient = Patient.objects.filter(public_id=public_id).first()
        if patient is None:
            return Response({"detail": "Patient not found."}, status=status.HTTP_404_NOT_FOUND)
        if not _can_read(patient, request.user, request=request):
            try:
                audit.append_audit_event(actor=request.user, action="deny", resource_type="Patient", resource_id=patient.public_id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
            except Exception:
                return Response({"detail": "Authorization service unavailable."}, status=503)
            return Response({"detail": "Not authorized for this patient."}, status=status.HTTP_403_FORBIDDEN)
        payload = PatientSerializer(patient).data
        payload["allergies"] = list(patient.allergyintolerance_records.values("code", "label", "reaction", "recorded_date"))
        payload["conditions"] = list(patient.condition_records.values("code", "label", "status", "recorded_date"))
        payload["observations"] = list(patient.observation_records.values("code", "label", "value", "unit", "recorded_date"))
        payload["devices"] = list(patient.device_records.values("code", "label", "status", "recorded_date"))
        active_ids = FamilyHistory.objects.filter(patient=patient).values_list("active_version_id", flat=True)
        payload["family_history"] = FamilyHistoryVersionSerializer(FamilyHistoryVersion.objects.filter(id__in=active_ids), many=True).data
        try:
            audit.append_audit_event(actor=request.user, action="read", resource_type="Patient", resource_id=patient.public_id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
        except Exception:
            return Response({"detail": "Authorization service unavailable."}, status=503)
        log_event("records.detail", component="records", operation="patient_detail", outcome="success", status=200, http_status=200, duration_ms=int((time.monotonic()-started)*1000), db_outcome="success", error_class="none")
        return Response(payload)

    @trace_function
    def patch(self, request, public_id):
        _ensure_demo_records(request.user)
        patient = Patient.objects.filter(public_id=public_id).first()
        if patient is None or not _can_read(patient, request.user, request=request):
            return Response({"detail": "Not authorized for this patient."}, status=status.HTTP_403_FORBIDDEN)
        if request.user.role == User.Role.PATIENT:
            return Response({"detail": "Patient demographics are read-only."}, status=status.HTTP_403_FORBIDDEN)
        serializer = PatientSerializer(patient, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                for field, value in serializer.validated_data.items():
                    setattr(patient, field, value)
                patient.full_clean()
                patient.save()
                audit.append_audit_event(actor=request.user, action="update", resource_type="Patient", resource_id=patient.public_id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
        except Exception as error:
            log_event("records.update.failure", outcome="failure", component="records", operation="patient_update", exception=error)
            return Response({"detail": "Unable to save patient record."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(PatientSerializer(patient).data)


class BreakGlassView(APIView):
    """type-10022026-Maurice: Emergency access is a clinician-only read grant."""
    permission_classes = [IsAuthenticated]

    def post(self, request, public_id):
        patient = Patient.objects.filter(public_id=public_id).first()
        if patient is None:
            return Response({"detail": "Patient not found."}, status=404)
        if request.user.role != User.Role.CLINICIAN or not request.user.is_active:
            try:
                audit.append_audit_event(actor=request.user, action="deny", resource_type="EmergencyAccessRequest", resource_id=public_id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
            except Exception:
                return Response({"detail": "Emergency access is unavailable."}, status=503)
            return Response({"detail": "Active clinician access required."}, status=403)
        try:
            grant = request_access(clinician=request.user, patient=patient, justification=request.data.get("justification"), correlation_id=getattr(request, "correlation_id", ""))
        except PermissionError:
            return Response({"detail": "Active clinician access required."}, status=403)
        except ValueError as error:
            return Response({"detail": str(error)}, status=400)
        return Response({"id": grant.pk, "state": grant.state, "expires_at": grant.expires_at.isoformat(), "patient": patient.public_id}, status=201)

    def delete(self, request, public_id):
        grant = EmergencyAccessRequest.objects.filter(patient__public_id=public_id, clinician=request.user, state=EmergencyAccessRequest.State.ACTIVE).order_by("-requested_at").first()
        if grant is None:
            return Response({"detail": "Active emergency grant not found."}, status=404)
        try:
            revoke_access(grant_id=grant.pk, actor=request.user, correlation_id=getattr(request, "correlation_id", ""))
        except PermissionError:
            return Response({"detail": "Not permitted."}, status=403)
        return Response({"state": EmergencyAccessRequest.State.REVOKED})


class BreakGlassReviewView(APIView):
    """type-10022026-Maurice: Admin-only reason-bearing review queue."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != User.Role.ADMIN:
            return Response({"detail": "Administrator access required."}, status=403)
        return Response([{"id": item.pk, "patient": item.patient.public_id, "clinician": item.clinician.username, "justification": item.justification, "state": item.state, "expires_at": item.expires_at.isoformat(), "suspicious": item.suspicious, "reviewed": item.reviewed_at is not None} for item in EmergencyAccessRequest.objects.select_related("patient", "clinician").filter(reviewed_at__isnull=True).order_by("requested_at")])

    def patch(self, request, grant_id):
        if request.user.role != User.Role.ADMIN:
            return Response({"detail": "Administrator access required."}, status=403)
        outcome = request.data.get("outcome")
        if outcome not in {choice for choice, _ in EmergencyAccessRequest.ReviewOutcome.choices}:
            return Response({"detail": "Review outcome is invalid."}, status=400)
        with transaction.atomic():
            grant = EmergencyAccessRequest.objects.select_for_update().select_related("patient").get(pk=grant_id)
            grant.reviewed_at = timezone.now(); grant.reviewed_by = request.user; grant.review_outcome = outcome; grant.suspicious = outcome == EmergencyAccessRequest.ReviewOutcome.SUSPICIOUS
            grant.save(update_fields=["reviewed_at", "reviewed_by", "review_outcome", "suspicious"])
            audit.append_audit_event(actor=request.user, action="review", resource_type="EmergencyAccessRequest", resource_id=grant.pk, patient=grant.patient, correlation_id=getattr(request, "correlation_id", ""))
        return Response({"id": grant.pk, "review_outcome": grant.review_outcome, "suspicious": grant.suspicious})


class PatientExportView(APIView):
    """type-10022026-Maurice: Request/status endpoint for authorized short-lived downloads."""
    permission_classes = [IsAuthenticated]

    def _patient(self, request, public_id):
        patient = Patient.objects.filter(public_id=public_id).first()
        allowed_role = request.user.role in {User.Role.CLINICIAN, User.Role.PATIENT}
        return patient if patient and allowed_role and normal_patient_access(patient, request.user) else None

    def post(self, request, public_id):
        started = time.monotonic()
        if (throttled := limited(request, "export", limit=10, window=60)) is not None:
            return throttled
        patient = self._patient(request, public_id)
        if patient is None:
            return Response({"detail": "Not authorized for this patient.", "retryable": False}, status=403)
        export_format = str(request.data.get("format", "")).lower()
        try:
            artifact = create_export(patient=patient, actor=request.user, export_format=export_format, correlation_id=getattr(request, "correlation_id", ""))
        except ValueError:
            return Response({"detail": "Format must be JSON or PDF.", "retryable": False}, status=400)
        except Exception:
            log_event("export.status.failure", outcome="failure", component="export", operation="request", duration_ms=int((time.monotonic() - started) * 1000))
            return Response({"detail": "Export unavailable; retry safely.", "retryable": True}, status=503)
        log_event("export.status.success", outcome="success", component="export", operation="request", duration_ms=int((time.monotonic() - started) * 1000))
        return Response(self._metadata(artifact, request), status=201)

    def get(self, request, public_id, artifact_id=None):
        patient = self._patient(request, public_id)
        artifact = PatientExport.objects.filter(artifact_id=artifact_id, patient=patient, requested_by=request.user).first() if patient and artifact_id else None
        if artifact is None:
            return Response({"detail": "Export not found or not authorized.", "retryable": False}, status=404)
        if artifact.expires_at <= timezone.now():
            purge_expired()
            return Response({"detail": "Export expired; request a new download.", "retryable": False}, status=410)
        return Response(self._metadata(artifact, request))

    @staticmethod
    def _metadata(artifact, request):
        return {"id": str(artifact.artifact_id), "status": "ready", "format": artifact.format, "sha256": artifact.sha256, "expires_at": artifact.expires_at.isoformat(), "download_url": f"/api/exports/{artifact.artifact_id}/download/"}


class PatientExportDownloadView(APIView):
    """type-10022026-Maurice: Serve exact immutable bytes only to the requesting actor."""
    permission_classes = [IsAuthenticated]

    def get(self, request, artifact_id):
        started = time.monotonic()
        artifact = PatientExport.objects.filter(artifact_id=artifact_id, requested_by=request.user).first()
        if artifact is None or (request.user.role == User.Role.PATIENT and artifact.patient.owner_id != request.user.id) or (request.user.role != User.Role.PATIENT and request.user.role != User.Role.CLINICIAN):
            return Response({"detail": "Export not found or not authorized.", "retryable": False}, status=404)
        if artifact.expires_at <= timezone.now():
            purge_expired()
            return Response({"detail": "Export expired; request a new download.", "retryable": False}, status=410)
        try:
            handle = open(artifact.path, "rb")
        except OSError as error:
            log_event("export.download.failure", outcome="failure", status=503, http_status=503, duration_ms=int((time.monotonic() - started) * 1000), component="export", operation="download", exception=error)
            return Response({"detail": "Export unavailable; retry safely.", "retryable": True}, status=503)
        response = FileResponse(handle, content_type="application/json" if artifact.format == "json" else "application/pdf")
        response["Content-Disposition"] = f'attachment; filename="patient-record.{artifact.format}"'
        response["X-Export-SHA256"] = artifact.sha256
        response["X-Export-Expires"] = artifact.expires_at.isoformat()
        log_event("export.download.success", outcome="success", component="export", operation="download", duration_ms=int((time.monotonic() - started) * 1000))
        return response


class DeviceCollectionView(APIView):
    """Ticket04: Role-scoped device CRUD with immutable versions and parse review."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def get(self, request, public_id):
        _ensure_demo_records(request.user)
        patient = Patient.objects.filter(public_id=public_id).first()
        if patient is None or not _can_read(patient, request.user, request=request):
            return Response({"detail": "Not authorized for this patient."}, status=status.HTTP_403_FORBIDDEN)
        audit.append_audit_event(actor=request.user, action="read", resource_type="Device", resource_id=patient.public_id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
        devices = []
        for device in patient.device_records.select_related("active_version"):
            if device.active_version:
                item = DeviceVersionSerializer(device.active_version).data
                item["device_id"] = device.pk
                devices.append(item)
            else:
                devices.append({"device_id": device.pk, "code": device.code, "label": device.label, "status": device.status, "recorded_date": device.recorded_date})
        return Response(devices)

    @trace_function
    def post(self, request, public_id):
        _ensure_demo_records(request.user)
        patient = Patient.objects.filter(public_id=public_id).first()
        if patient is None or not _can_read(patient, request.user) or request.user.role != User.Role.CLINICIAN:
            return Response({"detail": "Clinician access required."}, status=403)
        if not isinstance(request.data, dict) or not isinstance(request.data.get("udi"), str):
            # Ticket04 preserves the former read-only boundary for legacy payloads; creation requires UDI.
            return Response({"detail": "Device creation requires a UDI payload."}, status=405)
        if set(request.data) - {"udi", "code", "label", "status"}:
            return Response({"detail": "Unknown device fields are not accepted."}, status=400)
        if any(key in request.data and not isinstance(request.data[key], str) for key in ("code", "label", "status")):
            return Response({"detail": "Device fields must be strings."}, status=400)
        if len(request.data.get("udi", "")) > 256 or len(request.data.get("code", "UDI")) > 80 or len(request.data.get("label", "Implantable device")) > 160 or request.data.get("status", "active") not in {"active", "inactive", "entered-in-error"}:
            return Response({"detail": "Device fields exceed supported bounds."}, status=400)
        raw = request.data["udi"]
        result = parse_udi(raw)
        gudid = UnavailableGUDIDAdapter().enrich(result.device_identifier) if result.status == "parsed" else {"status": "not_requested", "synthetic_fields": {}}
        if result.status == "parsed" and Device.objects.filter(patient=patient, udi=raw).exists():
            return Response({"detail": "This device already exists."}, status=409)
        try:
            with transaction.atomic():
                device = Device.objects.create(patient=patient, code=request.data.get("code", result.device_identifier or "UDI"), label=request.data.get("label", "Implantable device"), status=request.data.get("status", "active"), udi=raw)
                version = DeviceVersion.objects.create(device=device, version=1, code=device.code, label=device.label, status=device.status, issuer=result.issuer, device_identifier=result.device_identifier, lot_number=result.lot_number, serial_number=result.serial_number, expiry_date=result.expiry_date, manufacture_date=result.manufacture_date, raw_input=raw, parser_version=result.parser_version, parse_status=result.status, parse_error_code=result.error_code, gudid_status=gudid["status"], created_by=request.user)
                device.active_version = version; device.save(update_fields=["active_version"])
                audit.append_audit_event(actor=request.user, action="create", resource_type="Device", resource_id=device.pk, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
                DeviceOutboxEvent.objects.create(device=device, version=version, kind="device.changed")
            return Response(DeviceVersionSerializer(version).data | {"device_id": device.pk}, status=201)
        except IntegrityError as error:
            log_event("device.create.failure", component="device", operation="create", outcome="conflict", db_outcome="rollback", exception=error)
            return Response({"detail": "This device already exists."}, status=409)
        except Exception as error:
            log_event("device.create.failure", component="device", operation="create", outcome="failure", db_outcome="rollback", exception=error)
            return Response({"detail": "Unable to save device."}, status=500)


class DeviceParseView(APIView):
    """Ticket04: Non-persistent parser preview; raw input never appears in logs."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def post(self, request, public_id):
        patient = Patient.objects.filter(public_id=public_id).first()
        if patient is None or not _can_read(patient, request.user):
            return Response({"detail": "Not authorized for this patient."}, status=403)
        if not isinstance(request.data, dict) or not isinstance(request.data.get("udi"), str):
            return Response({"udi": ["A UDI string is required."]}, status=400)
        result = parse_udi(request.data["udi"])
        gudid_status = "unavailable" if result.status == "parsed" else "not_requested"
        return Response({"status": result.status, "issuer": result.issuer, "device_identifier": result.device_identifier, "lot_number": result.lot_number, "serial_number": result.serial_number, "expiry_date": result.expiry_date, "manufacture_date": result.manufacture_date, "parser_version": result.parser_version, "error_code": result.error_code, "gudid_status": gudid_status})


class DeviceDetailView(APIView):
    """Ticket04: Clinician corrections append a version; patients remain read-only."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def patch(self, request, public_id, device_id):
        patient = Patient.objects.filter(public_id=public_id).first()
        if patient is None or not _can_read(patient, request.user, request=request):
            return Response({"detail": "Not authorized for this patient."}, status=403)
        if request.user.role != User.Role.CLINICIAN:
            return Response({"detail": "Clinician access required."}, status=403)
        try:
            with transaction.atomic():
                device = Device.objects.select_for_update().select_related("active_version").get(pk=device_id, patient=patient)
                previous = device.active_version
                if previous is None:
                    return Response({"detail": "Device has no version."}, status=409)
                unknown = set(request.data) - {"status", "code", "label", "udi"}
                if unknown or any(not isinstance(value, str) for value in request.data.values()):
                    return Response({"detail": "Invalid device correction."}, status=400)
                if len(request.data.get("udi", previous.raw_input)) > 256 or len(request.data.get("code", previous.code)) > 80 or len(request.data.get("label", previous.label)) > 160:
                    return Response({"detail": "Device fields exceed supported bounds."}, status=400)
                raw = request.data.get("udi", previous.raw_input)
                result = parse_udi(raw)
                status_value = request.data.get("status", previous.status)
                if status_value not in {"active", "inactive", "entered-in-error"}:
                    return Response({"status": ["Unsupported device lifecycle state."]}, status=400)
                version = DeviceVersion.objects.create(device=device, version=previous.version + 1, code=request.data.get("code", previous.code), label=request.data.get("label", previous.label), status=status_value, issuer=result.issuer if request.data.get("udi") else previous.issuer, device_identifier=result.device_identifier if request.data.get("udi") else previous.device_identifier, lot_number=result.lot_number if request.data.get("udi") else previous.lot_number, serial_number=result.serial_number if request.data.get("udi") else previous.serial_number, expiry_date=result.expiry_date if request.data.get("udi") else previous.expiry_date, manufacture_date=result.manufacture_date if request.data.get("udi") else previous.manufacture_date, raw_input=raw, parser_version=result.parser_version if request.data.get("udi") else previous.parser_version, parse_status=result.status if request.data.get("udi") else previous.parse_status, parse_error_code=result.error_code if request.data.get("udi") else previous.parse_error_code, created_by=request.user, supersedes=previous)
                device.active_version = version; device.status = status_value; device.code = version.code; device.label = version.label; device.udi = raw; device.save(update_fields=["active_version", "status", "code", "label", "udi"])
                audit.append_audit_event(actor=request.user, action="update", resource_type="Device", resource_id=device.pk, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
                DeviceOutboxEvent.objects.create(device=device, version=version, kind="device.changed")
            return Response(DeviceVersionSerializer(version).data | {"device_id": device.pk})
        except Device.DoesNotExist:
            return Response({"detail": "Device not found."}, status=404)


class DeviceHistoryView(APIView):
    """Ticket04: Authorized complete provenance history."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def get(self, request, public_id, device_id):
        patient = Patient.objects.filter(public_id=public_id).first()
        if patient is None or not _can_read(patient, request.user, request=request):
            return Response({"detail": "Not authorized for this patient."}, status=403)
        versions = DeviceVersion.objects.filter(device_id=device_id, device__patient=patient)
        audit.append_audit_event(actor=request.user, action="read", resource_type="DeviceHistory", resource_id=device_id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
        return Response(DeviceVersionSerializer(versions, many=True).data)


def _family_patient(request, public_id):
    """type-10022026-Maurice: Resolve family-history compartment without leaking existence."""
    patient = Patient.objects.filter(public_id=public_id).first()
    return patient if patient and _can_read(patient, request.user, request=request) else None


class FamilyHistoryCollectionView(APIView):
    """type-10022026-Maurice: Authorized family-history list/create with atomic audit/outbox."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def get(self, request, public_id):
        started = time.monotonic(); _ensure_demo_records(request.user); patient = _family_patient(request, public_id)
        if patient is None:
            return Response({"detail": "Not authorized for this patient."}, status=403)
        histories = FamilyHistory.objects.filter(patient=patient).select_related("active_version")
        query = request.query_params.get("code")
        if query:
            histories = histories.filter(active_version__condition_code=query)
        versions = [item.active_version for item in histories if item.active_version is not None]
        audit.append_audit_event(actor=request.user, action="read", resource_type="FamilyHistory", resource_id=public_id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
        log_event("family_history.list", component="family_history", operation="list", outcome="success", duration_ms=int((time.monotonic()-started)*1000), db_outcome="success")
        return Response(FamilyHistoryVersionSerializer(versions, many=True).data)

    @trace_function
    def post(self, request, public_id):
        started = time.monotonic(); _ensure_demo_records(request.user); patient = _family_patient(request, public_id)
        if patient is None or request.user.role != User.Role.CLINICIAN:
            return Response({"detail": "Clinician access required."}, status=403)
        serializer = FamilyHistoryVersionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        try:
            with transaction.atomic():
                history = FamilyHistory.objects.create(patient=patient)
                values = dict(serializer.validated_data); values["status"] = FamilyHistoryVersion.Status.ACTIVE
                version = FamilyHistoryVersion.objects.create(history=history, version=1, created_by=request.user, **values)
                history.active_version = version; history.save(update_fields=["active_version"])
                audit.append_audit_event(actor=request.user, action="create", resource_type="FamilyHistory", resource_id=history.pk, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
                FamilyHistoryOutboxEvent.objects.create(family_history=history, version=version, kind="family-history.changed")
            log_event("family_history.create", component="family_history", operation="create", outcome="success", duration_ms=int((time.monotonic()-started)*1000), db_outcome="success")
            return Response(FamilyHistoryVersionSerializer(version).data, status=201)
        except Exception as error:
            log_event("family_history.create.failure", component="family_history", operation="create", outcome="failure", duration_ms=int((time.monotonic()-started)*1000), db_outcome="failure", exception=error)
            return Response({"detail": "Unable to save family history."}, status=500)


class FamilyHistoryDetailView(APIView):
    """type-10022026-Maurice: Append corrections and enter-in-error versions; never delete."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, public_id, history_id):
        patient = _family_patient(request, public_id)
        if patient is None or request.user.role != User.Role.CLINICIAN:
            return Response({"detail": "Clinician access required."}, status=403)
        serializer = FamilyHistoryVersionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        try:
            with transaction.atomic():
                history = FamilyHistory.objects.select_for_update().select_related("active_version").get(pk=history_id, patient=patient)
                previous = history.active_version
                version = FamilyHistoryVersion.objects.create(history=history, version=previous.version + 1, supersedes=previous, created_by=request.user, **serializer.validated_data)
                history.active_version = version; history.save(update_fields=["active_version"])
                audit.append_audit_event(actor=request.user, action="update", resource_type="FamilyHistory", resource_id=history.pk, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
                FamilyHistoryOutboxEvent.objects.create(family_history=history, version=version, kind="family-history.changed")
            return Response(FamilyHistoryVersionSerializer(version).data)
        except FamilyHistory.DoesNotExist:
            return Response({"detail": "Family history not found."}, status=404)

    def delete(self, request, public_id, history_id):
        """type-10022026-Maurice: Explicitly reject destructive deletion."""
        return Response({"detail": "Family history is immutable; submit an entered-in-error correction."}, status=405)


class FamilyHistoryHistoryView(APIView):
    """type-10022026-Maurice: Return all provenance versions for an authorized entry."""
    permission_classes = [IsAuthenticated]

    def get(self, request, public_id, history_id):
        patient = _family_patient(request, public_id)
        if patient is None:
            return Response({"detail": "Not authorized for this patient."}, status=403)
        versions = FamilyHistoryVersion.objects.filter(history_id=history_id, history__patient=patient)
        return Response(FamilyHistoryVersionSerializer(versions, many=True).data)


def _medication_patient(request, public_id):
    """type-10022026-Maurice: Resolve medication scope without exposing unauthorized patient existence."""
    patient = Patient.objects.filter(public_id=public_id).first()
    if patient is None or not _can_read(patient, request.user, request=request):
        return None
    return patient


def _clinician(request):
    """type-10022026-Maurice: Only clinicians can mutate medication state."""
    return request.user.role == User.Role.CLINICIAN


class MedicationCollectionView(APIView):
    """type-10022026-Maurice: Medication drafts and authorized immutable history reads."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def get(self, request, public_id):
        patient = _medication_patient(request, public_id)
        if patient is None:
            return Response({"detail": "Not authorized for this patient."}, status=403)
        orders = MedicationOrder.objects.filter(patient=patient).select_related("active_version", "prescriber")
        result = [{"id": order.id, "prescriber": order.prescriber.username, "active_version": MedicationVersionSerializer(order.active_version).data if order.active_version else None} for order in orders]
        audit.append_audit_event(actor=request.user, action="read", resource_type="MedicationOrder", resource_id=public_id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
        log_event("medication.list", component="medication", operation="list", outcome="success")
        return Response(result)

    @trace_function
    def post(self, request, public_id):
        patient = _medication_patient(request, public_id)
        if patient is None or not _clinician(request):
            return Response({"detail": "Clinician access required."}, status=403)
        serializer = MedicationVersionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        try:
            with transaction.atomic():
                prescriber_id = request.data.get("prescriber_id")
                prescriber_name = request.data.get("prescriber")
                prescriber = User.objects.filter(role=User.Role.CLINICIAN).filter(pk=prescriber_id).first() if prescriber_id else User.objects.filter(role=User.Role.CLINICIAN, username=prescriber_name).first() if prescriber_name else request.user
                if prescriber.role != User.Role.CLINICIAN:
                    prescriber = None
                if prescriber is None:
                    return Response({"prescriber_id": ["Existing clinician prescriber is required."]}, status=400)
                order = MedicationOrder.objects.create(patient=patient, prescriber=prescriber)
                values = dict(serializer.validated_data)
                values["status"] = MedicationOrderVersion.Status.DRAFT
                version = MedicationOrderVersion.objects.create(order=order, version=1, created_by=request.user, **values)
                order.active_version = version
                order.save(update_fields=["active_version"])
                audit.append_audit_event(actor=request.user, action="create", resource_type="MedicationOrder", resource_id=order.id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
            log_event("medication.create", component="medication", operation="create", outcome="success")
            return Response({"id": order.id, "version": MedicationVersionSerializer(version).data}, status=201)
        except Exception as error:
            log_event("medication.create.failure", component="medication", operation="create", outcome="failure", exception=error)
            return Response({"detail": "Unable to save medication order."}, status=500)


class MedicationDetailView(APIView):
    """type-10022026-Maurice: Create a new version; no unsafe active signing is exposed."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def patch(self, request, public_id, order_id):
        patient = _medication_patient(request, public_id)
        if patient is None or not _clinician(request):
            return Response({"detail": "Clinician access required."}, status=403)
        serializer = MedicationVersionSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        try:
            with transaction.atomic():
                order = MedicationOrder.objects.select_for_update().select_related("active_version").get(id=order_id, patient=patient)
                if not order.active_version or order.active_version.status == MedicationOrderVersion.Status.CANCELLED:
                    return Response({"detail": "Cancelled medication orders cannot be changed."}, status=409)
                previous = order.active_version
                values = dict(serializer.validated_data)
                values["status"] = MedicationOrderVersion.Status.DRAFT
                version = MedicationOrderVersion.objects.create(order=order, version=previous.version + 1, supersedes=previous, created_by=request.user, **values)
                order.active_version = version
                order.save(update_fields=["active_version"])
                audit.append_audit_event(actor=request.user, action="update", resource_type="MedicationOrder", resource_id=order.id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
            log_event("medication.change", component="medication", operation="change", outcome="success")
            return Response(MedicationVersionSerializer(version).data)
        except MedicationOrder.DoesNotExist:
            return Response({"detail": "Medication order not found."}, status=404)
        except Exception as error:
            log_event("medication.change.failure", component="medication", operation="change", outcome="failure", exception=error)
            return Response({"detail": "Unable to change medication order."}, status=500)


class MedicationHistoryView(APIView):
    """type-10022026-Maurice: Return every immutable version, including supersession links."""
    permission_classes = [IsAuthenticated]

    def get(self, request, public_id, order_id):
        patient = _medication_patient(request, public_id)
        if patient is None:
            return Response({"detail": "Not authorized for this patient."}, status=403)
        versions = MedicationOrderVersion.objects.filter(order__id=order_id, order__patient=patient).select_related("supersedes")
        return Response(MedicationVersionSerializer(versions, many=True).data)


class MedicationCancelView(APIView):
    """type-10022026-Maurice: Append a terminal cancelled version atomically with its audit event."""
    permission_classes = [IsAuthenticated]

    def post(self, request, public_id, order_id):
        started = time.monotonic()
        patient = _medication_patient(request, public_id)
        if patient is None or not _clinician(request):
            return Response({"detail": "Clinician access required."}, status=403)
        try:
            with transaction.atomic():
                order = MedicationOrder.objects.select_for_update().select_related("active_version").get(id=order_id, patient=patient)
                previous = order.active_version
                if previous is None or previous.status == MedicationOrderVersion.Status.CANCELLED:
                    return Response({"detail": "Medication order is already cancelled."}, status=409)
                values = {field: getattr(previous, field) for field in ("medication_code", "medication_name", "dose", "dose_unit", "route", "frequency", "start_date", "quantity", "refills", "indication")}
                version = MedicationOrderVersion.objects.create(order=order, version=previous.version + 1, supersedes=previous, created_by=request.user, status=MedicationOrderVersion.Status.CANCELLED, **values)
                order.active_version = version
                order.save(update_fields=["active_version"])
                audit.append_audit_event(actor=request.user, action="cancel", resource_type="MedicationOrder", resource_id=order.id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
            return Response(MedicationVersionSerializer(version).data)
        except MedicationOrder.DoesNotExist:
            return Response({"detail": "Medication order not found."}, status=404)


class MedicationRefillView(APIView):
    """type-10022026-Maurice: Refill creates a new draft version and never signs it."""
    permission_classes = [IsAuthenticated]

    def post(self, request, public_id, order_id):
        patient = _medication_patient(request, public_id)
        if patient is None or not _clinician(request):
            return Response({"detail": "Clinician access required."}, status=403)
        try:
            with transaction.atomic():
                order = MedicationOrder.objects.select_for_update().select_related("active_version").get(id=order_id, patient=patient)
                previous = order.active_version
                if previous is None or previous.status == MedicationOrderVersion.Status.CANCELLED or previous.refills <= 0:
                    return Response({"detail": "Medication order is not eligible for refill."}, status=409)
                values = {field: getattr(previous, field) for field in ("medication_code", "medication_name", "dose", "dose_unit", "route", "frequency", "start_date", "quantity", "indication")}
                version = MedicationOrderVersion.objects.create(order=order, version=previous.version + 1, supersedes=previous, created_by=request.user, refills=previous.refills - 1, **values)
                order.active_version = version
                order.save(update_fields=["active_version"])
                audit.append_audit_event(actor=request.user, action="refill", resource_type="MedicationOrder", resource_id=order.id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
            return Response(MedicationVersionSerializer(version).data)
        except MedicationOrder.DoesNotExist:
            return Response({"detail": "Medication order not found."}, status=404)


class MedicationEvaluateView(APIView):
    """type-10022026-Maurice: Return persisted interaction findings for a draft."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def post(self, request, public_id, order_id):
        started = time.monotonic()
        patient = _medication_patient(request, public_id)
        if patient is None or not _clinician(request):
            return Response({"detail": "Clinician access required."}, status=403)
        try:
            version = MedicationOrder.objects.get(pk=order_id, patient=patient).active_version
            if version is None or version.status != MedicationOrderVersion.Status.DRAFT:
                return Response({"detail": "Only a draft medication can be evaluated."}, status=409)
            evaluation = evaluate_version(version=version, clinician=request.user)
            log_event("medication.evaluation.success", outcome="success", component="medication", operation="evaluate", status=200, http_status=200, duration_ms=int((time.monotonic()-started)*1000), db_outcome="success", error_class="none")
            return Response({"id": evaluation.id, "findings": evaluation.findings, "floor": evaluation.floor, "stale": False})
        except Exception as error:
            log_event("medication.evaluation.failure", outcome="failure", component="medication", operation="evaluate", status=503, http_status=503, duration_ms=int((time.monotonic()-started)*1000), db_outcome="failure", exception=error)
            return Response({"detail": "Safety evaluation unavailable; signing is blocked."}, status=503)


class MedicationAcknowledgeView(APIView):
    """type-10022026-Maurice: Capture explicit clinician acknowledgement."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def post(self, request, public_id, order_id):
        patient = _medication_patient(request, public_id)
        if patient is None or not _clinician(request):
            return Response({"detail": "Clinician access required."}, status=403)
        try:
            evaluation_id = request.data.get("evaluation_id")
            evaluation = InteractionEvaluation.objects.get(pk=evaluation_id, medication_version__order__patient=patient)
            acknowledgement = acknowledge_evaluation(evaluation_id=evaluation.pk, clinician=request.user)
            return Response({"id": acknowledgement.pk, "evaluation_id": evaluation.pk}, status=201)
        except Exception as error:
            log_event("medication.acknowledgement.failure", outcome="failure", component="medication", operation="acknowledge", exception=error)
            return Response({"detail": "Unable to record acknowledgement."}, status=400)


class MedicationSignView(APIView):
    """type-10022026-Maurice: Safely sign only after current fail-closed evaluation."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def post(self, request, public_id, order_id):
        patient = _medication_patient(request, public_id)
        if patient is None or not _clinician(request):
            return Response({"detail": "Clinician access required."}, status=403)
        try:
            order = MedicationOrder.objects.get(pk=order_id, patient=patient)
            version, evaluation = sign_version(order_id=order.pk, clinician=request.user, evaluation_id=request.data.get("evaluation_id"), acknowledgement=bool(request.data.get("acknowledged")), correlation_id=getattr(request, "correlation_id", ""))
            return Response({"version": MedicationVersionSerializer(version).data, "evaluation_id": evaluation.pk})
        except PermissionError as error:
            return Response({"detail": str(error)}, status=409)
        except Exception as error:
            log_event("medication.sign.unavailable", outcome="failure", component="medication", operation="sign", exception=error)
            return Response({"detail": "Signing unavailable; no medication was activated."}, status=503)


class InteractionRuleAdminView(APIView):
    """type-10022026-Maurice: Minimal administrator rule and floor APIs for Ticket 09 UI."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def get(self, request):
        if request.user.role != User.Role.ADMIN:
            return Response({"detail": "Administrator access required."}, status=403)
        configuration = AlertConfiguration.objects.get_or_create(singleton=True)[0]
        return Response({"rules": list(InteractionRule.objects.order_by("pk").values()), "severity_floor": configuration.severity_floor, "severity_choices": ["LOW", "MODERATE", "HIGH"]})

    @trace_function
    def post(self, request):
        if request.user.role != User.Role.ADMIN:
            return Response({"detail": "Administrator access required."}, status=403)
        if "severity_floor" in request.data:
            if request.data["severity_floor"] not in {"LOW", "MODERATE", "HIGH"}:
                return Response({"detail": "Invalid severity floor."}, status=400)
            configuration = AlertConfiguration.objects.get_or_create(singleton=True)[0]
            configuration.severity_floor = request.data["severity_floor"]
            configuration.save(update_fields=["severity_floor", "updated_at"])
            audit.append_audit_event(actor=request.user, action="update", resource_type="AlertConfiguration", resource_id=configuration.pk, correlation_id=getattr(request, "correlation_id", ""))
            log_event("admin.severity_floor.success", outcome="success", component="admin", operation="update")
            return Response({"severity_floor": configuration.severity_floor})
        allowed = {"kind", "medication_code", "related_medication_code", "allergy_code", "severity", "description", "active", "effective_from", "effective_to"}
        payload = {key: value for key, value in request.data.items() if key in allowed}
        if payload.get("severity") not in {"LOW", "MODERATE", "HIGH", "CRITICAL"}:
            return Response({"detail": "Invalid interaction severity."}, status=400)
        try:
            rule = InteractionRule(**payload)
            rule.full_clean()
            rule.save()
            audit.append_audit_event(actor=request.user, action="create", resource_type="InteractionRule", resource_id=rule.pk, correlation_id=getattr(request, "correlation_id", ""))
        except Exception as error:
            log_event("admin.interaction_rule.failure", outcome="failure", component="admin", operation="create", exception=error)
            return Response({"detail": "Invalid interaction rule."}, status=400)
        return Response({"id": rule.pk}, status=201)


class InteractionRuleDetailAdminView(APIView):
    """type-10022026-Maurice: Administrator-only safe rule edits and deactivation."""
    permission_classes = [IsAuthenticated]

    def _rule(self, request, rule_id):
        if request.user.role != User.Role.ADMIN:
            return None, Response({"detail": "Administrator access required."}, status=403)
        rule = InteractionRule.objects.filter(pk=rule_id).first()
        return (rule, None) if rule else (None, Response({"detail": "Interaction rule not found."}, status=404))

    @trace_function
    def patch(self, request, rule_id):
        rule, error = self._rule(request, rule_id)
        if error:
            return error
        allowed = {"kind", "medication_code", "related_medication_code", "allergy_code", "severity", "description", "active", "effective_from", "effective_to"}
        for key, value in request.data.items():
            if key in allowed:
                setattr(rule, key, value)
        if rule.severity not in {"LOW", "MODERATE", "HIGH", "CRITICAL"}:
            return Response({"detail": "Invalid interaction severity."}, status=400)
        try:
            rule.full_clean()
            rule.save()
            audit.append_audit_event(actor=request.user, action="update", resource_type="InteractionRule", resource_id=rule.pk, correlation_id=getattr(request, "correlation_id", ""))
        except Exception as error:
            log_event("admin.interaction_rule.failure", outcome="failure", component="admin", operation="update", exception=error)
            return Response({"detail": "Invalid interaction rule."}, status=400)
        return Response({"id": rule.pk, "active": rule.active, "severity": rule.severity})

    @trace_function
    def delete(self, request, rule_id):
        rule, error = self._rule(request, rule_id)
        if error:
            return error
        rule.active = False
        rule.save(update_fields=["active", "updated_at"])
        audit.append_audit_event(actor=request.user, action="update", resource_type="InteractionRule", resource_id=rule.pk, correlation_id=getattr(request, "correlation_id", ""))
        return Response(status=204)


class AdminUserView(APIView):
    """type-10022026-Maurice: Administrator-only user role and active-state management."""
    permission_classes = [IsAuthenticated]

    def _guard(self, request):
        return None if request.user.role == User.Role.ADMIN else Response({"detail": "Administrator access required."}, status=403)

    @trace_function
    def get(self, request):
        if (error := self._guard(request)) is not None:
            return error
        try:
            size = int(request.query_params.get("page_size", 50))
            page = max(int(request.query_params.get("page", 1)), 1)
            if not 1 <= size <= 100:
                raise ValueError
        except (TypeError, ValueError):
            return Response({"detail": "Invalid pagination."}, status=400)
        users = User.objects.order_by("id")
        start = (page - 1) * size
        rows = users[start:start + size]
        return Response({"count": users.count(), "page": page, "page_size": size, "results": [{"id": u.pk, "username": u.username, "role": u.role, "is_active": u.is_active, "is_staff": u.is_staff, "totp_enrolled": u.totp_enrolled} for u in rows]})

    @trace_function
    def post(self, request):
        if (error := self._guard(request)) is not None:
            return error
        username = str(request.data.get("username", "")).strip()
        password = str(request.data.get("password", ""))
        role = request.data.get("role", User.Role.PATIENT)
        if not username or len(username) > 150 or not password or role not in User.Role.values:
            return Response({"detail": "Username, password, and a supported role are required."}, status=400)
        if User.objects.filter(username=username).exists():
            return Response({"detail": "Unable to create user."}, status=400)
        try:
            with transaction.atomic():
                user = User(username=username, role=role, is_active=True)
                user.set_password(password)
                user.full_clean()
                user.save()
                audit.append_audit_event(actor=request.user, action="create", resource_type="User", resource_id=user.pk, correlation_id=getattr(request, "correlation_id", ""))
        except Exception as error:
            log_event("admin.user.failure", outcome="failure", component="admin", operation="create", exception=error)
            return Response({"detail": "Unable to create user."}, status=400)
        return Response({"id": user.pk, "username": user.username, "role": user.role, "is_active": user.is_active}, status=201)


class AdminUserDetailView(APIView):
    """type-10022026-Maurice: Prevent privilege escalation, self lockout, and last-admin removal."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def patch(self, request, user_id):
        if request.user.role != User.Role.ADMIN:
            return Response({"detail": "Administrator access required."}, status=403)
        target = User.objects.filter(pk=user_id).first()
        if target is None:
            return Response({"detail": "User not found."}, status=404)
        new_role = request.data.get("role", target.role)
        new_active = request.data.get("is_active", target.is_active)
        if new_role not in User.Role.values or not isinstance(new_active, bool):
            return Response({"detail": "Invalid user update."}, status=400)
        if target.pk == request.user.pk and (new_role != User.Role.ADMIN or not new_active):
            return Response({"detail": "You cannot remove your own administrator access."}, status=409)
        try:
            with transaction.atomic():
                # type-10022026-Maurice: Serialize last-admin decisions.
                active_admins = list(User.objects.select_for_update().filter(role=User.Role.ADMIN, is_active=True))
                if target.role == User.Role.ADMIN and (new_role != User.Role.ADMIN or not new_active) and len(active_admins) <= 1:
                    return Response({"detail": "At least one active administrator is required."}, status=409)
                target.role, target.is_active = new_role, new_active
                target.save(update_fields=["role", "is_active"])
                audit.append_audit_event(actor=request.user, action="update", resource_type="User", resource_id=target.pk, correlation_id=getattr(request, "correlation_id", ""))
        except Exception as error:
            log_event("admin.user.failure", outcome="failure", component="admin", operation="update", exception=error)
            return Response({"detail": "Unable to update user."}, status=400)
        return Response({"id": target.pk, "username": target.username, "role": target.role, "is_active": target.is_active})


class AuditReportView(APIView):
    """type-10022026-Maurice: Administrator-only paginated audit evidence view."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def get(self, request):
        if request.user.role != User.Role.ADMIN:
            return Response({"detail": "Administrator access required."}, status=status.HTTP_403_FORBIDDEN)
        events = AuditEvent.objects.select_related("actor", "patient")
        if request.query_params.get("action"):
            events = events.filter(action=request.query_params["action"])
        if request.query_params.get("patient"):
            events = events.filter(patient__public_id=request.query_params["patient"])
        if request.query_params.get("actor"):
            events = events.filter(actor__username=request.query_params["actor"])
        if request.query_params.get("resource_type"):
            events = events.filter(resource_type=request.query_params["resource_type"])
        if request.query_params.get("resource_id"):
            events = events.filter(resource_id=request.query_params["resource_id"])
        if request.query_params.get("from") and parse_datetime(request.query_params["from"]):
            events = events.filter(occurred_at__gte=parse_datetime(request.query_params["from"]))
        if request.query_params.get("to") and parse_datetime(request.query_params["to"]):
            events = events.filter(occurred_at__lte=parse_datetime(request.query_params["to"]))
        ordering = request.query_params.get("ordering", "-occurred_at")
        if ordering.lstrip("-") not in {"occurred_at", "sequence", "action", "resource_type"}:
            ordering = "-occurred_at"
        try:
            page_size = min(max(int(request.query_params.get("page_size", 50)), 1), 100)
            page_number = max(int(request.query_params.get("page", 1)), 1)
        except (TypeError, ValueError):
            return Response({"detail": "Invalid pagination."}, status=400)
        page = Paginator(events.order_by(ordering), page_size).get_page(page_number)
        return Response({"count": page.paginator.count, "next": page.next_page_number() if page.has_next() else None, "previous": page.previous_page_number() if page.has_previous() else None, "results": [{"sequence": e.sequence, "actor": e.actor.username if e.actor else None, "occurred_at": e.occurred_at.isoformat(), "patient": e.patient.public_id if e.patient else None, "action": e.action, "resource_type": e.resource_type, "resource_id": e.resource_id, "correlation_id": e.correlation_id, "previous_hash": e.previous_hash, "current_hash": e.current_hash} for e in page.object_list]})


class AuditVerifyView(APIView):
    """type-10022026-Maurice: Administrator-only chain integrity check."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def get(self, request):
        if request.user.role != User.Role.ADMIN:
            return Response({"detail": "Administrator access required."}, status=status.HTTP_403_FORBIDDEN)
        return Response(audit.verify_chain())


class QuestionnaireCollectionView(APIView):
    """Ticket05: Published questionnaires only; definitions are read-only to patients."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        questionnaires = Questionnaire.objects.filter(active_version__status="active").select_related("active_version").prefetch_related("active_version__items").order_by("code")
        return Response(QuestionnaireSerializer(questionnaires, many=True).data)


class QuestionnaireDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, questionnaire_id):
        questionnaire = Questionnaire.objects.filter(pk=questionnaire_id, active_version__status="active").select_related("active_version").prefetch_related("active_version__items").first()
        if not questionnaire:
            return Response({"detail": "Questionnaire not found."}, status=404)
        return Response(QuestionnaireSerializer(questionnaire).data)


def _questionnaire_patient(request, public_id):
    patient = Patient.objects.filter(public_id=public_id).first()
    if not patient:
        return None
    if request.user.role == User.Role.PATIENT and patient.owner_id != request.user.id:
        return None
    return patient


def _response_json(response_version):
    return QuestionnaireResponseVersionSerializer(response_version).data


class QuestionnaireResponseCollectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, public_id):
        patient = _questionnaire_patient(request, public_id)
        if not patient:
            return Response({"detail": "Not authorized for this patient."}, status=403)
        versions = QuestionnaireResponseVersion.objects.filter(response__patient=patient).select_related("questionnaire_version", "response__questionnaire").order_by("response_id", "-version")
        return Response([_response_json(item) for item in versions])

    def post(self, request, public_id):
        patient = _questionnaire_patient(request, public_id)
        if not patient or request.user.role != User.Role.PATIENT:
            return Response({"detail": "Only the patient may submit a response."}, status=403)
        try:
            questionnaire = Questionnaire.objects.get(pk=request.data.get("questionnaire_id"))
            response, version = create_response(patient=patient, questionnaire=questionnaire, actor=request.user, questionnaire_version_number=int(request.data.get("questionnaire_version")), answers=request.data.get("answers"), status=request.data.get("status", "draft"), correlation_id=getattr(request, "correlation_id", ""))
            return Response({"response_id": response.pk, **_response_json(version)}, status=201)
        except PermissionError:
            return Response({"detail": "Only the patient may submit a response."}, status=403)
        except (Questionnaire.DoesNotExist, ValueError, TypeError, QuestionnaireResponseVersion.DoesNotExist):
            return Response({"detail": "Invalid questionnaire response."}, status=400)


class QuestionnaireResponseDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, public_id, response_id):
        patient = _questionnaire_patient(request, public_id)
        response = QuestionnaireResponse.objects.filter(pk=response_id, patient=patient).first() if patient else None
        if not response or (request.user.role == User.Role.PATIENT and response.created_by_id != request.user.id):
            return Response({"detail": "Response not found."}, status=404)
        return Response({"response_id": response.pk, "versions": [_response_json(item) for item in response.versions.select_related("questionnaire_version").all()]})

    def post(self, request, public_id, response_id):
        patient = _questionnaire_patient(request, public_id)
        if not patient or request.user.role != User.Role.PATIENT:
            return Response({"detail": "Only the patient may correct a response."}, status=403)
        try:
            response = QuestionnaireResponse.objects.get(pk=response_id, patient=patient)
            _, version = create_response(patient=patient, questionnaire=response.questionnaire, actor=request.user, questionnaire_version_number=int(request.data.get("questionnaire_version")), answers=request.data.get("answers"), status=request.data.get("status", "submitted"), correction=response.pk, correlation_id=getattr(request, "correlation_id", ""))
            return Response({"response_id": response.pk, **_response_json(version)}, status=201)
        except PermissionError:
            return Response({"detail": "Only the patient may correct a response."}, status=403)
        except (QuestionnaireResponse.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Invalid response correction."}, status=400)


class QuestionnaireReviewQueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role != User.Role.CLINICIAN:
            return Response({"detail": "Clinician access required."}, status=403)
        versions = QuestionnaireResponseVersion.objects.filter(status="submitted", reviews__isnull=True).select_related("response__patient", "questionnaire_version", "response__questionnaire").order_by("created_at")
        return Response([{"id": item.id, "response_id": item.response_id, "patient": item.response.patient.public_id, **_response_json(item)} for item in versions])


class QuestionnaireReviewView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, response_version_id):
        try:
            review = review_response(response_version_id=response_version_id, reviewer=request.user, decision=request.data.get("decision"), reason=request.data.get("reason", ""), correlation_id=getattr(request, "correlation_id", ""))
            return Response({"id": review.id, "decision": review.decision, "reason": review.reason}, status=201)
        except QuestionnaireResponseVersion.DoesNotExist:
            return Response({"detail": "Response not found."}, status=404)
        except (PermissionError, ValueError):
            return Response({"detail": "Review is invalid."}, status=400)


def _amendment_json(item):
    """Return workflow metadata only; never expose source content or patient identifiers in telemetry."""
    return {"id": item.pk, "resource_type": item.resource_type, "resource_id": item.resource_id, "source_version": item.source_version, "source_reference": item.source_reference, "status": item.status, "submitted_at": item.submitted_at, "due_at": item.due_at, "overdue": item.due_at <= timezone.now() and item.status in {"submitted", "under_review"}, "reason": item.reason, "decision_reason": item.decision_reason, "accepted_version": item.accepted_version, "addendum": item.addendum}


def _amendment_patient(request, public_id):
    patient = Patient.objects.filter(public_id=public_id).first()
    return patient if patient and _can_read(patient, request.user, request=request) else None


class PatientAmendmentCollectionView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, public_id=None):
        if public_id is not None:
            patient = _amendment_patient(request, public_id)
            if not patient: return Response({"detail": "Amendment not found."}, status=404)
            items = PatientAmendment.objects.filter(patient=patient)
        else:
            if request.user.role != User.Role.CLINICIAN: return Response({"detail": "Clinician access required."}, status=403)
            items = PatientAmendment.objects.filter(status__in=["submitted", "under_review"])
        return Response([_amendment_json(item) for item in items.select_related("patient")])

    def post(self, request, public_id):
        patient = _amendment_patient(request, public_id)
        if not patient or request.user.role != User.Role.PATIENT or patient.owner_id != request.user.id:
            return Response({"detail": "Only the patient may request an amendment."}, status=403)
        try:
            item = create_amendment(patient=patient, actor=request.user, resource_type=request.data.get("resource_type"), resource_id=request.data.get("resource_id"), source_version=request.data.get("source_version"), reason=request.data.get("reason"), proposed_data=request.data.get("proposed_data"), correlation_id=getattr(request, "correlation_id", ""))
            return Response(_amendment_json(item), status=201)
        except PermissionError as error: return Response({"detail": str(error)}, status=403)
        except (ValueError, TypeError): return Response({"detail": "Amendment request is invalid."}, status=400)


class PatientAmendmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, amendment_id):
        item = PatientAmendment.objects.filter(pk=amendment_id).select_related("patient").first()
        if not item or not _can_read(item.patient, request.user): return Response({"detail": "Amendment not found."}, status=404)
        return Response(_amendment_json(item))

    def post(self, request, amendment_id):
        try:
            if request.data.get("action") == "start_review":
                return Response(_amendment_json(begin_review(amendment_id=amendment_id, reviewer=request.user)))
            item = decide_amendment(amendment_id=amendment_id, reviewer=request.user, decision=request.data.get("decision"), decision_reason=request.data.get("decision_reason", ""), correlation_id=getattr(request, "correlation_id", ""))
            return Response(_amendment_json(item))
        except PatientAmendment.DoesNotExist: return Response({"detail": "Amendment not found."}, status=404)
        except PermissionError as error: return Response({"detail": str(error)}, status=403)
        except ValueError as error: return Response({"detail": str(error)}, status=409 if "stale" in str(error) or "awaiting" in str(error) else 400)
