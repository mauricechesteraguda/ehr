<!-- type-10042026-Maurice -->
# ADR-009: Reusable one-provider Terraform foundations

- **Status:** Accepted for Ticket06 reference implementation.
- **Decision:** Keep AWS, GCP, and Azure modules under `platform/terraform/modules/`, with isolated
  development, staging, and production roots. One root selects one cloud provider per installation.
- **Ownership:** Terraform/OpenTofu owns private cluster infrastructure, managed data/storage,
  registries, secret-store handles, and optional Argo CD/root bootstrap. Argo owns all add-ons,
  application workloads, promotion, and environment values after bootstrap.
- **State:** Use provider-native encrypted/versioned remote state with access control and locking:
  S3 + DynamoDB lock table, GCS object generations, or Azure Blob lease. Backend examples contain
  placeholders only and must be copied outside Git.
- **Security:** Kubernetes APIs, data services, secret stores, registries, Argo, and telemetry
  management remain private. Workload identity is OIDC/federated or managed identity; static cloud
  keys are not accepted by module inputs. Outputs expose handles, never secret payloads.
- **Reliability:** Production uses multi-zone placement, encrypted storage, backups/PITR, and
  deletion protection where supported. RPO15m/RTO4h are planning targets, not measured claims;
  restore tests, regional failure behavior, quotas, and Azure Managed Redis availability require
  provider-specific authorized validation.
- **Validation:** `terraform fmt` and `init -backend=false`/`validate` are offline structural
  gates where the CLI and provider cache permit. No live plan, apply, credentials, or resource
  creation is performed by repository checks.
