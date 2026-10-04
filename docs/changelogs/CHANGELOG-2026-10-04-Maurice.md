# Changelog — 2026-10-04

## Documentation

- Added the Ticket 01 Tailwind v4 build-time foundation, self-hosted Outfit weights, local icon dependency, semantic Synthetic EHR tokens, primitive state variants, and a memory-only light-theme seam.

- Added a README screenshot gallery for the current synthetic demo workflows, covering sign-in, clinician medication ordering, administrator audit/quality review, patient record/questionnaire review, clinician medication ordering, administrator audit/quality review, and developer SMART/FHIR navigation.
- Replaced optimized role documentation captures with current Tailwind UI at 1440x900, including a reliable populated synthetic patient workspace; synthetic labels and masked audit values remain in evidence.
- Recaptured the seven README gallery images in the optional light presentation mode; the application remains dark-first by default and no production theme behavior was changed.

## Ticket 02 — Responsive application shell

- Added typed reusable shell and semantic UI primitives: AppShell, IconRail, Sidebar, TopBar, mobile drawer, breadcrumbs, clinical context ribbon, buttons, form wrappers, cards, badges, async states, and chart fallbacks.
- Added browser back/forward route synchronization and a memory-only dark/light theme toggle; no browser storage is used.
- Preserved existing role workflows, panel text, selectors, API calls, and synthetic-data safety boundaries.
- Added Ticket02 frontend contract coverage for TC-UI-0010..0018 and mapped each case to a RED-first test reference in `docs/test-cases/ehr-tailwind-redesign.csv`.

## Ticket 03 — Authentication and patient workspace redesign

- Added the responsive violet/dark authentication composition with synthetic-data notice, step/status guidance, TOTP and passkey states, recovery messaging, and memory-only access language while preserving existing form selectors and API behavior.
- Reframed the patient workspace with patient context, record tabs, responsive summary cards, clinical action surfaces, safe empty/error/status text, and mobile-friendly record navigation.
- Added RED-first coverage for TC-UI-0019..0027 in `src/ticket03.test.tsx` and mapped every Ticket03 CSV row to its test reference.

## Ticket 04 — Clinician workflow redesign

- Reorganized the clinician record view into responsive patient context, safety, action, queue, history, exchange, and review surfaces while preserving API calls, selectors, immutable-history behavior, and synthetic-data boundaries.
- Added explicit severity text/icons, critical-action treatment, emergency break-glass direction, mobile-safe forms/tables, and directional empty/error states.
- Added RED-first coverage for TC-UI-0028..0036 in `src/ticket04.test.tsx` and mapped every Ticket04 CSV row to its test reference.

## Ticket 06 — Existing flows, evidence, Compose and static serving

- Added ten executable regression/evidence tests for TC-UI-0046..0055 in `src/ticket06.test.tsx` and mapped each CSV row after the tests passed.
- Refreshed the README screenshot gallery with viewport metadata and current-source responsive sign-in captures at 1440x900, 1024x768, and 390x844; authenticated role captures remain explicitly omitted without a disposable backend.
- Recorded automated frontend, axe, static Compose, build, lint, and evidence results without claiming formal accessibility conformance or clinical validation.

## Ticket 08 — Documentation and current application regression

- Completed the operator DevSecOps README with evidence classification, dated planning cost ranges,
  Infracost authority, current application metrics limitation, and runbook links.
- Added discoverable documentation, URL-boundary, regression, and acceptance-evidence contract tests;
  mapped all Ticket08 platform cases without claiming kind or cloud deployment.
- Added local kind, k3s, cloud state/bootstrap, Argo recovery, rollback, backup/restore, secret,
  incident, certificate/DNS, monitoring, upgrade, and teardown safeguards.

Author Name: Aguda, Maurice
