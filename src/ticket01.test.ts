// type-10042026-Maurice: Ticket 01 contract coverage mapped to ehr-tailwind-redesign.csv.
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const styles = () => readFileSync(resolve(root, "src/styles.css"), "utf8");
const packageJson = () => JSON.parse(readFileSync(resolve(root, "package.json"), "utf8")) as { dependencies: Record<string, string>; devDependencies: Record<string, string> };

describe("Ticket 01 — Tailwind, Outfit, icon integration and production build", () => {
  it("TC-UI-0001 / REQ-UI-0001: pins the local design dependencies", () => {
    const dependencies = { ...packageJson().dependencies, ...packageJson().devDependencies };
    expect(dependencies.tailwindcss).toBe("4.3.3");
    expect(dependencies["@tailwindcss/vite"]).toBe("4.3.3");
    expect(dependencies["lucide-react"]).toBe("1.51.0");
    expect(dependencies["@fontsource/outfit"]).toBe("5.3.0");
  });

  it("TC-UI-0002 / REQ-UI-0002: exposes the authoritative Synthetic EHR token contract", () => {
    const source = styles();
    for (const token of ["#7C3AED", "#6D28D9", "#A78BFA", "#A855F7", "#10B981", "#F59E0B", "#0EA5E9", "#EF4444", "#0F0E1A", "#181727", "#F5F3FF", "#FFFFFF", "#4F46E5", "Outfit"]) expect(source).toContain(token);
    expect(source).toContain("--spacing: 4px");
    expect(source).toContain("--radius-lg: 20px");
  });

  it("TC-UI-0003 / REQ-UI-0003: contains no runtime CDN asset", () => {
    expect(styles()).not.toMatch(/https?:\/\//);
    expect(readFileSync(resolve(root, "vite.config.ts"), "utf8")).not.toMatch(/cdn|unpkg|jsdelivr/i);
  });

  it("TC-UI-0004 / REQ-UI-0004: configures Tailwind as a Vite build plugin", () => {
    const config = readFileSync(resolve(root, "vite.config.ts"), "utf8");
    expect(config).toContain("@tailwindcss/vite");
    expect(config).toContain("tailwindcss()");
  });

  it("TC-UI-0005 / REQ-UI-0005: defines reusable primitive variants", () => {
    expect(styles()).toMatch(/\.ui-(button|card|input|badge)/);
  });

  it("TC-UI-0006 / REQ-UI-0006: defines loading, empty, error, and no-results states", () => {
    expect(styles()).toMatch(/\.ui-state--(loading|empty|error|no-results)/);
  });

  it("TC-UI-0007 / REQ-UI-0007: preserves interaction and accessibility states", () => {
    const source = styles();
    expect(source).toContain(":focus-visible");
    expect(source).toContain("min-height: 2.75rem");
    expect(source).toContain("prefers-reduced-motion");
  });

  it("TC-UI-0008 / REQ-UI-0008: keeps tokens centralized", () => {
    const source = styles();
    expect(source).toContain("@theme");
    expect(source.match(/@theme\s*\{[\s\S]*?\}/)?.[0]).toContain("--color-primary: #7C3AED");
  });

  it("TC-UI-0009 / REQ-UI-0009: keeps a safe memory-only light-theme seam", () => {
    const source = styles();
    expect(source).toContain("[data-theme=light]");
    expect(source).toContain(".theme-light");
    expect(source).not.toMatch(/localStorage|sessionStorage/);
  });
});
