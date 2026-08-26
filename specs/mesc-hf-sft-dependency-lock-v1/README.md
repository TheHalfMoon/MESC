# MESC Hugging Face SFT Dependency Lock V1

Status: **IMPLEMENTATION / DEPENDENCY-LOCK GATE / NO TRAINING PERFORMED**

Canonical base:

```text
BASE_MAIN_SHA = c818f9e657fa98c8843557b0a767117817a1dcf9
BASE_MAIN_TREE = 805f4f612e09eb077fdac1c63ba76604e4b16c57
PR_190 = CLOSED_CANONICAL
HF_LOCAL_SFT_BACKEND_V1 = CANONICAL
TRAINING_EXECUTION = NOT_PERFORMED
```

## Purpose

The canonical local Hugging Face SFT backend deliberately landed without declaring or
locking the production training stack. That separation prevented backend implementation
from pretending that a clean checkout could reproduce a real LoRA/QLoRA runtime.

This gate closes that repository-only gap. It declares one exact optional training extra
and resolves its complete transitive dependency graph into the canonical `uv.lock`.
The gate does not install the training extra in default CI and does not execute a model,
GPU workload, provider request, inference, or training action.

## Canonical optional extra

The only V1 production training extra is:

```text
training-hf-sft
```

Its top-level packages are exact pins:

```text
accelerate==1.14.0
bitsandbytes==0.50.1
datasets==5.0.1
peft==0.20.0
torch==2.13.0
transformers==5.15.1
trl==1.10.0
```

The exact pins are intentional. `TrainingRunPlan.dependency_lock_sha256` is part of the
canonical launch identity, so the repository must not represent a floating production
training stack as reproducible.

Transitive package identities remain owned by `uv.lock`; they are not duplicated into a
second hand-maintained manifest.

## Compatibility basis

The selected versions were checked against current upstream package metadata before this
gate was constructed:

- TRL 1.10.0 requires Accelerate >=1.4.0, Datasets >=4.7.0, and Transformers >=4.56.2;
- TRL exposes PEFT and quantization integrations but does not make PEFT or bitsandbytes
  mandatory, so this repository pins both explicitly because the backend imports them;
- PEFT 0.20.0 requires Torch >=1.13.0 and accepts Transformers plus Accelerate >=0.21.0;
- bitsandbytes 0.50.1 requires Torch >=2.4,<3 and publishes Linux x86-64 wheels for the
  Python versions used by the repository;
- Transformers 5.15.1 supports Python 3.10+ and PyTorch 2.5+; and
- the selected Torch 2.13.0 publishes PyPI wheels through CPython 3.14 but no
  source distribution, so the project metadata is explicitly bounded to Python
  `>=3.11,<3.15`; and
- repository CI continues to qualify Python 3.11 and 3.12, while the dependency
  resolver gate separately proves the frozen training extra resolves at Python 3.14.

Those upstream ranges are evidence for candidate compatibility, not the final authority.
The final authority for this repository is successful `uv` resolution into the exact
canonical lock plus repository CI.

## Default environment remains lean

`medscale` keeps:

```text
project.dependencies = []
```

The training stack is optional and must not be installed by ordinary:

```text
uv sync --frozen
```

Default lint, typing, unit/integration tests, and `medscale check` therefore remain free of
Torch, Transformers, TRL, PEFT, Datasets, Accelerate, and bitsandbytes imports or GPU work.

A later operator who is independently authorized and whose runtime passes the training
qualification gates may explicitly request the extra. Declaring the extra is not execution
authority.

## Lock authority

`uv.lock` is the canonical complete dependency graph for this gate.

A later training launch must bind the SHA-256 of the exact lock bytes used to qualify the
runtime. The existing launch-plan and executor contracts already carry that
`dependency_lock_sha256`; this gate does not redefine those contracts.

Any future change to a top-level training package or a resolved transitive dependency is a
new lock identity and therefore changes the environment identity of future launch plans.

## Runtime scope

The dependency graph is resolved as packaging metadata. This gate does not claim that every
platform can execute `MESC-HF-LOCAL-SFT-BACKEND-V1`.

The canonical backend V1 currently requires Linux publication semantics for atomic
no-replace result publication and separately requires a BF16-capable CUDA runtime for real
training. Those runtime facts remain enforced by the backend and the later orchestrator;
they are not weakened by cross-platform package metadata.

## Historical publication-boundary reconciliation

The P01-04B publication implementation qualification recorded `pyproject.toml` and
`uv.lock` byte digests as part of the exact adoption identity of that historical
four-path implementation increment. Its continuously executed test originally
treated those historical packaging bytes as if they could never change again.

This gate does not rewrite those historical digests. It keeps them recorded as
adoption-baseline evidence, while continuing byte-identity enforcement remains on
the P01-04B runtime/split paths that are still required to be immutable. The
publication harness also explicitly prohibits the new training packages from
appearing in the private fixture publisher. This preserves the original publication
boundary while allowing a separately specified and qualified dependency-lock gate.

The dedicated cross-platform P01-04B publication qualification must return green on
the exact dependency-lock PR head after this reconciliation.

## Acceptance

This gate is complete only when exact-head evidence proves all of the following:

1. project metadata declares Python `>=3.11,<3.15`, matching the locked Torch
   artifact ceiling rather than advertising an unsupported future interpreter;
2. `training-hf-sft` contains exactly the seven pinned top-level packages above;
3. `uv lock` resolves the complete project without dependency conflicts;
4. `uv lock --check` accepts the generated lock as current;
5. the exact top-level versions appear in `uv.lock`;
6. `uv sync --frozen` succeeds without selecting the training extra;
7. dry-run syncs of `training-hf-sft` resolve from the frozen lock without
   installation, including a Python 3.14 edge-of-range check;
8. the repository dependency-lock regression tests pass;
9. normal Ruff, formatter, strict mypy, full pytest, and `medscale check` remain green on
   Python 3.11 and 3.12;
10. the dedicated P01-04B publication qualification remains green on every supported
   OS/Python matrix entry after historical dependency-baseline reconciliation; and
11. CodeQL and material review findings are clean on the exact PR head.

## Non-claims

This gate performs no:

- training-extra installation in default CI;
- model or tokenizer download;
- model-weight read or load;
- Hub authentication or token use;
- provider access;
- gated-license acceptance;
- remote-code execution;
- dataset acquisition;
- GPU probing or CUDA execution;
- inference; or
- training/fine-tuning.

It does not create a runtime-qualification receipt or training-authorization receipt.

## Next gate

After this dependency lock is canonical, the next repository-side implementation layer is
the training CLI/orchestrator. It must observe the actual local repository, lock, Python,
OS, GPU, model, corpus, readiness, launch-plan, local-asset, runtime-qualification, and
training-authorization evidence; construct the canonical backend explicitly; fail closed
on any mismatch; and invoke the existing executor only when all required authority is
already present.

Actual training remains separately authorized and is not part of that implementation gate.
