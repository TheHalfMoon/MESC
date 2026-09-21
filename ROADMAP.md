# MedScale Roadmap

This roadmap is a **filter, not a backlog.** It is a human-readable planning view; canonical specifications, governance, exact-head evidence, and accepted ADRs determine what is actually eligible, complete, releasable, or publishable.

The authoritative scope document is the [Research Vision](docs/vision/MEDSCALE_RESEARCH_VISION.md); the narrative is the [Strategic Blueprint](docs/vision/MEDSCALE_STRATEGIC_BLUEPRINT_V1.md).

## Live status and authority

This file cannot authorize execution, training, model promotion, publication, release, or clinical use. For MESC Research Loop V1 work, live status follows this precedence:

```text
canonical main commit/tree
  -> canonical MRL specifications, governance, and exact gate evidence
  -> independently verified PR/check/review/merge evidence
  -> mechanically derived machine-state projections
  -> human-readable roadmap/status prose
```

`PROJECT_STATE.json`, `CAPABILITY_MATRIX.json`, and `RESEARCH_PROGRAM_INDEX.json` remain non-authoritative derived views. The dependency-ordered MRL task ledger is [`specs/mesc-research-loop-v1/tasks.md`](specs/mesc-research-loop-v1/tasks.md), but a checkbox alone is not closeout evidence.

## Legacy T-phase map (Horizon 1)

The T0–T7 vocabulary predates the larger governed MRL implementation now present in the repository. The table below therefore distinguishes **implemented surfaces** from **phase completion** instead of treating module existence as proof that a research phase is complete.

| Phase | Title | Current repository truth | Depends on |
|---|---|---|---|
| **T0** | Repository & engineering foundation | ✅ complete | — |
| **T1** | Literature database & evidence foundation | 🟡 infrastructure implemented; Mission Zero screening/snapshot completion remains evidence-governed and is not asserted here | T0 |
| **T2** | `fhirkit`: validation + grammar | 🟡 validation boundary implemented; grammar-constrained generation objective remains open | T0, local validator/runtime requirements where applicable |
| **T3** | MedScale-Bench | 🟡 benchmark contracts, engine, scoring, artifacts, and replay surfaces implemented; full research-phase completion is not asserted here | T2 research gates |
| **T4** | Base-model landscape + constrained-decoding experiments | 🟡 model/runtime contracts and governed implementation surfaces exist; experiment eligibility/results require their own canonical evidence | T2, T3 |
| **T5** | Training-data pipeline | 🟡 governed training contracts/infrastructure exist; training execution is separately authorized and evidence-bound | T3 |
| **T6** | MESC-v0 adapter | 🟡 model/training infrastructure exists; adapter promotion/completion is not inferred from code presence | T4, T5 |
| **T7** | Honest evaluation + model card | 🟡 evaluation/governance infrastructure exists; final evaluation/publication completion remains separately gated | T3, T6 |

The original Horizon 1 success criterion remains directional: a reproducible benchmark outcome plus an honestly reported adapter or null result. No such result is asserted merely by this roadmap.

### Founder's engineering-phase vocabulary → T-phases

| Directive phase | T-phase(s) | Current truth |
|---|---|---|
| Phase 1 — core identifiers, hashing, provenance, reproducibility | T0 | implemented across reproducibility/provenance and later governed research infrastructure |
| Phase 2 — `medscale.litdb` | T1 | literature database, screening, review, integrity, and collaboration surfaces implemented; remaining human/evidence gates are separate |
| Phase 3 — `medscale.evidence` | T1/evidence spine | schema, storage, grading, checks, and identity governance implemented |
| Phase 4 — MedScale-Bench | T3 | executable deterministic benchmark surfaces exist; research completion is separately evidenced |
| Phase 5 — AI infrastructure | T4–T7 | ModelKit/backends plus governed MESC runtime/training/evaluation infrastructure exist; execution and promotion authority remain separately gated |

Language policy remains [ADR-0013](docs/adr/0013-language-strategy.md) (Python-first; Rust/Go role-gated by evidenced triggers).

## Horizons

- **Horizon 1 — Foundations (2026–2027) · committed.** Legacy T-phase goals are partially implemented through more granular canonical work; open objectives and evidence gates remain as shown above.
- **Horizon 2 — Breadth & rigor (2027–2029) · directional.** More FHIR resources/profiles, terminology grounding under licence, and broader benchmark work.
- **Horizon 3 — Platform (2029–2032) · directional.** Community-used open benchmark/toolkit and reproducibility infrastructure others can run.
- **Horizon 4 — Ambition, gated on evidence (2032–2036) · aspirational.** Broader verified clinical reasoning and interoperability where evidence justifies it.

> Horizon definitions follow the Research Vision. Where older condensed presentations differ, the **Research Vision and current canonical governance govern**.


## Ratified clinical workspace scope reconciliation

Issue #459 reconciled the Founder-directed target for MedScale to grow beyond its prior research-only product boundary toward a privacy-first, local-first clinical workspace. ADR-0038 is now canonically effective; implementation remains separately task-gated.

The Founder-ratified architecture and planning package are:

- [ADR-0038 — local clinical workspace boundary](docs/adr/0038-local-clinical-workspace-boundary.md) — **Accepted by Founder under R6; canonically effective after PR #460 protected merge and fresh-main qualification**;
- [Clinical Workspace V1 master specification](specs/medscale-clinical-workspace-v1/README.md);
- [capability map](specs/medscale-clinical-workspace-v1/capability_map.md);
- [data security and threat model](specs/medscale-clinical-workspace-v1/data_security.md);
- [migration, compatibility, and recovery contract](specs/medscale-clinical-workspace-v1/migration_recovery.md);
- [dependency-ordered task ledger](specs/medscale-clinical-workspace-v1/tasks.md);
- [2026-09-20 source refresh](docs/architecture/clinical_workspace_source_refresh_2026-09-20.md).

The architectural recommendation is one MedScale public project with two mechanically isolated trust domains: the existing synthetic-only **Research Core** and a future local **Clinical Workspace**. The Research Core may publish versioned interfaces outward; patient/workspace state must not flow back into Research Core training, evaluation, benchmarks, or MRL evidence.

ADR-0038 is canonically effective after PR #460 protected merge and fresh-main qualification. CW-000 and CW-001 are closed canonically. CW-002 is eligible but not activated: its own contract requires a ratified storage/key implementation ADR and separate activation before implementation begins. PHI ingestion, clinical production use, EHR writes, Workspace-data training/evaluation, model/runtime execution, publication, paid compute, and new MRL Stage-4 attempts remain separately governed.


## Current execution boundary

Do not infer the next executable task from this roadmap. Determine it from canonical `main`, the applicable specification/task ledger, declared dependencies, machine eligibility where required, exact-head verification evidence, and any mandatory independent review. Human screening, external data access, model/GPU execution, training, promotion, publication, and release remain evidence- or authority-dependent even when supporting code already exists.
