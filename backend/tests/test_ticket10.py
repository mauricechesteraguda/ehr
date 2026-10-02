"""type-10022026-Maurice: Ticket10 final integration acceptance coverage."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

pytestmark = pytest.mark.django_db


def test_TC_EHR_0092_seed_is_idempotent_and_resettable(capsys):
    call_command("seed_demo", password="ticket10-local-password")
    call_command("seed_demo", password="ticket10-local-password")
    from backend.users.models import AllergyIntolerance, InteractionRule, Patient, User
    assert User.objects.filter(username__startswith="demo-").count() == 4
    assert Patient.objects.filter(public_id__in=("P001", "P002")).count() == 2
    assert AllergyIntolerance.objects.filter(patient__public_id="P001").count() == 1
    assert InteractionRule.objects.count() == 2
    call_command("seed_demo", password="ticket10-local-password", reset=True)
    assert Patient.objects.filter(public_id__in=("P001", "P002")).count() == 2
    assert User.objects.filter(username="demo-admin").count() == 1


def test_TC_EHR_0094_smart_demo_pkce_refresh_and_patient_read():
    # type-10022026-Maurice: Highest-seam protocol proof reuses the public Ticket08 boundary.
    call_command("seed_demo", password="ticket10-local-password")
    from backend.tests.test_ticket08 import _authorization, _register, _tokens, _user
    client, _ = _user("ticket10-developer")
    registration = _register(client).json()
    token_response, _ = _tokens(client, registration)
    assert token_response.status_code == 200
    token = token_response.json()
    refreshed = client.post("/oauth/token/", {"grant_type": "refresh_token", "client_id": registration["client_id"], "client_secret": registration["client_secret"], "refresh_token": token["refresh_token"]}, content_type="application/json")
    assert refreshed.status_code == 200
    response = client.get("/fhir/R4/Patient/P001", HTTP_AUTHORIZATION=f"Bearer {refreshed.json()['access_token']}")
    assert response.status_code == 200 and response.json()["resourceType"] == "Patient"


def test_TC_EHR_0095_local_https_and_disclaimer():
    from pathlib import Path
    assert Path("vite.config.ts").read_text().find("HTTPS_CERT") >= 0
    assert "Synthetic data only" in Path("src/main.tsx").read_text()


def test_TC_EHR_0096_final_p0_integration_boundaries():
    call_command("seed_demo", password="ticket10-local-password")
    from backend.users.models import User
    assert {u.role for u in User.objects.filter(username__startswith="demo-")} == {"clinician", "patient", "admin", "developer"}


def test_seed_requires_explicit_local_password():
    with pytest.raises(CommandError):
        call_command("seed_demo", password=None)
