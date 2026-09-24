# Clinical Workspace V1 — Dependency-Ordered Task Ledger

- **Status:** Canonical implementation ledger — CW-001, CW-002, CW-003, CW-004, CW-005, CW-006, CW-007, CW-008 and CW-009 closed; CW-010, CW-011, CW-013, CW-015, CW-016 and CW-017 eligible
- **Date:** 2026-09-20 (frontier reconciled 2026-09-24; CW-002 closed 2026-09-21; CW-003 closed 2026-09-22; CW-004 activated and closed 2026-09-22; CW-005 activated and closed 2026-09-22; CW-006 activated 2026-09-22 and closed 2026-09-23; CW-007 activated 2026-09-23 and closed 2026-09-24; CW-008 activated 2026-09-24 and closed 2026-09-24; CW-009 activated 2026-09-24 and closed 2026-09-24)
- **Parent:** [Clinical Workspace V1](README.md)
- **Architecture gate:** ADR-0038 canonically effective after PR #460 protected merge and fresh-main qualification
- **Current implementation authority:** NONE — CW-009 closed canonically; CW-010, CW-011, CW-013, CW-015, CW-016 and CW-017 are eligible but each requires separate activation before any implementation begins

This ledger is implementation-ready planning. It is not an executable backlog until ADR-0038 is canonically effective, the applicable dependencies are closed canonically, and the applicable task is separately activated. Admissibility is per task: it held for CW-005 while that task was active; no implementation authority exists for any task until it is separately activated.

## Global gates

Every implementation task below inherits:

```text
ADR_0038_CANONICALLY_EFFECTIVE = REQUIRED
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

- `IN_PROGRESS_PLANNING` — planning closeout is active; no implementation authority exists.
- `BLOCKED_CANONICAL_EFFECT` — Founder ratification exists, but ADR-0038/CW-000 has not yet completed protected merge and fresh-main qualification.
- `BLOCKED_DEPENDENCY` — ADR-0038 is canonically effective, but one or more declared task dependencies are not `CLOSED_CANONICAL`.
- `ELIGIBLE` — canonical effect and declared dependencies are satisfied; the task awaits separate activation under repository governance.
- `IN_PROGRESS` — the task has been separately activated and is the one active implementation unit.
- `QUALIFIED_HEAD` — exact-head checks/review complete.
- `CLOSED_CANONICAL` — protected merge + fresh-main qualification complete.
- `BLOCKED_EXTERNAL_AUTHORITY` — canonical effect and technical dependencies are satisfied, but a task-specific external/data/clinical authority is still missing.

No checkbox alone proves completion.

## CW-000 — Architecture reconciliation closeout

**State:** `CLOSED_CANONICAL`

**Purpose:** close Issue #459 with an accepted architecture and canonical planning package.

**Deliverables**
- ADR-0038;
- master specification;
- source refresh;
- data/security threat model;
- capability map;
- migration/compatibility/recovery contract;
- this task ledger;
- docs/roadmap links.

**Acceptance**
- source facts bind current primary sources or immutable repository revisions;
- Research Core / Workspace / Domain X boundaries are unambiguous;
- no PHI/training/publication/runtime authority is inferred;
- independent review finds no unresolved material scope/security/license contradiction;
- Founder R6 ratification of ADR-0038 is recorded without broadening implementation or clinical-data authority;
- exact-head CI/CodeQL succeed;
- normal merge;
- fresh-main qualification succeeds.

**Stop**
- Founder selects another architecture;
- Research Core no-backflow cannot be made mechanical;
- source/license conflict invalidates the proposed architecture.

---

## CW-001 — Workspace boundary skeleton

**State:** `CLOSED_CANONICAL`

**Activation:** Issue #462.

**Closeout evidence:** [cw-001-closeout.md](cw-001-closeout.md)

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

**State:** `CLOSED_CANONICAL`

**Activation:** Issue #467 — Founder ratification of ADR-0039 and CW-002 activation.

**Closeout evidence:** [cw-002-closeout.md](cw-002-closeout.md) — implementation PR #469 merged at `19743d6b6b46f7729883e67f4cee26e72be2b323` (tree `bcf4685a8fe26b197607767691defd5ad4f47596`) after exact-head qualification of `9f9a02112a60cc281447db46c2ac876323af1dd4`, followed by fresh-main CI, CodeQL, Optional Extras/Backends and HF Publication qualification.

**Depends on:** CW-001.

**Purpose:** implement protected local storage using synthetic sensitive fixtures.

**Activation prerequisite (satisfied):** this task required its own implementation ADR (storage engine, key/cryptography strategy, migration approach) ratified under R6 and a separate activation. [ADR-0039](../../docs/adr/0039-local-protected-storage-and-key-management.md) was proposed in PR #466 and then **accepted by the Founder under R6 on 2026-09-21 with Amendment A1**, recorded in the [ratification record](adr-0039-founder-ratification.md). Activation does not waive any acceptance item below.

**Amended contract items (A1):** HKDF-SHA-256 workspace/version key derivation (A1.1); `scrypt` reserved for a future password-derived path (A1.2); 96-bit random per-operation AES-256-GCM nonce with misuse/reuse tests (A1.3); associated data additionally binds the immutable object/revision identity (A1.4); an explicit whole-store rollback limitation (A1.5); an `ACTIVE -> ROTATING -> RETIRING -> RETIRED` key state machine (A1.6); a capability-declaring platform key provider that fails closed (A1.7); dependency-policy reconciliation with no silent dependency (A1.8); a leakage surface beyond the database file (A1.9); an explicit plaintext-metadata scope (A1.10); `secure_delete=ON` as defense in depth only (A1.11); and preservation of every existing principle (A1.12).

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
- dependency/source license review;
- the Amendment A1 security clarifications above are each demonstrated by evidence bound to the exact qualified head.

**Demonstrated on canonical `main`** (see the closeout record for exact run identities): copied
storage is unreadable without the root secret; key and payload locations are separated; pragmas
are asserted rather than assumed; workspace isolation fails closed; the rotation state machine
completes and resumes deterministically; no plaintext fallback exists; and the dependency and
license record is [cw-002-dependency-license-review.md](cw-002-dependency-license-review.md).

**Stop**
- selected storage cannot support authenticated protection/recovery requirements;
- keys must be stored beside ciphertext without a separate protection mechanism.

---

## CW-003 — Provenance and audit spine

**State:** `CLOSED_CANONICAL`

**Depends on:** CW-001, CW-002.

**Activation:** Issue #471 — CW-003 activation. Its dependencies are `CLOSED_CANONICAL`; activation confers no acceptance and no authority beyond this bounded unit.

**Closeout evidence:** [cw-003-closeout.md](cw-003-closeout.md) — implementation PR #472 merged at `c47bab9aa3b0805b4939eba47ee1c3c296995155` (tree `7336adecf50e530859aaea4fe85fa61243603566`) after exact-head qualification of `2b3274f2edd53aa51654f4ac5c54f20181dbf830`, followed by fresh-main CI, CodeQL, Optional Extras/Backends and HF Publication qualification.

**Purpose:** create product provenance and security audit records before AI workflows.

**Implemented surfaces (provenance):** a provenance record is its own immutable workspace object bound to the object revision it describes, carrying the producer identity, explicit source references, review state, recorded content digest, provenance format version and policy version. Generated content must reference at least one source. The recorded digest is re-verified against stored content rather than trusted.

**Implemented surfaces (audit):** each audit event is one immutable object whose event identity is derived from its digest and whose object identity is its chain position, chained to its predecessor's digest from a genesis digest. The chain is contiguous; a replayed event, and a concurrent attempt to append a second event at an occupied chain position, collide with the stored object instead of appending. Deletion of content plus recording of that deletion is one store transaction, so audit metadata survives while the content does not. The caller supplies the occurrence time as a validated ISO-8601 instant with an explicit zone; the package imports no clock.

**Recorded limitation of this unit:** append-only is enforced by the API, by digest-derived identity and by chain verification. There is no database-level write-once trigger, and a removed tail event verifies internally unless a head digest is retained outside the store; that limitation is stated in the module, tested, and belongs to CW-018/CW-019 for stricter enforcement.

**Acceptance**
- generated/imported/edited objects have revision + source identity;
- audit events are append-only logical events;
- provenance and audit are separate concepts;
- sensitive payloads are absent from logs/audit;
- tamper/replay tests;
- deletion can preserve audit metadata without retaining deleted content.

---

## CW-004 — No-backflow and data-classification guard

**State:** `CLOSED_CANONICAL`

**Depends on:** CW-001, CW-003.

**Activation:** Issue #474 — CW-004 activation. Its dependencies are `CLOSED_CANONICAL`; activation conferred no acceptance and no authority beyond this bounded unit.

**Closeout evidence:** [cw-004-closeout.md](cw-004-closeout.md) — implementation PR #475 merged at `7029691e67b121c3b0903db5a6402a7c4719b78a` (tree `462f270a400883fce0e186dfe6ac84febc2f50cd`) after exact-head qualification of `bae0734c7460b58478cec9641ae728cdb31b9f5c`, followed by fresh-main CI, CodeQL, Optional Extras/Backends and HF Publication qualification.

**Purpose:** mechanically enforce Domain R/W/X separation.

**Implemented surfaces (classification):** one canonical typed vocabulary in `data_class.py`: the five trust domains of the planning package, the admitted data classes, and one table binding every class to exactly one domain. A domain is therefore always derived from a class and never supplied by the caller. An unknown or malformed class, an unsupported classification version, or a document whose recorded domain contradicts the table fails closed. The repeated `"SYNTHETIC"` literal of Issue #464 item 3 is replaced by that one canonical value.

**Implemented surfaces (no-backflow):** `nobackflow.py` holds the single declared trust-domain flow table and the only guard entry points. Domain R is refused as a destination for every source, so no write, copy, import or automatic admission into Research Core exists from the Workspace package. A quarantined export is refused automatic Research admission and refused re-admission into the Workspace; operational telemetry, analytics and logs are refused as Research Core data; secret-class material is refused every flow, including inside Domain W. Flows that the planning package declares but for which no authority exists in this unit (external connector, plugin/model runtime, external write) are refused rather than silently permitted, and any undeclared edge is refused by default. Refusals return provenance metadata — rule, domains, object identity — and never carry payload content.

**Implemented surfaces (export containment):** `admit_export_path` and `stage_export` prove that an export target is a strict path below a declared Domain X quarantine root and outside every declared Research Core root, using pure path algebra over caller-supplied absolute paths. De-identification is recorded as a transformation of an export and never as an admission.

**Recorded limitation of this unit:** the Workspace package holds no filesystem capability (no `os`, no `pathlib`, no `open`; the boundary guard forbids them), so the file-level rule is a lexical containment proof and does not resolve symlinks, junctions or reparse points; resolving them would require exactly the capability this package is denied. Link-based escape is therefore recorded as a limitation owned by the first later unit that obtains a filesystem capability, and by CW-019.

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

**State:** `CLOSED_CANONICAL`

**Depends on:** CW-003, CW-004.

**Activation:** Issue #477 — CW-005 activation. Its dependencies are `CLOSED_CANONICAL`; activation conferred no acceptance and no authority beyond this bounded unit.

**Closeout evidence:** [cw-005-closeout.md](cw-005-closeout.md) — implementation PR #478 merged at `0645cd770062f2af0d10fd047f946d9201c8ba41` (tree `1fe050ca0088c5fce05caa25c264798c4e3f7727`) after exact-head qualification of `967188069c8619fe8b075a2cdefcf7c39e8db5de`, followed by fresh-main CI, CodeQL, Optional Extras/Backends and HF Publication qualification.

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

**State:** `CLOSED_CANONICAL`

**Depends on:** CW-005.

**Activation:** Issue #480 -- CW-006 activation. Its dependencies are `CLOSED_CANONICAL`; activation conferred no acceptance and no authority beyond this bounded unit.

**Closeout evidence:** [cw-006-closeout.md](cw-006-closeout.md) -- implementation PR #482 merged at `e040c9f68146435f48a548d89fbe1c1c5158a2d9` (tree `f70d02dffec7807e1278882546f11edf8ab93594`) after exact-head qualification of `cc7ace96ce9b827563862eb232b33d19a26a237b`, followed by fresh-main CI, CodeQL, Optional Extras/Backends and HF Publication qualification.

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

**State:** `CLOSED_CANONICAL`

**Depends on:** CW-003, CW-004, CW-006.

**Activation:** Issue #484 -- CW-007 activation. Its dependencies are `CLOSED_CANONICAL`; activation conferred no acceptance and no authority beyond this bounded unit.

**Closeout evidence:** [cw-007-closeout.md](cw-007-closeout.md) -- implementation PR #485 merged at `68d1999c2f05f4ad8d81ad05f4b08760cc2fdcf4` (tree `bf98be01c81d129ad09c545df2b2270c9769c0c8`) after exact-head qualification of `bd464c16d90ad37972757d539a67875d5e37ebef`, followed by fresh-main CI, CodeQL, Optional Extras/Backends and HF Publication qualification.

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

**State:** `CLOSED_CANONICAL`

**Depends on:** CW-007.

**Activation:** Issue #487 -- CW-008 activation. Its dependencies are `CLOSED_CANONICAL`; activation conferred no acceptance and no authority beyond this bounded unit.

**Closeout evidence:** [cw-008-closeout.md](cw-008-closeout.md) -- implementation PR #488 merged at `be6240009cf3dd03efee47222e908d356ce58b93` (tree `77655e2435f619313d31cc49370315a25ac0a26e`) after exact-head qualification of `2ba4060466e4a5220718ed093d93328e8f1f7d5f`, followed by fresh-main CI, CodeQL, Optional Extras/Backends and HF Publication qualification.

**Purpose:** make review/edit state explicit.

**Acceptance**
- draft != reviewed != finalized;
- human edits preserve revision/provenance;
- source links survive or are explicitly invalidated;
- order/code/task suggestions remain drafts;
- no external write.

---

## CW-009 — Evidence corpus and retrieval snapshot

**State:** `CLOSED_CANONICAL`

**Depends on:** CW-001, CW-003, CW-004.

**Activation:** Issue #490 -- CW-009 activation. Its dependencies are `CLOSED_CANONICAL`; activation conferred no acceptance and no authority beyond this bounded unit.

**Closeout evidence:** [cw-009-closeout.md](cw-009-closeout.md) -- implementation PR #491 merged at `e1e55c1a5989ca1bbdf9730c9ea0f55605e05dd7` (tree `df6541b3891083d588e655c3d1c79a1d87dffd99`) after exact-head qualification of `3895ec0a9b3baab52ad8417bcda731f0c6cc347b`, followed by fresh-main CI, CodeQL, Optional Extras/Backends and HF Publication qualification.

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

**State:** `ELIGIBLE` (not activated)

**Depends on:** CW-009.

**Activation:** requires separate activation under repository governance. Its dependencies are `CLOSED_CANONICAL`; eligibility is not implementation authority.

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

**State:** `ELIGIBLE` (not activated)

**Depends on:** CW-003, CW-004.

**Activation:** requires separate activation under repository governance. Its dependencies are `CLOSED_CANONICAL`; eligibility is not implementation authority.

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

**State:** `BLOCKED_DEPENDENCY`

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

**State:** `ELIGIBLE` (not activated)

**Depends on:** CW-003, CW-004.

**Activation:** requires separate activation under repository governance. Its dependencies are `CLOSED_CANONICAL`; eligibility is not implementation authority.

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

**State:** `BLOCKED_DEPENDENCY`

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

**State:** `ELIGIBLE` (not activated)

**Depends on:** CW-003, CW-004, CW-008.

**Activation:** requires separate activation under repository governance. Its dependencies are `CLOSED_CANONICAL`; eligibility is not implementation authority.

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

**State:** `ELIGIBLE` (not activated)

**Depends on:** CW-001, CW-004.

**Activation:** requires separate activation under repository governance. Its dependencies are `CLOSED_CANONICAL`; eligibility is not implementation authority.

**Purpose:** expose Research Core artifacts through a local product view.

**Acceptance**
- read-only Research Core by default;
- displays artifact/revision/evidence identity;
- no patient context enters research queries automatically;
- no Research Core mutation outside existing governed interfaces.

---

## CW-017 — Dataset Workspace and export quarantine

**State:** `ELIGIBLE` (not activated)

**Depends on:** CW-002, CW-003, CW-004.

**Activation:** requires separate activation under repository governance. Its dependencies are `CLOSED_CANONICAL`; eligibility is not implementation authority.

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

**State:** `BLOCKED_DEPENDENCY`

**Depends on:** CW-002, CW-003, CW-011, CW-017.

**Purpose:** prove lifecycle protection across primary and derived state, including the contract in [migration_recovery.md](migration_recovery.md).

**Acceptance**
- encrypted backup;
- integrity manifest;
- quarantine restore;
- no silent overwrite of newer state;
- deleted object policy across indexes/graph/cache/backups;
- rotation crash test;
- recovery runbook;
- migration manifest/preflight/checkpoint-resume evidence;
- supported upgrade/downgrade refusal semantics;
- rollback or forward-repair exercise;
- audit coverage.

---

## CW-019 — Security and privacy closure

**State:** `BLOCKED_DEPENDENCY`

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

**State:** `BLOCKED_DEPENDENCY`

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

**State:** `BLOCKED_DEPENDENCY`

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

The following edge list is the authoritative rendered dependency view. Every arrow below corresponds to one declared direct dependency; no additional edge is implied by layout.

```text
CW-000 -> CW-001

CW-001 -> CW-002
CW-001 -> CW-003
CW-002 -> CW-003

CW-001 -> CW-004
CW-003 -> CW-004

CW-003 -> CW-005
CW-004 -> CW-005
CW-005 -> CW-006
CW-003 -> CW-007
CW-004 -> CW-007
CW-006 -> CW-007
CW-007 -> CW-008

CW-001 -> CW-009
CW-003 -> CW-009
CW-004 -> CW-009
CW-009 -> CW-010

CW-003 -> CW-011
CW-004 -> CW-011
CW-011 -> CW-012

CW-003 -> CW-013
CW-004 -> CW-013
CW-013 -> CW-014
CW-003 -> CW-014
CW-004 -> CW-014

CW-003 -> CW-015
CW-004 -> CW-015
CW-008 -> CW-015

CW-001 -> CW-016
CW-004 -> CW-016

CW-002 -> CW-017
CW-003 -> CW-017
CW-004 -> CW-017

CW-002 -> CW-018
CW-003 -> CW-018
CW-011 -> CW-018
CW-017 -> CW-018

CW-010 -> CW-019
CW-012 -> CW-019
CW-014 -> CW-019
CW-015 -> CW-019
CW-016 -> CW-019
CW-018 -> CW-019

CW-019 -> CW-020
CW-020 -> CW-021
```

The final `CW-020 -> CW-021` edge is necessary but not sufficient: CW-021 also requires the separate explicit Founder/governance authorization defined in its task contract. CW-009/CW-010 and CW-011/CW-012 may be scheduled only when R4 permits the next single task; the edge list expresses dependency, not parallel execution authority.

## Cross-project / MRL relation

The Clinical Workspace program does not unblock or rewrite MRL-0809.

```text
MRL_0809_RUNTIME_AUTHORITY = INDEPENDENT
ISSUE_429 = INDEPENDENT
ISSUE_450 = INDEPENDENT
WORKSPACE_PLANNING_SUCCESS != MRL_STAGE4_AUTHORITY
```

Research Core capabilities may later be consumed only at canonically qualified interfaces.

## Canonical closeout status

CW-000, CW-001, CW-002, CW-003, CW-004, CW-005, CW-006, CW-007, CW-008 and CW-009 are `CLOSED_CANONICAL`. ADR-0038 is canonically effective, ADR-0039 is accepted by the Founder under R6 as amended by A1, and ADR-0040 is accepted by the Founder under R6 with no amendment. Exact closure evidence is recorded in [cw-000-closeout.md](cw-000-closeout.md), [cw-001-closeout.md](cw-001-closeout.md), [cw-002-closeout.md](cw-002-closeout.md), [cw-003-closeout.md](cw-003-closeout.md) and [cw-004-closeout.md](cw-004-closeout.md), [cw-005-closeout.md](cw-005-closeout.md), [cw-006-closeout.md](cw-006-closeout.md), [cw-007-closeout.md](cw-007-closeout.md), [cw-008-closeout.md](cw-008-closeout.md), [cw-009-closeout.md](cw-009-closeout.md), and the ADR-0039 decision is recorded in [adr-0039-founder-ratification.md](adr-0039-founder-ratification.md) with the ADR-0040 decision recorded in [adr-0040-founder-ratification.md](adr-0040-founder-ratification.md).

Current frontier:

1. CW-001 is `CLOSED_CANONICAL`: implementation PR #463 merged through the protected path at canonical merge `1ec0c3dd2e379649fd0b6a710b9dbde0f60490f3` and completed fresh-main qualification;
2. CW-002 is `CLOSED_CANONICAL`: ADR-0039 was ratified under R6 with Amendment A1, CW-002 was activated under Issue #467, implementation PR #469 merged through the protected path at `19743d6b6b46f7729883e67f4cee26e72be2b323` with fresh-main qualification, and the closeout increment merged at `6f8d20c368549ed8640cfa9f197c7e0eb3d9ca56`;
3. CW-003 is `CLOSED_CANONICAL`: activated under Issue #471, implementation PR #472 merged at `c47bab9aa3b0805b4939eba47ee1c3c296995155` with fresh-main qualification, and closure evidence is recorded in [cw-003-closeout.md](cw-003-closeout.md);
4. CW-004 is `CLOSED_CANONICAL`: activated under Issue #474, implementation PR #475 merged at `7029691e67b121c3b0903db5a6402a7c4719b78a` with fresh-main qualification, and closure evidence is recorded in [cw-004-closeout.md](cw-004-closeout.md);
5. CW-005 is `CLOSED_CANONICAL`: activated under Issue #477, implementation PR #478 merged at `0645cd770062f2af0d10fd047f946d9201c8ba41` with fresh-main qualification, and closure evidence is recorded in [cw-005-closeout.md](cw-005-closeout.md);
6. CW-006 is `CLOSED_CANONICAL`: activated under Issue #480, implementation PR #482 merged at `e040c9f68146435f48a548d89fbe1c1c5158a2d9` with fresh-main qualification, and closure evidence is recorded in [cw-006-closeout.md](cw-006-closeout.md); CW-009, CW-011, CW-013, CW-016 and CW-017 are `ELIGIBLE` because their declared dependencies are `CLOSED_CANONICAL`, but each is **not activated** and no implementation authority exists for any of them;
7. CW-007 is `CLOSED_CANONICAL`: activated under Issue #484, implementation PR #485 merged at `68d1999c2f05f4ad8d81ad05f4b08760cc2fdcf4` with fresh-main qualification, and closure evidence is recorded in [cw-007-closeout.md](cw-007-closeout.md); CW-008, CW-009, CW-011, CW-013, CW-016 and CW-017 are `ELIGIBLE` because their declared dependencies are `CLOSED_CANONICAL`, but each is **not activated** and no implementation authority exists for any of them;
8. CW-008 is `CLOSED_CANONICAL`: activated under Issue #487, implementation PR #488 merged at `be6240009cf3dd03efee47222e908d356ce58b93` with fresh-main qualification, and closure evidence is recorded in [cw-008-closeout.md](cw-008-closeout.md); CW-009, CW-011, CW-013, CW-015, CW-016 and CW-017 are `ELIGIBLE` because their declared dependencies are `CLOSED_CANONICAL`, but each is **not activated** and no implementation authority exists for any of them;
9. CW-009 is `CLOSED_CANONICAL`: activated under Issue #490, implementation PR #491 merged at `e1e55c1a5989ca1bbdf9730c9ea0f55605e05dd7` with fresh-main qualification, and closure evidence is recorded in [cw-009-closeout.md](cw-009-closeout.md); CW-010, CW-011, CW-013, CW-015, CW-016 and CW-017 are `ELIGIBLE` because their declared dependencies are `CLOSED_CANONICAL`, but each is **not activated** and no implementation authority exists for any of them;
10. CW-012, CW-014, CW-018, CW-019 and CW-020 remain `BLOCKED_DEPENDENCY` until their declared predecessors close canonically;
11. CW-021 additionally requires the bounded explicit Founder/governance clinical-pilot authorization defined in its task contract.

No closeout or eligibility statement grants PHI, clinical production, EHR write, Workspace-data training/evaluation, publication, paid-compute, MRL-contract, or Stage-4 authority.
