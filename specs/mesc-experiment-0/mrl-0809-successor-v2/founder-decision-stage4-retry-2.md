# Founder decision — MRL-0809 successor v2 Stage-4 retry-2

Status: ACCEPTED / BOUNDED_RUNTIME_AUTHORITY / EFFECTIVE_AFTER_CANONICAL_FRESH_MAIN

Decision ID: `FD-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-2`

Date prepared: 2026-10-03

Date accepted: 2026-10-03

This packet records the separate Founder decision required after the BMM portability
repair became canonical and fresh-main qualified. Founder acceptance is recorded
below. Runtime execution remains disabled until this accepted decision
implementation is itself canonical and fresh-main qualified.

Machine-readable form:
`../mrl-0809-successor-v2-stage4-retry-2-authorization.json`.

## Canonical BMM-repair binding

```text
CANONICAL_BMM_REPAIR_MERGE_SHA = 07a20c8a01a6b3562b98fa48fbd19ed11be7a8eb
CANONICAL_BMM_REPAIR_MERGE_TREE = 0ae92820f266bf17a23507e3286ae33f968a2972
BMM_REPAIR_STATIC_MANIFEST_SHA256 = 1868f5501903b921ace2db47511b89c50b0017136e3ebe4180a7493fdc395728
DEPENDENCY_LOCK_SHA256 = 6fa0e0b49d19e305032ecd04940db0b9e252dd23b6fbec588b224f739048efc4
PRESERVED_REPAIR_STATIC_MANIFEST_SHA256 = d943a8bc4fbc7f5c8baf8716dd206b6262966c43c37a7a257645518a620f2c7d
CONSUMED_RETRY_1_FAILURE_RECORD_SHA256 = 6b8ed146e82b705bc536530e60a10b0c81c32f3ab3dd16f4155562706a9ecf0f
```

The bound BMM repair was fresh-main qualified by CI run `37138797577`, CodeQL
run `37138797582`, Optional Extras / Backends run `37138797581`, Hugging Face
Publication Qualification run `37138797607`, and local BMM static gates on
Python 3.11 and 3.12. PR #534 exact-head tree and the canonical merge tree are
both `0ae92820f266bf17a23507e3286ae33f968a2972`.

## Historical attempts remain immutable

The original successor-v2 attempt and retry-1 remain historical FAIL evidence.
Retry-1 remains Qwen stage PASS / Qwen probe FAIL with failure class
`SANDBOX_TRITON_CUDA_HELPER_BUILD_FAILURE`, CUDA OOM false, and Gemma NOT_RUN.
These facts must not be overwritten, relabeled, erased, or converted into PASS.

## Runtime grant

After the effectiveness boundary below is satisfied, exactly one launch is
authorized:

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

The frozen candidate roster and runtime representation remain:

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

The canonical BMM compatibility preflight must run first inside the governed
isolation boundary.

## Fail-stop and launch-consumption rule

Exactly one hosted launch invocation is authorized. No automatic retry or
relaunch is authorized.

```text
FIRST_OPERATION = BMM_COMPATIBILITY_PREFLIGHT
BMM_PREFLIGHT_FAIL => IMMEDIATE_STOP
FIRST_CANDIDATE_FAILURE => IMMEDIATE_STOP
NO_SECOND_CANDIDATE_AFTER_FIRST_CANDIDATE_FAILURE
NO_AUTOMATIC_RETRY
NO_AUTOMATIC_RELAUNCH
```

The launch authorization is exhausted once the hosted launch is invoked,
including provider/session or BMM-preflight infrastructure failure before a
candidate probe-start boundary. The runtime controller must persist a
launch-consumption receipt before invoking the BMM Stage-4 sequence. Any
subsequent hosted launch requires a new explicit Founder decision.

## Non-grants

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

## Accepted implementation sequence

```text
FOUNDER_ACCEPTANCE
-> RECORD EXACT ACCEPTANCE STATEMENT
-> CREATE FAIL-CLOSED MACHINE-READABLE RETRY-2 AUTHORIZATION
-> CREATE RETRY-2 AUTHORITY GATE AND TESTS
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

Blocked review lanes remain blocked; no review PASS may be fabricated.

## Effectiveness boundary

Founder acceptance alone is not executable runtime authority. Before the
accepted retry-2 implementation is canonical and fresh-main qualified:

```text
RUNTIME_EXECUTION = NOT_YET_EFFECTIVE
```

## Founder acceptance

Accepted explicitly by the Founder on 2026-10-03 with the exact statement:

```text
I approve FD-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-2, bound to canonical BMM repair merge 07a20c8a01a6b3562b98fa48fbd19ed11be7a8eb, tree 0ae92820f266bf17a23507e3286ae33f968a2972, and BMM repair static manifest SHA-256 1868f5501903b921ace2db47511b89c50b0017136e3ebe4180a7493fdc395728. I authorize exactly one further zero-cost STANDARD-T4 Stage-4 runtime-feasibility launch after the accepted retry-2 decision implementation is canonical and fresh-main qualified. The prior successor-v2 attempts remain historical FAIL evidence and must not be overwritten or relabeled. No automatic relaunch is authorized.
```

This acceptance grants no authority beyond the single bounded launch above.
