# Changelog — 2026-10-03

## Correction

- Restored canonical expansion continuity with TC-EXP-0106..0110 for C-CDA DTD/XXE rejection, entity-expansion rejection, checksum tamper detection, atomic invalid-import rollback, and reconciliation idempotency.
- Added discoverable Ticket 11 acceptance tests for all five cases without changing existing test behavior; reordered the canonical CSV numerically while preserving existing row fields, with blank QA fields and `Not Run` status.

## Evidence

- Canonical CSV validates at 120 unique continuous cases (TC-EXP-0001..0120) and exactly 18 columns per row; the restored cases have requirement mappings and discoverable automation references.
- Ticket 11 coverage passes 8 tests; the backend suite passes 178 tests, frontend tests pass 13 tests, and frontend typecheck/build, Django checks, migration checks, Compose configuration, and whitespace checks pass.

Author Name: Aguda, Maurice

## Ticket 15

- Added bounded FHIR Bulk Data-style asynchronous export on the unified Job/Outbox system, with allowlisted `_type`, optional `_since`, purpose/approval, idempotency, opaque status location, cancellation, encrypted expiring NDJSON artifacts, checksums, caps, and authorization rechecks.
- Added canonical TC-EXP-0121..0131 acceptance rows, Ticket 15 specification, and an administrator bulk export panel. This remains a synthetic demo and does not implement SMART Backend Services assertions.
- Verified TC-EXP-0121..0131 exactly once with 10 discoverable backend tests and 1 discoverable frontend test; all pass with no skips/placeholders. Full collection reconciles to 188 backend tests (178 prior + 10) and 14 frontend tests (13 prior + 1). Fixed status/cancel route kwargs and tampered AES-GCM download handling discovered RED-first.
