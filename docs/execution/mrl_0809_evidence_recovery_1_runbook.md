# MRL-0809 successor v2 evidence-recovery-1 runbook

Status: PREPARED_ONLY. Repository inclusion is not runtime authority.

Decision: `FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-1`.

The single evidence-recovery launch becomes executable only after the accepted implementation is merged under explicit Founder exact-head approval naming the final qualified PR head, becomes canonical, and the exact canonical merge commit is fresh-main qualified by CI, CodeQL, Optional Extras / Backends, and Hugging Face Publication Qualification.

## Merge adoption gate

Founder acceptance of the evidence-recovery decision is not reusable as merge approval for an implementation head that did not yet exist. Before merge, the final PR head must be exact-head qualified and the Founder must explicitly approve that exact head for an ordinary merge commit. Any head change invalidates the prior merge approval and requires a new exact-head approval.

Merge policy:

```text
NORMAL_MERGE_COMMIT_ONLY
NO_SQUASH
NO_REBASE
NO_FORCE_PUSH
MATCH_EXACT_HEAD
```

After the ordinary merge, the resulting canonical merge commit must complete all four fresh-main qualification lanes before any recovery runtime authority becomes effective.

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

No model, revision, GPU, quantization, placement, or runtime-representation substitution is allowed.

## Colab CLI baseline

The qualified operator path uses the official Google Colab CLI. The implementation was prepared against CLI `0.7.4`, which exposes `new`, `usage`, `status`, `exec`, `upload`, and `download`.

Before any hosted launch invocation:

```bash
colab usage
colab sessions
```

The account must show zero paid compute-unit balance for this zero-cost program. No paid compute may be purchased or consumed for this launch.

## Launch boundary

Exactly one new session may be allocated for this decision:

```bash
colab new --session mesc-evidence-recovery-1 --gpu T4
colab status --session mesc-evidence-recovery-1
```

Do not use `--high-mem`. Do not request another accelerator. Do not call `colab new` again if the launch is consumed or the session fails.

Inside the session, independently establish:

- Google Colab provider identity;
- `Tesla T4` GPU identity;
- standard machine shape;
- exact GPU UUID and VRAM;
- Colab release tag;
- provider execution/boot identity;
- sufficient free disk;
- required package versions;
- `HF_TOKEN` and `HUGGING_FACE_HUB_TOKEN` unset; and
- exact live canonical repository HEAD with a clean checkout.

The repository revision supplied to the recovery driver must equal live `origin/main` and must already have the four successful fresh-main qualification lanes.

## Driver invocation

The only authorized runtime entrypoint is:

```text
scripts/mesc_mrl_0809_evidence_recovery_1_driver.py
```

The driver must receive:

```text
--repository-root <exact clean canonical checkout>
--custody <new absent custody directory>
--python-executable <qualified Python 3.11 executable>
--expected-canonical-revision <exact fresh-main-qualified main SHA>
```

The driver writes the evidence-recovery authority receipt and launch-consumption receipt before invoking the preserved BMM fail-stop sequence. Once the hosted driver invocation begins, the single recovery launch is consumed even if provider/session or BMM preflight fails.

No retry or relaunch is authorized.

## Mandatory dual retention

On successful BMM completion, the driver must create:

```text
evidence-recovery-1-bundle.json
```

The bundle contains full base64-encoded bytes, byte counts, and SHA-256 digests for every required non-model evidence artifact, including the Gemma observation and assembled runtime-feasibility receipt.

Before returning success, the driver also emits the exact bundle bytes through stdout with the prefix:

```text
MESC_EVIDENCE_RECOVERY_BUNDLE_V1_BASE64=
```

The stdout copy is mandatory because Colab CLI execution history is an independent recovery path if the session filesystem is pruned before download.

## Immediate copy-out

After the single driver execution returns success, download the bundle before stopping or releasing the session:

```bash
colab download --session mesc-evidence-recovery-1 \
  <remote-custody>/evidence-recovery-1-bundle.json \
  <local-evidence-path>/evidence-recovery-1-bundle.json
```

Also download the individual evidence artifacts when the session remains available. The bundle, stdout history, and downloaded individual files must agree byte-for-byte on every artifact digest before any independent verification is attempted.

If the file download path is lost but the CLI execution event remains, recover the bundle from the `MESC_EVIDENCE_RECOVERY_BUNDLE_V1_BASE64=` stdout marker and verify the decoded bundle against its internal artifact digests.

## Stop conditions

Stop immediately without retry if any of the following occurs:

- provider/session failure after hosted launch invocation;
- wrong GPU or machine shape;
- non-zero paid compute use;
- live-main mismatch or dirty checkout;
- authority-gate failure;
- BMM compatibility preflight failure;
- candidate stage/probe failure;
- cleanup failure;
- missing required recovery artifact;
- bundle creation failure;
- stdout bundle emission failure; or
- any unapproved model, revision, offload, placement, quantization, or runtime-representation drift.

## Post-runtime governance

A successful evidence-recovery launch does not itself authorize trust admission, MRL-0809 closeout, MRL-0899 closeout, RQ1 execution, training, or weight mutation.

After copy-out, independently verify the new full receipt and all bound observations. Trust admission, if ever eligible, requires its own separately governed minimal admission action and any exact-head approval required by the canonical runbook.
