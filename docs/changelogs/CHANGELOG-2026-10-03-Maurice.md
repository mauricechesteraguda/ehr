# Changelog — 2026-10-03

## Correction

- Fixed live Compose startup: non-root Nginx now uses explicit writable pid/temp paths, Celery services configure Django before importing tasks, and Caddy uses valid route-block syntax.
- Bound tracing to the app runtime volume with best-effort writes so readiness remains an explicit 503/200 dependency state rather than becoming a 500 from an unwritable trace home; acceptance seeding no longer exposes the demo password in host command output.

- Restored canonical expansion continuity with TC-EXP-0106..0110 for C-CDA DTD/XXE rejection, entity-expansion rejection, checksum tamper detection, atomic invalid-import rollback, and reconciliation idempotency.
- Added discoverable Ticket 11 acceptance tests for all five cases without changing existing test behavior; reordered the canonical CSV numerically while preserving existing row fields, with blank QA fields and `Not Run` status.

## Evidence

- Canonical CSV validates at 120 unique continuous cases (TC-EXP-0001..0120) and exactly 18 columns per row; the restored cases have requirement mappings and discoverable automation references.
- Ticket 11 coverage passes 8 tests; the backend suite passes 178 tests, frontend tests pass 13 tests, and frontend typecheck/build, Django checks, migration checks, Compose configuration, and whitespace checks pass.

Author Name: Aguda, Maurice

## Ticket 17

- Isolated live Compose acceptance from unrelated host services: Compose now keeps normal demo defaults of 80/443 but accepts configurable host bindings, and the acceptance runner selects/checks free high ports, passes them through its environment, and validates the exported Caddy CA at the selected HTTPS URL.
- Added canonical `TC-EXP-0140..0160` integrated-Compose acceptance cases, each with a discoverable backend test reference.
- Added `scripts/compose_acceptance.py`: isolated project naming, preflight port checks, external generated secrets, BuildKit builds, bounded health waits, local-CA HTTPS validation, idempotent migration/seed, worker restart/persistence probes, structured evidence, and scoped cleanup.
- Expanded the README architecture/demo flow with the one-command acceptance invocation and exact macOS/Linux/Windows CA trust commands.
- Static verification is deterministic. Live Compose results must be recorded as pass or registry/Docker blocker; no live result is claimed by documentation alone.

## Ticket 15

- Added bounded FHIR Bulk Data-style asynchronous export on the unified Job/Outbox system, with allowlisted `_type`, optional `_since`, purpose/approval, idempotency, opaque status location, cancellation, encrypted expiring NDJSON artifacts, checksums, caps, and authorization rechecks.
- Added canonical TC-EXP-0121..0131 acceptance rows, Ticket 15 specification, and an administrator bulk export panel. This remains a synthetic demo and does not implement SMART Backend Services assertions.
- Verified TC-EXP-0121..0131 exactly once with 10 discoverable backend tests and 1 discoverable frontend test; all pass with no skips/placeholders. Full collection reconciles to 188 backend tests (178 prior + 10) and 14 frontend tests (13 prior + 1). Fixed status/cancel route kwargs and tampered AES-GCM download handling discovered RED-first.

## Ticket 16

- Added semantic landmarks/headings, explicit labels/descriptions, live loading/error states,
  visible focus, responsive/reduced-motion styles, and prototype safety boundary text.
- Added pinned `axe-core@4.10.2` Vitest checks and canonical TC-EXP-0132..0139 evidence rows.
- Added accessibility note, hazard/risk register, misuse cases, usability template,
  requirements traceability, contribution/release checklist, demo defect log, and a
  deterministic evidence manifest validator. Manual browser checks are explicitly `Not Run`.
- This remains synthetic, non-clinical prototype evidence with no formal WCAG, ISO/FDA/HIPAA
  certification or clinical validation claim.
