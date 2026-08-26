# MESC Training Runtime Qualification V1

Status: **IMPLEMENTATION / OBSERVATION RECEIPT / NO TRAINING AUTHORIZATION**

Canonical base:

```text
BASE_MAIN_SHA = 35f7069af39e550270e749e46f2d8ef8346bc963
BASE_MAIN_TREE = bc12c85116fd7c985b11705d285663f9f709acf4
PR_205 = CLOSED_CANONICAL
```

## Purpose

After `TRAINING_CODE_READY`, readiness/launch still consume an opaque
`runtime_qualification_sha256`. This package is the first repository producer that can
emit that digest from observed local runtime facts without inventing GPU identity or
authorizing training.

## Scope

```text
specs/mesc-training-runtime-qualification-v1/README.md
src/medscale/mesc/_training_runtime_qualification_v1.py
tests/test_mesc_training_runtime_qualification_v1.py
```

## Receipt fields

A `TrainingRuntimeQualificationReceipt` binds:

- `runner_class`
- `python_version`
- `os_name`
- `gpu_model` (must be supplied; never invented)
- `dependency_lock_sha256`
- `repository_sha` / `repository_tree`
- `probe_id` / `probe_version`
- `network_accessed` / `remote_code_allowed` (must be false for `PASS`)
- `smoke_disposition` (`SKIPPED` | `PASS` | `FAIL`)
- optional `smoke_receipt_sha256`
- `platform_qualified` (true only for disposition `PASS`)

Dispositions:

- `OBSERVED` — complete local facts with `smoke_disposition=SKIPPED`; **not** platform qualified
- `PASS` — smoke evidence present and passing; `platform_qualified=true`
- `BLOCKED` — policy/smoke failure

`receipt_sha256` is the opaque digest for readiness/launch. Callers that require
platform qualification must check `platform_qualified` / disposition `PASS`; an
`OBSERVED` receipt alone is not launch authority.

## Authority boundary

- Package installation is **not** `PLATFORM_QUALIFIED`.
- This package does not authorize training, download models, accept gated terms, or
  clear MedScale Spec 012.
- Default CI uses injected facts only.

## Next gate

A sibling fail-closed **training-authorization receipt** producer that validates an
already-supplied founder/operator authorization artifact into
`training_authorization_receipt_sha256` without minting authority from empty defaults.
