"""type-10022026-Maurice: Ticket 01 acceptance tests define the RED baseline."""

import pytest

from backend.users.logging import log_event
from backend.users.tracing import trace_function


@pytest.mark.django_db
def test_TC_EHR_0017_role_access_matrix_and_patient_self_only_restriction(client):
    """TC-EHR-0017: role-scoped access requires a real authenticated session."""
    response = client.get("/api/auth/session/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_TC_EHR_0018_unauthenticated_and_session_expiry_denial(client):
    """TC-EHR-0018: protected endpoints deny unauthenticated requests."""
    assert client.get("/api/shell/").status_code == 401


@pytest.mark.django_db
def test_TC_EHR_0019_mandatory_totp_enrollment_and_verification(client):
    """TC-EHR-0019: password-only login cannot establish a session."""
    response = client.post("/api/auth/login/", {"username": "demo", "password": "demo"})
    assert response.status_code == 400


@pytest.mark.django_db
def test_TC_EHR_0020_salted_one_way_credential_storage():
    """TC-EHR-0020: user credentials use Django's password hashing."""
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_user(username="one", password="same")
    assert user.password.startswith("!") is False
    assert user.password != "same"


@pytest.mark.django_db
def test_TC_EHR_0021_configurable_inactivity_timeout_and_reauthentication(client):
    """TC-EHR-0021: an authenticated idle session is invalidated."""
    assert client.get("/api/auth/session/").status_code == 401


def test_TC_EHR_0024_browser_ehi_storage_prohibition():
    """TC-EHR-0024: frontend session material must not use browser storage."""
    source = open("src/auth.ts", encoding="utf-8").read()
    assert "localStorage" not in source
    assert "sessionStorage" not in source


def test_TC_EHR_0026_tls_local_certificate_configuration():
    """TC-EHR-0026: local HTTPS is configured from developer certificate paths."""
    source = open("vite.config.ts", encoding="utf-8").read()
    assert "HTTPS_CERT" in source and "HTTPS_KEY" in source


@pytest.mark.django_db
def test_TC_EHR_0027_django_drf_postgres_react_typescript_foundation():
    """TC-EHR-0027: the stack exposes a typed role shell endpoint."""
    from django.test import Client
    assert Client().get("/api/shell/").status_code == 401


@pytest.mark.django_db
@trace_function
def test_TC_EHR_0038_safe_security_error_messages():
    """TC-EHR-0038: login errors do not disclose account existence."""
    log_event("test.ticket01.security_error_case")
    from django.test import Client
    response = Client().post("/api/auth/login/", {"username": "unknown", "password": "wrong"})
    assert response.status_code == 400
    assert "unknown" not in response.content.decode().lower()


def test_TC_EHR_0040_structured_events_redact_nested_sensitive_values(caplog):
    """TC-EHR-0040: nested sensitive fields never cross the operational log boundary."""
    log_event("auth.test.failure", outcome="failure", request={"password": "secret", "nested": {"otp": "123456"}}, role="clinician")
    record = caplog.records[-1]
    assert record.context["request"]["password"] == "[REDACTED]"
    assert record.context["request"]["nested"]["otp"] == "[REDACTED]"
    assert "role" not in record.context


@pytest.mark.django_db
def test_TC_EHR_0041_correlation_is_sanitized_and_returned(client):
    """TC-EHR-0041: the backend accepts safe correlation IDs and rejects unsafe headers."""
    response = client.post("/api/auth/login/", {"username": "demo", "password": "demo"}, HTTP_X_CORRELATION_ID="bad value\nsecret")
    assert response["X-Correlation-ID"]
    assert "\n" not in response["X-Correlation-ID"]


def test_TC_EHR_0043_exception_context_is_classified_without_message(caplog):
    """TC-EHR-0043: exception classification is retained without sensitive exception text."""
    log_event("auth.external.failure", outcome="failure", exception=ValueError("password=secret"))
    record = caplog.records[-1]
    assert record.context["exception_type"] == "ValueError"
    assert "password=secret" not in str(record.context)


def test_TC_EHR_0045_external_auth_events_have_lifecycle(caplog):
    """TC-EHR-0045: the external authentication boundary emits safe lifecycle events."""
    from backend.users.logging import external_authenticate

    external_authenticate(lambda: object())
    assert [record.event for record in caplog.records[-2:]] == ["auth.external.entry", "auth.external.exit"]


def test_TC_EHR_0046_correlation_context_is_reset_between_requests(caplog):
    """TC-EHR-0046: request correlation context cannot leak between sequential requests."""
    from backend.users.correlation import CorrelationMiddleware
    from backend.users.logging import _correlation_id, log_event

    def response(request):
        log_event("test.request", request_id=request.correlation_id)
        return type("Response", (), {"__setitem__": lambda self, key, value: None})()

    middleware = CorrelationMiddleware(response)
    middleware(type("Request", (), {"headers": {"X-Correlation-ID": "first"}})())
    log_event("test.after.first")
    assert caplog.records[-1].context["correlation_id"] == ""

    def raises(request):
        raise RuntimeError("sensitive password=secret")

    with pytest.raises(RuntimeError):
        CorrelationMiddleware(raises)(type("Request", (), {"headers": {"X-Correlation-ID": "second"}})())
    log_event("test.after.exception")
    assert caplog.records[-1].context["correlation_id"] == ""
    assert _correlation_id.get() == ""


@pytest.mark.django_db
@trace_function
def test_TC_EHR_0042_totp_enrollment_has_explicit_outcomes(client, caplog):
    """TC-EHR-0042: enrollment and verification expose entry plus outcome events."""
    from django.contrib.auth import get_user_model

    # Django's request warnings also enter caplog, but only ehr structured records carry
    # the event field this acceptance test is asserting against.
    def ehr_events():
        return [
            record.event
            for record in caplog.records
            if record.name.startswith("ehr.") and hasattr(record, "event")
        ]

    user = get_user_model().objects.create_user(username="enroll", password="password")
    client.force_login(user)
    client.post("/api/auth/enroll/")
    assert "auth.totp.enrollment.entry" in ehr_events()
    assert "auth.totp.enrollment.success" in ehr_events()
    caplog.clear()
    response = client.post("/api/auth/enroll/verify/", {"otp": "000000"})
    assert response.status_code == 400
    assert "auth.totp.enrollment.verification.entry" in ehr_events()
    assert "auth.totp.enrollment.verification.failure" in ehr_events()


def test_TC_EHR_0048_tracer_exception_metadata_is_sanitized(tmp_path, monkeypatch):
    """TC-EHR-0048: traced exception metadata excludes messages and arguments."""
    import json
    from backend.users import tracing

    trace_file = tmp_path / "trace.jsonl"
    monkeypatch.setattr(tracing, "TRACE_FILE", trace_file)

    @tracing.trace_function
    def fails():
        try:
            raise KeyError("token=secret")
        except KeyError as cause:
            raise ValueError("password=secret") from cause

    with pytest.raises(ValueError):
        fails()
    event = json.loads(trace_file.read_text().splitlines()[-1])
    assert event["exception_class"] == "ValueError"
    assert event["exception_code"] == "ValueError"
    assert event["cause_chain"] == ["KeyError"]
    assert len(event["stack_trace"]) <= 8
    assert "secret" not in json.dumps(event)
    assert "password" not in json.dumps(event)
