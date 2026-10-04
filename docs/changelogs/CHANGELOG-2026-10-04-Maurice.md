# Changelog — 2026-10-04

## Documentation

- Added the Ticket 01 Tailwind v4 build-time foundation, self-hosted Outfit weights, local icon dependency, semantic Synthetic EHR tokens, primitive state variants, and a memory-only light-theme seam.

- Added a README screenshot gallery for the current synthetic demo workflows, covering sign-in, clinician medication ordering, administrator audit/quality review, and developer SMART/FHIR navigation.
- Added optimized documentation captures with synthetic labels and masked audit values; the unreliable patient workspace capture was intentionally omitted.

## Ticket 02 — Responsive application shell

- Added typed reusable shell and semantic UI primitives: AppShell, IconRail, Sidebar, TopBar, mobile drawer, breadcrumbs, clinical context ribbon, buttons, form wrappers, cards, badges, async states, and chart fallbacks.
- Added browser back/forward route synchronization and a memory-only dark/light theme toggle; no browser storage is used.
- Preserved existing role workflows, panel text, selectors, API calls, and synthetic-data safety boundaries.
- Added Ticket02 frontend contract coverage for TC-UI-0010..0018 and mapped each case to a RED-first test reference in `docs/test-cases/ehr-tailwind-redesign.csv`.

Author Name: Aguda, Maurice
