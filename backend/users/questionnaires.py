"""Ticket05: deterministic questionnaire validation and transactional response workflow."""
from .logging import traced_operation
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from . import audit
from .models import QuestionnaireResponse, QuestionnaireResponseVersion, QuestionnaireOutboxEvent, QuestionnaireReview, User


@traced_operation
def validate_answers(questionnaire_version, answers, *, require_required=True):
    if not isinstance(answers, dict):
        raise ValueError("Answers must be an object.")
    items = list(questionnaire_version.items.all().order_by("ordinal", "link_id"))
    by_link = {item.link_id: item for item in items}
    if set(answers) - set(by_link):
        raise ValueError("Unknown questionnaire item.")
    for item in items:
        present = item.link_id in answers and answers[item.link_id] not in (None, "", [])
        if require_required and item.required and not present:
            raise ValueError("Required questionnaire item is missing.")
        if not present:
            continue
        values = answers[item.link_id] if item.repeats else [answers[item.link_id]]
        if item.repeats and not isinstance(answers[item.link_id], list):
            raise ValueError("Repeated item must be a list.")
        for value in values:
            _validate_item(item, value)
    return {key: answers[key] for key in sorted(answers, key=lambda key: (by_link[key].ordinal, key))}


def _validate_item(item, value):
    kind = item.item_type
    if kind == "boolean" and not isinstance(value, bool):
        raise ValueError("Boolean answer is invalid.")
    if kind == "integer" and (isinstance(value, bool) or not isinstance(value, int)):
        raise ValueError("Integer answer is invalid.")
    if kind in {"integer", "decimal", "quantity"}:
        raw = value.get("value") if kind == "quantity" and isinstance(value, dict) else value
        try:
            number = Decimal(str(raw))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("Numeric answer is invalid.")
        if item.min_value is not None and number < item.min_value:
            raise ValueError("Answer is below the minimum.")
        if item.max_value is not None and number > item.max_value:
            raise ValueError("Answer is above the maximum.")
    elif kind == "date":
        try: date.fromisoformat(value)
        except (TypeError, ValueError): raise ValueError("Date answer is invalid.")
    elif kind == "string":
        if not isinstance(value, str): raise ValueError("String answer is invalid.")
        if item.min_length is not None and len(value) < item.min_length: raise ValueError("String answer is too short.")
        if item.max_length is not None and len(value) > item.max_length: raise ValueError("String answer is too long.")
    elif kind == "choice":
        options = [option.get("value") if isinstance(option, dict) else option for option in (item.options or [])]
        if value not in options: raise ValueError("Choice answer is invalid.")
    elif kind == "quantity":
        if not isinstance(value, dict) or set(value) - {"value", "unit"} or "value" not in value or not isinstance(value.get("unit", ""), str):
            raise ValueError("Quantity answer is invalid.")


@transaction.atomic
@traced_operation
def create_response(*, patient, questionnaire, actor, questionnaire_version_number, answers, status, correlation_id="", correction=None):
    if actor.role != User.Role.PATIENT or patient.owner_id != actor.id:
        raise PermissionError("Only the patient may submit a response.")
    version = questionnaire.versions.select_for_update().get(version=questionnaire_version_number)
    if version.status != "active" or questionnaire.active_version_id != version.id:
        raise ValueError("Questionnaire version is not active.")
    if status == "draft" and not version.allow_draft:
        raise ValueError("Draft responses are not permitted.")
    normalized = validate_answers(version, answers, require_required=status == "submitted")
    if correction:
        response = QuestionnaireResponse.objects.select_for_update().get(pk=correction, patient=patient, questionnaire=questionnaire)
        previous = response.active_version
        if previous and previous.questionnaire_version_id != version.id:
            raise ValueError("Correction must use the pinned questionnaire version.")
        next_number = previous.version + 1 if previous else 1
    else:
        response = QuestionnaireResponse.objects.create(patient=patient, questionnaire=questionnaire, created_by=actor)
        previous, next_number = None, 1
    response_version = QuestionnaireResponseVersion.objects.create(response=response, questionnaire_version=version, version=next_number, status=status, answers=normalized, created_by=actor, supersedes=previous, submitted_at=timezone.now() if status == "submitted" else None)
    response.active_version = response_version
    response.save(update_fields=["active_version"])
    audit.append_audit_event(actor=actor, action="create", resource_type="QuestionnaireResponse", resource_id=response.pk, patient=patient, correlation_id=correlation_id)
    QuestionnaireOutboxEvent.objects.create(response_version=response_version, kind="questionnaire-response.changed")
    return response, response_version


@transaction.atomic
@traced_operation
def review_response(*, response_version_id, reviewer, decision, reason="", correlation_id=""):
    if reviewer.role != User.Role.CLINICIAN:
        raise PermissionError("Clinician access required.")
    if decision not in {"accepted", "returned", "rejected"}:
        raise ValueError("Unsupported review decision.")
    if decision in {"returned", "rejected"} and not str(reason).strip():
        raise ValueError("A reason is required.")
    response_version = QuestionnaireResponseVersion.objects.select_for_update().select_related("response", "response__patient").get(pk=response_version_id)
    if response_version.status != "submitted":
        raise ValueError("Only submitted responses can be reviewed.")
    review = QuestionnaireReview.objects.create(response_version=response_version, reviewer=reviewer, decision=decision, reason=str(reason).strip())
    audit.append_audit_event(actor=reviewer, action="update", resource_type="QuestionnaireReview", resource_id=review.pk, patient=response_version.response.patient, correlation_id=correlation_id)
    QuestionnaireOutboxEvent.objects.create(response_version=response_version, kind="questionnaire-response.reviewed")
    return review
