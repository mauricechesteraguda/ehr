# Prototype hazard/risk register — Ticket16

| ID | Hazard | Cause | Harm | Controls | Verification | Residual risk |
| --- | --- | --- | --- | --- | --- | --- |
| H-016-01 | User misses an actionable error | Error is color-only or not announced | Wrong/incomplete workflow | `role=alert`, text errors, focus-visible styles | axe + manual checklist | User-agent/AT differences remain |
| H-016-02 | Keyboard user cannot operate a panel | Non-semantic control or poor focus order | Abandoned or incorrect action | Native buttons/labels, landmarks, target sizing | axe + keyboard scenario | Full AT test pending |
| H-016-03 | Prototype output mistaken for clinical advice | Demo card/status lacks boundary | Unsafe clinical decision | Synthetic/non-clinical warnings and evidence note | Manifest + misuse case | Human misinterpretation possible |
| H-016-04 | Async state is acted on twice | Loading state is silent or control remains active | Duplicate request or stale action | Disabled busy controls and live status | Vitest state markers | Network races remain bounded server-side |
| H-016-05 | Narrow/zoomed layout hides content | Fixed-width or motion-only presentation | Missed data/action | Fluid layout, overflow-safe tables, reflow CSS | axe markers + manual reflow gate | Manual 200% check pending |

Residual risks are accepted only for this local synthetic prototype; they are not a
clinical risk assessment or certification record.
