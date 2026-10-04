<!-- type-10042026-Maurice -->
# ADR-001: Keep the platform in one repository

- **Status:** Accepted for the reference architecture.
- **Context:** Application, delivery, policy, infrastructure, evidence, and operator docs need cross-boundary review.
- **Decision:** Keep those contracts in one repository while retaining clear ownership directories.
- **Alternatives:** Separate infrastructure repository; per-service repositories; monorepo with no boundaries.
- **Rationale:** One review can correlate application, infrastructure, policy, and evidence changes without duplicating synthetic safety rules.
- **Consequences:** Centralized review and discoverability; larger change surface and stricter path ownership are required.
- **Reconsider when:** Independent release cadence, access isolation, or repository scale makes the boundary unsafe.
- **Exclusions/validation:** No repository split or CI implementation is included; this is unvalidated operationally.
