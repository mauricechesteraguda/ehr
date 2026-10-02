"""Ticket14 acceptance coverage; each canonical T14 case has one executable test."""
from datetime import date, timedelta

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


def _user(role, name):
    from backend.users.models import User
    return User.objects.create_user(username=name, password="ticket14", role=role, totp_enrolled=True)


def _patient(name, suffix):
    from backend.users.models import Patient
    return Patient.objects.create(public_id=f"{suffix}", display_name=name, birth_date=date(1980, 1, 1))


def _measure(schema, suffix="measure"):
    from backend.users.models import MeasureDefinition, MeasureVersion
    measure = MeasureDefinition.objects.create(url=f"http://example.org/Measure/{suffix}", title=suffix)
    version = MeasureVersion.objects.create(measure=measure, version=1, status="published", effective_start=date(2020, 1, 1), schema=schema)
    return measure, version


def _schema(resource="Patient", **parts):
    return {"schema_version": "1", "resource": resource, "denominator": [], "numerator": [], "exclusions": [], "stratifiers": [], **parts}


def test_T14_001_allowlisted_schema_predicates():
    from backend.users.quality import validate_schema
    schema = _schema(denominator=[{"field": "recorded_date", "op": "on_or_after", "value": "2026-01-01"}])
    assert validate_schema(schema)["schema_version"] == "1"


def test_T14_002_executable_schema_rejected():
    from backend.users.quality import SchemaError, validate_schema
    with pytest.raises(SchemaError):
        validate_schema(_schema(denominator=[{"field": "__import__", "op": "equals", "value": "x"}]))
    with pytest.raises(SchemaError):
        validate_schema({**_schema(), "expression": "__import__('os').system('id')"})


def test_T14_003_lifecycle_and_immutable_versions():
    from backend.users.models import MeasureVersion
    measure, version = _measure(_schema(), "lifecycle")
    version.status = "retired"
    with pytest.raises(ValueError):
        version.save()
    with pytest.raises(ValueError):
        version.delete()
    assert measure.versions.get(version=1).status == "published"


def test_T14_004_allergy_inclusive_window_and_entered_in_error_exclusion():
    from backend.users.models import AllergyIntolerance
    from backend.users.quality import evaluate_version
    patient = _patient("Allergy", "T14004")
    AllergyIntolerance.objects.create(patient=patient, code="ALG", label="documented", recorded_date=date(2026, 1, 1), status="active")
    AllergyIntolerance.objects.create(patient=patient, code="ALG", label="bad", recorded_date=date(2026, 1, 31), status="entered-in-error")
    _, version = _measure(_schema("AllergyIntolerance", window_days=30, numerator=[{"field": "code", "op": "equals", "value": "ALG"}], exclusions=[{"field": "status", "op": "equals", "value": "entered-in-error"}]), "allergy")
    result = evaluate_version(version, date(2026, 1, 1), date(2026, 1, 31), "a" * 64)
    assert result["initialPopulation"] == result["denominator"] == 1
    assert result["numerator"] == 1 and result["exclusions"] == 1


def test_T14_005_active_medication_uses_period_end():
    from backend.users.models import MedicationOrder, MedicationOrderVersion
    from backend.users.quality import evaluate_version
    owner = _user("clinician", "t14005-owner")
    patient = _patient("Medication", "T14005")
    order = MedicationOrder.objects.create(patient=patient, prescriber=owner)
    MedicationOrderVersion.objects.create(order=order, version=1, medication_code="RX", medication_name="Demo", dose=1, dose_unit="mg", route="oral", frequency="daily", start_date=date(2026, 2, 1), quantity=30, indication="demo", status="active", created_by=owner)
    _, version = _measure(_schema(numerator=[{"field": "active_medication_exists", "op": "equals", "value": True}]), "medication")
    result = evaluate_version(version, date(2026, 1, 1), date(2026, 1, 31), "b" * 64)
    assert result["denominator"] == 1 and result["numerator"] == 0


def test_T14_006_recent_bp_window_is_inclusive_and_empty_is_zero():
    from backend.users.models import Observation
    from backend.users.quality import evaluate_version
    patient = _patient("BP", "T14006")
    Observation.objects.create(patient=patient, code="BP", label="BP", value="120/80", recorded_date=date(2026, 1, 1))
    _, version = _measure(_schema(window_days=90, numerator=[{"field": "recent_bp_exists", "op": "equals", "value": True}]), "bp")
    result = evaluate_version(version, date(2025, 10, 3), date(2026, 1, 1), "c" * 64)
    assert result["denominator"] == result["numerator"] == 1
    _, empty_version = _measure(_schema(window_days=90, numerator=[{"field": "recent_bp_exists", "op": "equals", "value": True}]), "bp-empty")
    empty = evaluate_version(empty_version, date(2026, 1, 2), date(2026, 4, 2), "d" * 64)
    assert empty["denominator"] == 1 and empty["numerator"] == 0


def test_T14_007_reproducibility_pins_version_and_checksum():
    from backend.users.quality import evaluate_version
    _, version = _measure(_schema(), "repro")
    first = evaluate_version(version, date(2026, 1, 1), date(2026, 1, 31), "e" * 64)
    second = evaluate_version(version, date(2026, 1, 1), date(2026, 1, 31), "e" * 64)
    assert first == second and first["snapshotChecksum"] == "e" * 64


def test_T14_008_async_retry_and_idempotency_produce_one_report():
    from backend.users.jobs import deliver_job, enqueue_job
    from backend.users.models import MeasureReport, MeasureRun
    from backend.users.quality import run_measure
    owner = _user("admin", "t14008-admin")
    measure, version = _measure(_schema(), "async")
    job, created = enqueue_job(owner=owner, kind="quality.measure", idempotency_key="t14-008", input_data={"version": 1, "start_date": date(2026, 1, 1), "end_date": date(2026, 1, 31)})
    run = MeasureRun.objects.create(job=job, version=version, period_start=date(2026, 1, 1), period_end=date(2026, 1, 31), snapshot_checksum="f" * 64)
    assert created and enqueue_job(owner=owner, kind="quality.measure", idempotency_key="t14-008", input_data={"version": 1, "start_date": date(2026, 1, 1), "end_date": date(2026, 1, 31)})[0].pk == job.pk
    run_measure(run.pk); run_measure(run.pk)
    assert MeasureReport.objects.filter(run=run).count() == 1 and measure.versions.count() == 1
    deliver_job.apply(args=(str(job.pk), str(job.outbox_events.first().pk))).get()
    deliver_job.apply(args=(str(job.pk), str(job.outbox_events.first().pk))).get()
    assert MeasureReport.objects.filter(run=run).count() == 1


def test_T14_009_admin_and_quality_scope_roles():
    admin, clinician = _user("admin", "t14009-admin"), _user("clinician", "t14009-clinician")
    client = Client(); client.force_login(clinician)
    assert client.get("/api/admin/measures/").status_code == 403
    client.force_login(admin)
    assert client.get("/api/admin/measures/").status_code == 200


def test_T14_010_fhir_measure_and_report_content_types():
    from backend.users.models import MeasureReport, MeasureRun
    admin = _user("admin", "t14010-admin")
    measure, version = _measure(_schema(), "fhir")
    job = MeasureRun.objects.create(job=__import__("backend.users.models", fromlist=["Job"]).Job.objects.create(owner=admin, kind="quality.measure", idempotency_key="t14-010", input_checksum="1" * 64), version=version, period_start=date(2026, 1, 1), period_end=date(2026, 1, 31), snapshot_checksum="1" * 64)
    report = MeasureReport.objects.create(run=job, measure=measure, version=version, status="complete", period_start=job.period_start, period_end=job.period_end, snapshot_checksum=job.snapshot_checksum, populations={"denominator": 0, "numerator": 0})
    client = Client(); client.force_login(admin)
    assert client.get(f"/fhir/R4/Measure/{measure.pk}", HTTP_ACCEPT="application/fhir+json").headers["Content-Type"].startswith("application/fhir+json")
    response = client.get(f"/fhir/R4/MeasureReport/{report.pk}", HTTP_ACCEPT="application/fhir+json")
    assert response.json()["resourceType"] == "MeasureReport" and response.headers["Content-Type"].startswith("application/fhir+json")
