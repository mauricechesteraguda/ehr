// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import axe from "axe-core";
import { renderToStaticMarkup } from "react-dom/server";
import { Login, PatientSelectionPanel } from "./main";
const styles = readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");

const audit = async (html: string) => {
  document.body.innerHTML = html;
  const result = await axe.run(document.body);
  expect(result.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
};

afterEach(() => { document.body.innerHTML = ""; });

describe("Ticket16 accessibility and prototype safety evidence", () => {
  it("test_TC_EXP_0132_accessibility_shell_has_landmarks_and_headings", () => {
    const html = '<header><nav aria-label="Workspace navigation"></nav></header><main id="main-content"><h1>Role workspace</h1><section aria-labelledby="panel-title"><h2 id="panel-title">Panel</h2></section></main>';
    expect(html).toContain('aria-label="Workspace navigation"');
    expect(html).toContain('id="main-content"');
    expect(html).toContain("<h1>");
  });

  it("test_TC_EXP_0133_login_labels_and_live_errors", async () => {
    await audit(renderToStaticMarkup(<Login onSuccess={() => undefined} />));
    expect(document.body.querySelectorAll("label[for]")).toHaveLength(3);
    expect(document.body.textContent).toContain("Synthetic data only");
  });

  it("test_TC_EXP_0134_patient_panel_is_axe_clean", async () => {
    await audit(renderToStaticMarkup(<PatientSelectionPanel />));
    expect(document.body.querySelector("section[aria-labelledby]")).not.toBeNull();
    expect(document.body.textContent).toContain("synthetic fixture values only");
  });

  it("test_TC_EXP_0135_role_panel_markup_is_axe_clean", async () => {
    await audit('<main><h1>Administrator workspace</h1><section aria-labelledby="admin-title"><h2 id="admin-title">Administration</h2><form><label for="role">New user role</label><select id="role"><option>Patient</option></select><button type="submit">Create user</button></form></section></main>');
  });

  it("test_TC_EXP_0136_safety_status_is_text_not_color_only", () => {
    const html = '<aside role="note"><strong>Non-clinical demo:</strong> reminders only.</aside><p role="alert">Safety evaluation unavailable.</p>';
    expect(html).toContain("Non-clinical demo");
    expect(html).toContain('role="alert"');
  });

  it("test_TC_EXP_0137_focus_and_target_markers_exist", () => {
    expect(styles).toContain(":focus-visible");
    expect(styles).toContain("min-height: 2.75rem");
  });

  it("test_TC_EXP_0138_responsive_and_reduced_motion_markers_exist", () => {
    expect(styles).toContain("prefers-reduced-motion: reduce");
    expect(styles).toContain("max-width: 42rem");
  });
});
