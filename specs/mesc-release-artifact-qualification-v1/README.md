# MESC Release Artifact Qualification V1

Status: **IMPLEMENTATION / FAIL-CLOSED RELEASE OBSERVATION / NO SPEC 012 CLEARANCE BY DEFAULT**

Canonical base:

```text
BASE_MAIN_SHA = cd40d3867a46c2f7e4f249c6204474e531ba733f
BASE_MAIN_TREE = bde49cec683e97cbb32c7309ef8e44d20905219e
PR_214 = CLOSED_CANONICAL
```

## Purpose

Qualify an already-observed GitHub Release candidate for MedScale Spec 012
`ARTIFACT_IMPORT` admission readiness. Empty assets, missing evidence bindings,
mismatched release identity, or unverified digests remain `BLOCKED` / `NOT_READY`.

This package never invents release assets, never uploads artifacts, and never
clears MedScale Spec 012 from incomplete evidence.

## Scope

```text
specs/mesc-release-artifact-qualification-v1/README.md
src/medscale/mesc/_release_artifact_qualification_v1.py
tests/test_mesc_release_artifact_qualification_v1.py
```

## Required observed facts

- `repository` (exact `owner/name`)
- `tag_name`
- `release_id` (positive int)
- non-empty `assets` where each asset has:
  - `name`
  - `size_bytes` (positive int)
  - `content_sha256` (64 lowercase hex)
  - `browser_download_url` (non-empty; observation only — this package does not fetch)
- `evidence_binding`: exact `ReleaseEvidenceBinding` that binds:
  - the same `repository` / `tag_name` / `release_id`
  - `asset_manifest_sha256` equal to the content hash of the observed asset set
  - `provenance_sha256`, `rights_sha256`, `sbom_sha256`,
    `evaluation_report_sha256`, `training_execution_receipt_sha256`
  - `independent_refetch_verified=true`
  - `asset_hashes_verified=true`

Opaque digests that do not match the observed release identity/asset manifest are
rejected even when syntactically valid.

## Dispositions

```text
BLOCKED
RELEASE_READY
```

`RELEASE_READY` requires every required binding, at least one non-empty asset, an
exact-matching evidence binding, and both independent re-fetch and hash verification
flags true.

The report always records:

```text
medscale_spec_012_admission_readiness =
  READY only when disposition == RELEASE_READY
  otherwise NOT_READY
```

## Authority boundary

- Does not create GitHub Releases or upload assets.
- Does not download or mutate remote bytes (caller supplies observed facts).
- Does not authorize training.
- Does not mutate MedScale.
- Live empty `v0.1.0` observations must remain `BLOCKED` / `NOT_READY`.

## Next gates (external / evidence)

Produce and independently re-fetch a GitHub Release whose assets are non-empty and
hash-verified, with a release-bound evidence record covering provenance/rights/SBOM/
evaluation/training-execution identities derived from authorized training — not from
this package alone.
