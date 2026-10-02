"""Ticket15 FHIR Bulk Data endpoints; authorization is checked on every operation."""
from datetime import timedelta
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import User, Job, FHIRBulkExport
from .jobs import enqueue_job, cancel_job
from . import audit
from .bulk_exports import ALL_RESOURCES, TTL, parse_since, public_manifest, download_bulk_entry

def _authorized(request):
    if not request.user.is_authenticated or not request.user.is_active: return False
    token = getattr(request, "auth", None)
    if token is None: return request.user.role == User.Role.ADMIN
    app = getattr(token, "application", None)
    return bool(app and app.user and app.user.is_active and "system/*.read" in getattr(request, "smart_scopes", frozenset()))

class BulkExportView(APIView):
    permission_classes = [AllowAny]
    def _deny(self, request):
        try: audit.append_audit_event(actor=request.user if request.user.is_authenticated else None, action="deny", resource_type="FHIRBulkExport", resource_id="authorization")
        except Exception: return Response({"detail": "Bulk export authorization unavailable."}, status=503)
        return Response({"detail": "Bulk export authorization is required."}, status=403)
    def post(self, request): return self._start(request, request.data if isinstance(request.data, dict) else {})
    def get(self, request, export_id=None, resource_type=None):
        if export_id is not None: return self.get_status(request, export_id, resource_type)
        return self._start(request, request.query_params.dict())
    def _start(self, request, data):
        if not _authorized(request): return self._deny(request)
        raw_types = data.get("_type") or data.get("type")
        types = [x for x in str(raw_types).split(",") if x] if raw_types else sorted(ALL_RESOURCES)
        if not types or len(types) > 20 or any(x not in ALL_RESOURCES for x in types) or len(set(types)) != len(types): return Response({"detail": "Unsupported _type."}, status=400)
        if set(data) - {"_type", "type", "_since", "purpose", "approval", "idempotency_key"}: return Response({"detail": "Unsupported bulk export parameter."}, status=400)
        try: since = parse_since(data.get("_since")); purpose = str(data.get("purpose", "")); approval = str(data.get("approval", ""))
        except ValueError: return Response({"detail": "Invalid _since."}, status=400)
        if len(purpose) < 3 or len(purpose) > 500 or len(approval) < 3 or len(approval) > 500: return Response({"detail": "purpose and approval are required."}, status=400)
        idem = request.headers.get("Idempotency-Key") or data.get("idempotency_key")
        if not idem or len(str(idem)) > 160: return Response({"detail": "Idempotency-Key is required."}, status=400)
        payload = {"resource_types": sorted(types), "since": since.isoformat() if since else "", "purpose": purpose, "approval": approval}
        try: job, created = enqueue_job(owner=request.user, kind="fhir.bulk.export", idempotency_key=str(idem), input_data=payload, expires_at=timezone.now() + TTL)
        except ValueError: return Response({"detail": "Idempotency key is already used."}, status=409)
        if created:
            try:
                safe_query = "_type=" + ",".join(sorted(types)) + ("&_since=" + since.isoformat() if since else "")
                manifest = FHIRBulkExport.objects.create(job=job, resource_types=sorted(types), since=since, purpose=purpose, approval=approval, request_url=request.build_absolute_uri(request.path) + "?" + safe_query)
                audit.append_audit_event(actor=request.user, action="request", resource_type="FHIRBulkExport", resource_id=str(manifest.id))
            except Exception:
                job.delete(); return Response({"detail": "Export audit unavailable; nothing was queued."}, status=503)
        else: manifest = FHIRBulkExport.objects.get(job=job)
        response = Response({}, status=202 if created else 200); response["Content-Location"] = request.build_absolute_uri(f"/fhir/R4/$export/{manifest.id}"); return response

    def get_status(self, request, export_id, resource_type=None):
        if not _authorized(request): return self._deny(request)
        manifest = FHIRBulkExport.objects.select_related("job").filter(pk=export_id).first()
        if not manifest: return Response({"detail": "Export not found."}, status=404)
        if resource_type:
            try: body = download_bulk_entry(manifest, resource_type)
            except (FileNotFoundError, RuntimeError, ValueError): return Response({"detail": "Export unavailable."}, status=404)
            audit.append_audit_event(actor=request.user, action="read", resource_type="FHIRBulkExport", resource_id=str(manifest.id))
            return HttpResponse(body, content_type="application/fhir+ndjson")
        if manifest.job.state in (Job.State.QUEUED, Job.State.RUNNING):
            response = Response(public_manifest(request, manifest), status=202); response["Retry-After"] = "5"; return response
        return Response(public_manifest(request, manifest), status=200)

    def delete(self, request, export_id):
        if not _authorized(request): return self._deny(request)
        manifest = FHIRBulkExport.objects.select_related("job").filter(pk=export_id).first()
        if not manifest: return Response({"detail": "Export not found."}, status=404)
        cancel_job(manifest.job_id, actor=request.user); return Response(status=202)
