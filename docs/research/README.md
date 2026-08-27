# Research

- **Status:** Index
- **Date:** 2026-08-27

The scientific core of MedScale. Scientific claims trace to canonical research questions;
governance and infrastructure work follows the program/ADR traceability rules in the
research-program registry.

## Documents

| Document | Purpose |
|---|---|
| [research_questions.md](research_questions.md) | RQ1–RQ7: the foundational falsifiable questions MedScale exists to answer, each with a test artifact and falsification condition. |
| [research_program_registry.md](research_program_registry.md) | Preserves RQ1–RQ7 and reserves explicit namespaces/status for later MESC, MCRL, Arabic, AMGE, Omni, and MRL research programs. |
| [paper_taxonomy.md](paper_taxonomy.md) | The classification scheme for the literature database (litdb, T1). |
| [reproducibility_policy.md](reproducibility_policy.md) | The 10 operational principles that turn the rules R1–R7 into per-artifact requirements. |

## Referenced but not yet authored (planned)

These are cited by the documents above and will be created in their phase:

| Document | Phase | Purpose |
|---|---|---|
| [`../execution/search_strategy.md`](../execution/search_strategy.md) | T1 | ✅ Authored — per-source queries and PRISMA thresholds. |
| `failure_taxonomy.md` | T3 | The five-class FHIR error taxonomy (RQ4). |
| `../execution/constrained_decoding_hypothesis.md` | T2 | The form-vs-content 2×2 experiment design (RQ1). |
| `../execution/benchmark_spec.md` | T3 | MedScale-Bench task and metric definitions. |

## The seven questions at a glance

| RQ | Question | Primary phases |
|---|---|---|
| RQ1 | Does grammar decouple form from content? | T2, T4 |
| RQ2 | Marginal value of fine-tuning over a constrained base? | T6, T7 |
| RQ3 | Is the validator a perfect, scalable teacher? | T5, T3, T7 |
| RQ4 | Do FHIR errors decompose cleanly; does per-class sampling help? | T3, T5, T7 |
| RQ5 | Can we measure/reduce extraction hallucination without an LLM judge? | T7 |
| RQ6 | Does competence transfer across resource types/profiles? | T3, T5, T7 |
| RQ7 | Can terminology be grounded under licence constraints? | T2, Horizon 2 |
