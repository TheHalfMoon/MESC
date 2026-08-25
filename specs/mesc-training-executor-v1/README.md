# MESC Training Executor V1

Status: **IMPLEMENTATION / FAIL-CLOSED EXECUTION BOUNDARY / NO REAL TRAINING AUTHORITY GRANTED**

Canonical base:

```text
BASE_MAIN_SHA = 2ccce1984363251da8583337b5861600f6fcd3a8
BASE_MAIN_TREE = 43ed6f1f7344baa8ed913a943d342684b2f7b2a3
PR_185 = CLOSED_CANONICAL
TRAINING_LOCAL_ASSET_ATTESTATION = CANONICAL
```

## Purpose

Training readiness, launch planning, corpus binding, and local-asset attestation are now
canonical repository contracts. None of those contracts should be converted directly into
an unconstrained backend call. This package adds the narrow execution boundary that
recomputes upstream authority, snapshots one exact execution manifest, invokes only an
explicitly supplied backend, and returns a content-addressed terminal receipt.

The core executor is backend-neutral. It performs no model loading, network access, provider
access, authentication, license acceptance, GPU execution, inference, or training itself.
Default tests use fake backends only.

## Scope

Exactly these three paths belong to this implementation:

```text
specs/mesc-training-executor-v1/README.md
src/medscale/mesc/_training_executor_v1.py
tests/test_mesc_training_executor_v1.py
```

No workflow, dependency, CLI, model registry, dataset, readiness, launch-plan, or local
asset contract is changed.

## Canonical inputs

`execute_training(...)` requires exact canonical instances of:

- `TrainingReadinessManifest`;
- `TrainingReadinessReport`;
- `TrainingLaunchPlan`;
- `TrainingCorpusBindingReport`;
- `TrainingLocalAssetAttestationReport`;
- `TrainingExecutionEnvironment`;
- selected `TrainingRole`; and
- one explicitly injected `TrainingBackend`.

No backend means fail closed.

## Independent upstream revalidation

The executor does not trust caller booleans or a supplied READY status.

Before backend invocation it:

1. recomputes `assess_training_readiness(manifest)`;
2. requires the supplied readiness report to equal the recomputed report;
3. requires recomputed readiness to be `READY_TO_LAUNCH`;
4. rebuilds the launch plan from the exact manifest, recomputed readiness, and supplied
   compact/reasoner run plans;
5. requires the supplied launch plan to equal the rebuilt plan;
6. selects the exact role-specific run plan;
7. requires canonical PASS corpus binding for that exact training-dataset identity;
8. requires canonical PASS local-asset attestation bound to the exact launch, selected run,
   corpus binding, dataset, model id, revision, weight identity, corpus raw bytes, and local
   model-verifier receipt;
9. refuses any attestation that records network access, remote code, or gated-term
   acceptance; and
10. requires the caller-observed execution environment to match the selected run's exact
    repository SHA, repository tree, dependency lock, runner class, Python version, OS, and
    GPU identity.

## Execution environment observation

`TrainingExecutionEnvironment` is an explicit boundary input. The core deliberately does
not run Git, inspect dependency files, probe GPUs, or mutate the machine. A future CLI or
qualified runtime adapter is responsible for obtaining the actual observed values and
passing them to this contract.

The environment is content-addressed as `environment_sha256` and is bound into the backend
manifest and terminal receipt.

## Core-owned execution manifest

After all checks pass, the executor copies primitive canonical values into a new
`TrainingExecutionManifest` owned by the core. It binds at least:

```text
launch_plan_sha256
run_plan_sha256
readiness_manifest_sha256
corpus_binding_sha256
local_asset_attestation_sha256
environment_sha256
role
experiment_id
model_id
revision
weights_sha256
training_dataset_sha256
recipe_id
seeds
runner_class
python_version
os_name
gpu_model
repository_sha
repository_tree
dependency_lock_sha256
runtime_qualification_sha256
training_authorization_receipt_sha256
canonical_corpus_sha256
canonical_corpus_byte_count
model_verifier_receipt_sha256
result_namespaces
```

`execution_manifest_sha256` is deterministic.

Only this core-owned manifest is passed to the backend. The upstream caller-owned manifest,
launch plan, binding, attestation, and environment are not exposed to the backend. After the
backend returns, the executor recomputes the execution-manifest identity and fails if the
backend mutated it. Receipt construction then uses only the validated core-owned manifest,
closing the post-validation caller-object mutation window.

## Backend protocol

The backend implements:

```text
TrainingBackend.execute(
    *,
    manifest: TrainingExecutionManifest,
) -> TrainingBackendResult
```

The core does not provide a default backend. Tests inject fake implementations only.

A backend result records:

- `SUCCEEDED`, `FAILED`, or `ABORTED`;
- backend id and version;
- actual `started_at` and `finished_at` timestamps supplied by the execution boundary;
- final content-addressed result artifacts for success; and
- a failure reason for failed/aborted execution.

The core never fabricates execution timestamps.

## Timestamp contract

Backend timestamps must be valid canonical UTC RFC3339 values with whole seconds:

```text
YYYY-MM-DDTHH:MM:SSZ
```

`finished_at` cannot precede `started_at`.

## Result artifacts and namespace confinement

Each successful canonical result artifact binds:

```text
path
sha256
byte_count
```

Artifact paths must be canonical repository-relative POSIX paths. The executor sorts final
artifacts by path before constructing the receipt.

For `SUCCEEDED`:

- every artifact must equal or descend from one of the selected run's planned
  `result_paths` namespaces;
- no artifact may escape those namespaces;
- every planned namespace must be represented by at least one final artifact; and
- the sorted artifact set is content-addressed as `result_manifest_sha256`.

The receipt independently recomputes the result-manifest identity, preventing a direct
forged success receipt from pairing arbitrary artifact identities with an unrelated digest.

## Failure and abort semantics

`FAILED` and `ABORTED` are terminal observations, not partial successes.

They require:

```text
result_artifacts = ()
result_manifest_sha256 = null
failure_reason = non-empty
```

A backend exception produces `TrainingExecutionError`; the core does not invent timestamps,
a failure receipt, or successful artifacts on the backend's behalf.

Concrete backends remain responsible for staging/atomic publication of their filesystem
outputs. This core contract ensures that partial outputs cannot be represented as canonical
terminal artifacts in a failed or aborted receipt.

## TrainingExecutionReceipt V1

The canonical terminal receipt binds:

```text
disposition
launch_plan_sha256
run_plan_sha256
readiness_manifest_sha256
corpus_binding_sha256
local_asset_attestation_sha256
execution_manifest_sha256
environment_sha256
role
experiment_id
model_id
revision
weights_sha256
training_dataset_sha256
repository_sha
repository_tree
dependency_lock_sha256
runtime_qualification_sha256
training_authorization_receipt_sha256
backend_id
backend_version
started_at
finished_at
result_artifacts
result_manifest_sha256
failure_reason
```

`receipt_sha256` is deterministic.

## Security and authority boundary

This implementation does **not** authorize or perform:

- model-weight download or retrieval;
- Hub/provider authentication;
- acceptance of gated model terms;
- credential access;
- network model access;
- remote code execution;
- model loading;
- inference or generation;
- GPU execution; or
- real training/fine-tuning.

Repository implementation of an executor is not equivalent to a real training authorization.
The launch plan must already bind canonical runtime qualification and training authorization
receipts before this boundary can be crossed in a real execution environment.

## Default CI

Default CI uses fake backends and fixture identities only. It does not import or execute
Torch, Transformers, TRL, PEFT, Accelerate, bitsandbytes, model weights, providers, GPUs, or
training workloads.

## Next repository gate

After this executor is qualified and canonical, the next planned work is an optional
local-only Hugging Face SFT backend. Before implementing it, the repository must inspect
current official Transformers/TRL/PEFT/Accelerate APIs and resolve the canonical filesystem
semantics of `weights_sha256`; this executor deliberately does not invent those semantics.
