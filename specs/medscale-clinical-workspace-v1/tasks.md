# Clinical Workspace V1 — Dependency-Ordered Task Ledger

- **Status:** Proposed planning ledger
- **Date:** 2026-09-20
- **Parent:** [Clinical Workspace V1](README.md)
- **Architecture gate:** proposed ADR-0038
- **Current implementation authority:** NONE

This ledger is implementation-ready planning. It is not an executable backlog until the applicable architecture and task authority is accepted.

## Global gates

Every implementation task below inherits:

```text
ADR_0038_ACCEPTED = REQUIRED
PHI_INGESTION = NOT_AUTHORIZED
CLINICAL_PRODUCTION_USE = NOT_AUTHORIZED
EHR_WRITE = NOT_AUTHORIZED
TRAINING_ON_WORKSPACE_DATA = NOT_AUTHORIZED
MRL_CONTRACT_MUTATION = NOT_AUTHORIZED
NEW_MRL_STAGE4_ATTEMPT = NOT_AUTHORIZED
PAID_COMPUTE = NOT_AUTHORIZED
```

Unless a task explicitly requires a later separate authority, its development fixtures are synthetic only.

Each task is one governed unit under R4 and must finish exact-head qualification before the next dependent task begins.

## Completion states

- `BLOCKED_ARCHITECTURE` — awaits ADR-0038 acceptance.
- `ELIGIBLE` — architecture/dependencies permit implementation.
- `IN_PROGRESS` — one active task.
- `QUALIFIED_HEAD` — exact-head checks/review complete.
- `CLOSED_CANONICAL` — protected merge + fresh-main qualification complete.
- `BLOCKED_EXTERNAL_AUTHORITY` — technical prerequisites exist but explicit external/data/clinical authority is missing.

No checkbox alone proves completion.

## CW-000 — Architecture reconciliation closeout

**State:** `IN_PROGRESS_PLANNING`

**Purpose:** close Issue #459 with an accepted architecture and canonical planning package.

**Deliverables**
- ADR-0038;
- master specification;
- source refresh;
- data/security threat model;
- capability map;
- this task ledger;
- docs/roadmap links.

**Acceptance**
- source facts bind current primary sources or immutable repository revisions;
- Research Core / Workspace / Domain X boundaries are unambiguous;
- no PHI/training/publication/runtime authority is inferred;
- independent review finds no unresolved material scope/security/license contradiction;
- Founder explicitly accepts or rejects ADR-0038;
- exact-head CI/CodeQL succeed;
- normal merge;
- fresh-main qualification succeeds.

**Stop**
- Founder selects another architecture;
- Research Core no-backflow cannot be made mechanical;
- source/license conflict invalidates the proposed architecture.

---

## CW-001 — Workspace boundary skeleton

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-000.

**Purpose:** create the application/package boundary using synthetic fixtures only.

**Expected surfaces**
- future `apps/workspace/**`;
- future Workspace domain library if justified;
- import/dependency guard between Workspace and Research Core;
- synthetic patient/encounter object fixtures.

**Acceptance**
- Research Core installs/tests without Workspace;
- Workspace can consume only declared public/versioned Research interfaces;
- static/dependency test blocks Workspace-to-Research data backflow paths;
- no microphone, EHR, external model, real patient data, or credentials;
- offline test succeeds.

**Stop**
- implementation requires changing Research Core scientific evidence semantics;
- app framework introduces incompatible license or mandatory cloud runtime.

---

## CW-002 — Local protected storage and key abstraction

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-001.

**Purpose:** implement protected local storage using synthetic sensitive fixtures.

**Requires separate implementation ADR**
- database/storage engine;
- cryptographic library/key strategy;
- migration approach.

**Acceptance**
- sensitive fixture content is not readable from copied storage without key material;
- key and payload locations are separated;
- crash-safe transaction behavior;
- workspace isolation;
- key rotation test;
- no plaintext fallback;
- dependency/source license review.

**Stop**
- selected storage cannot support authenticated protection/recovery requirements;
- keys must be stored beside ciphertext without a separate protection mechanism.

---

## CW-003 — Provenance and audit spine

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-001, CW-002.

**Purpose:** create product provenance and security audit records before AI workflows.

**Acceptance**
- generated/imported/edited objects have revision + source identity;
- audit events are append-only logical events;
- provenance and audit are separate concepts;
- sensitive payloads are absent from logs/audit;
- tamper/replay tests;
- deletion can preserve audit metadata without retaining deleted content.

---

## CW-004 — No-backflow and data-classification guard

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-001, CW-003.

**Purpose:** mechanically enforce Domain R/W/X separation.

**Acceptance**
- direct W -> R write/copy/import paths fail;
- X -> R automatic admission fails;
- Workspace telemetry cannot become Research Core data;
- de-identified export remains Domain X;
- tests cover file/API/object-level bypass attempts;
- guard failure is fail-closed.

**Criticality:** this task is a prerequisite for every later data-bearing Workspace feature.

---

## CW-005 — Synthetic encounter session lifecycle

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-003, CW-004.

**Purpose:** implement encounter identity and recording-state semantics with synthetic audio fixtures only.

**Acceptance**
- consent/policy state required before simulated capture;
- start/pause/resume/stop state machine deterministic;
- chunk identity and retention metadata;
- crash-recovery fixture;
- delete cascade;
- no live microphone required.

---

## CW-006 — Local ASR adapter

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-005.

**Purpose:** define and implement an offline ASR adapter with synthetic/permitted fixtures.

**Separate qualification required for any model artifact.**

**Acceptance**
- exact model/runtime revision recorded;
- local path can run with network blocked;
- missing model fails explicitly;
- timestamps preserved;
- partial/failure outputs represented;
- Arabic/English capability only claimed if separately measured;
- no automatic model download during protected offline execution.

**Stop**
- only available backend requires sending audio remotely;
- model/license cannot support intended distribution/use.

---

## CW-007 — Source-linked clinical draft engine

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-003, CW-004, CW-006.

**Purpose:** generate a synthetic note draft whose support can be inspected.

**Acceptance**
- generated spans can reference transcript/source ranges;
- unsupported content is marked;
- exact model/template/input identities recorded;
- negative fixture proves unsupported facts do not become source-backed;
- failure/abstention first-class;
- no finalization action.

---

## CW-008 — Human review and finalization workflow

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-007.

**Purpose:** make review/edit state explicit.

**Acceptance**
- draft != reviewed != finalized;
- human edits preserve revision/provenance;
- source links survive or are explicitly invalidated;
- order/code/task suggestions remain drafts;
- no external write.

---

## CW-009 — Evidence corpus and retrieval snapshot

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-001, CW-003, CW-004.

**Purpose:** provide an offline/local evidence query path first.

**Acceptance**
- corpus source identities;
- immutable/frozen retrieval snapshot identity;
- exact query identity;
- result source IDs and dates;
- deterministic replay where corpus/index is unchanged;
- malicious content does not grant tool capability.

**Network connectors:** later separate task/authority.

---

## CW-010 — Claim-source and evidence-strength layer

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-009.

**Purpose:** prevent “has citations” from being equated with “is supported.”

**Acceptance**
- answer decomposes into claims;
- claim-source links explicit;
- evidence metadata method/version explicit;
- UNKNOWN supported;
- contradiction state;
- source freshness;
- missing-evidence/abstention state;
- adversarial citation mismatch fixtures.

---

## CW-011 — Longitudinal patient graph and timeline

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-003, CW-004.

**Purpose:** build a derived graph over synthetic Workspace objects.

**Acceptance**
- edge epistemic state mandatory;
- every edge has source refs;
- graph rebuildable from sources;
- source revision invalidates/rebuilds affected edges;
- path/explain returns provenance;
- cross-workspace traversal fails;
- deletion removes/rebuilds derived graph state.

---

## CW-012 — Linked document/table/graph workspace

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-011.

**Purpose:** expose healthcare-specific linked workspace objects.

**Acceptance**
- documents/tables/graph/timeline link through stable object IDs;
- no donor-specific schema becomes canonical accidentally;
- local persistence works offline;
- direct AFFiNE/other source reuse, if any, has exact path/revision/license record;
- Research Core artifacts remain read-only when viewed from Workspace.

---

## CW-013 — Bounded FHIR R4 import/export

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-003, CW-004.

**Purpose:** implement a small declared interoperability subset.

**Acceptance**
- exact supported resource set documented;
- parse/structure/profile/reference/provenance states separate;
- workspace/patient binding checked;
- security labels retained where present;
- FHIR Provenance mapping where applicable;
- malformed/unsupported resources fail explicitly;
- no EHR network access required.

---

## CW-014 — Read-only external connector framework

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-013, CW-003, CW-004.

**Purpose:** implement capability-scoped connector contracts without production credentials.

**Development:** mock/local fixture servers only.

**Acceptance**
- least-privilege capability manifest;
- destination allowlist;
- credential redaction;
- timeout/retry bounds;
- offline state;
- stale/version metadata;
- malformed response tests;
- writes mechanically disabled.

**Real endpoint access:** separate explicit authority.

---

## CW-015 — Local Workspace analytics

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-003, CW-004, CW-008.

**Purpose:** compute local operational metrics without turning them into research claims.

**Acceptance**
- metric definitions/version;
- patient-sensitive dimensions protected;
- analytics remain Workspace domain;
- export explicit;
- no automatic telemetry;
- no MRL/research status mutation.

---

## CW-016 — Research Workspace UI

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-001, CW-004.

**Purpose:** expose Research Core artifacts through a local product view.

**Acceptance**
- read-only Research Core by default;
- displays artifact/revision/evidence identity;
- no patient context enters research queries automatically;
- no Research Core mutation outside existing governed interfaces.

---

## CW-017 — Dataset Workspace and export quarantine

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-002, CW-003, CW-004.

**Purpose:** separate research datasets from clinical export staging.

**Acceptance**
- Research dataset mode uses current Research Core governance;
- Workspace export lands in Domain X;
- optional de-identification is an export transformation, not research admission;
- residual identifier tests;
- source/consent/rights manifest;
- cannot create Research Core dataset identity from Domain X.

**Research admission of Workspace-derived data:** separately governed and currently NOT AUTHORIZED.

---

## CW-018 — Backup, restore, deletion, and key rotation

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-002, CW-003, CW-011, CW-017.

**Purpose:** prove lifecycle protection across primary and derived state.

**Acceptance**
- encrypted backup;
- integrity manifest;
- quarantine restore;
- no silent overwrite of newer state;
- deleted object policy across indexes/graph/cache/backups;
- rotation crash test;
- recovery runbook;
- audit coverage.

---

## CW-019 — Security and privacy closure

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-010, CW-012, CW-014, CW-015, CW-016, CW-018.

**Purpose:** independently attack the synthetic/local implementation before any PHI proposal.

**Required review lanes**
- application security;
- supply chain;
- prompt injection/tool boundary;
- local storage/key management;
- connector security;
- backup/delete;
- privacy/data flow;
- provenance/audit;
- license/provenance.

**Acceptance**
- all high/critical findings resolved or architecture blocked;
- threat model reconciled with implementation;
- no hidden egress;
- no Research Core backflow;
- recovery exercises pass.

---

## CW-020 — PHI-readiness evidence packet

**State:** `BLOCKED_ARCHITECTURE`

**Depends on:** CW-019.

**Purpose:** assemble evidence showing the architecture could be considered for a later bounded real-data pilot.

**Acceptance**
- all security/data-flow evidence bound to exact canonical revision;
- runtime/model identities;
- connector scope;
- retention/deletion;
- incident response;
- unresolved risk register;
- independent review.

**Important**

```text
PHI_READINESS_EVIDENCE = NOT PHI AUTHORITY
```

This task cannot ingest PHI.

---

## CW-021 — Separately authorized bounded clinical pilot

**State:** `BLOCKED_EXTERNAL_AUTHORITY`

**Depends on:** CW-020 plus a new explicit Founder/governance authorization.

A valid authorization must name at minimum:

- exact canonical software revision;
- environment/device class;
- participants/users;
- allowed data class;
- patient/encounter scope;
- recording policy;
- model/runtime;
- network/connectors;
- retention/deletion;
- external destinations;
- maximum duration;
- incident/stop conditions;
- clinical review responsibility.

No generic roadmap approval or “go ahead” substitutes for this bounded authority.

---

## Dependency graph

```text
CW-000
  |
CW-001
  |
CW-002 -----+
  |         |
CW-003      |
  |         |
CW-004 <----+
  |
  +--> CW-005 -> CW-006 -> CW-007 -> CW-008 -> CW-015 --+
  |                                                        |
  +--> CW-009 -> CW-010 ----------------------------------+
  |                                                        |
  +--> CW-011 -> CW-012 ----------------------+            |
  |      |                                     |            |
  |      +------------------------------+      |            |
  |                                     |      |            |
  +--> CW-013 -> CW-014 ----------------+------+------------+
  |                                     |                   |
  +--> CW-016 --------------------------+-------------------+
  |                                     |                   |
  +--> CW-017 ---------------------> CW-018 ----------------+
                                                            |
                                                          CW-019
                                                            |
                                                          CW-020
                                                            |
                                                          CW-021 (separate external/clinical authority)
```

CW-009/CW-010 and CW-011/CW-012 may be scheduled only when R4 permits the next single task; the diagram expresses dependency, not parallel execution authority.

## Cross-project / MRL relation

The Clinical Workspace program does not unblock or rewrite MRL-0809.

```text
MRL_0809_RUNTIME_AUTHORITY = INDEPENDENT
ISSUE_429 = INDEPENDENT
ISSUE_450 = INDEPENDENT
WORKSPACE_PLANNING_SUCCESS != MRL_STAGE4_AUTHORITY
```

Research Core capabilities may later be consumed only at canonically qualified interfaces.

## Planning closeout

CW-000 is the only active unit in this planning PR.

All CW-001+ tasks remain blocked until:
1. ADR-0038 receives explicit Founder acceptance;
2. CW-000 merges normally and fresh-main qualifies;
3. the applicable task is separately activated under repository governance.
