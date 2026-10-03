# Founder decision proposal — MRL-0809 successor v2 Stage-4 retry-2

Status: PROPOSED / NO_RUNTIME_AUTHORITY

Decision ID: `FD-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-2`

Date prepared: 2026-10-03

This packet proposes the separate Founder decision required after the BMM portability repair became canonical and fresh-main qualified. It is not accepted by repository inclusion, branch creation, pull-request creation, or any generic continuation instruction.

No hosted Stage-4 execution is authorized unless and until the Founder explicitly accepts this exact decision, the accepted decision is converted into fail-closed machine-readable authority, that accepted authority is independently reviewed and exact-head qualified, and the accepted packet becomes canonical and fresh-main qualified.

## Canonical BMM-repair binding

This proposal is bound to exactly the following canonical repaired state:

```text
CANONICAL_BMM_REPAIR_MERGE_SHA = 07a20c8a01a6b3562b98fa48fbd19ed11be7a8eb
CANONICAL_BMM_REPAIR_MERGE_TREE = 0ae92820f266bf17a23507e3286ae33f968a2972
BMM_REPAIR_STATIC_MANIFEST_SHA256 = 1868f5501903b921ace2db47511b89c50b0017136e3ebe4180a7493fdc395728
DEPENDENCY_LOCK_SHA256 = 6fa0e0b49d19e305032ecd04940db0b9e252dd23b6fbec588b224f739048efc4
PRESERVED_REPAIR_STATIC_MANIFEST_SHA256 = d943a8bc4fbc7f5c8baf8716dd206b6262966c43c37a7a257645518a620f2c7d
CONSUMED_RETRY_1_FAILURE_RECORD_SHA256 = 6b8ed146e82b705bc536530e60a10b0c81c32f3ab3dd16f4155562706a9ecf0f
```

Fresh-main qualification on that exact merge completed successfully:

```text
CI_RUN = 37138797577 / SUCCESS
CODEQL_RUN = 37138797582 / SUCCESS
OPTIONAL_EXTRAS_RUN = 37138797581 / SUCCESS
HF_PUBLICATION_RUN = 37138797607 / SUCCESS
LOCAL_BMM_STATIC_GATE_PY311 = PASS
LOCAL_BMM_STATIC_GATE_PY312 = PASS
```

The exact-head tree of PR #534 and the canonical merge tree are identical: `0ae92820f266bf17a23507e3286ae33f968a2972`.

## Historical attempts remain immutable

The original successor-v2 attempt and the separately authorized retry-1 remain historical evidence and are not overwritten, relabeled, erased, or converted into PASS.

The retry-1 result remains:

```text
PRIOR_RETRY_1 = FAIL
PRIOR_RETRY_1_QWEN_STAGE = PASS
PRIOR_RETRY_1_QWEN_PROBE = FAIL
PRIOR_RETRY_1_QWEN_FAILURE_CLASS = SANDBOX_TRITON_CUDA_HELPER_BUILD_FAILURE
PRIOR_RETRY_1_QWEN_CUDA_OOM_OBSERVED = FALSE
PRIOR_RETRY_1_GEMMA_STAGE = NOT_RUN
PRIOR_RETRY_1_GEMMA_PROBE = NOT_RUN
```

The retry-1 failure does not establish T4 capacity infeasibility for the frozen Qwen candidate.

## Proposed runtime grant

If explicitly accepted by the Founder and only after the effectiveness boundary below is satisfied, this decision would authorize exactly one new zero-cost Stage-4 runtime-feasibility launch under the following frozen envelope:

```text
NEW_STAGE4_LAUNCHES_AUTHORIZED = 1
PROVIDER = GOOGLE_COLAB_FREE
GPU = Tesla T4
MACHINE_SHAPE = STANDARD
MONETARY_COST = 0
INPUT = SYNTHETIC_ONLY
SCIENTIFIC_CORPUS_ACCESS = FALSE
SEALED_TIER3_ACCESS = FALSE
SCIENTIFIC_RQ1_EXECUTION = FALSE
```

The launch remains bounded to the already-frozen successor-v2 candidate roster and runtime representation:

```text
CANDIDATE_1 = Qwen/Qwen3-8B
CANDIDATE_1_REVISION = b968826d9c46dd6066d109eabc6255188de91218
CANDIDATE_2 = google/gemma-4-12B-it
CANDIDATE_2_REVISION = 707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7
RUNTIME_REPRESENTATION = bitsandbytes-nf4-v1
QUANTIZATION = NF4_DOUBLE_QUANT_FLOAT16_COMPUTE
MODEL_DEVICE_POLICY = CUDA_DEVICE_0_ONLY
MAX_PEAK_GPU_MEMORY = 12_GiB
TRUST_REMOTE_CODE = FALSE
ISOLATED_WORKER_NETWORK = FALSE
```

The BMM portability preflight added by the canonical repair must execute first, inside the governed isolation boundary, before any candidate staging or canonical probe-start marker.

## Fail-stop and launch-consumption rule

The proposed authority permits one launch invocation only. No automatic relaunch is permitted under this decision.

The runtime path must enforce:

```text
FIRST_OPERATION = BMM_COMPATIBILITY_PREFLIGHT
BMM_PREFLIGHT_FAIL => IMMEDIATE_STOP
FIRST_CANDIDATE_FAILURE => IMMEDIATE_STOP
NO_SECOND_CANDIDATE_AFTER_FIRST_CANDIDATE_FAILURE
NO_AUTOMATIC_RETRY
NO_AUTOMATIC_RELAUNCH
```

If the BMM preflight or provider/session startup fails before any canonical candidate probe-start boundary is crossed, the scientific attempt is classified as infrastructure non-execution, but the single launch authorization is nevertheless exhausted. Any subsequent hosted launch requires a new explicit Founder decision.

If execution crosses the canonical probe-start boundary for a candidate, the scientific attempt is consumed. Any genuine model/load/probe/runtime failure after that boundary records FAIL and terminates the launch.

## Non-grants

The proposed grant must not be interpreted to authorize any of the following:

```text
MODEL_SUBSTITUTION = NOT_AUTHORIZED
REVISION_SUBSTITUTION = NOT_AUTHORIZED
GPU_CLASS_SUBSTITUTION = NOT_AUTHORIZED
QUANTIZATION_SUBSTITUTION = NOT_AUTHORIZED
CPU_OFFLOAD = FALSE
DISK_OFFLOAD = FALSE
AUTO_DEVICE_MAP = FALSE
OFFLOAD_FALLBACK = NOT_AUTHORIZED
PAID_COMPUTE = NOT_AUTHORIZED
TRAINING = FALSE
WEIGHT_MUTATION = FALSE
MODEL_PROMOTION = FALSE
SCIENTIFIC_RQ1_EXECUTION = NOT_AUTHORIZED
MRL0809_CLOSEOUT = NOT_AUTHORIZED_BY_THIS_DECISION
MRL0899_CLOSEOUT = NOT_AUTHORIZED_BY_THIS_DECISION
```

No scientific corpus, sealed Tier-3 data, final-role data, training labels, or model-weight mutation may be introduced by this runtime-feasibility launch.

## Acceptance and implementation sequence

If the Founder accepts this proposal, repository implementation must follow this order:

```text
FOUNDER_ACCEPTANCE
-> RECORD EXACT ACCEPTANCE STATEMENT
-> CREATE FAIL-CLOSED MACHINE-READABLE RETRY-2 AUTHORIZATION
-> CREATE/UPDATE RETRY-2 AUTHORITY GATE AND TESTS
-> LOCAL TESTS
-> REGRESSION TESTS
-> JEV
-> ALIBABA OPEN CODE REVIEW LOCAL OFFICIAL LANES
-> HOST REVIEW
-> CI
-> CODEQL
-> OPTIONAL EXTRAS / BACKENDS
-> HF PUBLICATION QUALIFICATION
-> EXACT-HEAD QUALIFICATION
-> FOUNDER MERGE APPROVAL
-> ORDINARY MERGE COMMIT
-> FRESH-MAIN REQUALIFICATION
-> EXACT CANONICAL AUTHORITY CHECK
-> ONE HOSTED STAGE-4 LAUNCH
```

Jev and Alibaba Open Code Review outcomes must be recorded exactly. A blocked provider lane is recorded as blocked; no review PASS may be fabricated.

## Effectiveness boundary

Before the accepted decision implementation itself is canonical and fresh-main qualified:

```text
RUNTIME_EXECUTION = NOT_AUTHORIZED
```

Repository preparation, tests, review, CI, and decision implementation do not themselves grant hosted runtime authority.

## Required Founder acceptance statement

To accept this exact proposal, the Founder must explicitly state:

```text
I approve FD-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-2, bound to canonical BMM repair merge 07a20c8a01a6b3562b98fa48fbd19ed11be7a8eb, tree 0ae92820f266bf17a23507e3286ae33f968a2972, and BMM repair static manifest SHA-256 1868f5501903b921ace2db47511b89c50b0017136e3ebe4180a7493fdc395728. I authorize exactly one further zero-cost STANDARD-T4 Stage-4 runtime-feasibility launch after the accepted retry-2 decision implementation is canonical and fresh-main qualified. The prior successor-v2 attempts remain historical FAIL evidence and must not be overwritten or relabeled. No automatic relaunch is authorized.
```

Until that exact decision is explicitly accepted, this file remains a proposal and grants no runtime authority.
