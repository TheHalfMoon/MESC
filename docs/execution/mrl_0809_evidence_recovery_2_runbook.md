# MRL-0809 successor v2 evidence-recovery-2 runbook

Status: PREPARED_ONLY. Repository inclusion is not runtime authority.

Decision: `FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-2`.

Recovery-2 exists solely to repair the evidence-retention failure recorded by Recovery-1.
Recovery-1 remains immutable, failed for evidence retention, and consumed.

## Effectiveness boundary

The single hosted Recovery-2 launch becomes executable only after:

1. the accepted implementation is exact-head qualified;
2. the Founder explicitly approves the final exact PR head for a normal merge commit;
3. the implementation is merged without squash, rebase, force-push, or history rewrite;
4. the exact canonical merge passes fresh-main CI, CodeQL, Optional Extras / Backends, and
   Hugging Face Publication Qualification; and
5. the canonical Recovery-2 authority gate passes against a clean live-main checkout.

Any head change invalidates exact-head merge approval.

## Frozen runtime contract

```text
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

Frozen candidates:

```text
Qwen/Qwen3-8B @ b968826d9c46dd6066d109eabc6255188de91218
google/gemma-4-12B-it @ 707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7
```

No model, revision, GPU, quantization, placement, or runtime-representation substitution is
allowed.

## Host controller

The authorized host-side entrypoint is:

```text
scripts/mesc_mrl_0809_evidence_recovery_2_host_controller.py
```

It has two phases.

### 1. Allocate exactly once

Immediately before the single hosted allocation, run the controller's `allocate` command.
The controller first writes and fsyncs the local host launch-consumption receipt and then
invokes exactly:

```text
colab new --session mesc-evidence-recovery-2 --gpu T4
```

If the allocation fails, the launch remains consumed. Do not invoke `allocate` again.

Before allocation, independently verify:

```text
colab usage
colab sessions
```

Paid compute-unit balance must be zero. No paid units may be purchased or consumed.

### 2. Run with continuous retention

After the one session is ready and the exact canonical repository/runtime environment is
prepared inside it, use the controller's `run` command.

The controller must start its local watcher before invoking the remote Recovery-2 driver.
The watcher continuously downloads each required custody artifact as soon as it appears.
Every local copy uses a temporary path, fsync, atomic replacement, and recorded SHA-256 plus
byte count.

The remote entrypoint is:

```text
scripts/mesc_mrl_0809_evidence_recovery_2_driver.py
```

The remote driver writes its authority and launch-consumption receipts before invoking the
preserved BMM fail-stop sequence.

## Required retention transaction

Recovery success requires this exact ordering:

```text
RUNTIME PASS
-> FINAL ARTIFACTS WRITTEN + FSYNC
-> HOST CONTINUOUS COPY-OUT COMPLETES
-> LOCAL BUNDLE/INDIVIDUAL BYTE VERIFICATION
-> LOCAL EVIDENCE MANIFEST FSYNC
-> HOST ACK UPLOADED
-> REMOTE DRIVER SUCCESS EXIT
```

The remote driver writes:

```text
evidence-recovery-2-bundle.json
evidence-recovery-2-copyout-ready.json
```

and then enters a bounded copy-out hold. It must not return success until a valid
`evidence-recovery-2-host-ack.json` is uploaded by the host controller.

The host acknowledgement is permitted only after the complete local evidence set is present
and every individual artifact matches the bundle's byte count and SHA-256 identity.

Standard-output history is not a sufficient retention path for Recovery-2.

### Failure-path custody preservation

If the remote driver exits without an acknowledged, completely verified evidence set, the host
stops the watcher and performs one best-effort final copy-out sweep of the frozen custody
filename list. Each host download and ACK upload attempt has a 20-second subprocess timeout;
the watcher is given a bounded 25-second shutdown after the stop signal. No automatic
reallocation or relaunch is permitted. Files copied before the ready marker, and all files
retained after a failed run, remain **provisional failure evidence**, not a verification PASS.
This last sweep cannot create the local success manifest or upload an ACK, and failure to
complete it does not change the fail-closed runtime disposition. The controller uses a local
`.partial/` directory for temporary downloads and a local
`evidence-recovery-2-colab-runner.py` to invoke the frozen remote driver. Neither is
independently admitted as scientific evidence.

## Session preflight

Inside the one allocated session, establish before runtime execution:

- Google Colab Free provider identity;
- exact Tesla T4 / STANDARD identity;
- exact GPU UUID and 15360 MiB-class VRAM evidence;
- Colab release tag and provider execution identity;
- sufficient free storage;
- exact locked runtime dependencies;
- bubblewrap availability;
- `HF_TOKEN` and `HUGGING_FACE_HUB_TOKEN` unset;
- exact clean canonical repository revision;
- live `origin/main` equality; and
- successful canonical Recovery-2 authority validation.

Wrong GPU, provider/session failure, preflight failure, or any authority failure exhausts the
single launch and must not trigger a second allocation.

## Stop conditions

Stop without retry or relaunch on any of the following:

- provider or session failure after the hosted launch boundary;
- wrong GPU or machine shape;
- nonzero paid compute use;
- live-main mismatch or dirty checkout;
- authority-gate failure;
- BMM compatibility-preflight failure;
- candidate stage/probe failure;
- cleanup failure;
- local watcher failure;
- local copy-out or fsync failure;
- bundle/individual byte mismatch;
- host-ack upload failure;
- copy-out hold timeout; or
- any unauthorized model, revision, GPU, quantization, placement, offload, or scientific-scope drift.

## Post-runtime governance

A successful Recovery-2 evidence transaction does not itself authorize:

```text
TRUST_ADMISSION
MRL0809_CLOSEOUT
MRL0899_CLOSEOUT
SCIENTIFIC_RQ1_EXECUTION
TRAINING
WEIGHT_MUTATION
MODEL_PROMOTION
RELEASE
DEPLOYMENT
```

After complete local retention, the resulting evidence must undergo independent verification.
Any trust admission or closeout remains a separate governed action.
