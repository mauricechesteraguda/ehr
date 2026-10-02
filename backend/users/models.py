"""type-10022026-Maurice: PostgreSQL-persisted role and TOTP enrollment state."""
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """type-10022026-Maurice: Application identity with explicit role and MFA state."""
    class Role(models.TextChoices):
        CLINICIAN = "clinician", "Clinician"
        PATIENT = "patient", "Patient"
        ADMIN = "admin", "Administrator"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PATIENT)
    totp_secret = models.CharField(max_length=64, blank=True, default="")
    totp_enrolled = models.BooleanField(default=False)


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
