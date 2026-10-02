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


class QuestionnaireItemSerializer(serializers.ModelSerializer):
    class Meta:
        from .models import QuestionnaireItem
        model = QuestionnaireItem
        fields = ["id", "link_id", "text", "item_type", "ordinal", "required", "repeats", "min_length", "max_length", "min_value", "max_value", "options"]


class QuestionnaireSerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    version = serializers.SerializerMethodField()

    class Meta:
        from .models import Questionnaire
        model = Questionnaire
        fields = ["id", "code", "title", "version", "items"]

    def get_version(self, obj):
        return obj.active_version.version if obj.active_version else None

    def get_items(self, obj):
        return QuestionnaireItemSerializer(obj.active_version.items.all(), many=True).data if obj.active_version else []


class QuestionnaireResponseVersionSerializer(serializers.ModelSerializer):
    questionnaire_id = serializers.IntegerField(source="questionnaire_version.questionnaire_id", read_only=True)
    questionnaire_version_number = serializers.IntegerField(source="questionnaire_version.version", read_only=True)

    class Meta:
        from .models import QuestionnaireResponseVersion
        model = QuestionnaireResponseVersion
        fields = ["id", "version", "questionnaire_id", "questionnaire_version_number", "status", "answers", "supersedes", "submitted_at", "created_at"]
        read_only_fields = fields


class FamilyHistoryVersionSerializer(serializers.ModelSerializer):
    """type-10022026-Maurice: Validate bounded family-history fields before atomic persistence."""
    class Meta:
        from .models import FamilyHistoryVersion
        model = FamilyHistoryVersion
        fields = ["id", "version", "relationship", "relative_sex", "relative_status", "relative_deceased", "condition_system", "condition_code", "condition_display", "submitted_display", "terminology_version", "onset_date", "recorded_date", "status", "supersedes", "created_by", "created_at"]
        read_only_fields = ["id", "version", "supersedes", "created_by", "created_at", "terminology_version"]

    def validate(self, attrs):
        from .terminology import adapter
        if attrs.get("relationship", "") not in {"mother", "father", "sibling", "child", "grandparent", "other"}:
            raise serializers.ValidationError({"relationship": "Select a supported relationship."})
        for name, allowed in (("relative_sex", {"female", "male", "unknown"}), ("relative_status", {"alive", "deceased", "unknown"})):
            if attrs.get(name, "unknown") not in allowed:
                raise serializers.ValidationError({name: "Select a supported value."})
        try:
            concept = adapter.validate(system=attrs.get("condition_system", ""), code=attrs.get("condition_code", ""), display=attrs.get("condition_display", ""))
        except Exception as error:
            # type-10022026-Maurice: Unavailable/unresolved terminology fails closed without guessed labels.
            raise serializers.ValidationError({"condition_code": "Terminology validation is unavailable or unresolved."}) from error
        attrs["terminology_version"] = concept.version
        attrs["submitted_display"] = attrs.get("submitted_display") or attrs["condition_display"]
        return attrs


class DeviceVersionSerializer(serializers.ModelSerializer):
    """Ticket04: Validate bounded clinician device changes and hide preserved raw input."""
    class Meta:
        from .models import DeviceVersion
        model = DeviceVersion
        fields = ["id", "version", "code", "label", "status", "issuer", "device_identifier", "lot_number", "serial_number", "expiry_date", "manufacture_date", "parser_version", "parse_status", "parse_error_code", "gudid_status", "supersedes", "created_by", "created_at"]
        read_only_fields = ["id", "version", "issuer", "device_identifier", "lot_number", "serial_number", "expiry_date", "manufacture_date", "parser_version", "parse_status", "parse_error_code", "gudid_status", "supersedes", "created_by", "created_at"]

    def validate(self, attrs):
        if attrs.get("status", "active") not in {"active", "inactive", "entered-in-error"}:
            raise serializers.ValidationError({"status": "Unsupported device lifecycle state."})
        if not str(attrs.get("code", "")).strip() or len(str(attrs.get("code", ""))) > 80:
            raise serializers.ValidationError({"code": "A bounded device code is required."})
        if len(str(attrs.get("label", ""))) > 160:
            raise serializers.ValidationError({"label": "Label is too long."})
        return attrs
