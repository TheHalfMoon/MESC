# MESC Hugging Face Local SFT Backend V1

Status: **IMPLEMENTATION / LOCAL-ONLY LORA+QLORA BACKEND / NO TRAINING EXECUTED**

Canonical base:

```text
BASE_MAIN_SHA = ad2d9911cebc0c5eb81faf64e05cec9f419ce3b0
BASE_MAIN_TREE = 5dce679ff8599fe56b116e4963a6b3a4d25c7bc1
PR_188 = CLOSED_CANONICAL
HF_SAFETENSORS_WEIGHT_IDENTITY_V1 = CANONICAL
TRAINING_EXECUTION = NOT_PERFORMED
```

## Purpose

The canonical training executor now has a concrete SafeTensors weight identity but still
accepts only an injected `TrainingBackend`. This package implements the first concrete
backend for already-local Hugging Face supervised fine-tuning.

The backend is deliberately narrower than a general Hugging Face launcher. It consumes a
core-owned `TrainingExecutionManifest`, one exact canonical `TrainingRecipe`, one
already-local SafeTensors model root, one already-attested canonical JSONL corpus path, one
repository root, and one injected SFT runtime.

No code in default CI downloads or loads a model, imports Torch/Hugging Face training
packages, accesses a GPU, or executes training.

## Scope

This implementation gate adds exactly three paths:

```text
specs/mesc-hf-local-sft-backend-v1/README.md
src/medscale/mesc/_training_hf_local_sft_backend_v1.py
tests/test_mesc_training_hf_local_sft_backend_v1.py
```

It intentionally does not yet change `pyproject.toml` or `uv.lock`.

That is not permission to use undeclared packages in a canonical training run. Before
`TRAINING_CODE_READY` can be declared, a later repository gate must pin the production
training extra and dependency lock for the exact supported Transformers/TRL/PEFT/
Accelerate/Datasets/bitsandbytes/Torch surface. The backend records runtime package
versions in its result summary so runtime qualification can compare observed software
against that later locked environment.

## Official API basis checked before implementation

The V1 implementation was designed against current official Hugging Face APIs on
2026-08-25.

The required API choices are:

- `AutoTokenizer.from_pretrained(...)` and `AutoModelForCausalLM.from_pretrained(...)`
  operate on the supplied local directory only;
- `local_files_only=True`;
- `trust_remote_code=False`;
- `token=False`, preventing use of a token saved by `hf auth login`;
- `use_safetensors=True` for model loading;
- Transformers `dtype=` for the current model-loading API;
- `BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
  bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.bfloat16)` for QLoRA;
- `prepare_model_for_kbit_training(...)` before QLoRA adapter construction;
- PEFT `LoraConfig(..., bias="none", task_type="CAUSAL_LM")`;
- TRL `SFTTrainer` receives an already-loaded model and explicit `processing_class`;
- `SFTConfig(report_to="none", push_to_hub=False, trust_remote_code=False)`;
- prompt-completion data with `completion_only_loss=True`; and
- `datasets.Dataset.from_list(...)` from already-parsed in-memory local records rather
  than any Hub dataset loader.

The V1 runtime never invokes `accelerate launch` and refuses implicit external
`ACCELERATE_CONFIG_FILE` or multi-process rank selection.

## Backend binding

`HfLocalSftBackend` requires an exact `TrainingRecipe` and, before runtime invocation,
requires all of the following:

```text
recipe.recipe_id == manifest.recipe_id
recipe.base.model_id == manifest.model_id
recipe.base.revision == manifest.revision
recipe.dataset.content_sha256 == manifest.training_dataset_sha256
recipe.base.backend == "transformers"
manifest.runner_class == "local"
recipe.seed in manifest.seeds
```

The adapter-method boundary is exact:

```text
LoRA  -> recipe.base.quantization == "none"
QLoRA -> recipe.base.quantization == "nf4"
```

No other V1 quantization spelling is accepted.

## Multiple-seed semantics

A `TrainingRecipe` contains one primary seed because that value participates in
`recipe_id`. A `TrainingRunPlan` independently contains an explicit unique seed tuple.

V1 does not discard either contract.

It requires the recipe primary seed to be present in the manifest seed tuple and executes
one fresh training runtime call for **every** manifest seed, in manifest order. Every seed
receives:

- the same exact recipe hyperparameters;
- the same exact locally attested model;
- the same exact corpus projection; and
- the seed itself as both TRL `seed` and `data_seed`.

Each seed writes to its own final adapter namespace:

```text
outputs/seed-<seed>/
```

The complete manifest seed tuple therefore remains part of `run_plan_sha256` and
`execution_manifest_sha256`; the recipe seed remains the canonical primary seed for the
recipe family.

This preserves existing launch-plan semantics without silently reducing a multi-seed run
to one execution. The final training-readiness audit must still decide whether the
scientific contract should evolve to make seed-grid identity explicit in a future recipe
version.

## Canonical corpus projection

The backend first reads the supplied corpus file locally with a no-follow regular-file
boundary and verifies the exact raw:

```text
canonical_corpus_sha256
canonical_corpus_byte_count
```

against `TrainingExecutionManifest`.

Only after the raw identity matches does it parse UTF-8 JSONL. The trainer projection uses
the already-canonical record fields:

```json
{
  "prompt": [{"role": "...", "content": "..."}],
  "completion": [{"role": "assistant", "content": "..."}]
}
```

No remote `load_dataset(...)` call is permitted. The real runtime creates an in-memory
`datasets.Dataset` with `Dataset.from_list(...)`.

The full canonical JSONL remains the audit source. The prompt-completion projection is a
runtime view only.

## Model re-verification

Immediately before training begins, the backend recomputes the canonical
`MESC-HF-SAFETENSORS-WEIGHT-IDENTITY-V1` identity and requires exact equality with
`manifest.weights_sha256`.

It repeats that verification before and after each seed run. A detected model-weight
identity change fails the backend and prevents canonical result publication.

The SafeTensors identity implementation itself uses a pinned no-follow directory
descriptor for identity traversal. Hugging Face subsequently loads through the supplied
local path; V1 therefore also relies on the separately qualified training runtime to
protect the local model directory from hostile replacement while training is active.
This package does not claim operating-system sandbox protection that it does not
implement.

## Fixed repository-bound execution profile

Callers cannot inject unbound trainer knobs.

The V1 backend fixes these values in repository code:

```text
per_device_train_batch_size = 1
gradient_accumulation_steps = 16
max_length = 2048
bf16 = true
fp16 = false
tf32 = false
gradient_checkpointing = true
packing = false
completion_only_loss = true
assistant_only_loss = false
full_determinism = true
eval_strategy = no
save_strategy = no
logging_strategy = no
report_to = none
push_to_hub = false
dataloader_num_workers = 0
```

The recipe continues to own:

```text
learning_rate
max_steps
lora_r
lora_alpha
lora_dropout
target_modules
adapter method
primary seed
```

The optimizer is repository-bound by adapter method:

```text
LoRA  -> adamw_torch_fused
QLoRA -> paged_adamw_8bit
```

These fixed values are indirectly bound by the run's exact repository SHA/tree and
dependency-lock identity. A future configurable training profile requires its own
content-addressed contract rather than constructor overrides.

## Tokenizer requirements

The real runtime loads the tokenizer from the same supplied local model directory with
local-only, no-token, no-remote-code options.

V1 requires:

- a non-empty local chat template;
- an EOS token; and
- a padding token.

If the tokenizer has no padding token, the runtime explicitly uses the validated EOS
token as padding.

The runtime never asks TRL to discover or download a processing class from a model name.

## QLoRA

For `AdapterMethod.QLORA`, V1 requires the recipe identity to use exact quantization
`nf4`.

The runtime loads the already-local SafeTensors base through Transformers with:

```text
4-bit loading
NF4 quantization
double quantization
BF16 compute
```

and then calls `prepare_model_for_kbit_training(...)`.

It does not quantize or publish a new canonical base-model identity. `weights_sha256`
continues to identify the already-local pre-quantization SafeTensors source payload; the
runtime quantization method is bound by recipe method, quantization identity, repository
code, and dependency lock.

## LoRA

For `AdapterMethod.LORA`, V1 requires:

```text
recipe.base.quantization == "none"
```

The local SafeTensors base is loaded in BF16 and receives the exact PEFT LoRA
configuration from the canonical recipe.

No full-model weight merge is performed. Final outputs are adapters.

## No implicit network, auth, telemetry, or distributed launch

During real runtime construction/execution, V1:

- imports the HF stack lazily;
- passes `token=False`;
- passes `local_files_only=True`;
- passes `trust_remote_code=False`;
- passes `use_safetensors=True`;
- sets `HF_HUB_OFFLINE=1`;
- sets `TRANSFORMERS_OFFLINE=1`;
- sets `HF_DATASETS_OFFLINE=1`;
- disables W&B through `WANDB_DISABLED=true`;
- uses `report_to="none"`;
- sets `push_to_hub=False`;
- refuses `WORLD_SIZE` values other than one;
- refuses externally selected nonlocal ranks; and
- refuses `ACCELERATE_CONFIG_FILE`.

No provider credential, gated-term acceptance, Hub push, model download, dataset
download, or remote code is authorized.

## Output layout

V1 requires exactly two planned sibling namespaces:

```text
<experiment-parent>/outputs
<experiment-parent>/results
```

The parent itself must be repository-relative.

For each seed the runtime writes the final PEFT adapter/tokenizer files beneath:

```text
outputs/seed-<seed>/
```

The backend writes:

```text
results/training-summary.json
```

The summary binds at least:

- backend id/version;
- execution-manifest SHA-256;
- experiment id;
- role;
- model id/revision/weights identity;
- training-dataset identity;
- recipe id;
- fixed execution profile;
- every seed;
- normalized runtime metrics; and
- observed runtime package versions.

## Atomic publication

The final experiment result root must not exist before execution.

The backend:

1. validates every existing publication-path ancestor below `repository_root` as a real
   non-symlink directory, creates missing ancestors one at a time, requires the resolved
   parent to remain inside the repository and on the same filesystem, and pins repository
   and publication directories with no-follow descriptors;
2. creates a private staging directory directly beneath the validated repository root;
3. trains every seed only into staging;
4. writes the summary only into staging;
5. rejects symlink, empty, non-regular, namespace-escaping, or multi-link outputs;
6. hashes every final file through a no-follow file descriptor, requiring stable
   descriptor identity and a single hard link before and after hashing;
7. revalidates publication ancestors and pinned directory identities and rechecks that the
   final result root still does not exist; and
8. atomically renames the complete staged experiment root with pinned source and
   destination directory descriptors.

Any ordinary exception before publication deletes staging and returns a canonical
`FAILED` `TrainingBackendResult` with no result artifacts. `KeyboardInterrupt`,
`SystemExit`, and other `BaseException` subclasses also delete staging, but are re-raised
instead of being converted into canonical failure results.

The backend never overwrites a prior experiment result root.

## Timestamp and failure behavior

The backend records actual UTC whole-second start/finish timestamps.

Expected runtime/backend failures become:

```text
disposition = FAILED
artifacts = ()
failure_reason = non-empty
```

`KeyboardInterrupt`, `SystemExit`, and other `BaseException` subclasses are not converted
into false canonical results.

The core executor remains responsible for validating the returned
`TrainingBackendResult` and result namespaces.

## Default CI

Default CI uses a fake `HfLocalSftRuntime`.

It validates:

- all manifest/recipe bindings;
- exact local model identity;
- exact corpus byte identity;
- local prompt-completion projection;
- multiple-seed execution;
- runtime failure and interrupt cleanup;
- no result overwrite;
- symlinked publication-ancestor rejection;
- namespace confinement;
- hardlink rejection and descriptor-based no-follow artifact hashing;
- lazy package import behavior; and
- exact local-only/no-token/no-remote-code/no-Hub arguments supplied by the real runtime
  adapter using fake modules.

Default CI does not import or execute real:

```text
torch
transformers
trl
peft
accelerate
datasets
bitsandbytes
```

and does not access a GPU, model, provider, credential, or network.

## Acceptance

This backend gate is complete only when exact-head CI, CodeQL, and review prove at least:

- no default-CI HF imports or training;
- deterministic fail-closed manifest/recipe binding;
- model identity re-verification;
- corpus raw-byte verification before parsing;
- prompt-completion projection;
- all planned seeds are executed;
- QLoRA is exact NF4 and LoRA is exact unquantized base identity;
- local-only/no-auth/no-remote-code model and tokenizer calls;
- no implicit reporting, Hub push, or distributed launch;
- no existing result overwrite;
- publication ancestors cannot redirect writes through symlinks or another filesystem;
- runtime artifact hashing is no-follow, single-link, and descriptor-stable;
- failed or interrupted execution leaves no staged canonical artifacts;
- successful execution atomically publishes both planned namespaces; and
- returned artifact hashes and byte counts describe the published files.

## Remaining repository gates

Canonicalization of this backend will not itself make training executable from a clean
checkout.

Before `TRAINING_CODE_READY`, the repository still needs at least:

1. a **training dependency-lock/optional-extra gate** that pins the exact production HF
   SFT stack into the repository lock;
2. the planned **training CLI/orchestrator** that observes the actual local execution
   environment, consumes canonical readiness/launch/binding/attestation inputs, constructs
   this backend explicitly, and invokes `execute_training(...)`; and
3. a final repository training-readiness audit.

Actual training additionally requires real authorized model assets, real qualified corpus
bytes, qualified runtime/GPU evidence, and the explicit training-authorization receipt.
This package grants none of those authorities.
