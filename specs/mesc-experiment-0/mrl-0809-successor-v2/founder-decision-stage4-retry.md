# Founder decision proposal — MRL-0809 successor v2 Stage-4 retry

Status: ACCEPTED / BOUNDED_RUNTIME_AUTHORITY / EFFECTIVE_AFTER_CANONICAL_FRESH_MAIN

Decision ID: `FD-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-1`

Date prepared: 2026-10-03

Date accepted: 2026-10-03

This packet records the separate Founder decision required by
`FD-MRL-0809-SUCCESSOR-V2-STAGE4-REPAIR-1` after the repaired repository
contract became canonical and fresh-main qualified. Founder acceptance is
recorded below. Runtime execution remains disabled until this accepted packet
is itself canonical and fresh-main qualified.

Machine-readable form: `../mrl-0809-successor-v2-stage4-retry-authorization.json`.

## Canonical repaired binding

The proposal is bound to exactly this repaired canonical state:

```text
CANONICAL_REPAIR_MERGE_SHA = 66c8d33eb48433f50b9e313ede804cf5fb31271a
CANONICAL_REPAIR_MERGE_TREE = 8d6a818294f763c7e49ba0acfa172848f44607ee
REPAIR_STATIC_MANIFEST_SHA256 = d943a8bc4fbc7f5c8baf8716dd206b6262966c43c37a7a257645518a620f2c7d
DEPENDENCY_LOCK_SHA256 = 6fa0e0b49d19e305032ecd04940db0b9e252dd23b6fbec588b224f739048efc4
PRESERVED_V2_MANIFEST_SHA256 = 56de494cf30b6d3dd3aa005e63d55ea7490f7645dd37cbb388188d635813a36d
```

Fresh-main qualification on that exact merge completed successfully:

```text
CI_RUN = 37064636326 / SUCCESS
CODEQL_RUN = 37064636325 / SUCCESS
OPTIONAL_EXTRAS_RUN = 37064636396 / SUCCESS
HF_PUBLICATION_RUN = 37064636344 / SUCCESS
LOCAL_REPAIR_STATIC_GATE = PASS
```

## Historical result remains immutable

The consumed predecessor Stage-4 attempt remains historical FAIL evidence.
It is not overwritten, relabeled, erased, retried under the consumed receipt,
or converted into PASS.

```text
PRIOR_CONSUMED_V2_ATTEMPT = FAIL
PRIOR_QWEN_FAILURE_CLASS = HARNESS_RUNTIME_PLACEMENT_AUDIT_COMPATIBILITY_FAILURE
PRIOR_QWEN_CUDA_OOM_OBSERVED = FALSE
PRIOR_GEMMA_RESULT = INCOMPLETE_NOT_QUALIFIED
```

The prior failure does not establish T4 capacity infeasibility for the frozen
Qwen candidate, and the incomplete Gemma probe remains non-qualifying evidence.

## Runtime grant

The Founder accepted the following single grant. It becomes executable only
after this accepted decision packet is canonical and fresh-main qualified:

```text
NEW_STAGE4_ATTEMPTS_AUTHORIZED = 1
PROVIDER = GOOGLE_COLAB_FREE
GPU = Tesla T4
MACHINE_SHAPE = STANDARD
MONETARY_COST = 0
INPUT = SYNTHETIC_ONLY
SCIENTIFIC_CORPUS_ACCESS = FALSE
SEALED_TIER3_ACCESS = FALSE
SCIENTIFIC_RQ1_EXECUTION = FALSE
```

The attempt is bounded to the already-frozen successor v2 candidates:

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

The following remain prohibited and may not be inferred from the proposed grant:

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
MRL0809_CLOSEOUT = NOT_AUTHORIZED_BY_THIS_DECISION
MRL0899_CLOSEOUT = NOT_AUTHORIZED_BY_THIS_DECISION
```

## Attempt consumption and fail-stop rule

The authorized attempt, after the effectiveness boundary below is satisfied, is consumed
when execution crosses the canonical probe-start boundary for either candidate.
Any genuine model/load/probe/runtime failure after that boundary records FAIL
and terminates the attempt. No automatic retry, candidate substitution, offload,
quantization change, or second attempt is authorized.

A provider/session startup failure may be classified as infrastructure
non-execution only when canonical evidence proves that no candidate probe-start
boundary was crossed.

## Effectiveness boundary

Founder acceptance is recorded in this file, but acceptance is not by itself
runtime execution authority. The single attempt may execute only after:

1. the accepted statement and machine-readable authorization are exact and fail-closed;
2. the decision implementation is independently reviewed and exact-head qualified;
3. this accepted packet is merged with an ordinary merge commit;
4. the resulting canonical `main` passes fresh-main CI, CodeQL, Optional Extras / Backends, and Hugging Face Publication Qualification; and
5. the runtime launch verifies the exact canonical repository state and the retry authority gate before any candidate staging begins.

Before all five conditions are true:

```text
RUNTIME_EXECUTION = NOT_YET_EFFECTIVE
```

## Founder acceptance

Accepted explicitly by the Founder on 2026-10-03 with the exact statement:

```text
I approve FD-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-1, bound to canonical repair merge 66c8d33eb48433f50b9e313ede804cf5fb31271a, tree 8d6a818294f763c7e49ba0acfa172848f44607ee, and repair static manifest SHA-256 d943a8bc4fbc7f5c8baf8716dd206b6262966c43c37a7a257645518a620f2c7d. I authorize exactly one further zero-cost STANDARD-T4 Stage-4 runtime-feasibility attempt after the accepted decision packet is canonical and fresh-main qualified. The prior consumed v2 attempt remains FAIL and must not be overwritten or relabeled.
```

This acceptance grants no model, revision, GPU-class, quantization, offload,
paid-compute, scientific-RQ1, training, weight-mutation, MRL-0809-closeout, or
MRL-0899-closeout authority beyond the single bounded runtime-feasibility
attempt defined above.
