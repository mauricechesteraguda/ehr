import { describe, expect, it } from "vitest";

describe("test_TC_EXP_0120_direct_delivery_ui", () => {
  it("test_TC_EXP_0120_direct_delivery_ui", async () => {
    const source = await import("fs").then((fs) => fs.readFileSync("src/main.tsx", "utf8"));
    expect(source).toContain("Simulation only:");
    expect(source).toContain("no SMTP, Direct network, or real message is sent");
    expect(source).toContain("C-CDA bytes and recipient addresses are never displayed");
    expect(source).toContain("Cancel");
    expect(source).toContain("Retry");
    expect(source).toContain('aria-label="Direct delivery"');
    expect(source).toContain('name="artifact_id"');
    expect(source).toContain('name="recipient" type="email"');
    expect(source).toContain('name="purpose" minLength={10} maxLength={240}');
    expect(source).toContain("fetchDirectArtifacts(patientId)");
    expect(source).toContain("fetchDirectDeliveries()");
    expect(source).toContain("createDirectDelivery");
    expect(source).toContain("cancelDirectDelivery");
    expect(source).toContain("retryDirectDelivery");
    expect(source).not.toContain("item.recipient");
    expect(source).not.toContain("item.payload");
  });
});
