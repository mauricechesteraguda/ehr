"""Ticket07 expansion: WebAuthn ceremonies and deterministic recovery boundaries."""
import base64
import hashlib
import json
import secrets
from datetime import timedelta

import webauthn
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.utils import timezone
from webauthn.helpers import options_to_json
from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement, AttestationConveyancePreference

from . import audit
from .logging import log_event
from .models import SmsRecoveryChallenge, User, WebAuthnChallenge, WebAuthnCredential
from .rate_limit import limited

def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))

def _session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key

def _challenge(request, ceremony, user=None):
    raw = secrets.token_bytes(32)
    WebAuthnChallenge.objects.create(user=user, session_key=_session(request), challenge_hash=hashlib.sha256(raw).hexdigest(), ceremony=ceremony, expires_at=timezone.now() + timedelta(seconds=settings.WEBAUTHN_CHALLENGE_TTL_SECONDS))
    return raw

def _options(options):
    return json.loads(options_to_json(options))

def registration_options(request):
    user = request.user
    challenge = _challenge(request, "register", user)
    existing = [PublicKeyCredentialDescriptor(id=c.credential_id, transports=c.transports) for c in user.webauthn_credentials.filter(revoked_at__isnull=True)]
    return _options(webauthn.generate_registration_options(rp_id=settings.WEBAUTHN_RP_ID, rp_name="EHR", user_name=user.username, user_id=str(user.pk).encode(), user_display_name=user.username, challenge=challenge, attestation=AttestationConveyancePreference.NONE, exclude_credentials=existing))

def authentication_options(request, user):
    challenge = _challenge(request, "authenticate", user)
    creds = [PublicKeyCredentialDescriptor(id=c.credential_id, transports=c.transports) for c in user.webauthn_credentials.filter(revoked_at__isnull=True)]
    return _options(webauthn.generate_authentication_options(rp_id=settings.WEBAUTHN_RP_ID, challenge=challenge, allow_credentials=creds, user_verification=UserVerificationRequirement.REQUIRED))

def consume(request, raw, ceremony, user):
    item = WebAuthnChallenge.objects.select_for_update().filter(challenge_hash=hashlib.sha256(raw).hexdigest(), ceremony=ceremony, user=user, session_key=_session(request), used_at__isnull=True, expires_at__gt=timezone.now()).first()
    if not item:
        raise ValueError("expired_or_replayed_challenge")
    item.used_at = timezone.now(); item.save(update_fields=["used_at"])

def verify_registration(request, payload, name="Passkey"):
    # The library validates client data origin/RP ID and attestation structure. Policy is none:
    # this application makes no claim that an authenticator is trusted by its attestation.
    raw = _unb64(payload["challenge"])
    with transaction.atomic():
        consume(request, raw, "register", request.user)
        verified = webauthn.verify_registration_response(credential=payload["credential"], expected_challenge=raw, expected_rp_id=settings.WEBAUTHN_RP_ID, expected_origin=settings.WEBAUTHN_ORIGIN, require_user_verification=True)
        credential = WebAuthnCredential.objects.create(user=request.user, credential_id=verified.credential_id, public_key=verified.credential_public_key, sign_count=verified.sign_count, transports=list(payload.get("credential", {}).get("response", {}).get("transports", [])), name=str(name)[:80], user_verified=verified.user_verified, backup_eligible=verified.credential_device_type.value == "multi_device", backup_state=verified.credential_backed_up)
        audit.append_audit_event(actor=request.user, action="create", resource_type="WebAuthnCredential", resource_id=credential.pk, correlation_id=getattr(request, "correlation_id", ""))
    log_event("auth.passkey.enrollment.success", user_role=request.user.role)
    return credential

def verify_authentication(request, payload, user):
    raw = _unb64(payload["challenge"])
    with transaction.atomic():
        consume(request, raw, "authenticate", user)
        credential_id = _unb64(payload["credential"]["rawId"])
        credential = WebAuthnCredential.objects.select_for_update().get(user=user, credential_id=credential_id, revoked_at__isnull=True)
        verified = webauthn.verify_authentication_response(credential=payload["credential"], expected_challenge=raw, expected_rp_id=settings.WEBAUTHN_RP_ID, expected_origin=settings.WEBAUTHN_ORIGIN, credential_public_key=bytes(credential.public_key), credential_current_sign_count=credential.sign_count, require_user_verification=True)
        if verified.new_sign_count < credential.sign_count or (verified.new_sign_count and verified.new_sign_count == credential.sign_count):
            raise ValueError("counter_regression")
        credential.sign_count = verified.new_sign_count; credential.user_verified = verified.user_verified; credential.backup_state = verified.credential_backed_up; credential.save(update_fields=["sign_count", "user_verified", "backup_state"])
        audit.append_audit_event(actor=user, action="read", resource_type="WebAuthnAuthentication", resource_id=credential.pk, correlation_id=getattr(request, "correlation_id", ""))
    login(request, user); request.session["mfa_generation"] = user.mfa_generation
    log_event("auth.passkey.authentication.success", user_role=user.role)
    return credential

def recovery_code(user, code):
    return hashlib.sha256(f"{user.pk}:{code}".encode()).hexdigest()
