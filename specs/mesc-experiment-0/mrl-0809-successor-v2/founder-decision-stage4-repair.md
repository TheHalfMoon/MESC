# Founder decision packet — MRL-0809 successor v2 Stage-4 harness repair

Status: ACCEPTED / REPOSITORY_REPAIR_ONLY / NO_RUNTIME_AUTHORITY

Decision ID: `FD-MRL-0809-SUCCESSOR-V2-STAGE4-REPAIR-1`

## Founder acceptance

Accepted explicitly by the Founder on 2026-10-01 with the exact statement:

```text
I approve FD-MRL-0809-SUCCESSOR-V2-STAGE4-REPAIR-1 for repository repair only. No Stage-4 retry is authorized.
```

This acceptance authorizes only the repository-side repair and qualification scope defined below. It does not authorize any new hosted runtime attempt.

## Proven trigger

The single authorized successor v2 Stage-4 attempt was consumed after the Qwen probe crossed the canonical probe-start boundary and failed inside the isolated worker with:

```text
HarnessError: loaded model did not expose an auditable device map
```

The Qwen frozen weight load reached `399/399`. No CUDA OOM was observed. The result therefore does not establish T4 capacity infeasibility for `Qwen/Qwen3-8B` under the successor v2 roster.

Gemma staging completed after notebook orchestration advanced past the Qwen failure. The Gemma probe began and was interrupted. No Gemma qualification result is admitted.

See `docs/execution/mrl_0809_successor_v2_stage4_failure_postmortem.md`.

## Authorized repository repair authority

The repository repair may:

1. version the repaired successor harness/receipt contract as required so the consumed v2 attempt remains immutable;
2. replace the mandatory-presence assumption for `model.hf_device_map` with a fail-closed multi-source placement audit;
3. continue to validate `hf_device_map` when it exists;
4. inspect all materialized parameters and buffers and require CUDA device 0;
5. reject CPU, disk, meta, CUDA device 1+, mixed-device, uninspectable, or empty placement evidence;
6. add deterministic placement-audit evidence to the worker/observation/receipt schema if required for independent verification;
7. add adversarial tests proving the repaired audit cannot convert real offload/fallback into PASS;
8. repair the Stage-4 notebook/driver so the first failed probe terminates execution before the second candidate can start;
9. update the static manifest, runbook, schemas, validators, tests, and machine-readable authorization bindings needed for the repaired version;
10. preserve all v1 and consumed-v2 evidence/contract material immutably rather than rewriting historical evidence.

### Constraints that remain frozen

The repair must not change:

```text
CANDIDATE_1 = Qwen/Qwen3-8B
CANDIDATE_1_REVISION = b968826d9c46dd6066d109eabc6255188de91218
CANDIDATE_2 = google/gemma-4-12B-it
CANDIDATE_2_REVISION = 707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7
PROVIDER = GOOGLE_COLAB_FREE
GPU = Tesla T4
MACHINE_SHAPE = STANDARD
RUNTIME_REPRESENTATION = bitsandbytes-nf4-v1
QUANTIZATION = NF4_DOUBLE_QUANT_FLOAT16_COMPUTE
MODEL_DEVICE_POLICY = CUDA_DEVICE_0_ONLY
CPU_OFFLOAD = FALSE
DISK_OFFLOAD = FALSE
AUTO_DEVICE_MAP = FALSE
TRUST_REMOTE_CODE = FALSE
ISOLATED_WORKER_NETWORK = FALSE
MAX_PEAK_GPU_MEMORY = 12_GiB
MONETARY_COST = 0
SCIENTIFIC_CORPUS_ACCESS = FALSE
SEALED_TIER3_ACCESS = FALSE
TRAINING = FALSE
WEIGHT_MUTATION = FALSE
SCIENTIFIC_RQ1_EXECUTION = FALSE
```

The repair must not weaken sandboxing, seccomp, staging identity, prompt-token binding, finite-logit checks, cleanup checks, repository identity checks, or independent verification.

## Required adversarial placement coverage

At minimum, repository tests must prove all of the following:

| Case | Expected |
| --- | --- |
| `hf_device_map` missing, every materialized parameter/buffer is `cuda:0` | placement audit may PASS |
| `hf_device_map` present and all entries resolve to CUDA 0, actual tensors all CUDA 0 | PASS |
| `hf_device_map` says CUDA 0 but a real parameter is CPU | FAIL |
| any parameter is `cuda:1` | FAIL |
| any parameter is `meta` | FAIL |
| any buffer is CPU | FAIL |
| mixed CUDA/CPU parameters or buffers | FAIL |
| `hf_device_map` contains `cpu` | FAIL |
| `hf_device_map` contains `disk` | FAIL |
| no materialized parameters or buffers can be audited | FAIL |
| placement target cannot be normalized deterministically | FAIL |

The implementation must prefer actual tensor placement over a permissive metadata map when the two disagree.

## Notebook/driver repair requirement

The consumed attempt exposed a second defect in the execution wrapper: a failed `%%bash` probe cell did not prevent the multi-cell Colab CLI driver from advancing to later cells.

A repaired governed execution path must therefore ensure:

```text
FIRST_PROBE_FAILURE => IMMEDIATE_STOP
NO_SECOND_CANDIDATE_STAGE_AFTER_FIRST_PROBE_FAILURE
NO_SECOND_CANDIDATE_PROBE_AFTER_FIRST_PROBE_FAILURE
NO_AUTOMATIC_RETRY
```

This behavior must be mechanically tested where practical and stated in the runbook.

## Qualification sequence

Repository repair qualification must follow:

```text
IMPLEMENT
-> LOCAL TESTS
-> REGRESSION TESTS
-> JEV
-> FIX
-> ALIBABA OPEN CODE REVIEW LOCAL OFFICIAL LANES
-> FIX
-> JEV RECHECK IF CODE CHANGED
-> OCR RECHECK IF CODE CHANGED
-> HOST REVIEW
-> CI
-> CODEQL
-> OPTIONAL EXTRAS / BACKENDS
-> HF PUBLICATION QUALIFICATION
-> EXACT-HEAD QUALIFICATION
-> FOUNDER MERGE APPROVAL
-> ORDINARY MERGE COMMIT
-> FRESH-MAIN REQUALIFICATION
```

Jev and Alibaba Open Code Review results must be recorded exactly; no PASS may be fabricated when a lane cannot run.

## Separate runtime decision required

Even after a repaired contract is merged and fresh-main qualified:

```text
NEW_STAGE4_ATTEMPT = NOT_AUTHORIZED_BY_THIS_PACKET
```

A second explicit Founder decision must bind the exact canonical repaired merge SHA/tree/static manifest and authorize exactly one further zero-cost STANDARD-T4 Stage-4 attempt.

That later decision must state that the prior consumed v2 attempt remains FAIL and is not overwritten or relabeled.

## Current non-grants

The accepted repository repair authority does not grant any of the following:

```text
NEW_STAGE4_ATTEMPT = NOT_AUTHORIZED
MODEL_SUBSTITUTION = NOT_AUTHORIZED
REVISION_SUBSTITUTION = NOT_AUTHORIZED
GPU_CLASS_SUBSTITUTION = NOT_AUTHORIZED
QUANTIZATION_SUBSTITUTION = NOT_AUTHORIZED
OFFLOAD_FALLBACK = NOT_AUTHORIZED
PAID_COMPUTE = NOT_AUTHORIZED
SCIENTIFIC_RQ1_EXECUTION = NOT_AUTHORIZED
MRL0809_CLOSEOUT = NOT_AUTHORIZED
MRL0899_CLOSEOUT = NOT_AUTHORIZED
```

## Acceptance boundary

This packet is accepted for repository repair only. Acceptance is not acceptance of a new Stage-4 runtime attempt. No hosted retry may occur until a separate Founder decision explicitly authorizes it against an exact canonical repaired revision.