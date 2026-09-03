# Release Process & Checklists

- **Status:** Binding strategy (ADR-0010, Accepted)
- **Original design date:** 2026-07-10
- **Governance reconciliation:** 2026-09-03

Verification is a run, not a claim (R5): every checklist item names *evidence* — a
command output, a file, a link. A checklist executed without pasted evidence is not
executed.

## The common spine (every release, any class)

1. Phase gate open, work merged to `main`, tree clean, required qualification green.
2. Class checklist (below) executed; evidence recorded in the release PR/commit.
3. Applicable reproduction/evidence record built ([reproducibility.md](reproducibility.md)).
4. Tag pushed (`vX.Y.Z` or `<artifact>-vX.Y`) only under separately applicable release authority; GitHub Release created through the qualified workflow path where implemented.
5. External distribution (PyPI / HF or another surface) runs **from CI only**, behind operator approval and only after its own distribution path is implemented and qualified ([ci_cd.md](ci_cd.md)). Until that path exists, external distribution waits.

The current `.github/workflows/release.yml` implements package build/GitHub Release
automation and exact-artifact qualification. TestPyPI/PyPI/Hugging Face publication
remains separately gated and is not created by ADR acceptance.

---

## Checklist: Python package release

- [ ] Quality gate green on the required CI matrix (3.11 + 3.12)
- [ ] Version bumped in `__about__.py`; CHANGELOG section dated when a new version is authorized
- [ ] Public API changes reflected in docs; new modules in `docs/README.md` map
- [ ] `uv build` produces wheel + sdist
- [ ] The release workflow downloads the exact built wheel and installs it into a fresh Python 3.11 venv without source checkout
- [ ] Installed package metadata version and `medscale --version` agree
- [ ] Tag `vX.Y.Z` exactly matches the installed package version `X.Y.Z` before GitHub Release creation
- [ ] GitHub Release contains the qualified artifacts plus the applicable release evidence
- [ ] External PyPI/TestPyPI distribution occurs only after its separately governed trusted-publishing path exists and is authorized

The PR-safe release-workflow qualification for the current baseline also requires the
installed package version to remain `0.2.0`. The tag path is intentionally
version-generic: it derives the wheel's installed metadata and rejects a tag whose
`vX.Y.Z` value does not match that metadata.

The clean-wheel gate is package qualification, not publication authority. It proves
that the exact built wheel installs and exposes a version-consistent CLI; it does not
create a tag, approve a release, or configure PyPI/TestPyPI credentials or trusted
publishing.

## Checklist: HF model release

- [ ] Base model/release terms satisfy the applicable Accepted governance
- [ ] Training manifest: data snapshot hashes, seeds, config, compute log
- [ ] Evaluation on pinned benchmark version with the required statistical evidence
- [ ] Contamination assertion output attached where applicable
- [ ] Model card complete per [model_cards.md](model_cards.md), including required safety statements
- [ ] Licence + inheritance verified per [licensing.md](licensing.md)
- [ ] GitHub Release `<model>-vX.Y` first; HF mirrors it through separately qualified CI with approval
- [ ] HF card metadata binds version, licence, base identity, and required tags

## Checklist: HF dataset release

- [ ] Provenance complete under applicable evidence rules
- [ ] Field-level licence review done; excluded fields documented where required
- [ ] Content hash of canonical export recorded; snapshot immutable
- [ ] Dataset card complete per [dataset_cards.md](dataset_cards.md)
- [ ] Validation pipeline green for schema/licence/contamination requirements
- [ ] PHI/synthetic-data boundary affirmed
- [ ] GitHub Release `<dataset>-vX.Y` precedes any separately qualified external mirror

## Checklist: HF Space release

- [ ] The artifact the Space demonstrates is itself RELEASED
- [ ] Space pins exact released versions (no `main` dependencies)
- [ ] No ungoverned data collection or PHI input path
- [ ] Hardware/cost boundary is approved
- [ ] Source lives canonically in GitHub; any Space repo is a governed mirror

## Checklist: Benchmark release

- [ ] Spec document versioned: tasks, metrics, splits, scoring, failure taxonomy
- [ ] Scorers deterministic + unit-tested; byte-identical re-runs demonstrated
- [ ] Data checklist passed for benchmark data
- [ ] Baseline results satisfy the benchmark publication gate
- [ ] Leaderboard policy stated per [benchmark_publication.md](benchmark_publication.md)
- [ ] MAJOR bumps state score incomparability explicitly

## Checklist: Paper publication

See [papers.md](papers.md). Paper/replication publication remains evidence-dependent and
is not authorized by package release governance.

## Checklist: Dataset update / Model update

- [ ] New version per [versioning.md](versioning.md) (never in-place)
- [ ] Diff summary vs prior version (rows/fields/weights changed and why)
- [ ] Prior version marked DEPRECATED with successor pointer — remains downloadable
- [ ] Downstream compatibility note records consumers of the old version

## Checklist: Deprecation

- [ ] Successor released (or explicit end-of-line rationale)
- [ ] Deprecation banner on applicable release/card surfaces
- [ ] CHANGELOG or artifact-history entry
- [ ] No silent deletion or broken existing download path

## Checklist: Retraction (integrity failure)

- [ ] Written reason: what was wrong, what it invalidates, how detected
- [ ] RETRACTED banner on applicable release/card surfaces; artifact remains visible where integrity policy requires the record
- [ ] Every dependent artifact assessed; dependents re-released, deprecated, or blocked as appropriate
- [ ] Paper corrections/notices handled under venue policy when applicable
- [ ] Post-mortem recorded in the governed archive
