<!-- type-10042026-Maurice -->
# ADR-007: Provide two observability profiles

- **Status:** Accepted for the reference architecture.
- **Context:** kind/k3s constraints differ materially from managed production telemetry needs.
- **Decision:** Maintain a lightweight profile with bounded metrics, logs, health, and alerts, and a production profile with configured retention, dashboards, rules, and routing.
- **Alternatives:** One maximal stack everywhere; no telemetry in demo; provider-only telemetry.
- **Rationale:** Required signals remain available without pretending constrained environments have production capacity or retention.
- **Consequences:** Profiles can diverge and must be documented and tested independently.
- **Reconsider when:** measured workload and operator budget invalidate the split.
- **Validation:** Ticket04 supplies bounded demo/cloud retention and private-stack references; retention, SLO, and capacity remain unmeasured.
