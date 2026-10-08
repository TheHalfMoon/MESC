# MRL-0809 successor v2 Stage-4 retry-1 failure postmortem

Status: `EVIDENCE_RECORD / ATTEMPT_CONSUMED / REPOSITORY_REPAIR_REQUIRED / NO_RETRY_AUTHORITY`

## Canonical runtime binding

```text
CANONICAL_MAIN = 2d8af295b86144a06ce6fe9aad741fed07c2f5d7
CANONICAL_TREE = 5cc4c44d83aa9e51c63c7283a3b037dfa2e3a7ff
RETRY_AUTHORIZATION_SHA256 = e0d4361b36fa9a78a02da2d8582f395897fec8ed1104438c943c50d1328e03d5
FOUNDER_DECISION_SHA256 = 0f9746a510c35b4a249ec1b832c7a4222abe27f2c4304bc360822e76d965fa75
PROVIDER = GOOGLE_COLAB_FREE
GPU = Tesla T4
GPU_VRAM = 15360 MiB
MONETARY_COST = 0
```

The Colab release was `release-colab-external-images_20261001-060042_RC00`. The runtime-instance identity came from `/proc/sys/kernel/random/boot_id`; only its SHA-256 is retained in the failure record.

## Evidence custody

The downloaded evidence archive has SHA-256 `48d260414e45e94deb851007e3caf2bb6ab1854667d56a2bbdebc53ea3463223`. The retained evidence hashes are:

```text
launcher/summary.json = 612642f90ba38a059d84bc710871d53b76507b037d7f5b50a842339a1da27532
launcher/launch.log = 184f734fe485aedde21e079740cb49ee45efcb73649db7d949f9d45e6359033a
launcher/evidence-manifest.json = 0f440a80dae980e20e6913871691e56a2d4c1b9f686104f430e7018d49e6ccdc
custody/stage4-retry-authority.json = a80ed4a5384afaa69e29a9fb7e6614d58b80d90d25167249b2d16eb6c0ff0563
custody/qwen-stage.json = 334618d90d4c3be14e63e378ec3dc5c0fe6ab589f07b76392a07f5ec266a90d6
custody/qwen-observation.json.probe-start.json = f37b340d2e06b0a1b11cf78e4b926a8659d51d30d08761166eab27747a464d6b
```

## Proven execution facts

Qwen staging completed for `Qwen/Qwen3-8B` at revision `b968826d9c46dd6066d109eabc6255188de91218`. The canonical probe-start marker was then written, so retry-1 was consumed. The isolated worker loaded far enough to enter synthetic generation after the repaired CUDA placement audit. No CUDA OOM was observed.

Generation failed in PyTorch 2.13's experimental native `bmm` override. The Qwen rotary-embedding path dispatched through `torch._native.ops.bmm_outer_product`, which invoked Triton. Triton attempted to compile its CUDA helper with GCC inside the isolated Bubblewrap worker and the compiler returned a non-zero exit status while linking `libcuda.so.1`.

The fail-stop retry driver then stopped immediately. Gemma staging and probing did not run. This is therefore not a Qwen capacity infeasibility result and not a Gemma result.

## Attempt-consumption classification

```text
RETRY_1_ATTEMPT = CONSUMED
QWEN_STAGE = PASS
QWEN_PROBE = FAIL
QWEN_CUDA_OOM = NOT_OBSERVED
QWEN_CAPACITY_INFEASIBILITY = NOT_ESTABLISHED
GEMMA_STAGE = NOT_RUN
GEMMA_PROBE = NOT_RUN
AUTOMATIC_RETRY = PROHIBITED
MRL_0809_CLOSEOUT = NOT_AUTHORIZED
MRL_0899_CLOSEOUT = NOT_AUTHORIZED
```

A later accidental duplicate launch was interrupted before any probe-start marker existed. Its evidence archive SHA-256 is `65d8cc90b98577003120a89b9edc685a9c824f2d629efd0e34e11a0615fa935b`; it is a non-consuming safety stop and does not create a second attempt.

## Repository repair objective

Repair-1 artifacts remain byte-preserved. The next repository repair is separately versioned and must:

1. preserve the exact model roster, revisions, NF4 representation, explicit CUDA-0 placement, no-offload policy, offline worker, synthetic prompt, generation budget, memory ceiling, and fail-stop ordering;
2. disable only the PyTorch 2.13 experimental native `bmm` override so eager `bmm` uses the stable ATen implementation;
3. execute a tiny CUDA `bmm` portability smoke inside the same Bubblewrap isolation before any candidate probe-start marker can be created;
4. fail before attempt consumption if that smoke cannot execute without Triton helper compilation failure;
5. preserve retry-1 as permanently consumed and make the retry-1 driver refuse any further launch.

This repair grants no new Stage-4 attempt. Any later hosted attempt requires a new exact-revision Founder decision after the repair is canonical and fresh-main qualified.
