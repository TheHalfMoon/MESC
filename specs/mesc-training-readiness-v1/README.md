# MESC Training Readiness V1

Status: **IMPLEMENTATION / PRE-EXECUTION / NO TRAINING PERFORMED**

Canonical base:

```text
BASE_MAIN_SHA = b37358593400554c8c8a415d4e2b3d098ce53f6b
PR_179 = CLOSED_CANONICAL
TRAINING_EXECUTION = NOT_PERFORMED
MODEL_WEIGHT_ACCESS = NOT_PERFORMED
```

## Purpose

MESC already has content-addressed LoRA/QLoRA recipe objects, but a recipe is not a
training authorization or a proof that the scientific prerequisites for training
have been satisfied. The current frontier strategy requires Pilot-01 closeout,
backbone-tournament finalist selection, data provenance/decontamination, held-out
evaluation isolation, and explicit authorization before the selected finalists are
trained.

This package adds one deterministic, fail-closed readiness gate that binds those
requirements to exact identities.

## Scope

This package changes exactly three paths:

```text
specs/mesc-training-readiness-v1/README.md
src/medscale/mesc/_training_readiness_v1.py
tests/test_mesc_training_readiness_v1.py
```

It does not add a trainer, dependency, workflow, provider integration, model download,
remote-code path, dataset acquisition path, inference path, or training execution.

## Required identities

A `TrainingReadinessManifest` binds:

- exact Compact finalist model id, immutable 40-lowercase-hex revision, weights
  SHA-256, and license identity;
- exact Reasoner finalist model id, immutable 40-lowercase-hex revision, weights
  SHA-256, and license identity;
- exact content-addressed `TrainingRecipe` for each finalist;
- Pilot-01 closeout artifact SHA-256;
- canonical backbone-tournament report SHA-256;
- exact training dataset SHA-256;
- provenance-ledger SHA-256;
- decontamination-report SHA-256;
- held-out evaluation contract SHA-256;
- R2-only training-data assertion;
- held-out-evaluation exclusion assertion;
- PHI absence assertion;
- optional runtime-qualification receipt SHA-256; and
- optional explicit training-authorization receipt SHA-256.

The readiness manifest itself has a deterministic SHA-256 identity derived from all
of the fields above plus the two recipe identities.

## Fail-closed dispositions

The gate has exactly three outcomes:

```text
BLOCKED
READY_FOR_AUTHORIZATION
READY_TO_LAUNCH
```

`BLOCKED` is returned if any scientific or governance prerequisite fails, including:

- Pilot-01 closeout is not exactly `PASS`;
- tournament disposition is not exactly `PASS`;
- decontamination disposition is not exactly `PASS`;
- training data is not proven R2-compatible;
- held-out evaluation data is not proven excluded from training;
- PHI is present;
- a recipe does not bind the selected finalist model id and exact revision; or
- a recipe dataset hash does not bind the exact proposed training dataset.

`READY_FOR_AUTHORIZATION` means the scientific identities are internally consistent,
but one or both live launch receipts are absent. It is **not** training authority.

`READY_TO_LAUNCH` is possible only when all scientific/governance bindings pass and
both a runtime-qualification receipt and an explicit training-authorization receipt
are present. The status still does not itself execute training.

## Why exact model revisions are mandatory here

The generic `ModelRef` type intentionally permits an optional revision because it is
used across broader MedScale workflows. Training readiness is stricter: finalist
weights must be tied to an immutable 40-character lowercase revision and a separate
weights SHA-256. A floating model reference cannot pass this gate.

## Strategy alignment

The gate implements the boundary between the current evaluation-first P0/P1 work and
the first P2 training action. It intentionally does not collapse these phases:

1. preserve/close Pilot-01;
2. execute and accept the backbone tournament under its own authority;
3. select Compact + Reasoner finalists;
4. freeze provenance/decontamination/evaluation isolation;
5. freeze one content-addressed recipe per finalist;
6. qualify the intended training runtime;
7. obtain explicit training authorization; then
8. permit a later executor to launch the frozen training plan.

## Non-claims

This package does not prove that any referenced real-world artifact currently exists.
It validates the manifest and cross-bindings supplied by the caller. The components
that produce and accept the real tournament report, data/provenance/decontamination
artifacts, runtime qualification, and operator authorization remain independently
responsible for those proofs.

This package performs no:

- provider access;
- credential access;
- model-weight access or retrieval;
- gated-access request or acceptance;
- real Phi source read/import/execution;
- prompt serialization;
- inference or generation;
- Backbone Tournament execution;
- training or fine-tuning.

## Next gate

After this package is canonical, the next repository-only step is a deterministic
**training launch-plan builder** that accepts only a `READY_TO_LAUNCH` report and
emits an auditable, content-addressed execution plan without executing it. The actual
trainer/provider invocation remains a separately authorized action.
