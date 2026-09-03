# Release CI/CD

- **Status:** Partial implementation; package/GitHub Release and fail-closed TestPyPI repository paths exist, external TestPyPI activation remains unverified and disabled
- **Original design date:** 2026-07-10
- **Governance reconciliation:** 2026-09-03
- **Related:** ADR-0010 is Accepted and governs this distribution architecture

## Current implemented state

The repository currently contains these release-related automation surfaces:

- `.github/workflows/ci.yml` — Python 3.11/3.12 quality gate with locked sync, Ruff, Ruff format, strict Mypy, Pytest with coverage, documentation link hygiene, machine-state integrity checks where applicable, and `medscale check`.
- `.github/workflows/codeql.yml` — code scanning.
- `.github/workflows/release.yml` — SHA-pinned package-release workflow.

`release.yml` currently provides:

1. **Tag path (`v*`)** — quality gate → wheel/sdist build → exact artifact download → clean installed-wheel smoke → installed package metadata/CLI/tag version consistency → GitHub Release creation.
2. **Fail-closed TestPyPI distribution edge** — after successful GitHub Release creation, the job downloads the exact same-run `dist-${{ github.ref_name }}` artifact and uses the SHA-pinned official PyPA Trusted Publishing action against TestPyPI. It performs no checkout or rebuild. It is tag-only, references the `testpypi` environment, scopes `id-token: write` to the publication job, and additionally requires `vars.TESTPYPI_PUBLISH_ENABLED == 'true'`.
3. **PR-safe workflow qualification** when `release.yml` changes — build wheel/sdist, compute SHA-256 checksums, upload the qualification artifact, download it in dependent jobs, verify byte identity, and install the exact wheel into a fresh Python 3.11 environment without a source checkout. The current v0.2.0 qualification requires installed metadata version `0.2.0` and matching `medscale --version` output. Required repository tests also inspect the TestPyPI job contract without invoking the publisher.
4. Third-party Actions referenced by immutable commit SHA.

The clean-install jobs intentionally do not check out repository source. Their
`medscale --version` success therefore comes from the downloaded wheel installed into
the fresh environment rather than an in-tree `src/` import.

The tag-path gate does not hard-code `0.2.0`: it derives the installed version from
`importlib.metadata`, requires the CLI to report that same version, and requires
`GITHUB_REF_NAME` to equal `v<installed-version>`. A later correctly versioned release
can therefore qualify without weakening the current v0.2.0 PR baseline.

The TestPyPI repository path is deliberately **disabled by default**. This repository
does not set `TESTPYPI_PUBLISH_ENABLED`, and the connected execution surface cannot
verify or configure the required protected GitHub Environment or matching TestPyPI
Trusted Publisher. A YAML `environment: testpypi` reference is therefore not evidence
that the external protection exists. The enable guard must remain false until that
external configuration is independently evidenced and operator-approved.

The historical `v0.2.0` tag predates later workflow hardening. Current automation must
not be projected backward onto that historical tag.

The existence of these workflow paths does **not** authorize creating a tag, publishing
a release, enabling TestPyPI, or uploading to PyPI/TestPyPI/Hugging Face. It describes
implemented repository automation only.

## Binding design principles

1. **CI is the publication mechanism when publication is authorized.** Do not substitute ad-hoc local uploads for an approved CI path.
2. **Human/governance gate at the distribution edge.** Publication remains an explicit operator decision even when automation exists.
3. **Validate before distribution.** Artifact identity, package validity, release semantics, and required evidence must be established before external publication.
4. **Reuse the exact qualified artifact.** A publication job must not silently rebuild a different wheel.
5. **Least privilege.** External distribution uses only the permissions required by that path; trusted-publishing/OIDC authority is scoped to the applicable gated environment.
6. **Fail closed on external configuration.** Repository automation must not infer that a protected Environment or Trusted Publisher exists merely from a workflow reference.
7. **No runtime CD.** MedScale ships research artifacts/packages; this workflow does not deploy a clinical or hosted runtime.

## Current vs future work

| Capability | Current status | Boundary |
|---|---|---|
| Python quality gate | Implemented | CI |
| Coverage floor | Implemented in test configuration/CI | Quality only |
| Documentation source/link hygiene | Implemented in required CI | Repository-local, no network/hosting authority |
| Wheel + sdist build | Implemented | Tag path and PR-safe qualification |
| Artifact upload/download byte-identity qualification | Implemented | PR-safe workflow self-qualification |
| Clean installed-wheel CLI smoke (`medscale --version`) | Implemented in tag and PR-safe workflow paths | Exact built wheel, fresh venv, no source checkout |
| GitHub Release creation from `v*` tags | Implemented workflow path | Requires an authorized tag push; workflow existence is not release authority |
| TestPyPI Trusted Publishing repository path | Implemented by ALIGN-24 and PR-qualified | Disabled unless explicit enable guard is true; external Environment/Trusted Publisher still requires independent evidence |
| TestPyPI external activation | Not verified or enabled by repository work | Requires protected `testpypi` Environment, matching Trusted Publisher, operator approval, and explicit enable variable |
| PyPI publication | Not implemented | Separate publication authority required |
| Hugging Face dataset/model publication | Not implemented by this package workflow | Separate artifact-specific governance required |
| Hosted documentation deployment | Not currently justified | Add only with a concrete consumer/provider and scoped authority |

## External activation and future publication constraints

The TestPyPI job uses GitHub Trusted Publishing/OIDC, job-local least privilege,
`environment: testpypi`, exact artifact reuse, and the official PyPA publishing action
pinned to an immutable commit. It must remain disabled until the external Environment
protection and matching TestPyPI Trusted Publisher are independently evidenced.

A future production PyPI path requires its own separately scoped implementation,
qualification, external trust configuration, and publication authority. It must reuse
the exact qualified artifact and must not silently rebuild a different wheel.

Dataset/model publication requires its own contract, licence checks, manifest/card
validation, provenance, and applicable scientific/governance evidence. Package release
automation must not be treated as model or dataset release authority.

## Non-goals

- No automatic model training or retraining.
- No deployment to clinical or product runtimes.
- No hidden credentials or local publishing path.
- No auto-merge.
- No claim that an old tag ran workflow revisions added later.
- No claim that repository-side TestPyPI code proves external Trusted Publisher or Environment configuration.

The pipeline's purpose is to make an **approved and qualified** path reproducible, not
to turn repository automation into approval.
