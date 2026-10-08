# Founder decision — MRL-0809 successor v2 evidence recovery 2

Status: ACCEPTED / BOUNDED_EVIDENCE_RECOVERY_AUTHORITY / EFFECTIVE_AFTER_CANONICAL_FRESH_MAIN

Decision ID: `FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-2`

Date accepted: 2026-10-06

## Purpose

Authorize implementation and exactly one additional bounded evidence-recovery launch after
Evidence-Recovery-1 completed the frozen runtime sequence but failed its evidence-retention
objective.

Recovery-1 remains immutable, failed for evidence retention, and consumed. This decision
does not overwrite, relabel, or reopen Recovery-1.

## Canonical predecessor binding

```text
RECOVERY_1_CANONICAL_MERGE_SHA = f9b7579189b77b06379d1a71d104d4b0267cf500
RECOVERY_1_CANONICAL_MERGE_TREE = 7bf4cbace9bce891da652a12ec3d7b6b4d9a8b03
RECOVERY_1_FAILURE_RECORD_SHA256 = 4bb9e9c5bfd85e7315bc788cad3f92d0ab1e7736ee57d8d620093acfca13a23b
RECOVERY_1_DISPOSITION = FAIL_EVIDENCE_RETENTION_AFTER_RUNTIME_PASS
RECOVERY_1_LAUNCH_CONSUMED = TRUE
```

The Recovery-1 record proves that the runtime sequence completed with driver return code
zero, while independent verification remained blocked because complete Gemma observation,
assembled runtime-feasibility receipt, and recovery-bundle bytes were not retained locally.

## Runtime grant

After the accepted Recovery-2 implementation is canonical and the exact canonical merge is
fresh-main qualified, exactly one additional hosted launch is authorized:

```text
EVIDENCE_RECOVERY_2_LAUNCHES_AUTHORIZED = 1
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

No model, revision, GPU class, quantization, runtime representation, placement policy, or
scientific scope may change.

## Host-controlled retention requirement

Recovery-2 must use a host-controlled continuous-retention protocol. Local retention is part
of the running transaction, not a manual post-runtime step.

Before the remote BMM sequence begins, the host controller must:

1. persist and fsync a local launch-consumption record;
2. start the local evidence watcher;
3. establish the exact session, repository, authority, and runtime preflight; and
4. prove that the watcher is active before invoking the remote Recovery-2 driver.

During remote execution, the host watcher must continuously copy each non-model evidence
artifact as soon as it appears, write through a temporary path, fsync it, atomically publish
it locally, and record byte count plus SHA-256 identity.

Recovery success is forbidden until the complete required evidence set exists locally and
is independently byte-verified.

## Driver exit hold

After the final runtime bundle is written and fsync'd, the remote driver must enter a bounded
copy-out hold. It must not return success until the host controller has:

1. copied the final bundle and every required individual evidence artifact locally;
2. verified all local bytes against the bundle byte counts and SHA-256 digests;
3. fsync'd a deterministic local evidence manifest; and
4. uploaded a host acknowledgement binding the final bundle and local manifest identities.

The required ordering is:

```text
RUNTIME PASS
-> FINAL ARTIFACTS WRITTEN + FSYNC
-> HOST COPY-OUT
-> LOCAL BYTE/HASH VERIFICATION
-> HOST ACK
-> REMOTE DRIVER SUCCESS EXIT
```

Standard-output history is not sufficient evidence retention and may not be used as the sole
recovery path.

## Launch-consumption rule

Exactly one hosted launch invocation is authorized. The launch is consumed by the first
Recovery-2 hosted allocation/invocation, including provider/session or preflight failure.

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

Founder acceptance authorizes implementation but does not make the hosted launch immediately
executable.

```text
RECOVERY_2_RUNTIME_EXECUTION = NOT_YET_EFFECTIVE
```

The single Recovery-2 launch may occur only after the accepted implementation is canonical
and the exact canonical merge commit has successful fresh-main qualification for CI,
CodeQL, Optional Extras / Backends, and Hugging Face Publication Qualification.

## Founder acceptance

Accepted explicitly by the Founder on 2026-10-06 with the exact statement:

```text
I approve FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-2. I authorize implementation and exactly one additional zero-cost Google Colab Free STANDARD-T4 evidence-recovery launch using the exact frozen Qwen and Gemma models, revisions, bitsandbytes-nf4-v1 runtime representation, synthetic-only input, and no-offload policy. Recovery-1 remains immutable, failed for evidence retention, and consumed. Recovery-2 must use host-controlled continuous retention with local byte-level hashing/fsync and must not report recovery success until the complete required evidence set is preserved and independently verifiable locally. No automatic retry or relaunch, model/revision/GPU/quantization substitution, paid compute, CPU/disk offload, RQ1 execution, training, weight mutation, trust admission, MRL-0809 closeout, or MRL-0899 closeout is authorized. The single launch may occur only after the accepted Recovery-2 implementation is canonical and fresh-main qualified.
```

This acceptance grants no authority beyond the bounded implementation and single
Evidence-Recovery-2 launch described above.
