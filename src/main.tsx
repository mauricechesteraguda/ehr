// type-10022026-Maurice: Minimal role-scoped post-login shell.
import { StrictMode, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { roleShellTitle, type Role } from "./auth";
import { useEffect, useState } from "react";
import { createMedication, fetchAudit, fetchMedicationHistory, fetchMedications, fetchPatient, fetchPatients, type AuditEvent, type MedicationOrder, type MedicationVersion, type PatientRecord } from "./records";

function App() {
  const [patients, setPatients] = useState<PatientRecord[]>([]);
  const [selected, setSelected] = useState<PatientRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [role, setRole] = useState<Role>("patient");
  const [medications, setMedications] = useState<MedicationOrder[]>([]);
  const [medicationHistory, setMedicationHistory] = useState<MedicationVersion[]>([]);
  const [medicationError, setMedicationError] = useState("");
  const [savingMedication, setSavingMedication] = useState(false);
  const isAdmin = role === "admin";
  useEffect(() => {
    fetchPatients().then(setPatients).catch(() => setError("Unable to load synthetic patients.")).finally(() => setLoading(false));
  }, []);
  useEffect(() => { if (isAdmin) fetchAudit().then(setAudit).catch(() => undefined); }, [isAdmin]);
  useEffect(() => { fetch("/api/auth/session/", { credentials: "include" }).then((response) => response.ok ? response.json() : null).then((session) => { if (session?.role) setRole(session.role as Role); }).catch(() => undefined); }, []);
  const openPatient = (id: string) => { setLoading(true); setError(""); fetchPatient(id).then((record) => { setSelected(record); return fetchMedications(id).then(setMedications); }).catch(() => setError("Unable to load this synthetic record.")).finally(() => setLoading(false)); };
  const submitMedication = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!selected || role !== "clinician") return; setSavingMedication(true); setMedicationError(""); const form = new FormData(event.currentTarget); const payload = Object.fromEntries(form.entries()) as Record<string, string | number>; payload.dose = Number(payload.dose); payload.quantity = Number(payload.quantity); payload.refills = Number(payload.refills); createMedication(selected.public_id, payload).then((order) => { setMedications((current) => [...current, order]); event.currentTarget.reset(); }).catch(() => setMedicationError("Unable to save draft. No medication or audit event was created.")).finally(() => setSavingMedication(false)); };
  return <main>
    <h1>EHR demo</h1><p>{roleShellTitle(role)}</p>
    <aside role="note"><strong>Synthetic data only.</strong> This demo contains no real patient information.</aside>
    {loading && <p role="status">Loading patient records…</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !error && !selected && patients.length === 0 && <p>No synthetic patients found.</p>}
    {!selected && patients.map((patient) => <button key={patient.public_id} onClick={() => openPatient(patient.public_id)}>{patient.display_name}</button>)}
    {isAdmin && <section aria-label="Audit viewer"><h2>Audit trail</h2><p>Administrator-only, append-only evidence.</p><table><thead><tr><th>UTC time</th><th>Actor</th><th>Action</th><th>Patient</th><th>Current hash</th></tr></thead><tbody>{audit.map((event) => <tr key={event.sequence}><td>{event.occurred_at}</td><td>{event.actor}</td><td>{event.action}</td><td>{event.patient ?? "—"}</td><td>{event.current_hash}</td></tr>)}</tbody></table></section>}
    {selected && <section aria-label="Patient record"><button onClick={() => setSelected(null)}>Back</button><h2>{selected.display_name}</h2>
      <p>Race: {selected.race} · Ethnicity: {selected.ethnicity} · Language: {selected.preferred_language}</p>
      <p>Sex: {selected.sex} · Sexual orientation: {selected.sexual_orientation} · Gender identity: {selected.gender_identity}</p>
      <p>Birth date: {selected.birth_date} · Death date: {selected.death_date ?? "Not recorded"}</p>
      <h3>Allergies</h3><ul>{selected.allergies.map((item) => <li key={String(item.code)}>{item.label}</li>)}</ul>
      <h3>Conditions</h3><ul>{selected.conditions.map((item) => <li key={String(item.code)}>{item.label}</li>)}</ul>
      <h3>Observations</h3><ul>{selected.observations.map((item) => <li key={String(item.code)}>{item.label}: {item.value} {item.unit}</li>)}</ul>
       <h3>Devices (read-only)</h3><ul>{selected.devices.map((item) => <li key={String(item.code)}>{item.label} ({item.status})</li>)}</ul>
       <h3>Medication orders</h3>
       {role === "clinician" && <form onSubmit={submitMedication} aria-label="Clinician medication draft form"><label>Medication code <input name="medication_code" required /></label><label>Name <input name="medication_name" required /></label><label>Dose <input name="dose" type="number" min="0.001" step="0.001" required /></label><label>Unit <input name="dose_unit" required /></label><label>Route <input name="route" required /></label><label>Frequency <input name="frequency" required /></label><label>Start date <input name="start_date" type="date" required /></label><label>Quantity <input name="quantity" type="number" min="0.001" step="0.001" required /></label><label>Refills <input name="refills" type="number" min="0" step="1" defaultValue="0" required /></label><label>Indication <input name="indication" required /></label><button disabled={savingMedication}>{savingMedication ? "Saving…" : "Save draft"}</button><p>Signing is intentionally unavailable until interaction evaluation (Ticket 05).</p></form>}
       {medicationError && <p role="alert">{medicationError}</p>}
       {medications.length === 0 ? <p>No medication orders found.</p> : <ul>{medications.map((order) => <li key={order.id}><strong>{order.active_version?.medication_name}</strong> — {order.active_version?.status}<button onClick={() => fetchMedicationHistory(selected.public_id, order.id).then(setMedicationHistory).catch(() => setMedicationError("Unable to load medication history."))}>History</button></li>)}</ul>}
       {medicationHistory.length > 0 && <section aria-label="Immutable medication history"><h4>Immutable history</h4><ol>{medicationHistory.map((version) => <li key={version.id}>v{version.version}: {version.medication_name}, {version.dose} {version.dose_unit}, {version.status}</li>)}</ol></section>}
     </section>}
  </main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
