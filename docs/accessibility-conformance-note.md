# Accessibility conformance note — Ticket16

This note records prototype evidence only. It does **not** claim formal WCAG 2.2 AA
conformance, certification, clinical validation, or suitability for real patient data.

## Automated surfaces

`src/ticket16.test.tsx` checks login, patient selection, clinician card, administrator,
developer, loading/error/empty, and responsive/reduced-motion markers with pinned
`axe-core@4.10.2`. Serious and critical axe violations fail; no axe rule is disabled.

Ticket06 regression coverage is in `src/ticket06.test.tsx` (10 tests). The full frontend run
completed with 15 files and 74 tests passing, including the existing serious/critical axe checks;
`npm run lint`, `npm run build`, `npm run validate:evidence`, and the static Compose contract also
passed. The browser smoke used the current-source Vite server for the login page at 1440x900,
1024x768, and 390x844. No authenticated role-workspace browser capture was claimed because no
disposable PostgreSQL/Redis/Django runtime was available.

## Manual checklist

Browser automation was unavailable in this environment, so these checks are explicitly
`Not Run`, never Pass:

| Check | Status | Evidence/exception |
| --- | --- | --- |
| Keyboard-only traversal and logical focus order | Not Run | Run against login and each role route |
| Visible focus at 200% zoom | Not Run | Confirm focus remains visible |
| Screen reader landmarks, headings, labels, live regions | Not Run | Verify with VoiceOver/NVDA |
| Contrast for text, controls, focus, and status | Not Run | Verify with a contrast analyser |
| 200% zoom/reflow without two-dimensional scrolling | Not Run | Verify at 320 CSS px equivalent |
| Reduced motion preference | Not Run | Verify no essential motion is lost |
| Touch/target size at narrow viewport | Not Run | Verify primary controls remain usable |
| No color-only status meaning | Not Run | Verify text/status labels remain present |

## Known exceptions / follow-up

* Native browser validation bubbles and the WebAuthn ceremony are user-agent controlled
  and require manual testing.
* The large existing role workspace is represented by shared semantic shell markers;
  full interaction testing is still a manual release gate.
* A production accessibility audit and assistive-technology matrix are out of scope for
  this synthetic, non-clinical prototype.
