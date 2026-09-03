# Artifact Lifecycle

- **Status:** Binding strategy (ADR-0010, Accepted)
- **Original design date:** 2026-07-10
- **Governance reconciliation:** 2026-09-03

## Lifecycle states (all artifact classes)

```text
PLANNED ──► IN_DEVELOPMENT ──► RELEASE_CANDIDATE ──► RELEASED ──► DEPRECATED
                                                        │              │
                                                        └──► RETRACTED ◄┘
```

| State | Meaning | Exit condition |
|---|---|---|
| PLANNED | Named in a roadmap/spec; no gate passed | Phase gate opens |
| IN_DEVELOPMENT | Being built under its phase ticket | Release criteria met |
| RELEASE_CANDIDATE | Checklist executed; manifest built; validation green | Operator approval |
| RELEASED | Tagged, immutable, distributed through the applicable authorized surface | — (immutable) |
| DEPRECATED | Superseded; still available; card/README banner names the successor | — |
| RETRACTED | Defective or integrity-compromised; marked, **never silently deleted**; reason + successor recorded | — |

**Why immutability:** every MedScale claim cites artifacts by version (R7). A mutable
release would silently invalidate published numbers — the exact failure mode the
program exists to prevent.

## Artifact registry

### 1. Python package — `medscale`

| Aspect | Policy |
|---|---|
| Contents | The library: reproducibility primitives, evidence model, litdb; later fhirkit/bench per phase |
| Release criteria | Quality gate green on CI matrix; CHANGELOG section written; version bumped in `__about__.py` when a new version is authorized; docs consistent; no unreleased schema change unnoted |
| Versioning | SemVer, `0.x` until the separately governed 1.0 evidence criterion is met ([versioning.md](versioning.md)) |
| Channels | GitHub Release through the qualified `vX.Y.Z` workflow path when a tag is separately authorized. ALIGN-24 implements a fail-closed TestPyPI repository path, but it remains disabled until the protected `testpypi` Environment and matching Trusted Publisher are independently evidenced and the enable variable is explicitly set. Production PyPI remains unimplemented. |
| Changelog | Keep-a-Changelog style; every release has a section; "Unreleased" accumulates |

### 2. Models (future — gates in [ai_model_strategy](../architecture/ai_model_strategy.md))

Naming reconciliation (binding): MedScale **never pretrains**, so "MedScale Base" cannot
be a trained model. The family name is **MESC**; released artifacts are *adapters* plus
pinned base references.

| Artifact | What it actually is | Earliest phase |
|---|---|---|
| `medscale-base-ref` | A **configuration release**, not weights: pinned Tier-1 base model id + revision + grammar + prompts + decoding params. Why: makes the "constrained base" condition of RQ1/RQ2 citable and reproducible | T4 |
| `mesc-fhir` (= MESC-v0) | QLoRA adapter for FHIR generation/validation/repair tasks | T6 |
| `mesc-evidence` | Adapter for evidence-extraction tasks (pillar 2) | H2 |

Per model, required at release: source repo tag; training manifest (data snapshot
hashes, seeds, config); evaluation on the pinned benchmark version (3 seeds, mean ±
95% CI, constraint/prompting deltas split); model card per [model_cards.md](model_cards.md);
licence per [licensing.md](licensing.md) and the applicable upstream terms;
reproduction manifest; the [release checklist](release_process.md). Model access or
implementation does not itself establish redistribution eligibility.

### 3. Datasets (future)

| Artifact | Provenance | Earliest phase |
|---|---|---|
| `medscale-litdb` | Export of the literature database: records + screening states + evidence objects. Field-level licence filter applied as required by its release evidence | end of T1 |
| `medscale-bench-data` | Synthetic FHIR task data (Synthea + fixtures + validator-labeled corruptions) | T3 |
| `medscale-evidence` | The verified evidence-object corpus (may ship inside litdb v1; separate once it grows) | H2 |
| `medscale-fhir-synthetic` | Reusable synthetic FHIR corpora from the T5 pipeline | T5 |

Per dataset, required: provenance chain (R1 for literature; generator version + seed +
config for synthetic); per-release licence evidence; immutable snapshot with content
hash (`medscale.reproducibility.content_hash` over the canonical export); metadata
schema declared ([dataset_cards.md](dataset_cards.md)); and the separately implemented
validation required by the applicable release gate. A planned DOI or mirror is not
claimed until its own publication path and evidence exist.

### 4. Benchmarks

MedScale-Bench = **spec + data + scorers + leaderboard**, versioned together
([benchmark_publication.md](benchmark_publication.md)). Earliest: T3.

### 5. Papers & replication packages

Every paper release follows the governed replication-package requirements: repo tag,
applicable manifests/data snapshots, and exact reproduction commands
([papers.md](papers.md)). Paper publication remains evidence-dependent.

### 6. Documentation & schemas

Docs version with the repository (tags snapshot them); superseded docs move to
`docs/archive/` with an in-file banner. Schemas (evidence `schema_version`, future
knowledge/FHIR grammar schemas) use append-only integer versions per ADR-0009;
schema bumps require their applicable governance.

## Ownership

Solo-operator program: the operator is release manager for every class. Each checklist
still names its verification commands so that a future second maintainer inherits a
procedure, not tribal knowledge.
