<!-- type-10042026-Maurice -->
# ADR-003: Terraform/OpenTofu and Argo ownership boundary

- **Status:** Accepted for the reference architecture.
- **Context:** Cluster lifecycle and application reconciliation have different state and approval needs.
- **Decision:** Terraform/OpenTofu owns the cluster and Argo installation; Argo owns application workloads and environment promotion.
- **Alternatives:** Terraform applies workloads; Argo provisions cloud infrastructure; operators apply both directly.
- **Rationale:** The boundary limits state overlap and makes workload changes GitOps-reviewable.
- **Consequences:** Bootstrap ordering and recovery documentation are required; direct workload apply is out of bounds.
- **Reconsider when:** lifecycle tooling gains a tested, safer ownership model.
- **Exclusions/validation:** No runnable IaC or Argo manifests are included; scope is unvalidated.
