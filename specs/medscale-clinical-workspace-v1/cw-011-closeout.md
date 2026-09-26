# CW-011 Canonical Closeout Evidence

- **Task:** CW-011 -- Longitudinal patient graph and timeline
- **Status:** `CLOSED_CANONICAL`
- **Parent issue:** [#498](https://github.com/TheHalfMoon/MESC/issues/498) -- CW-011 activation
- **Implementation PR:** [#499](https://github.com/TheHalfMoon/MESC/pull/499) -- `codex/feat/cw-011-patient-graph-timeline`
- **Qualified head:** `b4be14dbb942e3e8cd9ec0a2854302d8599a154b`
- **Head tree:** `40f03fba4797bf70857862d92ebaf7805ce3ebb8`
- **Base:** `3a4c9d7381ded99170432f6025e225815457241c` (CW-010 closeout merge)
- **Canonical merge SHA:** `198cbc1ccc67d00bf06b748c382223e340338fa0`
- **Canonical merge tree:** `40f03fba4797bf70857862d92ebaf7805ce3ebb8`
- **Merge parents:** `3a4c9d7381ded99170432f6025e225815457241c` (previous canonical `main`), `b4be14dbb942e3e8cd9ec0a2854302d8599a154b` (qualified head)
- **Contracts:** [Clinical Workspace V1](README.md), [data security](data_security.md), [capability map](capability_map.md), [task ledger](tasks.md)

This record documents closure evidence that already exists on canonical `main`; it creates no clinical, PHI, training, publication, research-admission, production, model, remote-inference, remote-retrieval, network-connector, EHR-write, external-write, or autonomous-action authority.

## 1. Governance state entering implementation

```text
CW-001 through CW-010 CLOSED_CANONICAL
CW-010 closeout merge                 3a4c9d7381ded99170432f6025e225815457241c
CW-011                                activated under Issue 498 on 2026-09-26 as the single active unit under R4
gating contracts                      no new ADR required; synthetic-only deterministic path under Issue 498 activation contract
model contract                        NONE -- no real generation model selected, admitted, or ratified
authorization                         synthetic fixtures only; no network connectors, no remote retrieval, no model download, no paid compute, no PHI
new dependencies                      none; no new packages, no manifest change, no frozen MRL mutation
Issues 429, 450, 464                 separately governed and untouched
```

## 2. Pre-merge exact-head evidence

Qualified head `b4be14dbb942e3e8cd9ec0a2854302d8599a154b` on base `3a4c9d7381ded99170432f6025e225815457241c`:

- CI run `36251159388` (CI, pull_request event): SUCCESS -- static py3.11, static py3.12, all eight pytest shard jobs py3.11 and py3.12, quality py3.11, quality py3.12
- CodeQL run `36251159410` (CodeQL, pull_request event): SUCCESS -- analyze python with no new alerts
- check runs: quality py3.11 SUCCESS, quality py3.12 SUCCESS, static py3.11 SUCCESS, static py3.12 SUCCESS, analyze python SUCCESS, CodeQL SUCCESS, cubic skipping with no finding, all pytest shards SUCCESS
- mergeable MERGEABLE with clean merge state at merge time (protected merge completed 2026-09-26T16:02:52Z)
- unresolved review threads immediately before merge: 0

### 2.1 Review lanes for PR 499, recorded honestly

```text
Jev bounded review         TypeSafe Jev yes/no probes (jev-1.13.0) on synthetic-only design facts; no PHI, real patient data, secrets, credentials, API keys, production data, or sealed MRL material sent. Results, all no: stale derived edges 0.04, unsupported edge certainty 0.03, cross-workspace traversal 0.02, provenance bypass 0.03, foreign source refs 0.03, revision invalidation failure 0.10, deletion propagation failure 0.17, nondeterministic rebuild 0.02, malicious content authority 0.03, hidden network path 0.03, hidden model path 0.04, PHI creep 0.04, production creep 0.10. Jev screening only; not claimed as a merge gate.
Alibaba Open Code Review   Tool installation verified on this host: open-code-review v1.12.9 at C:/Users/Shehr/.opencodereview/bin/ocr.exe, SHA-256 ae6f4785fea34a5cfef93ad22d8e7fb8032bbd12c45f2cbcc98cbe1b38cceff1 matching the official release manifest. Full LLM review lane blocked at the provider-authority boundary: all 28 built-in providers require remote credentials, none are configured, and paid compute is not authorized, so no review content was sent anywhere. The official no-LLM delegate lane was executed instead (delegate preview over the exact base/head diff plus resolved review rules for the three reviewable source files), and those rules were applied to the final diff by host-agent review with no blocking findings. No OCR source, workflow, dependency, or configuration was added to MESC. No OCR review claimed beyond this record.
host-agent review          Performed on the complete diff at the qualified head, covering authority boundaries, deterministic node/edge/view identities, source/revision/digest bindings, provenance and audit correctness, epistemic-state distinctions, contradiction and UNKNOWN semantics, rebuild determinism and idempotence, path/explain provenance exposure, deletion propagation, prompt and tool-injection resistance, fail-closed behavior, workspace isolation, and the absence of network, remote retrieval, model, PHI, production, and EHR/external-write scope. Exception chaining verified (every raise inside an except handler carries its cause; no bare except; no assert-based validation in shipped code). No defects carried to commit.
reviewing GitHub bots      cubic skipping with no finding; CodeRabbit pass (review skipped for this repository).
```

### 2.2 Repairs inside PR 499

PR 499 holds one commit. Forward-only with no repair commits required:

```text
b4be14d  feat: implement CW-011 longitudinal patient graph and timeline
```

Ruff check, ruff format, the workspace boundary guard, and the docs link hygiene gate were verified clean locally before commit. No rebase, no force-push, no history rewrite, no protection bypass, no frozen MRL mutation.

### 2.3 Synthetic-only path qualification

```text
NODE_REVISION = graph-node-00000001
EDGE_REVISION = graph-edge-00000001
VIEW_REVISION = graph-view-00000001
DERIVATION_METHOD = cw011-deterministic-derivation
DERIVATION_METHOD_VERSION = 1
SCHEMA_VERSION = cw011-patient-graph/1
GRAPH_SCHEMA_VERSION = 1
PRODUCER = admitted human operator (HUMAN); no model producer
REAL_MODEL_AUTHORITY = NONE
WEIGHTS = NONE DOWNLOADED
REMOTE_RETRIEVAL = NONE
NETWORK_CONNECTORS = NONE
PAID_COMPUTE = NONE
EXTERNAL_WRITE = NONE EXISTS
```

Edge admission is mechanical binding of caller-supplied endpoints, relationship, epistemic state, and source identities against admitted store objects; fixture and operator identities are deterministic test values only and are not a real-model decision. No real model is used to infer edges, classify relationships, resolve contradictions, create timelines, or score certainty.

### 2.4 Negative and superseded evidence

```text
superseded GitHub heads   none; single-commit PR with no superseded head claimed as success
cancelled or stale runs   none claimed as success
local Windows limits      default pytest temp root may deny access on this host; local re-verification uses an explicit writable basetemp where required; the Workspace package is outside the strict mypy file set while Issue 464 item 1 is open (CI py3.11/py3.12 authoritative)
MRL binding note          no MRL-0809-frozen source was touched by this increment, so no MRL live-binding step applies beyond the passing static gate
```

No MRL-0809-frozen source (pyproject.toml, uv.lock, workflows, MRL modules, MRL evidence) was touched by this increment, and no MRL contract was mutated.

## 3. Protected merge

PR 499 merged through the protected path on 2026-09-26 (mergedAt 2026-09-26T16:02:52Z, ordinary merge commit with expected-head protection). No squash, no rebase, no force-push, no history rewrite, no gate weakening, no protection bypass.

```text
BASE  = 3a4c9d7381ded99170432f6025e225815457241c
HEAD  = b4be14dbb942e3e8cd9ec0a2854302d8599a154b
MERGE = 198cbc1ccc67d00bf06b748c382223e340338fa0
TREE  = 40f03fba4797bf70857862d92ebaf7805ce3ebb8
PARENTS = 3a4c9d7381ded99170432f6025e225815457241c, b4be14dbb942e3e8cd9ec0a2854302d8599a154b
```

The merge tree equals the qualified head tree: no unexpected mutation occurred at merge time.

## 4. Fresh-main qualification

Workflows triggered by merge commit `198cbc1ccc67d00bf06b748c382223e340338fa0`:

- CI run `36254057190` (CI): SUCCESS
- CodeQL run `36254057183` (CodeQL): SUCCESS
- Optional Extras / Backends run `36254057174`: SUCCESS
- Hugging Face Publication Qualification run `36254057195`: SUCCESS

All four fresh-main gates are complete and SUCCESS on the merge commit.

Required CI jobs on fresh-main CI `36254057190`: static py3.11 SUCCESS, static py3.12 SUCCESS, pytest 8/8 SUCCESS (shard 0-3 py3.11 and py3.12), quality py3.11 SUCCESS, quality py3.12 SUCCESS.

## 5. What CW-011 delivered

```text
derived nodes              admitted nodes bind one node key, one node kind, one label, and exactly one corpus source revision with its digest; identities are deterministic uuid5 values so a new source revision yields a new node identity
mandatory epistemic        every edge carries one explicit epistemic state from the admitted twelve-member vocabulary; SUPPORTED-family states are verdict metadata reused from CW-010 and never collapse into one another; edge existence proves no medical relationship
sourced edges              edges bind two distinct nodes, one relationship, and 1-8 corpus source revisions with digests, plus optional CW-010 claim-set/claim context validated against the stored claim set; derivation method/version and graph schema version bound into every edge identity
frozen views               rebuilds sort members deterministically and are idempotent on identical inputs; reordered inputs yield the identical view; duplicates, foreign members, out-of-node-set edges, and stale members are refused; changed revisions yield different member and view identities
revision invalidation      reads re-verify endpoint nodes, bound sources, claim sets, and provenance digests; any absence or mismatch raises GraphStaleError instead of serving known-stale state
path and explain           breadth-first search over current edges with deterministic tie-breaking; every step exposes source ids, source revisions, epistemic state, derivation identity, and the recorded provenance digest; view-scoped and store-wide modes; no path fails closed
cross-workspace isolation  every entry point checks workspace identity; foreign nodes, edges, source refs, mixed paths, forged bindings, and copied edge identities fail closed
deletion                   node deletion removes the node, all incident edges, and their provenance records while keeping audit events; source deletion makes bound derived state stale on next read or rebuild; stale projections refused
timelines                  deterministic node/edge projection of a frozen view carrying no clinical-time claim
inert content              labels and source text stored verbatim, never evaluated or executed; malicious instruction strings remain data and grant no capability
identity boundaries        workspace, node, edge, and view identities enforced; forged identities refused
serialization              deterministic canonical JSON with stable identities derived from admitted members and semantics
provenance                 nodes, edges, and views stored with CW-003 provenance (IMPORTED records, human producers, per-source refs) and audit spine (OBJECT_CREATE plus OBJECT_DELETE with content removed and metadata kept, never clinical text)
no network connectors      no network, remote retrieval, connector, model download, or cloud path exists in this slice; connectors remain a later separately authorized capability
tests                      CW-011 suites in tests/test_clinical_workspace_patient_graph_v1.py (11 acceptance tests) and tests/test_clinical_workspace_patient_graph_adversarial_v1.py (9 adversarial tests) plus implementation in apps/workspace/src/medscale_workspace/patient_graph.py with identity and error extensions
```

## 6. Recorded limitations

```text
bounds               nodes capped at 256 per view and edges at 512 per view, 8 sources per edge, 512 chars per label, 128 chars per key/identifier, path depth at most 16; larger or unadmitted inputs refused, not truncated
epistemic            epistemic states are explicit caller-supplied parameters; this unit performs no textual entailment, no relationship inference, and grants no support-quality, relevance-quality, or clinical-utility claim
views                frozen snapshots: a view over an old revision remains valid history and is not rewritten; currency is established by rebuilding against current sources, and stale members fail closed on read
paths                breadth-first search over current edges only; stale edges are skipped rather than traversed, so a path touching stale state reports no path instead of a stale path
concurrency          identity collisions fail closed as replay or conflict errors; no multi-writer merge
no connectors        web, remote, and connector retrieval are absent by design and remain owned by a later separately authorized capability
no microphone        no live microphone, audio device, streaming, or codec path in this unit
no quality claim     no support-quality, clinical quality, or production readiness claim granted by this unit
no real model        fixture and operator identities are deterministic test values, not a real-model decision; any model-backed enhancement needs separate authority
prior limitations    platform secret-storage provider, whole-store rollback, plaintext metadata visibility, secure_delete scope, audit write-once scope, tail-truncation head digest, append cost, ASR link-based export escape, draft link-based export escape, review link-based export escape, lexical-overlap ranking, and snapshot bounds remain as previously declared unless explicitly resolved elsewhere
```

## 7. Result

```text
CW_011 = CLOSED_CANONICAL
CW-001 through CW-011 = CLOSED_CANONICAL
CW-012, CW-013, CW-015, CW-016, CW-017 = ELIGIBLE_NOT_ACTIVATED
  (each depends only on CLOSED_CANONICAL units; each requires its own separate activation)
CW-014, CW-018, CW-019, CW-020 = BLOCKED_DEPENDENCY
CW-021 = BLOCKED_DEPENDENCY plus a required separate explicit Founder and governance clinical-pilot authorization
Issue 498 = close with this closeout (activation fulfilled; do not rewrite historical activation body)
Issue 429, 450, 464 = separately governed and untouched
MRL-0809 (429, 450) = separately governed and untouched
```

CW-011 grants no PHI ingestion, no real patient import, no clinical production use, no real EHR write, no external write, no network-connector admission, no remote retrieval, no autonomous tool execution, no Workspace-data training or research evaluation or admission, no model promotion, no external publication, no paid compute, no MRL contract mutation, and no new MRL Stage-4 attempt.

## 8. Explicit non-grants preserved

```text
CW_011 = CLOSED_CANONICAL
CW_011_MODEL_AUTHORITY = NONE
PHI_AUTHORIZATION = NOT_GRANTED
PRODUCTION_AUTHORIZATION = NOT_GRANTED
REMOTE_INFERENCE_AUTHORIZATION = NOT_GRANTED
REMOTE_RETRIEVAL_AUTHORIZATION = NOT_GRANTED
NETWORK_CONNECTOR_AUTHORIZATION = NOT_GRANTED
EHR_WRITE_AUTHORIZATION = NOT_GRANTED
EXTERNAL_WRITE_AUTHORIZATION = NOT_GRANTED
TRAINING_AUTHORIZATION = NOT_GRANTED
PAID_COMPUTE_AUTHORIZATION = NOT_GRANTED
CLINICAL_QUALITY = NOT_CLAIMED
SUPPORT_QUALITY = NOT_CLAIMED
PRODUCTION_READINESS = NOT_GRANTED
```

No real model has been selected or admitted. No support or clinical quality is claimed. No production readiness is granted. Deterministic derivation mechanics are a correctness property, not a quality claim.
