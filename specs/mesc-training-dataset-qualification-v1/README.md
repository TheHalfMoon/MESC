# MESC Training Dataset Qualification V1

Status: **IMPLEMENTATION / T5 PRE-EXECUTION / NO TRAINING DATA READS**

Canonical base:

```text
BASE_MAIN_SHA = 696131ae6f579bb4c8971c41453033034af56f49
PR_181 = CLOSED_CANONICAL
TRAINING_READINESS_GATE = CANONICAL
TRAINING_LAUNCH_PLAN = CANONICAL
TRAINING_EXECUTION = NOT_PERFORMED
```

## Purpose

MESC already has deterministic dataset release, audit, quality, and split-freeze
contracts. T5 must not create a second dataset pipeline. This package composes those
existing contracts into one fail-closed qualification artifact for the exact records
that would be consumed by a future training run.

The qualification artifact is the bridge between dataset engineering and
`MESC-TRAINING-READINESS-V1`. A dataset is not eligible for readiness merely because
a release exists or a quality report says `green`; every governance and contamination
artifact must bind the exact same training record set.

This package qualifies supplied artifacts. It does not read the underlying dataset and
does not execute training.

## Scope

Exactly three paths are introduced:

```text
specs/mesc-training-dataset-qualification-v1/README.md
src/medscale/mesc/_training_dataset_qualification_v1.py
tests/test_mesc_training_dataset_qualification_v1.py
```

No existing dataset-builder public surface is modified. No dependency, workflow, CLI,
provider, credential, model, trainer, or GPU integration is added.

## Canonical inputs

`qualify_training_dataset(...)` consumes only existing deterministic contract objects:

- `DatasetReleaseManifest`;
- `AuditReport`;
- `QualityReport`;
- `SplitAssignmentFreeze`; and
- `TrainingDatasetEvidenceBundle` containing content-addressed external evidence
  identities supplied by the caller.

The function does not open files or inspect hidden source data. It verifies whether the
supplied artifacts form one internally consistent qualification chain.

## Exact training-record identity

T5 derives the identity of the training membership from the frozen `train` assignment:

```text
training_record_ids_sha256 = SHA256(canonical_json({
  "kind": "mesc.training_dataset.record_ids.v1",
  "record_ids": sorted(split_freeze.train)
}))
```

The future trainer consumes a training-dataset identity derived from:

- released dataset id;
- released dataset version;
- released dataset fingerprint;
- split-freeze fingerprint;
- fixed split name `train`; and
- exact training-record membership identity.

Consequently, changing even one training record changes the training dataset identity.
Validation/test membership remains bound through the split-freeze fingerprint, so the
full partition state also participates in the training identity.

## Evidence coverage requirement

The following evidence artifacts must all carry the exact same
`covered_record_ids_sha256` equal to the derived training-record identity:

- provenance ledger;
- decontamination report;
- license review;
- PHI scan;
- R2 policy review; and
- held-out exclusion report.

Each evidence disposition must be exactly `PASS`. A report covering a superset,
subset, previous split, or merely similarly named dataset does not qualify the current
training set.

## Existing quality-report linkage

T5 requires the existing `QualityReport` to expose machine-readable bindings to the
same evidence rather than accepting an unstructured `green=True` assertion.

Required keys are:

```text
stage_quality_summaries.provenance:
  covered_record_ids_sha256
  disposition = PASS
  ledger_sha256

contamination_summary:
  covered_record_ids_sha256
  disposition = PASS
  report_sha256

license_audit:
  covered_record_ids_sha256
  disposition = PASS
  review_sha256

stage_quality_summaries.phi_scan:
  covered_record_ids_sha256
  disposition = PASS
  phi_present = false
  report_sha256

stage_quality_summaries.r2_policy:
  covered_record_ids_sha256
  disposition = PASS
  r2_training_data_only = true
  report_sha256

benchmark_linkage_status:
  covered_record_ids_sha256
  disposition = PASS
  heldout_eval_record_ids_sha256
  report_sha256
  training_overlap_count = 0
```

These are consumed as data inside the already-existing mapping fields; no
`QualityReport` schema expansion is required.

## Release and audit requirements

Qualification fails closed unless:

- release, audit, and quality dataset ids match exactly;
- release, audit, and quality dataset versions match exactly;
- the split freeze binds the exact released dataset fingerprint;
- the training split is non-empty;
- the audit record count equals the total split-freeze assignment count;
- the audit is green and contains no failures;
- audit validation statuses are non-empty and all exactly `PASS`;
- checksum-verification statuses are non-empty and all exactly `PASS`;
- the quality report is green;
- release validation and quality summaries explicitly record `green=true`; and
- release dataset/manifest/bundle identities are valid SHA-256 values where required.

## Hard scientific and safety gates

A training dataset is `PASS` only when all of the following are true:

```text
PHI_PRESENT = false
R2_TRAINING_DATA_ONLY = true
HELDOUT_TRAINING_OVERLAP_COUNT = 0
HELDOUT_EVAL_RECORD_SET != TRAINING_RECORD_SET
```

No field may be inferred from a missing report. Missing, mismatched, malformed, or
non-PASS evidence becomes a blocker.

## Qualification output

`TrainingDatasetQualificationReport` records deterministic identities for:

- release artifact;
- audit report;
- quality report;
- split freeze;
- training record membership;
- exact training dataset;
- provenance ledger;
- decontamination report;
- license review;
- PHI scan;
- R2 review;
- held-out exclusion report; and
- held-out evaluation membership.

The complete report has a deterministic `qualification_sha256` and disposition
`BLOCKED` or `PASS`.

A `PASS` report has zero blockers and alone exposes
`can_bind_to_readiness=True`.

## Readiness bridge

`build_readiness_manifest_from_qualified_dataset(...)` accepts only a `PASS` T5
qualification and builds the existing canonical `TrainingReadinessManifest` without
changing its V1 schema.

It copies the exact:

- `training_dataset_sha256`;
- `provenance_ledger_sha256`;
- `decontamination_report_sha256`;
- `license_review_sha256`;
- R2 disposition fact;
- held-out exclusion fact; and
- PHI fact.

Tournament, Pilot-01 closeout, evaluation-contract, runtime-qualification, and explicit
training-authorization identities remain separate inputs and cannot be manufactured by
T5.

`TrainingReadinessManifest` V1 does not contain a dedicated T5 qualification hash.
Therefore the `TrainingDatasetQualificationReport` and its `qualification_sha256` must
be retained alongside the readiness artifact as upstream audit evidence. This package
does not overload an unrelated readiness field to hide that limitation.

## Content-addressing boundary

No current time, local path, hostname, random id, provider metadata, or credential is
included in T5-derived identities. The training identity depends only on frozen
scientific/data artifacts.

## Non-claims

This package performs no:

- dataset file reads;
- dataset generation or mutation;
- network access;
- model/provider access;
- credential access;
- license or gated-term acceptance;
- model-weight retrieval;
- prompt serialization;
- inference or generation;
- Backbone Tournament execution;
- trainer import;
- GPU execution;
- training or fine-tuning.

A synthetic or fixture PASS demonstrates contract behavior only. It is not evidence
that the real MESC training dataset has been produced or qualified.

## Next gate

After T5 is canonical, the remaining repository execution layer is a **fail-closed
training executor boundary**. It must consume only a canonical launch plan, verify local
model/data assets against their frozen identities without silent downloads, materialize
the canonical runtime `ExperimentManifest`, execute only a separately authorized
trainer backend, and retain outputs for replayable scoring.

Actual training still requires real tournament finalists, real T5 evidence, runtime
qualification, model-weight availability under valid terms, and an explicit training
authorization receipt.
