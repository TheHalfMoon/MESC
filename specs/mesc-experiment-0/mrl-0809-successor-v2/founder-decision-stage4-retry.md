# Founder decision proposal — MRL-0809 successor v2 Stage-4 retry

Status: PROPOSED / NO_RUNTIME_AUTHORITY

Decision ID: `FD-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-1`

Date prepared: 2026-10-03

This packet proposes the separate Founder decision required by
`FD-MRL-0809-SUCCESSOR-V2-STAGE4-REPAIR-1` after the repaired repository
contract became canonical and fresh-main qualified. Merely adding or reviewing
this file grants no runtime authority.

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

## Proposed runtime grant

Only after explicit Founder acceptance and canonicalization of the accepted
decision packet, the following single grant would become effective:

```text
PROPOSED_NEW_STAGE4_ATTEMPTS = 1
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

The authorized attempt, if this proposal later becomes effective, is consumed
when execution crosses the canonical probe-start boundary for either candidate.
Any genuine model/load/probe/runtime failure after that boundary records FAIL
and terminates the attempt. No automatic retry, candidate substitution, offload,
quantization change, or second attempt is authorized.

A provider/session startup failure may be classified as infrastructure
non-execution only when canonical evidence proves that no candidate probe-start
boundary was crossed.

## Effectiveness boundary

This proposal is not self-executing. It remains `NO_RUNTIME_AUTHORITY` unless:

1. the Founder explicitly accepts `FD-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-1`;
2. the accepted statement is persisted in this decision record;
3. the corresponding machine-readable authorization and static bindings are implemented;
4. the decision implementation is independently reviewed and exact-head qualified;
5. the accepted packet is merged with an ordinary merge commit under the required governance; and
6. the resulting `main` is fresh-main qualified.

No hosted runtime attempt may occur before all six conditions are true.

## Proposed Founder acceptance text

If the Founder intends to grant the bounded retry after reviewing this packet,
the explicit decision should be:

```text
I approve FD-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-1, bound to canonical repair merge
66c8d33eb48433f50b9e313ede804cf5fb31271a, tree
8d6a818294f763c7e49ba0acfa172848f44607ee, and repair static manifest SHA-256
d943a8bc4fbc7f5c8baf8716dd206b6262966c43c37a7a257645518a620f2c7d. I authorize
exactly one further zero-cost STANDARD-T4 Stage-4 runtime-feasibility attempt after
the accepted decision packet is canonical and fresh-main qualified. The prior
consumed v2 attempt remains FAIL and must not be overwritten or relabeled.
```
