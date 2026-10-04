<!-- type-10042026-Maurice -->
# ADR-003: Terraform/OpenTofu and Argo ownership boundary

- **Status:** Accepted for the reference architecture.
- **Context:** Cluster lifecycle and application reconciliation have different state and approval needs.
- **Decision:** Terraform/OpenTofu owns the cluster and Argo installation; Argo owns application workloads and environment promotion.
- **Alternatives:** Terraform applies workloads; Argo provisions cloud infrastructure; operators apply both directly.
- **Rationale:** The boundary limits state overlap and makes workload changes GitOps-reviewable.
- **Consequences:** Bootstrap ordering and recovery documentation are required; direct workload apply is out of bounds.
- **Reconsider when:** lifecycle tooling gains a tested, safer ownership model.
- **Implementation:** Ticket06 provides reusable EKS/GKE/AKS foundations, encrypted remote-state
  backend examples, and an optional pinned Argo CD Helm bootstrap. The module boundary excludes
  application workloads, add-ons, data payloads, and secret values; cloud plan/apply remains an
  authorized-runner operation.
- **Limitations:** Provider quotas, exact managed-service feature availability, restore duration,
  and provider-specific RPO/RTO behavior require a separately approved cloud validation. Static
  Terraform validation does not prove network reachability or recovery performance.
