# MRL-0809 successor v2 Stage-4 retry — pre-probe non-execution record

Status: `EVIDENCE_RECORD / ATTEMPT_NOT_CONSUMED / REPOSITORY_REPAIR_REQUIRED`

## Canonical runtime binding

The accepted retry packet was canonical and fresh-main qualified before this episode.

```text
CANONICAL_MAIN = 8347c114a8402d8139cf80d6f406267cf20e521a
CANONICAL_TREE = 6aa345e18f20a9bfb90d476b6d875253ee2c5867
AUTHORIZATION_SHA256 = e0d4361b36fa9a78a02da2d8582f395897fec8ed1104438c943c50d1328e03d5
DECISION_SHA256 = 0f9746a510c35b4a249ec1b832c7a4222abe27f2c4304bc360822e76d965fa75
PROVIDER = GOOGLE_COLAB_FREE
GPU = Tesla T4
GPU_VRAM = 15360 MiB
MONETARY_COST = 0
```

The live Colab release was `release-colab-external-images_20261001-060042_RC00`.
The independently bound runtime identity was
`manual-colab-boot:4b3b91f2-a6a6-4dec-bd89-2d25fa19f9a3`.
The observed GPU UUID was `GPU-69a60fba-3068-1952-0100-9f9e824398c0`.
## Qualified setup before launch

Preflight proved the exact Tesla T4 allocation, 75,387,830,272 free bytes before setup,
the canonical `main` SHA, the Colab release, and the runtime identity.

The frozen runtime package surface was independently rechecked inside the repository
virtual environment:

```text
accelerate = 1.14.0
bitsandbytes = 0.50.2
huggingface-hub = 1.23.0
pillow = 12.3.0
torch = 2.13.0
torchvision = 0.28.0
transformers = 5.16.1
xgrammar = 0.2.7
bubblewrap = 0.9.0
```

The canonical retry authority gate passed on the exact checkout. A read-only remote roster
metadata/capacity preflight then succeeded with 69,979,590,656 free bytes and a frozen
roster requirement of 25,025,488,695 bytes. No candidate weights were downloaded by that
diagnostic.
## Non-execution evidence

The first governed launch created only the retry authority receipt and an empty
`qwen-snapshot/` directory. It created no Qwen stage receipt, no observation, no Gemma
material, and no `*.probe-start.json` marker. The authority receipt SHA-256 was
`b9d4cc6aebc22f78cdcef4812261bc8cd8a6aab2a7bdf015f5b02f6df853def1`.
That custody was preserved separately as the first pre-stage non-execution record.

One bounded continuation of the same unconsumed attempt was then executed with stdout and
stderr captured. It again failed during Qwen staging before any candidate download or
probe-start marker. The captured log was 2,998 bytes with SHA-256:

```text
01dd06c5229c039b4e99cb0c9bcc18b5c87d08aed5f5efb4b6c7b53905b490fe
```

The decisive traceback was:

```text
importlib.metadata.PackageNotFoundError: No package metadata was found for accelerate
...
HarnessError: required package missing: accelerate
...
Stage4ExecutionError: Stage-4 command failed; execution stopped without retry: stage
```
## Proven root cause

The repository virtual environment was not missing `accelerate`; the independent package
check immediately before launch proved the complete frozen package set.

The failure was caused by the preserved repair driver resolving the virtual-environment
entry point with `python_executable.resolve(strict=True)`. On the Colab uv environment,
`.venv/bin/python` is a symlink to the uv-managed base interpreter. Dereferencing that
symlink therefore changed the launched interpreter from the qualified virtual environment
to the base interpreter, which does not expose the virtual-environment package metadata.

This is a launch-path identity defect, not a T4 capacity result, model failure, package-lock
drift, candidate-identity failure, or Hugging Face staging result.

## Attempt-consumption classification

Both observed launch episodes stopped before creation of any canonical probe-start marker.
No Qwen or Gemma observation exists and no candidate probe began.

```text
NEW_RETRY_ATTEMPT_STATE = NOT_CONSUMED
QWEN_STAGE = NOT_COMPLETED
QWEN_PROBE = NOT_STARTED
GEMMA_STAGE = NOT_STARTED
GEMMA_PROBE = NOT_STARTED
SCIENTIFIC_RQ1_EXECUTION = NOT_AUTHORIZED
```
## Repository repair boundary

The hash-bound repair-1 driver remains immutable. The retry-specific driver is repaired
instead so that it preserves the absolute `.venv/bin/python` path without dereferencing the
symlink before staging or probing. The retry-specific sequence remains exactly:

```text
QWEN_STAGE
-> QWEN_PROBE
-> REMOVE_QWEN_SNAPSHOT
-> GEMMA_STAGE
-> GEMMA_PROBE
-> REMOVE_GEMMA_SNAPSHOT
-> ASSEMBLE
```

Any Qwen probe failure must still stop before Gemma. No automatic retry, model substitution,
offload, quantization change, GPU substitution, or paid compute is introduced.

The same single Founder-authorized retry may resume only after this repository correction is
independently reviewed, exact-head qualified, merged by ordinary merge commit, and the new
canonical `main` is fresh-main qualified. The accepted decision and authorization bytes are
not modified by this repair.
