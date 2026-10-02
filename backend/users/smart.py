"""type-10022026-Maurice: SMART-on-FHIR authorization and developer portal."""
import secrets
import hashlib
import base64
import hmac
import time
from datetime import timedelta
from urllib.parse import urlencode, urlsplit

from django.contrib.auth.hashers import check_password, make_password
from django.http import JsonResponse
from django.utils import timezone
from django.conf import settings
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from oauth2_provider.models import AccessToken, Application, Grant, RefreshToken, set_token_value

from . import audit
from .logging import log_event
from .models import Patient, User
from .tracing import trace_function
from .rate_limit import limited

SCOPES = frozenset(("openid", "fhirUser", "patient/Patient.r", "patient/MedicationRequest.r", "patient/AllergyIntolerance.r", "patient/Condition.r", "patient/Observation.r", "patient/Device.r"))
RESOURCE_SCOPES = {"Patient": "patient/Patient.r", "MedicationRequest": "patient/MedicationRequest.r", "AllergyIntolerance": "patient/AllergyIntolerance.r", "Condition": "patient/Condition.r", "Observation": "patient/Observation.r", "Device": "patient/Device.r"}


def _event(name, started, outcome, error=None, status=500):
    """type-10022026-Maurice: Log external SMART lifecycle without sensitive inputs."""
    values = {"component": "smart", "operation": name, "outcome": outcome, "status": status, "http_status": status, "duration_ms": int((time.monotonic() - started) * 1000)}
    if error is not None:
        values["exception"] = error
    log_event(f"smart.{name}.{outcome}", **values)


def _audit(actor, action, resource, request, patient=None):
    """type-10022026-Maurice: Fail closed when SMART security evidence cannot be persisted."""
    return audit.append_audit_event(actor=actor, action=action, resource_type=resource, resource_id="smart", patient=patient, correlation_id=getattr(request, "correlation_id", ""))


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
        if not name or not redirects or not requested.issubset(SCOPES) or not SCOPES.issubset(requested):
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
        else:
            _event("token", started, "failure", status=400)
            return Response({"error": "unsupported_grant_type"}, status=400)
        from django.db import transaction
        access_value, refresh_value = secrets.token_urlsafe(48), secrets.token_urlsafe(48)
        try:
            with transaction.atomic():
                access = AccessToken(user=user, application=app, expires=timezone.now() + timedelta(seconds=300), scope=scope, resource=resource)
                set_token_value(access, access_value); access.save()
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
