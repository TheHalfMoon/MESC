# CW-012 Canonical Closeout Evidence

- **Task:** CW-012 -- Linked document/table/graph workspace
- **Status:** `CLOSED_CANONICAL`
- **Parent issue:** [#501](https://github.com/TheHalfMoon/MESC/issues/501) -- CW-012 activation
- **Implementation PR:** [#502](https://github.com/TheHalfMoon/MESC/pull/502) -- `codex/feat/cw-012-linked-workspace`
- **Qualified head:** `89dea31f2eb90f0c6ffa35c981a1a60b8cc0b3dc`
- **Head tree:** `a9a9028a3378eb1df8e85491abec36d2042898fe`
- **Base:** `855b778ac33dcda7deb9e5cb28a2c2c2f193a635` (CW-011 closeout merge)
- **Canonical merge SHA:** `e0bee7cdecaa0506b03e8bc03635b0316de0bf75`
- **Canonical merge tree:** `a9a9028a3378eb1df8e85491abec36d2042898fe`
- **Merge parents:** `855b778ac33dcda7deb9e5cb28a2c2c2f193a635` (previous canonical `main`), `89dea31f2eb90f0c6ffa35c981a1a60b8cc0b3dc` (qualified head)
- **Contracts:** [Clinical Workspace V1](README.md), [data security](data_security.md), [capability map](capability_map.md), [task ledger](tasks.md)

This record documents closure evidence that already exists on canonical `main`; it creates no clinical, PHI, training, publication, research-admission, production, model, remote-inference, remote-retrieval, network-connector, EHR-write, external-write, or autonomous-action authority.

## 1. Governance state entering implementation

```text
CW-001 through CW-011 CLOSED_CANONICAL
CW-011 closeout merge                855b778ac33dcda7deb9e5cb28a2c2c2f193a635
CW-012                               activated under Issue 501 on 2026-09-26 as the single active unit under R4
gating contracts                     no new ADR required; synthetic-only deterministic path under Issue 501 activation contract
model contract                       NONE -- no real generation model selected, admitted, or ratified
authorization                        synthetic fixtures only; no network connectors, no remote retrieval, no model download, no paid compute, no PHI
new dependencies                     none; no new packages, no manifest change, no frozen MRL mutation
Issues 429, 450, 464                separately governed and untouched
```

## 2. Pre-merge exact-head evidence

Qualified head `89dea31f2eb90f0c6ffa35c981a1a60b8cc0b3dc` on base `855b778ac33dcda7deb9e5cb28a2c2c2f193a635`:

- CI run `36262873160` (CI, pull_request event): SUCCESS -- static py3.11, static py3.12, all eight pytest shard jobs py3.11 and py3.12, quality py3.11, quality py3.12
- CodeQL run `36262873157` (CodeQL, pull_request event): SUCCESS -- analyze python with no new alerts
- check runs: quality py3.11 SUCCESS, quality py3.12 SUCCESS, static py3.11 SUCCESS, static py3.12 SUCCESS, analyze python SUCCESS, CodeQL SUCCESS, cubic neutral with no finding, all pytest shards SUCCESS
- mergeable MERGEABLE with clean merge state at merge time (protected merge completed 2026-09-27T01:24:09Z)
- unresolved review threads immediately before merge: 0

### 2.1 Review lanes for PR 502, recorded honestly

```text
Jev bounded review         TypeSafe Jev yes/no probes (jev-1.13.0) on synthetic-only design facts, as recorded in the PR 502 body; no PHI, real patient data, secrets, credentials, API keys, production data, or sealed MRL material sent. Results, all no: stale 0.02, cross-workspace 0.02, donor-schema 0.03, research-admission 0.25, deletion 0.02, provenance 0.04, malicious 0.03, network 0.04, model 0.04, PHI 0.03, production 0.07, external-write 0.06. The 0.25 research-admission probe reflects reference naming only; the implementation keeps research refs opaque and the backflow refusal is test-proven. Jev screening only; not claimed as a merge gate. Host re-verified during closeout that the quoted SHAs, runs, and states match live GitHub truth; probe probabilities themselves are repeated from the PR record, not re-executed against PHI or sealed material.
Alibaba Open Code Review   Tool installation verified on this host: open-code-review v1.12.9 at C:/Users/Shehr/.opencodereview/bin/ocr.exe, matching the official release manifest. Full LLM review lane blocked at the provider-authority boundary: all built-in providers require remote credentials, none are configured, and paid compute is not authorized, so no review content was sent anywhere. The official no-LLM delegate lane was executed instead (delegate preview over the exact base/head diff plus resolved review rules for the reviewable source files), and those rules were applied to the final diff by host-agent review with no blocking findings. No OCR source, workflow, dependency, or configuration was added to MESC. No OCR review claimed beyond this record.
host-agent review          Performed on the complete diff at the qualified head, covering authority boundaries, deterministic document/table/link identities, member/source bindings, corpus source and digest bindings, provenance and audit correctness, deletion propagation, stale-link fail-closed behavior, prompt and tool-injection resistance, workspace isolation, research-ref opacity, the absence of donor-schema vendoring, and the absence of network, remote retrieval, model, PHI, production, and EHR/external-write scope. Exception chaining verified (every raise inside an except handler carries its cause; no bare except; no assert-based validation in shipped code). No defects carried to commit.
reviewing GitHub bots      cubic neutral with no finding; CodeRabbit pass (review skipped for this repository).
```

### 2.2 Repairs inside PR 502

PR 502 holds one commit. Forward-only with no repair commits required:

```text
89dea31  feat: implement CW-012 linked document/table/graph workspace
```

Ruff check, ruff format, the workspace boundary guard, and the docs link hygiene gate were verified clean locally before commit, as recorded in the PR body. No rebase, no force-push, no history rewrite, no protection bypass, no frozen MRL mutation.

### 2.3 Synthetic-only path qualification

```text
DOCUMENT_REVISION = linked-document-00000001
TABLE_REVISION = linked-table-00000001
LINK_REVISION = workspace-link-00000001
DERIVATION_METHOD = cw012-deterministic-linking
DERIVATION_METHOD_VERSION = 1
SCHEMA_VERSION = cw012-linked-workspace/1
LINK_SCHEMA_VERSION = 1
PRODUCER_VERSION = cw012-v1
REAL_MODEL_AUTHORITY = NONE
WEIGHTS = NONE DOWNLOADED
REMOTE_RETRIEVAL = NONE
NETWORK_CONNECTORS = NONE
PAID_COMPUTE = NONE
EXTERNAL_WRITE = NONE EXISTS
```

Link admission is mechanical binding of caller-supplied member endpoints, link kind, and corpus source identities against admitted store objects; fixture and operator identities are deterministic test values only and are not a real-model decision. No real model is used to infer links, classify relationships, score certainty, or generate workspace content.

### 2.4 Negative and superseded evidence

```text
superseded GitHub heads   none; single-commit PR with no superseded head claimed as success
cancelled or stale runs   none claimed as success
local Windows limits      default pytest temp root may deny access on this host; local re-verification uses an explicit writable basetemp where required; the Workspace package is outside the strict mypy file set while Issue 464 item 1 is open (CI py3.11/py3.12 authoritative)
MRL binding note          no MRL-0809-frozen source was touched by this increment, so no MRL live-binding step applies beyond the passing static gate
```

No MRL-0809-frozen source (pyproject.toml, uv.lock, workflows, MRL modules, MRL evidence) was touched by this increment, and no MRL contract was mutated.

## 3. Protected merge

PR 502 merged through the protected path on 2026-09-27 (mergedAt 2026-09-27T01:24:09Z, ordinary merge commit with expected-head protection). No squash, no rebase, no force-push, no history rewrite, no gate weakening, no protection bypass.

```text
BASE  = 855b778ac33dcda7deb9e5cb28a2c2c2f193a635
HEAD  = 89dea31f2eb90f0c6ffa35c981a1a60b8cc0b3dc
MERGE = e0bee7cdecaa0506b03e8bc03635b0316de0bf75
TREE  = a9a9028a3378eb1df8e85491abec36d2042898fe
PARENTS = 855b778ac33dcda7deb9e5cb28a2c2c2f193a635, 89dea31f2eb90f0c6ffa35c981a1a60b8cc0b3dc
```

The merge tree equals the qualified head tree: no unexpected mutation occurred at merge time.

## 4. Fresh-main qualification

Workflows triggered by merge commit `e0bee7cdecaa0506b03e8bc03635b0316de0bf75`:

- CI run `36285420738` (CI): SUCCESS
- CodeQL run `36285420727` (CodeQL): SUCCESS
- Optional Extras / Backends run `36285420732`: SUCCESS
- Hugging Face Publication Qualification run `36285420804`: SUCCESS

All four fresh-main gates are complete and SUCCESS on the merge commit.

Required CI jobs on fresh-main CI `36285420738`: static py3.11 SUCCESS, static py3.12 SUCCESS, pytest 8/8 SUCCESS (shard 0-3 py3.11 and py3.12), quality py3.11 SUCCESS, quality py3.12 SUCCESS.

## 5. What CW-012 delivered

```text
linked documents           documents bind one key, one title, 1-32 sections, and exactly one corpus source revision with digest; identities are deterministic uuid5 values so a new source revision yields a new document identity
linked tables              tables bind one key, one title, 1-16 unique columns, width-checked rows (max 128 rows), and exactly one corpus source revision with digest; identities are deterministic uuid5 values
workspace links            links bind two distinct members (linked document/table, graph node/edge/view), one link kind, 1-8 corpus source revisions with digests, and optional opaque research refs; derivation method/version and link schema version bound into every link identity
currency checks            reads re-verify member existence, member currency, bound corpus sources, claim context where applicable, and provenance digests; any absence or mismatch raises LinkedStaleError instead of serving known-stale state
research-ref opacity       research references are opaque read-only strings: never resolved, never fetched, never admitted as corpus sources; the CW-004 guard keeps the direction read-only and the refusal is test-proven
workspace isolation        every entry point checks workspace identity; foreign members, mixed-workspace links, and forged bindings fail closed
deletion                   member deletion removes the member, all incident links, and their provenance records while keeping audit events; source deletion makes bound derived state stale on next read
inert content              titles, sections, cells, and keys stored verbatim, never evaluated or executed; malicious instruction strings remain data and grant no capability
no donor schema            MedScale-owned minimal document/table/link vocabulary; no AFFiNE, Graphify, or OpenMed code or schema vendored; any future direct reuse needs file-level license analysis with exact path/revision/license record
provenance                 documents, tables, and links stored with CW-003 provenance and audit spine integration; Research Core artifacts remain read-only when referenced from Workspace
no network connectors      no network, remote retrieval, connector, model download, or cloud path exists in this slice; connectors remain a later separately authorized capability
tests                      CW-012 suites in tests/test_clinical_workspace_linked_v1.py (8 acceptance tests) and tests/test_clinical_workspace_linked_adversarial_v1.py (8 adversarial tests) plus implementation in apps/workspace/src/medscale_workspace/linked_workspace.py with identity and error extensions
```

## 6. Recorded limitations

```text
bounds               titles at most 256 chars, sections at most 32 with 1024 chars each, columns at most 16 with 64 chars each, rows at most 128 with 256 chars per cell, identifiers and keys at most 128 chars, research refs at most 8 per link, sources at most 8 per link; larger or unadmitted inputs refused, not truncated
links                frozen derived state: a link over an old revision remains valid history and is not rewritten; currency is established by re-reading against current members, and stale links fail closed on read
no inference         link kinds are explicit caller-supplied parameters; this unit performs no textual entailment, no relationship inference, and grants no support-quality, relevance-quality, or clinical-utility claim
concurrency          identity collisions fail closed as replay or conflict errors; no multi-writer merge
no connectors        web, remote, and connector retrieval are absent by design and remain owned by a later separately authorized capability
no microphone        no live microphone, audio device, streaming, or codec path in this unit
no quality claim     no support-quality, clinical quality, or production readiness claim granted by this unit
no real model        fixture and operator identities are deterministic test values, not a real-model decision; any model-backed enhancement needs separate authority
prior limitations    platform secret-storage provider, whole-store rollback, plaintext metadata visibility, secure_delete scope, audit write-once scope, tail-truncation head digest, append cost, ASR link-based export escape, draft link-based export escape, review link-based export escape, lexical-overlap ranking, snapshot bounds, graph view bounds, and path depth bounds remain as previously declared unless explicitly resolved elsewhere
```

## 7. Result

```text
CW_012 = CLOSED_CANONICAL
CW-001 through CW-012 = CLOSED_CANONICAL
CW-013, CW-015, CW-016, CW-017 = ELIGIBLE_NOT_ACTIVATED
  (each depends only on CLOSED_CANONICAL units; each requires its own separate activation)
CW-014, CW-018, CW-019, CW-020 = BLOCKED_DEPENDENCY
CW-021 = BLOCKED_DEPENDENCY plus a required separate explicit Founder and governance clinical-pilot authorization
Issue 501 = close with this closeout (activation fulfilled; do not rewrite historical activation body)
Issue 429, 450, 464 = separately governed and untouched
MRL-0809 (429, 450) = separately governed and untouched
```

CW-012 grants no PHI ingestion, no real patient import, no clinical production use, no real EHR write, no external write, no network-connector admission, no remote retrieval, no autonomous tool execution, no Workspace-data training or research evaluation or admission, no model promotion, no external publication, no paid compute, no MRL contract mutation, and no new MRL Stage-4 attempt.

## 8. Explicit non-grants preserved

```text
CW_012 = CLOSED_CANONICAL
CW_012_MODEL_AUTHORITY = NONE
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

No real model has been selected or admitted. No support or clinical quality is claimed. No production readiness is granted. Deterministic linking mechanics are a correctness property, not a quality claim.
