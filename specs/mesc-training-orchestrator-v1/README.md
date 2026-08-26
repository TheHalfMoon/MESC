# MESC Training Orchestrator V1

Status: **IMPLEMENTATION / FAIL-CLOSED / NO TRAINING AUTHORIZATION GRANTED**

Canonical base:

```text
BASE_MAIN_SHA = fcd17b081caae015e239176f9e02916131e4626c
BASE_MAIN_TREE = 559aa0e381d03e536bb2680dcc78a18d494dc4e4
PR_200 = CLOSED_CANONICAL
TRAINING_EXECUTION = NOT_AUTHORIZED_BY_THIS_PACKAGE
```

## Purpose

After the local Hugging Face SFT backend and the `training-hf-sft` dependency-lock gate,
the repository still lacked the fail-closed wiring layer that observes the actual local
execution environment, consumes already-canonical training authority, constructs the
backend explicitly, and invokes `execute_training(...)`.

This package is that layer.

## Scope

This package changes exactly three paths:

```text
specs/mesc-training-orchestrator-v1/README.md
src/medscale/mesc/_training_orchestrator_v1.py
tests/test_mesc_training_orchestrator_v1.py
```

Public `medscale mesc-train` CLI registration is intentionally deferred until typed
manifest serialization exists. Reproduction commands must call the library orchestrator
API; they must not advertise an unregistered CLI.

It does not:

- invent runtime-qualification or training-authorization receipts;
- download models or accept gated terms;
- install the training extra in default CI;
- redefine readiness, launch, corpus-binding, attestation, executor, or backend contracts;
- publish release artifacts; or
- claim `TRAINING_READY`, `RELEASE_READY`, or MedScale Spec 012 admission readiness.

## Required behavior

`run_training_orchestrator(...)` must:

1. assess or accept a readiness report and require `READY_TO_LAUNCH`;
2. rebuild the launch plan and require byte-exact equality with the supplied plan;
3. observe or accept a `TrainingExecutionEnvironment` and require equality with the
   selected run plan (`repository_sha`, `repository_tree`, `dependency_lock_sha256`,
   `runner_class`, `python_version`, `os_name`, `gpu_model`);
4. attest already-local model and corpus assets through
   `attest_local_training_assets(...)`;
5. construct `HfLocalSftBackend` explicitly (or an injected backend factory for tests);
6. invoke `execute_training(...)` only when every prior gate already passes; and
7. fail closed on any mismatch.

Observation helpers:

- `hash_dependency_lock` — SHA-256 of exact `uv.lock` bytes (no-follow);
- `observe_repository_identity` — `git rev-parse HEAD` and `HEAD^{tree}`;
- `observe_python_version` / `observe_os_name`;
- `observe_gpu_model` — requires an explicit `gpu_probe` (no invented GPU identity);
- `observe_training_execution_environment` — composes the above.

## Authority boundary

This package grants **no** training authority by itself.

Actual training still requires:

- real authorized local model assets;
- real qualified corpus bytes;
- qualified runtime/GPU evidence receipts already bound into readiness/launch;
- an explicit training-authorization receipt already bound into readiness/launch; and
- operator execution outside default CI.

Default CI must keep using injected fakes and must not import Torch / Transformers / TRL /
PEFT / Accelerate / bitsandbytes at module import time beyond the already-lazy backend
runtime builder.

## Next gate

After this orchestrator is `CLOSED_CANONICAL`, the remaining repository-side gate before
`TRAINING_CODE_READY` is the final repository training-readiness audit named by the HF
local SFT backend remaining-gates section.

Release of a MedScale-admissible artifact remains further gated by real authorized
training/evaluation evidence and MESC release governance — not by this package alone.
