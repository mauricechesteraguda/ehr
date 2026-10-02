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
};

export type AuditEvent = { sequence: number; actor: string | null; occurred_at: string; patient: string | null; action: string; resource_type: string; resource_id: string; correlation_id: string; previous_hash: string; current_hash: string };
export type AdminUser = { id: number; username: string; role: "clinician" | "patient" | "admin" | "developer"; is_active: boolean; is_staff: boolean; totp_enrolled: boolean };
export type InteractionRule = { id: number; kind: string; medication_code: string; related_medication_code: string; allergy_code: string; severity: "LOW" | "MODERATE" | "HIGH" | "CRITICAL"; description: string; active: boolean };
export type MedicationVersion = { id: number; version: number; medication_code: string; medication_name: string; dose: string; dose_unit: string; route: string; frequency: string; start_date: string; quantity: string; refills: number; indication: string; status: "draft" | "active" | "cancelled"; supersedes: number | null; created_at: string };
export type MedicationOrder = { id: number; prescriber: string; active_version: MedicationVersion | null };
export type InteractionFinding = { rule_id: number; kind: string; severity: "LOW" | "MODERATE" | "HIGH" | "CRITICAL"; description: string; suppressed: boolean };
export type InteractionEvaluation = { id: number; floor: "LOW" | "MODERATE" | "HIGH"; stale: boolean; findings: InteractionFinding[] };
export type PatientExport = { id: string; status: "ready"; format: "json" | "pdf"; sha256: string; expires_at: string; download_url: string };

export async function requestPatientExport(publicId: string, format: PatientExport["format"], fetcher: typeof fetch = fetch): Promise<PatientExport> {
  const response = await fetcher(`/api/patients/${encodeURIComponent(publicId)}/exports/`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ format }) });
  if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail ?? "Export unavailable; retry safely.");
  return response.json() as Promise<PatientExport>;
}

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
