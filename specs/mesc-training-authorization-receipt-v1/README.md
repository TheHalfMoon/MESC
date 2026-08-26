# MESC Training Authorization Receipt V1

Status: **IMPLEMENTATION / FAIL-CLOSED VALIDATOR / NO AUTHORITY MINTED**

Canonical base:

```text
BASE_MAIN_SHA = 35f7069af39e550270e749e46f2d8ef8346bc963
BASE_MAIN_TREE = bc12c85116fd7c985b11705d285663f9f709acf4
```

## Purpose

Emit `training_authorization_receipt_sha256` only by validating an already-supplied
founder/operator authorization artifact. Empty defaults never become AUTHORIZED.

## Scope

```text
specs/mesc-training-authorization-receipt-v1/README.md
src/medscale/mesc/_training_authorization_receipt_v1.py
tests/test_mesc_training_authorization_receipt_v1.py
```

## Required bindings

- `authorization_scope = TRAINING_EXECUTION`
- `authorizer_id`
- `subject_readiness_manifest_sha256`
- `runtime_qualification_sha256`
- `corpus_binding_sha256`
- `local_asset_attestation_sha256`
- `authorization_statement`
- explicit `authorize=true` for `AUTHORIZED`

`AUTHORIZED` implies `real_training_authorized=true`.  
`authorize=false` always yields `BLOCKED` with `real_training_authorized=false`.

## Authority boundary

- Does not invent founder authorization.
- Does not execute training.
- Does not download models or accept gated terms.
- Does not clear MedScale Spec 012.
- Fixture/CI paths must call `authorize=false` unless a real authorization artifact is supplied out-of-band.

## Next gate

Bind these receipt producers into readiness construction helpers and continue corpus/model
asset evidence acquisition. Real training remains externally gated.
