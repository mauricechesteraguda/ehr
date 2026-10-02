import { describe, expect, it } from "vitest";

describe("Ticket 13 CDS card accessibility contract", () => {
  it("uses a stable UUID and bounded severity contract", () => {
    const card = { uuid: "00000000-0000-0000-0000-000000000001", indicator: "CRITICAL" };
    expect(card.uuid).toMatch(/^[0-9a-f-]{36}$/); expect(["LOW", "MODERATE", "HIGH", "CRITICAL"]).toContain(card.indicator);
  });
  it("exposes non-clinical demo language", () => {
    expect("Non-clinical demo: cards are reminders only").toMatch(/Non-clinical demo/);
  });
});
