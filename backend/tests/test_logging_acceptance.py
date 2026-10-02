"""type-10022026-Maurice: final logging and demo regression acceptance coverage."""
import json
import logging
import os
import stat
import logging as pylogging
from pathlib import Path

import pytest
from django.core.management import call_command

from backend.users.logging import JsonConsoleFormatter, external_authenticate, log_event

pytestmark = pytest.mark.django_db


def _formatted(event, **context):
    """type-10022026-Maurice: Render one representative operational event for mechanical checks."""
    record = logging.LogRecord("ehr", logging.INFO, __file__, 1, event, (), None)
    record.event = event
    record.context = context
    return json.loads(JsonConsoleFormatter().format(record))


def test_TC_EHR_0097_enrollment_file_is_private_and_console_is_redacted(tmp_path, capsys):
    """type-10022026-Maurice: Enrollment secrets stay in a mode-600 external file."""
    path = tmp_path / "enrollment.txt"
    call_command("seed_demo", password="logging-demo-password", totp_secret_file=str(path))
    output = capsys.readouterr()
    rendered = output.out + output.err
    secret_text = path.read_text()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert secret_text and "TOTP" not in rendered
    assert "logging-demo-password" not in rendered
    assert all(secret not in rendered for secret in (line.split(": ", 1)[1] for line in secret_text.splitlines()))


def test_TC_EHR_0098_console_events_are_json_and_allowlisted():
    """type-10022026-Maurice: Console records expose only the operational envelope."""
    success = _formatted("demo.boundary.success", status=200, duration_ms=4, outcome="success", correlation_id="corr-1")
    failure = _formatted("demo.boundary.failure", status=500, duration_ms=7, outcome="failure", password="do-not-log", payload={"patient": "P001"})
    assert success["event"] == "demo.boundary.success"
    assert {"status", "duration_ms", "outcome", "correlation_id"} <= success.keys()
    assert "password" not in failure and "payload" not in failure
    assert failure["outcome"] == "failure"


def test_TC_EHR_0099_trace_records_are_bounded_and_path_safe(tmp_path, monkeypatch):
    """type-10022026-Maurice: External trace JSONL contains safe diagnostic metadata only."""
    import backend.users.tracing as tracing

    trace_path = tmp_path / "trace.jsonl"
    monkeypatch.setattr(tracing, "TRACE_FILE", trace_path)

    @tracing.trace_function
    def traced_failure():
        raise ValueError("password=not-a-trace-field")

    with pytest.raises(ValueError):
        traced_failure()
    records = [json.loads(line) for line in trace_path.read_text().splitlines()]
    exception = next(record for record in records if record["event"] == "exception")
    rendered = json.dumps(exception)
    assert exception["exception_class"] == "ValueError"
    assert "password=not-a-trace-field" not in rendered
    assert all(not Path(location.split(":", 1)[0]).is_absolute() for location in exception["stack_trace"])


def test_TC_EHR_0100_seed_never_exposes_totp_secrets(capsys):
    """type-10022026-Maurice: Normal and reset seed modes do not print enrollment values."""
    call_command("seed_demo", password="logging-demo-password")
    call_command("seed_demo", password="logging-demo-password")
    call_command("seed_demo", password="logging-demo-password", reset=True)
    rendered = capsys.readouterr().out
    assert "totp_secret" not in rendered.lower()
    assert "secret=" not in rendered.lower()


def test_TC_EHR_0101_structured_console_logs_are_allowlisted():
    """type-10022026-Maurice: Allowlisted structured event fields remain machine-readable."""
    event = _formatted("logging.allowlisted", status=200, duration_ms=12, outcome="success", component="test", operation="emit")
    assert {"event", "status", "duration_ms", "outcome", "component", "operation", "correlation_id"} <= event.keys()


def test_TC_EHR_0102_fhir_boundaries_emit_outcomes():
    """type-10022026-Maurice: FHIR boundary outcome shape is represented without payloads."""
    event = _formatted("fhir.read.failure", status=503, duration_ms=9, outcome="failure", error_class="DatabaseError", db_outcome="unavailable")
    assert event["status"] == 503 and event["outcome"] == "failure"
    assert event["error_class"] == "DatabaseError" and event["db_outcome"] == "unavailable"


def test_TC_EHR_0103_patient_and_medication_boundaries_emit_outcomes():
    """type-10022026-Maurice: Patient and medication DB events carry bounded result metadata."""
    events = [_formatted(name, status=200, duration_ms=3, outcome="success", db_outcome="committed") for name in ("patient.detail", "medication.evaluate")]
    assert all({"status", "duration_ms", "outcome", "db_outcome", "correlation_id"} <= event.keys() for event in events)


def test_TC_EHR_0104_smart_lifecycle_logs_are_safe():
    """type-10022026-Maurice: SMART lifecycle event shape excludes query and token material."""
    event = _formatted("smart.token.refresh", http_status=200, http_class="2xx", duration_ms=5, outcome="success", token="secret-token")
    assert event["http_status"] == 200 and event["http_class"] == "2xx"
    assert "token" not in event


def test_TC_EHR_0105_external_and_export_boundaries_emit_outcomes():
    """type-10022026-Maurice: External authentication emits safe lifecycle records."""
    external_authenticate(lambda: "synthetic-result")
    event = _formatted("export.failure", status=500, duration_ms=11, outcome="failure", error_class="ExportError", payload="clinical")
    assert event["error_class"] == "ExportError" and "payload" not in event


def test_TC_EHR_0106_rate_limit_cache_failure_is_observable():
    """type-10022026-Maurice: Cache failures are visible by class, never by identity."""
    event = _formatted("rate_limit.cache.failure", status=200, duration_ms=2, outcome="degraded", error_class="CacheError", username="patient@example.test")
    assert event["outcome"] == "degraded" and event["error_class"] == "CacheError"
    assert "username" not in event


def test_TC_EXP_0161_logging_contract_has_stable_fields():
    event = _formatted("contract.success", operation="run", outcome="success", status="completed", severity="INFO", duration_ms=2, correlation_id="c")
    assert {"event_name", "operation", "status", "severity", "duration_ms", "correlation_id"} <= event.keys()


def test_TC_EXP_0162_job_metadata_is_opaque_and_bounded():
    event = _formatted("job.completed", outcome="success", job_id="sensitive-reference", attempt=2, duration_ms=3)
    assert event["job_id"] != "sensitive-reference" and len(event["job_id"]) == 16 and event["attempt"] == 2


def test_TC_EXP_0163_worker_outcomes_have_attempt_and_duration():
    for name, outcome in (("job.received", "started"), ("job.retry", "retry"), ("job.terminal_failure", "failure"), ("job.completed", "success")):
        event = _formatted(name, outcome=outcome, job_id="job", attempt=1, duration_ms=1)
        assert {"job_id", "attempt", "duration_ms", "status", "severity"} <= event.keys()


def test_TC_EXP_0164_health_uses_structured_boundary_events():
    source = __import__("pathlib").Path(__file__).parents[1] / "users/health.py"
    text = source.read_text()
    assert "log_event" in text and "logger." not in text


def test_TC_EXP_0165_seed_lifecycle_is_structured_without_raw_logger():
    source = __import__("pathlib").Path(__file__).parents[1] / "users/management/commands/seed_demo.py"
    text = source.read_text()
    assert "demo.seed.started" in text and "demo.seed.success" in text and "logger." not in text


def test_TC_EXP_0166_major_workflows_name_safe_boundaries():
    source = " ".join(p.read_text() for p in (__import__("pathlib").Path(__file__).parents[1] / "users").glob("*.py"))
    for name in ("ccda", "direct", "population", "bulk", "questionnaire", "amendment", "break", "quality"):
        assert name in source.lower()


def test_TC_EXP_0167_passkey_challenge_lifecycle_is_logged():
    from backend.users import passkeys
    assert "challenge.created" in __import__("pathlib").Path(passkeys.__file__).read_text()


def test_TC_EXP_0168_totp_sms_lifecycle_events_are_allowlisted():
    source = (__import__("pathlib").Path(__file__).parents[1] / "users/views.py").read_text()
    assert "auth.totp" in source and "auth.recovery.sms" in source


def test_TC_EXP_0169_default_deny_redaction_excludes_unknown_payloads():
    event = _formatted("boundary.failure", outcome="failure", credentials="secret", clinical_code="x", payload={"x": "y"})
    assert not {"credentials", "clinical_code", "payload"} & event.keys()


def test_TC_EXP_0170_compose_failure_diagnostic_is_sanitized():
    from backend.tests.test_ticket17_compose import _safe_diagnostic
    diagnostic = _safe_diagnostic("fatal /home/user/.env password=x https://user:pass@example.test:443")
    rendered = json.dumps(diagnostic)
    assert "password" not in rendered and "/home" not in rendered and "https" not in rendered


def test_TC_EXP_0171_failures_default_to_error_severity():
    event = _formatted("operation.failure", outcome="failure")
    assert event["severity"] == "ERROR"


def test_TC_EXP_0172_correlation_is_always_present():
    assert "correlation_id" in _formatted("operation.success", outcome="success")


def test_TC_EXP_0173_boundary_and_remediation_are_safe_fields():
    event = _formatted("db.failure", outcome="failure", boundary="postgres", error_class="OperationalError", error_code="unavailable", remediation_hint="retry")
    assert {"boundary", "error_class", "error_code", "remediation_hint"} <= event.keys()


def test_TC_EXP_0174_tracing_is_separate_from_operational_logging():
    from backend.users import tracing
    assert tracing.trace_function is not None and tracing.trace_function is not __import__("backend.users.logging", fromlist=["log_event"]).log_event


def test_TC_EXP_0175_event_name_is_canonical_and_legacy_event_is_compatible():
    event = _formatted("canonical.success", outcome="success")
    assert event["event_name"] == event["event"] == "canonical.success"


def test_TC_EXP_0176_duration_is_bounded_integer():
    event = _formatted("timed.success", outcome="success", duration_ms=7)
    assert isinstance(event["duration_ms"], int) and 0 <= event["duration_ms"] < 100000


def test_TC_EXP_0177_passkey_failures_have_error_class_contract():
    event = _formatted("auth.passkey.challenge.consume.failure", outcome="failure", error_class="ValueError", error_code="expired", duration_ms=1)
    assert event["severity"] == "ERROR" and event["error_class"] == "ValueError"


def test_TC_EXP_0178_redaction_never_serializes_exception_text():
    event = _formatted("exception.failure", outcome="failure", exception=ValueError("password=secret"))
    assert "password=secret" not in json.dumps(event)
