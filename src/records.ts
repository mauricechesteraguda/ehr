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
export type MedicationVersion = { id: number; version: number; medication_code: string; medication_name: string; dose: string; dose_unit: string; route: string; frequency: string; start_date: string; quantity: string; refills: number; indication: string; status: "draft" | "active" | "cancelled"; supersedes: number | null; created_at: string };
export type MedicationOrder = { id: number; prescriber: string; active_version: MedicationVersion | null };

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
