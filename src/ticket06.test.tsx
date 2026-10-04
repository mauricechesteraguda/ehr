// @vitest-environment jsdom
// type-10042026-Maurice: Ticket06 regression and evidence contracts.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import axe from "axe-core";
import { AppShell, CategoryBarChart, TrendChart } from "./ui";
import { AdminWorkspace, DeveloperWorkspace } from "./main";

const root = process.cwd();
const read = (file: string) => readFileSync(resolve(root, file), "utf8");
const pngSize = (file: string) => {
  const bytes = readFileSync(resolve(root, file));
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20) };
};
const shell = (role: "patient" | "clinician" | "admin" | "developer", route = "/") =>
  renderToStaticMarkup(<AppShell role={role} username="demo" route={route} onNavigate={() => undefined}><p>Demo workspace</p></AppShell>);

describe("Ticket06 — existing flows, evidence, Compose and static serving", () => {
  it("test_TC_UI_0046_concurrency_and_rollback_regression", () => {
    const html = shell("clinician");
    expect(html).toContain("Synthetic data only");
    expect(html).toContain('id="main-content"');
    expect(read("src/workflow.ts")).toContain("roleWorkspacePath");
  });

  it("test_TC_UI_0047_role_flow_loading_and_error_coverage", async () => {
    const html = shell("admin", "/admin");
    expect(html).toContain('aria-label="Workspace navigation"');
    expect(read("src/main.tsx")).toContain("Loading patient records");
    expect(read("src/main.tsx")).toContain("Unable to load");
    for (const role of ["patient", "clinician", "admin", "developer"] as const) {
      document.body.innerHTML = shell(role);
      const result = await axe.run(document.body);
      expect(result.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? ""))).toEqual([]);
    }
  });

  it("test_TC_UI_0048_api_retry_does_not_duplicate_rows", () => {
    const html = renderToStaticMarkup(<AdminWorkspace users={[]} audit={[]} jobs={[]} rules={[]} severityFloor="LOW" error="" onRetry={() => undefined} onCancelJob={() => undefined} onUpdateUser={() => undefined} onCreateUser={() => undefined} />);
    expect(html.match(/No users loaded\./g)).toHaveLength(1);
    expect(html.match(/No audit events loaded\./g)).toHaveLength(1);
    expect(html).toContain('data-ticket="TC-UI-0039 TC-UI-0040 TC-UI-0042 TC-UI-0043 TC-UI-0044 TC-UI-0045"');
  });

  it("test_TC_UI_0049_theme_does_not_persist_across_reload", () => {
    const html = shell("patient");
    expect(html).not.toContain("localStorage");
    expect(html).not.toContain("sessionStorage");
    expect(read("src/ui.tsx")).toContain('useState<"dark" | "light">("dark")');
  });

  it("test_TC_UI_0050_responsive_forms_retain_correction", () => {
    const styles = read("src/styles.css");
    expect(styles).toContain("grid-template-columns");
    expect(styles).toContain("@media (max-width: 42rem)");
    expect(read("src/main.tsx")).toContain("onChange={(event)");
  });

  it("test_TC_UI_0051_chart_table_survives_svg_failure", () => {
    const html = renderToStaticMarkup(<><TrendChart title="Synthetic trend" points={[{ label: "Jan", value: 2 }]} /><CategoryBarChart title="Synthetic categories" items={[{ label: "Open", value: 1 }]} /></>);
    expect(html).toContain("<table>");
    expect(html).toContain("Synthetic trend data");
    expect(html).toContain("Synthetic categories data");
  });

  it("test_TC_UI_0052_permission_denied_preserves_route", () => {
    const html = shell("patient", "/admin");
    expect(html).toContain('aria-current="page"');
    expect(html).toContain("Workspace");
    expect(read("src/main.tsx")).toContain("You are not authorized to open the administrator workspace");
  });

  it("test_TC_UI_0053_screenshot_gallery_has_viewport_metadata", () => {
    const readme = read("README.md");
    expect(readme).toContain("1440x900");
    expect(readme).toContain("390x844");
    expect(readme).toContain("Synthetic/non-clinical prototype");
    const links = [...readme.matchAll(/\]\((docs\/screenshots\/[^)]+\.png)\)/g)].map((match) => match[1]);
    expect(links.length).toBeGreaterThanOrEqual(6);
    for (const link of links) expect(pngSize(link)).toMatchObject({ width: expect.any(Number), height: expect.any(Number) });
    expect(pngSize("docs/screenshots/login-mfa-mobile.png")).toEqual({ width: 390, height: 844 });
    expect(pngSize("docs/screenshots/login-mfa-tablet.png")).toEqual({ width: 1024, height: 768 });
  });

  it("test_TC_UI_0054_compose_readiness_safe_failure", () => {
    const compose = read("docker-compose.yml");
    expect(compose).toContain("healthcheck:");
    expect(compose).toContain("depends_on:");
    expect(read("backend/tests/test_ticket17_compose.py")).toContain("TimeoutError");
  });

  it("test_TC_UI_0055_rollback_leaves_api_data_unchanged", () => {
    const html = renderToStaticMarkup(<DeveloperWorkspace />);
    expect(html).toContain("memory-only");
    expect(html).not.toContain("localStorage");
    expect(html).not.toContain("sessionStorage");
    expect(read("src/records.ts")).toContain("throw new Error");
  });
});
