# Changelog — 2026-10-02

## Implemented

- Established the Tickets 01–04 EHR demo foundation with Django/DRF, React/Vite TypeScript, and PostgreSQL configuration.
- Added password authentication with mandatory TOTP enrollment and verification, role-scoped sessions, configurable inactivity expiry, and protected patient access.
- Added synthetic coded demographics and read-only allergy, condition, observation, and device records for the demo patients.
- Added append-only, hash-chained audit events, administrator-only filtering and pagination, and audit-chain verification.
- Added clinician medication draft creation with immutable versions, change, cancel, refill, and history endpoints; medication signing remains unavailable.
- Added structured operational logging with sensitive-field redaction, safe correlation identifiers, and local HTTPS certificate-path configuration.
- Added the README with synthetic-data safeguards, architecture, local setup, demo-user/TOTP instructions, API routes, verification commands, and troubleshooting guidance.
- Included the MVP requirements, migrations, test-case CSV, dependency manifests and lockfile, configuration example, and LICENSE.

## Verification

- Backend acceptance suite: 26 tests collected; execution requires a local PostgreSQL role/database configured from `.env`.
- Frontend suite: 5 tests passed.
- Frontend typecheck/lint and production build checks are included in the verification commands and pass for this foundation.
- `git diff --check` completed without whitespace errors.

## Deferred

- Interaction evaluation and medication signing (Ticket 05), FHIR, SMART on FHIR, exports, Docker Compose, repository seeding, and a built-in demo account remain deferred.
- The React client still lacks a login/enrollment screen and a Vite `/api` proxy; direct transmission is not included.

Author Name: Aguda, Maurice
