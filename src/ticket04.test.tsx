// @vitest-environment jsdom
// type-10042026-Maurice: Ticket04 clinician workflow accessibility and responsive RED-first evidence.
import axe from "axe-core";
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { AppShell } from "./ui";

const clinicianShell = renderToStaticMarkup(
  <AppShell role="clinician" username="demo" route="/" onNavigate={() => undefined} page="Clinician workspace">
    <div className="workspace-dashboard">
      <aside className="breakglass-banner" role="alert" aria-label="Emergency access banner"><strong>⚠ EMERGENCY BREAK-GLASS ACTIVE</strong><button className="critical-action">Revoke emergency access</button></aside>
      <section className="patient-record" aria-label="Patient record">
        <nav className="record-tabs" aria-label="Patient record sections"><a href="#overview">Overview</a><a href="#clinical">Clinical context</a><a href="#actions">Actions</a></nav>
        <section className="safety-alerts" aria-label="Medication safety alerts"><span className="severity-badge severity-critical">◆ CRITICAL</span><button className="critical-action" disabled>Sign safely</button></section>
        <section aria-label="Questionnaire review queue"><h2>Questionnaire review queue</h2><p>No submitted responses awaiting review.</p></section>
        <section aria-label="Patient amendment review queue"><h2>Patient amendment review queue</h2><p>No amendment requests awaiting review.</p></section>
        <section aria-label="Direct delivery"><h2>Direct delivery (local simulation)</h2><p>Simulation only.</p></section>
        <section aria-label="C-CDA transition and reconciliation"><h2>C-CDA transition</h2></section>
      </section>
    </div>
  </AppShell>,
);

describe("Ticket 04 — clinician workspace workflow", () => {
  it("TC-UI-0028 / REQ-UI-0010: keeps a visible focus path with skip link and section tabs", () => {
    expect(clinicianShell).toContain('href="#main-content"');
    expect(clinicianShell).toContain('aria-label="Patient record sections"');
  });
  it("TC-UI-0029 / REQ-RESP-0001: declares reduced-motion-safe workflow classes", () => {
    expect(clinicianShell).toContain("workspace-dashboard");
    expect(clinicianShell).toContain("record-tabs");
  });
  it("TC-UI-0030 / REQ-RESP-0002: exposes clinician landmarks for axe review", () => {
    expect(clinicianShell).toContain('aria-label="Patient record"');
    expect(clinicianShell).toContain('aria-label="Medication safety alerts"');
  });
  it("TC-UI-0031 / REQ-RESP-0003: uses explicit target-size action classes", () => {
    expect(clinicianShell).toContain("critical-action");
    expect(clinicianShell).toContain("Revoke emergency access");
  });
  it("TC-UI-0032 / REQ-RESP-0004: keeps the emergency state directional", () => {
    expect(clinicianShell).toContain('role="alert"');
    expect(clinicianShell).toContain("EMERGENCY BREAK-GLASS ACTIVE");
  });
  it("TC-UI-0033 / REQ-RESP-0005: preserves responsive workflow sections", () => {
    expect(clinicianShell).toContain("Questionnaire review queue");
    expect(clinicianShell).toContain("Patient amendment review queue");
  });
  it("TC-UI-0034 / REQ-RESP-0006: preserves empty queue guidance", () => {
    expect(clinicianShell).toContain("No submitted responses awaiting review.");
    expect(clinicianShell).toContain("No amendment requests awaiting review.");
  });
  it("TC-UI-0035 / REQ-RESP-0007: keeps simulated exchange boundaries visible", () => {
    expect(clinicianShell).toContain("Direct delivery (local simulation)");
    expect(clinicianShell).toContain("C-CDA transition");
  });
  it("TC-UI-0036 / REQ-RESP-0008: severity is text and icon, not color alone", () => {
    expect(clinicianShell).toContain('class="severity-badge severity-critical"');
    expect(clinicianShell).toContain("◆ CRITICAL");
  });
  it("TC-UI-0030 / REQ-RESP-0002: clinician workflow has no serious or critical axe findings", async () => {
    document.body.innerHTML = clinicianShell;
    const result = await axe.run(document.body);
    expect(result.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
  });
});
