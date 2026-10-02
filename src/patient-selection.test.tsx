// @vitest-environment jsdom
/** @trace TC-EXP-0099; trailmap: Ticket 09 frontend selection panel states. */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it, vi } from "vitest";
import { PatientSelectionPanel } from "./main";
import { selectPatient } from "./records";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

vi.mock("./records", async () => ({
  ...(await vi.importActual<typeof import("./records")>("./records")),
  selectPatient: vi.fn(),
}));

describe("Ticket 09 patient selection panel", () => {
  it("test_TC_EXP_0099_panel_states", async () => {
    // Safe test logging only; no submitted demographics or token material is emitted.
    console.info("ticket09 frontend panel state coverage");
    const host = document.createElement("div");
    document.body.appendChild(host);
    const root = createRoot(host);
    let resolveSelection!: (value: { patient_id: string; request_id: string }) => void;
    vi.mocked(selectPatient).mockReturnValueOnce(new Promise((resolve) => { resolveSelection = resolve; }));

    await act(async () => root.render(<PatientSelectionPanel />));
    expect(host.textContent).toContain("synthetic fixture values only");
    const form = host.querySelector("form")!;
    const identifier = host.querySelector("input[name='identifier']") as HTMLInputElement;
    const birthDate = host.querySelector("input[name='birth_date']") as HTMLInputElement;
    identifier.value = "P001";
    birthDate.value = "1988-02-03";
    await act(async () => form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
    expect(host.textContent).toContain("Selection in progress");
    await act(async () => {
      resolveSelection({ patient_id: "opaque-patient", request_id: "request-1" });
      await new Promise<void>((resolve) => setTimeout(resolve, 0));
    });
    expect(host.textContent).toContain("Selection succeeded");
    expect(host.textContent).not.toContain("P001");
    await act(async () => root.unmount());
    host.remove();
  });
});
