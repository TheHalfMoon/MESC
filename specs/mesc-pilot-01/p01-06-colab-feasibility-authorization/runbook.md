# P01-06 — Google Colab Feasibility Smoke Runbook

Status: **AUTHORIZED ON CANONICAL MERGE / NOT EXECUTED**

Controlling decision:

`FD-P01-06-COLAB-1`

Issue:

`#360`

This runbook is an execution protocol. Its presence is not execution evidence.

## 1. Purpose

Determine whether the exact Pilot-01 primary Llama 3.2 3B target can load and complete a
minimal non-scientific generation-path smoke on the GPU actually allocated by Google Colab,
and record the resulting memory feasibility facts.

If the primary path fails specifically because of demonstrated memory pressure, the exact
1B low-memory fallback may be tested under the conditional authorization in
`FD-P01-06-COLAB-1`.

This phase does not run Pilot-01 benchmark evaluation and does not train an adapter.

## 2. Exact identities

Primary:

```text
meta-llama/Llama-3.2-3B-Instruct
revision = 0cb88a4f764b7a12671c53f0838cd831a0843b95
```

Conditional fallback:

```text
meta-llama/Llama-3.2-1B-Instruct
revision = 9213176726f574b556790deb65791e0c5aa438b6
```

Repository execution identity:

```text
AUTHORIZATION_MAIN_SHA = exact canonical main commit containing FD-P01-06-COLAB-1
AUTHORIZATION_MAIN_TREE = tree of AUTHORIZATION_MAIN_SHA
```

Do not run from an unmerged authorization branch.

## 3. Required account state

Before model acquisition:

- the Colab session must be a Google-hosted GPU runtime;
- the executing Hugging Face account must already have legitimate access to the selected
  Llama repository;
- `HF_TOKEN` must be supplied through Colab Secrets or an equivalent non-printing secret
  mechanism;
- no token may be pasted into notebook source, logs, repository files, or the final report.

If gated access is absent, stop with:

```text
FINAL_DISPOSITION = BLOCKED
STOP_REASON = GATED_MODEL_ACCESS_UNAVAILABLE
```

Do not accept terms through this runbook and do not substitute another model.

## 4. Runtime preflight

Record, without guessing:

```text
python_version
torch_version
cuda_available
cuda_version
gpu_count
gpu_model
gpu_total_memory_bytes
colab_runtime_class
```

The GPU model must come from the live runtime. No H100/A100/L4/T4 class is assumed in
advance.

Fail closed if:

- CUDA is unavailable;
- GPU count is not exactly one for this smoke;
- GPU identity cannot be observed;
- repository checkout does not resolve to the exact authorization commit;
- the locked environment cannot be installed.

## 5. Repository environment

Use the exact canonical authorization commit and the existing repository Transformers
backend. The intended setup is conceptually:

```bash
git checkout <AUTHORIZATION_MAIN_SHA>
uv sync --locked --extra backends-transformers
```

The exact environment installer may differ in Colab, but dependency resolution must remain
bound to the repository lock. Do not add Unsloth, PEFT, TRL, bitsandbytes, or any training
extra merely to make P01-06 pass.

If a Colab image preinstalls conflicting packages, record the conflict and stop rather than
silently changing the canonical dependency set.

## 6. Model acquisition

For the active target:

1. authenticate without printing the token;
2. resolve the exact pinned revision;
3. require remote resolved revision equality;
4. acquire only the files needed for Transformers model/tokenizer load;
5. preserve a metadata-only local file manifest with file sizes and SHA-256 values;
6. use `trust_remote_code=False`;
7. reject alternate revisions or model substitutions.

A cached snapshot is acceptable only if its repository/revision identity is verified before
use.

## 7. Primary smoke

The primary smoke must not use PubMedQA or any other scientific evaluation content.

Use a fixed synthetic operational input whose purpose is only to exercise tokenizer,
model-load, device placement, and bounded generation. The exact text must be recorded in the
execution report or its hash if the final protocol elects to avoid raw prompt text.

Required sequence:

1. reset CUDA peak-memory statistics when supported;
2. instantiate tokenizer and model;
3. place the model on the authorized GPU using the ordinary repository-compatible
   Transformers path;
4. record allocated/reserved memory after load;
5. execute one bounded generation with a very small output-token ceiling;
6. synchronize the device;
7. record peak allocated/reserved memory;
8. destroy model/tokenizer references and clear cache;
9. stop before any benchmark/scientific evaluation.

Success means only:

```text
PRIMARY_LOAD = PASS
SYNTHETIC_SMOKE = PASS
```

It does not mean model quality, Pilot-01 success, B0/B1 accuracy, MRL readiness, or training
readiness.

## 8. Primary memory failure and fallback

The fallback is allowed only when the primary failure is genuinely memory-related.

Examples of qualifying evidence include a CUDA out-of-memory error or an observed memory
ceiling that prevents the authorized primary load/smoke from completing.

Before fallback, record:

```text
PRIMARY_LOAD = FAIL_MEMORY
PRIMARY_FAILURE_CLASS = <observed class>
PRIMARY_PEAK_MEMORY_BYTES = <observed value or null if unavailable>
FALLBACK_REASON = PRIMARY_MEMORY_LIMIT
```

Then repeat the same protocol using only:

```text
meta-llama/Llama-3.2-1B-Instruct
revision = 9213176726f574b556790deb65791e0c5aa438b6
```

Fallback is not allowed for:

- missing gated access;
- wrong revision;
- network/authentication failure;
- dependency failure;
- Colab disconnect;
- unrelated Python/runtime exception.

If both primary and authorized fallback fail for memory feasibility:

```text
FINAL_DISPOSITION = BLOCKED
STOP_REASON = COLAB_MEMORY_INSUFFICIENT
```

## 9. Required evidence record

The execution output must be metadata-only and canonicalizable. At minimum it records:

```text
schema_version = MESC-P01-06-COLAB-FEASIBILITY-V1
repository_sha
repository_tree
execution_started_at_utc
execution_completed_at_utc
colab_runtime_class
python_version
torch_version
cuda_version
gpu_model
gpu_count
gpu_total_memory_bytes
primary_model_id
primary_model_revision
primary_snapshot_manifest_sha256
primary_load_disposition
primary_allocated_memory_after_load_bytes
primary_reserved_memory_after_load_bytes
primary_peak_allocated_memory_bytes
primary_peak_reserved_memory_bytes
synthetic_smoke_input_sha256
synthetic_smoke_disposition
fallback_used
fallback_model_id
fallback_model_revision
fallback_snapshot_manifest_sha256
fallback_load_disposition
fallback_peak_allocated_memory_bytes
fallback_peak_reserved_memory_bytes
fallback_reason
final_disposition
stop_reason
```

No credentials, weights, tokenizer/model snapshot bytes, benchmark examples, scientific
prompts, or generated benchmark answers belong in the repository evidence record.

## 10. Final dispositions

Allowed terminal dispositions:

```text
PASS_PRIMARY
PASS_FALLBACK
BLOCKED
```

Interpretation:

- `PASS_PRIMARY` — primary 3B path is feasible on the observed Colab GPU.
- `PASS_FALLBACK` — primary failed specifically for memory, and the exact authorized 1B
  fallback passed.
- `BLOCKED` — any mandatory prerequisite or feasibility condition failed.

A disconnect is `BLOCKED`, not success.

## 11. Stop boundary

After the feasibility record is captured, stop.

Do not:

- run B0/B1 scientific evaluation;
- inspect test-partition content;
- create an adapter;
- run QLoRA;
- install or use Unsloth for training;
- publish model artifacts or metrics;
- continue automatically into P01-07.

P01-07 eligibility must be determined only after P01-06 evidence is independently reviewed,
qualified, and adopted on canonical main.

## 12. Unsloth successor note

If P01-06 closes successfully, P01-07 planning should evaluate **Google Colab + Unsloth** as
a candidate QLoRA execution implementation because it can reduce memory pressure while
preserving the MESC manifest/receipt authority model.

That evaluation must remain separate from P01-06. Unsloth must be treated as an execution
adapter beneath MESC governance, not as a source of scientific or authorization truth.
