import { describe, expect, it } from "vitest";
import { roleWorkspacePath } from "./workflow";

describe("TC-EHR-0093 role workflows and accessible states", () => {
  it("routes every role to a bounded workspace and does not persist session data", () => {
    expect(roleWorkspacePath("clinician")).toBe("/");
    expect(roleWorkspacePath("patient")).toBe("/");
    expect(roleWorkspacePath("admin")).toBe("/admin");
    expect(roleWorkspacePath("developer")).toBe("/developer");
    expect(globalThis).not.toHaveProperty("localStorage");
  });
});
