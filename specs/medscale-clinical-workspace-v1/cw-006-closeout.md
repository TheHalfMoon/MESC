# CW-006 Canonical Closeout Evidence

- **Task:** CW-006 -- Local ASR adapter
- **Status:** `CLOSED_CANONICAL`
- **Parent issue:** [#480](https://github.com/TheHalfMoon/MESC/issues/480) -- CW-006 activation
- **Implementation PR:** [#482](https://github.com/TheHalfMoon/MESC/pull/482) -- `feat/cw-006-local-asr-adapter`
- **Qualified intermediate head:** `c61370664488e4ad3e274ec61a233c46652ec6de`
- **Intermediate head tree:** `b1247dce54a5c74a76380f5b5309a7d65cc376e4`
- **Qualified final head:** `cc7ace96ce9b827563862eb232b33d19a26a237b`
- **Qualified final tree:** `f70d02dffec7807e1278882546f11edf8ab93594`
- **Base:** `75c4bbbc480e23432016ed1350e4385a774e4406` (tree `4124904c76bd9ad2c037ba85dc5a0b13cdd02d55`)
- **Canonical merge SHA:** `e040c9f68146435f48a548d89fbe1c1c5158a2d9`
- **Canonical merge tree:** `f70d02dffec7807e1278882546f11edf8ab93594`
- **Merge parents:** `75c4bbbc480e23432016ed1350e4385a774e4406` (previous canonical `main`), `cc7ace96ce9b827563862eb232b33d19a26a237b` (qualified final head)
- **Contracts:** [Clinical Workspace V1](README.md) sections 4.1, 4.2 boundary, 11, 12, 13, 14, 15, [data security](data_security.md), [capability map](capability_map.md), [ADR-0040](../../docs/adr/0040-local-asr-model-and-reference-runtime.md) as accepted under R6 with no amendment, [ADR-0040 ratification](adr-0040-founder-ratification.md), [model registry](../../docs/models/model_registry.md)

This record documents closure evidence that already exists on canonical `main`; it creates no clinical, PHI, training, publication, research-admission, production, or remote runtime authority.

## 1. Governance state entering implementation

```text
CW-001, CW-002, CW-003, CW-004, CW-005 CLOSED_CANONICAL
CW-005 closeout merge                 0645cd770062f2af0d10fd047f946d9201c8ba41
CW-006                                activated under Issue 480 on 2026-09-22 as the single active unit under R4
gating contracts                      ADR-0040 proposed in PR 481 and accepted by the Founder under R6 on 2026-09-22 with no amendment; implementation authority under Issue 480 only within the ADR-0040 protected local-only fail-closed contract
model contract                        openai/whisper-large-v3-turbo at 41f01f3fe87f28c78e2fbf8b568835947dd65ed9 (mit) with reference runtime transformers 5.16.1 and torch 2.13.0
authorization                         one-time zero-cost Colab qualification authorized for CW-006 only in cw-006-colab-qualification-authorization.md; production remote ASR remains NOT_AUTHORIZED
new dependencies                      optional asr-local group only in apps/workspace scope (torch==2.13.0, transformers==5.16.1); root pyproject.toml and uv.lock untouched; basic Workspace shell remains installable and testable without ASR dependencies
Issues 429, 450, 464                 separately governed and untouched
```

## 2. Pre-merge exact-head evidence

Intermediate head `c61370664488e4ad3e274ec61a233c46652ec6de` on base `75c4bbbc480e23432016ed1350e4385a774e4406`:

- CI run `35826399366`: SUCCESS
- CodeQL run `35826399421`: SUCCESS
- CodeRabbit: SUCCESS with manual review notice and no finding
- cubic reviewer: NEUTRAL with no finding
- required checks: quality py3.11 PASS, quality py3.12 PASS, analyze python PASS
- review threads: 0; allowed merge methods: merge only

Final head `cc7ace96ce9b827563862eb232b33d19a26a237b` on the same base:

- CI run `35879795961` (CI, pull_request event): SUCCESS -- static py3.11, static py3.12, all eight pytest shard jobs py3.11 and py3.12, quality py3.11, quality py3.12
- CodeQL run `35879796101` (CodeQL, pull_request event): SUCCESS -- analyze python with no new alerts
- check runs: quality py3.11 SUCCESS, quality py3.12 SUCCESS, static py3.11 SUCCESS, static py3.12 SUCCESS, analyze python SUCCESS, CodeQL SUCCESS, cubic NEUTRAL with no finding, all pytest shards SUCCESS
- mergeable MERGEABLE with mergeStateStatus CLEAN at merge time
- unresolved review threads immediately before merge: 0

### 2.1 Review lanes for PR 482, recorded honestly

```text
Jev bounded review         Authorized screening only; no PHI, real patient audio, credentials, keys, secrets, production clinical payloads, or sealed MRL material sent. Results are screening only and independently verified.
Alibaba Open Code Review   Local no-LLM paths only where applicable; no repository content sent to a remote model endpoint. Markdown exclusions reviewed manually under the host lane. No OCR LLM review claimed unless an endpoint performed it.
host-agent review          Performed on the complete diff at the qualified head, covering adapter manifest verification, local-files-only behavior, missing artifact failure, revision mismatch failure, timestamp preservation, SUCCESS versus PARTIAL versus FAILED typing, workspace and session binding, provenance and audit spine reuse, classification and no-backflow guard preservation, boundary guard, dependency scope, and frozen MRL evidence.
reviewing GitHub bots      cubic NEUTRAL with no finding; CodeRabbit pass with manual-review notice and no finding.
```

### 2.2 Repairs inside PR 482

PR 482 holds six commits. Forward-only repairs:

```text
4408361  feat: implement CW-006 real local Transformers backend with guard scope
ad733e5  fix: remove trailing blank line blocking CI diff check
bc4c2b5  fix: satisfy Ruff lint and format for exact-head CI
c613706  fix: satisfy Mypy strict for exact-head CI
cc7ace9  docs: record CW-006 real-model runtime qualification evidence
```

No rebase, no force-push, no history rewrite, no protection bypass, no frozen MRL mutation.

### 2.3 Real-model runtime-path qualification

Recorded in [cw-006-real-model-qualification.md](cw-006-real-model-qualification.md) against exact head `c61370664488e4ad3e274ec61a233c46652ec6de`:

```text
REAL_MODEL_RUNTIME_QUALIFICATION = PASS for the real runtime path only
MODEL_ID = openai/whisper-large-v3-turbo
FULL_IMMUTABLE_REVISION = 41f01f3fe87f28c78e2fbf8b568835947dd65ed9
MODEL_LICENSE = mit
REFERENCE_RUNTIME = transformers 5.16.1 with torch 2.13.0
WEIGHT_SHA256 = 542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1
WEIGHT_SIZE = 1617824864 bytes
FIXTURE_LICENSE = cc-by-4.0
FIXTURE_PHI = NONE
PAID_COMPUTE = NONE
network denial active for backend and inference = true
missing snapshot fails explicitly = true
```

### 2.4 Negative and superseded evidence

```text
superseded GitHub heads   c014b2e, 4408361, ad733e5, bc4c2b5, c613706 superseded by cc7ace9; no superseded head claimed as success
cancelled or stale runs   none claimed as success
local Windows limits      default pytest temp root may deny access on this host; local re-verification uses an explicit writable basetemp where required; Unix-only MRL sandbox test remains untouched
MRL binding note          CI static jobs passed the MRL canonical closeout evidence live binding step on the exact head; local runs without the CI checkout context are NOT claimed as evidence
```

No MRL-0809-frozen source (pyproject.toml, uv.lock, workflows, MRL modules, MRL evidence) was touched by this increment, and no MRL contract was mutated.

## 3. Protected merge

PR 482 merged through the protected path on 2026-09-23 (mergedAt 2026-09-23T16:08:30Z, by TheHalfMoon, ordinary merge commit). No bypass, no force-push, no rebase, no history rewrite, no gate weakening. The ruleset allows only merge and requires thread resolution plus quality py3.11, quality py3.12, and analyze python with strict up-to-date policy; all held at merge time. GitHub PGP signature verified true with reason valid.

```text
BASE  = 75c4bbbc480e23432016ed1350e4385a774e4406
HEAD  = cc7ace96ce9b827563862eb232b33d19a26a237b
MERGE = e040c9f68146435f48a548d89fbe1c1c5158a2d9
TREE  = f70d02dffec7807e1278882546f11edf8ab93594
PARENTS = 75c4bbbc480e23432016ed1350e4385a774e4406, cc7ace96ce9b827563862eb232b33d19a26a237b
```

## 4. Fresh-main qualification

Workflows triggered by merge commit `e040c9f68146435f48a548d89fbe1c1c5158a2d9`:

- CI run `35886669886` (CI): SUCCESS
- CodeQL run `35886670057` (CodeQL): SUCCESS
- Optional Extras / Backends run `35886669943`: SUCCESS
- Hugging Face Publication Qualification run `35886669930`: SUCCESS

All four fresh-main gates are complete and SUCCESS on the merge commit.

## 5. What CW-006 delivered

```text
manifest             deterministic local manifest binding MODEL_ID, FULL_IMMUTABLE_REVISION, MODEL_LICENSE, REFERENCE_RUNTIME, WEIGHT_SHA256, WEIGHT_SIZE, CONFIG_BLOB, PROCESSOR_BLOB, TOKENIZER_BLOB; manifest verified before any load; mutable main and latest refused
local-only           trust_remote_code false with local_files_only true; no runtime download; no Hub acquisition; no network fallback; no remote inference; no cloud fallback; no audio or transcript telemetry
fail-closed          missing snapshot fails explicitly; revision mismatch fails explicitly; network attempt fails closed; malformed timestamps fail validation; wrong workspace or session binding fails validation
typing               explicit SUCCESS versus PARTIAL versus FAILED with workspace, session, input, model, revision, runtime, language, segment, and timestamp binding
timestamps           preservation required; malformed or impossible ordering or non finite values fail validation
provenance           transcripts stored with CW-003 provenance and audit spine; generated content references at least one source; recorded digests re-verified
isolation            workspace and session binding checked on every load and validation; foreign workspace or session fails closed
guard scope          CW-002 protected storage, CW-003 provenance and audit, CW-004 classification and no-backflow reused without weakening; optional asr-local group only in apps/workspace scope
tests                CW-006 suites in tests/test_clinical_workspace_asr_v1.py, tests/test_clinical_workspace_asr_adversarial_v1.py, tests/test_clinical_workspace_asr_transformers_v1.py plus storage adversarial guard coverage
```

## 6. Recorded limitations

```text
bounds               audio payloads capped at 65536 bytes; transcripts capped at 65536 chars; segments capped at 256; larger inputs refused, not truncated
retention            session-scoped retention class v1 only; other classes or versions fail closed and remain owned by later units
concurrency          revision collisions fail closed as replay or concurrency errors; no multi-writer merge
no microphone        no live microphone, audio device, streaming, or codec path in this unit; CW-005 lifecycle remains independently testable without CW-006
no quality claim     no WER, accuracy, language quality, or clinical quality claim granted by this unit
platform             qualification runner fixes were notebook-only Colab compatibility repairs; they were not ported into the governed application source
Issue 464 items      Workspace strict mypy coverage and version single-sourcing remain separate and are not bundled here
prior limitations    platform secret-storage provider, whole-store rollback, plaintext metadata visibility, secure_delete scope, audit write-once scope, tail-truncation head digest, append cost, and ASR link-based export escape remain as previously declared unless explicitly resolved elsewhere
```

## 7. Result

```text
CW_006 = CLOSED_CANONICAL
CW-009, CW-011, CW-013, CW-016, CW-017 = ELIGIBLE_NOT_ACTIVATED
  (each depends only on CLOSED_CANONICAL units; each requires its own separate activation)
CW-007 = ELIGIBLE_NOT_ACTIVATED after this closeout
  (depends on CW-003, CW-004, CW-006, all now CLOSED_CANONICAL; eligibility is not implementation authority; separate activation still required before any implementation begins)
CW-008, CW-010, CW-012, CW-014, CW-015, CW-018, CW-019, CW-020 = BLOCKED_DEPENDENCY
CW-021 = BLOCKED_DEPENDENCY plus a required separate explicit Founder and governance clinical-pilot authorization
Issue 480 = close with this closeout (activation fulfilled)
Issue 464 = open, separate CW-001 follow-up work unit
MRL-0809 (429, 450) = separately governed and untouched
```

CW-006 grants no PHI ingestion, no real patient import, no clinical production use, no real EHR write, no autonomous clinical action, no remote application-model egress, no Workspace-data training or research evaluation or admission, no model promotion, no external publication, no paid compute, no MRL contract mutation, and no new MRL Stage-4 attempt.

## 8. Explicit non-grants preserved

```text
CW-006 = CLOSED_CANONICAL
REAL_MODEL_RUNTIME_QUALIFICATION = PASS
PRODUCTION_AUTHORITY = LOCAL_ONLY FAIL_CLOSED
PHI_INGESTION = NOT_AUTHORIZED
REAL_PATIENT_AUDIO = NOT_AUTHORIZED
CLINICAL_PRODUCTION_USE = NOT_AUTHORIZED
EHR_WRITE = NOT_AUTHORIZED
REMOTE_ASR = NOT_AUTHORIZED
AUTOMATIC_MODEL_DOWNLOAD_IN_PROTECTED_RUNTIME = NOT_AUTHORIZED
TRAINING = NOT_AUTHORIZED
FINE_TUNING = NOT_AUTHORIZED
WEIGHT_MUTATION = NOT_AUTHORIZED
WER = NOT_CLAIMED
ACCURACY = NOT_CLAIMED
CLINICAL_QUALITY = NOT_CLAIMED
```

Production authority remains LOCAL_ONLY and FAIL_CLOSED under existing governance.
