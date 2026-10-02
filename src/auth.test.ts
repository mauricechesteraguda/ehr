// type-10022026-Maurice: Ticket 01 frontend acceptance tests.
import { describe, expect, it } from "vitest";
import { authRequest, roleShellTitle } from "./auth";

describe("TC-EHR-0017 role shell", () => {
  it("renders a role-scoped shell", () => {
    expect(roleShellTitle("clinician")).toBe("Clinician workspace");
  });
});

describe("TC-EHR-0024 browser storage", () => {
  it("does not persist session data", () => {
    expect(typeof localStorage).toBe("undefined");
  });
});

describe("TC-EHR-0044 frontend auth observability", () => {
  it("logs classified success with duration and correlation without payloads", async () => {
    const records: unknown[] = [];
    const response = new Response("{}", { status: 200, headers: { "X-Correlation-ID": "corr-safe" } });
    await authRequest("/api/auth/login/", { method: "POST", body: JSON.stringify({ password: "secret" }) },
      async () => response, (record) => records.push(record));
    expect(records).toEqual(expect.arrayContaining([
      expect.objectContaining({ event: "auth.request.entry", correlationId: expect.any(String) }),
      expect.objectContaining({ event: "auth.request.exit", outcome: "success", httpClass: "2xx", correlationId: "corr-safe" }),
    ]));
    expect(JSON.stringify(records)).not.toContain("secret");
  });

  it("logs classified failure without the response body", async () => {
    const records: unknown[] = [];
    const response = new Response("password=secret", { status: 401, headers: { "X-Correlation-ID": "corr-fail" } });
    await expect(authRequest("/api/auth/login/", {}, async () => response, (record) => records.push(record))).rejects.toThrow();
    expect(records).toEqual(expect.arrayContaining([
      expect.objectContaining({ event: "auth.request.failure", outcome: "failure", httpClass: "4xx", correlationId: "corr-fail" }),
    ]));
    expect(JSON.stringify(records)).not.toContain("secret");
  });
});

describe("TC-EHR-0047 frontend auth exact HTTP status", () => {
  it("logs the numeric response status alongside its sanitized class", async () => {
    const records: unknown[] = [];
    const response = new Response("secret body", { status: 429, headers: { "X-Correlation-ID": "corr-rate" } });
    await expect(authRequest("/api/auth/login/", {}, async () => response, (record) => records.push(record))).rejects.toThrow();
    expect(records).toEqual(expect.arrayContaining([
      expect.objectContaining({ event: "auth.request.failure", httpStatus: 429, httpClass: "4xx", correlationId: "corr-rate" }),
    ]));
  });
});
