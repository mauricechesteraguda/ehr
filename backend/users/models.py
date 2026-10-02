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

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"
        indexes = [models.Index(fields=["role", "is_active"], name="user_role_active_idx")]


class Patient(models.Model):
    """type-10022026-Maurice: Synthetic patient demographics with coded values only."""
    public_id = models.CharField(max_length=20, unique=True)
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

    class Meta:
        ordering = ["public_id"]

    def clean(self):
        """type-10022026-Maurice: Reject impossible synthetic demographic dates."""
        from django.core.exceptions import ValidationError
        if self.death_date and self.death_date < self.birth_date:
            raise ValidationError({"death_date": "Death date must not precede birth date."})


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
    """type-10022026-Maurice: Synthetic explicitly read-only device display record."""
    status = models.CharField(max_length=30, default="active")


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
