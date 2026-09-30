# MRL-0809 Successor (v2) Google Colab Runtime-Feasibility Runbook

Status: PREPARED_ONLY. Do not execute Stage 4 until the successor contract is merged under explicit Founder exact-head approval **and** the exact merge commit has four successful fresh-main lanes: CI, CodeQL, Optional Extras / Backends and HF Publication Qualification.

- **Authority:** [FD-MRL-0809-SUCCESSOR-V2-1](../../specs/mesc-experiment-0/mrl-0809-successor-v2/founder-decision.md); machine-readable in [`mrl-0809-successor-v2-authorization.json`](../../specs/mesc-experiment-0/mrl-0809-successor-v2-authorization.json).
- **Contract:** [successor README](../../specs/mesc-experiment-0/mrl-0809-successor-v2/README.md).
- **v1 runbook (historical, not to be reused):** [mrl_0809_runtime_feasibility_runbook.md](mrl_0809_runtime_feasibility_runbook.md).

## Scope

This runbook covers only the **one** bounded, zero-cost MRL-0809 successor dual-candidate runtime-feasibility attempt authorized by FD-MRL-0809-SUCCESSOR-V2-1. It authorizes none of the following:
- scientific corpus access or sealed Tier-3 access;
- the RQ1 scientific experiment;
- training, optimizer use, LoRA/QLoRA, distillation, RL or weight mutation;
- paid compute, a higher-memory GPU, or CPU/disk offload;
- candidate substitution;
- promotion, release, deployment or clinical use.

The frozen v1 roster (`Qwen/Qwen3.8-27B`, `google/gemma-4-31B-it`) is **not** retried. Its OOM result is preserved in `mrl-0809-v1-infeasibility-record.json`.

## Hard prerequisites

Before starting, prove all of the following. Any failed prerequisite means STOP **before** any probe starts; that is not a consumed attempt.
- the successor contract PR is merged, and the four fresh-main lanes above are terminal SUCCESS on the exact merge SHA;
- the repository is on exact live `origin/main`, with a clean working tree;
- `specs/mesc-experiment-0/mrl-0809-runtime-feasibility-slot-v2.json` is still `ABSENT`;
- the provider is Google Colab free tier (`GOOGLE_COLAB_FREE`), the assigned GPU is exactly `Tesla T4`, and monetary cost is zero;
- no scientific corpus or sealed Tier-3 material is mounted or copied into the runtime;
- no Hugging Face token is present (`HF_TOKEN` unset). Both candidates are public and ungated, and no credential or terms acceptance is permitted.

If a T4 is unavailable, wait for normal free availability. Never substitute another GPU.

## Frozen successor candidates

Execute both, sequentially, in the same Colab provider session:

1. `Qwen/Qwen3-8B` at revision `b968826d9c46dd6066d109eabc6255188de91218`
   - text-only;
   - processor policy `TOKENIZER_ONLY_TEXT_MODEL`;
   - selected payload 16,397,431,693 bytes.
2. `google/gemma-4-12B-it` at revision `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`
   - multimodal checkpoint, text-only generation;
   - processor policy `AUTO_PROCESSOR_EXACT_REVISION`;
   - selected payload 23,951,746,871 bytes.

No candidate substitution is allowed.

## Repository setup

    git clone https://github.com/TheHalfMoon/MESC.git
    cd MESC
    git fetch origin main
    git checkout --detach origin/main
    git status --short
    git rev-parse HEAD
    git rev-parse HEAD^{tree}
    git ls-remote origin refs/heads/main

    uv python install 3.11
    uv sync --no-dev --extra rq1-runtime-feasibility --frozen
    uv cache clean
    sudo apt-get update
    sudo apt-get install -y bubblewrap

The `rq1-runtime-feasibility` extra and `uv.lock` are the v1 bytes, unchanged; the successor manifest binds them. It must still install exactly these pinned versions:

```text
accelerate 1.14.0
bitsandbytes 0.50.2
huggingface-hub 1.23.0
pillow 12.3.0
torch 2.13.0
torchvision 0.28.0
transformers 5.16.1
xgrammar 0.2.7
```

## Provider identity and zero-cost attestation

    export MESC_MRL0809_ZERO_COST_ATTESTATION=1
    export MESC_COLAB_RUNTIME_ID="<independently-obtained-current-colab-session-id>"
    test -n "$COLAB_RELEASE_TAG"
    unset HF_TOKEN HUGGING_FACE_HUB_TOKEN

## Evidence custody

    export MRL0809_CUSTODY=/content/mrl0809-v2-custody
    mkdir -p "$MRL0809_CUSTODY"

All snapshots, receipts, observations and probe-start markers stay outside the repository.

## Staging policy

The staging policy is the v1 policy unchanged:
- a roster-wide free-space preflight before any byte is downloaded;
- serialized downloads;
- Xet disabled;
- a controlled empty cache;
- exact selected payload plus a 1 GiB reserve.

For the successor manifests:
- Gemma needs `25,025,488,695` bytes free before staging, which is also the roster-wide threshold;
- Qwen needs `17,471,173,517` bytes.

The weight allowlist comes from the SHA-bound `candidate-roster-v2.json`. Processor metadata is required only for Gemma (`processor_config.json`). Qwen is tokenizer-only.

## Candidate 1 — Qwen

    .venv/bin/python scripts/mesc_mrl_0809_runtime_feasibility_v2.py stage \
      --repository-root "$PWD" \
      --candidate "Qwen/Qwen3-8B" \
      --destination "$MRL0809_CUSTODY/qwen-snapshot" \
      --receipt-out "$MRL0809_CUSTODY/qwen-stage.json"

    .venv/bin/python scripts/mesc_mrl_0809_runtime_feasibility_v2.py probe \
      --repository-root "$PWD" \
      --candidate "Qwen/Qwen3-8B" \
      --snapshot "$MRL0809_CUSTODY/qwen-snapshot" \
      --stage-receipt "$MRL0809_CUSTODY/qwen-stage.json" \
      --observation-out "$MRL0809_CUSTODY/qwen-observation.json" \
      --python-executable "$PWD/.venv/bin/python"

    rm -rf "$MRL0809_CUSTODY/qwen-snapshot"

**Before the isolated worker starts**, `probe` writes `qwen-observation.json.probe-start.json`. From that moment the attempt counts as begun (see Attempt consumption).

**The isolated worker enforces:**
- sandbox and seccomp: the v1 bubblewrap/seccomp sandbox, no network, `local_files_only`, `trust_remote_code=False`;
- model placement: `bitsandbytes-nf4-v1` (NF4, double quantization, float16 compute), with every module on CUDA device 0;
- prompt: the prompt comes from the model's own chat template, and its token IDs must equal the frozen digest;
- generation: greedy, single-beam, 12 new tokens, with every generated step's logits finite;
- headroom: peak GPU memory of 12 GiB or less;
- cleanup: GPU allocations return to the 64 MiB cleanup envelope.

## Candidate 2 — Gemma

    .venv/bin/python scripts/mesc_mrl_0809_runtime_feasibility_v2.py stage \
      --repository-root "$PWD" \
      --candidate "google/gemma-4-12B-it" \
      --destination "$MRL0809_CUSTODY/gemma-snapshot" \
      --receipt-out "$MRL0809_CUSTODY/gemma-stage.json"

    .venv/bin/python scripts/mesc_mrl_0809_runtime_feasibility_v2.py probe \
      --repository-root "$PWD" \
      --candidate "google/gemma-4-12B-it" \
      --snapshot "$MRL0809_CUSTODY/gemma-snapshot" \
      --stage-receipt "$MRL0809_CUSTODY/gemma-stage.json" \
      --observation-out "$MRL0809_CUSTODY/gemma-observation.json" \
      --python-executable "$PWD/.venv/bin/python"

    rm -rf "$MRL0809_CUSTODY/gemma-snapshot"

If the provider session changes between candidates, STOP. Do not combine observations from different sessions.

## Assemble and independently verify

    .venv/bin/python scripts/mesc_mrl_0809_runtime_feasibility_v2.py assemble \
      --repository-root "$PWD" \
      --observation "$MRL0809_CUSTODY/qwen-observation.json" \
      --observation "$MRL0809_CUSTODY/gemma-observation.json" \
      --receipt-out "$MRL0809_CUSTODY/runtime-feasibility-v2.json"

Copy only the final receipt and the two stage receipts to a separate clean verifier environment, at the exact receipt repository SHA:

    .venv/bin/python scripts/mesc_mrl_0809_runtime_feasibility_v2.py verify \
      --repository-root "$PWD" \
      --receipt "$MRL0809_VERIFY/runtime-feasibility-v2.json" \
      --stage-receipt "$MRL0809_VERIFY/qwen-stage.json" \
      --stage-receipt "$MRL0809_VERIFY/gemma-stage.json" \
      --verification-out "$MRL0809_VERIFY/independent-verification-v2.json"

**What admission requires:** only an independently verified v2 receipt may enter the v2 trust root and v2 evidence slot, through a separate minimal admission PR that needs its own exact-head approval.

**What admission may not touch:** the v1 slot, the v1 trust root and every v1 contract file must stay byte-identical. The successor gate refuses to pass otherwise.

## Attempt consumption

**Attempt consumed:** once any `.probe-start.json` marker exists, the attempt is consumed by any genuine failure:
- CUDA OOM or any other load failure;
- offload or placement outside device 0;
- non-finite logits, or empty or no generation;
- prompt-token drift;
- exceeding the 12 GiB headroom ceiling;
- cleanup failure.

Record `SUCCESSOR_STAGE4 = FAIL`, preserve every receipt, log and marker, and STOP. Do not substitute a candidate, enable offload, change quantization or retry without a new governed Founder decision.

**Not consumed:** only a provider/session failure before any probe-start marker exists may be classified `INFRASTRUCTURE_NON_EXECUTION`. A staging failure (download, identity or storage) before the first probe also leaves no marker. Record it, but this distinction must never be used to obtain unlimited retries.

## Stop conditions

STOP immediately, preserving evidence, if any of these occur:
- the GPU is not exactly a Tesla T4;
- the provider or session changes;
- zero cost cannot be attested;
- a credential or terms prompt appears;
- storage preflight fails;
- a candidate identity mismatches;
- offload is needed;
- network access is needed inside the sandbox;
- logits are non-finite;
- the headroom ceiling is exceeded;
- cleanup fails;
- a package drifts;
- `main` moves;
- any scientific corpus or Tier-3 material becomes accessible.

A successor Stage-4 PASS makes MRL-0809 eligible for a successor closeout only. It does not authorize RQ1 execution, which needs a separate Founder decision after MRL-0899 is recomputed.
