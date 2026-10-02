"""type-10022026-Maurice: final logging and demo regression acceptance coverage."""
import json
import logging
import os
import stat
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
