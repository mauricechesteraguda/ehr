// type-10022026-Maurice: Minimal role-scoped post-login shell.
import { StrictMode, type FormEvent } from "react";
import { createRoot } from "react-dom/client";
import { logout, roleShellTitle, type Role } from "./auth";
import { useEffect, useState } from "react";
import "./styles.css";
import { roleWorkspacePath } from "./workflow";
import { acknowledgeMedication, createAdminUser, createMedication, evaluateMedication, fetchAdminUsers, fetchAudit, fetchInteractionAdmin, fetchMedicationHistory, fetchMedications, fetchPatient, fetchPatients, requestPatientExport, signMedication, updateAdminUser, updateSeverityFloor, type AdminUser, type AuditEvent, type InteractionEvaluation, type MedicationOrder, type MedicationVersion, type PatientRecord, type PatientExport, type InteractionRule } from "./records";

function Login({ onSuccess }: { onSuccess: (role: Role, username: string) => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setBusy(true); setError("");
    const values = Object.fromEntries(new FormData(event.currentTarget).entries());
    fetch("/api/auth/login/", { method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(values) })
      .then(async (response) => { const body = await response.json().catch(() => ({})); if (!response.ok) throw new Error(body.detail ?? "Unable to sign in; check credentials and TOTP."); return body; })
      .then((body) => onSuccess(body.role as Role, String(values.username)))
      .catch((reason: Error) => setError(reason.message)).finally(() => setBusy(false));
  };
  return <main><h1>EHR demo sign in</h1><p role="note"><strong>Synthetic data only.</strong> Never use real credentials or patient data.</p><form onSubmit={submit} aria-label="Sign in"><label>Username <input name="username" autoComplete="username" required /></label><label>Password <input name="password" type="password" autoComplete="current-password" required /></label><label>Current TOTP code <input name="otp" inputMode="numeric" pattern="[0-9]{6}" required /></label><button disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>{error && <p role="alert">{error}</p>}</form></main>;
}

function Header({ role, username, navigate }: { role: Role; username: string; navigate: (path: string) => void }) {
  return <header><h1>EHR demo</h1><p>{roleShellTitle(role)} · {username}</p><nav aria-label="Workspace navigation"><button onClick={() => navigate("/")}>Records</button>{role === "admin" && <button onClick={() => navigate("/admin")}>Administration</button>}{role === "developer" && <button onClick={() => navigate("/developer")}>SMART developer</button>}<button onClick={() => logout().then(() => window.location.reload())}>Sign out</button></nav></header>;
}

function App() {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [username, setUsername] = useState("");
  const [patients, setPatients] = useState<PatientRecord[]>([]);
  const [selected, setSelected] = useState<PatientRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [role, setRole] = useState<Role>("patient");
  const [route, setRoute] = useState(window.location.pathname);
  const [medications, setMedications] = useState<MedicationOrder[]>([]);
  const [medicationHistory, setMedicationHistory] = useState<MedicationVersion[]>([]);
  const [medicationError, setMedicationError] = useState("");
  const [savingMedication, setSavingMedication] = useState(false);
  const [exportFormat, setExportFormat] = useState<"json" | "pdf">("json");
  const [exportState, setExportState] = useState<PatientExport | null>(null);
  const [exportError, setExportError] = useState("");
  const [exportLoading, setExportLoading] = useState(false);
  const [evaluations, setEvaluations] = useState<Record<number, InteractionEvaluation>>({});
  const [acknowledged, setAcknowledged] = useState<Record<number, boolean>>({});
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [rules, setRules] = useState<InteractionRule[]>([]);
  const [severityFloor, setSeverityFloor] = useState<"LOW" | "MODERATE" | "HIGH">("LOW");
  const [adminError, setAdminError] = useState("");
  const [newUser, setNewUser] = useState({ username: "", password: "", role: "patient" as AdminUser["role"] });
  const isAdmin = role === "admin";
  useEffect(() => {
    fetch("/api/auth/session/", { credentials: "include" }).then((response) => response.ok ? response.json() : null).then((session) => {
      if (session?.role) { setRole(session.role as Role); setUsername(session.username ?? ""); setAuthenticated(true); }
      else setAuthenticated(false);
    }).catch(() => setAuthenticated(false));
  }, []);
  useEffect(() => {
    if (authenticated && role !== "developer") fetchPatients().then(setPatients).catch(() => setError("Unable to load synthetic patients; try again.")).finally(() => setLoading(false));
    else if (authenticated) setLoading(false);
  }, [authenticated, role]);
  useEffect(() => { if (isAdmin) { fetchAudit().then(setAudit).catch(() => setAdminError("Unable to load audit evidence; re-authenticate.")); fetchAdminUsers().then(setAdminUsers).catch(() => setAdminError("Unable to load administrator users.")); fetchInteractionAdmin().then((settings) => { setRules(settings.rules); setSeverityFloor(settings.severity_floor); }).catch(() => setAdminError("Unable to load safety settings.")); } }, [isAdmin]);
  const navigate = (next: string) => { window.history.pushState({}, "", next); setRoute(next); setSelected(null); };
  if (authenticated === null) return <main aria-busy="true"><p role="status">Loading secure session…</p></main>;
  if (!authenticated) return <Login onSuccess={(nextRole, nextUsername) => { setRole(nextRole); setUsername(nextUsername); setAuthenticated(true); }} />;
  if (route === roleWorkspacePath("developer")) return <main><Header role={role} username={username} navigate={navigate} /><section aria-labelledby="developer-title"><h2 id="developer-title">Developer SMART workspace</h2><p>Use the documented local SMART demo to register an app, review consent, exchange PKCE tokens, refresh, and read FHIR Patient.</p><p role="note">Tokens are never stored in browser storage. Use HTTPS callback URLs and synthetic data only.</p></section></main>;
  const openPatient = (id: string) => { setLoading(true); setError(""); fetchPatient(id).then((record) => { setSelected(record); return fetchMedications(id).then(setMedications); }).catch(() => setError("Unable to load this synthetic record.")).finally(() => setLoading(false)); };
  const submitMedication = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!selected || role !== "clinician") return; setSavingMedication(true); setMedicationError(""); const form = new FormData(event.currentTarget); const payload = Object.fromEntries(form.entries()) as Record<string, string | number>; payload.dose = Number(payload.dose); payload.quantity = Number(payload.quantity); payload.refills = Number(payload.refills); createMedication(selected.public_id, payload).then((order) => { setMedications((current) => [...current, order]); event.currentTarget.reset(); }).catch(() => setMedicationError("Unable to save draft. No medication or audit event was created.")).finally(() => setSavingMedication(false)); };
  return <main>
     <Header role={role} username={username} navigate={navigate} /><p>{roleShellTitle(role)}</p>
    <aside role="note"><strong>Synthetic data only.</strong> This demo contains no real patient information.</aside>
    {loading && <p role="status">Loading patient records…</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !error && !selected && patients.length === 0 && <p>No synthetic patients found.</p>}
    {!selected && patients.map((patient) => <button key={patient.public_id} onClick={() => openPatient(patient.public_id)}>{patient.display_name}</button>)}
     {isAdmin && <section aria-label="Audit viewer"><h2>Audit trail</h2><p>Administrator-only, append-only evidence.</p><table><thead><tr><th>UTC time</th><th>Actor</th><th>Action</th><th>Patient</th><th>Current hash</th></tr></thead><tbody>{audit.map((event) => <tr key={event.sequence}><td>{event.occurred_at}</td><td>{event.actor}</td><td>{event.action}</td><td>{event.patient ?? "—"}</td><td>{event.current_hash}</td></tr>)}</tbody></table></section>}
     {isAdmin && <section aria-label="Administration"><h2>Administration</h2>{adminError && <p role="alert">{adminError}</p>}<h3>Users</h3><form onSubmit={(event) => { event.preventDefault(); createAdminUser(newUser.username, newUser.password, newUser.role).then((user) => { setAdminUsers((items) => [...items, user]); setNewUser({ username: "", password: "", role: "patient" }); }).catch(() => setAdminError("Unable to create user.")); }}><input aria-label="New username" value={newUser.username} onChange={(event) => setNewUser({ ...newUser, username: event.target.value })} placeholder="Username" required /><input aria-label="Temporary password" type="password" value={newUser.password} onChange={(event) => setNewUser({ ...newUser, password: event.target.value })} placeholder="Temporary password" required /><select aria-label="New user role" value={newUser.role} onChange={(event) => setNewUser({ ...newUser, role: event.target.value as AdminUser["role"] })}><option value="patient">Patient</option><option value="clinician">Clinician</option><option value="admin">Administrator</option><option value="developer">Developer</option></select><button>Create user</button></form><table><thead><tr><th>User</th><th>Role</th><th>Active</th><th>Action</th></tr></thead><tbody>{adminUsers.map((user) => <tr key={user.id}><td>{user.username}</td><td><select aria-label={`Role for ${user.username}`} value={user.role} onChange={(event) => updateAdminUser(user.id, { role: event.target.value as AdminUser["role"] }).then((next) => setAdminUsers((items) => items.map((item) => item.id === next.id ? next : item))).catch(() => setAdminError("Unable to update user."))}><option value="patient">Patient</option><option value="clinician">Clinician</option><option value="admin">Administrator</option><option value="developer">Developer</option></select></td><td>{user.is_active ? "Active" : "Inactive"}</td><td><button onClick={() => updateAdminUser(user.id, { is_active: !user.is_active }).then((next) => setAdminUsers((items) => items.map((item) => item.id === next.id ? next : item))).catch(() => setAdminError("Unable to update user."))}>{user.is_active ? "Deactivate" : "Activate"}</button></td></tr>)}</tbody></table><h3>Interaction safety</h3><label>Minimum alert severity <select value={severityFloor} onChange={(event) => { const next = event.target.value as "LOW" | "MODERATE" | "HIGH"; updateSeverityFloor(next).then(() => setSeverityFloor(next)).catch(() => setAdminError("Unable to update safety floor.")); }}><option value="LOW">Low</option><option value="MODERATE">Moderate</option><option value="HIGH">High</option></select></label><ul>{rules.map((rule) => <li key={rule.id}>{rule.severity}: {rule.description} ({rule.active ? "active" : "inactive"})</li>)}</ul></section>}
    {selected && <section aria-label="Patient record"><button onClick={() => setSelected(null)}>Back</button><h2>{selected.display_name}</h2>
      <p>Race: {selected.race} · Ethnicity: {selected.ethnicity} · Language: {selected.preferred_language}</p>
      <p>Sex: {selected.sex} · Sexual orientation: {selected.sexual_orientation} · Gender identity: {selected.gender_identity}</p>
       <p>Birth date: {selected.birth_date} · Death date: {selected.death_date ?? "Not recorded"}</p>
       <section aria-label="Patient record download"><h3>Download synthetic record</h3><label>Format <select value={exportFormat} onChange={(event) => setExportFormat(event.target.value as "json" | "pdf")}><option value="json">JSON + data dictionary</option><option value="pdf">PDF (non-clinical)</option></select></label><button disabled={exportLoading} onClick={() => { setExportError(""); setExportState(null); setExportLoading(true); requestPatientExport(selected.public_id, exportFormat).then(setExportState).catch((error: Error) => setExportError(error.message)).finally(() => setExportLoading(false)); }}>{exportLoading ? "Preparing…" : "Create download"}</button>{exportError && <p role="alert">{exportError}</p>}{exportState && <p role="status">Ready. SHA-256: {exportState.sha256}. Expires: {exportState.expires_at}. <a href={exportState.download_url}>Download</a></p>}</section>
      <h3>Allergies</h3><ul>{selected.allergies.map((item) => <li key={String(item.code)}>{item.label}</li>)}</ul>
      <h3>Conditions</h3><ul>{selected.conditions.map((item) => <li key={String(item.code)}>{item.label}</li>)}</ul>
      <h3>Observations</h3><ul>{selected.observations.map((item) => <li key={String(item.code)}>{item.label}: {item.value} {item.unit}</li>)}</ul>
       <h3>Devices (read-only)</h3><ul>{selected.devices.map((item) => <li key={String(item.code)}>{item.label} ({item.status})</li>)}</ul>
       <h3>Medication orders</h3>
        {role === "clinician" && <form onSubmit={submitMedication} aria-label="Clinician medication draft form"><label>Medication code <input name="medication_code" required /></label><label>Name <input name="medication_name" required /></label><label>Dose <input name="dose" type="number" min="0.001" step="0.001" required /></label><label>Unit <input name="dose_unit" required /></label><label>Route <input name="route" required /></label><label>Frequency <input name="frequency" required /></label><label>Start date <input name="start_date" type="date" required /></label><label>Quantity <input name="quantity" type="number" min="0.001" step="0.001" required /></label><label>Refills <input name="refills" type="number" min="0" step="1" defaultValue="0" required /></label><label>Indication <input name="indication" required /></label><button disabled={savingMedication}>{savingMedication ? "Saving…" : "Save draft"}</button></form>}
       {medicationError && <p role="alert">{medicationError}</p>}
        {medications.length === 0 ? <p>No medication orders found.</p> : <ul>{medications.map((order) => <li key={order.id}><strong>{order.active_version?.medication_name}</strong> — {order.active_version?.status}<button onClick={() => fetchMedicationHistory(selected.public_id, order.id).then(setMedicationHistory).catch(() => setMedicationError("Unable to load medication history."))}>History</button>{role === "clinician" && order.active_version?.status === "draft" && <><button onClick={() => evaluateMedication(selected.public_id, order.id).then((evaluation) => setEvaluations((current) => ({ ...current, [order.id]: evaluation }))).catch(() => setMedicationError("Safety evaluation unavailable; signing is blocked."))}>Evaluate safety</button>{evaluations[order.id] && <section aria-label="Medication safety alerts"><ul>{evaluations[order.id].findings.map((finding) => <li key={finding.rule_id}>{finding.suppressed ? "Suppressed below floor" : `${finding.severity}: ${finding.description}`}</li>)}</ul>{evaluations[order.id].findings.some((finding) => !finding.suppressed && finding.severity !== "CRITICAL") && <button onClick={() => acknowledgeMedication(selected.public_id, order.id, evaluations[order.id].id).then(() => setAcknowledged((current) => ({ ...current, [order.id]: true }))).catch(() => setMedicationError("Unable to acknowledge safety alert."))}>Acknowledge</button>}<button disabled={evaluations[order.id].findings.some((finding) => finding.severity === "CRITICAL") || (evaluations[order.id].findings.some((finding) => !finding.suppressed) && !acknowledged[order.id])} onClick={() => signMedication(selected.public_id, order.id, evaluations[order.id].id, Boolean(acknowledged[order.id])).then((version) => setMedications((current) => current.map((item) => item.id === order.id ? { ...item, active_version: version } : item))).catch((error: Error) => setMedicationError(error.message))}>Sign safely</button></section>}</>}</li>)}</ul>}
       {medicationHistory.length > 0 && <section aria-label="Immutable medication history"><h4>Immutable history</h4><ol>{medicationHistory.map((version) => <li key={version.id}>v{version.version}: {version.medication_name}, {version.dose} {version.dose_unit}, {version.status}</li>)}</ol></section>}
     </section>}
  </main>;
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
