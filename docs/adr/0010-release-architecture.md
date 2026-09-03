# ADR-0010 — Release Architecture: GitHub-Canonical, CI-Published, Gated Distribution

- **Status:** Accepted
- **Date:** 2026-07-10
- **Accepted:** 2026-09-03 after reconciliation to canonical `main`
- **Deciders:** Operator (solo founder)
- **Supersedes:** none
- **Superseded by:** none
- **Related:** [ADR-0003](0003-repository-topology.md) (topology),
  [ADR-0005](0005-research-intelligence-scope.md) (identity),
  [docs/releases/](../releases/README.md) (binding release policy),
  [distribution_hf.md](../architecture/distribution_hf.md) (HF identity record)

## Context

MedScale publishes or may publish artifacts across five classes (package, models,
datasets, benchmarks, papers/replication packages) to GitHub Releases and separately
authorized distribution surfaces such as PyPI and Hugging Face. Without a decided
architecture, each release becomes an ad-hoc event: manual uploads, mutable artifacts,
cards drifting from sources, and numbers in papers that no longer trace to bytes.

At acceptance, canonical `main` already contains `.github/workflows/release.yml`. That
workflow implements SHA-pinned package quality/build automation, PR-safe artifact
round-trip qualification, clean installation of the exact built wheel, installed
metadata/CLI version binding, tag/version binding, and GitHub Release creation for an
authorized `v*` tag. The historical `v0.2.0` tag predates some of that later workflow
hardening and must not be described as having run automation added afterward.

TestPyPI, PyPI, and Hugging Face publication remain separately governed distribution
edges. Their absence is a release-readiness gap, not permission for a manual upload.

## Decision

1. **Canonical flow:** GitHub is the only source of truth. Build and qualification run
   from GitHub CI. GitHub Releases precede any separately authorized external mirror or
   package distribution. A distribution surface that drifts from its source tag is a
   defect.
2. **Releases are immutable.** Tags never move; published artifacts never change;
   fixes are new versions. Deprecation and retraction mark artifacts visibly and never
   delete them.
3. **CI is the only publisher.** PyPI/TestPyPI publication must use trusted publishing;
   Hugging Face publication must use release automation. External distribution jobs
   require an operator-approval environment gate and least privilege. Manual uploads
   (CLI/web) are prohibited. Until a particular distribution path is implemented and
   separately authorized, that distribution waits.
4. **Qualify the exact artifact that is distributed.** A publication path must reuse
   the exact built artifact that passed identity, clean-install, and version-binding
   qualification; it must not silently rebuild a second candidate.
5. **Every release carries the applicable reproducibility record**
   ([releases/reproducibility.md](../releases/reproducibility.md)): source identity,
   tool/environment identity, and artifact-specific evidence required by the relevant
   release class. Release validation must not invent unavailable scientific evidence.
6. **Lifecycle states are governed:** PLANNED → IN_DEVELOPMENT → RELEASE_CANDIDATE →
   RELEASED → DEPRECATED/RETRACTED, with per-class checklists
   ([releases/release_process.md](../releases/release_process.md)).
7. **Cards are verification documents.** Model/dataset cards carry required safety,
   provenance, licence, and version metadata appropriate to their artifact class.
8. **Model naming reconciliation:** the released family is **MESC** (`mesc-fhir`,
   `mesc-evidence`); "MedScale-Base" exists only as `medscale-base-ref`, a pinned
   configuration release, never MedScale-trained base weights — preserving
   "adapt, don't pretrain".

## Consequences

**Positive:** publication becomes a pipeline with the same integrity properties as the
science (immutable, verified, reproducible); external distribution cannot become a
second source of truth; a future collaborator inherits procedures, not tribal
knowledge.

**Negative / costs:** each external distribution path requires dedicated automation,
environment protection, and operator approval before use; immutability forces version
discipline even for trivial fixes; distribution may wait after a GitHub Release until
its own governed path is qualified.

## Alternatives considered

- **Manual publishing with checklists only.** Rejected: checklists without enforcement
  decay; one manual upload can break the provenance chain invisibly.
- **Hugging Face as primary home for models/datasets.** Rejected: MedScale's claims
  trace to git tags and manifests; distribution mirrors do not replace repository-wide
  governance and evidence gates.
- **Separate release repositories per artifact.** Rejected: contradicts ADR-0004's
  single-repo discipline; prefixed tags provide independent artifact cadences.

## Compliance

This ADR is binding from its accepted reconciliation on 2026-09-03.

- `.github/workflows/release.yml` is the canonical implemented package/GitHub-Release
  automation surface at acceptance.
- TestPyPI/PyPI/Hugging Face distribution automation is not created or authorized by
  accepting this ADR; each path requires separately scoped implementation,
  qualification, and distribution authority.
- No credential, secret, OIDC trust relationship, environment, tag, release, upload,
  model/data execution, or deployment authority is created by this decision alone.
- Manual PyPI/Hugging Face uploads are integrity violations; any published integrity
  failure follows the retraction process.
