// type-10022026-Maurice: Pure role routing seam keeps navigation testable without browser EHI.
import type { Role } from "./auth";

export function roleWorkspacePath(role: Role): string {
  return role === "developer" ? "/developer" : role === "admin" ? "/admin" : "/";
}
