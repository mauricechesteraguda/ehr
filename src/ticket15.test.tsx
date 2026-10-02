import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { FHIRBulkExportPanel } from "./main";

describe("Ticket15 FHIR bulk export UI", () => {
  it("test_TC_EXP_0131_exposes_bounded_lifecycle_panel_without_break_glass", () => {
    const html = renderToStaticMarkup(<FHIRBulkExportPanel />);
    expect(html).toContain("FHIR Bulk Data export");
    expect(html).toContain("Authorization is rechecked");
    expect(html).toContain("Start FHIR bulk export");
    expect(html).not.toContain("Emergency break-glass");
  });
});
