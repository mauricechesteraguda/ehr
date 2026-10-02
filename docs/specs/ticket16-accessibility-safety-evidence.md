# Ticket16 — WCAG 2.2 AA quality improvements and prototype safety evidence

## Scope

Ticket16 improves the React shell and its login, patient, clinician, administrator,
and developer panels. It adds semantic landmarks, labelled controls, announced async
states/errors, visible focus, keyboard-safe targets, responsive/reflow styles, and a
reduced-motion policy. Automated axe checks cover representative P1/P2 panel markup.

This is a **prototype quality gate**, not a claim of formal WCAG conformance, ISO/FDA/HIPAA
certification, or clinical validation. Data, identities, and evidence are synthetic and
non-clinical.

## Acceptance boundaries

* Serious or critical axe findings fail automated tests; no rule is disabled.
* Manual keyboard, screen-reader, contrast, and 200% reflow checks remain `Not Run` when
  browser automation is unavailable.
* The evidence manifest is machine-validated for required sections, links, IDs, and
  traceability. It contains no PII, credentials, or clinical claims.

## Required artifacts

| Artifact | Purpose |
| --- | --- |
| `docs/accessibility-conformance-note.md` | Tested surfaces, known exceptions, and manual checklist |
| `docs/hazard-risk-register.md` | Hazard/cause/harm/control/verification/residual-risk register |
| `docs/misuse-cases.md` | Accessibility and prototype safety misuse cases |
| `docs/usability-scenarios-results.md` | Reusable scenario/results record |
| `docs/requirements-traceability.md` | FR to API/UI/test/artifact mapping |
| `docs/contribution-testing-release-checklist.md` | Contributor and release gates |
| `docs/incident-demo-defect-log.md` | Non-production incident/demo defect record |
| `docs/evidence-manifest-ticket16.json` | Machine-readable evidence index |
| `scripts/validate_ticket16_evidence.py` | Deterministic manifest/schema/link validator |
