"""type-10022026-Maurice: SMART-on-FHIR authorization and developer portal."""
import secrets
import hashlib
import base64
import hmac
import time
import unicodedata
import re
from datetime import date
from datetime import timedelta
from urllib.parse import urlencode, urlsplit

from django.contrib.auth.hashers import check_password, make_password
from django.http import JsonResponse
from django.core.cache import cache
from django.utils import timezone
from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from oauth2_provider.models import AccessToken, Application, Grant, RefreshToken, set_token_value

from . import audit
from .logging import log_event
from .models import Patient, SmartTokenContext, User
from .tracing import trace_function
from .rate_limit import limited

SCOPES = frozenset(("openid", "fhirUser", "patient/Patient.r", "patient/Patient.s", "patient/MedicationRequest.r", "patient/AllergyIntolerance.r", "patient/Condition.r", "patient/Observation.r", "patient/Device.r", "patient/Questionnaire.r", "patient/QuestionnaireResponse.r"))
RESOURCE_SCOPES = {"Patient": "patient/Patient.r", "MedicationRequest": "patient/MedicationRequest.r", "AllergyIntolerance": "patient/AllergyIntolerance.r", "Condition": "patient/Condition.r", "Observation": "patient/Observation.r", "Device": "patient/Device.r", "FamilyMemberHistory": "patient/FamilyMemberHistory.r", "Questionnaire": "patient/Questionnaire.r", "QuestionnaireResponse": "patient/QuestionnaireResponse.r"}


def _event(name, started, outcome, error=None, status=500):
    """type-10022026-Maurice: Log external SMART lifecycle without sensitive inputs."""
    values = {"component": "smart", "operation": name, "outcome": outcome, "status": status, "http_status": status, "duration_ms": int((time.monotonic() - started) * 1000)}
    if error is not None:
        values["exception"] = error
    log_event(f"smart.{name}.{outcome}", **values)


def _audit(actor, action, resource, request, patient=None):
    """type-10022026-Maurice: Fail closed when SMART security evidence cannot be persisted."""
    return audit.append_audit_event(actor=actor, action=action, resource_type=resource, resource_id="smart", patient=patient, correlation_id=getattr(request, "correlation_id", ""))


SELECTION_SCOPE = "patient/Patient.s"
_SELECTION_FIELDS = {"identifier", "given_name", "family_name", "birth_date"}
_SELECTION_NO_RESULT = "No matching patient."


def _selection_request_id(request):
    return getattr(request, "correlation_id", "") or secrets.token_hex(16)


def _normalize_name(value):
    """Ticket09: NFKC + casefold + collapsed Unicode whitespace, exact only."""
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def _selection_parts(patient):
    if patient.given_name and patient.family_name:
        return patient.given_name, patient.family_name
    pieces = patient.display_name.split()
    return (" ".join(pieces[:-1]), pieces[-1]) if len(pieces) >= 2 else ("", "")


def _selection_limited(request, app):
    address = request.META.get("REMOTE_ADDR", "unknown").split(",", 1)[0][:64]
    actor = str(request.user.pk) if getattr(request.user, "is_authenticated", False) else "anonymous"
    key = f"ehr:rate:patient-selection:{app.client_id}:{actor}:{address}"
    try:
        if cache.add(key, 1, 60):
            return None
        count = cache.incr(key)
        if count > 10:
            log_event("security.rate_limit", outcome="blocked", component="security", operation="patient_selection")
            return Response({"detail": "Too many requests; retry later."}, status=429)
    except Exception:
        return Response({"detail": "Patient selection is temporarily unavailable."}, status=503)
    return None


class PatientSelectionView(APIView):
    """Ticket09: exact, non-enumerating selection for registered SMART apps."""
    # Allow the view to record unauthenticated/expired-token attempts; selection
    # authorization itself remains fail-closed in _forbidden().
    permission_classes = [AllowAny]

    def _forbidden(self, request, request_id, status=403):
        try:
            _audit(request.user if request.user.is_authenticated else None, "deny", "PatientSelection", request)
        except Exception:
            return Response({"detail": "Patient selection is temporarily unavailable.", "request_id": request_id}, status=503)
        return Response({"detail": "Patient selection is not permitted.", "request_id": request_id}, status=status)

    def post(self, request):
        request_id = _selection_request_id(request)
        token = getattr(request, "auth", None)
        app = getattr(token, "application", None)
        # Authorization is deliberately complete before parsing/querying demographics.
        if not isinstance(token, AccessToken) or not app or app.registration_source != "manual" or not app.user.is_active or not request.user.is_active:
            return self._forbidden(request, request_id)
        if token.expires <= timezone.now() or SELECTION_SCOPE not in getattr(request, "smart_scopes", frozenset()):
            return self._forbidden(request, request_id)
        try:
            context = token.mfa_context
            if context.user_id != request.user.pk or context.application_id != app.pk or context.mfa_generation != request.user.mfa_generation:
                return self._forbidden(request, request_id)
        except SmartTokenContext.DoesNotExist:
            return self._forbidden(request, request_id)
        if (limited_response := _selection_limited(request, app)) is not None:
            try:
                _audit(request.user, "deny", "PatientSelection", request)
            except Exception:
                return Response({"detail": "Patient selection is temporarily unavailable.", "request_id": request_id}, status=503)
            return limited_response

        payload = request.data if isinstance(request.data, dict) else {}
        if set(payload) - _SELECTION_FIELDS:
            return self._forbidden(request, request_id, 400)
        identifier = payload.get("identifier")
        given = payload.get("given_name")
        family = payload.get("family_name")
        birth = payload.get("birth_date")
        has_identifier = "identifier" in payload
        has_name = "given_name" in payload or "family_name" in payload
        valid_identifier = isinstance(identifier, str) and bool(re.fullmatch(r"[A-Za-z0-9._:-]{1,64}", identifier))
        valid_names = all(isinstance(value, str) and 1 <= len(value) <= 80 and _normalize_name(value) for value in (given, family))
        if has_identifier == has_name or not birth or not isinstance(birth, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", birth):
            valid = False
        else:
            valid = valid_identifier if identifier else valid_names
        try:
            parsed_birth = date.fromisoformat(birth) if valid else None
        except ValueError:
            parsed_birth = None
            valid = False
        matches = []
        if valid:
            queryset = Patient.objects.filter(birth_date=parsed_birth)
            if identifier:
                matches = list(queryset.filter(public_id=identifier)[:2])
            else:
                given_normalized, family_normalized = _normalize_name(given), _normalize_name(family)
                for patient in queryset.iterator():
                    patient_given, patient_family = _selection_parts(patient)
                    if _normalize_name(patient_given) == given_normalized and _normalize_name(patient_family) == family_normalized:
                        matches.append(patient)
                        if len(matches) == 2:
                            break
        if len(matches) != 1:
            try:
                _audit(request.user, "deny", "PatientSelection", request)
            except Exception:
                return Response({"detail": "Patient selection is temporarily unavailable.", "request_id": request_id}, status=503)
            return Response({"detail": _SELECTION_NO_RESULT, "request_id": request_id}, status=404)
        try:
            _audit(request.user, "read", "PatientSelection", request)
        except Exception:
            return Response({"detail": "Patient selection is temporarily unavailable.", "request_id": request_id}, status=503)
        # Match FHIR's opaque Patient identifier format; never return public_id or demographics.
        opaque_id = base64.urlsafe_b64encode(f"Patient:{matches[0].pk}".encode()).decode().rstrip("=")
        signature = hmac.new(settings.SECRET_KEY.encode(), f"Patient:{matches[0].pk}".encode(), hashlib.sha256).hexdigest()[:16]
        return Response({"patient_id": f"{opaque_id}-{signature}", "request_id": request_id}, status=200)


def _redirects(value):
    """type-10022026-Maurice: Preserve redirect URI octets for exact comparison."""
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [line.strip() for line in str(value or "").splitlines() if line.strip()]


def _valid_redirect(uri, app):
    """type-10022026-Maurice: Require an exact registered redirect, never a prefix or host match."""
    return bool(uri) and uri in _redirects(app.redirect_uris) and not any(c in uri for c in ("\r", "\n"))


@trace_function
def _pkce_challenge(value):
    """type-10022026-Maurice: Compute RFC 7636 S256 without retaining verifier material."""
    return base64.urlsafe_b64encode(hashlib.sha256(value.encode("ascii")).digest()).rstrip(b"=").decode("ascii")


class DeveloperAppsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """type-10022026-Maurice: List only the authenticated developer's registrations."""
        return Response([{"client_id": a.client_id, "name": a.name, "redirect_uris": _redirects(a.redirect_uris), "scopes": sorted(SCOPES), "client_type": a.client_type} for a in Application.objects.filter(user=request.user, registration_source="manual")])

    def post(self, request):
        """type-10022026-Maurice: Register a confidential app and reveal its secret only in this response."""
        started = time.monotonic()
        name, redirects = str(request.data.get("name", "")).strip(), _redirects(request.data.get("redirect_uris"))
        requested = set(str(request.data.get("scope", " ".join(SCOPES))).split())
        if not name or not redirects or not requested.issubset(SCOPES) or not {"openid", "fhirUser"}.issubset(requested):
            _event("app", started, "failure")
            return Response({"detail": "Valid name, exact HTTPS redirects and approved SMART scopes are required."}, status=400)
        if any(urlsplit(uri).scheme != "https" for uri in redirects):
            return Response({"detail": "Redirect URIs must use HTTPS."}, status=400)
        secret = secrets.token_urlsafe(48)
        app = Application.objects.create(user=request.user, name=name, redirect_uris="\n".join(redirects), client_type=Application.CLIENT_CONFIDENTIAL, authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE, client_secret=make_password(secret), hash_client_secret=True, registration_source="manual")
        _audit(request.user, "create", "SMARTApp", request)
        _event("app", started, "success")
        return Response({"client_id": app.client_id, "client_secret": secret, "name": name, "redirect_uris": redirects, "scope": " ".join(sorted(requested))}, status=201)


class DeveloperAppRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, client_id):
        """type-10022026-Maurice: Revoke an app and its outstanding tokens without exposing token material."""
        started = time.monotonic()
        app = Application.objects.filter(client_id=client_id, user=request.user).first()
        if not app:
            return Response({"detail": "Application not found."}, status=404)
        AccessToken.objects.filter(application=app).delete()
        RefreshToken.objects.filter(application=app).update(revoked=timezone.now())
        app.delete()
        _audit(request.user, "delete", "SMARTApp", request)
        _event("revoke", started, "success")
        return Response(status=204)


class AuthorizationView(APIView):
    permission_classes = [IsAuthenticated]

    @trace_function
    def _request(self, request):
        """type-10022026-Maurice: Validate OAuth request shape before any consent or queryset work."""
        app = Application.objects.filter(client_id=request.data.get("client_id") or request.query_params.get("client_id"), registration_source="manual").first()
        redirect = request.data.get("redirect_uri") or request.query_params.get("redirect_uri")
        scope = set(str(request.data.get("scope") or request.query_params.get("scope") or "").split())
        challenge = request.data.get("code_challenge") or request.query_params.get("code_challenge")
        method = request.data.get("code_challenge_method") or request.query_params.get("code_challenge_method")
        # type-10022026-Maurice: This portal registers confidential clients, but
        # still binds every code to RFC 7636 S256; plain and missing PKCE are rejected.
        if not app or not _valid_redirect(redirect, app) or not scope or not scope.issubset(SCOPES) or not challenge or method != "S256":
            return None, None, None, None
        if not request.user.totp_enrolled or not request.session.get("totp_authenticated"):
            return None, None, None, None
        return app, redirect, scope, challenge

    @trace_function
    def get(self, request):
        """type-10022026-Maurice: Return explicit app identity, scope list and bounded patient context."""
        started = time.monotonic(); app, redirect, scope, challenge = self._request(request)
        if not app:
            _event("authorize", started, "failure", status=400)
            return Response({"detail": "Invalid authorization request."}, status=400)
        patient_id = request.query_params.get("patient") or request.query_params.get("launch")
        patient = Patient.objects.filter(public_id=patient_id).first() if patient_id else None
        if patient_id and (patient is None or (request.user.role == User.Role.PATIENT and patient.owner_id != request.user.id)):
            _event("authorize", started, "failure", status=403)
            return Response({"detail": "Invalid patient context."}, status=403)
        _event("consent_display", started, "success", status=200)
        return Response({"consent_required": True, "app": {"client_id": app.client_id, "name": app.name}, "scopes": sorted(scope), "patient": patient.public_id if patient else None, "redirect_uri": redirect})

    @trace_function
    def post(self, request):
        """type-10022026-Maurice: Approve or deny once, recording both decisions without token material."""
        started = time.monotonic()
        app, redirect, scope, challenge = self._request(request)
        if not app:
            _event("authorize", started, "failure", status=400)
            return Response({"detail": "Invalid authorization request."}, status=400)
        if str(request.data.get("decision", "")).lower() != "approve":
            try:
                _audit(request.user, "deny", "SMARTConsent", request)
            except Exception:
                _event("authorize", started, "failure", "audit_unavailable", 503)
                return Response({"detail": "Authorization evidence is unavailable."}, status=503)
            _event("authorize", started, "denied", status=403)
            return Response({"error": "access_denied"}, status=403)
        patient_id = request.data.get("patient") or request.query_params.get("patient")
        patient = Patient.objects.filter(public_id=patient_id).first() if patient_id else None
        if patient_id and (not patient or (request.user.role == User.Role.PATIENT and patient.owner_id != request.user.id)):
            return Response({"detail": "Invalid patient context."}, status=403)
        from django.db import transaction
        try:
            with transaction.atomic():
                grant = Grant.objects.create(user=request.user, application=app, code=secrets.token_urlsafe(48), expires=timezone.now() + timedelta(minutes=5), redirect_uri=redirect, scope=" ".join(sorted(scope)), resource=[patient.public_id] if patient else [], code_challenge=challenge, code_challenge_method="S256")
                _audit(request.user, "consent", "SMARTConsent", request, patient)
        except Exception:
            _event("authorize", started, "failure", "audit_unavailable", 503)
            return Response({"detail": "Authorization evidence is unavailable."}, status=503)
        _event("authorize", started, "success", status=200)
        separator = "&" if "?" in redirect else "?"
        return Response({"redirect": f"{redirect}{separator}{urlencode({'code': grant.code, 'state': request.data.get('state', '')})}"})


def _client(request, app):
    """type-10022026-Maurice: Verify a confidential client secret without logging it."""
    supplied = request.data.get("client_secret", "")
    return app and app.client_type == Application.CLIENT_CONFIDENTIAL and check_password(str(supplied), app.client_secret)


class TokenView(APIView):
    permission_classes = [AllowAny]

    @trace_function
    def post(self, request):
        """type-10022026-Maurice: Exchange one-time grants or rotate refresh tokens."""
        if (throttled := limited(request, "oauth-token", limit=20, window=60)) is not None:
            return throttled
        started = time.monotonic()
        app = Application.objects.filter(client_id=request.data.get("client_id"), registration_source="manual").first()
        if not _client(request, app):
            _event("token", started, "failure", status=401)
            return Response({"error": "invalid_client"}, status=401)
        grant = None
        mfa_generation = None
        if request.data.get("grant_type") == "authorization_code":
            verifier = str(request.data.get("code_verifier", ""))
            if not verifier or len(verifier) > 128:
                _event("token", started, "failure", status=400)
                return Response({"error": "invalid_grant"}, status=400)
            from django.db import transaction
            with transaction.atomic():
                grant = Grant.objects.select_for_update().select_related("user").filter(application=app, code=request.data.get("code"), redirect_uri=request.data.get("redirect_uri"), expires__gt=timezone.now(), code_challenge_method="S256").first()
                try:
                    valid_verifier = _pkce_challenge(verifier)
                except (UnicodeEncodeError, ValueError):
                    valid_verifier = ""
                if not grant or not hmac.compare_digest(valid_verifier, grant.code_challenge):
                    _event("token", started, "failure", status=400)
                    return Response({"error": "invalid_grant"}, status=400)
                grant.delete()
                user, scope, resource = grant.user, grant.scope, grant.resource
                mfa_generation = user.mfa_generation
        elif request.data.get("grant_type") == "refresh_token":
            from django.conf import settings
            from django.db import transaction
            with transaction.atomic():
                refresh = RefreshToken.objects.select_for_update(of=("self",)).select_related("user", "access_token").filter(application=app, token_checksum=hashlib.sha256(str(request.data.get("refresh_token", "")).encode()).hexdigest(), revoked__isnull=True, created__gt=timezone.now() - timedelta(seconds=settings.OAUTH2_PROVIDER["REFRESH_TOKEN_EXPIRE_SECONDS"])).first()
                if not refresh:
                    _event("refresh", started, "failure", status=400)
                    return Response({"error": "invalid_grant"}, status=400)
                refresh.revoked = timezone.now(); refresh.save(update_fields=["revoked"])
                user, scope, resource = refresh.user, refresh.access_token.scope, refresh.access_token.resource
                try:
                    mfa_generation = refresh.access_token.mfa_context.mfa_generation
                except SmartTokenContext.DoesNotExist:
                    _event("refresh", started, "failure", status=400)
                    return Response({"error": "invalid_grant"}, status=400)
        else:
            _event("token", started, "failure", status=400)
            return Response({"error": "unsupported_grant_type"}, status=400)
        from django.db import transaction
        access_value, refresh_value = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
        try:
            with transaction.atomic():
                access = AccessToken(user=user, application=app, expires=timezone.now() + timedelta(seconds=300), scope=scope, resource=resource)
                set_token_value(access, access_value); access.save()
                SmartTokenContext.objects.create(access_token=access, user=user, application=app, mfa_generation=mfa_generation, completed_at=timezone.now())
                refresh = RefreshToken(user=user, application=app, access_token=access, revoked=None, resource=resource)
                set_token_value(refresh, refresh_value); refresh.save()
                _audit(user, "token", "SMARTToken", request)
        except Exception:
            _event("token", started, "failure", "audit_unavailable", 503)
            return Response({"error": "temporarily_unavailable"}, status=503)
        _event("token", started, "success", status=200)
        return Response({"access_token": access_value, "token_type": "Bearer", "expires_in": 300, "refresh_token": refresh_value, "scope": scope})


class RevokeTokenView(APIView):
    permission_classes = [AllowAny]

    @trace_function
    def post(self, request):
        """type-10022026-Maurice: Revoke bearer or refresh material idempotently."""
        started = time.monotonic(); value = str(request.data.get("token", ""))
        checksum = hashlib.sha256(value.encode()).hexdigest()
        access_ids = list(AccessToken.objects.filter(token_checksum=checksum).values_list("id", flat=True))
        AccessToken.objects.filter(id__in=access_ids).delete()
        RefreshToken.objects.filter(token_checksum=checksum).update(revoked=timezone.now())
        RefreshToken.objects.filter(access_token_id__in=access_ids).update(revoked=timezone.now())
        _event("revoke", started, "success", status=200)
        return Response(status=200)


class LaunchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """type-10022026-Maurice: Create a short-lived launch handoff without putting tokens in browser storage."""
        if not request.user.totp_enrolled or not request.session.get("totp_authenticated"):
            return Response({"detail": "A current TOTP-authenticated session is required."}, status=401)
        patient = request.query_params.get("patient", "")
        if patient and not Patient.objects.filter(public_id=patient).exists():
            return Response({"detail": "Invalid patient context."}, status=400)
        return Response({"launch": "ehr" if patient else "standalone", "patient": patient or None, "authorization_endpoint": "/oauth/authorize/"})


def smart_configuration(request):
    """type-10022026-Maurice: Publish SMART discovery endpoints without client-specific data."""
    base = request.build_absolute_uri("/").rstrip("/")
    return JsonResponse({"authorization_endpoint": f"{base}/oauth/authorize/", "token_endpoint": f"{base}/oauth/token/", "revocation_endpoint": f"{base}/oauth/revoke_token/", "scopes_supported": sorted(SCOPES), "capabilities": ["launch-ehr", "launch-standalone", "client-public", "client-confidential"]})


def capability_statement(request):
    """type-10022026-Maurice: Advertise the read-only SMART FHIR capability surface."""
    return JsonResponse({"resourceType": "CapabilityStatement", "status": "active", "kind": "instance", "format": ["json", "application/fhir+json"], "rest": [{"mode": "server", "security": {"extension": [{"url": "http://fhir-registry.smarthealthit.org/StructureDefinition/oauth-uris", "extension": [{"url": "authorize", "valueUri": request.build_absolute_uri("/oauth/authorize/")}, {"url": "token", "valueUri": request.build_absolute_uri("/oauth/token/")}]}]}, "resource": [{"type": resource, "interaction": [{"code": "read"}, {"code": "search-type"}]} for resource in ("Patient", "MedicationRequest", "AllergyIntolerance", "Condition", "Observation", "Device")]}]})
