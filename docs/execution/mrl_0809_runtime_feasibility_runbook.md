# MRL-0809 Google Colab Runtime-Feasibility Runbook

Status: PREPARED_ONLY. Do not execute Stage 4 until Issue #429 Stage 3 is terminally qualified on the exact canonical main SHA/tree.

## Scope

This runbook is only for the one bounded, zero-cost MRL-0809 dual-candidate runtime-feasibility qualification authorized by Issue #429.

It does not authorize scientific corpus access, sealed Tier-3 disclosure, scientific experiment/evaluation execution, training, optimizer use, weight mutation, paid compute, candidate substitution, promotion, release, deployment, or clinical use.

## Hard prerequisites

Before consuming the one Stage-4 attempt, prove all of the following:

- the repository is on exact live origin/main;
- the working tree is clean;
- Stage 3 is terminally successful for the exact main SHA/tree;
- required CI is green for Python 3.11 and Python 3.12;
- CodeQL, Optional Extras / Backends, P01-04B2D Qualification, and P01-04B Publication Qualification are green;
- Issue #429 is open and still authorizes the same frozen candidates and constraints;
- Google Colab is the provider;
- the assigned GPU is exactly Tesla T4;
- the session is zero monetary cost;
- no scientific corpus or sealed Tier-3 material is mounted or copied into the runtime.

Any failed prerequisite means STOP without consuming a model-load attempt.

## Frozen candidates

Execute both, sequentially, in the same Colab provider session:

1. Qwen/Qwen3.8-27B
   - revision 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
2. google/gemma-4-31B-it
   - revision 842da3794eaa0b77d5f08bae87a17459d91ff475

No candidate substitution is allowed.

## Repository setup

Use a fresh clone of exact canonical main. Do not copy scientific data into the clone.

    git clone https://github.com/TheHalfMoon/MESC.git
    cd MESC
    git fetch origin main
    git checkout --detach origin/main
    git status --short
    git rev-parse HEAD
    git rev-parse HEAD^{tree}
    git ls-remote origin refs/heads/main

The local HEAD and live origin/main SHA must be identical.

Install only from the committed lock:

    uv python install 3.11
    uv sync --no-dev --extra rq1-runtime-feasibility --frozen
    uv cache clean
    sudo apt-get update
    sudo apt-get install -y bubblewrap

The dedicated `rq1-runtime-feasibility` extra is intentionally minimal and exact-pinned. It contains only `accelerate`, `bitsandbytes`, `huggingface-hub`, `torch`, `transformers`, and `xgrammar`, which are the packages required by the Stage-4 harness and its frozen runtime identity. Do not install the broader training extra or the development dependency group in the Colab qualification environment. This installation does not authorize or perform training. The harness never constructs an optimizer or invokes a training path.

## Provider identity and zero-cost attestation

Set the independently obtained Colab runtime/session identity. Do not invent or recycle an identity from another session.

    export MESC_MRL0809_ZERO_COST_ATTESTATION=1
    export MESC_COLAB_RUNTIME_ID="<independently-obtained-current-colab-session-id>"
    test -n "$COLAB_RELEASE_TAG"

The harness independently rejects non-Linux execution, any GPU other than exact Tesla T4, missing zero-cost attestation, missing provider identity, package-version drift, or non-canonical main.

## Evidence custody

All model snapshots and generated evidence must remain outside the repository:

    export MRL0809_CUSTODY=/content/mrl0809-custody
    mkdir -p "$MRL0809_CUSTODY"

Do not add custody files to Git.

## Storage-efficient bounded staging policy

The Stage-4 acquisition path is deliberately storage-bounded rather than protected by a coarse percentage or 10 GiB margin. For the locked `huggingface-hub==1.23.0` local-directory download path, the harness enforces all of the following:

- before any candidate byte is downloaded, the harness resolves the exact remote selected-payload manifest for **both** frozen candidates and requires the current writable filesystem to satisfy the larger roster-wide threshold; Qwen therefore cannot begin if Gemma is already known not to fit;
- downloads are serialized with `max_workers=1`;
- Xet transport/chunk caching is disabled for this bounded acquisition;
- the Hub cache lookup path is redirected to a fresh controlled cache under the empty candidate destination, so a pre-existing global Hub cache cannot trigger an unaccounted full-file copy;
- temporary download files and final payload files share the destination filesystem, and metadata/cache material is removed after successful staging;
- exact payload bytes are still selected from the frozen remote manifest and verified byte-for-byte after staging;
- processor metadata is candidate-specific and exact: Qwen uses `preprocessor_config.json`, while Gemma uses `processor_config.json`; the canonical receipt field remains `processor_config_sha256` and binds the already-frozen digest for each candidate;
- the preflight requires exact selected payload bytes plus a fixed 1 GiB control reserve;
- the receipt records the exact roster preflight candidate set, roster-wide required free bytes, candidate-specific required bytes, pre/post-stage free bytes, serialized worker count, cache-reuse policy, and Xet policy;
- the stage fails closed if the 1 GiB control reserve is not still present after successful download cleanup.

For the currently frozen manifests this means:

- Qwen selected payload: `55,586,036,114` bytes; required pre-stage free space: `56,659,777,938` bytes;
- Gemma selected payload: `62,578,656,403` bytes; required pre-stage free space: `63,652,398,227` bytes.

The 1 GiB reserve is not model payload and is not permission to fill the filesystem to zero. It is an explicit fail-closed operational floor retained after staging for repository receipts, metadata, filesystem control, and probe startup. Any download implementation or dependency change that invalidates the single-worker same-filesystem bound requires a new governed repair before another Stage-4 attempt.

## Candidate 1 — Qwen

Stage only the authorized MRL-0801 weight allowlist plus required tokenizer/processor metadata. The harness performs a remote size preflight before download and refuses to start if free storage is below the bounded threshold.

    .venv/bin/python scripts/mesc_mrl_0809_runtime_feasibility.py stage \
      --repository-root "$PWD" \
      --candidate "Qwen/Qwen3.8-27B" \
      --destination "$MRL0809_CUSTODY/qwen-snapshot" \
      --receipt-out "$MRL0809_CUSTODY/qwen-stage.json"

The stage command verifies exact revision metadata and the full SafeTensors identity against the already admitted MRL-0801 weights_sha256 and artifact_identity_sha256. It also binds every staged payload file to an exact root-level path, byte count, and SHA-256 digest, and the probe rejects any added, removed, symlinked, or modified payload before isolated execution.

Run the isolated probe:

    .venv/bin/python scripts/mesc_mrl_0809_runtime_feasibility.py probe \
      --repository-root "$PWD" \
      --candidate "Qwen/Qwen3.8-27B" \
      --snapshot "$MRL0809_CUSTODY/qwen-snapshot" \
      --stage-receipt "$MRL0809_CUSTODY/qwen-stage.json" \
      --observation-out "$MRL0809_CUSTODY/qwen-observation.json" \
      --python-executable "$PWD/.venv/bin/python"

The probe reverifies the staged SafeTensors bytes before entering a no-network bubblewrap sandbox. Colab CUDA requires host thread IDs to remain aligned with the NVIDIA driver, so the runtime-specific boundary uses explicit user, network, IPC, UTS, and cgroup namespaces while intentionally omitting a PID namespace. The `/proc` root remains a bounded 4 KiB tmpfs: only the sandbox process's own `/proc/self` view is bound writable for CUDA thread-name operations, while `/proc/cpuinfo`, `/proc/sys/vm/mmap_min_addr`, and `/proc/driver/nvidia` are bound read-only. No provider process table is exposed. The CUDA loader receives only the non-secret fixed driver environment (`LD_LIBRARY_PATH=/usr/lib64-nvidia`, `NVIDIA_VISIBLE_DEVICES=all`, `NVIDIA_DRIVER_CAPABILITIES=compute,utility`). Because PID namespaces are intentionally omitted for Colab CUDA compatibility, a deterministic x86_64 seccomp filter denies process-signaling syscalls (`kill`, queued signal calls, thread signal calls, and `pidfd_send_signal`, including x32 syscall-number variants). Nested NVIDIA device parents are still created before explicit device binds. The model must remain GPU-only with no CPU/disk offload or capacity fallback.

After a successful unload receipt, remove the Qwen snapshot to recover storage:

    rm -rf "$MRL0809_CUSTODY/qwen-snapshot"

Do not delete the stage receipt or observation.

## Candidate 2 — Gemma

Repeat in the same Colab provider session:

    .venv/bin/python scripts/mesc_mrl_0809_runtime_feasibility.py stage \
      --repository-root "$PWD" \
      --candidate "google/gemma-4-31B-it" \
      --destination "$MRL0809_CUSTODY/gemma-snapshot" \
      --receipt-out "$MRL0809_CUSTODY/gemma-stage.json"

    .venv/bin/python scripts/mesc_mrl_0809_runtime_feasibility.py probe \
      --repository-root "$PWD" \
      --candidate "google/gemma-4-31B-it" \
      --snapshot "$MRL0809_CUSTODY/gemma-snapshot" \
      --stage-receipt "$MRL0809_CUSTODY/gemma-stage.json" \
      --observation-out "$MRL0809_CUSTODY/gemma-observation.json" \
      --python-executable "$PWD/.venv/bin/python"

    rm -rf "$MRL0809_CUSTODY/gemma-snapshot"

If the provider session changes between candidates, STOP. Do not combine observations from different sessions.

## Assemble the canonical Stage-4 receipt

Only after both candidate observations succeed:

    .venv/bin/python scripts/mesc_mrl_0809_runtime_feasibility.py assemble \
      --repository-root "$PWD" \
      --observation "$MRL0809_CUSTODY/qwen-observation.json" \
      --observation "$MRL0809_CUSTODY/gemma-observation.json" \
      --receipt-out "$MRL0809_CUSTODY/runtime-feasibility.json"

    sha256sum "$MRL0809_CUSTODY/runtime-feasibility.json"

Assembly fails closed unless both observations bind one identical provider execution identity, one identical runtime identity, the exact canonical main SHA/tree, the immutable static-prerequisite manifest, the exact dependency lock, exact candidates, and the same bitsandbytes-nf4-v1 representation.

## Stage 5 — independent receipt verification

Do not modify the trust root or evidence slot in the Colab session.

Copy the final canonical receipt plus the two canonical stage receipts to a separate clean verifier environment. Do not copy either model snapshot. Independently re-fetch the exact repository SHA/tree named by the receipt; if live canonical main has moved, STOP rather than silently verifying a stale run.

Run the committed independent verifier from that clean environment. Put the three copied evidence files in a verifier-only custody directory first:

    export MRL0809_VERIFY=/path/to/mrl0809-independent-verification
    mkdir -p "$MRL0809_VERIFY"

    .venv/bin/python scripts/mesc_mrl_0809_runtime_feasibility.py verify \
      --repository-root "$PWD" \
      --receipt "$MRL0809_VERIFY/runtime-feasibility.json" \
      --stage-receipt "$MRL0809_VERIFY/qwen-stage.json" \
      --stage-receipt "$MRL0809_VERIFY/gemma-stage.json" \
      --verification-out "$MRL0809_VERIFY/independent-verification.json"

    sha256sum "$MRL0809_VERIFY/runtime-feasibility.json"
    sha256sum "$MRL0809_VERIFY/independent-verification.json"

The verifier uses the canonical repository validator and independently recomputes the stage-receipt digests and exact harness binding. It emits a deterministic PASS artifact only after the final receipt, both stage receipts, canonical repository SHA/tree, static manifest, dependency lock, and runtime identity agree.

The independent verification must recompute:

- receipt SHA-256;
- static-prerequisite manifest SHA-256;
- dependency-lock SHA-256;
- repository SHA/tree binding;
- the full embedded runtime-identity SHA-256;
- the embedded harness SHA-256 against scripts/mesc_mrl_0809_runtime_feasibility.py at the exact receipt repository SHA;
- exact candidate revision/metadata identities plus the admitted MRL-0801 weights_sha256 and artifact_identity_sha256 values;
- each candidate stage-receipt SHA-256 binding;
- each stage receipt's exact SafeTensors file manifest, re-deriving both `weights_sha256` and `artifact_identity_sha256` from its recorded raw-byte file identities;
- each candidate embedded synthetic-generation evidence, including the exact fixed prompt identity and bounded generated token IDs;
- exact Tesla T4 / Google Colab / CPython 3.11 / locked package / bitsandbytes-nf4-v1 runtime policy;
- zero-cost, no-network, no-training, no-mutation, no-fallback, and cleanup constraints.

Only an independently verified canonical receipt may proceed to the separate minimal trust/evidence-slot admission PR.

## Stop conditions

STOP immediately and preserve the failure evidence without substitution if any of these occur:

- GPU is not exact Tesla T4;
- provider or session identity changes;
- zero-cost status cannot be attested;
- storage preflight fails;
- exact candidate revision/metadata/weight identity fails;
- model requires CPU or disk offload;
- local-only isolated load fails;
- any network access is required inside isolated load/generation;
- synthetic text-only generation fails;
- cleanup/unload fails;
- package identity drifts;
- repository main moves after qualification begins;
- any scientific corpus or sealed Tier-3 material becomes accessible to the probe.

A failed Stage-4 attempt does not authorize provider substitution, paid compute, smaller models, alternate quantization, altered revisions, or a scientific run.
