# MedScale Clinical Workspace V1 — Canonical Planning Specification

- **Status:** Canonical planning package — ADR-0038 effective; CW-000 closed; no implementation authority
- **Date:** 2026-09-20
- **Parent issue:** #459
- **Architecture ADR:** [ADR-0038](../../docs/adr/0038-local-clinical-workspace-boundary.md) — Accepted by Founder under R6; canonically effective
- **Canonical planning base:** `475a389777c02a1992acafa24b1cfd1dae24c46b`
- **Scope:** architecture, data/security boundaries, capability decomposition, delivery sequencing, acceptance contracts
- **Non-scope:** PHI ingestion, production clinical use, model/runtime execution, training, publication, release, paid compute, MRL contract changes
- **Companion contracts:** [data security](data_security.md) · [capability map](capability_map.md) · [migration/recovery](migration_recovery.md) · [task ledger](tasks.md) · [CW-000 closeout](cw-000-closeout.md)

## 1. Purpose

This package reconciles two truths that must remain simultaneously valid:

1. MedScale already contains a rigorous, synthetic-only Research Core whose scientific evidence must remain reproducible and uncontaminated.
2. The Founder has expanded the intended MedScale product identity toward a privacy-first, local-first clinical workspace that combines clinical documentation, evidence search, structured patient context, graph/timeline workflows, analytics/research/dataset tooling, and interoperable local data access.

The planning package makes that expansion implementable without silently converting local clinical data into research evidence.

## 2. Architecture choice

The recommended architecture is **one MedScale project with two isolated domains**:

```text
┌──────────────────────────────── MedScale ────────────────────────────────┐
│                                                                         │
│  ┌──────────────────────┐        versioned one-way interfaces           │
│  │    Research Core     │ ─────────────────────────────────────────┐     │
│  │                      │                                          │     │
│  │ src/medscale/**      │                                          ▼     │
│  │ MRL / benchmarks     │                           ┌──────────────────┐   │
│  │ synthetic-only data  │                           │ Clinical         │   │
│  │ research evidence    │                           │ Workspace        │   │
│  └──────────────────────┘                           │                  │   │
│           ▲                                         │ local patient    │   │
│           │                                         │ and encounter    │   │
│           │              FORBIDDEN                  │ state            │   │
│           └──────────── PHI / patient state ────────┤ evidence UX      │   │
│                                                     │ graph / tables   │   │
│                                                     │ analytics        │   │
│                                                     └──────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

This is a **trust-domain split**, not a branding split.

## 3. Product principles

### 3.1 Local-first is the default execution contract

The core Workspace path must function with no cloud service:

- local patient/encounter store;
- local audio/transcript pipeline when qualified local models exist;
- local note drafting when a qualified local model exists;
- local FHIR validation;
- local graph/timeline;
- local search over locally admitted content;
- local analytics over local data;
- explicit offline state shown to the user.

Optional network connectors are separately visible, separately permissioned, and must never become silent fallbacks.

### 3.2 Human control is a hard boundary

The system drafts, links, explains, and proposes. It does not silently finalize high-consequence actions.

V1 requirements:

- notes are drafts until reviewed;
- orders are suggestions until explicitly confirmed;
- coding suggestions are non-final until explicitly confirmed;
- evidence answers expose sources and uncertainty;
- conflicting evidence is surfaced, not collapsed;
- low-evidence or unsupported outputs may abstain;
- user edits are first-class provenance events.

### 3.3 Provenance precedes convenience

Every important Workspace artifact must be traceable to:

- source data;
- transformation/model/runtime;
- timestamp;
- local policy/consent context;
- user review/edit history;
- export/write target where applicable.

### 3.4 Research evidence and clinical state are different asset classes

A local clinical note can be useful without being admissible scientific evidence.

No Workspace artifact becomes Research Core training/evaluation/benchmark input through:

- file copying;
- export;
- de-identification;
- user opt-in alone;
- local analytics;
- graph derivation;
- model feedback.

Any later research admission requires an independent dataset/source governance path.

## 4. Capability model

The target Workspace is decomposed into capability planes so that each can be tested and authorized independently.

### 4.1 Encounter plane

Responsibilities:

- consent state before recording;
- local microphone/device capture;
- pause/resume/stop;
- optional speaker segmentation/diarization;
- local ASR adapter;
- timestamped transcript;
- structured encounter markers;
- recording retention controls;
- explicit deletion.

Required failure behavior:

- no microphone permission -> named failure;
- local model missing -> named dependency failure;
- network-only ASR configured while offline -> no silent fallback;
- storage full -> stop capture safely and preserve already committed chunks;
- consent revoked mid-encounter -> capture stops immediately and audit event is written.

### 4.2 Clinical drafting plane

Responsibilities:

- specialty-aware note templates;
- source-linked draft sections;
- problem/medication/allergy/finding extraction;
- missing-information markers;
- uncertainty/abstention;
- clinician-directed rewrite/refinement;
- structured action suggestions;
- coding suggestions;
- draft order suggestions;
- patient-facing summary draft.

Every generated span should be able to link to one or more supporting sources:

```text
DraftSpan
  -> SourceRef(audio time range | transcript range | FHIR resource/version | document range)
  -> GenerationIdentity
  -> Confidence / uncertainty metadata
  -> ReviewState
```

No unsupported content may be made to look source-backed.

### 4.3 Evidence plane

Responsibilities:

- natural-language evidence questions;
- local evidence corpus retrieval;
- optional explicitly authorized external retrieval connector;
- exact source/citation identity;
- source freshness metadata;
- claim-to-source links;
- evidence strength metadata;
- contradiction detection;
- evidence gaps;
- answer abstention;
- patient-context scoping only when permitted.

An answer object must separate:

```text
question
answer_claims[]
sources[]
claim_source_links[]
evidence_strength[]
contradictions[]
missing_information[]
abstentions[]
retrieval_time
corpus_snapshot_identity
model_runtime_identity
```

A citation existing is not proof that it supports the claim. Claim-source entailment must be independently checkable.

### 4.4 Patient graph and timeline plane

The graph is a view over admitted local data, not the source of truth.

Node classes may include:

- Patient;
- Encounter;
- Condition;
- Medication;
- Allergy/Intolerance;
- Observation;
- Procedure;
- DiagnosticReport;
- Document;
- EvidenceSource;
- ClinicalClaim;
- Task;
- Appointment;
- Practitioner/Organization where authorized.

Every graph edge has:

```text
edge_type
source_node
target_node
epistemic_state = EXTRACTED | DERIVED | INFERRED | ASSERTED | AMBIGUOUS
source_refs[]
producer_identity
confidence?
created_at
review_state
```

Rules:

- deterministic FHIR links are `DERIVED`;
- explicit textual relations may be `EXTRACTED`;
- model-generated relations are `INFERRED`;
- clinician edits/assertions are `ASSERTED`;
- conflicting unresolved relations are `AMBIGUOUS`;
- graph traversal must preserve edge provenance;
- a graph query result may not erase epistemic state.

### 4.5 Workspace plane

The Workspace combines:

- patient timeline;
- encounter workspace;
- note/document editor;
- evidence panel;
- graph view;
- tables/databases;
- analytics;
- research workspace;
- dataset workspace;
- tasks/follow-up;
- export/share controls.

The user interface should support linked objects rather than disconnected pages.

The implementation may learn from AFFiNE-style docs/canvas/tables composition, but Workspace semantics remain healthcare-specific and source reuse is license-gated.

### 4.6 Integration plane

Initial boundary:

- FHIR R4 import/export;
- local file import;
- explicitly configured local database connector;
- read-only EHR/FHIR server connector only after separate connector authorization.

Later boundaries require separate decisions for:

- production EHR writes;
- scheduling;
- orders;
- billing submission;
- messaging;
- remote storage;
- cross-organization synchronization.

## 5. Abridge-class workflow coverage target

The Workspace roadmap should cover the useful product pattern, not copy branding or unsupported claims.

### Before encounter

Planned capabilities:

- patient/context summary;
- recent encounter timeline;
- active problems/medications/allergies;
- relevant labs/imaging/document changes;
- unresolved tasks/care gaps when source support exists;
- evidence links for context-sensitive questions.

### During encounter

Planned capabilities:

- consented ambient capture;
- live transcript;
- speaker-aware transcript where technically qualified;
- structured observation extraction;
- clinician-visible evidence lookup;
- draft task/order capture;
- explicit recording state.

### After encounter

Planned capabilities:

- structured note draft;
- source-linked statements;
- review/edit;
- suggested diagnosis/coding metadata;
- suggested orders/tasks/follow-up;
- patient summary draft;
- explicit export/write;
- provenance/audit event.

### Trust controls

The Workspace must match or exceed these trust patterns:

- source linkage for generated content;
- clinician review before finalization;
- model/version identity;
- traceable edits;
- no hidden autonomous write;
- no cloud requirement for the core path.

## 6. OpenEvidence-class evidence workflow coverage target

The target is a high-quality evidence workspace with stronger inspectability.

Planned capabilities:

- natural-language medical evidence search;
- peer-reviewed/guideline source ingestion through authorized connectors;
- citation-aware synthesis;
- evidence strength classification;
- date/freshness filtering;
- specialty/topic filters;
- contradiction surfacing;
- patient-context-aware query construction when policy permits;
- voice query as an input mode;
- saved evidence threads;
- compare-guidelines/compare-trials view;
- source table/figure attachment where rights permit;
- auditable answer replay from an immutable retrieval snapshot.

The Research Core evidence machinery may supply schemas and verification primitives; patient-specific query context remains Workspace-only.

## 7. OpenMed-class local NLP coverage target

OpenMed is a candidate implementation donor and comparator, not a source of truth.

Workspace-relevant capabilities:

- local clinical NER;
- PII detection;
- de-identification as a user-controlled export aid;
- local/offline model execution;
- CPU/CUDA/Apple/mobile/browser adapter ideas;
- FHIR-related extraction/export workflows;
- batch extraction;
- local service/tool interfaces.

Rules:

- each model artifact has its own rights/provenance record;
- SDK Apache-2.0 does not imply every model/dataset is Apache-2.0;
- de-identification never automatically makes data admissible to Research Core;
- OpenMed outputs are not gold;
- performance claims require MedScale-owned benchmarks.

## 8. AFFiNE / Graphify design lessons

### AFFiNE-derived product principles

Useful principles:

- local-first ownership;
- docs + canvas + tables in one workspace;
- linked object model;
- offline-capable editing;
- optional collaboration as a later layer;
- self-hostable architecture.

Reuse constraint:

AFFiNE is not treated as a uniformly MIT codebase. Any direct reuse requires file/path-level license analysis. The Workspace should adopt interaction principles before adopting code.

### Graphify-derived graph principles

Useful principles:

- graph edges must be explainable;
- extracted and inferred relationships are explicitly distinguished;
- local deterministic extraction is preferred where available;
- graph query/path/explain operations are useful UX primitives;
- graph state is a derived, inspectable artifact rather than a hidden embedding index.

Healthcare adaptation:

- use FHIR identities and local Workspace object identities;
- preserve source/version references;
- attach security/consent scope to sensitive graph nodes/edges;
- do not infer a clinical relation without marking it as inference;
- never treat graph connectivity as medical truth.

## 9. Data domains

### Domain R — Research Core

Contains:

- synthetic fixtures;
- research datasets admitted by current governance;
- benchmark data;
- MRL evidence;
- research model artifacts;
- reproducibility artifacts.

Workspace access to Domain R is read-only through versioned interfaces where appropriate.

### Domain W — Workspace clinical state

Future contents may include, only after separate PHI authorization:

- patients;
- encounters;
- recordings;
- transcripts;
- notes;
- imported FHIR;
- attachments;
- local evidence-search context;
- graph state;
- audit records;
- user preferences.

Research Core access to Domain W is forbidden.

### Domain X — Export/admission staging

Purpose:

- explicit user-requested export;
- de-identification workflow;
- rights/privacy review;
- validation;
- provenance package.

Domain X is **not** Research Core. A separate governance decision is required before an export is admitted into Domain R.

## 10. Local storage contract

Before PHI-capable implementation:

- no plaintext sensitive database accepted by default;
- encryption keys are not stored with encrypted payloads;
- root key material uses platform-protected secret storage where available;
- per-workspace data encryption keys are supported;
- attachments use authenticated encryption;
- temporary audio/model scratch data has bounded lifetime;
- crash recovery never writes unencrypted fallback copies;
- backups are encrypted separately;
- backup restore verifies integrity and policy version;
- deletion covers primary store, derived indexes, graph projections, caches, and local backups according to declared retention semantics;
- audit logs record deletion without retaining deleted content.

The exact database/encryption library is a later implementation ADR because its choice carries security and licensing consequences.

## 11. Identity and provenance contract

Every persisted object requires:

```text
object_id
object_type
workspace_id
created_at
updated_at
producer
source_refs[]
content_digest
schema_version
policy_version
security_labels[]
review_state
```

Generated objects additionally require:

```text
model_id
model_revision
runtime_id
prompt_or_template_digest
generation_parameters_digest
input_digest_set
output_digest
```

Imported FHIR objects retain:

- resource type/id/version where supplied;
- source endpoint/file identity;
- import time;
- validation status;
- FHIR Provenance mapping where available.

## 12. Audit contract

Audit events are append-only logical events for at least:

- login/unlock;
- workspace open/close;
- patient/encounter read;
- capture start/pause/resume/stop;
- transcript creation/edit/delete;
- AI generation;
- evidence query;
- export;
- connector read/write;
- note finalization;
- order/code suggestion acceptance/rejection;
- backup/restore;
- delete;
- policy change;
- key rotation;
- security failure.

Audit records must not leak full sensitive payloads.

## 13. Consent and policy contract

V1 planning distinguishes:

- recording consent;
- local processing consent/policy;
- external connector/network permission;
- export permission;
- sharing permission;
- retention policy.

No permission is inferred from another permission.

Revocation affects future actions immediately and schedules applicable retained artifacts for policy-governed deletion.

## 14. Network policy

Default:

```text
NETWORK_CORE_PATH = OFF
TELEMETRY = OFF
SILENT_FALLBACK = FORBIDDEN
```

Any networked feature must declare:

- destination;
- purpose;
- data classes transmitted;
- authentication mode;
- retention assumptions;
- retry behavior;
- offline behavior;
- user-visible state;
- audit event.

Network access from a model adapter must never be implied by model load.

## 15. Model/runtime policy

The Workspace does not inherit MRL execution authority.

Workspace local-model implementation requires its own artifact/runtime qualification for:

- model identity;
- revision;
- license;
- hardware compatibility;
- memory/latency;
- offline behavior;
- prompt/template identity;
- supported languages/modalities;
- known limitations;
- safety/abstention behavior.

No Workspace model execution can be relabeled as MRL evidence.

## 16. FHIR policy

FHIR remains the canonical external clinical representation.

Workspace V1 should support a bounded declared subset before broad coverage.

Every operation distinguishes:

- parse;
- structural validation;
- profile/invariant validation;
- terminology state;
- reference integrity;
- provenance;
- semantic support;
- export/write state.

A structurally valid resource is not automatically clinically correct.

FHIR R4 `Provenance`, `AuditEvent`, security labels, and applicable Consent semantics are reference points for data lineage and audit behavior.

## 17. Evidence grading

Evidence strength is metadata, not a single magic score.

Minimum fields:

```text
source_type
publication_type
publication_date
guideline_status?
peer_reviewed?
population_scope
study_design?
sample_size?
risk_of_bias_state
directness
recency
conflict_state
grade_method
grade_version
```

If metadata cannot be established, the grade state is `UNKNOWN`.

No model confidence score substitutes for evidence quality.

## 18. Analytics plane

Workspace analytics may compute local operational/clinical-workspace measures such as:

- encounters processed;
- note review time;
- draft edit distance;
- evidence searches;
- unresolved items;
- local model latency;
- failure rates;
- user-approved structured outputs.

These metrics are local Workspace metrics. They are not research claims unless separately admitted under Research Core governance.

## 19. Research workspace

The Research Workspace is a UI over Research Core capabilities, not a route for patient data into research.

Functions may include:

- literature collections;
- evidence objects;
- benchmark/artifact inspection;
- experiment manifests;
- replay;
- dataset manifests;
- model cards;
- graph views over research artifacts.

Opening a patient object in the clinical Workspace must never automatically add it to a research collection.

## 20. Dataset workspace

The Dataset Workspace has two distinct modes:

### Research datasets

Governed by existing Research Core rules.

### Clinical export staging

Governed by Domain X. It can:

- select records;
- run de-identification;
- inspect residual identifiers;
- record source/consent/rights;
- produce an export manifest.

It cannot:

- mark the export “research admitted”;
- move data into MRL/training folders;
- create a research dataset identity;
- authorize training.

## 21. Security posture

The system assumes:

- local device compromise is possible;
- malicious documents can be imported;
- prompt injection can arrive through notes/evidence pages;
- a model may hallucinate or emit dangerous structured actions;
- connectors may return stale or malformed data;
- plugins may be malicious;
- backups may be stolen;
- logs may leak sensitive data;
- users may accidentally export the wrong scope.

The detailed threat model is in [data_security.md](data_security.md).

## 22. Recovery and failure modes

The detailed version/schema/key/index migration and rollback contract is [migration_recovery.md](migration_recovery.md).

The Workspace must have explicit recovery for:

- interrupted recording;
- ASR/model crash;
- database corruption;
- key loss;
- partial import;
- partial export;
- failed FHIR write;
- evidence connector outage;
- stale model;
- stale evidence index;
- graph rebuild failure;
- backup restore failure;
- disk-full state.

Rules:

- prefer recoverable append/chunk writes over monolithic state;
- partial downstream writes require transaction/reconciliation identifiers;
- failed writes do not become local success;
- graph/index rebuilds are derived operations and may be discarded/rebuilt;
- source records and provenance are retained according to policy;
- recovery never bypasses encryption, audit, or consent rules.

## 23. Observability

Local observability is allowed; hidden telemetry is not.

Local diagnostics may include:

- structured logs without sensitive payloads;
- health checks;
- model/runtime timings;
- queue lengths;
- disk pressure;
- index state;
- connector state;
- audit verification.

External telemetry is disabled by default and requires a separate explicit data contract.

## 24. Plugin/connector boundary

Plugins/connectors run with least privilege.

Each declares capabilities such as:

```text
READ_FHIR
WRITE_FHIR
READ_LOCAL_FILES
WRITE_LOCAL_FILES
NETWORK
MICROPHONE
EXPORT
MODEL_EXECUTION
```

V1 implementation should begin with read-only connectors.

No plugin receives research/training authority through capability access.

## 25. Implementation shape

No production code is authorized by this planning package, but future implementation should preserve these top-level boundaries:

```text
src/medscale/**                         # existing Research Core
specs/medscale-clinical-workspace-v1/** # product contracts
apps/workspace/**                       # future UI/application shell
packages/workspace-*/**                 # future product libraries if justified
```

If introducing a second language/toolchain, a dedicated implementation ADR must justify it.

## 26. Acceptance strategy

Every implementation slice must include:

- positive tests;
- negative/fail-closed tests;
- provenance assertions;
- offline/no-network test where applicable;
- data-domain boundary tests;
- crash/recovery test where stateful;
- security test for its new attack surface;
- exact-head CI;
- independent review;
- protected merge;
- fresh-main qualification.

## 27. Product milestones

### CW0 — Architecture and trust boundary

Deliverables:

- ADR-0038 decision;
- this specification;
- source refresh;
- data/security model;
- task DAG.

No production code.

### CW1 — Synthetic-only local workspace skeleton

Deliverables:

- local application shell;
- synthetic patient/encounter fixtures only;
- local object identity;
- audit/provenance skeleton;
- no microphone/model/EHR/PHI.

### CW2 — Local encounter and note workflow

Deliverables:

- synthetic/local audio fixtures;
- ASR adapter;
- transcript;
- draft note;
- source linkage;
- review flow.

No production PHI authorization implied.

### CW3 — Evidence workspace

Deliverables:

- local corpus;
- retrieval;
- citations;
- evidence metadata;
- contradiction/abstention;
- replay.

### CW4 — Patient graph and longitudinal context

Deliverables:

- FHIR/object graph;
- provenance-labelled edges;
- timeline;
- query/path/explain.

### CW5 — FHIR/read-only integration

Deliverables:

- bounded FHIR import/export;
- read-only connector;
- reconciliation;
- failure semantics.

### CW6 — Analytics, research, and dataset workspaces

Deliverables:

- local analytics;
- Research Core UI;
- Dataset Workspace with export/admission separation.

### CW7 — Security and PHI-readiness qualification

Deliverables:

- encryption implementation;
- key management;
- backup/restore;
- deletion;
- threat-model closure;
- penetration/security review;
- privacy/data-flow review.

**CW7 does not itself authorize PHI.**

### CW8 — Separately authorized clinical pilot

Requires a later explicit Founder/governance authorization with scope, environment, data class, users, retention, model/runtime, connector, and stop conditions.

## 28. Planning closeout for issue #459

The planning exit conditions are satisfied:

- ADR-0038 was explicitly ratified by the Founder under R6;
- the planning package received independent exact-head review with no material defect;
- the task dependency graph remained complete and acyclic;
- existing MRL evidence and authority boundaries remained unchanged;
- PR #460 exact head `f1f35558599fbbacd4c4045731496531d3a5eb34` qualified;
- PR #460 merged normally at `b9d122cb59a11eb1195e9caa0e9ae3cd03705265`;
- fresh-main CI, CodeQL, Optional Extras / Backends, and Hugging Face Publication Qualification all succeeded on that merge SHA.

CW-000 is `CLOSED_CANONICAL`. Exact closure evidence is recorded in [cw-000-closeout.md](cw-000-closeout.md).

CW-001 is `CLOSED_CANONICAL`. Exact closure evidence is recorded in [cw-001-closeout.md](cw-001-closeout.md).

CW-002 is `CLOSED_CANONICAL`. ADR-0039 (storage engine, key and cryptography strategy, migration approach) was accepted by the Founder under R6 on 2026-09-21 with Amendment A1, CW-002 was activated under Issue #467, and implementation PR #469 merged through the protected path with fresh-main qualification. The [ratification record](adr-0039-founder-ratification.md) is controlling for the amended decision and [cw-002-closeout.md](cw-002-closeout.md) records the closure evidence. CW-003 (provenance and audit spine) is `CLOSED_CANONICAL`: activated under Issue #471 and closed through PR #472, with evidence in [cw-003-closeout.md](cw-003-closeout.md). CW-004 (no-backflow and data-classification guard) is `CLOSED_CANONICAL`: activated under Issue #474 and closed through PR #475, with evidence in [cw-004-closeout.md](cw-004-closeout.md). CW-005 (synthetic encounter session lifecycle) is `CLOSED_CANONICAL`: activated under Issue #477 and closed through PR #478, with evidence in [cw-005-closeout.md](cw-005-closeout.md). CW-006, CW-009, CW-011, CW-013, CW-016 and CW-017 are `ELIGIBLE` but not activated; CW-007 onward remains dependency-blocked. No Clinical Workspace increment confers PHI, clinical-production, EHR-write, training, publication or MRL authority.
