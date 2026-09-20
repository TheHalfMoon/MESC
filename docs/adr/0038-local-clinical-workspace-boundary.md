# ADR-0038 — Local clinical workspace boundary

- **Status:** Proposed
- **Date:** 2026-09-20
- **Issue:** #459
- **Planning base:** `475a389777c02a1992acafa24b1cfd1dae24c46b`
- **Authority:** planning only

## Context

Canonical MedScale is research infrastructure with strict no-PHI, reproducibility, evidence, MRL, model/runtime, and scientific-authority semantics. The founder-directed target scope is broader: a local-first/private clinical workspace with medical scribe, evidence/research assistance, patient/data graph views, analytics, research, and dataset workflows.

Mixing research evidence and potentially sensitive workspace state without a hard boundary would create ambiguity about what may enter datasets, benchmarks, training, publication, or canonical evidence.

## Proposed decision

Use a **bounded local clinical-workspace surface around an unchanged research core**.

```text
MedScale
├── Research Core
│   ├── evidence / literature
│   ├── dataset contracts
│   ├── benchmark / replay
│   ├── FHIR research contracts
│   ├── modelkit / MRL / scientific governance
│   └── canonical research artifacts
├── Local Clinical Workspace
│   ├── scribe capture/transcription
│   ├── encounter/document workspace
│   ├── evidence-search presentation
│   ├── graph projection
│   ├── analytics
│   └── user-controlled exports/connectors
└── Explicit adapters
    ├── research artifacts -> workspace
    └── workspace PHI -> research core: PROHIBITED
```

## Boundary invariants

1. Research core remains no-PHI.
2. Workspace artifacts cannot silently become datasets, benchmark items, model inputs, publication artifacts, or scientific results.
3. Core workspace behavior must have a qualified local path; cloud integrations are optional and explicit.
4. Canonical research evidence remains immutable and content-addressed.
5. FHIR interoperability is not a clinical-correctness claim.
6. Evidence answers retain source provenance and uncertainty.
7. Scribe outputs remain drafts until explicit review.
8. Graph state is a derived projection, not canonical research or patient-record truth.
9. Secrets never enter repository artifacts, logs, prompts, or exported research bundles.
10. Repository implementation authority remains distinct from PHI, clinical, runtime, training, release, publication, and deployment authority.

## Data zones

### Zone R — Research
Existing canonical governance. No PHI.

### Zone W — Workspace
Future sensitive-data zone. Until a separate data-protection specification is accepted:

```text
PHI_INGESTION = NOT_AUTHORIZED
PATIENT_RECORD_PERSISTENCE = NOT_AUTHORIZED
CLINICAL_PRODUCTION_USE = NOT_AUTHORIZED
```

### Zone X — External integrations
Opt-in, least privilege, no ambient network, explicit credentials and destination.

### Zone P — Export/publication
Explicit user/governance action with provenance, sensitivity, redaction, and destination checks.

## Required freezes before implementation

- process topology and trust boundaries;
- storage and encryption boundary;
- key lifecycle;
- identity/tenancy/session semantics;
- audit model;
- deletion/retention/backup;
- audio/attachment lifecycle;
- connector permission model;
- offline behavior;
- transcript/note lifecycle;
- citation/evidence object model;
- graph projection contract;
- FHIR import/export contract;
- plugin isolation;
- migration/rollback;
- threat model;
- telemetry policy;
- resource budgets;
- supported platforms;
- deterministic synthetic security fixtures.

## Alternatives

### A. Single mixed application state
Rejected for planning because research, product, and sensitive state can be conflated.

### B. Bounded workspace around research core
**Proposed.** Preserves the research constitution while allowing one MedScale project identity.

### C. Separate repository/product consuming MedScale
Architecturally safe fallback if sufficient isolation cannot be proven inside one repository.

## Non-grants

```text
PHI_INGESTION = NOT_AUTHORIZED
CLINICAL_PRODUCTION_USE = NOT_AUTHORIZED
MEDICAL_DEVICE_CLAIM = NOT_AUTHORIZED
TRAINING = NOT_AUTHORIZED
WEIGHT_MUTATION = NOT_AUTHORIZED
MODEL_PROMOTION = NOT_AUTHORIZED
EXTERNAL_PUBLICATION = NOT_AUTHORIZED
PAID_COMPUTE = NOT_AUTHORIZED
MRL_CONTRACT_MUTATION = NOT_AUTHORIZED
```

## Acceptance

This ADR remains Proposed until source evidence, trust-zone data flow, threat model, ADR/spec conflict map, dependency-ordered tasks, independent review, exact-head CI/CodeQL, protected normal merge, and fresh-main qualification are complete.
