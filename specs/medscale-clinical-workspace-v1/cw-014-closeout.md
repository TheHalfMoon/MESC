# CW-014 Canonical Closeout Evidence

- **Task:** CW-014 -- Read-only external connector framework
- **Status:** `CLOSED_CANONICAL` (pending closeout-PR merge + fresh-main; see section 8)
- **Parent issue:** [#507](https://github.com/TheHalfMoon/MESC/issues/507) -- CW-014 activation
- **Implementation PR:** [#508](https://github.com/TheHalfMoon/MESC/pull/508) -- `codex/feat/cw-014-connector`
- **Qualified head:** `f4e24601c6c2821cbb394d09b0d9890e17a2eb16`
- **Head tree:** `31f183f6cd0ec37d307c2a137bb0bd33496c8f77`
- **Base:** `296308db2da2ef4badac8566eb8954ad9589b891` (CW-013 closeout merge)
- **Canonical merge SHA:** `5ee3a52de8e2f8d30477e089edc6b112be62a160`
- **Canonical merge tree:** `31f183f6cd0ec37d307c2a137bb0bd33496c8f77`
- **Merge parents:** `296308db2da2ef4badac8566eb8954ad9589b891` (previous canonical `main`), `f4e24601c6c2821cbb394d09b0d9890e17a2eb16` (qualified head)
- **Contracts:** [Clinical Workspace V1](README.md), [data security](data_security.md), [capability map](capability_map.md), [task ledger](tasks.md)

This record documents closure evidence that already exists on canonical `main`; it creates no clinical, PHI, training, publication, research-admission, production, model, remote-inference, remote-retrieval, network-connector, EHR-write, external-write, or autonomous-action authority. The fixture-only connector framework does NOT grant real network connector authority; real endpoint access remains NOT AUTHORIZED.

## 1. Governance state entering implementation

```text
CW-001 through CW-013 CLOSED_CANONICAL
CW-013 closeout merge                296308db2da2ef4badac8566eb8954ad9589b891
CW-014                               activated under Issue 507 on 2026-09-27 as the single active unit under R4
gating contracts                     no new ADR required; synthetic-only deterministic path under Issue 507 activation contract
model contract                       NONE -- no real generation model selected, admitted, or ratified
authorization                        synthetic fixtures only; mock/local fixture transports only; no production credentials, no network, no remote retrieval, no model download, no paid compute, no PHI
new dependencies                     none; no new packages, no manifest change, no frozen MRL mutation
Issues 429, 450, 464                separately governed and untouched
```

## 2. Pre-merge exact-head evidence

Qualified head `f4e24601c6c2821cbb394d09b0d9890e17a2eb16` on base `296308db2da2ef4badac8566eb8954ad9589b891`:

- CI run `36336639236` (CI, pull_request event): SUCCESS -- static py3.11, static py3.12, all eight pytest shard jobs py3.11 and py3.12, docs link hygiene, diff check, strict mypy, quality gates
- CodeQL run `36336639229` (CodeQL, pull_request event): SUCCESS -- analyze python with no new alerts
- mergeable MERGEABLE with clean merge state at merge time (protected merge completed 2026-09-27T18:11:31Z)
- unresolved review threads immediately before merge: 0
- merge executed under the operator credential following an explicit exact-head approval naming `f4e24601c6c2821cbb394d09b0d9890e17a2eb16`; no cross-head approval reuse is claimed

### 2.1 Review lanes for PR 508, recorded honestly

```text
Jev bounded review         CLI 0.3.2 with model jev-1.13.0 (TypeSafe provider): a design-stage
probe, a final-diff probe, and a post-fix re-run on the FINAL effective head f4e2460. Nine
yes/no probes over synthetic-only design facts in each run; no PHI, real patient data,
secrets, credentials, API keys, production data, or sealed MRL material sent. Final results,
all no: stale-state acceptance 0.04, provenance bypass 0.04, cross-workspace leakage 0.04,
unsupported-state promotion 0.03, malicious-content authority 0.02, export-containment
escape 0.09, hidden network/model 0.11, security-label loss 0.17 (no security labels exist
in this unit's scope; envelopes carry opaque digested payloads), identity collision 0.03.
Jev screening only; not claimed as a merge gate.
Alibaba Open Code Review   Tool installation verified on this host: open-code-review v1.12.9
(windows/amd64, build 2026-09-22) at C:/Users/Shehr/.opencodereview/bin/ocr.exe, matching the
official release manifest. Full LLM review lane blocked at the provider-authority boundary: the
only configured provider (anthropic) has no API key, no zero-cost provider credential exists,
and paid compute is not authorized, so no review content was sent anywhere. The official no-LLM
lanes were executed instead (review preview over the exact base/head diff: 4 source files
reviewable, 2 test files excluded as default_path; delegate rule lane plus per-file rules check
for the Python rule group), and those rules were applied to the final diff by host-agent review
with no blocking findings. The two CI findings below were caught by CI gates, fixed forward-only,
and re-qualified. No OCR source, workflow, dependency, or configuration was added to MESC.
No OCR review claimed beyond this record.
host-agent review          Performed on the complete final diff against the official rule content,
covering authority boundaries, deterministic uuid5 manifest/envelope identities, allowlist and
capability enforcement, retry/offline/malformed fail-closed behavior, secret-absence design,
provenance and audit correctness, deletion-marker semantics consistent with the store
architecture, inert payloads, workspace isolation, and the absence of network, remote
retrieval, model, PHI, production, and EHR/external-write scope. No defects carried to commit.
reviewing GitHub bots      no blocking bot findings recorded.
```

### 2.2 Repairs inside PR 508

PR 508 holds three commits, forward-only with two repair commits and no history rewrite:

```text
6e0b4fc  feat: implement CW-014 read-only connector framework
c7e1511  fix: annotate CW-014 test helpers for strict mypy
f4e2460  fix: replace getattr with direct attribute access in CW-014 fetch
```

Repair 1: CI strict mypy refused unannotated test helpers (`no-untyped-def` /
`no-untyped-call`), unlike the fully annotated CW-013 test precedent. All test helpers were
annotated; method assignment was replaced with dedicated transport classes.

Repair 2: CI shard 3 (both pythons) failed the CW-001/CW-004 boundary-guard tests because
`fetch_envelope` used `getattr` for transport capability lookup, and reflective capability
access is forbidden workspace-wide. The lookup now uses direct attribute access with an
explicit `AttributeError`-to-`ConnectorInputError` cause chain.

Ruff check, ruff format, `git diff --check`, strict mypy, the CW-014 suites (15/15), and the
two guard suites were verified locally before each commit. No rebase, no force-push
(fast-forwards `6e0b4fc..c7e1511..f4e2460`), no history rewrite, no protection bypass, no
frozen MRL mutation.

### 2.3 Synthetic-only path qualification

```text
CONNECTOR_NAMESPACE = c014ec70-0004-4000-8000-000000000014 (uuid5 namespace)
CONNECTOR_REVISION = connector-envelope-00000001
PRODUCER_VERSION = cw014-v1
DERIVATION_METHOD = cw014-deterministic-connector
DERIVATION_METHOD_VERSION = 1
SCHEMA_VERSION = cw014-connector/1
ENVELOPE_SCHEMA_VERSION = 1
REAL_MODEL_AUTHORITY = NONE
WEIGHTS = NONE DOWNLOADED
REMOTE_RETRIEVAL = NONE
NETWORK_CONNECTORS = NONE (fixture transports only)
PRODUCTION_CREDENTIALS = NONE
PAID_COMPUTE = NONE
EXTERNAL_WRITE = NONE EXISTS
```

Connector admission is mechanical validation of caller-supplied manifests and fixture responses
against the read-only contract; fixture and operator identities are deterministic test values
only and are not a real-model decision. No real model is used to fetch, classify, score, or
generate workspace content. Transports are in-memory test doubles holding synthetic payloads;
the one test secret never enters the module, the store, or the audit trail (test-proven).

### 2.4 Negative and superseded evidence

```text
superseded GitHub heads   6e0b4fc8152b93053d0755d5f687b009fc0de06a (CI 36334163865 FAILURE on
strict mypy; CodeQL 36334163837 SUCCESS) and c7e15110460bc062240da1cc9c129c25ff74cb7f
(CI 36334455265 FAILURE on the boundary-guard getattr ban; CodeQL 36334455310 SUCCESS);
both preserved, neither claimed as the merged head, none deleted
cancelled or stale runs   none claimed as success
local Windows limits      default pytest temp root may deny access on this host; local re-verification uses an explicit writable basetemp where required; local mypy is newer than the CI-pinned version and may flag out-of-scope workspace files (CI py3.11/py3.12 authoritative); symlink/filemode MRL tests fail locally on Windows for privilege reasons and pass on Linux CI
MRL binding note          no MRL-0809-frozen source was touched by this increment, so no MRL live-binding step applies beyond the passing static gate
```

No MRL-0809-frozen source (pyproject.toml, uv.lock, workflows, MRL modules, MRL evidence) was touched by this increment, and no MRL contract was mutated.

## 3. Protected merge

PR 508 merged through the protected path on 2026-09-27 (mergedAt 2026-09-27T18:11:31Z,
ordinary merge commit with expected parents, under the operator credential following explicit
exact-head approval). No squash, no rebase, no force-push, no history rewrite, no gate
weakening, no protection bypass.

```text
BASE  = 296308db2da2ef4badac8566eb8954ad9589b891
HEAD  = f4e24601c6c2821cbb394d09b0d9890e17a2eb16
MERGE = 5ee3a52de8e2f8d30477e089edc6b112be62a160
TREE  = 31f183f6cd0ec37d307c2a137bb0bd33496c8f77
PARENTS = 296308db2da2ef4badac8566eb8954ad9589b891, f4e24601c6c2821cbb394d09b0d9890e17a2eb16
```

The merge tree equals the qualified head tree: no unexpected mutation occurred at merge time.

## 4. Fresh-main qualification

Workflows triggered by merge commit `5ee3a52de8e2f8d30477e089edc6b112be62a160`:

- CI run `36339729752` (CI): SUCCESS
- CodeQL run `36339729758` (CodeQL): SUCCESS
- Optional Extras / Backends run `36339729760`: SUCCESS
- Hugging Face Publication Qualification run `36339729750`: SUCCESS

All four fresh-main gates are complete and SUCCESS on the merge commit.

## 5. What CW-014 delivered

```text
read-only capabilities       exactly 3 admitted capabilities (read-fhir, read-file,
read-directory); no write capability exists anywhere; unknown, repeated, or write-like
capabilities refused, never truncated
capability manifest          caller-held validated values binding connector uuid5 identity,
capability subset, non-empty fixture:// destination allowlist, timeout 1..60000 ms, retries
0..5, offline flag, and an opaque credential reference; manifests are never stored objects
destination allowlist        fixture scheme only with named fixture, no empty segments, no
upwards traversal, no backslash; non-allowlisted fetches refused before touching transport
credential design            secret bytes never enter the module; audit metadata records only
whether a credential reference was bound; the fixture secret appears in no stored bytes and
no audit event bytes (test-proven)
timeout/retry bounds         validated bounds passed to the transport; temporary failures
retried at most max_retries times then refused; permanent failures refused immediately
offline state                offline connectors refused without touching the transport (call
count test-proven); no silent fallback, no queued send
stale/version metadata       envelopes carry source version and retrieval instant; envelope
identity binds the source version so a new version yields a new identity; re-fetch collides
instead of overwriting; reads re-verify digests and bindings; deletions preserve audit events
malformed responses          non-object, member-missing, oversized, over-long, and
bad-version/bad-time responses refused at named stages
writes disabled              no write capability, no write entry point, no write transport
method; no CONNECTOR_WRITE audit event is emitted anywhere (trail scan test-proven)
inert content                payloads stored as frozen tuples, never evaluated or executed;
malicious instruction strings remain data and grant no capability
provenance                 every envelope stored with CW-003 provenance (producer IMPORT,
source kind connector_response, digest) and a redacted CONNECTOR_READ audit event;
workspace binding checked on every entry point
no network connectors      no network, remote retrieval, production credential, model
download, or cloud path exists in this slice; real endpoint access remains separately
authorized and NOT AUTHORIZED here
tests                      CW-014 suites in tests/test_clinical_workspace_connector_v1.py (7 acceptance tests) and tests/test_clinical_workspace_connector_adversarial_v1.py (8 adversarial tests) plus implementation in apps/workspace/src/medscale_workspace/connector.py with error, identity, and provenance extensions
```

## 6. Recorded limitations

```text
bounds               destinations and queries at most 512 chars, versions at most 64 chars,
names and identifiers at most 128 chars, strings at most 1024 chars, lists at most 128
members, depth at most 8, envelopes at most 32768 canonical bytes; larger or unadmitted
inputs refused, not truncated
fixture-only         every destination must use the fixture scheme; the transport contract is
duck-typed with a single fetch method; a transport raising an undeclared exception fails
loud, never silent
no inference         no terminology validation, no semantic support judgment, no response
ranking or relevance claim; a well-formed response is not automatically correct
no real endpoints    production EHR/FHIR servers, SMART-on-FHIR, credentials, and network
policy are absent by design; this framework grants no real connector authority
no quality claim     no support-quality, clinical quality, or production readiness claim granted
by this unit
no real model        fixture and operator identities are deterministic test values, not a
real-model decision; any model-backed enhancement needs separate authority
prior limitations    platform secret-storage provider, whole-store rollback, plaintext metadata
visibility, secure_delete scope, audit write-once scope, tail-truncation head digest, append
cost, ASR link-based export escape, draft link-based export escape, review link-based export
escape, lexical-overlap ranking, snapshot bounds, graph view bounds, path depth bounds, and
lexical export-path containment remain as previously declared unless explicitly resolved
elsewhere
```

## 7. Result

```text
CW_014 = CLOSED_CANONICAL (on closeout merge + fresh-main; see section 8)
CW-001 through CW-014 = CLOSED_CANONICAL
CW-015, CW-016, CW-017 = ELIGIBLE_NOT_ACTIVATED
  (each depends only on CLOSED_CANONICAL units; each requires its own separate activation)
CW-018, CW-019, CW-020 = BLOCKED_DEPENDENCY
CW-021 = BLOCKED_DEPENDENCY plus a required separate explicit Founder and governance clinical-pilot authorization
Issue 507 = close with this closeout (activation fulfilled; do not rewrite historical activation body)
Issue 429, 450, 464 = separately governed and untouched
MRL-0809 (429, 450) = separately governed and untouched
```

CW-014 grants no PHI ingestion, no real patient import, no clinical production use, no real EHR write, no external write, no network-connector admission, no remote retrieval, no autonomous tool execution, no Workspace-data training or research evaluation or admission, no model promotion, no external publication, no paid compute, no MRL contract mutation, and no new MRL Stage-4 attempt.

## 8. Explicit non-grants preserved

```text
CW_014 = CLOSED_CANONICAL (on closeout merge + fresh-main)
CW_014_MODEL_AUTHORITY = NONE
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

No real model has been selected or admitted. No support or clinical quality is claimed. No production readiness is granted. Deterministic connector mechanics are a correctness property, not a quality claim.
