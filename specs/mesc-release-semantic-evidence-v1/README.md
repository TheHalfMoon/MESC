# MESC Release Semantic Evidence V1

Status: **IMPLEMENTATION / FAIL-CLOSED EVIDENCE VALIDATION / NO RELEASE CREATION**

Canonical base:

```text
BASE_MAIN_SHA = 4b193c01f5f94447afd359b0420640647b449a69
BASE_MAIN_TREE = 3f48f3a9af89d8e82f04c0501019b09084ff860a
PR_213 = CLOSED_CANONICAL
PR_214 = CLOSED_CANONICAL
PR_215 = CLOSED_CANONICAL
TRAINING_CODE_READY = PROVEN_ON_EXACT_MAIN
```

## Purpose

Close the remaining presence-only authority gap in
`MESC-RELEASE-ARTIFACT-QUALIFICATION-V1`.

A syntactically valid SHA-256 value is an identity, not proof that provenance, rights,
SBOM, evaluation, or training execution evidence exists or has the required semantics.
This package validates exact evidence bytes before those identities may participate in a
`RELEASE_READY` decision.

## Evidence order

```text
successful training execution receipt bytes
  -> provenance artifact + release-bound envelope
  -> rights artifact + release-bound envelope
  -> SBOM artifact + release-bound envelope
  -> evaluation artifact + release-bound envelope
  -> ReleaseSemanticEvidenceBundle
  -> release artifact qualification
```

The bundle is acyclic: release-bound evidence may reference the already-completed training
receipt; the training receipt never references a future release.

## Training receipt requirements

The supplied bytes must be strict canonical JSON for the exact
`MESC-TRAINING-EXECUTOR-V1` receipt key set. Qualification requires:

- `disposition == SUCCEEDED`;
- `failure_reason == null`;
- non-empty, unique, path-ordered result artifacts;
- canonical SHA/git identities;
- `result_manifest_sha256` recomputed from the exact result artifact set; and
- receipt identity recomputed from the parsed canonical payload.

No opaque receipt digest is accepted in place of these bytes.

## Release-bound evidence requirements

Each provenance/rights/SBOM/evaluation evidence item contains:

1. exact non-empty evidence artifact bytes; and
2. a strict canonical JSON envelope binding those bytes to:
   - evidence kind;
   - repository;
   - tag;
   - positive release id;
   - exact observed release asset manifest SHA-256;
   - successful training execution receipt SHA-256;
   - exact artifact byte count and SHA-256; and
   - `disposition == PASS`.

Artifact semantics are additionally checked:

- provenance binds the asset manifest and training receipt;
- rights is `PASS` and binds the asset manifest;
- SBOM is JSON identifying CycloneDX or SPDX;
- evaluation is `PASS` and binds both the asset manifest and training receipt.

Every document in one bundle must agree on repository/tag/release id/asset manifest and
must reference the exact validated training receipt.

## Authority boundary

This package does **not**:

- execute training or evaluation;
- create or upload GitHub Release assets;
- download remote bytes;
- invent provenance, rights, SBOM, or evaluation evidence;
- grant training authorization;
- mutate MedScale; or
- claim `RELEASE_READY` by itself.

Synthetic CI fixtures exercise only the validator contract. Real readiness still requires
real post-training evidence and independently observed release assets.
