# MESC Release Artifact Qualification V1

Status: **IMPLEMENTATION / FAIL-CLOSED RELEASE OBSERVATION / NO SPEC 012 CLEARANCE BY DEFAULT**

Canonical base:

```text
BASE_MAIN_SHA = 4b193c01f5f94447afd359b0420640647b449a69
BASE_MAIN_TREE = 3f48f3a9af89d8e82f04c0501019b09084ff860a
PR_213 = CLOSED_CANONICAL
PR_214 = CLOSED_CANONICAL
PR_215 = CLOSED_CANONICAL
```

## Purpose

Qualify an already-observed GitHub Release candidate for MedScale Spec 012
`ARTIFACT_IMPORT` admission readiness. Empty assets, missing evidence bindings,
mismatched release identity, missing semantic evidence, or unverified digests remain
`BLOCKED` / `NOT_READY`.

This package never invents release assets, never uploads artifacts, and never clears
MedScale Spec 012 from incomplete evidence.

## Scope

```text
specs/mesc-release-artifact-qualification-v1/README.md
src/medscale/mesc/_release_artifact_qualification_v1.py
tests/test_mesc_release_artifact_qualification_v1.py
```

Semantic evidence is validated by the separate canonical package:

```text
specs/mesc-release-semantic-evidence-v1/README.md
src/medscale/mesc/_release_semantic_evidence_v1.py
tests/test_mesc_release_semantic_evidence_v1.py
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
    (assets are ordered by exact `name` before hashing so tuple order cannot forge
    a different manifest identity)
  - `provenance_sha256`, `rights_sha256`, `sbom_sha256`,
    `evaluation_report_sha256`, `training_execution_receipt_sha256`
  - `independent_refetch_verified=true`
  - `asset_hashes_verified=true`
- `semantic_evidence`: exact `ReleaseSemanticEvidenceBundle` proving that:
  - the training execution receipt bytes represent a successful canonical executor receipt;
  - provenance/rights/SBOM/evaluation envelopes hash the exact supplied evidence bytes;
  - every evidence item is bound to the same repository/tag/release id/asset manifest;
  - provenance and evaluation bind the exact successful training receipt;
  - rights and evaluation have `PASS` semantics; and
  - SBOM bytes identify CycloneDX or SPDX JSON.

Opaque digests alone are never sufficient for `RELEASE_READY`.

## Dispositions

```text
BLOCKED
RELEASE_READY
```

`RELEASE_READY` requires every required binding, at least one non-empty asset, an
exact-matching semantic evidence bundle, both independent re-fetch and hash verification
flags true, and exact equality between every evidence-binding digest and its validated
semantic document identity.

The report always records:

```text
medscale_spec_012_admission_readiness =
  READY only when disposition == RELEASE_READY
  otherwise NOT_READY
```

## Authority boundary

- Does not create GitHub Releases or upload assets.
- Does not download or mutate remote bytes (caller supplies observed facts/evidence bytes).
- Does not execute training or evaluation.
- Does not authorize training.
- Does not mutate MedScale.
- Live empty `v0.1.0` observations remain `BLOCKED` / `NOT_READY`.

## Next gates (external / evidence)

Produce authorized training and evaluation evidence, provenance, rights evidence, and a
real SBOM; create a GitHub Release with non-empty immutable assets; independently re-fetch
those assets; then construct the semantic evidence bundle and observed release binding from
those real bytes. Repository code alone cannot manufacture those facts.
