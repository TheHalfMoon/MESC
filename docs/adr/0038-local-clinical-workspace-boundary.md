# ADR-0038 — Separate the MedScale research core from a local clinical workspace surface

- **Status:** Accepted by Founder under R6 — pending canonical merge
- **Date:** 2026-09-20
- **Deciders:** Founder
- **Ratified:** 2026-09-21 by explicit Founder decision under R6
- **Related:** Issue #459, ADR-0003, ADR-0005, ADR-0007, ADR-0008, ADR-0035, ADR-0036, `specs/medscale-clinical-workspace-v1/`
- **Supersedes on canonical merge:** only the portions of the Research Vision, ADR-0003, ADR-0005, and ADR-0007 that state MedScale can never own a clinician-facing/local product surface. It does **not** weaken R1-R7, MRL evidence, model/runtime authority, publication authority, or the research-core PHI boundary.

## Context

Canonical MedScale is currently an open medical research platform with a strict synthetic-only research boundary. The Research Vision and ADR-0003 intentionally place product workflows, PHI, UI, storage, and clinical applications outside MedScale and assign those responsibilities to Afia. ADR-0005 likewise keeps verified evidence infrastructure as research infrastructure rather than a clinician-facing answer product.

The Founder has since directed a broader MedScale product goal: a privacy-first, local-first system that eventually combines an Abridge-class clinical scribe workflow, OpenEvidence-class evidence retrieval, OpenMed-class local clinical extraction, a provenance-aware patient/data graph, analytics/research/dataset workspaces, and FHIR/EHR integration while retaining the existing scientific program.

That goal cannot be implemented safely by quietly adding PHI-aware UI and storage to the research package. Doing so would collapse two different trust domains:

1. a public, reproducible, synthetic-only research system whose evidence may support scientific claims; and
2. a local clinical workspace that may eventually hold sensitive patient content and human-authored clinical work.

The distinction must be architectural, not conventional.

## Options considered

### Option A — One application and one data plane

Place research, clinical workspace, storage, evidence search, scribe, and analytics behind one application/data model.

**Benefits**
- smallest conceptual product surface;
- fewer deployment units;
- direct reuse of all internal services.

**Rejected because**
- creates an easy PHI-to-research backflow path;
- makes scientific artifact provenance dependent on a mutable product database;
- turns every workspace feature into a potential MRL contamination vector;
- requires rewriting the strongest existing MedScale governance guarantees.

### Option B — One MedScale project with an isolated research core and clinical workspace

Keep one public project/repository identity, but define two separately governed execution and data domains:

- **Research Core** — the existing `medscale` package and MRL program; synthetic-only; reproducible; no workspace database access.
- **Clinical Workspace** — a separately bounded local application/runtime that may consume released or explicitly versioned Research Core interfaces, but cannot become an evidence source for Research Core training, evaluation, benchmarks, or MRL artifacts.

**Benefits**
- preserves the scientific trust boundary;
- fulfills the Founder’s one-project product direction;
- allows local-first clinical workflows without reclassifying research artifacts;
- creates an explicit place for encryption, consent, audit, retention, backup, deletion, and patient-specific state;
- permits shared FHIR/evidence primitives through controlled interfaces.

**Costs**
- two internal lifecycles and test matrices inside one project;
- strict dependency/data-flow enforcement is mandatory;
- product and research releases cannot be conflated.

### Option C — Separate product repository consuming MedScale

Keep current MedScale unchanged and implement the clinical workspace in a separate repository.

**Benefits**
- strongest physical isolation;
- least disturbance to current governance.

**Rejected as the preferred direction because**
- conflicts with the Founder’s explicit goal for MedScale itself to become the end-to-end local product;
- recreates the current MedScale/Afia split rather than reconciling it.

It remains the rollback option if Option B proves unable to preserve the trust boundary mechanically.

## Decision

Adopt **Option B**.

MedScale remains one public project, but it gains a second, explicitly isolated product domain named **MedScale Clinical Workspace**.

The architecture is:

```text
MedScale repository / public project
|
+-- Research Core
|   +-- src/medscale/**
|   +-- specs/mesc-*/**
|   +-- research datasets/evidence/benchmarks
|   +-- synthetic-only
|   +-- may publish versioned capabilities outward
|   +-- MUST NOT read Workspace state
|
+-- Clinical Workspace
    +-- future app/runtime surface
    +-- local-first patient/encounter/evidence workspace
    +-- may consume approved Research Core APIs/artifacts
    +-- owns local sensitive state when separately authorized
    +-- MUST NOT contribute patient/workspace content to Research Core
```

The dependency and information-flow rule is:

```text
Research Core --versioned interfaces/artifacts--> Clinical Workspace

Clinical Workspace --PHI/patient content/telemetry--> Research Core
                         FORBIDDEN

Clinical Workspace --explicit de-identified export--> Dataset admission queue
                         NOT automatically trusted
                         requires separate source/rights/privacy/research admission
```

## Boundary invariants

### Research Core invariants

The existing Research Core retains all current requirements:

- R1-R7 remain binding.
- Research training/evaluation/benchmarks remain synthetic-only unless a later explicit governance amendment changes that rule.
- MRL evidence identities and historical results remain immutable.
- No workspace database, transcript, recording, patient graph, clinical note, user telemetry, or clinical export is a Research Core evidence source by default.
- No product feature can set MRL task state, research readiness, model promotion, release, or publication authority.
- Research Core can be installed, tested, and reproduced without the Clinical Workspace.

### Clinical Workspace invariants

Before any PHI-capable implementation is authorized, the Workspace specification must enforce:

- local-first operation for the core path;
- explicit network boundaries and no silent cloud fallback;
- encryption-at-rest and protected key material;
- encounter/patient access controls;
- immutable audit events for reads, writes, exports, deletion, model actions, and connector actions;
- explicit retention and deletion semantics for audio, transcripts, notes, embeddings/indexes, graphs, and backups;
- human review before any drafted clinical note, order, code, or other write is treated as final;
- source linkage/provenance for AI-generated clinical content;
- no automatic training or model-improvement upload from local clinical content;
- fail-closed behavior when a required local model, evidence source, validator, or security capability is unavailable.

### Shared interface invariants

Research and Workspace may share **interfaces**, not mutable patient state.

Permitted examples:

- FHIR R4 resource validation and transformation APIs;
- evidence-object schemas and citation/provenance primitives;
- model backend interfaces that have been separately qualified for local use;
- deterministic hashing, artifact identity, and verification utilities.

Forbidden examples:

- Research Core querying the Workspace database;
- Research tests reading real workspace fixtures;
- MRL artifact generation from workspace encounter data;
- workspace telemetry being used as training or evaluation data without a separate admitted dataset contract;
- silently upgrading a research candidate/model because the Workspace downloaded a newer artifact.

## Capability planes

The Clinical Workspace is planned as six planes with narrow contracts:

1. **Encounter plane** — consent, capture, audio lifecycle, diarization/ASR adapters, transcript timeline.
2. **Clinical drafting plane** — source-linked note drafts, structured facts, coding/order suggestions, human review/signing.
3. **Evidence plane** — local/authorized retrieval, citation verification, evidence strength metadata, contradiction and abstention.
4. **Patient graph plane** — longitudinal entities/events/relationships with explicit provenance and edge epistemic state.
5. **Workspace plane** — documents, tables, graph/timeline views, research/analytics/dataset workspaces.
6. **Integration plane** — FHIR import/export and later explicitly governed EHR/database connectors.

Security, provenance, audit, policy, and authorization are cross-cutting planes rather than optional modules.

## Provenance model

Every generated or inferred clinical artifact must expose enough provenance to answer:

- what source material supported it;
- what transformation/model produced it;
- what model/runtime/version was used;
- whether the relationship was directly extracted or inferred;
- who reviewed or modified it;
- what was exported or written downstream;
- what policy/consent allowed the action.

For FHIR resources, the Workspace should map provenance and audit behavior to FHIR R4 `Provenance`, `AuditEvent`, security labels, and applicable consent/policy references while retaining richer local metadata where needed.

Graph relationships use explicit epistemic labels:

```text
EXTRACTED   = explicitly present in an admitted source
DERIVED     = produced by deterministic transformation
INFERRED    = model/algorithm inference with supporting inputs
ASSERTED    = human assertion or edit
AMBIGUOUS   = conflicting or unresolved evidence
```

An inferred edge must never be silently presented as an extracted fact.

## Product workflow principle

The target interaction is not “chatbot first.” It is a longitudinal clinical workspace:

```text
before encounter
  -> local context summary + unresolved items + relevant evidence

during encounter
  -> consented capture
  -> live transcript / structured observations
  -> optional evidence lookup
  -> draft actions only

after encounter
  -> source-linked note draft
  -> proposed codes/orders/tasks
  -> clinician review
  -> explicit export/write
  -> audit + provenance record
```

All final clinical actions remain human-controlled unless a later separate governance decision authorizes a narrower automation.

## External-source reuse policy

Founder permission to reuse code does not eliminate repository-level provenance and license obligations.

Current planning dispositions:

- **OpenMed** — Apache-2.0 SDK source at the reviewed revision; candidate for bounded reuse/adaptation behind Workspace adapters after file-level provenance and model/dataset rights review.
- **Graphify** — Apache-2.0 repository at the reviewed revision; patterns for local deterministic graph construction, explainable edges, and graph query are reusable candidates. Patient-graph semantics must be MedScale-owned and healthcare-specific.
- **AFFiNE** — mixed licensing; concepts such as local-first docs/canvas/tables are useful, but direct code reuse requires path-level license review. Do not import the tree wholesale.
- **OctoBase** — AGPL-3.0 at the reviewed repository metadata; not admitted into the Apache-2.0 core by this ADR.
- **Abridge / OpenEvidence** — product/workflow references only; no source-code reuse is assumed.
- **HL7 FHIR** — standards/reference semantics; implementation must respect applicable specification and terminology licensing.

Every donor-derived implementation task must record source repository, exact revision, source path, license, local modifications, and attribution/NOTICE impact.

## Reconciliation with current accepted decisions

On canonical merge, this ADR changes the following interpretations:

- **Research Vision:** “MedScale is not a clinician-facing product” becomes true only of the **Research Core**, not the whole MedScale project.
- **ADR-0003:** Afia may continue consuming MedScale, but it is no longer the only permitted product surface. The Research Core still never depends on Afia.
- **ADR-0005:** verified evidence infrastructure remains a Research Core pillar; the Workspace may expose evidence-search UX without turning clinical usage into research evidence.
- **ADR-0007:** OpenMed de-identification/local NLP becomes an eligible Workspace capability after separate implementation admission; it remains outside the Research Core’s synthetic-only data path.
- **ADR-0008:** FHIR remains the canonical clinical interchange representation. The Workspace may own EHR-system workflow at its boundary without expanding `fhirkit` into an EHR system.

## Explicit non-grants

This ADR and its planning package do **not** authorize:

```text
PHI_INGESTION = NOT_AUTHORIZED
CLINICAL_PRODUCTION_USE = NOT_AUTHORIZED
MEDICAL_DEVICE_CLAIM = NOT_AUTHORIZED
AUTONOMOUS_ORDER_EXECUTION = NOT_AUTHORIZED
AUTONOMOUS_CODING_SUBMISSION = NOT_AUTHORIZED
REAL_EHR_WRITE_ACCESS = NOT_AUTHORIZED
TRAINING_ON_WORKSPACE_DATA = NOT_AUTHORIZED
RESEARCH_EVALUATION_ON_WORKSPACE_DATA = NOT_AUTHORIZED
SCIENTIFIC_CORPUS_ACCESS = FALSE
SEALED_TIER3_ITEM_DISCLOSURE = FALSE
TRAINING_EXECUTION = NOT_AUTHORIZED
WEIGHT_MUTATION = NOT_AUTHORIZED
MODEL_PROMOTION = NOT_AUTHORIZED
EXTERNAL_PUBLICATION = NOT_AUTHORIZED
PAID_COMPUTE = NOT_AUTHORIZED
MRL_CONTRACT_MUTATION = NOT_AUTHORIZED
NEW_MRL_STAGE4_ATTEMPT = NOT_AUTHORIZED
```

## Acceptance requirements

Before this ADR can become Accepted:

1. the source-refresh and capability map must be reviewed against current primary sources;
2. the data/security boundary must show a mechanically enforceable no-backflow path;
3. implementation tasks must be dependency ordered and independently reviewable;
4. no task may depend on PHI, clinical production access, paid compute, or a new MRL runtime attempt;
5. the Founder must explicitly approve this architecture choice;
6. the accepted commit must pass ordinary exact-head review/CI and protected merge;
7. fresh canonical-main qualification must succeed.

Until then, this ADR is planning evidence only.

## Rollback

If the single-project isolation cannot be proven mechanically before PHI-capable work, revert to Option C: keep Research Core in MedScale and move the clinical product surface to a separately governed repository. No Research Core evidence would need rewriting because the boundary is preserved from the start.
