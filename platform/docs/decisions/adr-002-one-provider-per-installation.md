<!-- type-10042026-Maurice -->
# ADR-002: Select one cloud provider per installation

- **Status:** Accepted for the reference architecture.
- **Context:** EKS, GKE, and AKS have different identity, networking, and managed-data contracts.
- **Decision:** An installation selects exactly one provider; alternatives remain documented, not falsely interchangeable.
- **Alternatives:** Simultaneous multi-cloud; provider-neutral lowest-common-denominator modules; one permanent provider.
- **Rationale:** Explicit provider assumptions are safer to validate and operate than hidden portability claims.
- **Consequences:** Provider-specific paths and migration work remain visible; simultaneous failover is not implied.
- **Reconsider when:** a tested multi-cloud operating model and ownership exist.
- **Exclusions/validation:** No provider is selected or cloud-tested by this ADR; no credentials or endpoints are added.
