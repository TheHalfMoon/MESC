# MESC Training Readiness Receipt Binding V1

Status: **IMPLEMENTATION / FAIL-CLOSED CONSTRUCTION HELPER / NO AUTHORITY MINTED**

Canonical base:

```text
BASE_MAIN_SHA = 2b9aa412053c71a096115e87fe5275ba8337399e
BASE_MAIN_TREE = 872592833061defec3086433d8c18396a72105f3
```

## Purpose

Bind already-produced runtime-qualification and training-authorization **receipt objects**
into a scientific `TrainingReadinessManifest` without accepting opaque forged digests as
proof of PASS/AUTHORIZED status.

This closes the repository-side gap named by the training-authorization receipt package:
receipt producers exist, but readiness construction previously accepted any matching
SHA-256 string.

## Scope

```text
specs/mesc-training-readiness-receipt-binding-v1/README.md
src/medscale/mesc/_training_readiness_receipt_binding_v1.py
tests/test_mesc_training_readiness_receipt_binding_v1.py
```

## Binding rules

### Runtime qualification

`bind_runtime_qualification_to_readiness(manifest, receipt)` may set
`runtime_qualification_sha256` only when:

- scientific assessment of the input manifest is not `BLOCKED`;
- `receipt.disposition == PASS`;
- `receipt.platform_qualified is True`;
- the manifest does not already bind a different runtime receipt digest.

`OBSERVED` and `BLOCKED` runtime receipts are refused. Package installation alone is never
treated as platform-qualified.

### Training authorization

`bind_training_authorization_to_readiness(manifest, receipt, *, runtime_qualification)`
may set `training_authorization_receipt_sha256` only when:

- the manifest already binds a runtime qualification digest;
- the supplied `runtime_qualification` receipt is exact-type `PASS` with
  `platform_qualified=true` and its digest equals the bound runtime digest;
- `receipt.disposition == AUTHORIZED` and `receipt.real_training_authorized is True`;
- `receipt.subject_readiness_manifest_sha256` equals the **pre-authorization**
  readiness identity (`training_authorization_receipt_sha256=None`);
- `receipt.runtime_qualification_sha256 == manifest.runtime_qualification_sha256`;
- the manifest does not already bind a different authorization receipt digest.

Runtime binding refuses manifests that already carry an authorization digest.
Both binders require exact dataclass types (`type(x) is ...`), not subclasses.
`authorize=false` / `BLOCKED` receipts are refused. This helper never calls the
authorization builder with `authorize=True`.

### Launch construction

`construct_ready_to_launch_readiness(...)` binds runtime then authorization in order and
requires the final assessment disposition to be exactly `READY_TO_LAUNCH`.

## Authority boundary

This package does not:

- invent runtime or authorization receipts;
- download models or accept gated terms;
- execute training;
- publish GitHub Release assets;
- clear MedScale Spec 012; or
- claim that fixture digests prove real model/corpus/GPU evidence exists.

## Next gates (external / evidence)

- authorized local model assets with exact `weights_sha256`;
- qualified corpus bytes bound through corpus-binding/attestation;
- runtime smoke evidence yielding `platform_qualified=true` on the intended host;
- explicit founder/operator `authorize=true` authorization artifact;
- authorized training, evaluation, rights/SBOM/provenance; and
- a GitHub Release with non-empty immutable assets that survive independent re-fetch and
  hash verification (assessed by `mesc-release-artifact-qualification-v1` once observed).
