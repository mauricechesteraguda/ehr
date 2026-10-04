<!-- type-10042026-Maurice -->
# ADR-006: Use Envoy Gateway for application ingress

- **Status:** Accepted for the reference architecture.
- **Context:** Application ingress needs a Kubernetes-native policy boundary while administration stays private.
- **Decision:** Envoy Gateway is the intended application ingress boundary; cluster, Argo, metrics, dashboards, and data paths remain private.
- **Alternatives:** Cloud-specific ingress per provider; direct service exposure; another gateway controller.
- **Rationale:** A single declarative gateway contract reduces provider-specific exposure assumptions.
- **Consequences:** Gateway lifecycle and provider integration must be tested; it is not a promise of public access.
- **Reconsider when:** protocol, support, or security requirements cannot be met.
- **Exclusions/validation:** No gateway configuration or public hostname is implemented; unvalidated.
