# MedOrigin — Successor Software Version Decision Dossier

- **Status:** PROPOSED FOR FOUNDER REVIEW — not a version authorization, release candidate, tag, or publication grant
- **Prepared:** 2026-10-17
- **Source for this assessment:** protected `main` at `41469c0626b1a4c57536fdb9920f538841d6dd25`
- **Tracker:** [Software release #574](https://github.com/TheHalfMoon/MedOrigin/issues/574)
- **Binding policy:** [ADR-0010](../adr/0010-release-architecture.md), [ADR-0011](../adr/0011-versioning-licensing.md), [ADR-0020](../adr/0020-public-api-stability.md), [R1–R7](../governance/rules.md), [release process](release_process.md), and the MRL-0809 static-prerequisite freeze

## 1. Decision requested, not yet made

**Proposed** next Research Core distribution: `medscale 0.3.0` under public project name **MedOrigin**, preserving the `medscale` import namespace, CLI and public contract. A minor increment is a conservative *proposal* to account for substantial changes since the historically tagged `0.2.0`; a full public-API, persisted-data-format and deprecation review must confirm whether `0.3.0` is appropriate under ADR-0020 before adoption. It is **not** a factual claim that all breaking changes have been assessed. Retain `0.2.0` as the **current** build version until a governed version-change decision is recorded.

The independently installable Workspace has its own distribution identity `medscale-workspace`, dynamic version sourced from `apps/workspace/src/medscale_workspace/__init__.py`, and baseline `0.1.0.dev1`. **No new Workspace version is proposed here**; its cadence, candidate suffix, and inclusion/exclusion from the first Core GitHub Release must be explicitly decided separately. Its local offline synthetic shell is not a clinician GUI or an authorized PHI/EHR runtime.

No package index, model, dataset, research training, clinical deployment or external distribution is in scope.

## 2. Immutable historical lineage and current verified artifacts

| Evidence | Verified identity and limit |
| --- | --- |
| Historical annotated tag | `v0.2.0`, tag-object SHA `0a05333fb8551ec262f5304a273bb075c8e8fe46`, target commit `d2e651a55c92f2218aca49acaa5b7bd18a75f096`; **never move/recreate** |
| Current package version | `src/medscale/__about__.py` = `0.2.0`; Hatch reads it dynamically |
| Current Core distribution and CLI | `medscale`, `medscale --version`; no unconditional Core runtime dependencies |
| Workspace | `medscale-workspace 0.1.0.dev1`, local synthetic-only shell; pinned runtime `cryptography==50.0.1` |
| Latest qualified main | `41469c0626b1a4c57536fdb9920f538841d6dd25`; [12/12 full CI jobs](https://github.com/TheHalfMoon/MedOrigin/actions/runs/38996765545), [CodeQL](https://github.com/TheHalfMoon/MedOrigin/actions/runs/38996765654), [five optional-extras jobs](https://github.com/TheHalfMoon/MedOrigin/actions/runs/38996765616) and [read-only release round trip](https://github.com/TheHalfMoon/MedOrigin/actions/runs/38996816435) all **SUCCESS** |
| Actual downloadable qualification artifact | [GitHub run #38996816435](https://github.com/TheHalfMoon/MedOrigin/actions/runs/38996816435), artifact ID `12087835985`, archived digest `sha256:a27aa3ab32b72d8015a8128e68c60e974233ec03f9b76380d57769052429f42c`; inner wheel SHA-256 `4ee77ac19ec43daa58f6ff079944f3deff9ed2aeba0f8f214f47c6567e4281d6`, sdist SHA-256 `c10e66842673e927628937f1d101590bf3153aab23f956e902e0baaa49970af6` |
| Final receipt | [Issue #574 technical completion](https://github.com/TheHalfMoon/MedOrigin/issues/574#issuecomment-6231258914); source-only candidate evidence, **not an approved versioned release** |

All project/tag-version comparisons and artifact hashes refer to their **explicit source**; a wheel built from current `main` with metadata `0.2.0` is not the historical tagged `v0.2.0` artifact. GitHub Action artifacts are ephemeral and are not distribution authorization.

## 3. Frozen-input collision — must be solved before changing root metadata

The canonical MRL-0809 frozen static prerequisites bind the byte content of the root files:

| Frozen input | SHA-256 independently verified on Windows |
| --- | --- |
| `pyproject.toml` | `c36c33208236dafb136a147dfff0060d592e23daab4b4240521d4747d23ea510` |
| `uv.lock` | `6fa0e0b49d19e305032ecd04940db0b9e252dd23b6fbec588b224f739048efc4` |

The accepted research prerequisite manifests under `specs/mesc-experiment-0/` record these exact hashes. A previously attempted root dependency change caused a negative-evidence drift; see `specs/medscale-clinical-workspace-v1/cw-002-dependency-license-review.md`. **Do not regenerate an older manifest in place or weaken its drift gate.** If a successor *research* prerequisite set is authorized, it needs a new, separately approved immutable identity with lineage back to its predecessor; all still-applicable historical evidence remains preserved.

The current root `pyproject.toml` points its `Homepage`, `Repository`, `Documentation` and `Issues` metadata to the historical `https://github.com/TheHalfMoon/MESC` path. Although historical links may redirect, a new MedOrigin-branded public package should point to `https://github.com/TheHalfMoon/MedOrigin` **only after** a governed frozen-input reconciliation. Do not falsify package metadata by replacing the frozen root bytes without that authorization.

**Important lock nuance:** the current `uv.lock` local editable `medscale` package entry has **no `version` key**. Do not claim it carries a separately pinned `0.2.0` value or that a version bump necessarily requires `uv.lock` regeneration. Any proposed change to `__about__.py`, Hatch output, the root metadata, or the resolver must instead be tested on an isolated copy with `uv sync --frozen`, then checked against the exact MRL prerequisite byte contracts. No speculative mutation is authorized by this dossier.

## 4. Other affected sources and compatibility gates

The separate [historical-compatibility preflight](historical_compatibility_preflight_574.md) found static public-facade stability but a meaningful `dataset freeze` persisted-byte/order correction and 187 changed source paths. This is preliminary evidence only, not complete source-to-source behavioral compatibility.

1. **Source-of-truth version:** `src/medscale/__about__.py` feeds installed metadata and `medscale --version`; test wheel/sdist, clean installed CLI, and exact new `vX.Y.Z` match. A version bump is not merely a string change.
2. **Historical citation:** `CITATION.cff` currently records MedOrigin with historical version `0.2.0` and released date `2026-07-13`. `tests/test_medorigin_public_identity.py` intentionally asserts those values. Preserve the historical citation until an independently approved successor version/date exists; then update the citation and regression contract in the same authorized release change, without backdating.
3. **Change reporting:** propose the applicable `CHANGELOG.md` section and source-accurate `RELEASES.md` successor entry; never overwrite the historical `v0.2.0` narrative or invent dates, model-performance claims or release receipts.
4. **PR-safe release workflow:** the current `release.yml` PR/manual read-only path intentionally checks installed `0.2.0`; the tag path already derives metadata version and requires the tag to match. Any authorized successor version must update/qualify nonpublishing assertions and regression tests without weakening the tag-vs-wheel equality check, token privileges, upload/download identity or publish gating.
5. **Public compatibility review:** enumerate public-frozen API changes, CLI exit-code/flag changes, data-format/identifier changes and required deprecation aliases since historical tag; record decisions against ADR-0017 and ADR-0020. This has **not** been completed by CI alone.
6. **Optional extras and licensing:** Core's base wheel has no unconditional runtime dependencies, but optional ML/ASR/training extras carry their own license and redistribution constraints; they are **not bundled model weights**. Workspace's runtime `cryptography==50.0.1`, `cffi` and `pycparser` have [recorded license evidence](../../specs/medscale-clinical-workspace-v1/cw-002-dependency-license-review.md), not a universal third-party release waiver. Do not add weights/datasets/vendor sources to an artifact absent exact rights, notices and source provenance.
7. **Clinical and scientific scope:** maintain the strict synthetic-only, no-PHI, no-backflow, no production EHR write and no-clinical-accuracy-claim boundary. Research MRL-0809 and CW-021 remain independently governed.

## 5. Decision alternatives (ordered, all unapproved)

| Option | What would happen | Disposition now |
| --- | --- | --- |
| **A — Reconcile a successor source identity first** | Propose and obtain explicit governed approval for a future version and any root-metadata edits; preserve prior frozen inputs and create successor evidence/manifest identity if required; run strict contract and build tests on a new branch; only then seek separate release/tag approval. | **Recommended path for a truthful MedOrigin-branded distribution**; not authorized by this proposal |
| **B — Stage source-independent packaging projection** | Design a separately governed packaging adapter producing updated distribution metadata without mutating frozen source files. Must prove exact source/metadata provenance, compatibility, clean-install, no hidden tag/version override, complete CI and an Accepted ADR. | Research alternative only; **not adopted**, because it risks release-source drift |
| **C — Keep the current source preview** | Continue offering documented source-checkout build/install instructions for `0.2.0` without creating a tag or presenting a new release. | **Current safe default** until Option A is approved |

**Do not silently choose Option B to evade frozen inputs.** A build-time overlay that lies about source or version is a release integrity defect.

## 6. Evidence needed for an authorized implementation

- [ ] Founder/operator accepts a specific successor Core SemVer, confirms Workspace release scope, and explicitly chooses a source-identity reconciliation strategy. This decision does **not** itself authorize release publication.
- [ ] Exact historical-tag-to-successor API, persisted-format and behavioral compatibility audit, including any deprecation migrations and test receipts.
- [ ] Frozen MRL-0809 byte-identity impact analysis, documented separate research authorization for any changed frozen source, and preserved legacy manifests/evidence.
- [ ] On an independent future implementation PR: source-version/metadata/citation/docs and test consistency, root `uv sync --frozen` verification, no-backflow/FHIR boundary tests, wheel/sdist license checks, clean-install on Python 3.11 and 3.12, and CodeQL/quality/optional-backend CI.
- [ ] Verified reproducibility manifest with exact **future** tree/commit, tools/platform, wheel/sdist SHA-256, installed metadata/CLI, rights, supported Python versions and expressly excluded capabilities.
- [ ] **A second, explicit tag/GitHub Release authorization** under ADR-0010 and R5/R6; CI-only publisher from the exact artifact, protected environment where required; TestPyPI/PyPI/Hugging Face remain separately disabled unless approved and proven.
- [ ] After actual publication only: record immutable version/tag/commit/artifact receipts and change tracker status to `SOFTWARE_RELEASED`. Until then use `SOFTWARE_WORK_IN_PROGRESS` / bounded source-qualification status.

## 7. Prohibited work by this document

No changes to `pyproject.toml`, `uv.lock`, previously frozen specs, the historical `v0.2.0` tag, a source release version, model weights, research data, patient records, production EHR state, GPU experiments, published artifacts, credentials or external publisher configuration. No claim of a completed clinician UI, clinical approval, scientific readiness or a publicly released new MedOrigin version.

**Decision state: `PROPOSED_ONLY`. The issue #574 version/tag-planning gate remains OPEN for formal founder decision and any requisite frozen-input authorization.**
