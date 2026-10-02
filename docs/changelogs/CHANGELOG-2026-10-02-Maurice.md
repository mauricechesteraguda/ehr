# Changelog — 2026-10-02

## Implemented

- Closed final P0 logging acceptance blockers: seed enrollment is opt-in to a mode-600 file with no secret output, console events are structured JSON, and FHIR/patient/medication/SMART/external-auth/export/rate-limit boundaries emit safe status, duration, outcome, error-class, and database outcome evidence.

- Established the Tickets 01–04 EHR demo foundation with Django/DRF, React/Vite TypeScript, and PostgreSQL configuration.
- Added password authentication with mandatory TOTP enrollment and verification, role-scoped sessions, configurable inactivity expiry, and protected patient access.
- Added synthetic coded demographics and read-only allergy, condition, observation, and device records for the demo patients.
- Added append-only, hash-chained audit events, administrator-only filtering and pagination, and audit-chain verification.
- Added clinician medication draft creation with immutable versions, change, cancel, refill, and history endpoints; medication signing remains unavailable.
- Added structured operational logging with sensitive-field redaction, safe correlation identifiers, and local HTTPS certificate-path configuration.
- Added the README with synthetic-data safeguards, architecture, local setup, demo-user/TOTP instructions, API routes, verification commands, and troubleshooting guidance.
- Included the MVP requirements, migrations, test-case CSV, dependency manifests and lockfile, configuration example, and LICENSE.

## Final integration — Ticket10

- Added an idempotent/resettable synthetic `seed_demo` command with clinician, patient, administrator, and developer accounts, TOTP setup output only at local execution time, synthetic patients/clinical rows/devices/medication/interaction rules, and redacted startup/seed/demo lifecycle logging.
- Integrated the React login shell, role navigation, developer SMART workspace, Vite API proxy, responsive keyboard-visible focus styling, reduced-motion handling, and explicit loading/empty/error/re-authentication states without browser EHI storage.
- Added the dependency-free `scripts/smart_demo.py` sample client for PKCE code exchange, refresh rotation, and bounded FHIR Patient read; documented local HTTPS and the under-ten-minute role walkthrough.
- Added Ticket10 CSV scenarios TC-EHR-0092–TC-EHR-0096 and discoverable backend seam tests for seed idempotency, SMART refresh/FHIR read, HTTPS/disclaimer, role boundaries, and password-required setup.
- Final verification: 74 backend tests passed on disposable PostgreSQL; 7 frontend tests passed; TypeScript lint, Vite production build, Python compile check, CSV 18-column validation, secret/path scan, and `git diff --check` passed. Browser E2E was not added because no browser test dependency/toolchain is installed locally.

## Complete P0 delivery — Tickets05–10

- Ticket05 completed interaction safety and medication signing: immutable evaluations and acknowledgements, LOW/MODERATE/HIGH floors, unsuppressible CRITICAL findings, fail-closed activation, and administrator-only rule management.
- Ticket06 completed authorized JSON/PDF export and patient download flows with exact-byte SHA-256 metadata, fifteen-minute artifact expiry and cleanup, bounded duplicate storage, transient browser state, and rollback on audit failure.
- Ticket07 completed six-resource read-only FHIR R4 access with SMART bearer scope/patient compartment enforcement, safe OperationOutcome failures, content integrity metadata, and bounded diagnostics.
- Ticket08 completed confidential SMART registration, discovery, consent, exact redirect validation, PKCE S256, code replay/expiry handling, refresh rotation/revocation, audit fail-closed behavior, and developer demo client coverage.
- Ticket09 completed administrator role and safety-rule management, self-lockout/last-admin safeguards, audit viewer separation, inactivity enforcement, security headers and request bounds, rate limits, and injection-safe validation.
- Ticket10 completed seeded synthetic demo workflows, the role-based React shell, developer SMART workspace, responsive safe states, dependency-free SMART demo client, and final integration documentation.
- Full P0 evidence is represented by CSV cases TC-EHR-0001–TC-EHR-0106 with exactly 18 columns, continuous identifiers, blank QA result fields, and `Not Run` status pending execution in the target environment. Final evidence includes backend/frontend acceptance results, production/type/compile checks, CSV validation, secret/private-key/certificate/PII/trace/temp/cache/artifact scans, and whitespace validation; no environment secrets or trace files are included.

## Verification

- Backend acceptance suite: 26 tests collected; execution requires a local PostgreSQL role/database configured from `.env`.
- Frontend suite: 5 tests passed.
- Frontend typecheck/lint and production build checks are included in the verification commands and pass for this foundation.
- `git diff --check` completed without whitespace errors.

## Deferred

- Production deployment, real EHI, and deferred P2 capabilities remain out of scope; the local synthetic prototype does not transmit data directly.

## Expansion checkpoint — Tickets01–10

- Added the Docker Compose platform with Caddy local HTTPS, health-checked PostgreSQL/Redis/API/web/worker/Beat services, persistent named volumes, idempotent startup seeding, and the documented preview/confirmed reset flow.
- Completed Tickets02–10: durable jobs and outbox processing; family history; device UDI; questionnaires and terminology; amendments; passkeys and recovery; break-glass access; patient selection; and population export workflows with role, audit, retry, expiry, and synthetic-data safeguards.
- Static Compose/configuration tests, source checks, and local test suites pass; the live Compose image build remains unverified because PyPI connectivity is intermittent.

Author Name: Aguda, Maurice
## Ticket11 — bounded C-CDA transition reconciliation
- Added deterministic, checksum-bound C-CDA generation/import jobs with secure bounded parsing and encrypted artifacts.
- Added immutable document metadata, FHIR-shaped reconciliation candidates, clinician decisions, audit/outbox boundaries, and atomic bounded batches.
- Verification follow-up added canonical acceptance coverage for TC-EXP-0111/0112/0113, fixed secure parser checksum handling and medication mapping, and pinned the defused XML runtime dependency.

## Ticket12 — deterministic Direct-shaped delivery

- Added an authorized clinician/admin, idempotent delivery boundary for bounded C-CDA TransitionDocument artifacts.
- Added a visibly simulated local adapter with deterministic success, transient, timeout, unavailable, and permanent fixtures; it performs no SMTP, Direct network, or real delivery.
- Added payload-free transactional outbox/audit metadata, immutable safe attempts and receipt checksums, fail-closed artifact expiry/missing/checksum handling, lifecycle APIs, and accessible UI status/actions.
- Verification follow-up added executable TC-EXP-0114..0120 coverage for bounded inputs, idempotency, deterministic no-network outcomes, retries/cancellation, missing/tampered artifacts, atomic rollback, and UI lifecycle safeguards.
# Ticket 13 — deterministic CDS Hooks-shaped demo

- Added versioned service discovery, bounded hook invocation, immutable cards/invocation evidence, admin rule lifecycle, and atomic audit/outbox records.
- Added clinician card actions and accessible React UI. All output is explicitly non-clinical and uses redacted evidence links.
- Fixed TC-EXP-1309's accidental skip by adding a deterministic synthetic allergy/medication P0 fixture; the complete CDS acceptance suite now executes without skips.
