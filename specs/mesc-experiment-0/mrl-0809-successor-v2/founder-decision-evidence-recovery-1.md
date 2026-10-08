# Founder decision — MRL-0809 successor v2 evidence recovery 1

Status: ACCEPTED / BOUNDED_EVIDENCE_RECOVERY_AUTHORITY / EFFECTIVE_AFTER_CANONICAL_FRESH_MAIN

Decision ID: `FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-1`

Date accepted: 2026-10-05

## Purpose

Authorize exactly one bounded evidence-recovery replay after the successful but unadmitted Stage-4 Retry-2 runtime sequence. The sole purpose is to preserve complete runtime evidence bytes that were not retained before the consumed Colab session was pruned.

The prior Retry-2 outcome remains immutable and consumed. This decision does not relabel, overwrite, or reopen that historical launch.

## Canonical predecessor binding

```text
CANONICAL_OUTCOME_MERGE_SHA = 1a634525e95ae1bb6a9fa01745ecd63c2d82684a
CANONICAL_OUTCOME_MERGE_TREE = 8c60c1ea30757fd743de8bee462e5f81c292ecb1
RETRY_2_OUTCOME_RECORD_SHA256 = 2346c595176a5cbeaff40897a4be64e0ebdad0e40c58438bb6f6a4d98304fda3
PRIOR_RETRY_2_DISPOSITION = PASS_RUNTIME_SEQUENCE_UNADMITTED
PRIOR_RETRY_2_LAUNCH_CONSUMED = TRUE
```

The prior runtime sequence remains frozen evidence. The missing bytes were:

- `gemma-observation.json`
- `runtime-feasibility-v2-bmm-repair-1.json`

## Runtime grant

After this accepted evidence-recovery implementation is canonical and fresh-main qualified, exactly one additional hosted launch is authorized:

```text
EVIDENCE_RECOVERY_LAUNCHES_AUTHORIZED = 1
PROVIDER = GOOGLE_COLAB_FREE
GPU = Tesla T4
MACHINE_SHAPE = STANDARD
MONETARY_COST = 0
INPUT = SYNTHETIC_ONLY
RUNTIME_REPRESENTATION = bitsandbytes-nf4-v1
CPU_OFFLOAD = FALSE
DISK_OFFLOAD = FALSE
AUTO_DEVICE_MAP = FALSE
```

The exact frozen roster remains:

```text
CANDIDATE_1 = Qwen/Qwen3-8B
CANDIDATE_1_REVISION = b968826d9c46dd6066d109eabc6255188de91218
CANDIDATE_2 = google/gemma-4-12B-it
CANDIDATE_2_REVISION = 707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7
```

The recovery launch must use the same fail-stop BMM sequence and runtime identity constraints already proven by Retry-2. It may not change model, revision, GPU class, quantization, runtime representation, placement policy, or scientific scope.

## Evidence-retention requirement

The recovery implementation must fail closed unless, after the BMM sequence completes, it preserves the complete bytes of all non-model evidence artifacts in a deterministic recovery bundle.

The recovery bundle must include the exact full bytes, byte counts, and SHA-256 digests of at least:

- BMM compatibility preflight receipt;
- Qwen stage receipt;
- Qwen probe-start marker;
- Qwen observation;
- Gemma stage receipt;
- Gemma probe-start marker;
- Gemma observation;
- assembled runtime-feasibility receipt;
- recovery authority receipt; and
- recovery launch-consumption receipt.

The bundle must be written inside custody and emitted to standard output in a recoverable encoding before the recovery driver returns success. This provides a second retention path through Colab CLI execution history if the hosted session is pruned before file copy-out.

## Launch-consumption rule

Exactly one hosted launch invocation is authorized. The launch is consumed before the BMM sequence begins, including provider/session or preflight failure.

```text
NO_AUTOMATIC_RETRY
NO_AUTOMATIC_RELAUNCH
PROVIDER_OR_SESSION_FAILURE_EXHAUSTS_LAUNCH
PREFLIGHT_FAILURE_EXHAUSTS_LAUNCH
```

Any later hosted launch requires a new explicit Founder decision.

## Explicit non-grants

```text
MODEL_SUBSTITUTION = NOT_AUTHORIZED
REVISION_SUBSTITUTION = NOT_AUTHORIZED
GPU_CLASS_SUBSTITUTION = NOT_AUTHORIZED
QUANTIZATION_SUBSTITUTION = NOT_AUTHORIZED
CPU_OFFLOAD = FALSE
DISK_OFFLOAD = FALSE
AUTO_DEVICE_MAP = FALSE
PAID_COMPUTE = NOT_AUTHORIZED
SCIENTIFIC_RQ1_EXECUTION = NOT_AUTHORIZED
TRAINING = FALSE
WEIGHT_MUTATION = FALSE
TRUST_ADMISSION = NOT_AUTHORIZED_BY_THIS_DECISION
MRL0809_CLOSEOUT = NOT_AUTHORIZED_BY_THIS_DECISION
MRL0899_CLOSEOUT = NOT_AUTHORIZED_BY_THIS_DECISION
```

## Effectiveness boundary

Founder acceptance alone is not executable runtime authority.

```text
RECOVERY_RUNTIME_EXECUTION = NOT_YET_EFFECTIVE
```

The recovery launch may occur only after the accepted evidence-recovery implementation is canonical and the exact canonical merge commit has successful fresh-main qualification for CI, CodeQL, Optional Extras / Backends, and Hugging Face Publication Qualification.

## Founder acceptance

Accepted explicitly by the Founder on 2026-10-05 with the exact statement:

```text
I approve FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-1. I authorize exactly one additional zero-cost Google Colab Free STANDARD-T4 evidence-recovery launch using the exact frozen Qwen and Gemma models, revisions, runtime representation, and no-offload policy. The prior Retry-2 outcome remains immutable and consumed. No automatic retry or relaunch, model/revision/GPU/quantization substitution, paid compute, RQ1 execution, training, weight mutation, trust admission, MRL-0809 closeout, or MRL-0899 closeout is authorized by this decision. The new launch may occur only after the accepted evidence-recovery implementation is canonical and fresh-main qualified.
```

This acceptance grants no authority beyond the single bounded evidence-recovery launch above.
