"""type-10022026-Maurice: Safe authentication payload validation."""
from rest_framework import serializers


class LoginSerializer(serializers.Serializer):
    """type-10022026-Maurice: Validate password login without logging values."""
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    otp = serializers.CharField(required=False, allow_blank=True, write_only=True)


class OtpSerializer(serializers.Serializer):
    """type-10022026-Maurice: Validate one-time codes."""
    otp = serializers.RegexField(regex=r"^\d{6}$")


class PatientSerializer(serializers.ModelSerializer):
    """type-10022026-Maurice: Serialize approved synthetic patient fields only."""
    synthetic_demo = serializers.SerializerMethodField()

    class Meta:
        from .models import Patient
        model = Patient
        fields = ["public_id", "display_name", "race", "ethnicity", "preferred_language", "sex", "sexual_orientation", "gender_identity", "birth_date", "death_date", "synthetic_demo"]
        read_only_fields = ["public_id", "display_name", "synthetic_demo"]

    def get_synthetic_demo(self, obj):
        """type-10022026-Maurice: Mark every returned record as non-production demo data."""
        return True


class MedicationVersionSerializer(serializers.ModelSerializer):
    """type-10022026-Maurice: Validate every required medication field before persistence."""
    class Meta:
        from .models import MedicationOrderVersion
        model = MedicationOrderVersion
        fields = ["id", "version", "medication_code", "medication_name", "dose", "dose_unit", "route", "frequency", "start_date", "quantity", "refills", "indication", "status", "supersedes", "created_at"]
        read_only_fields = ["id", "version", "status", "supersedes", "created_at"]

    def validate(self, attrs):
        """type-10022026-Maurice: Enforce positive quantities and controlled non-empty values."""
        for field in ("medication_code", "medication_name", "dose_unit", "route", "frequency", "indication"):
            if not str(attrs.get(field, "")).strip():
                raise serializers.ValidationError({field: "This field is required."})
        for field in ("dose", "quantity"):
            if attrs.get(field) is None or attrs[field] <= 0:
                raise serializers.ValidationError({field: "Must be positive."})
        if attrs.get("refills", 0) < 0:
            raise serializers.ValidationError({"refills": "Must be zero or greater."})
        if not attrs.get("start_date"):
            raise serializers.ValidationError({"start_date": "This field is required."})
        controlled = {
            "dose_unit": {"mg", "mcg", "g", "mL", "tablet", "capsule", "unit"},
            "route": {"oral", "IV", "IM", "SC", "topical", "inhaled"},
            "frequency": {"QD", "BID", "TID", "QID", "PRN", "once daily", "twice daily"},
        }
        for field, values in controlled.items():
            if attrs[field] not in values:
                raise serializers.ValidationError({field: "Select a supported controlled value."})
        return attrs
