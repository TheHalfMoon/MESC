# Ecosystem Evolution — The Linux-Style Long View

- **Status:** Horizon-3 ecosystem vision; extraction remains deliberately unimplemented and gated
- **Date:** 2026-07-10
- **Current-status reconciliation:** 2026-09-02
- **Related:** [ADR-0004](../adr/0004-t0-foundation-scope.md) (single package — still binding), [ADR-0012](../adr/0012-layered-architecture-model.md) (capability layers), Founder's Permanent Directive (2026-07-10)

MedScale should eventually be an *ecosystem* of independently valuable systems — the way Linux is not a kernel but a world. This document records that ambition **and the gates that keep it from prematurely fragmenting a solo-maintained platform.** Today, one repository and one Python package (`medscale`) remains correct (ADR-0004); ecosystems are extracted from working monoliths, not designed in advance.

The repository has evolved substantially since this vision was written. The table below therefore distinguishes a subpackage/surface that now exists from the much stronger claim that its legacy research phase or future extraction is complete.

## Future systems → where they live today

| Future system (directive) | Lives today as | Graduation phase |
|---|---|---|
| `medscale-core` | reproducibility/provenance plus later governed core research contracts | H2+ |
| `medscale-verification` | validators, deterministic scorers, integrity/evidence gates, and governed verification surfaces inside the monolith | H2+ |
| `medscale-evidence` | `medscale.evidence` and related evidence checks/storage | H2+ |
| `medscale-litdb` | `medscale.litdb` | H2+ |
| `medscale-modelkit` / `medscale-registry` | `medscale.modelkit` plus governed model/runtime/training infrastructure elsewhere in the package | H2+ |
| `medscale-fhir` | `medscale.fhirkit`: validation/report/storage implemented; grammar-constrained generation remains open | H2+ |
| `medscale-bench` | `medscale.bench`: deterministic contracts, scoring, artifacts, and replay implemented; full T3 research completion is not asserted | H2+ — still a plausible early extraction candidate if external demand exists |
| `medscale-training` | governed training contracts/infrastructure exist; execution and promotion remain separately authorized | H3 |
| `medscale-validation` | verification/validator surfaces inside the monolith | H2+ |
| `medscale-research` | research/MRL contracts, procedures, evaluation controls, and reproducibility infrastructure inside the monolith | H3 |
| `medscale-runtime` / `medscale-sdk` / `medscale-cli` / `medscale-api` / `medscale-docs` / `medscale-hub` | CLI/package surfaces exist where implemented, but no independent extracted products are implied | H3 — each extraction needs its own evidence and ADR |
| `medscale-agents` | still separately gated by architecture/governance | H3 |

## Graduation gates (all must hold before any extraction)

1. **External consumers exist** who want the piece without the whole.
2. **The API has been stable** across at least two release cycles.
3. **Independent release cadence is actually needed.**
4. **Maintainer capacity exists.** Every extracted package creates its own CI, versioning, security, and issue-management burden.
5. **A dedicated ADR** records the split, dependency direction, ownership, and migration path.

Until then, subpackage boundaries inside `medscale` are the future package boundaries. Code existence is not extraction authority.

## Interface roadmap (model-agnostic platform growth)

The directive named a set of model interfaces. Current repository implementations have grown beyond the original 2026-07-10 snapshot, but interface presence still does not grant model execution, training, promotion, or deployment authority.

| Interface | Current status | Boundary |
|---|---|---|
| Text generation | Provider-neutral interfaces and governed backend/runtime surfaces exist | Exact model/runtime use remains separately configured and governed |
| Span extraction | Public protocol/surfaces exist | Consumer-specific evaluation remains separately gated |
| Structured output | Use explicit schemas/contracts where implemented | No blanket claim of grammar-constrained decoding |
| Classification | Task-specific deterministic/research surfaces exist where implemented | No autonomous clinical decision authority |
| Embedding | Not a general public platform claim | Add only with a concrete governed consumer |
| Evaluation | Deterministic benchmark/evaluation infrastructure exists | Primary metrics remain non-LLM-judge and evidence-bound |
| Function calling / reasoning / summarization | Not generalized platform claims | Require their own governed consumer and contracts |

## Registry schema evolution

Model and artifact registries should record **verifiable facts**, not marketing capability columns. Fields enter with real governed data and consumers. Historical registry design documents remain useful context, but current canonical contracts and accepted ADRs govern their exact schemas.

## The final picture — consumption-side view

```text
Afia (one application among future many)
│  UI · Workspace · Notes · Agents · Patient Apps · Research Apps
└──► MedScale Engine
     litdb · Evidence Objects · Benchmark · Verification ·
     Model Evaluation · Clinical Knowledge · Research Intelligence · APIs
```

The one-way dependency boundary remains unchanged: MedScale is synthetic-only research infrastructure; PHI and application telemetry do not flow back into its training/evaluation data.

## Beyond the repository (vision only unless separately implemented and authorized)

| Dimension | Long-term targets | Governance boundary |
|---|---|---|
| Distribution artifacts | PyPI · HF org · Docker/OCI images · docs site · archival DOIs | Each publication/extraction path requires release, licence, provenance, and authority gates |
| Community collaborations | HL7 FHIR community · OHDSI/OMOP · research-data/model communities | Collaboration does not waive data/licence/governance requirements |
| Adoption targets | University informatics labs · health systems for validator/benchmark evaluation · standards communities | Adoption targets are directional, not current usage claims |
| Venues | JAMIA / npj Digital Medicine / NeurIPS D&B / ACL BioNLP / EMNLP / AMIA / MLHC | Venue names are planning targets, not publication claims |
| Standards ambition | Reusable release-manifest/evidence-provenance conventions | Must be supported by published specifications and evidence before standardization claims |

Rule unchanged: none of this vision overrides today's canonical repository governance. Each new extraction, capability, publication path, or external dependency enters through its own scoped gate.
