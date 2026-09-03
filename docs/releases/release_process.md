# Release Process & Checklists

- **Status:** Strategy (ADR-0010, Proposed)
- **Date:** 2026-07-10

Verification is a run, not a claim (R5): every checklist item names *evidence* — a
command output, a file, a link. A checklist executed without pasted evidence is not
executed.

## The common spine (every release, any class)

1. Phase gate open, work merged to `main`, tree clean, CI green.
2. Class checklist (below) executed; evidence recorded in the release PR/commit.
3. Reproduction manifest built ([reproducibility.md](reproducibility.md)).
4. Tag pushed (`vX.Y.Z` or `<artifact>-vX.Y`); GitHub Release created with manifest +
   CHANGELOG excerpt attached.
5. Distribution (PyPI / HF) **from CI only**, behind operator approval
   ([ci_cd.md](ci_cd.md)). Until automation exists, distribution waits — a release
   without automation is a GitHub Release only.

---

## Checklist: Python package release

- [ ] Quality gate green locally **and** on CI matrix (3.11 + 3.12)
- [ ] Version bumped in `__about__.py`; CHANGELOG section dated
- [ ] Public API changes reflected in docs; new modules in `docs/README.md` map
- [ ] `uv build` produces wheel + sdist
- [ ] The release workflow downloads the exact built wheel, installs it into a fresh Python 3.11 venv without source checkout, and verifies `medscale --version` before GitHub Release creation
- [ ] Tag `vX.Y.Z`; GitHub Release with CHANGELOG excerpt + manifest
- [ ] (v0.2+) PyPI publish via CI job with operator approval only after the separately governed publication path exists

The clean-wheel gate is package qualification, not publication authority. It proves that the exact built wheel installs and exposes the expected CLI version; it does not create a tag, approve a release, or configure PyPI/TestPyPI credentials or trusted publishing.

## Checklist: HF model release

- [ ] Base model is Tier-1 (ADR-0006) — or a dedicated Accepted ADR authorizes otherwise
- [ ] Training manifest: data snapshot hashes, seeds, config, compute log
- [ ] Evaluation on pinned benchmark version: 3 seeds, mean ± 95% CI, constraint vs prompting deltas split
- [ ] Contamination assertion output attached (nothing tuned on test)
- [ ] Model card complete per [model_cards.md](model_cards.md) — including the
      not-a-medical-device and synthetic-only statements
- [ ] Licence + inheritance verified per [licensing.md](licensing.md)
- [ ] GitHub Release `<model>-vX.Y` first; HF repo mirrors it via CI with approval
- [ ] HF card metadata: version, licence, `base_model`, tags per [distribution.md](distribution.md)

## Checklist: HF dataset release

- [ ] Provenance complete (R1 for literature-derived; generator+seed+config for synthetic)
- [ ] Field-level licence review done; excluded fields documented (`LICENSE.md` in the export)
- [ ] Content hash of canonical export recorded; snapshot immutable
- [ ] Dataset card complete per [dataset_cards.md](dataset_cards.md)
- [ ] Validation pipeline green: schema check, licence check, contamination assertion (if splits)
- [ ] PHI statement: synthetic-only / metadata-only affirmed (R2)
- [ ] GitHub Release `<dataset>-vX.Y`; HF mirrors via CI; Zenodo DOI if paper-cited

## Checklist: HF Space release

- [ ] The artifact the Space demonstrates is itself RELEASED (a Space never previews unreleased work)
- [ ] Space pins exact released versions (no `main` dependencies)
- [ ] No data collection from users; no PHI input paths; disclaimer text present
- [ ] Runs within free/affordable hardware tier or has an approved cost note
- [ ] Source of the Space lives in GitHub; HF Space repo is a mirror

## Checklist: Benchmark release

- [ ] Spec document versioned: tasks, metrics, splits, scoring, failure taxonomy
- [ ] Scorers deterministic + unit-tested; byte-identical re-runs demonstrated
- [ ] Data checklist (above) passed for the bench data
- [ ] Baseline results published with the release (never a bare benchmark)
- [ ] Leaderboard policy stated per [benchmark_publication.md](benchmark_publication.md)
- [ ] MAJOR bumps state score incomparability explicitly

## Checklist: Paper publication

See [papers.md](papers.md) — pre-registered falsification criteria, R1 citations from
litdb only, replication package tagged before submission.

## Checklist: Dataset update / Model update

- [ ] New version per [versioning.md](versioning.md) (never in-place)
- [ ] Diff summary vs prior version (rows/fields/weights changed and why)
- [ ] Prior version marked DEPRECATED with successor pointer — remains downloadable
- [ ] Downstream compatibility note (which benchmark/model versions consumed the old one)

## Checklist: Deprecation

- [ ] Successor released (or explicit end-of-line rationale)
- [ ] Banner on GitHub Release notes + HF card ("Deprecated — use X")
- [ ] CHANGELOG entry; `deprecated` tag in HF metadata
- [ ] No deletion; no breaking of existing download paths

## Checklist: Retraction (integrity failure)

- [ ] Written reason: what was wrong, what it invalidates, how detected
- [ ] RETRACTED banner on GitHub Release + HF card; artifact stays visible (science
      requires the record; deletion hides the lesson)
- [ ] Every dependent artifact assessed; dependents re-released or deprecated
- [ ] If a paper cited it: correction/notice per venue policy
- [ ] Post-mortem note added to `docs/archive/`
