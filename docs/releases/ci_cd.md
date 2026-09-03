# Release CI/CD

- **Status:** Partial implementation; package build/GitHub Release workflow exists, external publication remains gated
- **Original design date:** 2026-07-10
- **Related:** ADR-0010 remains Proposed unless and until separately ratified

## Current implemented state

The repository currently contains these release-related automation surfaces:

- `.github/workflows/ci.yml` — Python 3.11/3.12 quality gate with locked sync, Ruff, Ruff format, strict Mypy, Pytest with coverage, machine-state integrity checks where applicable, and `medscale check`.
- `.github/workflows/codeql.yml` — code scanning.
- `.github/workflows/release.yml` — SHA-pinned package-release workflow.

`release.yml` currently provides:

1. **Tag path (`v*`)** — quality gate → wheel/sdist build → exact artifact download → clean installed-wheel `medscale --version` smoke → GitHub Release creation.
2. **PR-safe workflow qualification** when `release.yml` changes — build wheel/sdist, compute SHA-256 checksums, upload the qualification artifact, download it in dependent jobs, verify byte identity, and install the exact wheel into a fresh Python 3.11 environment without a source checkout before checking `medscale --version`.
3. Third-party Actions referenced by immutable commit SHA.

The clean-install jobs intentionally do not check out repository source. Their `medscale --version` success therefore comes from the downloaded wheel installed into the fresh environment rather than an in-tree `src/` import.

The existence of this workflow does **not** authorize creating a tag, publishing a release, or uploading to PyPI/TestPyPI/Hugging Face. It describes available automation only.

## Design principles that remain binding

1. **CI is the publication mechanism when publication is authorized.** Do not substitute ad-hoc local uploads for an approved CI path.
2. **Human/governance gate at the distribution edge.** Publication remains an explicit decision even when automation exists.
3. **Validate before distribution.** Artifact identity, package validity, release semantics, and required evidence must be established before external publication.
4. **No runtime CD.** MedScale ships research artifacts/packages; this workflow does not deploy a clinical or hosted runtime.

## Current vs future work

| Capability | Current status | Boundary |
|---|---|---|
| Python quality gate | Implemented | CI |
| Coverage floor | Implemented in test configuration/CI | Quality only |
| Wheel + sdist build | Implemented | Tag path and PR-safe qualification |
| Artifact upload/download byte-identity qualification | Implemented | PR-safe workflow self-qualification |
| Clean installed-wheel CLI smoke (`medscale --version`) | Implemented in tag and PR-safe workflow paths | Installs the exact built wheel into a fresh venv without source checkout |
| GitHub Release creation from `v*` tags | Implemented workflow path | Requires quality, build, and clean-wheel smoke plus an authorized tag push; workflow existence is not release authority |
| TestPyPI publication/dry-run path | Not implemented | Must use trusted publishing/OIDC and an explicitly gated environment if authorized |
| PyPI publication | Not implemented | Separate publication authority required |
| Hugging Face dataset/model publication | Not implemented by this package workflow | Separate artifact-specific governance required |
| Docs/data/reproducibility specialized validation workflows | Directional / separate work | Add only with a concrete consumer and scoped authority |

## Future publication design constraints

A future TestPyPI/PyPI path should prefer GitHub trusted publishing (OIDC), least privilege, environment protection, and exact artifact reuse. A qualification job must never silently rebuild a different wheel for publication; the published artifact should be the exact artifact that passed build, byte-identity, and clean-install qualification.

Dataset/model publication requires its own contract, licence checks, manifest/card validation, provenance, and applicable scientific/governance evidence. Package release automation must not be treated as model or dataset release authority.

## Non-goals

- No automatic model training or retraining.
- No deployment to clinical or product runtimes.
- No hidden credentials or local publishing path.
- No auto-merge.
- No claim that an old tag ran workflow revisions added later.

The pipeline's purpose is to make an **approved and qualified** path reproducible, not to turn repository automation into approval.
