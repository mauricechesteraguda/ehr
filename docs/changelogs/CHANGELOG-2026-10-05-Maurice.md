# Changelog — 2026-10-05

## CI dependency path correction

- Corrected the platform validation workflow to install from the tracked root `requirements.txt`.
- Added Ticket 07 regression coverage for dependency files resolved against effective workflow working directories.

## CI YAML test dependency

- Declared pinned `PyYAML==6.0.3` in root `requirements.txt` for platform-test collection.
- Added Ticket 08 regression coverage and verified clean dependency installation supports platform-test collection.

## CI PostgreSQL service

- Added an isolated, digest-pinned PostgreSQL 17.2 Alpine service and matching synthetic Django CI environment for Ticket 07 tests.
- Added semantic Ticket 07 workflow regression coverage for service readiness and the intentional absence of Redis.

## Terraform and Helm CI bootstrapping

- Added full-SHA-pinned official setup actions to every Terraform- or Helm-invoking CI job, using the repository contract versions Terraform 1.9.8 and Helm 3.16.4.
- Added semantic regression coverage for setup ordering, unconditional execution, immutable action refs, and exact manifest versions.

## Platform evidence cardinality maintenance

- Updated the existing TC-PLAT-0059 contract for the approved 64-case, 55-requirement canonical evidence matrix.
- Preserved exact columns, unique continuous IDs, nonblank automated references, and blank QA fields for `Not Run` evidence.

## Workflow shell lint cleanliness

- Added discoverable TC-PLAT-0064 coverage for unsafe embedded shell patterns and made the affected workflow blocks actionlint/ShellCheck-clean.

## Scoped Terraform linting

- Added TC-PLAT-0065 coverage for tracked Terraform directory discovery and shared absolute TFLint configuration.
- Scoped CI TFLint to the nine environment roots and three modules, and fixed provider constraints plus the unused AWS declaration for zero findings.

## CI tool path parsing

- Preserved backslashes while reading discovered Terraform directories and added TC-PLAT-0064 coverage for unsafe shell `read` invocations.

## Safe Terraform path parsing

- Corrected the TFLint path-discovery loop to consume NUL-delimited Terraform paths with a token-safe Bash `read` delimiter.
- Extended TC-PLAT-0065 with an offline parser fixture covering nonempty path assignment.

## Scoped Kubernetes manifest validation

- Scoped kubeconform to the checked-in Kubernetes manifest roots and directories, excluding GitOps metadata files.
- Strengthened TC-PLAT-0039 to require the exact 21-file, 33-document manifest set and top-level Kubernetes identity fields.

## Kyverno offline policy gate

- Set `mutateDigest: false` on the Audit-only production signature hook without changing its image references, attestors, or Audit action.
- Added pinned Kyverno v1.15.2 offline positive/negative baseline fixtures and required both policy smoke apply and `kyverno test` in platform CI.
- Signature verification remains a documented Not Run live/registry check.

Author Name: Aguda, Maurice
