"""type-10022026-Maurice: Password plus mandatory TOTP session API."""
import pyotp
import time
from datetime import date
from django.contrib.auth import authenticate, login, logout
from django.core.paginator import Paginator
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.http import FileResponse
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from .logging import external_authenticate, log_event
from . import audit
from .models import AllergyIntolerance, AuditEvent, Condition, Device, Observation, Patient, User, MedicationOrder, MedicationOrderVersion, InteractionRule, AlertConfiguration, InteractionEvaluation, PatientExport
from .exports import create_export, purge_expired
from .interaction_safety import acknowledge_evaluation, evaluate_version, sign_version
from .serializers import LoginSerializer, OtpSerializer, PatientSerializer, MedicationVersionSerializer
from .tracing import trace_function
from .rate_limit import limited


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
    if not pyotp.TOTP(user.totp_secret).verify(otp, valid_window=0):
        log_event("auth.mfa.failure", user_role=user.role)
        return Response({"detail": "Invalid credentials or verification code."}, status=401)
    login(request, user)
    request.session["totp_authenticated"] = True
    log_event("auth.login.success", user_role=user.role)
    return Response({"role": user.role})


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
def _can_read(patient, user):
    """type-10022026-Maurice: Apply the object-level role boundary before serialization."""
    return user.role in (User.Role.CLINICIAN, User.Role.ADMIN) or (user.role == User.Role.PATIENT and patient.owner_id == user.id)


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
        if not _can_read(patient, request.user):
            return Response({"detail": "Not authorized for this patient."}, status=status.HTTP_403_FORBIDDEN)
        payload = PatientSerializer(patient).data
        payload["allergies"] = list(patient.allergyintolerance_records.values("code", "label", "reaction", "recorded_date"))
        payload["conditions"] = list(patient.condition_records.values("code", "label", "status", "recorded_date"))
        payload["observations"] = list(patient.observation_records.values("code", "label", "value", "unit", "recorded_date"))
        payload["devices"] = list(patient.device_records.values("code", "label", "status", "recorded_date"))
        audit.append_audit_event(actor=request.user, action="read", resource_type="Patient", resource_id=patient.public_id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
        log_event("records.detail", component="records", operation="patient_detail", outcome="success", status=200, http_status=200, duration_ms=int((time.monotonic()-started)*1000), db_outcome="success", error_class="none")
        return Response(payload)

    @trace_function
    def patch(self, request, public_id):
        _ensure_demo_records(request.user)
        patient = Patient.objects.filter(public_id=public_id).first()
        if patient is None or not _can_read(patient, request.user):
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


class PatientExportView(APIView):
    """type-10022026-Maurice: Request/status endpoint for authorized short-lived downloads."""
    permission_classes = [IsAuthenticated]

    def _patient(self, request, public_id):
        patient = Patient.objects.filter(public_id=public_id).first()
        return patient if patient and (request.user.role == User.Role.CLINICIAN or (request.user.role == User.Role.PATIENT and patient.owner_id == request.user.id)) else None

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
    """type-10022026-Maurice: Read-only synthetic device collection."""
    permission_classes = [IsAuthenticated]

    @trace_function
    def get(self, request, public_id):
        _ensure_demo_records(request.user)
        patient = Patient.objects.filter(public_id=public_id).first()
        if patient is None or not _can_read(patient, request.user):
            return Response({"detail": "Not authorized for this patient."}, status=status.HTTP_403_FORBIDDEN)
        audit.append_audit_event(actor=request.user, action="read", resource_type="Device", resource_id=patient.public_id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))
        return Response(list(patient.device_records.values("code", "label", "status", "recorded_date")))


def _medication_patient(request, public_id):
    """type-10022026-Maurice: Resolve medication scope without exposing unauthorized patient existence."""
    patient = Patient.objects.filter(public_id=public_id).first()
    if patient is None or not _can_read(patient, request.user):
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
