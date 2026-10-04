<!-- type-10042026-Maurice -->
# ADR-005: External Secrets with workload identity

- **Status:** Accepted for the reference architecture.
- **Context:** Secret values must not enter Git, images, rendered evidence, or long-lived workload credentials.
- **Decision:** External Secrets fetches named references using short-lived least-privilege workload identity.
- **Alternatives:** Sealed values committed to Git; static cloud keys; manual secret injection.
- **Rationale:** The boundary keeps values external and ties access to workload, namespace, and action.
- **Consequences:** Provider availability is a runtime dependency and failure states need safe classification.
- **Reconsider when:** a provider cannot offer the required identity and audit controls.
- **Exclusions/validation:** No provider, secret name, credential, or secret value is specified; unvalidated.
