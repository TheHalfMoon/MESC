# Execution

- **Status:** Active repository execution index (`medscale` package version v0.2.0)

This directory contains MedScale execution and phase-planning documents. It is not an authority source by itself: eligibility and completion come from canonical specifications, governance, exact gate evidence, and accepted decisions on canonical `main`.

The original T0–T7 phase vocabulary remains useful as historical planning context, but the repository now contains more granular governed MESC/MRL work. Module existence must not be read as proof that a legacy research phase is complete.

## Current phase map

- **T0 — Repository foundation:** foundation complete.
- **T1 — Literature database & evidence:** implementation surfaces exist across `medscale.litdb`, evidence, screening/review, integrity, and collaboration. Human Mission Zero screening/snapshot completion remains separately evidence-governed.
- **T2 — FHIR toolkit:** `medscale.fhirkit` validation/report/storage surfaces exist. Grammar-constrained generation remains open and is not claimed as complete here.
- **T3 — MedScale-Bench:** deterministic benchmark contracts, engine, scoring, artifacts, and replay surfaces exist. Full research-phase completion is not inferred from those surfaces.
- **T4–T7 — Model/training/evaluation work:** governed implementation infrastructure exists in the repository, but execution, promotion, training, evaluation conclusions, and publication remain subject to their own canonical gates.

For current task ordering, consult the applicable canonical specification/task ledger rather than this summary.

## Legacy T1 search and screening artifacts

| Document | Purpose | Status |
|---|---|---|
| [`search_strategy.md`](search_strategy.md) | Per-source queries, PRISMA workflow, and reproducible ingestion design | Authored |
| `benchmark_spec.md` | Legacy proposed T3 task/metric document | Not the current benchmark authority; use canonical benchmark/MESC specs |
| `constrained_decoding_hypothesis.md` | Legacy proposed T2 form-vs-content experiment design | Not present; grammar work remains separately gated |

### Screening the corpus (`medscale screen`)

Human title/abstract screening turns the deduplicated corpus into evidence records under an append-only audit trail. No model becomes the decision-maker of record.

```text
uv run medscale screen status
uv run medscale screen duplicates --reviewer <you>
uv run medscale screen next --reviewer <you>
uv run medscale screen resume --reviewer <you>
uv run medscale screen next --query Q2 --limit 50
```

Legacy ordering remains: resolve uncertain duplicate groups before title/abstract screening where the applicable screening protocol requires it. Corrections are append-only events; history is not rewritten.

> This directory does not authorize starting a phase, running external data acquisition, using PHI, executing models/GPUs, training, promotion, publication, or release. Those actions require the applicable canonical authority and evidence.
