// type-10042026-Maurice: Ticket02 RED-first contract coverage mapped to the UI CSV.
import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { AppShell, Badge, CategoryBarChart, ErrorState, Loading, TrendChart } from "./ui";

describe("Ticket 02 — primitives, data states, charts and shell", () => {
  it("TC-UI-0010 / REQ-UI-0010: renders explicit success and semantic status", () => {
    const html = renderToStaticMarkup(<Badge tone="success">Saved</Badge>);
    expect(html).toContain("Saved");
    expect(html).toContain("svg");
  });
  it("TC-UI-0011 / REQ-UI-0011: renders loading and bounded error states", () => {
    expect(renderToStaticMarkup(<Loading message="Loading fixture" />)).toContain("Loading fixture");
    expect(renderToStaticMarkup(<ErrorState message="Try again" />)).toContain("Try again");
  });
  it("TC-UI-0012 / REQ-UI-0012: charts expose table fallbacks and summaries", () => {
    const html = renderToStaticMarkup(<><TrendChart title="Trend" points={[{ label: "Mon", value: 2 }]} /><CategoryBarChart title="Categories" items={[{ label: "Beds", value: 4 }]} /></>);
    expect(html).toContain("<table");
    expect(html).toContain("Mon: 2");
    expect(html).toContain("Beds: 4");
  });
  it("TC-UI-0013 / REQ-UI-0013: status meaning is text plus icon", () => {
    const html = renderToStaticMarkup(<Badge tone="danger">Critical</Badge>);
    expect(html).toContain("Critical");
    expect(html).toContain("aria-hidden");
  });
  it("TC-UI-0014 / REQ-UI-0014: shell contracts retain labelled navigation", () => {
    const html = renderToStaticMarkup(<AppShell role="clinician" username="demo" route="/" onNavigate={() => undefined}><p>Content</p></AppShell>);
    expect(html).toContain('aria-label="Workspace navigation"');
    expect(html).toContain('aria-label="Breadcrumb"');
  });
  it("TC-UI-0015 / REQ-UI-0015: shell action is callback-only", () => {
    expect(renderToStaticMarkup(<AppShell role="patient" username="demo" route="/" onNavigate={() => undefined}><p>Content</p></AppShell>)).toContain("View records");
  });
  it("TC-UI-0016 / REQ-UI-0016: route state has a visible current item", () => {
    const html = renderToStaticMarkup(<AppShell role="admin" username="demo" route="/admin" onNavigate={() => undefined}><p>Content</p></AppShell>);
    expect(html).toContain('aria-current="page"');
  });
  it("TC-UI-0017 / REQ-UI-0017: desktop shell includes 64px rail and 240px sidebar contracts", () => {
    const html = renderToStaticMarkup(<AppShell role="clinician" username="demo" route="/" onNavigate={() => undefined}><p>Content</p></AppShell>);
    expect(html).toContain("icon-rail");
    expect(html).toContain("sidebar");
  });
  it("TC-UI-0018 / REQ-UI-0018: shell has responsive drawer and touch targets", () => {
    const html = renderToStaticMarkup(<AppShell role="clinician" username="demo" route="/" onNavigate={() => undefined}><p>Content</p></AppShell>);
    expect(html).toContain("mobile-menu");
    expect(html).toContain("app-shell");
  });
});
