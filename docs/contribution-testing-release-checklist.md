# Contribution, testing, and release checklist — Ticket16

- [ ] Use synthetic/non-clinical data only; never commit PII, secrets, tokens, or traces.
- [ ] Add a specification row before adding a test row; preserve canonical continuous IDs.
- [ ] Run `npm test -- --run`, `npm run lint`, `npm run build`, and `npm run validate:evidence`.
- [ ] Run backend full suite (>188 tests, no skips) and Django checks/migration checks.
- [ ] Run Compose config validation and inspect generated artifacts for secrets/PII.
- [ ] Run keyboard, screen-reader, contrast, 200% reflow, reduced-motion, target-size,
      and color-independent status checks; record unavailable browser checks as `Not Run`.
- [ ] Review hazard residual risk and known exceptions; do not claim WCAG/ISO/FDA/HIPAA
      certification or clinical validation.
- [ ] Confirm only Ticket16 files are staged and release evidence links resolve.
