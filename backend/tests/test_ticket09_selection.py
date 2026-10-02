"""Ticket09 expansion acceptance tests for registered-app patient selection."""
from datetime import date, timedelta
from logging import getLogger
from unittest.mock import patch
import uuid

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone
from oauth2_provider.models import AccessToken, Application, set_token_value

pytestmark = pytest.mark.django_db
logger = getLogger(__name__)


def _selection_token(*, scope="patient/Patient.s", with_mfa=True, expired=False):
    from backend.users.models import SmartTokenContext, User

    user = User.objects.create_user(username=f"selection-user-{uuid.uuid4().hex[:8]}", password="not-used", role=User.Role.DEVELOPER, is_active=True, mfa_generation=2)
    app = Application.objects.create(user=user, name="Selection fixture", client_type=Application.CLIENT_CONFIDENTIAL, authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE, registration_source="manual")
    token_value = f"selection-token-{uuid.uuid4().hex}"
    token = AccessToken(user=user, application=app, expires=timezone.now() + timedelta(seconds=-1 if expired else 300), scope=f"openid fhirUser {scope}", resource=[])
    set_token_value(token, token_value)
    token.save()
    if with_mfa:
        SmartTokenContext.objects.create(access_token=token, user=user, application=app, mfa_generation=2, completed_at=timezone.now())
    return user, app, token_value


def _client(user, token="selection-token"):
    client = Client(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def _patient(**values):
    from backend.users.models import Patient

    defaults = {"display_name": "Ana Maria Smith", "given_name": "Ana Maria", "family_name": "Smith", "birth_date": date(1988, 2, 3)}
    defaults.update(values)
    return Patient.objects.create(**defaults)


def test_TC_EXP_0096_authorization():
    """Missing scope, expired token and missing MFA are forbidden before lookup."""
    # trace: TC-EXP-0096; trailmap: Ticket 09 authorization boundary; logging is safe/no PHI.
    logger.info("ticket09 selection authorization boundary")
    from backend.users.models import Patient

    patient = _patient(public_id="SEL001")
    for kwargs in ({"scope": "patient/Patient.r"}, {"expired": True}, {"with_mfa": False}):
        user, _, token = _selection_token(**kwargs)
        response = _client(user, token).post("/api/smart/patient-selection/", {"identifier": patient.public_id, "birth_date": "1988-02-03"}, content_type="application/json")
        assert response.status_code in {401, 403, 503}
        assert "patient_id" not in response.json()


def test_TC_EXP_0097_exact_contract():
    # trace: TC-EXP-0097; trailmap: Ticket 09 exact-match contract; logging is safe/no PHI.
    logger.info("ticket09 selection exact contract")
    patient = _patient(public_id="SEL002")
    user, _, token = _selection_token()
    client = _client(user, token)
    response = client.post("/api/smart/patient-selection/", {"identifier": patient.public_id, "birth_date": "1988-02-03"}, content_type="application/json")
    assert response.status_code == 200
    assert set(response.json()) == {"patient_id", "request_id"}
    assert "SEL002" not in response.json()["patient_id"]
    assert client.post("/api/smart/patient-selection/", {"given_name": "ANA\u00a0MARIA", "family_name": "SMITH", "birth_date": "1988-02-03"}, content_type="application/json").status_code == 200
    assert client.post("/api/smart/patient-selection/", {"identifier": "' OR 1=1 --", "birth_date": "1988-02-03"}, content_type="application/json").status_code == 404

    _patient(public_id="SEL003", given_name="Duplicate", family_name="Person", display_name="Duplicate Person", birth_date=date(1990, 1, 1))
    _patient(public_id="SEL004", given_name="Duplicate", family_name="Person", display_name="Duplicate Person", birth_date=date(1990, 1, 1))
    duplicate = client.post("/api/smart/patient-selection/", {"given_name": "Duplicate", "family_name": "Person", "birth_date": "1990-01-01"}, content_type="application/json")
    assert duplicate.status_code == 404 and duplicate.json()["detail"] == "No matching patient."


def test_TC_EXP_0098_rate_audit_failure():
    # trace: TC-EXP-0098; trailmap: Ticket 09 resilience and audit boundary; logging is safe/no PHI.
    logger.info("ticket09 selection rate and audit failure boundary")
    cache.clear()
    user, _, token = _selection_token()
    client = _client(user, token)
    responses = [client.post("/api/smart/patient-selection/", {"identifier": "none", "birth_date": "1988-02-03"}, content_type="application/json") for _ in range(11)]
    assert responses[-1].status_code == 429
    cache.clear()
    with patch("backend.users.smart.audit.append_audit_event", side_effect=RuntimeError("unavailable")):
        assert client.post("/api/smart/patient-selection/", {"identifier": "none", "birth_date": "1988-02-03"}, content_type="application/json").status_code == 503
