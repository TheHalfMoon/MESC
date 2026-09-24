# CW-009 Canonical Closeout Evidence

- **Task:** CW-009 -- Evidence corpus and retrieval snapshot
- **Status:** `CLOSED_CANONICAL`
- **Parent issue:** [#490](https://github.com/TheHalfMoon/MESC/issues/490) -- CW-009 activation
- **Implementation PR:** [#491](https://github.com/TheHalfMoon/MESC/pull/491) -- `codex/feat/cw-009-evidence-corpus-retrieval`
- **Qualified head:** `3895ec0a9b3baab52ad8417bcda731f0c6cc347b`
- **Head tree:** `df6541b3891083d588e655c3d1c79a1d87dffd99`
- **Base:** `fa5cb12fb582c7002bdfa5e1e8a4f83891a03463` (tree `6c80d4d66867960456bdebea83bc67e233847ea1`)
- **Canonical merge SHA:** `e1e55c1a5989ca1bbdf9730c9ea0f55605e05dd7`
- **Canonical merge tree:** `df6541b3891083d588e655c3d1c79a1d87dffd99`
- **Merge parents:** `fa5cb12fb582c7002bdfa5e1e8a4f83891a03463` (previous canonical `main`), `3895ec0a9b3baab52ad8417bcda731f0c6cc347b` (qualified head)
- **Contracts:** [Clinical Workspace V1](README.md), [data security](data_security.md), [capability map](capability_map.md), [task ledger](tasks.md)

This record documents closure evidence that already exists on canonical `main`; it creates no clinical, PHI, training, publication, research-admission, production, model, remote-inference, remote-retrieval, network-connector, EHR-write, external-write, or autonomous-action authority.

## 1. Governance state entering implementation

```text
CW-001 through CW-008 CLOSED_CANONICAL
CW-008 closeout merge                 fa5cb12fb582c7002bdfa5e1e8a4f83891a03463
CW-009                                activated under Issue 490 on 2026-09-24 as the single active unit under R4
gating contracts                      no new ADR required; synthetic-only deterministic path under Issue 490 activation contract
model contract                        NONE -- no real generation model selected, admitted, or ratified
authorization                         synthetic fixtures only; no network connectors, no remote retrieval, no model download, no paid compute, no PHI
new dependencies                      none; no new packages, no root manifest change, no frozen MRL mutation
Issues 429, 450, 464                 separately governed and untouched
```

## 2. Pre-merge exact-head evidence

Qualified head `3895ec0a9b3baab52ad8417bcda731f0c6cc347b` on base `fa5cb12fb582c7002bdfa5e1e8a4f83891a03463`:

- CI run `36016820825` (CI, pull_request event): SUCCESS -- static py3.11, static py3.12, all eight pytest shard jobs py3.11 and py3.12, quality py3.11, quality py3.12
- CodeQL run `36016820878` (CodeQL, pull_request event): SUCCESS -- analyze python with no new alerts
- check runs: quality py3.11 SUCCESS, quality py3.12 SUCCESS, static py3.11 SUCCESS, static py3.12 SUCCESS, analyze python SUCCESS, CodeQL SUCCESS, cubic NEUTRAL with no finding, all pytest shards SUCCESS
- mergeable MERGEABLE with clean merge state at merge time (protected merge completed 2026-09-24T15:51:12Z)
- unresolved review threads immediately before merge: 0

### 2.1 Review lanes for PR 491, recorded honestly

```text
Jev bounded review         TypeSafe Jev yes/no probes on synthetic-only design facts; no PHI, real patient data, secrets, credentials, API keys, production data, or sealed MRL material sent. Results: snapshot mutability no/0.06, injection authority no/0.08, hidden network no/0.10, replay nondeterminism no/0.04, cross-workspace leakage no/0.16, model creep no/0.09. Jev screening only; not claimed as a merge gate.
Alibaba Open Code Review   Unavailable on this host: neither ocr nor open-code-review on PATH. Nothing installed, no donor workflow added, no repository content sent to a remote model endpoint. Recorded as OCR_UNAVAILABLE. No OCR review claimed.
host-agent review          Performed on the complete diff at the qualified head, covering deterministic identity, immutable snapshot semantics, deterministic replay, provenance and audit correctness, workspace and data-class isolation, prompt and tool-injection resistance, fail-closed behavior, and the absence of network, remote retrieval, model, PHI, production, and EHR/external-write scope. One boundary-guard finding fixed pre-commit: str.replace calls rewritten as index checks to satisfy the persistent-mutation rule, with the guard re-verified PASS.
reviewing GitHub bots      cubic NEUTRAL with no finding.
```

### 2.2 Repairs inside PR 491

PR 491 holds one commit. Forward-only with no repair commits required:

```text
3895ec0  feat: implement CW-009 evidence corpus and retrieval snapshot
```

The boundary-guard finding was fixed before commit, together with ruff and mypy cleanups. No rebase, no force-push, no history rewrite, no protection bypass, no frozen MRL mutation.

### 2.3 Synthetic-only path qualification

```text
SOURCE_REVISION = source-00000001
SNAPSHOT_REVISION = snapshot-00000001
QUERY_REVISION = query-00000001
RESULT_REVISION = result-00000001
INDEX_IDENTITY = cw009-lexical-overlap/1
RANKING_IDENTITY = overlap-desc-source-asc/1
SCHEMA_VERSION = cw009-retrieval/1
PRODUCER = synthetic fixture import (IMPORT) and admitted human operator (HUMAN); no model producer
REAL_MODEL_AUTHORITY = NONE
WEIGHTS = NONE DOWNLOADED
REMOTE_RETRIEVAL = NONE
NETWORK_CONNECTORS = NONE
PAID_COMPUTE = NONE
EXTERNAL_WRITE = NONE EXISTS
```

Ranking is lexical token overlap counted in pure Python; fixture and operator identities are deterministic test values only and are not a real-model decision.

### 2.4 Negative and superseded evidence

```text
superseded GitHub heads   none; single-commit PR with no superseded head claimed as success
cancelled or stale runs   none claimed as success
local Windows limits      default pytest temp root may deny access on this host; local re-verification uses an explicit writable basetemp where required
MRL binding note          no MRL-0809-frozen source was touched by this increment, so no MRL live-binding step applies beyond the passing static gate
```

No MRL-0809-frozen source (pyproject.toml, uv.lock, workflows, MRL modules, MRL evidence) was touched by this increment, and no MRL contract was mutated.

## 3. Protected merge

PR 491 merged through the protected path on 2026-09-24 (mergedAt 2026-09-24T15:51:12Z, by TheHalfMoon, ordinary merge commit with expected-head protection). No squash, no rebase, no force-push, no history rewrite, no gate weakening, no protection bypass.

```text
BASE  = fa5cb12fb582c7002bdfa5e1e8a4f83891a03463
HEAD  = 3895ec0a9b3baab52ad8417bcda731f0c6cc347b
MERGE = e1e55c1a5989ca1bbdf9730c9ea0f55605e05dd7
TREE  = df6541b3891083d588e655c3d1c79a1d87dffd99
PARENTS = fa5cb12fb582c7002bdfa5e1e8a4f83891a03463, 3895ec0a9b3baab52ad8417bcda731f0c6cc347b
```

## 4. Fresh-main qualification

Workflows triggered by merge commit `e1e55c1a5989ca1bbdf9730c9ea0f55605e05dd7`:

- CI run `36023210117` (CI): SUCCESS
- CodeQL run `36023210102` (CodeQL): SUCCESS
- Optional Extras / Backends run `36023210113`: SUCCESS
- Hugging Face Publication Qualification run `36023210053`: SUCCESS

All four fresh-main gates are complete and SUCCESS on the merge commit.

Required CI jobs on fresh-main CI `36023210117`: static py3.11 SUCCESS, static py3.12 SUCCESS, pytest 8/8 SUCCESS (shard 0-3 py3.11 and py3.12), quality py3.11 SUCCESS, quality py3.12 SUCCESS.

## 5. What CW-009 delivered

```text
corpus identity          stable source identities derived from workspace, corpus key, locator, and revision; content digests bind exact bytes; changed bytes, revisions, or locators yield different identities
immutable snapshots      frozen manifests binding member identities, revisions, digests, index contract, ordering rules, and schema version; member order does not affect identity; frozen snapshots never mutate
query identity           normalized text, snapshot, result limit, and match mode bound into deterministic query identities; different parameters yield different identities
deterministic ranking    lexical token overlap with source-identity tie-breaking; no model, embedding, or reranker; same snapshot and query always replay identically
result provenance        result sets preserve query, snapshot, source, revision, date, rank, and score; replay recomputes from the frozen snapshot and refuses divergence, staleness, and mismatches
inert evidence           corpus passages stored and returned verbatim and never evaluated; prompt-injection content stays inert with no capability events; malicious content cannot grant tools, network, or authority
identity boundaries      workspace, corpus, and snapshot identity enforced; cross-workspace and cross-corpus use fails closed; forged identities refused
serialization            deterministic canonical JSON with stable identities derived from admitted members and semantics
provenance               corpus, snapshot, query, and result records stored with CW-003 provenance (IMPORTED records, fixture and operator producers) and audit spine (OBJECT_CREATE, EVIDENCE_QUERY with identifier-only metadata, never clinical text)
no network connectors    no network, remote retrieval, connector, model download, or cloud path exists in this slice; connectors remain a later separately authorized capability
tests                    CW-009 suites in tests/test_clinical_workspace_corpus_v1.py, tests/test_clinical_workspace_retrieval_v1.py, and tests/test_clinical_workspace_retrieval_adversarial_v1.py plus implementation in apps/workspace/src/medscale_workspace/corpus.py and apps/workspace/src/medscale_workspace/retrieval.py with identity and error extensions
```

## 6. Recorded limitations

```text
bounds               sources capped at 256 per snapshot, 64 results per query, 4096 chars per evidence text, 512 chars per query; larger or unadmitted inputs refused, not truncated
ranking              lexical overlap only; no semantic-quality, relevance-quality, or clinical-utility claim granted by this unit
concurrency          identity collisions fail closed as replay or conflict errors; no multi-writer merge
no connectors        web, remote, and connector retrieval are absent by design and remain owned by a later separately authorized capability
no microphone        no live microphone, audio device, streaming, or codec path in this unit
no quality claim     no retrieval quality, clinical quality, or production readiness claim granted by this unit
no real model        fixture and operator identities are deterministic test values, not a real-model decision; any model-backed enhancement needs separate authority
prior limitations    platform secret-storage provider, whole-store rollback, plaintext metadata visibility, secure_delete scope, audit write-once scope, tail-truncation head digest, append cost, ASR link-based export escape, draft link-based export escape, and review link-based export escape remain as previously declared unless explicitly resolved elsewhere
```

## 7. Result

```text
CW_009 = CLOSED_CANONICAL
CW-001 through CW-009 = CLOSED_CANONICAL
CW-010, CW-011, CW-013, CW-015, CW-016, CW-017 = ELIGIBLE_NOT_ACTIVATED
  (each depends only on CLOSED_CANONICAL units; each requires its own separate activation)
CW-012, CW-014, CW-018, CW-019, CW-020 = BLOCKED_DEPENDENCY
CW-021 = BLOCKED_DEPENDENCY plus a required separate explicit Founder and governance clinical-pilot authorization
Issue 490 = close with this closeout (activation fulfilled; do not rewrite historical activation body)
Issue 429, 450, 464 = separately governed and untouched
MRL-0809 (429, 450) = separately governed and untouched
```

CW-009 grants no PHI ingestion, no real patient import, no clinical production use, no real EHR write, no external write, no network-connector admission, no remote retrieval, no autonomous tool execution, no Workspace-data training or research evaluation or admission, no model promotion, no external publication, no paid compute, no MRL contract mutation, and no new MRL Stage-4 attempt.

## 8. Explicit non-grants preserved

```text
CW_009 = CLOSED_CANONICAL
CW_009_MODEL_AUTHORITY = NONE
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
RETRIEVAL_QUALITY = NOT_CLAIMED
PRODUCTION_READINESS = NOT_GRANTED
```

No real generation model has been selected or admitted. No retrieval or clinical quality is claimed. No production readiness is granted. Deterministic replay is a correctness property, not a quality claim.
