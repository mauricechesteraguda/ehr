import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { MeasureCatalogPanel } from "./main";

describe("Ticket14 quality-measure UI", () => {
  it("test_T14_UI_catalog_discloses_published_counts_only", () => {
    const html = renderToStaticMarkup(<MeasureCatalogPanel />);
    expect(html).toContain("Clinical quality measures");
    expect(html).toContain("Reports show counts only");
    expect(html).not.toContain("patient_id");
  });
});
