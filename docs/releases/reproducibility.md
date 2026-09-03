# Release Reproducibility — The Manifest

- **Status:** Strategy (ADR-0010, Accepted)
- **Original strategy date:** 2026-07-10
- **Reconciled:** 2026-09-03 under ALIGN-23
- **Related:** [reproducibility policy](../research/reproducibility_policy.md) (the
  binding science policy this operationalizes for published artifacts)

Every future externally published MedScale artifact must carry the applicable governed
release manifest/evidence package required for its class. The manifest is an integrity
contract: publication may not substitute prose for missing provenance, version,
reproduction, rights, or evaluation evidence.

This policy does **not** claim that the current package release workflow already
implements the complete cross-artifact manifest/card/licence validation described
below. Canonical `.github/workflows/release.yml` currently implements package build,
artifact round-trip/identity qualification, clean installed-wheel qualification,
version/tag binding, and GitHub Release creation for an authorized tag path. Broader
manifest/card/licence enforcement remains class-specific future work and must be
implemented and qualified before external publication relies on it.

The historical `v0.2.0` reference is an annotated tag. No corresponding GitHub Release
is evidenced in the repository's current release records. The tag predates later
release-workflow hardening; no later check is projected backward as evidence that the
historical tag passed it.

## Required manifest fields by applicable release contract

A governed release contract may require fields such as:

| Field | Content | Why |
|---|---|---|
| `artifact` | Name + class + version | Identity |
| `git_sha` | Full commit SHA of the source tag/revision | Traceability to canonical source |
| `built_at` | Timezone-aware ISO-8601 build timestamp | Audit |
| `python` | Exact interpreter version when relevant | Environment |
| `lock_hash` | Dependency-lock identity when applicable | Dependency state |
| `tool_versions` | Versions/identities of tools that materially affect the artifact | Gate context |
| `seeds` | Every applicable build/train/eval seed | Determinism/auditability |
| `dataset_snapshots` | Exact dataset names/versions/content identities consumed | Provenance/contamination control |
| `evaluation_manifest` | Exact benchmark/scorer/result identities when evaluation exists | Result traceability |
| `environment` | Relevant OS/accelerator/provider/runtime facts actually used | Bounded nondeterminism disclosure |
| `reproduction` | Exact commands + expected-output identities/pointers | Independent reproduction |

Fields that do not apply to an artifact class must be governed explicitly rather than
silently filled with invented values. Fields that do apply must be supported by actual
evidence.

Canonical serialization/content-identity helpers may be reused where their contracts
fit the release class. Their existence does not by itself mean a full release-manifest
schema or validation pipeline has been implemented for every class.

## Class-specific additions

When applicable and actually evidenced:

- **Models:** training manifest, data/config identities, adapter/training parameters,
  compute record, contamination/split evidence, and evaluation artifacts.
- **Datasets:** generator/version/seed/config for synthetic data or exact acquisition/
  query/run provenance for literature-derived data; field-level rights/licence record.
- **Benchmarks:** task/spec/scorer version, split identities, baseline result artifacts,
  and comparability statement.
- **Papers/replication packages:** exact cited artifact identities, environment,
  commands, expected outputs, and citation/evidence verification.
- **Hosted mirrors/Spaces:** exact canonical source release and pinned artifact
  identities; downstream mirrors never become the source of truth.

## Validation boundary

Validation must be fail-closed for the evidence that its release class requires, but a
requirement is not considered mechanically enforced until the corresponding canonical
workflow/code exists and has passed its own exact-head qualification.

Current package automation must therefore be described only by what it actually checks.
Future TestPyPI/PyPI, Hugging Face, model, dataset, benchmark, paper, or replication
publication paths must add the appropriate manifest/card/licensing/provenance checks in
their own separately scoped units before those paths are eligible for use.

Missing external rights, credentials, trusted-publisher configuration, model/data
access, compute evidence, scientific results, or publication approval cannot be
manufactured by a release manifest or by accepting ADR-0010.
