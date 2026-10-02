"""type-10022026-Maurice: Idempotent synthetic P0 demo data management command."""
import os
import secrets
import time
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from oauth2_provider.models import Application

from backend.users.models import (
    AlertConfiguration,
    AllergyIntolerance,
    AuditEvent,
    Condition,
    Device, DeviceVersion, DeviceOutboxEvent,
    InteractionRule,
    InteractionEvaluation,
    InteractionAcknowledgement,
    MedicationOrder,
    MedicationOrderVersion,
    Observation,
    Patient,
    PatientExport,
    User,
    FamilyHistory, FamilyHistoryVersion, FamilyHistoryOutboxEvent,
    Questionnaire, QuestionnaireVersion, QuestionnaireItem,
    QuestionnaireResponse, QuestionnaireResponseVersion, QuestionnaireReview, QuestionnaireOutboxEvent,
    MeasureDefinition, MeasureVersion,
)
from backend.users.logging import log_event

DEMO_USERS = {
    "demo-clinician": User.Role.CLINICIAN,
    "demo-patient": User.Role.PATIENT,
    "demo-admin": User.Role.ADMIN,
    "demo-developer": User.Role.DEVELOPER,
}


class Command(BaseCommand):
    help = "Create or reset deterministic synthetic EHR demo data; secrets are local-only."

    def add_arguments(self, parser):
        parser.add_argument("--password", default=os.environ.get("DEMO_PASSWORD"), help="Local demo password (or DEMO_PASSWORD).")
        parser.add_argument("--reset", action="store_true", help="Remove demo-owned records before seeding.")
        parser.add_argument("--totp-secret-file", help="Explicit mode: write enrollment secrets to this local file (mode 600), never stdout.")

    @transaction.atomic
    def handle(self, *args, **options):
        started = time.monotonic()
        log_event("demo.seed.started", component="seed", operation="seed_demo", outcome="started", boundary="database")
        password = options.get("password")
        if not password:
            raise CommandError("Supply --password or DEMO_PASSWORD; no password is stored in the repository.")
        if options["reset"]:
            self._reset()
        users, secrets_by_user = self._users(password, bool(options.get("totp_secret_file")))
        patients = self._patients(users["demo-patient"])
        self._clinical_data(patients)
        self._family_history(patients[0], users["demo-clinician"])
        self._medication(patients[0], users["demo-clinician"])
        self._interactions()
        self._questionnaire(users["demo-clinician"])
        self._measures()
        log_event("demo.seed.success", component="seed", operation="seed_demo", outcome="success", boundary="database", duration_ms=int((time.monotonic() - started) * 1000))
        self.stdout.write(self.style.SUCCESS("Synthetic demo ready: P001/P002 and four role accounts."))
        if options.get("totp_secret_file") and secrets_by_user:
            path = os.path.abspath(options["totp_secret_file"])
            flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
            fd = os.open(path, flags, 0o600)
            with os.fdopen(fd, "w") as handle:
                for username, secret in secrets_by_user.items():
                    handle.write(f"{username}: {secret}\n")
            self.stdout.write(f"Enrollment file written with mode 600: {path}")

    def _measures(self):
        definitions = [
            ("http://example.org/Measure/allergy-documentation", "Allergy documentation coverage", {"resource": "Patient", "denominator": [], "numerator": [{"field": "allergy_exists", "op": "equals", "value": True}], "exclusions": [], "stratifiers": [], "schema_version": "1"}),
            ("http://example.org/Measure/active-medication-review", "Active-medication review", {"resource": "Patient", "denominator": [], "numerator": [{"field": "active_medication_exists", "op": "equals", "value": True}], "exclusions": [], "stratifiers": [], "schema_version": "1"}),
            ("http://example.org/Measure/recent-blood-pressure", "Recent blood-pressure observation coverage", {"resource": "Patient", "window_days": 90, "denominator": [], "numerator": [{"field": "recent_bp_exists", "op": "equals", "value": True}], "exclusions": [], "stratifiers": [], "schema_version": "1"}),
        ]
        for url, title, schema in definitions:
            measure, _ = MeasureDefinition.objects.get_or_create(url=url, defaults={"title": title, "description": "Synthetic deterministic demo measure", "provenance": {"source": "seed_demo", "method": "allowlisted-dsl"}})
            if not measure.versions.filter(version=1).exists():
                MeasureVersion.objects.create(measure=measure, version=1, status="published", effective_start=date(2020, 1, 1), schema=schema, provenance=measure.provenance)

    def _users(self, password, enroll=False):
        users, generated = {}, {}
        for username, role in DEMO_USERS.items():
            user, created = User.objects.get_or_create(username=username, defaults={"role": role})
            changed = []
            if created:
                user.set_password(password); changed.append("password")
            if user.role != role:
                user.role = role; changed.append("role")
            if enroll and not user.totp_secret:
                import pyotp
                user.totp_secret = pyotp.random_base32(); changed.append("totp_secret")
                generated[username] = user.totp_secret
            if enroll and not user.totp_enrolled:
                user.totp_enrolled = True; changed.append("totp_enrolled")
            if changed:
                user.save(update_fields=changed)
            users[username] = user
        # Existing secrets are deliberately not printed as values can be copied from prior setup.
        return users, generated

    def _patients(self, owner):
        rows = [
            ("P001", "Demo Patient One", "Demo Patient", "One", "2106-3", "2186-5", "en", "female", "straight", "woman", date(1980, 1, 1)),
            ("P002", "Demo Patient Two", "Demo Patient", "Two", "2054-5", "2135-2", "es", "male", "gay", "man", date(1975, 5, 5)),
            # Ticket09 selection fixtures: exact same normalized name/DOB must not select either.
            ("P003", "Duplicate Patient", "Duplicate", "Patient", "2106-3", "2186-5", "en", "female", "straight", "woman", date(1990, 9, 9)),
            ("P004", "Duplicate Patient", "Duplicate", "Patient", "2054-5", "2135-2", "es", "male", "gay", "man", date(1990, 9, 9)),
        ]
        patients = []
        for public_id, name, given, family, race, ethnicity, language, sex, orientation, gender, birth in rows:
            patient, _ = Patient.objects.update_or_create(public_id=public_id, defaults={"display_name": name, "given_name": given, "family_name": family, "race": race, "ethnicity": ethnicity, "preferred_language": language, "sex": sex, "sexual_orientation": orientation, "gender_identity": gender, "birth_date": birth, "owner": owner if public_id == "P001" else None})
            patients.append(patient)
        return patients

    def _clinical_data(self, patients):
        for patient in patients:
            AllergyIntolerance.objects.get_or_create(patient=patient, code="227493005", defaults={"label": "Demo allergy", "reaction": "Demo reaction"})
            Condition.objects.get_or_create(patient=patient, code="38341003", defaults={"label": "Demo condition"})
            Observation.objects.get_or_create(patient=patient, code="8310-5", defaults={"label": "Body temperature", "value": "Demo value", "unit": "Cel"})
            device, _ = Device.objects.get_or_create(patient=patient, code="DEV-DEMO", defaults={"label": "Demo monitoring device", "status": "active"})
            if not device.active_version:
                version = DeviceVersion.objects.create(device=device, version=1, code=device.code, label=device.label, status=device.status, issuer="GS1", device_identifier="", parser_version="seed-1", parse_status=DeviceVersion.ParseStatus.PARSE_FAILED, parse_error_code="synthetic_fixture", created_by=User.objects.get(username="demo-clinician"))
                device.active_version = version; device.save(update_fields=["active_version"])

    def _medication(self, patient, clinician):
        order, _ = MedicationOrder.objects.get_or_create(patient=patient, prescriber=clinician)
        if not order.active_version:
            version = MedicationOrderVersion.objects.create(order=order, version=1, medication_code="WARFARIN", medication_name="Demo medication", dose="2.000", dose_unit="mg", route="oral", frequency="daily", start_date=date(2026, 1, 1), quantity="30.000", refills=2, indication="Synthetic demo", status=MedicationOrderVersion.Status.ACTIVE, created_by=clinician)
            order.active_version = version; order.save(update_fields=["active_version"])

    def _family_history(self, patient, clinician):
        """type-10022026-Maurice: Seed one approved synthetic family-history version."""
        history, _ = FamilyHistory.objects.get_or_create(patient=patient)
        if not history.active_version:
            version = FamilyHistoryVersion.objects.create(history=history, version=1, relationship="mother", relative_sex="female", relative_status="deceased", relative_deceased=True, condition_system="http://snomed.info/sct", condition_code="IHD-001", condition_display="Synthetic ischemic heart disease", submitted_display="Synthetic ischemic heart disease", terminology_version="synthetic-2026-01", recorded_date=date(2026, 1, 1), created_by=clinician)
            history.active_version = version; history.save(update_fields=["active_version"])

    def _interactions(self):
        InteractionRule.objects.get_or_create(kind=InteractionRule.Kind.DRUG_ALLERGY, medication_code="AMOX", allergy_code="227493005", defaults={"severity": InteractionRule.Severity.HIGH, "description": "Synthetic allergy alert"})
        InteractionRule.objects.get_or_create(kind=InteractionRule.Kind.DRUG_DRUG, medication_code="AMOX", related_medication_code="WARFARIN", defaults={"severity": InteractionRule.Severity.MODERATE, "description": "Synthetic drug interaction"})
        AlertConfiguration.objects.get_or_create(singleton=True, defaults={"severity_floor": AlertConfiguration.SeverityFloor.LOW})

    def _questionnaire(self, clinician):
        questionnaire, _ = Questionnaire.objects.get_or_create(code="demo-health-check", defaults={"title": "Synthetic health check"})
        if not questionnaire.active_version:
            version = QuestionnaireVersion.objects.create(questionnaire=questionnaire, version=1, status=QuestionnaireVersion.Status.ACTIVE, allow_draft=True, created_by=clinician)
            items = [("well", "Feeling well?", "boolean", True, False, {},), ("days", "Days of symptoms", "integer", True, False, {"min_value": 0, "max_value": 365},), ("temperature", "Temperature", "decimal", False, False, {"min_value": 30, "max_value": 45},), ("onset", "Onset date", "date", False, False, {},), ("note", "Additional note", "string", False, False, {"max_length": 240},), ("visit_type", "Visit type", "choice", True, False, {"options": ["routine", "urgent"]},), ("weight", "Weight", "quantity", False, False, {"min_value": 0, "max_value": 500},)]
            for ordinal, (link_id, text, item_type, required, repeats, bounds) in enumerate(items, 1):
                QuestionnaireItem.objects.create(questionnaire_version=version, link_id=link_id, text=text, item_type=item_type, ordinal=ordinal, required=required, repeats=repeats, **bounds)
            questionnaire.active_version = version
            questionnaire.save(update_fields=["active_version"])

    def _reset(self):
        demo_users = User.objects.filter(username__in=DEMO_USERS)
        demo_patients = Patient.objects.filter(public_id__in=("P001", "P002", "P003", "P004"))
        QuestionnaireReview.objects.filter(response_version__response__patient__in=demo_patients).delete()
        QuestionnaireOutboxEvent.objects.filter(response_version__response__patient__in=demo_patients).delete()
        QuestionnaireResponseVersion.objects.filter(response__patient__in=demo_patients).delete()
        QuestionnaireResponse.objects.filter(patient__in=demo_patients).delete()
        QuestionnaireItem.objects.filter(questionnaire_version__questionnaire__code="demo-health-check").delete()
        Questionnaire.objects.filter(code="demo-health-check").update(active_version=None)
        QuestionnaireVersion.objects.filter(questionnaire__code="demo-health-check").delete()
        Questionnaire.objects.filter(code="demo-health-check").delete()
        PatientExport.objects.filter(patient__in=demo_patients).delete()
        InteractionAcknowledgement.objects.filter(evaluation__medication_version__order__patient__in=demo_patients).delete()
        InteractionEvaluation.objects.filter(medication_version__order__patient__in=demo_patients).delete()
        MedicationOrder.objects.filter(patient__in=demo_patients).update(active_version=None)
        MedicationOrderVersion.objects.filter(order__patient__in=demo_patients).delete()
        MedicationOrder.objects.filter(patient__in=demo_patients).delete()
        FamilyHistoryOutboxEvent.objects.filter(family_history__patient__in=demo_patients).delete()
        FamilyHistory.objects.filter(patient__in=demo_patients).update(active_version=None)
        FamilyHistoryVersion.objects.filter(history__patient__in=demo_patients).delete()
        FamilyHistory.objects.filter(patient__in=demo_patients).delete()
        DeviceOutboxEvent.objects.filter(device__patient__in=demo_patients).delete()
        Device.objects.filter(patient__in=demo_patients).update(active_version=None)
        DeviceVersion.objects.filter(device__patient__in=demo_patients).delete()
        Device.objects.filter(patient__in=demo_patients).delete()
        AuditEvent.objects.filter(patient__in=demo_patients).delete()
        AuditEvent.objects.filter(actor__in=demo_users).delete()
        demo_patients.delete()
        Application.objects.filter(user__in=demo_users).delete()
        demo_users.delete()
        InteractionRule.objects.filter(medication_code__in=("AMOX", "WARFARIN")).delete()
        log_event("demo.reset.success", component="seed", operation="reset", outcome="success", boundary="database")
