<!-- type-10042026-Maurice -->
# Platform context and scope

Ticket02 records the architecture vocabulary needed before implementation tickets add
charts, infrastructure, GitOps applications, policy, and runbooks. It deliberately contains
no executable deployment configuration and makes no cloud, endpoint, clinical, security
certification, or recovery claim.

The platform must preserve the repository's synthetic/non-clinical boundary, default-deny
operational logging, private administration surfaces, append-only application history, and
absence of browser EHI/session persistence. Local Compose remains the current runtime. Kind
is the intended disposable convergence seam; k3s and one selected managed provider are later
validation targets, not current capabilities.

Unknowns to resolve later include provider selection, exact resource sizing, backup tiers,
measured RPO/RTO/SLO values, Infracost inputs, exception review, and operator ownership.
