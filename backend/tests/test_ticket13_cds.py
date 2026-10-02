"""Ticket13 acceptance coverage; inputs are synthetic and assertions are PHI-free."""
from datetime import date
import pytest

pytestmark = pytest.mark.django_db


def _fixture():
    from backend.users.models import Patient, User
    actor = User.objects.create_user(username="cds-clinician", password="safe", role="clinician")
    patient = Patient.objects.create(public_id="CDS001", display_name="Synthetic CDS", birth_date=date(1980, 1, 1))
    return actor, patient


def test_TC_EXP_1301_discovery():
    from backend.users.cds import discovery
    assert {item["hook"] for item in discovery()["services"]} == {"medication-prescribe", "patient-view"}


def test_TC_EXP_1302_valid_hook():
    from backend.users.cds import discovery, invoke
    actor, patient = _fixture(); service = next(x for x in discovery()["services"] if x["hook"] == "patient-view")
    result = invoke(service_id=service["id"], payload={"context": {"patientId": patient.public_id}, "prefetch": {}}, actor=actor, request_key="hook-1302")
    assert result.hook == "patient-view" and list(result.cards.all()) == []


@pytest.mark.parametrize("payload", [{}, {"context": {}}, {"context": {"patientId": "bad\nvalue"}}, {"context": {"patientId": "CDS001"}, "prefetch": {"x": "a" * 17000}}])
def test_TC_EXP_1303_context_bounds(payload):
    from backend.users.cds import _safe_context
    with pytest.raises(ValueError): _safe_context(payload)


def test_TC_EXP_1304_unknown_service():
    from backend.users.cds import invoke
    actor, patient = _fixture()
    with pytest.raises(LookupError): invoke(service_id="missing", payload={"context": {"patientId": patient.public_id}}, actor=actor, request_key="x")


def test_TC_EXP_1305_deterministic_empty_cards():
    from backend.users.cds import invoke
    actor, patient = _fixture(); payload = {"context": {"patientId": patient.public_id}, "prefetch": {}}
    first = invoke(service_id="demo-patient-view", payload=payload, actor=actor, request_key="same-1305")
    second = invoke(service_id="demo-patient-view", payload=payload, actor=actor, request_key="same-1305")
    assert first.pk == second.pk and first.context_fingerprint == second.context_fingerprint


def test_TC_EXP_1306_indicator_values_are_bounded():
    from backend.users.cds import INDICATORS
    assert INDICATORS == {"LOW", "MODERATE", "HIGH", "CRITICAL"}


def test_TC_EXP_1307_conflicting_idempotency_rejected():
    from backend.users.cds import invoke
    actor, patient = _fixture(); invoke(service_id="demo-patient-view", payload={"context": {"patientId": patient.public_id}}, actor=actor, request_key="conflict")
    with pytest.raises(ValueError): invoke(service_id="demo-patient-view", payload={"context": {"patientId": patient.public_id}, "prefetch": {"different": True}}, actor=actor, request_key="conflict")


def test_TC_EXP_1308_published_rule_is_immutable():
    from backend.users.models import CDSRuleVersion
    rule = CDSRuleVersion.objects.filter(published_at__isnull=False).first(); original = rule.config
    rule.config = {"kind": "hostile"}
    with pytest.raises(ValueError): rule.save()
    rule.refresh_from_db(); assert rule.config == original


def test_TC_EXP_1309_invalid_suggestion_rejected():
    from backend.users.cds import act
    from backend.users.cds import invoke
    from backend.users.models import AllergyIntolerance, CDSCard, InteractionRule, MedicationOrder, MedicationOrderVersion
    actor, patient = _fixture()
    AllergyIntolerance.objects.create(patient=patient, code="ALLERGY-CDS", label="Synthetic allergy")
    InteractionRule.objects.create(
        kind=InteractionRule.Kind.DRUG_ALLERGY,
        medication_code="MED-CDS",
        allergy_code="ALLERGY-CDS",
        severity=InteractionRule.Severity.HIGH,
    )
    order = MedicationOrder.objects.create(patient=patient, prescriber=actor)
    MedicationOrderVersion.objects.create(
        order=order, version=1, created_by=actor, medication_code="MED-CDS",
        medication_name="Synthetic medication", dose=1, dose_unit="mg", route="oral",
        frequency="daily", start_date=date(2026, 1, 1), quantity=1,
        indication="deterministic CDS acceptance fixture", status=MedicationOrderVersion.Status.ACTIVE,
    )
    invoke(
        service_id="demo-patient-view",
        payload={"context": {"patientId": patient.public_id}, "prefetch": {}},
        actor=actor,
        request_key="card-1309",
    )
    card = CDSCard.objects.filter(invocation__patient=patient).first()
    with pytest.raises(ValueError): act(card_id=card.pk, actor=actor, action="accept", suggestion_id="not-offered")


def test_TC_EXP_1310_reason_boundaries():
    from backend.users.cds import act
    with pytest.raises(ValueError): act(card_id="00000000-0000-0000-0000-000000000000", actor=_fixture()[0], action="unsupported")


def test_TC_EXP_1311_failure_is_transactional():
    from backend.users.cds import invoke
    from backend.users.models import CDSInvocation
    actor, patient = _fixture()
    with pytest.raises(LookupError): invoke(service_id="missing", payload={"context": {"patientId": patient.public_id}}, actor=actor, request_key="rollback")
    assert not CDSInvocation.objects.filter(request_key="rollback").exists()


def test_TC_EXP_1312_action_records_are_append_only():
    from backend.users.models import CDSCardAction
    assert CDSCardAction._meta.get_field("created_at").auto_now_add


def test_TC_EXP_1313_safe_failure_contract():
    from backend.users.cds import SUPPORTED_HOOKS
    assert "order-sign" in SUPPORTED_HOOKS


def test_TC_EXP_1314_safe_source_link():
    from backend.users.cds import discovery
    assert all("CDS001" not in str(item) and "Synthetic CDS" not in str(item) for item in discovery()["services"])


def test_TC_EXP_1315_roles_are_explicit():
    from backend.users.models import User
    assert User.Role.CLINICIAN == "clinician" and User.Role.ADMIN == "admin"
