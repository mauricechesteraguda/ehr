<!-- type-10042026-Maurice -->
# ADR-008: Managed cloud data versus demo in-cluster data

- **Status:** Accepted for the reference architecture.
- **Context:** Production durability, backup ownership, and demo convenience have different requirements.
- **Decision:** Managed PostgreSQL and Redis are the production target; demo may use visibly lower-durability in-cluster dependencies and is disposable.
- **Alternatives:** In-cluster data everywhere; managed data in demo; one opaque profile.
- **Rationale:** The distinction makes recovery ownership and limitations explicit and prevents demo durability from being mistaken for production readiness.
- **Consequences:** Two data paths require separate values, tests, warnings, and recovery runbooks.
- **Reconsider when:** demo needs durable recovery or the selected provider cannot meet managed-data needs.
- **Exclusions/validation:** No data service is provisioned here; backup/RPO/RTO behavior remains unvalidated.
