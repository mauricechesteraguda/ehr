# EHR Prototype: MVP Product Requirements Document

**Repo:** `mauricechesteraguda/ehr`

| | |
|---|---|
| **Owner** | AGUDATECH IT Solutions |
| **Status** | Draft v0.1 |
| **Repo** | `mauricechesteraguda/ehr` |
| **Type** | Public demo prototype |


> **Disclaimer:** This is a prototype for demonstration. It is **not** certified, **not** clinically validated, and must **never** hold real patient data. Use synthetic data only (e.g., Synthea).

---

## 1. Overview

### 1.1 Problem
Electronic health record (EHR) requirements are large and interdependent. A reviewer cannot judge a team's grasp of them from a document alone. A small working slice makes the design, security posture, and standards awareness visible.

### 1.2 Product Vision
A browser-based EHR that lets a clinician order medications safely, lets a patient see their own record, and exposes the data through a standards-based FHIR R4 API, all with a tamper-resistant audit trail.

### 1.3 MVP Goal
Deliver one end-to-end clinical workflow, secured and audited, with a working FHIR API, in a form that can be run from a GitHub repo in a few commands.

### 1.4 Non-Goals (MVP)
- Formal certification or conformance testing
- Real patient data or production deployment
- Billing, scheduling, or lab/imaging integrations
- Full C-CDA, QRDA, and CQM support
- Mobile apps

---

## 2. Users

| Persona | Needs |
|---|---|
| **Clinician** | Find a patient, review their record, place and manage medication orders, and see interaction alerts. |
| **Patient** | Log in securely, view and download their own record. |
| **Administrator** | Manage users and roles, tune alert thresholds, and review audit logs. |
| **Third-party developer** | Register an app and read patient data through the FHIR API. |

---

## 3. MVP Scope

Priority key: **P0** = must ship in MVP, **P1** = ship if time allows, **P2** = post-MVP.

| FR | Capability | Priority | MVP treatment |
|---|---|---|---|
| FR-01 | CPOE: Medications | P0 | Full: create, change, cancel, refill |
| FR-02 | Drug-Drug / Drug-Allergy Checks | P0 | Small seeded interaction table; admin-adjustable severity threshold |
| FR-03 | Demographics | P0 | All listed fields, using standard value sets |
| FR-04 | Family Health History | P1 | Record and update with SNOMED CT codes (small code subset) |
| FR-05 | Implantable Device List | P1 | Record/change/view; UDI parsing for a sample of UDI formats |
| FR-06 | Transitions of Care | P2 | Deferred |
| FR-07 | Clinical Information Reconciliation | P2 | Deferred (depends on FR-06) |
| FR-08 | EHI Export | P0 | Single-patient export, JSON plus data dictionary; population export P1 |
| FR-09 | Direct Project | P2 | Deferred |
| FR-10 | Decision Support Interventions | P2 | Deferred |
| FR-11 to FR-13 | CQMs (record/export, import/calculate, report) | P2 | Deferred |
| FR-14 | View, Download, Transmit | P0 | View and download only; transmit via download. Direct transmission deferred |
| FR-15 | Patient Health Information Capture | P1 | Questionnaire submission with clinician review queue |
| FR-16 | Amendments | P1 | Request and accept/deny/append/notify workflow |
| FR-17 | Application Access: Patient Selection | P1 | Patient lookup endpoint |
| FR-18 | Application Access: Bulk Export | P2 | Deferred |
| FR-19 | Standardized API | P0 | FHIR R4 read/search for a core resource subset, SMART-on-FHIR app registration, OAuth 2.0 |
| FR-20 | Accessibility-Centered Design | P1 | WCAG 2.0 AA checks on core screens, with a short conformance note |
| FR-21 | C-CDA Creation Performance | P2 | Deferred |
| FR-22 | Safety-Enhanced Design | P2 | Deferred; basic usability testing notes only |
| FR-23 | Authentication, Access Control, Authorization | P0 | Role-based access (clinician, patient, admin) |
| FR-24 | Multi-Factor Authentication | P0 | TOTP; WebAuthn P1; SMS fallback P2 |
| FR-25 | Encrypt Authentication Credentials | P0 | Salted one-way hash with a modern work factor |
| FR-26 | Automatic Log-off | P0 | Configurable inactivity timeout |
| FR-27 | Emergency Access | P1 | Break-glass with required justification |
| FR-28 | Auditable Events and Tamper-Resistance | P0 | Append-only log with hash chaining; admins cannot disable |
| FR-29 | Auditing Actions on Health Information | P0 | Create, read, update, delete, print, export |
| FR-30 | Audit Reports | P0 | Filterable, sortable audit report view |
| FR-31 | End-User Device Encryption | P0 | No EHI persisted to the browser by default |
| FR-32 | Integrity | P0 | SHA-2 hash on each export/transmission |
| FR-33 | Trusted Connection | P0 | TLS 1.2+ everywhere |
| FR-34 | Quality Management System | P2 | Deferred; lightweight contributing and testing guide only |

---

## 4. Core User Flows

1. **Clinician places an order.** Log in with MFA, search for a patient, open the record, create a medication order, review any interaction alert, then sign the order. The system records the action in the audit log.
2. **Patient reviews their record.** Log in with MFA, view demographics, medications, allergies, and problems, then download a copy.
3. **Administrator reviews activity.** Log in, open the audit report, filter by user, patient, action, or date, and sort the results.
4. **Developer reads data via API.** Register an app, complete the OAuth 2.0 / SMART flow, then call FHIR read and search endpoints.
5. **Emergency access (P1).** A user requests break-glass access, enters a justification, and gets time-limited access that is flagged in the audit log.

---

## 5. MVP Functional Requirements

Each item lists acceptance criteria. IDs match the full requirements document.

### 5.1 Clinical

**FR-01 CPOE: Medications (P0)**
- A clinician can create, change, cancel, and refill a medication order.
- Required order fields are validated and stored on the patient record.
- Changes keep prior versions visible in history.

**FR-02 Interaction Checks (P0)**
- On order entry, the system checks the active medication list and the allergy/intolerance list.
- Alerts appear to the ordering clinician before the order is signed.
- An administrator can change the severity threshold within a defined allowed range.

**FR-03 Demographics (P0)**
- Race, ethnicity, preferred language, sex, sexual orientation, gender identity, date of birth, and date of death can be recorded and edited.
- Fields use standard coded value sets, not free text, where a value set is required.

**FR-04 Family Health History (P1)**
- Family history entries use SNOMED CT problem codes and can be added and updated.

**FR-05 Implantable Device List (P1)**
- Devices can be added, changed, and viewed.
- A UDI is parsed into its GUDID data elements on entry.

### 5.2 Data Access and Exchange

**FR-08 EHI Export (P0)**
- An authorized user can run an export for a single patient.
- Output is machine-readable (JSON) and ships with a data dictionary.
- P1: scheduled, time-limited, and all-patient exports; the export API.

**FR-14 View, Download (P0)**
- A patient can view their record and download it in a human-readable form and a machine-readable form.
- Transmission to a third party is by download in the MVP.

**FR-15 Patient Health Information Capture (P1)**
- A patient can submit questionnaire responses, which land in a clinician review queue.

**FR-16 Amendments (P1)**
- A patient can request an amendment.
- A clinician can accept, deny, append, or notify, and each outcome is tracked.

**FR-17 Patient Selection API (P1)**
- A registered app can submit the required parameters and receive a unique patient identifier for a single patient.

**FR-19 Standardized FHIR API (P0)**
- FHIR R4 read and search for: `Patient`, `MedicationRequest`, `AllergyIntolerance`, `Condition`, `Observation`, `Device`.
- SMART-on-FHIR app registration, OAuth 2.0 authorization, refresh tokens, and both standalone and EHR launch.
- App registration is free and self-service through a developer portal page.

### 5.3 Security and Audit

**FR-23 Authentication and Access Control (P0)**
- Identity is verified before any access.
- Roles (clinician, patient, administrator) limit which data and functions each user can reach.
- A patient can only see their own record.

**FR-24 Multi-Factor Authentication (P0)**
- TOTP is required for all roles.
- P1: WebAuthn/FIDO2. P2: SMS fallback.

**FR-25 Credential Protection (P0)**
- Credentials are stored only as salted one-way hashes with a work factor aligned to current NIST guidance.

**FR-26 Automatic Log-off (P0)**
- Sessions end after a configurable idle period and require re-authentication.

**FR-27 Emergency Access (P1)**
- A defined set of users can use break-glass access.
- A justification is required and the event is fully audited.

**FR-28 Auditable Events and Tamper-Resistance (P0)**
- Auditable events are written to an append-only log.
- Each entry includes a hash of the previous entry, and an integrity-check command or page verifies the chain.
- No role, including administrator, can disable logging.

**FR-29 Action Auditing (P0)**
- Each record access logs the action (create, read, update, delete, print, export), acting user, timestamp, patient, and resource.

**FR-30 Audit Reports (P0)**
- An administrator can filter and sort audit events by user, patient, action, resource, and date.

**FR-31 End-User Device Encryption (P0)**
- No EHI is persisted in browser storage by default.
- If local storage is ever enabled, it must be encrypted.

**FR-32 Integrity (P0)**
- Each export and API transmission carries a SHA-256 (or stronger) hash for verification.

**FR-33 Trusted Connection (P0)**
- All traffic uses TLS 1.2 or higher.

### 5.4 Design and Quality

**FR-20 Accessibility (P1)**
- Core screens pass automated WCAG 2.0 AA checks, with a short written conformance note in the repo.

**FR-22 / FR-34 (P2)**
- Basic usability notes and a contributing/testing guide are included. Formal processes are deferred.

---

## 6. Non-Functional Requirements

| Area | Requirement |
|---|---|
| **Security** | Secrets are kept out of the repo. Dependencies are scanned. Least-privilege database roles. |
| **Privacy** | Synthetic data only. A prominent notice in the README and the UI. |
| **Performance** | Typical page and FHIR read responses under 500 ms on the demo dataset. |
| **Availability** | Single-instance demo; no high-availability target. |
| **Portability** | Runs locally with one command (e.g., Docker Compose). |
| **Observability** | Structured application logs, kept separate from the audit log. |
| **Testing** | Unit tests for access control, audit chaining, and interaction checks; API tests for FHIR endpoints. |
| **Documentation** | README with setup, a demo walkthrough, and an architecture diagram. |

---

## 7. Data Model (Core Entities)

- **User** (role, MFA secret, credential hash)
- **Patient** (demographics fields from FR-03)
- **MedicationOrder** (patient, drug, dose, route, frequency, status, version history)
- **Allergy**, **Problem**, **FamilyHistory**, **ImplantableDevice**
- **InteractionRule** (drug pair or drug-allergy, severity)
- **AuditEvent** (user, action, patient, resource, timestamp, previous hash, hash)
- **AppRegistration** (client ID, redirect URIs, scopes)
- **AmendmentRequest** and **QuestionnaireSubmission** (P1)

---

## 8. Suggested Architecture

| Layer | Suggestion |
|---|---|
| **Frontend** | React single-page app |
| **Backend** | Python (Django), with REST for the app and FHIR R4 for external access |
| **Database** | PostgreSQL |
| **Auth** | OAuth 2.0 / OpenID Connect with TOTP |
| **FHIR** | A FHIR facade over the app's own data model, or an off-the-shelf FHIR server if time is short |
| **Packaging** | Docker Compose |
| **Seed data** | Synthea-generated synthetic patients |

These are proposals and can change as the build progresses.

---

## 9. Milestones

| Phase | Focus | Outcome |
|---|---|---|
| **M1: Foundation** | Repo, database, auth, roles, MFA, session timeout | Secure login works |
| **M2: Audit** | Append-only chained audit log and report page | Every action is traceable |
| **M3: Clinical core** | Demographics, allergies, problems, medication orders, interaction checks | Clinician workflow works end to end |
| **M4: Patient and export** | Patient portal view/download, single-patient EHI export | Patient workflow works |
| **M5: FHIR API** | FHIR read/search subset, OAuth/SMART, developer portal | External app can read data |
| **M6: Polish** | P1 items, accessibility checks, docs, demo script | Demo-ready repo |

---

## 10. Success Metrics

- A new user can clone, run, and log in within 10 minutes using the README.
- The clinician flow (login, order, alert, sign) can be demoed in under 5 minutes.
- All P0 requirements have passing automated tests.
- The audit-chain verification detects a deliberately altered log entry.
- A sample third-party app can complete the OAuth flow and read a `Patient` resource.

---

## 11. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Scope is too large for a prototype | Hold to the P0 list and defer P2 items firmly. |
| Reviewers mistake the demo for a certified product | Disclaimer in README and UI; synthetic data only. |
| FHIR and SMART details take longer than expected | Use an existing FHIR library or server for the facade. |
| Interaction checking is clinically shallow | Label it as a demonstration rule set, not clinical content. |
| Accidental real data in the repo | Seed only generated data; add a pre-commit check. |

---

## 12. Open Questions

1. Should the FHIR layer be custom, or built on an existing FHIR server?
2. Which standard value sets and code subsets (SNOMED CT, UDI samples) can be used freely in a public repo?
3. Is a hosted demo needed, or is run-it-locally enough?
4. Should WebAuthn move into the P0 list?
5. Which license suits the repo?

---

## 13. Out of Scope for MVP (Deferred Requirements)

FR-06 Transitions of Care, FR-07 Reconciliation, FR-09 Direct Project, FR-10 Decision Support Interventions, FR-11 to FR-13 CQMs, FR-18 Bulk Export, FR-21 C-CDA Creation Performance, FR-22 Safety-Enhanced Design (formal), FR-34 Quality Management System.
