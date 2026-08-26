# MESC Training Authorization Receipt V1

Status: **IMPLEMENTATION / FAIL-CLOSED VALIDATOR / NO AUTHORITY MINTED**

Canonical base:

```text
BASE_MAIN_SHA = 1cb02d0b5f47b0fc070d597dae54d6f7de704e82
BASE_MAIN_TREE = 9f503da71ec75398707f8f91a272529376051783
```

## Purpose

Emit `training_authorization_receipt_sha256` only by validating an already-supplied
founder/operator authorization artifact. Empty defaults never become AUTHORIZED.

Authorization binds a **stable pre-authorization subject identity**
(`authorization_subject_sha256`) so the receipt is not circular with the final
readiness manifest that will later include this receipt digest. Post-launch local-asset
attestation is deliberately **not** an authorization input.

## Scope

```text
specs/mesc-training-authorization-receipt-v1/README.md
src/medscale/mesc/_training_authorization_receipt_v1.py
tests/test_mesc_training_authorization_receipt_v1.py
```

## Required bindings

- `authorization_scope = TRAINING_EXECUTION`
- `authorizer_id`
- `authorization_subject_sha256` (from `TrainingReadinessManifest.authorization_subject_sha256`)
- `runtime_qualification_sha256`
- `corpus_binding_sha256`
- `authorization_statement`
- explicit `authorize=true` for `AUTHORIZED`

`AUTHORIZED` implies `real_training_authorized=true`.  
`authorize=false` always yields `BLOCKED` with `real_training_authorized=false`.

## Authority boundary

- Does not invent founder authorization.
- Does not execute training.
- Does not download models or accept gated terms.
- Does not clear MedScale Spec 012.
- Does not bind post-launch `local_asset_attestation_sha256`.
- Fixture/CI paths must call `authorize=false` unless a real authorization artifact is supplied out-of-band.

## Next gate

Receipt producers bind through `mesc-training-readiness-receipt-binding-v1`. Remaining
work is external/evidence: authorized local model assets, qualified corpus bytes,
platform-qualified runtime smoke, explicit `authorize=true`, training/evaluation,
rights/SBOM/provenance, and a non-empty qualifying GitHub Release.
