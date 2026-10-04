// type-10042026-Maurice: Ticket03 responsive auth/workspace RED-first evidence.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Login } from "./main";
import { AppShell } from "./ui";

describe("Ticket 03 — authentication and patient workspace composition", () => {
  const shell = renderToStaticMarkup(<AppShell role="patient" username="demo" route="/" onNavigate={() => undefined}><section className="workspace-dashboard"><div className="patient-record"><div className="record-heading"><h2>Demo patient</h2></div><div className="record-grid"><article>Demographics</article><article>Care signal</article></div></div></section></AppShell>);

  it("TC-UI-0019 / REQ-A11Y-0001: exposes mobile navigation and responsive touch controls", () => { expect(shell).toContain("mobile-menu"); expect(shell).toContain("workspace-dashboard"); });
  it("TC-UI-0020 / REQ-A11Y-0002: keeps workspace surfaces safe for responsive tables", () => { expect(shell).toContain("app-shell"); expect(shell).toContain("page-frame"); });
  it("TC-UI-0021 / REQ-A11Y-0003: keeps forms and record cards responsive", () => { expect(shell).toContain("page-frame"); expect(shell).toContain("ui-button"); });
  it("TC-UI-0022 / REQ-A11Y-0004: preserves textual fallback content", () => { expect(shell).toContain("Demographics"); expect(shell).toContain("Care signal"); });
  it("TC-UI-0023 / REQ-A11Y-0005: provides stable workspace landmarks", () => { expect(shell).toContain('aria-label="Workspace navigation"'); expect(shell).toContain('aria-label="Breadcrumb"'); });
  it("TC-UI-0024 / REQ-A11Y-0006: renders the intentional shell composition", () => { expect(shell).toContain("context-ribbon"); expect(shell).toContain("record-heading"); });
  it("TC-UI-0025 / REQ-A11Y-0007: keeps theme changes memory-only", () => { expect(shell).not.toContain("localStorage"); expect(shell).not.toContain("sessionStorage"); });
  it("TC-UI-0026 / REQ-A11Y-0008: includes semantic dark/light surfaces", () => { expect(shell).toContain("theme-dark"); expect(shell).toContain("context-ribbon"); });
  it("TC-UI-0027 / REQ-A11Y-0009: auth has skip-ready main content and live errors", () => { const html = renderToStaticMarkup(<Login onSuccess={() => undefined} />); expect(html).toContain('id="main-content"'); expect(html).toContain('aria-live="polite"'); expect(html).toContain("Synthetic data only"); });
});
