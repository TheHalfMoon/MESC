# MESC Training Launch Plan V1

Status: **IMPLEMENTATION / PRE-EXECUTION / NO TRAINING PERFORMED**

Canonical base:

```text
BASE_MAIN_SHA = 598af613b30cee8600b166131f8047ba2289b5f8
PR_180 = CLOSED_CANONICAL
TRAINING_READINESS_GATE = CANONICAL
TRAINING_EXECUTION = NOT_PERFORMED
```

## Purpose

`MESC-TRAINING-READINESS-V1` proves whether the supplied scientific, data,
license, runtime, and authorization identities are internally sufficient to permit
a later launch. It intentionally does not describe the exact run layout.

This package adds the next fail-closed bridge: an immutable, content-addressed
training launch plan for the selected Compact and Reasoner finalists. The plan is
constructed only from a readiness report that independently recomputes to
`READY_TO_LAUNCH` for the exact supplied readiness manifest.

The package plans training. It does not execute training.

## Scope

Exactly three paths are introduced:

```text
specs/mesc-training-launch-plan-v1/README.md
src/medscale/mesc/_training_launch_plan_v1.py
tests/test_mesc_training_launch_plan_v1.py
```

No dependency, workflow, CLI, provider, credential, model, dataset, inference, or
trainer integration is added.

## Required run identity

Each `TrainingRunPlan` freezes:

- exact role: `compact` or `reasoner`;
- stable experiment id;
- non-empty research-question references;
- exact content-addressed `TrainingRecipe.recipe_id`;
- selected model id;
- immutable 40-lowercase-hex model revision;
- model weights SHA-256;
- exact training dataset SHA-256;
- explicit unique non-negative seeds;
- intended runner class;
- Python version;
- operating-system identity;
- GPU model identity;
- dependency-lock SHA-256;
- clean repository commit SHA;
- exact repository tree identity;
- repository-relative result paths; and
- a single-line reproduction command.

These fields cover the pre-run portion of the binding experiment-manifest policy.
Runtime-observed fields such as actual peak VRAM and the actual start timestamp are
not fabricated before execution; they remain outputs of the later executor.

## Cross-run invariants

The complete `TrainingLaunchPlan` contains exactly one Compact run and one Reasoner
run. Both must bind:

- the same repository commit;
- the same repository tree;
- the same dependency lock;
- the same readiness manifest and launch receipts; and
- disjoint result paths.

Experiment ids must also be distinct.

## Readiness re-verification

`build_training_launch_plan(...)` never trusts a supplied readiness label by itself.
It:

1. recomputes `assess_training_readiness(manifest)`;
2. requires byte/field-equivalent readiness evidence;
3. requires `READY_TO_LAUNCH`;
4. requires zero blockers and zero launch requirements;
5. requires the readiness report to bind the exact manifest SHA-256;
6. requires both runtime-qualification and explicit training-authorization receipts;
7. binds the Compact run to the exact selected Compact candidate and recipe; and
8. binds the Reasoner run to the exact selected Reasoner candidate and recipe.

A forged, stale, merely `READY_FOR_AUTHORIZATION`, or otherwise mismatched report
fails closed.

## Content addressing

Every run has a deterministic `run_plan_sha256`. The complete launch plan has a
deterministic `plan_sha256`. Any change to model identity, recipe, dataset, seeds,
environment target, dependency lock, code identity, output layout, reproduction
command, runtime qualification, or training authorization changes the resulting
plan identity.

No timestamps or randomly generated identifiers participate in the pre-launch plan.

## Relationship to the experiment framework

The existing `medscale.modelkit.manifests.ExperimentManifest` remains the canonical
post-start experiment manifest. This package does not duplicate or supersede it.
The later executor must materialize the run-time manifest using the launch-plan
bindings plus runtime-observed fields such as `started_at` and peak VRAM, then retain
saved outputs so scoring remains replayable without re-inference.

## Security and governance

This package performs no:

- network access;
- provider access;
- credential access;
- gated-license acceptance;
- model-weight access or retrieval;
- dataset reads;
- remote-code import or execution;
- prompt serialization;
- inference or generation;
- Backbone Tournament execution;
- trainer import;
- GPU execution;
- training or fine-tuning.

A valid launch plan is not evidence that the referenced real artifacts exist. That
truth remains owned by the readiness artifacts and later execution environment.

## Next gate

After this package is canonical, the repository-side path to training requires two
remaining implementation layers:

1. a **T5 training-dataset qualification contract** that consumes the existing
   deterministic dataset-builder/freeze primitives and emits the provenance,
   decontamination, held-out isolation, and license evidence required by the readiness
   manifest; and
2. a **training executor boundary** that consumes only a canonical launch plan,
   materializes the runtime experiment manifest, runs a separately approved trainer,
   and writes auditable outputs without silently downloading or accepting assets.

Neither layer may manufacture real tournament finalists, model weights, dataset
artifacts, runtime qualification, or operator authorization.