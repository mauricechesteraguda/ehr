# Ticket16 misuse cases

| ID | Misuse case | Expected boundary/control | Verification |
| --- | --- | --- | --- |
| MC-016-01 | User treats a demo CDS card as a treatment instruction | Persistent non-clinical warning; card cannot silently mutate chart | `src/ticket16.test.tsx`, accessibility note |
| MC-016-02 | User submits real patient/credential data | Login and shell state synthetic-only warning; no browser persistence | README, manual checklist |
| MC-016-03 | User activates an action using only color | Status has text and semantic live/error roles | axe checks, H-016-01 |
| MC-016-04 | User navigates with keyboard only | Native controls and visible focus preserve order | Manual checklist `Not Run` |
