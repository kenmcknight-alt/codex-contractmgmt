# Lightweight Contract Management System

## Purpose
This document translates the provided business requirements into an enterprise-ready, lightweight contract management solution that follows common application development best practices while avoiding CLM overreach.

## Guiding Principles
- **Single source of truth** for contract data and documents.
- **Accountability by design** through ownership, auditability, and approval flows.
- **Minimal operational overhead** with streamlined workflows and role-based access control.
- **Human-validated AI** with explicit provenance and immutable audit trails.
- **Rapid time-to-value** via modular architecture and iterative delivery.

## Business Objectives Alignment
- **Governance & auditability**: immutable audit trail, approvals, and exportable logs.
- **Visibility & accountability**: ownership, renewal notifications, and executive reporting.
- **User-friendly**: simple workflows, minimal steps, and intuitive UI.
- **Regulatory readiness**: retention policies, read-only archives, and access restrictions.

## Users & Roles
| Role | Core Responsibilities | Key Permissions |
| --- | --- | --- |
| IT Admin | User/role management, configuration, audit exports | Full system access, data export |
| Business Admin | Vendor/contract management, reporting | CRUD on vendors/contracts, reporting |
| Contract Owner | Lifecycle decisions, renewals | Own contracts, renew/terminate actions |
| Reviewer | Validates AI-extracted data | Approve/override extracted fields |

## Domain Model (High-Level)
**Entities**
- **Contract**: state, owner, vendor, effective/termination dates, notice period, renewal intent.
- **Vendor**: master data, risk profile, relationship status.
- **Document**: versioned storage, metadata, relationship to contract.
- **Tag**: flexible classification, non-mandatory taxonomy.
- **Audit Event**: immutable log of actions, actor, timestamp.
- **Extraction Record**: AI output + validation status + approver.
- **Notification**: due dates, delivery status.

**Relationships**
- One **Contract** → one **Vendor** and one **Owner**.
- One **Vendor** → many **Contracts**.
- One **Contract** → many **Documents** and many **Tags**.

## Lifecycle States
- **Draft** → **Active** → **Expiring** → **Terminated** → **Archived**
- State transitions are audited and require role-specific permissions.

## Core Capabilities
### 1) Contract Lifecycle Management
- Single contract owner with explicit accountability.
- Workflow for creation, approval, and lifecycle updates.
- Renewal intent capture with rationale.

### 2) Vendor Management
- Central vendor repository with visibility into contract exposure.
- Vendor-level roll-ups for renewals and obligations.

### 3) Document Management
- Secure upload of contract and supporting documents.
- Versioned storage with immutable history and metadata.
- Document hashes for integrity checks.

### 4) AI Extraction & Validation
- AI extracts key fields (dates, price, terms, renewal notices).
- **Human validation required** before becoming authoritative.
- Data provenance: each field indicates **AI-extracted vs. human-verified**.

### 5) Tagging & Classification
- Flexible tags; no forced taxonomy in MVP.
- Filtering by tags for reporting and renewals.

### 6) Access Control & Confidentiality
- Role-based access control (RBAC).
- Ownership-based access and explicit sharing.
- Sensitive contract restrictions.

### 7) Notifications & Renewal Awareness
- Default alert at **6 months** prior to notice deadlines.
- Configurable reminders and escalation rules.

### 8) Reporting & Executive Oversight
- 5-year horizon executive report.
- Timeline visualization for renewals/expirations.
- Professional formatting with title page and footers.

### 9) Auditability & Governance
- Immutable audit trail of all key actions and state changes.
- Search and export capability for audits.

### 10) Records Management
- Configurable retention policies.
- Read-only archived contracts remain discoverable.

## Proposed Architecture (Enterprise Patterns)
### 1) Application Layers
- **Presentation Layer**: Web UI (React/Next.js or similar), responsive and accessible.
- **API Layer**: REST/GraphQL service (Node.js, Python, or Java/Spring Boot).
- **Domain Layer**: Contract lifecycle logic, validation rules, and approvals.
- **Data Layer**: Relational DB (PostgreSQL) + object storage for documents (S3-compatible).

### 2) Key Services
- **Contract Service**: CRUD + state transitions + ownership management.
- **Vendor Service**: Vendor profiles and contract exposure.
- **Document Service**: Uploads, versioning, hashes, retention.
- **Extraction Service**: AI pipeline + validation workflows.
- **Notification Service**: Deadline alerts, escalation, scheduling.
- **Reporting Service**: Executive timelines and exports.
- **Audit Service**: Append-only event log.

### 3) Integrations
- Email/SMS providers for notifications.
- Optional e-signature integration (future).
- Scheduled jobs for renewal alerts and retention enforcement.

## Data & Security Best Practices
- **Authentication**: SSO (SAML/OIDC) for enterprise readiness.
- **Authorization**: RBAC + ownership checks at API and data layers.
- **Encryption**: At rest (DB, object storage) and in transit (TLS).
- **Audit logging**: Immutable write-once event store.
- **Data integrity**: Document hashing and checksum verification.

## API Examples (Illustrative)
- `POST /contracts` – create contract (draft)
- `PATCH /contracts/{id}/state` – transition state
- `POST /contracts/{id}/documents` – upload new version
- `POST /contracts/{id}/extractions` – trigger AI extraction
- `POST /contracts/{id}/extractions/{id}/approve` – approve AI data
- `GET /reports/executive` – 5-year horizon timeline report

## UI/UX Considerations
- Minimal steps for key actions (create, upload, approve, renew).
- Clear visual timeline for renewals and expirations.
- Prominent indicators for AI vs. verified data.
- Easy access to audit history per contract.

## MVP vs. Phase 2
### MVP
- Core contract/vendor CRUD
- Document upload + versioning
- AI extraction + approval
- Basic notifications (6-month alerts)
- Executive report (PDF)

### Phase 2
- Advanced analytics
- Integrations with ERP/CRM
- Enhanced retention automation
- Workflow customization

## Success Metrics
- Renewal actions captured before notice deadlines.
- Executive visibility across 1–5 years.
- Audit readiness without manual document hunting.
- Elimination of parallel spreadsheets.

## Deliverables
- Requirements-aligned architecture and workflows.
- Implementation-ready service boundaries.
- Governance, audit, and reporting coverage.

---
This design maps directly to the provided business requirements while maintaining a lightweight, enterprise-ready footprint.
