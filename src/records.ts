// type-10022026-Maurice: Protected, non-persistent synthetic record API client.
import type { LogSink } from "./logger";

export type RecordTrace = (event: { event: "entry" | "exit" | "error"; function: string }) => void;
export type PatientRecord = {
  public_id: string;
  display_name: string;
  race: string;
  ethnicity: string;
  preferred_language: string;
  sex: string;
  sexual_orientation: string;
  gender_identity: string;
  birth_date: string;
  death_date: string | null;
  synthetic_demo: boolean;
  allergies: Array<Record<string, string | null>>;
  conditions: Array<Record<string, string | null>>;
  observations: Array<Record<string, string | null>>;
  devices: Array<Record<string, string | null>>;
  family_history: FamilyHistoryVersion[];
};
export type FamilyHistoryVersion = { id: number; version: number; relationship: string; relative_sex: string; relative_status: string; relative_deceased: boolean | null; condition_system: string; condition_code: string; condition_display: string; submitted_display: string; terminology_version: string; onset_date: string | null; recorded_date: string | null; status: "active" | "entered-in-error"; supersedes: number | null };

export type AuditEvent = { sequence: number; actor: string | null; occurred_at: string; patient: string | null; action: string; resource_type: string; resource_id: string; correlation_id: string; previous_hash: string; current_hash: string };
export type BreakGlassGrant = { id: number; state: "active" | "expired" | "revoked"; expires_at: string; patient: string };
export type AdminUser = { id: number; username: string; role: "clinician" | "patient" | "admin" | "developer"; is_active: boolean; is_staff: boolean; totp_enrolled: boolean };

export async function requestBreakGlass(patient: string, justification: string): Promise<BreakGlassGrant> {
  const response = await fetch(`/api/patients/${encodeURIComponent(patient)}/break-glass/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ justification }) });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail ?? "Emergency access request was denied.");
  return body;
}

export type CDSCard = { uuid: string; summary: string; detail: string; indicator: "LOW" | "MODERATE" | "HIGH" | "CRITICAL"; source: { label: string; url: string }; suggestions: Array<{ id: string; label: string }> };
export async function invokeCDS(service: string, patientId: string): Promise<CDSCard[]> {
  const response = await fetch(`/api/cds-services/${encodeURIComponent(service)}`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID() }, body: JSON.stringify({ hookInstance: crypto.randomUUID(), context: { patientId }, prefetch: {} }) });
  const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(body.detail ?? "CDS service unavailable."); return body.cards as CDSCard[];
}
export async function actOnCDSCard(uuid: string, action: "accept" | "dismiss" | "override", suggestionId = "", reason = ""): Promise<void> {
  const response = await fetch(`/api/cds-cards/${encodeURIComponent(uuid)}/actions/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action, suggestionId, reason }) });
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new Error(body.detail ?? "Unable to record card action."); }
}

export async function revokeBreakGlass(patient: string): Promise<void> {
  const response = await fetch(`/api/patients/${encodeURIComponent(patient)}/break-glass/`, { method: "DELETE", credentials: "include" });
  if (!response.ok) throw new Error("Unable to revoke emergency access.");
}

export async function fetchBreakGlassReview(): Promise<any[]> { const response = await fetch("/api/admin/break-glass/", { credentials: "include" }); if (!response.ok) throw new Error("Unable to load emergency review queue."); return response.json(); }
export async function reviewBreakGlass(id: number, outcome: string): Promise<any> { const response = await fetch(`/api/admin/break-glass/${id}/`, { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ outcome }) }); if (!response.ok) throw new Error("Unable to review emergency access."); return response.json(); }
export type InteractionRule = { id: number; kind: string; medication_code: string; related_medication_code: string; allergy_code: string; severity: "LOW" | "MODERATE" | "HIGH" | "CRITICAL"; description: string; active: boolean };
export type MedicationVersion = { id: number; version: number; medication_code: string; medication_name: string; dose: string; dose_unit: string; route: string; frequency: string; start_date: string; quantity: string; refills: number; indication: string; status: "draft" | "active" | "cancelled"; supersedes: number | null; created_at: string };
export type MedicationOrder = { id: number; prescriber: string; active_version: MedicationVersion | null };
export type InteractionFinding = { rule_id: number; kind: string; severity: "LOW" | "MODERATE" | "HIGH" | "CRITICAL"; description: string; suppressed: boolean };
export type InteractionEvaluation = { id: number; floor: "LOW" | "MODERATE" | "HIGH"; stale: boolean; findings: InteractionFinding[] };
export type PatientExport = { id: string; status: "ready"; format: "json" | "pdf"; sha256: string; expires_at: string; download_url: string };
export type JobStatus = { id: string; kind: string; state: string; attempts: number; max_attempts: number; queued_at: string; started_at: string | null; finished_at: string | null; heartbeat_at: string | null; error_code: string | null; dependency: string };
export type PopulationExport = { id?: string; job_id?: string; state: string; format: "csv" | "jsonl"; sha256?: string | null; size_bytes?: number | null; expires_at?: string; download_url?: string | null; attempts?: number; error_code?: string | null };
export type DeviceVersion = { id: number; device_id?: number; version: number; code: string; label: string; status: "active" | "inactive" | "entered-in-error"; issuer: string; device_identifier: string; lot_number: string; serial_number: string; expiry_date: string | null; manufacture_date: string | null; parser_version: string; parse_status: "parsed" | "parse_failed" | "unsupported"; parse_error_code: string; gudid_status: string; supersedes: number | null; created_at: string };
export type DeviceParsePreview = { status: string; issuer: string; device_identifier: string; lot_number: string; serial_number: string; expiry_date: string | null; manufacture_date: string | null; parser_version: string; error_code: string };
export type PatientAmendment = { id: number; resource_type: string; resource_id: string; source_version: number; source_reference: string; status: "submitted" | "under_review" | "accepted" | "denied" | "appended"; submitted_at: string; due_at: string; overdue: boolean; reason: string; decision_reason: string; accepted_version: number | null; addendum: Record<string, unknown> | null };
export type PatientSelectionResult = { patient_id: string; request_id: string };
export type DirectArtifact = { id: number; template_id: string; template_version: string; created_at: string; expires_at: string | null; size_bytes: number; sha256: string };
export type DirectDelivery = { id: string; artifact_id: number; purpose: string; state: string; attempts: number; max_attempts: number; error_code: string | null; receipt_code: string | null; receipt_checksum: string | null; created_at: string; finished_at: string | null };
export async function fetchDirectArtifacts(patient: string): Promise<DirectArtifact[]> { const r = await fetch(`/api/patients/${encodeURIComponent(patient)}/direct/artifacts/`, { credentials: "include" }); if (!r.ok) throw new Error("Unable to load C-CDA artifacts."); return r.json(); }
export async function fetchDirectDeliveries(): Promise<DirectDelivery[]> { const r = await fetch("/api/direct/deliveries/", { credentials: "include" }); if (!r.ok) throw new Error("Unable to load delivery status."); return r.json(); }
export async function createDirectDelivery(payload: { artifact_id: number; recipient: string; purpose: string }, key: string): Promise<DirectDelivery> { const r = await fetch("/api/direct/deliveries/", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "Idempotency-Key": key }, body: JSON.stringify(payload) }); const b = await r.json().catch(() => ({})); if (!r.ok) throw new Error(b.detail ?? "Unable to queue simulated delivery."); return b; }
export async function cancelDirectDelivery(id: string): Promise<DirectDelivery> { const r = await fetch(`/api/direct/deliveries/${id}/cancel/`, { method: "POST", credentials: "include" }); if (!r.ok) throw new Error("Unable to cancel delivery."); return r.json(); }
export async function retryDirectDelivery(id: string): Promise<DirectDelivery> { const r = await fetch(`/api/direct/deliveries/${id}/retry/`, { method: "POST", credentials: "include" }); if (!r.ok) throw new Error("Unable to retry delivery."); return r.json(); }

export async function selectPatient(payload: Record<string, string>, fetcher: typeof fetch = fetch): Promise<PatientSelectionResult> {
  const response = await fetcher("/api/smart/patient-selection/", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail ?? "Patient selection is unavailable.");
  return body as PatientSelectionResult;
}

export async function fetchAmendments(publicId: string, fetcher: typeof fetch = fetch): Promise<PatientAmendment[]> {
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/amendments/`, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to load amendment requests.");
  return response.json();
}
export async function createAmendment(publicId: string, payload: { resource_type: string; resource_id: string | number; source_version: number; reason: string; proposed_data?: Record<string, unknown> }, fetcher: typeof fetch = fetch): Promise<PatientAmendment> {
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/amendments/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Unable to submit amendment request.");
  return response.json();
}
export async function fetchAmendmentQueue(fetcher: typeof fetch = fetch): Promise<PatientAmendment[]> {
  const response = await fetcher("/api/amendments/", { credentials: "include" });
  if (!response.ok) throw new Error("Unable to load amendment review queue.");
  return response.json();
}
export async function reviewAmendment(id: number, decision: "accepted" | "denied" | "appended", decisionReason = "", fetcher: typeof fetch = fetch): Promise<PatientAmendment> {
  const response = await fetcher(`/api/amendments/${id}/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, decision_reason: decisionReason }) });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Unable to decide amendment.");
  return response.json();
}
export async function startAmendmentReview(id: number, fetcher: typeof fetch = fetch): Promise<PatientAmendment> {
  const response = await fetcher(`/api/amendments/${id}/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "start_review" }) });
  if (!response.ok) throw new Error("Unable to start amendment review.");
  return response.json();
}

export async function previewDevice(publicId: string, udi: string, fetcher: typeof fetch = fetch): Promise<DeviceParsePreview> {
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/devices/parse/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ udi }) });
  if (!response.ok) throw new Error("UDI parser preview unavailable.");
  return response.json();
}
export async function createDevice(publicId: string, payload: Record<string, string>, fetcher: typeof fetch = fetch): Promise<DeviceVersion> {
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/devices/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Unable to save device.");
  return response.json();
}
export async function fetchDeviceHistory(publicId: string, deviceId: number, fetcher: typeof fetch = fetch): Promise<DeviceVersion[]> {
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/devices/${deviceId}/history/`, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to load device history.");
  return response.json();
}

export async function fetchFamilyHistory(publicId: string, fetcher: typeof fetch = fetch): Promise<FamilyHistoryVersion[]> {
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/family-history/`, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to load family history.");
  return response.json();
}

export async function createFamilyHistory(publicId: string, payload: Record<string, string | boolean>, fetcher: typeof fetch = fetch): Promise<FamilyHistoryVersion> {
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/family-history/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error("Unable to save family history; terminology validation failed or is unavailable.");
  return response.json();
}

export async function fetchJobs(fetcher: typeof fetch = fetch): Promise<JobStatus[]> {
  const response = await fetcher("/api/jobs/", { credentials: "include" });
  if (!response.ok) throw new Error("Unable to load job status.");
  return response.json() as Promise<JobStatus[]>;
}

export async function cancelJob(id: string, fetcher: typeof fetch = fetch): Promise<JobStatus> {
  const response = await fetcher(`/api/jobs/${encodeURIComponent(id)}/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action: "cancel" }) });
  if (!response.ok) throw new Error("Unable to cancel job.");
  return response.json() as Promise<JobStatus>;
}

export async function requestPatientExport(publicId: string, format: PatientExport["format"], fetcher: typeof fetch = fetch): Promise<PatientExport> {
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/exports/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ format }) });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Export unavailable; retry safely.");
  return response.json() as Promise<PatientExport>;
}

export async function requestPopulationExport(payload: Record<string, string | number>, idempotencyKey: string, fetcher: typeof fetch = fetch): Promise<PopulationExport> { const response = await fetcher("/api/admin/population-exports/", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", "Idempotency-Key": idempotencyKey }, body: JSON.stringify(payload) }); if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Population export unavailable; retry safely."); return response.json(); }
export async function fetchPopulationExports(fetcher: typeof fetch = fetch): Promise<PopulationExport[]> { const response = await fetcher("/api/admin/population-exports/", { credentials: "include" }); if (!response.ok) throw new Error("Unable to load population exports."); return response.json(); }
export async function populationExportAction(id: string, action: "cancel" | "retry", fetcher: typeof fetch = fetch): Promise<PopulationExport> { const response = await fetcher(`/api/admin/population-exports/${encodeURIComponent(id)}/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ action }) }); if (!response.ok) throw new Error("Unable to update population export."); return response.json(); }

export async function fetchMedications(publicId: string, fetcher: typeof fetch = fetch): Promise<MedicationOrder[]> {
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/medications/`, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to load medication history.");
  return response.json() as Promise<MedicationOrder[]>;
}

export async function createMedication(publicId: string, payload: Record<string, string | number>, fetcher: typeof fetch = fetch): Promise<MedicationOrder> {
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/medications/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  if (!response.ok) throw new Error("Unable to save medication draft.");
  return response.json() as Promise<MedicationOrder>;
}

export async function fetchMedicationHistory(publicId: string, orderId: number, fetcher: typeof fetch = fetch): Promise<MedicationVersion[]> {
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/medications/${orderId}/history/`, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to load medication history.");
  return response.json() as Promise<MedicationVersion[]>;
}

export async function evaluateMedication(publicId: string, orderId: number, fetcher: typeof fetch = fetch): Promise<InteractionEvaluation> {
  // type-10022026-Maurice: Frontend safety boundary never logs clinical response payloads.
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/medications/${orderId}/evaluate/`, { method: "POST", credentials: "include" });
  if (!response.ok) throw new Error("Safety evaluation unavailable; signing is blocked.");
  return response.json() as Promise<InteractionEvaluation>;
}

export async function acknowledgeMedication(publicId: string, orderId: number, evaluationId: number, fetcher: typeof fetch = fetch): Promise<void> {
  // type-10022026-Maurice: Explicit clinician acknowledgement is a separate auditable request.
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/medications/${orderId}/acknowledge/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ evaluation_id: evaluationId }) });
  if (!response.ok) throw new Error("Unable to acknowledge safety alert.");
}

export async function signMedication(publicId: string, orderId: number, evaluationId: number, acknowledged: boolean, fetcher: typeof fetch = fetch): Promise<MedicationVersion> {
  // type-10022026-Maurice: Signing is only reported successful after the backend atomically activates it.
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/medications/${orderId}/sign/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ evaluation_id: evaluationId, acknowledged }) });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Signing unavailable; retry safely.");
  return (await response.json() as { version: MedicationVersion }).version;
}

export async function fetchAudit(fetcher: typeof fetch = fetch, sink: LogSink = () => undefined, trace: RecordTrace = () => undefined): Promise<AuditEvent[]> {
  trace({ event: "entry", function: "fetchAudit" });
  sink({ level: "info", event: "audit.viewer.entry" });
  try {
    const response = await fetcher("/api/audit/?ordering=-occurred_at", { credentials: "include" });
    if (!response.ok) throw new Error(`Audit report failed (${response.status})`);
    const data = await response.json() as { results: AuditEvent[] };
    sink({ level: "info", event: "audit.viewer.exit", outcome: "success", httpStatus: response.status });
    trace({ event: "exit", function: "fetchAudit" });
    return data.results;
  } catch (error) {
    sink({ level: "error", event: "audit.viewer.error", outcome: "failure" });
    trace({ event: "error", function: "fetchAudit" });
    throw error;
  }
}

export async function fetchAdminUsers(fetcher: typeof fetch = fetch): Promise<AdminUser[]> {
  const response = await fetcher("/api/admin/users/?page_size=100", { credentials: "include" });
  if (!response.ok) throw new Error("Unable to load administrator users.");
  return (await response.json() as { results: AdminUser[] }).results;
}

export async function createAdminUser(username: string, password: string, role: AdminUser["role"], fetcher: typeof fetch = fetch): Promise<AdminUser> {
  const response = await fetcher("/api/admin/users/", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username, password, role }) });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Unable to create user.");
  return response.json() as Promise<AdminUser>;
}

export async function updateAdminUser(id: number, update: Partial<Pick<AdminUser, "role" | "is_active">>, fetcher: typeof fetch = fetch): Promise<AdminUser> {
  const response = await fetcher(`/api/admin/users/${id}/`, { method: "PATCH", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(update) });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Unable to update user.");
  return response.json() as Promise<AdminUser>;
}

export async function fetchInteractionAdmin(fetcher: typeof fetch = fetch): Promise<{ rules: InteractionRule[]; severity_floor: "LOW" | "MODERATE" | "HIGH"; severity_choices: string[] }> {
  const response = await fetcher("/api/admin/interaction-rules/", { credentials: "include" });
  if (!response.ok) throw new Error("Unable to load safety settings.");
  return response.json();
}

export async function updateSeverityFloor(floor: "LOW" | "MODERATE" | "HIGH", fetcher: typeof fetch = fetch): Promise<void> {
  const response = await fetcher("/api/admin/interaction-rules/", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ severity_floor: floor }) });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Unable to update safety floor.");
}

export async function fetchPatients(query = "", fetcher: typeof fetch = fetch, sink: LogSink = () => undefined, trace: RecordTrace = () => undefined): Promise<PatientRecord[]> {
  trace({ event: "entry", function: "fetchPatients" });
  sink({ level: "info", event: "records.search.entry" });
  try {
    const response = await fetcher(`/api/patients/?q=${encodeURIComponent(query)}`, { credentials: "include" });
    if (!response.ok) throw new Error(`Record search failed (${response.status})`);
    const data = await response.json() as PatientRecord[];
    sink({ level: "info", event: "records.search.exit", outcome: "success", httpStatus: response.status });
    trace({ event: "exit", function: "fetchPatients" });
    return data;
  } catch (error) {
    sink({ level: "error", event: "records.search.error", outcome: "failure" });
    trace({ event: "error", function: "fetchPatients" });
    throw error;
  }
}

export async function fetchPatient(publicId: string, fetcher: typeof fetch = fetch, sink: LogSink = () => undefined, trace: RecordTrace = () => undefined): Promise<PatientRecord> {
  trace({ event: "entry", function: "fetchPatient" });
  sink({ level: "info", event: "records.detail.entry" });
  try {
    const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/`, { credentials: "include" });
    if (!response.ok) throw new Error(`Record detail failed (${response.status})`);
    const data = await response.json() as PatientRecord;
    sink({ level: "info", event: "records.detail.exit", outcome: "success", httpStatus: response.status });
    trace({ event: "exit", function: "fetchPatient" });
    return data;
  } catch (error) {
    sink({ level: "error", event: "records.detail.error", outcome: "failure" });
    trace({ event: "error", function: "fetchPatient" });
    throw error;
  }
}

export type QuestionnaireItem = { id: number; link_id: string; text: string; item_type: "boolean" | "integer" | "decimal" | "date" | "string" | "choice" | "quantity"; ordinal: number; required: boolean; repeats: boolean; min_length?: number | null; max_length?: number | null; min_value?: string | null; max_value?: string | null; options: Array<string | { value: string }> };
export type Questionnaire = { id: number; code: string; title: string; version: number; items: QuestionnaireItem[] };
export type QuestionnaireResponse = { id: number; version: number; questionnaire_id: number; questionnaire_version_number: number; status: string; answers: Record<string, unknown>; response_id?: number };

async function questionnaireRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { credentials: "include", ...init });
  if (response.status === 401) throw new Error("Your session expired; please sign in again.");
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Questionnaire request failed.");
  return response.json() as Promise<T>;
}
export const fetchQuestionnaires = () => questionnaireRequest<Questionnaire[]>("/api/questionnaires/");
export const fetchQuestionnaireResponses = (patient: string) => questionnaireRequest<QuestionnaireResponse[]>(`/api/patients/${encodeURIComponent(patient)}/questionnaire-responses/`);
export const saveQuestionnaireResponse = (patient: string, payload: { questionnaire_id: number; questionnaire_version: number; answers: Record<string, unknown>; status: "draft" | "submitted" }) => questionnaireRequest<QuestionnaireResponse>(`/api/patients/${encodeURIComponent(patient)}/questionnaire-responses/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
export const fetchQuestionnaireReviewQueue = () => questionnaireRequest<QuestionnaireResponse[]>("/api/questionnaire-review-queue/");
export const reviewQuestionnaireResponse = (id: number, decision: string, reason = "") => questionnaireRequest<{ id: number }>(`/api/questionnaire-response-versions/${id}/review/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision, reason }) });
