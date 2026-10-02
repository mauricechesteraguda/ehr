"""type-10022026-Maurice: PostgreSQL-persisted role and TOTP enrollment state."""
from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid


class User(AbstractUser):
    """type-10022026-Maurice: Application identity with explicit role and MFA state."""
    class Role(models.TextChoices):
        CLINICIAN = "clinician", "Clinician"
        PATIENT = "patient", "Patient"
        ADMIN = "admin", "Administrator"
        DEVELOPER = "developer", "Developer"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    totp_secret = models.CharField(max_length=64, blank=True, default="")
    totp_enrolled = models.BooleanField(default=False)
    recovery_phone_hash = models.CharField(max_length=64, blank=True, default="")
    mfa_generation = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        indexes = [models.Index(fields=["role", "is_active"], name="user_role_active_idx")]


class WebAuthnCredential(models.Model):
    """Ticket07 expansion: public authenticator metadata only; no attestation trust claim."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="webauthn_credentials")
    credential_id = models.BinaryField(unique=True)
    public_key = models.BinaryField()
    sign_count = models.PositiveBigIntegerField(default=0)
    transports = models.JSONField(default=list)
    backup_eligible = models.BooleanField(default=False)
    backup_state = models.BooleanField(default=False)
    user_verified = models.BooleanField(default=False)
    name = models.CharField(max_length=80, default="Passkey")
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class WebAuthnChallenge(models.Model):
    """Single-use, session-bound ceremony state; challenge bytes are never logged."""
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40)
    challenge_hash = models.CharField(max_length=64, unique=True)
    ceremony = models.CharField(max_length=16)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)


class SmsRecoveryChallenge(models.Model):
    """Deterministic demo delivery record; only a hash of the code is retained."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    code_hash = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)
    delivery_reference = models.CharField(max_length=80)


class Patient(models.Model):
    """type-10022026-Maurice: Synthetic patient demographics with coded values only."""
    public_id = models.CharField(max_length=20, unique=True)
    given_name = models.CharField(max_length=80, blank=True, default="")
    family_name = models.CharField(max_length=80, blank=True, default="")
    owner = models.OneToOneField(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="patient_record")
    display_name = models.CharField(max_length=80)
    race = models.CharField(max_length=40, choices=[("2106-3", "White"), ("2054-5", "Black or African American"), ("UNK", "Unknown")], default="UNK")
    ethnicity = models.CharField(max_length=40, choices=[("2186-5", "Not Hispanic or Latino"), ("2135-2", "Hispanic or Latino"), ("UNK", "Unknown")], default="UNK")
    preferred_language = models.CharField(max_length=20, choices=[("en", "English"), ("es", "Spanish"), ("UNK", "Unknown")], default="en")
    sex = models.CharField(max_length=20, choices=[("female", "Female"), ("male", "Male"), ("unknown", "Unknown")], default="unknown")
    sexual_orientation = models.CharField(max_length=30, choices=[("straight", "Straight"), ("gay", "Gay or lesbian"), ("unknown", "Unknown")], default="unknown")
    gender_identity = models.CharField(max_length=30, choices=[("woman", "Woman"), ("man", "Man"), ("non-binary", "Non-binary"), ("unknown", "Unknown")], default="unknown")
    birth_date = models.DateField()
    death_date = models.DateField(null=True, blank=True)
    restricted_access = models.BooleanField(default=False)

    class Meta:
        ordering = ["public_id"]

    def clean(self):
        """type-10022026-Maurice: Reject impossible synthetic demographic dates."""
        from django.core.exceptions import ValidationError
        if self.death_date and self.death_date < self.birth_date:
            raise ValidationError({"death_date": "Death date must not precede birth date."})


class SmartTokenContext(models.Model):
    """Ticket09: immutable proof that a SMART token was issued from MFA context."""
    access_token = models.OneToOneField("oauth2_provider.AccessToken", on_delete=models.CASCADE, related_name="mfa_context")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="smart_token_contexts")
    application = models.ForeignKey("oauth2_provider.Application", on_delete=models.CASCADE, related_name="mfa_token_contexts")
    mfa_generation = models.PositiveIntegerField()
    completed_at = models.DateTimeField()


class ClinicianPatientAssignment(models.Model):
    """type-10022026-Maurice: Explicit normal-access policy for restricted synthetic patients."""
    clinician = models.ForeignKey(User, on_delete=models.CASCADE, related_name="patient_assignments")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="clinician_assignments")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["clinician", "patient"], name="clinician_patient_assignment_unique")]


class EmergencyAccessRequest(models.Model):
    """type-10022026-Maurice: A non-renewable, read-only 30-minute break-glass grant."""
    class State(models.TextChoices):
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    class ReviewOutcome(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        SUSPICIOUS = "suspicious", "Suspicious"
        ESCALATED = "escalated", "Escalated"

    clinician = models.ForeignKey(User, on_delete=models.PROTECT, related_name="emergency_access_requests")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="emergency_access_requests")
    justification = models.CharField(max_length=500)
    requested_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    state = models.CharField(max_length=10, choices=State.choices, default=State.ACTIVE)
    revoked_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="emergency_access_reviews")
    review_outcome = models.CharField(max_length=12, choices=ReviewOutcome.choices, blank=True, default="")
    suspicious = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["state", "expires_at"], name="emergency_expiry_idx"), models.Index(fields=["reviewed_at"], name="emergency_review_idx")]


class EmergencyAccessOutboxEvent(models.Model):
    """type-10022026-Maurice: Payload-free notification intent committed with a grant."""
    request = models.ForeignKey(EmergencyAccessRequest, on_delete=models.CASCADE, related_name="outbox_events")
    kind = models.CharField(max_length=40, default="break_glass_granted")
    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)


class FamilyHistory(models.Model):
    """type-10022026-Maurice: Stable synthetic family-history identity; versions are append-only."""
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="family_histories")
    active_version = models.ForeignKey("FamilyHistoryVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="active_for")
    created_at = models.DateTimeField(auto_now_add=True)


class FamilyHistoryVersion(models.Model):
    """type-10022026-Maurice: Provenance-preserving family-history snapshot."""
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        ENTERED_IN_ERROR = "entered-in-error", "Entered in error"

    history = models.ForeignKey(FamilyHistory, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    relationship = models.CharField(max_length=40)
    relative_sex = models.CharField(max_length=20, default="unknown")
    relative_status = models.CharField(max_length=30, default="unknown")
    relative_deceased = models.BooleanField(null=True, blank=True)
    condition_system = models.URLField(max_length=300)
    condition_code = models.CharField(max_length=80)
    condition_display = models.CharField(max_length=240)
    submitted_display = models.CharField(max_length=240, blank=True, default="")
    terminology_version = models.CharField(max_length=80, blank=True, default="")
    onset_date = models.DateField(null=True, blank=True)
    recorded_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    supersedes = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="superseded_by")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="family_history_versions_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["history", "version"], name="family_history_version_unique")]
        ordering = ["version"]

    def save(self, *args, **kwargs):
        """type-10022026-Maurice: Prevent mutation of clinical history evidence."""
        if self.pk:
            raise ValueError("Family history is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """type-10022026-Maurice: Corrections use entered-in-error versions, never deletion."""
        raise ValueError("Family history cannot be deleted")


class FamilyHistoryOutboxEvent(models.Model):
    """type-10022026-Maurice: Atomic, payload-free family-history integration intent."""
    family_history = models.ForeignKey(FamilyHistory, on_delete=models.CASCADE, related_name="outbox_events")
    version = models.ForeignKey(FamilyHistoryVersion, on_delete=models.CASCADE)
    kind = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)


class ClinicalRecord(models.Model):
    """type-10022026-Maurice: Read-only synthetic clinical record display values."""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="%(class)s_records")
    code = models.CharField(max_length=40)
    label = models.CharField(max_length=120)
    recorded_date = models.DateField(null=True, blank=True)

    class Meta:
        abstract = True


class AllergyIntolerance(ClinicalRecord):
    """type-10022026-Maurice: Synthetic allergy/intolerance display record."""
    reaction = models.CharField(max_length=120, blank=True)


class Condition(ClinicalRecord):
    """type-10022026-Maurice: Synthetic condition display record."""
    status = models.CharField(max_length=30, default="active")


class Observation(ClinicalRecord):
    """type-10022026-Maurice: Synthetic observation display record."""
    value = models.CharField(max_length=120)
    unit = models.CharField(max_length=30, blank=True)


class Device(ClinicalRecord):
    """Ticket04: Stable device identity; clinical evidence lives in immutable versions."""
    status = models.CharField(max_length=30, default="active")
    udi = models.CharField(max_length=256, blank=True, default="")
    active_version = models.ForeignKey("DeviceVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="active_for")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["patient", "udi"], condition=~models.Q(udi=""), name="device_patient_udi_unique")]


class DeviceVersion(models.Model):
    """Ticket04: Append-only UDI/provenance snapshot; corrections supersede, never mutate."""
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        INACTIVE = "inactive", "Inactive"
        ENTERED_IN_ERROR = "entered-in-error", "Entered in error"

    class ParseStatus(models.TextChoices):
        PARSED = "parsed", "Parsed"
        PARSE_FAILED = "parse_failed", "Parse failed"
        UNSUPPORTED = "unsupported", "Unsupported"

    device = models.ForeignKey(Device, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    code = models.CharField(max_length=80)
    label = models.CharField(max_length=160)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    issuer = models.CharField(max_length=20)
    device_identifier = models.CharField(max_length=80, blank=True, default="")
    lot_number = models.CharField(max_length=20, blank=True, default="")
    serial_number = models.CharField(max_length=20, blank=True, default="")
    expiry_date = models.DateField(null=True, blank=True)
    manufacture_date = models.DateField(null=True, blank=True)
    raw_input = models.CharField(max_length=256, blank=True, default="")
    parser_version = models.CharField(max_length=40)
    parse_status = models.CharField(max_length=20, choices=ParseStatus.choices)
    parse_error_code = models.CharField(max_length=50, blank=True, default="")
    gudid_status = models.CharField(max_length=20, default="not_requested")
    supersedes = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="superseded_by")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="device_versions_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["device", "version"], name="device_version_unique")]
        ordering = ["version"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Device history is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Device history cannot be deleted")


class DeviceOutboxEvent(models.Model):
    """Ticket04: Atomic payload-free integration intent for device changes."""
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name="outbox_events")
    version = models.ForeignKey(DeviceVersion, on_delete=models.CASCADE)
    kind = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)


class AuditEvent(models.Model):
    """type-10022026-Maurice: Immutable, hash-chained security audit evidence."""
    sequence = models.BigAutoField(primary_key=True)
    actor = models.ForeignKey(User, null=True, on_delete=models.PROTECT, related_name="audit_events")
    occurred_at = models.DateTimeField()
    patient = models.ForeignKey(Patient, null=True, blank=True, on_delete=models.PROTECT, related_name="audit_events")
    action = models.CharField(max_length=20)
    resource_type = models.CharField(max_length=80)
    resource_id = models.CharField(max_length=120)
    correlation_id = models.CharField(max_length=80)
    previous_hash = models.CharField(max_length=64)
    current_hash = models.CharField(max_length=64)

    class Meta:
        ordering = ["sequence"]
        indexes = [models.Index(fields=["occurred_at"], name="audit_occurred_at_idx"), models.Index(fields=["action"], name="audit_action_idx")]


class MeasureDefinition(models.Model):
    """Ticket14 stable identity; versions contain the immutable executable-free schema."""
    url = models.CharField(max_length=240, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    provenance = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class MeasureVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"; PUBLISHED = "published", "Published"; RETIRED = "retired", "Retired"
    measure = models.ForeignKey(MeasureDefinition, related_name="versions", on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    effective_start = models.DateField(); effective_end = models.DateField(null=True, blank=True)
    schema = models.JSONField(); provenance = models.JSONField(default=dict)
    published_at = models.DateTimeField(null=True, blank=True)
    class Meta: constraints = [models.UniqueConstraint(fields=["measure", "version"], name="measure_version_unique")]
    def save(self, *args, **kwargs):
        if self.pk: raise ValueError("Measure versions are immutable")
        return super().save(*args, **kwargs)
    def delete(self, *args, **kwargs): raise ValueError("Measure versions are immutable")


class MeasureRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.OneToOneField("Job", on_delete=models.PROTECT, related_name="measure_run")
    version = models.ForeignKey(MeasureVersion, on_delete=models.PROTECT)
    period_start = models.DateField(); period_end = models.DateField(); snapshot_checksum = models.CharField(max_length=64)
    status = models.CharField(max_length=20, default="queued"); created_at = models.DateTimeField(auto_now_add=True)


class MeasureReport(models.Model):
    run = models.OneToOneField(MeasureRun, on_delete=models.PROTECT, related_name="report")
    measure = models.ForeignKey(MeasureDefinition, on_delete=models.PROTECT)
    version = models.ForeignKey(MeasureVersion, on_delete=models.PROTECT)
    status = models.CharField(max_length=20); period_start = models.DateField(); period_end = models.DateField()
    snapshot_checksum = models.CharField(max_length=64); populations = models.JSONField(); created_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        if self.pk: raise ValueError("Measure reports are immutable")
        return super().save(*args, **kwargs)


class MedicationOrder(models.Model):
    """type-10022026-Maurice: Stable medication identity whose versions are immutable."""
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="medication_orders")
    prescriber = models.ForeignKey(User, on_delete=models.PROTECT, related_name="prescribed_medications")
    active_version = models.ForeignKey("MedicationOrderVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="active_for")
    created_at = models.DateTimeField(auto_now_add=True)


class MedicationOrderVersion(models.Model):
    """type-10022026-Maurice: Append-only medication draft/history version; signing is Ticket05."""
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        CANCELLED = "cancelled", "Cancelled"

    order = models.ForeignKey(MedicationOrder, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    medication_code = models.CharField(max_length=80)
    medication_name = models.CharField(max_length=160)
    dose = models.DecimalField(max_digits=12, decimal_places=3)
    dose_unit = models.CharField(max_length=30)
    route = models.CharField(max_length=40)
    frequency = models.CharField(max_length=40)
    start_date = models.DateField()
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    refills = models.PositiveIntegerField(default=0)
    indication = models.CharField(max_length=240)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    supersedes = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="superseded_by")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="medication_versions_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["order", "version"], name="med_order_version_unique")]
        ordering = ["version"]

    def save(self, *args, **kwargs):
        """type-10022026-Maurice: Prevent in-place edits to clinical history."""
        if self.pk:
            raise ValueError("Medication history is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """type-10022026-Maurice: Medication history cannot be deleted."""
        raise ValueError("Medication history is immutable")


class InteractionRule(models.Model):
    """type-10022026-Maurice: Synthetic, administrator-managed safety rule metadata."""
    class Kind(models.TextChoices):
        DRUG_DRUG = "DRUG_DRUG", "Drug-drug"
        DRUG_ALLERGY = "DRUG_ALLERGY", "Drug-allergy"

    class Severity(models.TextChoices):
        LOW = "LOW", "Low"
        MODERATE = "MODERATE", "Moderate"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    medication_code = models.CharField(max_length=80)
    related_medication_code = models.CharField(max_length=80, blank=True, default="")
    allergy_code = models.CharField(max_length=80, blank=True, default="")
    severity = models.CharField(max_length=10, choices=Severity.choices)
    description = models.CharField(max_length=240, default="Synthetic demo rule")
    active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["active", "severity"], name="rule_active_severity_idx"), models.Index(fields=["medication_code", "active"], name="rule_med_active_idx")]

    def save(self, *args, **kwargs):
        """type-10022026-Maurice: Validate rule shape before persistence."""
        from django.core.exceptions import ValidationError
        if self.kind == self.Kind.DRUG_DRUG and not self.related_medication_code:
            raise ValidationError("Drug-drug rules require a related medication code.")
        if self.kind == self.Kind.DRUG_ALLERGY and not self.allergy_code:
            raise ValidationError("Drug-allergy rules require an allergy code.")
        return super().save(*args, **kwargs)


class AlertConfiguration(models.Model):
    """type-10022026-Maurice: Singleton synthetic alert floor; critical is never suppressed."""
    class SeverityFloor(models.TextChoices):
        LOW = "LOW", "Low"
        MODERATE = "MODERATE", "Moderate"
        HIGH = "HIGH", "High"

    singleton = models.BooleanField(default=True, unique=True)
    severity_floor = models.CharField(max_length=10, choices=SeverityFloor.choices, default=SeverityFloor.LOW)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["severity_floor"], name="alert_floor_idx")]


class InteractionEvaluation(models.Model):
    """type-10022026-Maurice: Immutable point-in-time interaction evaluation evidence."""
    medication_version = models.ForeignKey(MedicationOrderVersion, on_delete=models.PROTECT, related_name="evaluations")
    evaluated_at = models.DateTimeField()
    fingerprint = models.CharField(max_length=64)
    floor = models.CharField(max_length=10)
    findings = models.JSONField(default=list)
    stale = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="interaction_evaluations")

    def save(self, *args, **kwargs):
        """type-10022026-Maurice: Evaluation evidence is append-only."""
        if self.pk:
            raise ValueError("Interaction evaluation is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """type-10022026-Maurice: Evaluation evidence cannot be deleted."""
        raise ValueError("Interaction evaluation is immutable")


class InteractionAcknowledgement(models.Model):
    """type-10022026-Maurice: Immutable clinician acknowledgement evidence."""
    evaluation = models.ForeignKey(InteractionEvaluation, on_delete=models.PROTECT, related_name="acknowledgements")
    clinician = models.ForeignKey(User, on_delete=models.PROTECT, related_name="interaction_acknowledgements")
    acknowledged_at = models.DateTimeField()

    def save(self, *args, **kwargs):
        """type-10022026-Maurice: Acknowledgements are append-only."""
        if self.pk:
            raise ValueError("Interaction acknowledgement is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """type-10022026-Maurice: Acknowledgements cannot be deleted."""
        raise ValueError("Interaction acknowledgement is immutable")


class PatientExport(models.Model):
    """type-10022026-Maurice: Short-lived, server-owned patient download artifact."""
    class Format(models.TextChoices):
        JSON = "json", "JSON"
        PDF = "pdf", "PDF"

    artifact_id = models.UUIDField(unique=True, editable=False, default=uuid.uuid4)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="exports")
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="patient_exports")
    format = models.CharField(max_length=4, choices=Format.choices)
    path = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["patient", "requested_by", "format"], name="one_active_export_slot")]


class Job(models.Model):
    """Ticket02 durable job contract; Redis carries only this opaque identifier."""
    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=80)
    owner = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="jobs")
    patient = models.ForeignKey(Patient, null=True, blank=True, on_delete=models.PROTECT, related_name="jobs")
    input_checksum = models.CharField(max_length=64)
    redacted_input = models.JSONField(default=dict)
    idempotency_key = models.CharField(max_length=160)
    state = models.CharField(max_length=20, choices=State.choices, default=State.QUEUED)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    queued_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    error_class = models.CharField(max_length=120, blank=True, default="")
    error_code = models.CharField(max_length=80, blank=True, default="")
    result_ref = models.CharField(max_length=160, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["idempotency_key"], name="job_idempotency_unique"), models.CheckConstraint(check=models.Q(max_attempts__gte=1, max_attempts__lte=3), name="job_max_attempts_1_3")]
        indexes = [models.Index(fields=["state", "queued_at"], name="job_dispatch_idx"), models.Index(fields=["heartbeat_at"], name="job_heartbeat_idx")]


class CcdaDocument(models.Model):
    """Ticket11: immutable bounded transition metadata; bytes remain encrypted on disk."""
    job = models.OneToOneField(Job, on_delete=models.PROTECT, related_name="ccda_document")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="ccda_documents")
    direction = models.CharField(max_length=8)
    template_id = models.CharField(max_length=120)
    template_version = models.CharField(max_length=40)
    provenance = models.JSONField(default=dict)
    sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField(default=0)
    artifact_path = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("C-CDA document metadata is immutable")
        return super().save(*args, **kwargs)


class DirectDelivery(models.Model):
    """Ticket12: local-only Direct-shaped delivery metadata; no recipient or payload is retained."""
    class State(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    artifact = models.ForeignKey(CcdaDocument, on_delete=models.PROTECT, related_name="direct_deliveries")
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="direct_deliveries")
    recipient_hash = models.CharField(max_length=64)
    recipient_ciphertext = models.BinaryField()
    purpose = models.CharField(max_length=240)
    idempotency_key = models.CharField(max_length=160, unique=True)
    state = models.CharField(max_length=20, choices=State.choices, default=State.QUEUED)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    error_code = models.CharField(max_length=40, blank=True, default="")
    receipt_code = models.CharField(max_length=80, blank=True, default="")
    receipt_checksum = models.CharField(max_length=64, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(check=models.Q(max_attempts__gte=1, max_attempts__lte=3), name="direct_max_attempts_1_3")]
        indexes = [models.Index(fields=["owner", "created_at"], name="direct_owner_created_idx")]


class DirectDeliveryAttempt(models.Model):
    """Ticket12: immutable attempt metadata; adapter responses are reduced to safe codes."""
    delivery = models.ForeignKey(DirectDelivery, on_delete=models.PROTECT, related_name="delivery_attempts")
    number = models.PositiveSmallIntegerField()
    state = models.CharField(max_length=20, choices=DirectDelivery.State.choices)
    outcome_code = models.CharField(max_length=40, blank=True, default="")
    receipt_checksum = models.CharField(max_length=64, blank=True, default="")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["delivery", "number"], name="direct_attempt_number_unique")]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Direct delivery attempts are immutable")
        return super().save(*args, **kwargs)


class DirectDeliveryOutbox(models.Model):
    """Ticket12: transactional, payload-free intent for the local delivery worker."""
    delivery = models.OneToOneField(DirectDelivery, on_delete=models.CASCADE, related_name="outbox")
    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)


class ReconciliationCandidate(models.Model):
    """Ticket11: imported FHIR-shaped proposal; never a clinical record until accepted."""
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        DEFERRED = "deferred", "Deferred"
        STALE = "stale", "Stale"
        CONFLICT = "conflict", "Conflict"

    document = models.ForeignKey(CcdaDocument, on_delete=models.PROTECT, related_name="candidates")
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="reconciliation_candidates")
    section = models.CharField(max_length=30)
    resource_type = models.CharField(max_length=40)
    payload = models.JSONField()
    source_fingerprint = models.CharField(max_length=64)
    state = models.CharField(max_length=12, choices=State.choices, default=State.PENDING)
    decided_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "source_fingerprint"], name="ccda_candidate_fingerprint_unique")]


class JobAttempt(models.Model):
    """Per-delivery state; error fields are deliberately class/code only."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="job_attempts")
    number = models.PositiveSmallIntegerField()
    state = models.CharField(max_length=20, choices=Job.State.choices, default=Job.State.RUNNING)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    heartbeat_at = models.DateTimeField(null=True, blank=True)
    error_class = models.CharField(max_length=120, blank=True, default="")
    error_code = models.CharField(max_length=80, blank=True, default="")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["job", "number"], name="job_attempt_number_unique")]


class OutboxEvent(models.Model):
    """Transactional intent; body contains no clinical data, only job contract metadata."""
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        DISPATCHED = "dispatched", "Dispatched"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="outbox_events")
    kind = models.CharField(max_length=80)
    state = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["state", "created_at"], name="outbox_pending_idx")]


class CDSService(models.Model):
    """Ticket13: versioned, local-only CDS Hooks service metadata."""
    id = models.CharField(max_length=80, primary_key=True)
    hook = models.CharField(max_length=40)
    title = models.CharField(max_length=160)
    description = models.CharField(max_length=240, default="Deterministic non-clinical demo")
    version = models.CharField(max_length=20, default="1.0.0")
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["id", "version"], name="cds_service_version_unique")]


class CDSRuleVersion(models.Model):
    """Published rule snapshots are immutable; activation is an admin-only pointer."""
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    service = models.ForeignKey(CDSService, on_delete=models.PROTECT, related_name="rules")
    rule_key = models.CharField(max_length=80)
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    config = models.JSONField(default=dict)
    safety_critical = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["service", "rule_key", "version"], name="cds_rule_version_unique")]

    def save(self, *args, **kwargs):
        if self.pk and CDSRuleVersion.objects.filter(pk=self.pk).exclude(status=self.status).exists():
            # Status transitions are the only permitted mutation after publication.
            previous = CDSRuleVersion.objects.get(pk=self.pk)
            if previous.published_at and self.config != previous.config:
                raise ValueError("Published CDS rule is immutable")
        if self.pk and CDSRuleVersion.objects.filter(pk=self.pk, published_at__isnull=False).exists() and self.config != CDSRuleVersion.objects.get(pk=self.pk).config:
            raise ValueError("Published CDS rule is immutable")
        return super().save(*args, **kwargs)


class CDSInvocation(models.Model):
    """Immutable, PHI-free invocation evidence and idempotency boundary."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_key = models.CharField(max_length=120)
    hook = models.CharField(max_length=40)
    service = models.ForeignKey(CDSService, on_delete=models.PROTECT)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT)
    context_fingerprint = models.CharField(max_length=64)
    outcome = models.CharField(max_length=20, default="success")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["service", "request_key"], name="cds_invocation_idempotency_unique")]


class CDSCard(models.Model):
    """Immutable card snapshot returned by an invocation."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invocation = models.ForeignKey(CDSInvocation, on_delete=models.PROTECT, related_name="cards")
    rule = models.ForeignKey(CDSRuleVersion, on_delete=models.PROTECT)
    summary = models.CharField(max_length=240)
    detail = models.CharField(max_length=500)
    indicator = models.CharField(max_length=10)
    source = models.JSONField(default=dict)
    suggestions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


class CDSCardAction(models.Model):
    """Append-only clinician response; accepts never mutate domain data directly."""
    class Action(models.TextChoices):
        ACCEPT = "accept", "Accept"
        DISMISS = "dismiss", "Dismiss"
        OVERRIDE = "override", "Override"

    card = models.ForeignKey(CDSCard, on_delete=models.PROTECT, related_name="actions")
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=10, choices=Action.choices)
    suggestion_id = models.CharField(max_length=80, blank=True, default="")
    reason = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["card", "actor", "action", "suggestion_id"], name="cds_card_action_idempotent")]


class CDSOutboxEvent(models.Model):
    """Atomic, payload-free integration intent for CDS audit consumers."""
    invocation = models.ForeignKey(CDSInvocation, on_delete=models.PROTECT, related_name="outbox_events")
    card = models.ForeignKey(CDSCard, null=True, blank=True, on_delete=models.PROTECT)
    kind = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)


class PopulationExportSchedule(models.Model):
    """Ticket10: administrator-owned, all-demo-patient export schedule metadata."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="population_export_schedules")
    scope = models.CharField(max_length=20, default="all-demo")
    start_date = models.DateField()
    end_date = models.DateField()
    purpose = models.CharField(max_length=500)
    format = models.CharField(max_length=20)
    timezone = models.CharField(max_length=64, default="UTC")
    cadence = models.CharField(max_length=20, default="once")
    next_run_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PopulationExportArtifact(models.Model):
    """Ticket10: encrypted-at-rest artifact; path and payload never enter API/audit logs."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.OneToOneField(Job, on_delete=models.CASCADE, related_name="population_artifact")
    schedule = models.ForeignKey(PopulationExportSchedule, null=True, blank=True, on_delete=models.SET_NULL, related_name="artifacts")
    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name="population_export_artifacts")
    format = models.CharField(max_length=20)
    path = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveBigIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()


class Questionnaire(models.Model):
    """Ticket05: Stable questionnaire identity; published snapshots never change."""
    code = models.CharField(max_length=80, unique=True)
    title = models.CharField(max_length=160)
    active_version = models.ForeignKey("QuestionnaireVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="active_for")
    created_at = models.DateTimeField(auto_now_add=True)


class QuestionnaireVersion(models.Model):
    """Ticket05: Immutable, ordered questionnaire definition snapshot."""
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        RETIRED = "retired", "Retired"

    questionnaire = models.ForeignKey(Questionnaire, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    allow_draft = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="questionnaire_versions_created")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["questionnaire", "version"], name="questionnaire_version_unique")]
        ordering = ["version"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Questionnaire version is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Questionnaire version cannot be deleted")


class QuestionnaireItem(models.Model):
    """Ticket05: Immutable typed item belonging to one questionnaire version."""
    class ItemType(models.TextChoices):
        BOOLEAN = "boolean", "Boolean"
        INTEGER = "integer", "Integer"
        DECIMAL = "decimal", "Decimal"
        DATE = "date", "Date"
        STRING = "string", "String"
        CHOICE = "choice", "Choice"
        QUANTITY = "quantity", "Quantity"

    questionnaire_version = models.ForeignKey(QuestionnaireVersion, on_delete=models.PROTECT, related_name="items")
    link_id = models.CharField(max_length=80)
    text = models.CharField(max_length=240)
    item_type = models.CharField(max_length=12, choices=ItemType.choices)
    ordinal = models.PositiveIntegerField()
    required = models.BooleanField(default=False)
    repeats = models.BooleanField(default=False)
    min_length = models.PositiveIntegerField(null=True, blank=True)
    max_length = models.PositiveIntegerField(null=True, blank=True)
    min_value = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    max_value = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)
    options = models.JSONField(default=list, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["questionnaire_version", "link_id"], name="questionnaire_item_link_unique"), models.UniqueConstraint(fields=["questionnaire_version", "ordinal"], name="questionnaire_item_order_unique")]
        ordering = ["ordinal", "link_id"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Questionnaire item is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Questionnaire item cannot be deleted")


class QuestionnaireResponse(models.Model):
    """Ticket05: Stable response identity whose versions are immutable corrections."""
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="questionnaire_responses")
    questionnaire = models.ForeignKey(Questionnaire, on_delete=models.PROTECT, related_name="responses")
    active_version = models.ForeignKey("QuestionnaireResponseVersion", null=True, blank=True, on_delete=models.PROTECT, related_name="active_for")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="questionnaire_responses_created")
    created_at = models.DateTimeField(auto_now_add=True)


class QuestionnaireResponseVersion(models.Model):
    """Ticket05: Immutable answers pinned to the exact questionnaire definition."""
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        RETURNED = "returned", "Returned"

    response = models.ForeignKey(QuestionnaireResponse, on_delete=models.PROTECT, related_name="versions")
    questionnaire_version = models.ForeignKey(QuestionnaireVersion, on_delete=models.PROTECT, related_name="response_versions")
    version = models.PositiveIntegerField()
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    answers = models.JSONField(default=dict)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="questionnaire_response_versions_created")
    supersedes = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="corrections")
    submitted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["response", "version"], name="questionnaire_response_version_unique")]
        ordering = ["version"]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Questionnaire response version is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Questionnaire response version cannot be deleted")


class QuestionnaireReview(models.Model):
    """Ticket05: Immutable clinician review decision for one submitted response."""
    class Decision(models.TextChoices):
        ACCEPTED = "accepted", "Accepted"
        RETURNED = "returned", "Returned"
        REJECTED = "rejected", "Rejected"

    response_version = models.ForeignKey(QuestionnaireResponseVersion, on_delete=models.PROTECT, related_name="reviews")
    reviewer = models.ForeignKey(User, on_delete=models.PROTECT, related_name="questionnaire_reviews")
    decision = models.CharField(max_length=12, choices=Decision.choices)
    reason = models.CharField(max_length=500, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Questionnaire review is immutable")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Questionnaire review cannot be deleted")


class QuestionnaireOutboxEvent(models.Model):
    """Ticket05: Payload-free notification intent committed with domain changes."""
    response_version = models.ForeignKey(QuestionnaireResponseVersion, on_delete=models.CASCADE, related_name="outbox_events")
    kind = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)


class PatientAmendment(models.Model):
    """Ticket06: immutable patient amendment request and source evidence."""
    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        UNDER_REVIEW = "under_review", "Under review"
        ACCEPTED = "accepted", "Accepted"
        DENIED = "denied", "Denied"
        APPENDED = "appended", "Appended"

    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, related_name="amendments")
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="amendments_requested")
    resource_type = models.CharField(max_length=80)
    resource_id = models.CharField(max_length=120)
    source_version = models.PositiveIntegerField()
    source_reference = models.CharField(max_length=240)
    source_checksum = models.CharField(max_length=64)
    source_snapshot = models.JSONField()
    proposed_data = models.JSONField(default=dict)
    reason = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SUBMITTED)
    submitted_at = models.DateTimeField()
    due_at = models.DateTimeField()
    reviewer = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name="amendments_reviewed")
    decision_reason = models.CharField(max_length=500, blank=True, default="")
    decided_at = models.DateTimeField(null=True, blank=True)
    accepted_version = models.PositiveIntegerField(null=True, blank=True)
    addendum = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["due_at", "id"]
        indexes = [models.Index(fields=["status", "due_at"], name="amendment_queue_idx"), models.Index(fields=["patient", "submitted_at"], name="amendment_patient_idx")]

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.get(pk=self.pk)
            immutable = ("patient_id", "requested_by_id", "resource_type", "resource_id", "source_version", "source_reference", "source_checksum", "source_snapshot", "proposed_data", "reason", "submitted_at", "due_at")
            if any(getattr(previous, field) != getattr(self, field) for field in immutable):
                raise ValueError("Amendment evidence is immutable")
        return super().save(*args, **kwargs)


class PatientAmendmentOutbox(models.Model):
    """Ticket06: retryable, payload-free notification intent."""
    class State(models.TextChoices):
        PENDING = "pending", "Pending"
        RETRY = "retry", "Retry"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    amendment = models.ForeignKey(PatientAmendment, on_delete=models.CASCADE, related_name="outbox_events")
    kind = models.CharField(max_length=80)
    state = models.CharField(max_length=12, choices=State.choices, default=State.PENDING)
    attempts = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    last_error_code = models.CharField(max_length=80, blank=True, default="")


class PatientAmendmentCorrection(models.Model):
    """Ticket06: versioned correction/addendum projection; source remains untouched."""
    amendment = models.OneToOneField(PatientAmendment, on_delete=models.PROTECT, related_name="correction")
    resource_type = models.CharField(max_length=80)
    resource_id = models.CharField(max_length=120)
    version = models.PositiveIntegerField()
    data = models.JSONField(default=dict)
    supersedes_version = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["resource_type", "resource_id", "version"], name="amendment_correction_version_unique")]
