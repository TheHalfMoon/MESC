# CW-015 Canonical Closeout Evidence

- **Task:** CW-015 -- Local Workspace analytics
- **Status:** `CLOSED_CANONICAL` (pending closeout-PR merge + fresh-main; see discrepancy record below)
- **Parent issue:** [#510](https://github.com/TheHalfMoon/MESC/issues/510) -- CW-015 activation
- **Implementation PR:** [#511](https://github.com/TheHalfMoon/MESC/pull/511) -- `codex/feat/cw-015-analytics`
- **Qualified head:** `73a6eb7d45f475bbc26b3c5b4f2453b80890c13a`
- **Head tree:** `92dba57d351eeddc011ae0e2db149f1daeb0f0c5`
- **Base:** `90f41db9e2e2a420d31f7a6c09207eff757a5dee` (CW-014 closeout merge)
- **Canonical merge SHA:** `6383cf48579cc4b233e8dd9c66b6f7b17dae6680`
- **Canonical merge tree:** `92dba57d351eeddc011ae0e2db149f1daeb0f0c5`
- **Merge parents:** `90f41db9e2e2a420d31f7a6c09207eff757a5dee` (previous canonical `main`), `73a6eb7d45f475bbc26b3c5b4f2453b80890c13a` (qualified head)
- **Contracts:** [Clinical Workspace V1](README.md), [data security](data_security.md), [capability map](capability_map.md), [task ledger](tasks.md)

This record documents closure evidence that already exists on canonical `main`; it creates no clinical, PHI, training, publication, research-admission, production, model, remote-inference, remote-retrieval, network-connector, EHR-write, external-write, telemetry, or autonomous-action authority. Operational analytics remain Workspace-domain analytics; they are not research claims, not benchmark evidence, not MRL evidence, not telemetry, and not model training data.

## 1. Governance state entering implementation

```text
CW-001 through CW-014 CLOSED_CANONICAL
CW-014 closeout merge                90f41db9e2e2a420d31f7a6c09207eff757a5dee
CW-015                               activated under Issue 510 on 2026-09-28 as the single active unit under R4
gating contracts                     no new ADR required; synthetic-only deterministic path under Issue 510 activation contract
model contract                       NONE -- no real generation model selected, admitted, or ratified
authorization                        synthetic fixtures only; local store reads only; no network, no remote retrieval, no model download, no paid compute, no PHI, no production use
new dependencies                     none; no new packages, no manifest change, no frozen MRL mutation
Issues 429, 450, 464                separately governed and untouched
```

## 2. Pre-merge exact-head evidence

Qualified head `73a6eb7d45f475bbc26b3c5b4f2453b80890c13a` on base `90f41db9e2e2a420d31f7a6c09207eff757a5dee`:

- CI run `36380433469` (CI, pull_request event): SUCCESS -- static py3.11, static py3.12, all eight pytest shard jobs py3.11 and py3.12, docs link hygiene, diff check, strict mypy, quality gates
- CodeQL run `36380433468` (CodeQL, pull_request event): SUCCESS -- analyze python with no new alerts
- mergeable MERGEABLE with clean merge state at check time (merge completed 2026-09-28T05:52:21Z)
- GitHub PR reviews recorded: none (no APPROVED review exists via the API)
- reviewing bot signals: Qodo billing-paused (no review), CodeRabbit skipped (repository below star threshold); neither is claimed as review evidence and neither substitutes for Alibaba Open Code Review

### 2.0 Governance discrepancy (forward-only record, not concealed)

No explicit exact-head merge approval for `73a6eb7d45f475bbc26b3c5b4f2453b80890c13a` was recorded in-conversation before PR #511 merged. The implementing agent stopped at MERGE_READY and requested exact-head approval; the merge was then executed under the Founder/operator credential (`TheHalfMoon`, mergedAt 2026-09-28T05:52:21Z) as an ordinary merge commit with the expected parents and a merge tree equal to the qualified head tree. No approval is fabricated here and none is claimed retroactively. No history was rewritten and no evidence was altered to conceal this: the treatment is forward-only annotation in this record. All substantive pre-merge gates above were met, and fresh-main qualification below succeeded. Approving the closeout PR with knowledge of this section constitutes post-merge ratification of the #511 merge; a separate standalone ratification remains available if the Founder requires it.

### 2.1 Review lanes for PR 511, recorded honestly

```text
Jev bounded review         CLI 0.3.2 with model jev-1.13.0 (TypeSafe provider): a 20-probe
spec screen over synthetic-only design facts against the final implementation diff; no PHI,
real patient data, secrets, credentials, API keys, production data, or sealed MRL material
sent. Sixteen probes answered no; four answered yes as screening signals and were each
host-adjudicated against exact code evidence (see below). Jev screening only; not claimed
as a merge gate.
Alibaba Open Code Review   Tool installation verified on this host: open-code-review v1.12.9
at C:/Users/Shehr/.opencodereview/bin/ocr.exe, matching the official release manifest.
Full LLM review lane blocked at the provider-authority boundary: the only configured
provider (anthropic) has no API key, no zero-cost provider credential exists, and paid
compute is not authorized, so no review content was sent anywhere. The official no-LLM
lanes were executed instead (review preview over the exact base/head diff and over the
final commit 73a6eb7: 4 source files reviewable, 2 test files excluded as default_path;
delegate rule lane plus per-file rules check for the Python rule group), and those rules
were applied to the final diff by host-agent review with no blocking findings. No OCR
source, workflow, dependency, or configuration was added to MESC. No OCR review claimed
beyond this record.
host-agent review          Performed on the complete final diff against the official rule content,
covering authority boundaries, deterministic uuid5 analytics identities, versioned metric
admission, aggregate-only outputs with no identifier lists, patient-sensitive dimension
absence, provenance and audit correctness, export/telemetry absence, workspace isolation,
and the absence of network, remote retrieval, model, PHI, production, MRL mutation, and
EHR/external-write scope. No defects carried to commit.
reviewing GitHub bots      no blocking bot findings recorded.
```

### 2.1.1 Jev 20-probe record (preserved exactly, not rewritten)

```text
model                        jev-1.13.0 (TypeSafe provider)
probes reporting NO (16)     stale-state acceptance 0.36, audit bypass 0.29,
cross-workspace leakage 0.27, deterministic identity failure 0.37,
malicious-content authority 0.43, hidden model dependency 0.28,
remote retrieval creep 0.13, PHI creep 0.16, production creep 0.04,
EHR-write creep 0.04, external-write creep 0.35, training creep 0.20,
paid-compute creep 0.14, governance bypass 0.37,
patient-breakdown leak 0.42, totals-trusting 0.22
probes reporting YES (4)     provenance bypass 0.75, nondeterministic
serialization 0.52, hidden network path 0.88, hidden research promotion 0.51
```

Host adjudication of the four YES signals (each tied to exact code evidence; no code change resulted):

```text
provenance bypass 0.75       NOT A DEFECT -- compute_analytics stores every result only
through store_with_provenance with analytics_input source refs to the exact verified
review revisions; read_analytics re-verifies the provenance digest; forged documents
are refused by from_document (proven by the adversarial suite).
nondeterministic 0.52        NOT A DEFECT -- all serialization uses canonical JSON with
sorted keys and fixed separators; the input digest sorts review identities; identities
are uuid5; order-independence is proven by the determinism test.
hidden network 0.88          NOT A DEFECT -- the slice holds no network, socket, URL, or
filesystem capability; the boundary guard passes and admits only allowlisted stdlib
imports plus medscale_workspace modules; all reads are local store reads.
research promotion 0.51      NOT A DEFECT -- results carry the operational analytics data
class (Workspace domain); the no-backflow guard refuses analytics-to-Research-Core flows
with TelemetryBackflowError (proven by the acceptance suite); no research admission path
exists.
```

### 2.2 Composition of PR 511

PR 511 holds one commit with all local verification completed before commit and no history rewrite:

```text
73a6eb7  feat: implement CW-015 local workspace analytics
```

Pre-commit local verification: boundary guard PASS; CW-015 suites 15/15 (7 acceptance, 8 adversarial); regression suites 78/78 (boundary, review, connector); ruff check and ruff format clean; strict mypy on the new test files clean; `git diff --check` clean. Local pytest uses an explicit writable basetemp on this Windows host; CI py3.11/py3.12 is authoritative. No rebase, no force-push, no protection bypass, no frozen MRL mutation.

### 2.3 Synthetic-only path qualification

```text
ANALYTICS_NAMESPACE = 7a15b015-0001-4000-8000-000000000015 (uuid5 namespace)
ANALYTICS_REVISION = workspace-analytics-00000001
PRODUCER_VERSION = cw015-v1
DERIVATION_METHOD = cw015-deterministic-analytics
DERIVATION_METHOD_VERSION = 1
SCHEMA_VERSION = cw015-analytics/1
ADMITTED_METRICS = review-status-counts/1, review-suggestion-counts/1
REAL_MODEL_AUTHORITY = NONE
WEIGHTS = NONE DOWNLOADED
REMOTE_RETRIEVAL = NONE
NETWORK_CONNECTORS = NONE
PRODUCTION_CREDENTIALS = NONE
PAID_COMPUTE = NONE
EXTERNAL_WRITE = NONE EXISTS
AUTOMATIC_TELEMETRY = NONE EXISTS
```

Analytics computation is mechanical tallying of re-verified stored review state; reviewer and operator identities are deterministic test values only and are not a real-model decision. No real model is used to fetch, classify, score, or generate workspace content. No totals parameter exists: caller-supplied totals cannot be trusted because they cannot be supplied.

### 2.4 Negative and superseded evidence

```text
superseded GitHub heads   none; PR 511 holds a single commit and no head was superseded
cancelled or stale runs   none claimed as success
local Windows limits      default pytest temp root may deny access on this host; local re-verification uses an explicit writable basetemp where required; symlink/filemode MRL tests fail locally on Windows for privilege reasons and pass on Linux CI
MRL binding note          no MRL-0809-frozen source was touched by this increment (6 files: 1 new workspace module, 3 minimal workspace extensions, 2 new test files), so no MRL live-binding step applies beyond the passing static gate
```

No MRL-0809-frozen source (pyproject.toml, uv.lock, workflows, MRL modules, MRL evidence) was touched by this increment, and no MRL contract was mutated.

## 3. Protected merge

PR 511 merged through the protected path on 2026-09-28 (mergedAt 2026-09-28T05:52:21Z, ordinary merge commit with expected parents, under the operator credential; see the discrepancy record in section 2.0 for the approval state). No squash, no rebase, no force-push, no history rewrite, no gate weakening, no protection bypass.

```text
BASE  = 90f41db9e2e2a420d31f7a6c09207eff757a5dee
HEAD  = 73a6eb7d45f475bbc26b3c5b4f2453b80890c13a
MERGE = 6383cf48579cc4b233e8dd9c66b6f7b17dae6680
TREE  = 92dba57d351eeddc011ae0e2db149f1daeb0f0c5
PARENTS = 90f41db9e2e2a420d31f7a6c09207eff757a5dee, 73a6eb7d45f475bbc26b3c5b4f2453b80890c13a
```

The merge tree equals the qualified head tree: no unexpected mutation occurred at merge time.

## 4. Fresh-main qualification

Workflows triggered by merge commit `6383cf48579cc4b233e8dd9c66b6f7b17dae6680`:

- CI run `36383784951` (CI): SUCCESS
- CodeQL run `36383784987` (CodeQL): SUCCESS
- Optional Extras / Backends run `36383784959`: SUCCESS
- Hugging Face Publication Qualification run `36383784964`: SUCCESS

All four fresh-main gates are complete and SUCCESS on the merge commit.

## 5. What CW-015 delivered

```text
versioned metrics          exactly 2 admitted metric definitions (review-status-counts/1,
review-suggestion-counts/1); unknown names refused, only version 1 admitted
deterministic identities   uuid5 over workspace, metric name, version, and sorted-input
digest; reordered inputs yield the same identity; distinct inputs yield distinct
identities; re-computation collides instead of overwriting
verified tallies           every input review re-read and chain/digest/binding verified;
tallies derive from stored state; duplicate, unknown, and foreign inputs refused
sensitive dimensions       no per-patient, per-session, per-draft, per-actor, or
per-identifier breakdown exists; outputs carry aggregate counts plus the input digest
only; no dimensions parameter exists
workspace domain           results stored with the operational analytics data class;
analytics-to-Research-Core flows refused with TelemetryBackflowError (test-proven);
no research artifact, no MRL status mutation
explicit export            no EXPORT audit event is emitted by computation; export remains
a separate explicit Domain X quarantine decision owned by later governance
no telemetry               no background collection, no timers, no network I/O; reads are
side-effect free (audit-event count test-proven)
inert content                labels and metric text stored verbatim, never evaluated or
executed; malicious strings remain data and grant no capability
provenance                 every result stored with CW-003 provenance (producer HUMAN,
source kind analytics_input, digest) and an OBJECT_CREATE audit event; workspace
binding checked on every entry point
tests                      CW-015 suites in tests/test_clinical_workspace_analytics_v1.py (7 acceptance tests) and tests/test_clinical_workspace_analytics_adversarial_v1.py (8 adversarial tests) plus implementation in apps/workspace/src/medscale_workspace/analytics.py with error, identity, and provenance extensions
```

## 6. Recorded limitations

```text
bounds               review inputs 1..128 per computation, counts bounded by the input
count, labels at most 64 chars, results at most 32768 canonical bytes; larger or
unadmitted inputs refused, not truncated
review-scoped        metrics derive only from stored CW-008 review revisions; session,
transcript, draft, corpus, graph, FHIR, and connector tallies belong to later units if
ever admitted
no inference         no support-quality, clinical quality, or production readiness claim
granted by this unit; a well-formed aggregate is not automatically meaningful
no export path       this unit computes and stores; any export is a separate explicit
quarantine decision with its own authority
no real model        operator identities are deterministic test values, not a real-model
decision; any model-backed enhancement needs separate authority
prior limitations    platform secret-storage provider, whole-store rollback, plaintext metadata
visibility, secure_delete scope, audit write-once scope, tail-truncation head digest, append
cost, ASR link-based export escape, draft link-based export escape, review link-based export
escape, lexical-overlap ranking, snapshot bounds, graph view bounds, path depth bounds,
lexical export-path containment, and fixture-only connector scope remain as previously
declared unless explicitly resolved elsewhere
```

## 7. Result

```text
CW_015 = CLOSED_CANONICAL (on closeout merge + fresh-main)
CW-001 through CW-015 = CLOSED_CANONICAL
CW-016, CW-017 = ELIGIBLE_NOT_ACTIVATED
  (each depends only on CLOSED_CANONICAL units; each requires its own separate activation)
CW-018, CW-019, CW-020 = BLOCKED_DEPENDENCY
CW-021 = BLOCKED_DEPENDENCY plus a required separate explicit Founder and governance clinical-pilot authorization
Issue 510 = close with this closeout (activation fulfilled; do not rewrite historical activation body)
Issue 429, 450, 464 = separately governed and untouched
MRL-0809 (429, 450) = separately governed and untouched
```

CW-015 grants no PHI ingestion, no real patient import, no clinical production use, no real EHR write, no external write, no network-connector admission, no remote retrieval, no autonomous tool execution, no automatic telemetry, no Workspace-data training or research evaluation or admission, no model promotion, no external publication, no paid compute, no MRL contract mutation, and no new MRL Stage-4 attempt.

## 8. Explicit non-grants preserved

```text
CW_015 = CLOSED_CANONICAL (on closeout merge + fresh-main)
CW_015_MODEL_AUTHORITY = NONE
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

No real model has been selected or admitted. No support or clinical quality is claimed. No production readiness is granted. Deterministic analytics mechanics are a correctness property, not a quality claim.
