<!-- type-10042026-Maurice -->
# ADR-004: GitOps sync and promotion

- **Status:** Accepted for the reference architecture.
- **Context:** Environment changes need reviewable desired state and a distinct production approval.
- **Decision:** Git is desired state; development and staging may auto-sync after normal gates, while production requires explicit approval. Drift is reported and corrected through Git.
- **Alternatives:** Direct kubectl changes; auto-promote production; manual sync for every environment.
- **Rationale:** Review, provenance, and approval are clearer without weakening lower-environment feedback.
- **Consequences:** Emergency changes need a documented process; drift can remain until reviewed.
- **Reconsider when:** measured recovery or governance requirements demand another promotion control.
- **Exclusions/validation:** No Argo application is implemented or live-tested here.
