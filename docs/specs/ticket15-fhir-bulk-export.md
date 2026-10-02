# Ticket15 — FHIR Bulk Data-style export

Bounded synthetic demo only. Authorized administrators or active SMART system tokens
with `system/*.read` may request `application/fhir+ndjson` population exports. `_type`
is an allowlist of implemented FHIR resources; `_since` is optional. Requests require a
purpose, approval reference, and idempotency key. Jobs use the existing DB Job/Outbox
contract, produce no partial manifest, encrypt randomized per-resource files with
AES-GCM, enforce a 100 MB total cap and 24-hour expiry, and recheck authorization and
integrity on every download. Patient selection and break-glass are deliberately absent;
this is not a full SMART Backend Services assertion flow.
