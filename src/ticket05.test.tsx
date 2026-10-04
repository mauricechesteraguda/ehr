// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { AdminWorkspace, DeveloperWorkspace } from "./main";

const adminProps = { users: [], audit: [], jobs: [], rules: [], severityFloor: "LOW", error: "", onRetry: () => undefined, onCancelJob: () => undefined, onUpdateUser: () => undefined, onCreateUser: () => undefined };

describe("Ticket05 admin and developer workspace redesign", () => {
  it("test_TC_UI_0039_admin_permissions_have_explicit_sections", () => {
    const html = renderToStaticMarkup(<AdminWorkspace {...adminProps} />);
    expect(html).toContain("Users and roles");
    expect(html).toContain("Audit chain");
    expect(html).toContain("Jobs and status");
  });
  it("test_TC_UI_0040_admin_empty_states_are_explicit", () => {
    const html = renderToStaticMarkup(<AdminWorkspace {...adminProps} />);
    expect(html).toContain("No users loaded.");
    expect(html).toContain("No audit events loaded.");
    expect(html).toContain("No background jobs loaded.");
  });
  it("test_TC_UI_0042_admin_tables_are_captioned_and_status_textual", () => {
    const html = renderToStaticMarkup(<AdminWorkspace {...adminProps} />);
    expect(html).toContain("<caption>Users and assigned roles</caption>");
    expect(html).toContain("Minimum alert severity");
    expect(html).toContain("No interaction rules loaded.");
  });
  it("test_TC_UI_0043_developer_warns_about_synthetic_memory_only_boundary", () => {
    const html = renderToStaticMarkup(<DeveloperWorkspace />);
    expect(html).toContain("Demonstration only");
    expect(html).toContain("memory-only");
    expect(html).toContain("Patient selection test panel");
  });
  it("test_TC_UI_0044_developer_consent_fields_are_exact_and_accessible", () => {
    const html = renderToStaticMarkup(<DeveloperWorkspace />);
    expect(html).toContain("Exact HTTPS redirect URI");
    expect(html).toContain("Consent will show the exact requested scopes.");
    expect(html).toContain("Register SMART app");
  });
  it("test_TC_UI_0045_developer_does_not_render_tokens_or_secret_by_default", () => {
    const html = renderToStaticMarkup(<DeveloperWorkspace />);
    expect(html).not.toContain("access_token");
    expect(html).not.toContain("refresh_token");
    expect(html).not.toContain("client_secret");
  });
});
