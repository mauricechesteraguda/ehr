"""type-10022026-Maurice: Ticket08 SMART acceptance coverage."""
import base64
import hashlib
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import Client
from django.utils import timezone

pytestmark = pytest.mark.django_db
REDIRECT = "https://localhost/callback"
VERIFIER = "ticket08-verifier-with-sufficient-length-123456789"
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).rstrip(b"=").decode()
SCOPES = "openid fhirUser patient/Patient.r patient/MedicationRequest.r patient/AllergyIntolerance.r patient/Condition.r patient/Observation.r patient/Device.r"


def _user(username="ticket08-developer"):
    """type-10022026-Maurice: Build a TOTP-authenticated synthetic developer session."""
    from backend.users.models import User
    user = User.objects.create_user(username=username, password="safe", role=User.Role.CLINICIAN, totp_enrolled=True)
    client = Client(); client.force_login(user)
    session = client.session; session["totp_authenticated"] = True; session.save()
    return client, user


def _register(client):
    """type-10022026-Maurice: Register only through the public developer route."""
    return client.post("/api/smart/apps/", {"name": "Sample app", "redirect_uris": [REDIRECT], "scope": SCOPES}, content_type="application/json")


def _authorization(client, registration, **extra):
    values = {"client_id": registration["client_id"], "redirect_uri": REDIRECT, "scope": SCOPES, "code_challenge": CHALLENGE, "code_challenge_method": "S256", **extra}
    return client.post("/oauth/authorize/", values, content_type="application/json")


def _tokens(client, registration, **extra):
    consent = _authorization(client, registration, decision="approve", state="state-08")
    assert consent.status_code == 200
    code = consent.json()["redirect"].split("code=", 1)[1].split("&", 1)[0]
    payload = {"grant_type": "authorization_code", "client_id": registration["client_id"], "client_secret": registration["client_secret"], "code": code, "redirect_uri": REDIRECT, "code_verifier": VERIFIER, **extra}
    response = client.post("/oauth/token/", payload, content_type="application/json")
    return response, code


def test_TC_EHR_0072_registration_exact_redirect():
    """type-10022026-Maurice: Secret is one-time response data and redirect is exact."""
    client, _ = _user(); response = _register(client); assert response.status_code == 201
    registration = response.json(); assert registration["client_secret"]
    listed = client.get("/api/smart/apps/"); assert listed.status_code == 200; assert "client_secret" not in listed.json()[0]
    assert client.get("/oauth/authorize/", {"client_id": registration["client_id"], "redirect_uri": REDIRECT + "/suffix", "scope": SCOPES, "code_challenge": CHALLENGE, "code_challenge_method": "S256"}).status_code == 400


def test_TC_EHR_0073_malformed_registration():
    """type-10022026-Maurice: Reject malformed app payloads before persistence."""
    client, _ = _user()
    from backend.users.models import User
    from oauth2_provider.models import Application
    before = Application.objects.count()
    for payload in ({"name": "", "redirect_uris": ["http://localhost/callback"], "scope": SCOPES}, {"name": "bad", "redirect_uris": [REDIRECT], "scope": "not-approved"}, {"name": "bad", "scope": SCOPES}):
        assert client.post("/api/smart/apps/", payload, content_type="application/json").status_code == 400
    assert Application.objects.count() == before
    assert not User.objects.filter(username="bad").exists()


def test_TC_EHR_0074_discovery():
    """type-10022026-Maurice: SMART discovery exposes endpoints and approved scopes."""
    response = Client().get("/.well-known/smart-configuration"); metadata = response.json()
    assert response.status_code == 200 and metadata["token_endpoint"].endswith("/oauth/token/")
    assert set(SCOPES.split()).issubset(metadata["scopes_supported"])
    assert "client_secret" not in response.content.decode()


def test_TC_EHR_0075_consent():
    """type-10022026-Maurice: Consent names app, scopes and bounded standalone/EHR context."""
    client, _ = _user(); registration = _register(client).json()
    response = client.get("/oauth/authorize/", {"client_id": registration["client_id"], "redirect_uri": REDIRECT, "scope": SCOPES, "code_challenge": CHALLENGE, "code_challenge_method": "S256"})
    assert response.status_code == 200 and response.json()["consent_required"] is True
    assert response.json()["app"]["client_id"] == registration["client_id"] and set(response.json()["scopes"]) == set(SCOPES.split())
    assert "code" not in response.json()
    assert client.get("/api/smart/launch/").json()["launch"] == "standalone"


def test_TC_EHR_0076_denial_invalid_redirect():
    """type-10022026-Maurice: Deny and redirect variants never issue a code."""
    client, _ = _user(); registration = _register(client).json()
    invalid = {"client_id": registration["client_id"], "redirect_uri": "https://localhost/callback?evil=1", "scope": SCOPES, "code_challenge": CHALLENGE, "code_challenge_method": "S256"}
    assert client.get("/oauth/authorize/", invalid).status_code == 400
    assert _authorization(client, registration, decision="deny").status_code == 403
    from oauth2_provider.models import Grant
    assert not Grant.objects.filter(application__client_id=registration["client_id"]).exists()


def test_TC_EHR_0077_code_replay_expiry():
    """type-10022026-Maurice: Real grants are PKCE-bound, one-time and expiry checked."""
    client, _ = _user(); registration = _register(client).json()
    response, code = _tokens(client, registration); assert response.status_code == 200
    replay = client.post("/oauth/token/", {"grant_type": "authorization_code", "client_id": registration["client_id"], "client_secret": registration["client_secret"], "code": code, "redirect_uri": REDIRECT, "code_verifier": VERIFIER}, content_type="application/json")
    assert replay.status_code == 400 and replay.json()["error"] == "invalid_grant"
    _authorization(client, registration, decision="approve")
    from oauth2_provider.models import Grant
    grant = Grant.objects.get(application__client_id=registration["client_id"]); grant.expires = timezone.now() - timedelta(seconds=1); grant.save(update_fields=["expires"])
    expired = client.post("/oauth/token/", {"grant_type": "authorization_code", "client_id": registration["client_id"], "client_secret": registration["client_secret"], "code": grant.code, "redirect_uri": REDIRECT, "code_verifier": VERIFIER}, content_type="application/json")
    assert expired.status_code == 400 and expired.json()["error"] == "invalid_grant"


def test_TC_EHR_0078_refresh_revoke():
    """type-10022026-Maurice: Rotation consumes old refresh material and revocation blocks both families."""
    client, _ = _user(); registration = _register(client).json(); response, _ = _tokens(client, registration); tokens = response.json()
    rotated = client.post("/oauth/token/", {"grant_type": "refresh_token", "client_id": registration["client_id"], "client_secret": registration["client_secret"], "refresh_token": tokens["refresh_token"]}, content_type="application/json")
    assert rotated.status_code == 200 and rotated.json()["refresh_token"] != tokens["refresh_token"]
    old = client.post("/oauth/token/", {"grant_type": "refresh_token", "client_id": registration["client_id"], "client_secret": registration["client_secret"], "refresh_token": tokens["refresh_token"]}, content_type="application/json")
    assert old.status_code == 400 and old.json()["error"] == "invalid_grant"
    assert client.post("/oauth/revoke_token/", {"token": rotated.json()["access_token"]}, content_type="application/json").status_code == 200
    revoked = client.get("/fhir/R4/Patient", HTTP_AUTHORIZATION=f"Bearer {rotated.json()['access_token']}")
    assert revoked.status_code == 401


def test_TC_EHR_0079_scope_compartment():
    """type-10022026-Maurice: SMART scope denial precedes FHIR ORM evaluation and compartment is exact."""
    client, user = _user(); registration = _register(client).json(); from backend.users.models import Patient
    Patient.objects.create(public_id="P001", display_name="One", birth_date="1980-01-01", sex="female"); Patient.objects.create(public_id="P002", display_name="Two", birth_date="1980-01-01", sex="female")
    response, _ = _tokens(client, registration); token = response.json()["access_token"]
    from oauth2_provider.models import AccessToken
    AccessToken.objects.filter(token_checksum=hashlib.sha256(token.encode()).hexdigest()).update(scope="openid fhirUser")
    with patch("backend.users.fhir._ensure_demo_records") as seeded:
        denied = client.get("/fhir/R4/Patient", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert denied.status_code == 403 and not seeded.called
    AccessToken.objects.filter(token_checksum=hashlib.sha256(token.encode()).hexdigest()).update(scope=SCOPES, resource=["P001"])
    allowed = client.get("/fhir/R4/Patient", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert allowed.status_code == 200 and {entry["resource"]["id"] for entry in allowed.json()["entry"]} == {"P001"}


def test_TC_EHR_0080_session_audit_fail_closed():
    """type-10022026-Maurice: Expired TOTP session and audit outage produce no grant/token."""
    client, _ = _user(); registration = _register(client).json(); session = client.session; session["totp_authenticated"] = False; session.save()
    denied = _authorization(client, registration, decision="approve"); assert denied.status_code == 400
    session["totp_authenticated"] = True; session.save()
    with patch("backend.users.smart.audit.append_audit_event", side_effect=RuntimeError("audit unavailable")):
        failed = _authorization(client, registration, decision="approve")
    assert failed.status_code >= 500
    from oauth2_provider.models import Grant
    assert not Grant.objects.filter(application__client_id=registration["client_id"]).exists()


def test_TC_EHR_0081_pkce_s256_confidential_policy():
    """type-10022026-Maurice: Confidential clients require S256 PKCE; plain/missing/wrong verifiers are invalid_grant."""
    client, _ = _user(); registration = _register(client).json()
    base = {"client_id": registration["client_id"], "redirect_uri": REDIRECT, "scope": SCOPES}
    assert client.get("/oauth/authorize/", {**base, "code_challenge": CHALLENGE, "code_challenge_method": "plain"}).status_code == 400
    assert client.get("/oauth/authorize/", base).status_code == 400
    consent = _authorization(client, registration, decision="approve"); code = consent.json()["redirect"].split("code=", 1)[1].split("&", 1)[0]
    wrong = client.post("/oauth/token/", {"grant_type": "authorization_code", "client_id": registration["client_id"], "client_secret": registration["client_secret"], "code": code, "redirect_uri": REDIRECT, "code_verifier": "wrong-verifier"}, content_type="application/json")
    assert wrong.status_code == 400 and wrong.json()["error"] == "invalid_grant"
