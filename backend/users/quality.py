"""Ticket14: safe declarative demo clinical quality measures and FHIR-shaped reports."""
import hashlib
import json
from datetime import date, timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .fhir import FHIRJSONRenderer

from .audit import append_audit_event
from .jobs import enqueue_job
from .models import (AllergyIntolerance, MedicationOrderVersion, Observation, Patient,
                     MeasureDefinition, MeasureVersion, MeasureRun, MeasureReport)

ALLOWED_RESOURCES = {"Patient", "AllergyIntolerance", "MedicationOrderVersion", "Observation"}
ALLOWED_OPS = {"exists", "not_exists", "equals", "not_equals", "in", "before", "on_or_before", "after", "on_or_after"}
ALLOWED_FIELDS = {"code", "status", "recorded_date", "value", "medication_code", "start_date", "allergy_exists", "active_medication_exists", "recent_bp_exists"}


class SchemaError(ValueError):
    pass


def validate_schema(schema):
    """Validate a small data-only DSL; never interpret arbitrary expressions."""
    if not isinstance(schema, dict) or set(schema) - {"schema_version", "resource", "denominator", "numerator", "exclusions", "stratifiers", "window_days"}:
        raise SchemaError("unsupported schema keys")
    if schema.get("schema_version") != "1":
        raise SchemaError("unsupported schema version")
    if schema.get("resource") not in ALLOWED_RESOURCES:
        raise SchemaError("unsupported resource")
    def predicates(items):
        if not isinstance(items, list) or len(items) > 20:
            raise SchemaError("predicates must be a bounded list")
        for item in items:
            if not isinstance(item, dict) or set(item) - {"field", "op", "value"}:
                raise SchemaError("invalid predicate")
            if item.get("field") not in ALLOWED_FIELDS or item.get("op") not in ALLOWED_OPS:
                raise SchemaError("predicate is not allowlisted")
            if item["op"] in {"equals", "not_equals", "in", "before", "on_or_before", "after", "on_or_after"} and "value" not in item:
                raise SchemaError("predicate value required")
    predicates(schema.get("denominator", [])); predicates(schema.get("numerator", [])); predicates(schema.get("exclusions", []))
    if not isinstance(schema.get("stratifiers", []), list) or any(x not in ALLOWED_FIELDS for x in schema.get("stratifiers", [])):
        raise SchemaError("invalid stratifier")
    if "window_days" in schema and (not isinstance(schema["window_days"], int) or not 0 <= schema["window_days"] <= 3660):
        raise SchemaError("invalid window")
    return schema


def _snapshot(period_start, period_end):
    """Stable metadata only: IDs are hashed and clinical values never enter jobs/logs."""
    rows = []
    for model in (Patient, AllergyIntolerance, MedicationOrderVersion, Observation):
        qs = model.objects.all().order_by("pk").values("pk", "patient_id")
        rows.extend(f"{model.__name__}:{r['pk']}:{r['patient_id']}" for r in qs)
    raw = json.dumps({"start": str(period_start), "end": str(period_end), "rows": rows}, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()


def _rows(resource):
    return {"Patient": Patient.objects.all(), "AllergyIntolerance": AllergyIntolerance.objects.all(),
            "MedicationOrderVersion": MedicationOrderVersion.objects.all(), "Observation": Observation.objects.all()}[resource]


def _match(obj, predicate, period_end=None):
    field, op, expected = predicate["field"], predicate["op"], predicate.get("value")
    if field == "allergy_exists": actual = AllergyIntolerance.objects.filter(patient_id=obj.pk).exclude(status="entered-in-error").exists()
    elif field == "active_medication_exists": actual = MedicationOrderVersion.objects.filter(order__patient_id=obj.pk, status="active", **({"start_date__lte": period_end} if period_end else {})).exists()
    elif field == "recent_bp_exists": actual = Observation.objects.filter(patient_id=obj.pk, code="BP").exists()
    else: actual = getattr(obj, field, None)
    if isinstance(actual, date): actual = actual.isoformat()
    if op == "exists": return actual is not None and actual != ""
    if op == "not_exists": return actual is None or actual == ""
    if op == "equals": return str(actual) == str(expected)
    if op == "not_equals": return str(actual) != str(expected)
    if op == "in": return str(actual) in {str(x) for x in expected}
    return {"before": actual < str(expected), "on_or_before": actual <= str(expected), "after": actual > str(expected), "on_or_after": actual >= str(expected)}[op]


def _population(schema, period_start, period_end):
    rows = list(_rows(schema["resource"]))
    date_field = "recorded_date" if schema["resource"] in {"AllergyIntolerance", "Observation"} else "start_date" if schema["resource"] == "MedicationOrderVersion" else None
    if date_field:
        lower = period_end - timedelta(days=schema.get("window_days", (period_end - period_start).days))
        rows = [r for r in rows if getattr(r, date_field, None) is not None and lower <= getattr(r, date_field) <= period_end]
    def selected(item, predicates):
        for p in predicates:
            if p["field"] == "recent_bp_exists":
                lower = period_end - timedelta(days=schema.get("window_days", 90))
                actual = Observation.objects.filter(patient_id=item.pk, code="BP", recorded_date__gte=lower, recorded_date__lte=period_end).exists()
                if actual != bool(p.get("value")): return False
            elif not _match(item, p, period_end): return False
        return True
    rows = [r for r in rows if selected(r, schema.get("denominator", []))]
    exclusions = schema.get("exclusions", [])
    excluded = [r for r in rows if exclusions and selected(r, exclusions)]
    rows = [r for r in rows if r not in excluded]
    numerator = [r for r in rows if selected(r, schema.get("numerator", []))]
    return len(rows), len(numerator), len(excluded)


def evaluate_version(version, period_start, period_end, snapshot_checksum):
    validate_schema(version.schema)
    denominator, numerator, exclusions = _population(version.schema, period_start, period_end)
    return {"initialPopulation": denominator, "denominator": denominator, "numerator": numerator,
            "exclusions": exclusions, "measureScore": (numerator / denominator if denominator else None),
            "period": {"start": str(period_start), "end": str(period_end)}, "snapshotChecksum": snapshot_checksum}


def run_measure(run_id):
    with transaction.atomic():
        run = MeasureRun.objects.select_for_update().select_related("version").get(pk=run_id)
        existing = MeasureReport.objects.filter(run=run).first()
        if existing:
            return existing
        result = evaluate_version(run.version, run.period_start, run.period_end, run.snapshot_checksum)
        return MeasureReport.objects.create(run=run, measure=run.version.measure, version=run.version,
                                            status="complete", period_start=run.period_start, period_end=run.period_end,
                                            snapshot_checksum=run.snapshot_checksum, populations=result)


def _admin(request):
    return request.user.is_authenticated and request.user.role == "admin"


def _scope(request, write=False):
    required = "quality/Measure.w" if write else "quality/Measure.r"
    return not hasattr(request, "smart_scopes") or required in request.smart_scopes


def _measure_json(measure, version=None):
    version = version or measure.versions.filter(status="published").order_by("-version").first()
    return {"resourceType": "Measure", "id": str(measure.id), "url": measure.url, "version": version.version if version else None,
            "status": version.status if version else "draft", "effectivePeriod": {"start": str(version.effective_start), "end": str(version.effective_end) if version.effective_end else None} if version else None,
            "title": measure.title, "description": measure.description, "schemaVersion": version.schema.get("schema_version") if version else None}


class MeasureAdminView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, measure_id=None):
        if not _admin(request) or not _scope(request): return Response({"detail": "Administrator quality access required."}, status=403)
        qs = MeasureDefinition.objects.all().prefetch_related("versions")
        if measure_id: 
            m = qs.filter(pk=measure_id).first()
            return Response(_measure_json(m)) if m else Response({"detail": "Measure not found."}, status=404)
        return Response({"entry": [_measure_json(m) for m in qs]})
    def post(self, request, measure_id=None):
        if not _admin(request) or not _scope(request, True): return Response({"detail": "Administrator quality write access required."}, status=403)
        try:
            schema = validate_schema(request.data.get("schema", {}))
            with transaction.atomic():
                m = MeasureDefinition.objects.create(url=request.data["url"], title=request.data["title"], description=request.data.get("description", ""), provenance=request.data.get("provenance", {}))
                v = MeasureVersion.objects.create(measure=m, version=1, schema=schema, effective_start=request.data.get("effectiveStart", date.today()), status="draft", provenance=m.provenance)
                append_audit_event(actor=request.user, action="create", resource_type="MeasureDefinition", resource_id=m.pk)
            return Response(_measure_json(m, v), status=201)
        except (KeyError, SchemaError, ValueError) as e: return Response({"detail": str(e)}, status=400)
    def patch(self, request, measure_id):
        if not _admin(request) or not _scope(request, True): return Response({"detail": "Administrator quality write access required."}, status=403)
        v = MeasureVersion.objects.filter(pk=measure_id).select_related("measure").first()
        if not v: return Response({"detail": "Version not found."}, status=404)
        action = request.data.get("status")
        if action not in {"published", "retired"}: return Response({"detail": "Only publish or retire is allowed."}, status=400)
        v.status = action; v.published_at = timezone.now() if action == "published" else v.published_at; v.save(update_fields=["status", "published_at"])
        return Response(_measure_json(v.measure, v))
    def put(self, request, measure_id):
        if not _admin(request) or not _scope(request, True): return Response({"detail": "Administrator quality write access required."}, status=403)
        parent = MeasureDefinition.objects.filter(pk=measure_id).first()
        if not parent: return Response({"detail": "Measure not found."}, status=404)
        try: schema = validate_schema(request.data["schema"])
        except (KeyError, SchemaError) as e: return Response({"detail": str(e)}, status=400)
        latest = parent.versions.order_by("-version").first()
        v = MeasureVersion.objects.create(measure=parent, version=latest.version + 1, schema=schema, effective_start=request.data.get("effectiveStart", date.today()), provenance=request.data.get("provenance", parent.provenance))
        return Response(_measure_json(parent, v), status=201)


class MeasureRunView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, request, measure_id):
        if not _admin(request) or not _scope(request, True): return Response({"detail": "Administrator quality write access required."}, status=403)
        v = MeasureVersion.objects.filter(measure_id=measure_id, status="published").order_by("-version").first()
        if not v: return Response({"detail": "Published measure version required."}, status=409)
        start, end = date.fromisoformat(request.data["start"]), date.fromisoformat(request.data["end"])
        checksum = _snapshot(start, end); key = request.headers.get("Idempotency-Key") or f"measure:{v.pk}:{start}:{end}:{checksum}"
        with transaction.atomic():
            job, _ = enqueue_job(owner=request.user, kind="quality.measure", idempotency_key=key, input_data={"version": v.version, "start_date": start, "end_date": end})
            run, _ = MeasureRun.objects.get_or_create(job=job, defaults={"version": v, "period_start": start, "period_end": end, "snapshot_checksum": checksum, "status": "queued"})
        return Response({"runId": str(run.id), "jobId": str(job.id), "status": run.status}, status=202)


class MeasureReportView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request, report_id=None):
        if not _admin(request) or not _scope(request): return Response({"detail": "Administrator quality access required."}, status=403)
        qs = MeasureReport.objects.select_related("measure", "version")
        if report_id: qs = qs.filter(pk=report_id)
        reports = list(qs.order_by("-created_at"))
        def shape(r): return {"resourceType": "MeasureReport", "id": str(r.id), "status": r.status, "measure": r.measure.url, "measureVersion": r.version.version, "period": {"start": str(r.period_start), "end": str(r.period_end)}, "group": [{"population": [{"code": {"code": k}, "count": v} for k, v in r.populations.items() if k in {"initialPopulation", "denominator", "numerator", "exclusions"}]}], "snapshotChecksum": r.snapshot_checksum}
        return Response(shape(reports[0]) if report_id and reports else ({"entry": [shape(r) for r in reports]} if not report_id else {"detail": "Report not found."}), status=200 if reports or not report_id else 404)


class FHIRQualityView(APIView):
    """FHIR Measure/MeasureReport read, search, and asynchronous $evaluate boundary."""
    permission_classes = [IsAuthenticated]
    renderer_classes = [FHIRJSONRenderer]
    def _allowed(self, request, write=False):
        return (request.user.role in {"admin", "clinician"} and
                (not hasattr(request, "smart_scopes") or ("quality/Measure.w" if write else "quality/Measure.r") in request.smart_scopes))
    def get(self, request, resource_name, resource_id=None):
        if not self._allowed(request): return Response({"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "security"}]}, status=403)
        if resource_name == "Measure":
            qs = MeasureDefinition.objects.all()
            if resource_id: 
                obj = qs.filter(pk=resource_id).first()
                return Response(_measure_json(obj), status=200) if obj else Response({"resourceType": "OperationOutcome"}, status=404)
            return Response({"resourceType": "Bundle", "type": "searchset", "total": qs.count(), "entry": [{"resource": _measure_json(m)} for m in qs]})
        qs = MeasureReport.objects.select_related("measure", "version").order_by("-created_at")
        if resource_id: qs = qs.filter(pk=resource_id)
        reports = list(qs[:50])
        def report(r): return {"resourceType": "MeasureReport", "id": str(r.pk), "status": r.status, "measure": r.measure.url, "period": {"start": str(r.period_start), "end": str(r.period_end)}, "group": [{"population": [{"code": {"code": k}, "count": v} for k, v in r.populations.items()]}]}
        if resource_id and not reports: return Response({"resourceType": "OperationOutcome"}, status=404)
        return Response(report(reports[0]) if resource_id else {"resourceType": "Bundle", "type": "searchset", "total": len(reports), "entry": [{"resource": report(r)} for r in reports]})
    def post(self, request, resource_name=None):
        if resource_name != "Measure" or not self._allowed(request, True): return Response({"resourceType": "OperationOutcome"}, status=403)
        try:
            measure_id = request.data.get("measure") or request.data.get("measureId")
            start, end = date.fromisoformat(request.data["periodStart"]), date.fromisoformat(request.data["periodEnd"])
            v = MeasureVersion.objects.filter(measure_id=measure_id, status="published").order_by("-version").first()
            if not v: return Response({"resourceType": "OperationOutcome"}, status=404)
            checksum = _snapshot(start, end); job, _ = enqueue_job(owner=request.user, kind="quality.measure", idempotency_key=request.headers.get("Idempotency-Key", f"fhir:{v.pk}:{start}:{end}"), input_data={"version": v.version, "start_date": start, "end_date": end})
            run, _ = MeasureRun.objects.get_or_create(job=job, defaults={"version": v, "period_start": start, "period_end": end, "snapshot_checksum": checksum})
            return Response({"resourceType": "Task", "id": str(job.id), "status": "accepted", "output": [{"valueReference": {"reference": f"MeasureReport/{run.id}"}}]}, status=202)
        except (KeyError, ValueError): return Response({"resourceType": "OperationOutcome"}, status=400)
