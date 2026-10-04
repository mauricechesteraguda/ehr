<!-- type-10042026-Maurice -->
# Platform glossary

This glossary is implementation-free and applies only to the synthetic platform reference.

| Term | Meaning in this repository |
| --- | --- |
| Demo profile | Disposable local or kind profile using lower-durability in-cluster dependencies. |
| Managed profile | Intended cloud profile using provider-managed PostgreSQL/Redis and backups. |
| Bootstrap | The bounded process that establishes cluster prerequisites and Argo ownership. |
| Promotion | Making a reviewed application revision active in an environment. |
| Healthy capacity | Existing ready workload capacity retained while a candidate is rejected. |
| Workload identity | Short-lived identity granted to a named workload, namespace, and action set. |
| External Secrets | A controller boundary that materializes only references fetched from an external provider. |
| RPO/RTO | Recovery point/time planning targets; neither is validated by this skeleton. |
| SLO | A proposed service objective requiring measured evidence; not a certification claim. |
| Evidence class | Static, kind, k3s, cloud, or unvalidated classification for an observation. |
