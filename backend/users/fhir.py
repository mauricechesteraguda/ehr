"""type-10022026-Maurice: Authenticated, read-only FHIR R4 facade."""
import base64
import hashlib
import hmac
from urllib.parse import urlencode

from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.renderers import JSONRenderer
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import audit
from .logging import log_event
from .models import AllergyIntolerance, Condition, Device, MedicationOrderVersion, Observation, Patient, User, FamilyHistoryVersion, Questionnaire, QuestionnaireResponseVersion, ClinicianPatientAssignment, EmergencyAccessRequest
from .tracing import trace_function
from .views import _ensure_demo_records
from .smart import RESOURCE_SCOPES


RESOURCE_MODELS = {
    "AllergyIntolerance": AllergyIntolerance,
    "Condition": Condition,
    "Observation": Observation,
    "Device": Device,
    "FamilyMemberHistory": FamilyHistoryVersion,
    "Questionnaire": Questionnaire,
    "QuestionnaireResponse": QuestionnaireResponseVersion,
}
ALLOWED_PARAMS = {
    "Patient": {"name", "identifier", "page", "_count"},
    "MedicationRequest": {"patient", "status", "page", "_count"},
    "AllergyIntolerance": {"patient", "page", "_count"},
    "Condition": {"patient", "page", "_count"},
    "Observation": {"patient", "page", "_count"},
    "Device": {"patient", "page", "_count"},
    "FamilyMemberHistory": {"patient", "code", "page", "_count"},
    "Questionnaire": {"code", "status", "page", "_count"},
    "QuestionnaireResponse": {"patient", "status", "questionnaire", "page", "_count"},
}
ALL_RESOURCES = frozenset((*RESOURCE_MODELS, "Patient", "MedicationRequest"))
DEMO_SYSTEM = "http://example.org/fhir/CodeSystem/ehr-demo"


class FHIRJSONRenderer(JSONRenderer):
    """type-10022026-Maurice: Negotiate every FHIR body as FHIR JSON."""

    media_type = "application/fhir+json"
    format = "fhir+json"
    charset = None


@trace_function
def _response(payload, code=status.HTTP_200_OK):
    """type-10022026-Maurice: Return a payload for the FHIR renderer."""
    return Response(payload, status=code)


@trace_function
def _outcome(code, diagnostics, http_status):
    """type-10022026-Maurice: Return safe, payload-free FHIR failure evidence."""
    return _response({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": code, "diagnostics": diagnostics}]}, http_status)


@trace_function
def _token(kind, pk):
    """type-10022026-Maurice: Encode internal ids as non-enumerating opaque ids."""
    raw = f"{kind}:{pk}".encode()
    signature = hmac.new(settings.SECRET_KEY.encode(), raw, hashlib.sha256).hexdigest()[:16]
    return base64.urlsafe_b64encode(raw).decode().rstrip("=") + "-" + signature


@trace_function
def _internal_id(kind, token):
    """type-10022026-Maurice: Verify and decode an opaque id without a broad query."""
    try:
        encoded, signature = token.rsplit("-", 1)
        encoded += "=" * (-len(encoded) % 4)
        raw = base64.urlsafe_b64decode(encoded.encode())
        expected = hmac.new(settings.SECRET_KEY.encode(), raw, hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(signature, expected) or raw.split(b":", 1)[0].decode() != kind:
            return None
        value = raw.split(b":", 1)[1].decode()
        return int(value)
    except (ValueError, UnicodeDecodeError, TypeError):
        return None


@trace_function
def _patient_queryset(user, patient_context=None, *, allow_emergency=False):
    """type-10022026-Maurice: Apply compartment policy before evaluation."""
    queryset = Patient.objects.all()
    if user.role == User.Role.PATIENT:
        queryset = queryset.filter(owner=user)
    elif user.role == User.Role.CLINICIAN:
        policy = Q(restricted_access=False) | Q(clinician_assignments__clinician=user)
        if allow_emergency:
            policy |= Q(emergency_access_requests__clinician=user, emergency_access_requests__state=EmergencyAccessRequest.State.ACTIVE, emergency_access_requests__expires_at__gt=timezone.now())
        queryset = queryset.filter(policy).distinct()
    if patient_context:
        queryset = queryset.filter(public_id=patient_context)
    return queryset


@trace_function
def _patient_filter(queryset, public_id):
    """type-10022026-Maurice: Filter a resource to one exact patient identifier."""
    return queryset.filter(patient__public_id=public_id)


@trace_function
def _code(code, label, system=DEMO_SYSTEM):
    """type-10022026-Maurice: Map synthetic coded values to public demo terminology."""
    return {"coding": [{"system": system, "code": code, "display": label}], "text": label}


@trace_function
def _resource(resource_name, instance):
    """type-10022026-Maurice: Serialize approved model fields to FHIR R4 resources."""
    if resource_name == "Patient":
        return {"resourceType": "Patient", "id": instance.public_id, "meta": {"tag": [{"system": DEMO_SYSTEM, "code": "synthetic", "display": "Synthetic demo"}]}, "identifier": [{"system": DEMO_SYSTEM, "value": instance.public_id}], "name": [{"text": instance.display_name}], "gender": instance.sex, "birthDate": instance.birth_date.isoformat()}
    if resource_name == "Questionnaire":
        version = instance.active_version
        return {"resourceType": "Questionnaire", "id": _token(resource_name, instance.pk), "url": f"http://example.org/questionnaire/{instance.code}", "status": "active", "version": str(version.version), "title": instance.title, "item": [{"linkId": item.link_id, "text": item.text, "type": item.item_type, "required": item.required, "repeats": item.repeats, "answerOption": [{"valueString": option.get("value") if isinstance(option, dict) else option} for option in (item.options or [])]} for item in version.items.all()]}
    if resource_name == "QuestionnaireResponse":
        response = instance.response
        questionnaire = response.questionnaire
        types = {item.link_id: item.item_type for item in instance.questionnaire_version.items.all()}
        def answer(key, value):
            kind = {"boolean": "valueBoolean", "integer": "valueInteger", "decimal": "valueDecimal", "date": "valueDate", "string": "valueString", "choice": "valueCoding", "quantity": "valueQuantity"}[types.get(key, "string")]
            if kind == "valueCoding": value = {"code": value, "display": value}
            return {kind: value}
        return {"resourceType": "QuestionnaireResponse", "id": _token(resource_name, instance.pk), "status": "completed" if instance.status == "submitted" else "in-progress", "questionnaire": f"Questionnaire/{_token('Questionnaire', questionnaire.pk)}|{instance.questionnaire_version.version}", "subject": {"reference": f"Patient/{response.patient.public_id}"}, "item": [{"linkId": key, "answer": [answer(key, value)] if not isinstance(value, list) else [answer(key, child) for child in value]} for key, value in instance.answers.items()]}
    patient = instance.order.patient if resource_name == "MedicationRequest" else (instance.history.patient if resource_name == "FamilyMemberHistory" else instance.patient)
    patient_ref = {"reference": f"Patient/{patient.public_id}"}
    if resource_name == "MedicationRequest":
        return {"resourceType": "MedicationRequest", "id": _token("MedicationRequest", instance.pk), "status": instance.status, "intent": "order", "subject": patient_ref, "medicationCodeableConcept": _code(instance.medication_code, instance.medication_name)}
    if resource_name == "FamilyMemberHistory":
        return {"resourceType": resource_name, "id": _token(resource_name, instance.pk), "status": instance.status, "patient": patient_ref, "relationship": _code(instance.relationship, instance.relationship.title()), "sex": _code(instance.relative_sex, instance.relative_sex.title()), "condition": [{"code": {"coding": [{"system": instance.condition_system, "code": instance.condition_code, "display": instance.condition_display}], "text": instance.submitted_display or instance.condition_display}, "onsetDate": instance.onset_date.isoformat() if instance.onset_date else None, "recordedDate": instance.recorded_date.isoformat() if instance.recorded_date else None}], "extension": [{"url": "http://example.org/fhir/StructureDefinition/terminology-version", "valueString": instance.terminology_version}]}
    if resource_name == "AllergyIntolerance":
        return {"resourceType": resource_name, "id": _token(resource_name, instance.pk), "clinicalStatus": _code("active", "Active"), "code": _code(instance.code, instance.label), "patient": patient_ref, "reaction": [{"manifestation": [{"text": instance.reaction}]}] if instance.reaction else []}
    if resource_name == "Condition":
        return {"resourceType": resource_name, "id": _token(resource_name, instance.pk), "clinicalStatus": _code(instance.status, instance.status.title()), "code": _code(instance.code, instance.label), "subject": patient_ref}
    if resource_name == "Observation":
        return {"resourceType": resource_name, "id": _token(resource_name, instance.pk), "status": "final", "code": _code(instance.code, instance.label, "http://loinc.org"), "subject": patient_ref, "valueQuantity": {"value": instance.value, "unit": instance.unit} if instance.unit else {"value": instance.value}}
    version = getattr(instance, "active_version", None)
    return {"resourceType": "Device", "id": _token(resource_name, instance.pk), "status": version.status if version else instance.status, "identifier": ([{"system": "urn:gs1", "value": version.device_identifier}] if version and version.device_identifier else []), "type": _code(version.code if version else instance.code, version.label if version else instance.label), "lotNumber": version.lot_number if version and version.lot_number else None, "serialNumber": version.serial_number if version and version.serial_number else None, "expirationDate": version.expiry_date.isoformat() if version and version.expiry_date else None, "manufactureDate": version.manufacture_date.isoformat() if version and version.manufacture_date else None, "patient": patient_ref}


@trace_function
def _bundle(request, resource_name, resources, total, page, count):
    """type-10022026-Maurice: Build bounded deterministic searchset links."""
    base = request.build_absolute_uri(request.path)
    links = [{"relation": "self", "url": f"{base}?{urlencode(sorted(request.query_params.items()))}"}]
    if page > 1:
        links.append({"relation": "prev", "url": f"{base}?{urlencode(sorted({**request.query_params.dict(), 'page': page - 1}.items()))}"})
    if page * count < total:
        links.append({"relation": "next", "url": f"{base}?{urlencode(sorted({**request.query_params.dict(), 'page': page + 1}.items()))}"})
    return {"resourceType": "Bundle", "id": hashlib.sha256(f"{resource_name}:{request.get_full_path()}".encode()).hexdigest()[:24], "type": "searchset", "total": total, "link": links, "entry": [{"fullUrl": f"{base}/{item['id']}", "resource": item} for item in resources]}


@trace_function
def _audit(actor, resource_name, resource_id, patient=None, request=None):
    """type-10022026-Maurice: Make FHIR reads fail closed on audit failure."""
    audit.append_audit_event(actor=actor, action="read", resource_type=f"FHIR/{resource_name}", resource_id=resource_id, patient=patient, correlation_id=getattr(request, "correlation_id", ""))


class FHIRFacadeView(APIView):
    """type-10022026-Maurice: Read/search only FHIR R4 endpoint."""
    permission_classes = [IsAuthenticated]
    renderer_classes = [FHIRJSONRenderer]

    @trace_function
    def handle_exception(self, exc):
        """type-10022026-Maurice: Normalize authentication failures as OperationOutcome."""
        response = super().handle_exception(exc)
        if response is not None and response.status_code in (400, 401, 403, 405):
            issue_code = "security" if response.status_code in (401, 403) else "invalid"
            return _outcome(issue_code, "FHIR request is not permitted.", response.status_code)
        return response

    @trace_function
    def finalize_response(self, request, response, *args, **kwargs):
        """type-10022026-Maurice: Finalize success and failure bodies through FHIR negotiation."""
        return super().finalize_response(request, response, *args, **kwargs)

    @trace_function
    def get(self, request, resource_name, resource_id=None):
        """type-10022026-Maurice: Enforce params, scope, audit, and serialization in order."""
        started = __import__("time").monotonic()
        if resource_name not in ALL_RESOURCES:
            log_event("fhir.boundary", component="fhir", operation="read_search", outcome="failure", status=404, http_status=404, duration_ms=int((__import__("time").monotonic()-started)*1000), db_outcome="not_run")
            return _outcome("not-found", "FHIR resource is not available.", status.HTTP_404_NOT_FOUND)
        # type-10022026-Maurice: Check SMART scope and compartment before ORM evaluation.
        smart_scopes = getattr(request, "smart_scopes", None)
        required_scope = RESOURCE_SCOPES.get(resource_name)
        if smart_scopes is not None and (required_scope not in smart_scopes or not {"openid", "fhirUser"}.issubset(smart_scopes)):
            return _outcome("security", "FHIR scope is not permitted.", status.HTTP_403_FORBIDDEN)
        unknown = set(request.query_params) - ALLOWED_PARAMS[resource_name]
        if unknown:
            return _outcome("invalid", "Unsupported search parameter.", status.HTTP_400_BAD_REQUEST)
        try:
            _ensure_demo_records(request.user)
            if resource_id is not None:
                if resource_name == "Patient":
                    queryset = _patient_queryset(request.user, getattr(request, "smart_patient", None), allow_emergency=True).filter(public_id=resource_id)
                elif resource_name == "MedicationRequest":
                    pk = _internal_id(resource_name, resource_id)
                    queryset = MedicationOrderVersion.objects.none() if pk is None else MedicationOrderVersion.objects.filter(pk=pk, order__patient__in=_patient_queryset(request.user, getattr(request, "smart_patient", None), allow_emergency=True)).select_related("order__patient")
                elif resource_name == "FamilyMemberHistory":
                    pk = _internal_id(resource_name, resource_id)
                    queryset = FamilyHistoryVersion.objects.none() if pk is None else FamilyHistoryVersion.objects.filter(pk=pk, status="active")
                    queryset = queryset.filter(history__patient__in=_patient_queryset(request.user, getattr(request, "smart_patient", None), allow_emergency=True))
                elif resource_name == "QuestionnaireResponse":
                    pk = _internal_id(resource_name, resource_id)
                    queryset = QuestionnaireResponseVersion.objects.none() if pk is None else QuestionnaireResponseVersion.objects.filter(pk=pk, response__patient__in=_patient_queryset(request.user, getattr(request, "smart_patient", None), allow_emergency=True))
                elif resource_name == "Questionnaire":
                    pk = _internal_id(resource_name, resource_id)
                    queryset = Questionnaire.objects.none() if pk is None else Questionnaire.objects.filter(pk=pk, active_version__status="active")
                else:
                    pk = _internal_id(resource_name, resource_id)
                    queryset = RESOURCE_MODELS[resource_name].objects.none() if pk is None else RESOURCE_MODELS[resource_name].objects.filter(pk=pk)
                    if "patient" in ALLOWED_PARAMS[resource_name]:
                        queryset = queryset.filter(patient__in=_patient_queryset(request.user, getattr(request, "smart_patient", None), allow_emergency=True))
                instance = queryset.first()
                if instance is None:
                    return _outcome("not-found", "FHIR resource was not found.", status.HTTP_404_NOT_FOUND)
                patient = instance if resource_name == "Patient" else (instance.response.patient if resource_name == "QuestionnaireResponse" else (instance.order.patient if resource_name == "MedicationRequest" else (instance.history.patient if resource_name == "FamilyMemberHistory" else (None if resource_name == "Questionnaire" else instance.patient))))
                _audit(request.user, resource_name, resource_id, patient, request)
                return _response(_resource(resource_name, instance))

            try:
                page = int(request.query_params.get("page", "1")); count = int(request.query_params.get("_count", "20"))
            except ValueError:
                return _outcome("value", "Pagination values are invalid.", status.HTTP_400_BAD_REQUEST)
            if page < 1 or count < 1 or count > 50:
                return _outcome("value", "Pagination is outside the supported bounds.", status.HTTP_400_BAD_REQUEST)
            if resource_name == "Patient":
                queryset = _patient_queryset(request.user, getattr(request, "smart_patient", None))
                if request.query_params.get("name"):
                    queryset = queryset.filter(display_name__icontains=request.query_params["name"])
                if request.query_params.get("identifier"):
                    queryset = queryset.filter(public_id=request.query_params["identifier"])
            elif resource_name == "MedicationRequest":
                queryset = MedicationOrderVersion.objects.filter(order__patient__in=_patient_queryset(request.user, getattr(request, "smart_patient", None))).select_related("order__patient")
                if request.query_params.get("patient"):
                    patient_id = request.query_params["patient"].removeprefix("Patient/")
                    queryset = queryset.filter(order__patient__public_id=patient_id)
                if request.query_params.get("status"):
                    if request.query_params["status"] not in {"draft", "active", "cancelled"}:
                        return _outcome("value", "MedicationRequest status is invalid.", status.HTTP_400_BAD_REQUEST)
                    queryset = queryset.filter(status=request.query_params["status"])
            elif resource_name == "FamilyMemberHistory":
                queryset = FamilyHistoryVersion.objects.filter(status="active", history__patient__in=_patient_queryset(request.user, getattr(request, "smart_patient", None))).select_related("history__patient")
                if request.query_params.get("patient"):
                    queryset = queryset.filter(history__patient__public_id=request.query_params["patient"].removeprefix("Patient/"))
                if request.query_params.get("code"):
                    queryset = queryset.filter(condition_code=request.query_params["code"])
            elif resource_name == "Questionnaire":
                queryset = Questionnaire.objects.filter(active_version__status="active").select_related("active_version").prefetch_related("active_version__items")
                if request.query_params.get("code"):
                    queryset = queryset.filter(code=request.query_params["code"])
            elif resource_name == "QuestionnaireResponse":
                queryset = QuestionnaireResponseVersion.objects.filter(response__patient__in=_patient_queryset(request.user, getattr(request, "smart_patient", None))).select_related("response__patient", "response__questionnaire", "questionnaire_version")
                if request.query_params.get("patient"):
                    queryset = queryset.filter(response__patient__public_id=request.query_params["patient"].removeprefix("Patient/"))
                if request.query_params.get("status"):
                    queryset = queryset.filter(status="submitted" if request.query_params["status"] == "completed" else "draft")
            else:
                queryset = RESOURCE_MODELS[resource_name].objects.filter(patient__in=_patient_queryset(request.user, getattr(request, "smart_patient", None))).select_related("patient")
                if request.query_params.get("patient"):
                    queryset = _patient_filter(queryset, request.query_params["patient"].removeprefix("Patient/"))
            total = queryset.count()
            instances = list(queryset.order_by("pk")[(page - 1) * count:page * count])
            resources = [_resource(resource_name, item if resource_name != "MedicationRequest" else item) for item in instances]
            _audit(request.user, resource_name, "search", None, request)
            log_event("fhir.search", component="fhir", operation="search", outcome="success", status=200, http_status=200, duration_ms=int((__import__("time").monotonic()-started)*1000), db_outcome="success", error_class="none")
            return _response(_bundle(request, resource_name, resources, total, page, count))
        except Exception as error:
            log_event("fhir.failure", component="fhir", operation="read_search", outcome="failure", status=503, http_status=503, duration_ms=int((__import__("time").monotonic()-started)*1000), db_outcome="failure", exception=error)
            return _outcome("transient", "FHIR request could not be completed.", status.HTTP_503_SERVICE_UNAVAILABLE)
