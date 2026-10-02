import { describe, expect, it, vi } from "vitest";
import { requestPatientExport } from "./records";

describe("TC-EHR-0070 authorized download UI boundary", () => {
  it("TC-EHR-0070 requests the selected format without browser EHI storage", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "safe", status: "ready", format: "pdf", sha256: "a".repeat(64), expires_at: "2026-10-02T00:15:00Z", download_url: "/api/exports/safe/download/" }), { status: 201 }));
    await requestPatientExport("P001", "pdf", fetcher);
    expect(fetcher).toHaveBeenCalledWith("/api/patients/P001/exports/", expect.objectContaining({ body: JSON.stringify({ format: "pdf" }), credentials: "include" }));
    expect(globalThis).not.toHaveProperty("localStorage");
  });
});
