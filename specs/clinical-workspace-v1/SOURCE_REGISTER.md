# Clinical Workspace V1 — Source Register

- **Status:** Source-refresh ledger
- **Issue:** #459
- Names here are references to investigate, not adopted dependencies or verified capability claims.

## Canonical internal sources

- `README.md`
- `ROADMAP.md`
- `docs/vision/MEDSCALE_RESEARCH_VISION.md`
- `docs/vision/MEDSCALE_STRATEGIC_BLUEPRINT_V1.md`
- `docs/architecture/medscale_reference_architecture.md`
- `docs/architecture/ecosystem_analysis.md`
- `docs/architecture/openmed_integration_strategy.md`
- `docs/architecture/openmed_capability_analysis.md`
- `docs/adr/0003-repository-topology.md`
- `docs/adr/0005-research-intelligence-scope.md`
- `docs/adr/0007-openmed-adapter.md`
- `docs/adr/0008-interoperability-fhir-canonical.md`
- `docs/adr/0012-layered-architecture-model.md`
- `docs/adr/0015-model-agnostic-platform.md`
- `docs/adr/0020-public-api-stability.md`
- `docs/adr/0033-modelkit-public-surface-and-runtime-governance.md`
- `docs/adr/0035-mrl-governance-constitution.md`
- `docs/adr/0036-performance-first-health-model-strategy.md`
- `specs/mesc-research-loop-v1/`
- `specs/clinical-workspace-v1/`

## Historical planning

PR #393 is reference material only until reconciled. Do not merge its stale branch directly.

## External/reference families requiring fresh primary-source verification

### Medical scribe
- Abridge
- Suki
- Microsoft/Nuance DAX
- Freed

Verify capture surfaces, local/cloud boundary, transcript/note lifecycle, integration surfaces, human review, and security/privacy claims.

### Evidence/research assistance
- OpenEvidence
- OpenMed

Verify citation model, retrieval/provenance, offline/local behavior, runtime boundary, license/data implications, and reproducibility/export.

### Graph/data workspace
- Graphify
- AFFiNE

Verify graph/data model, local-first storage, derived-view semantics, collaboration/sync, extension architecture, and license/provenance.

### Structured workspace/data grid
- Baserow and other qualified open-source candidates discovered during source review.

Verify local data model, schema/migration, permissions, offline behavior, extension boundary, and license.

## Source admission template

```text
SOURCE_NAME =
SOURCE_TYPE =
PRIMARY_URL =
IMMUTABLE_REVISION =
RETRIEVED_AT =
LICENSE =
LICENSE_EVIDENCE =
CAPABILITY_CLAIMS =
CLAIM_EVIDENCE =
CODE_REUSE = NO | CANDIDATE | APPROVED
REUSE_SCOPE =
SECURITY_REVIEW =
PROVENANCE_REVIEW =
NOTES =
```

## Rules

- Marketing claims are not performance evidence.
- Repository license does not automatically cover models, datasets, media, trademarks, or hosted services.
- Permission does not remove dependency/license compatibility review.
- Prefer bounded interfaces over wholesale copying.
- No source may weaken local-first, no-PHI research-core, evidence, security, or authority boundaries.
