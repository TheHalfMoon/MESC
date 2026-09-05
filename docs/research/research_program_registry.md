# MedScale / MESC Research Program Registry

- **Status:** Canonical registry candidate for MRL-0
- **Date:** 2026-09-05
- **Related:** `research_questions.md`, ADR-0035, ADR-0036, MESC strategy documents, MRL V1

## Purpose

Preserve the foundational `RQ1` through `RQ7` identifiers while giving later research
programs collision-free namespaces and explicit status. This registry is an identity and
traceability contract. It does not turn strategy prose into scientific evidence and does
not authorize model/data/runtime/training activity.

## Registry rules

1. The exact bare identifiers `RQ1` through `RQ7` are permanently reserved for the
   foundational questions in `research_questions.md`.
2. Their existing statements, falsification conditions, test artifacts, and statuses are
   not renamed or rewritten by this registry.
3. Every later canonical research question must use one registered prefix.
4. A strategy document, roadmap item, milestone, or product capability is not a canonical
   research question until a question record is explicitly accepted with:
   - a unique namespaced identifier;
   - a falsifiable statement;
   - a test/evidence artifact;
   - a falsification or null-result condition;
   - an explicit status;
   - a canonical source path.
5. Namespace reservation does not grant implementation, execution, training, evaluation,
   model-access, data-access, promotion, deployment, or release authority.
6. Duplicate identifiers or reuse of the same identifier for materially different
   questions are prohibited.
7. Superseded questions retain their historical identifier and disposition; identifiers
   are never recycled.

## Foundational questions — preserved exactly

| ID | Canonical source | Status |
|---|---|---|
| `RQ1` | `docs/research/research_questions.md` | OPEN |
| `RQ2` | `docs/research/research_questions.md` | OPEN — depends on RQ1 result first |
| `RQ3` | `docs/research/research_questions.md` | OPEN |
| `RQ4` | `docs/research/research_questions.md` | OPEN |
| `RQ5` | `docs/research/research_questions.md` | OPEN |
| `RQ6` | `docs/research/research_questions.md` | OPEN |
| `RQ7` | `docs/research/research_questions.md` | OPEN — Horizon 2 |

The table above is an index only. `research_questions.md` remains the normative source for
the full question text and falsification semantics.

## Later-program namespaces

| Program | Reserved question namespace | Current program status | Current canonical/strategy source | Question-catalog status |
|---|---|---|---|---|
| Cross-cutting MESC research | `MESC-RQ-<NNNN>` | PERFORMANCE-FIRST ACTIVE STRATEGY | `docs/adr/0036-performance-first-health-model-strategy.md`, `docs/strategy/mesc_health_model_program_2026-09-05.md`, `docs/strategy/mesc_frontier_program_2026-08-18.md` | RESERVED — individual questions require separate canonicalization |
| MESC Capability Realization Layer | `MCRL-RQ-<NNNN>` | FOUNDER-DIRECTED STRATEGY DRAFT | `docs/strategy/mesc_capability_realization_layer_2026-08-18.md` | RESERVED — individual questions require separate canonicalization |
| English + Arabic medical intelligence | `ARABIC-RQ-<NNNN>` | PERFORMANCE-FIRST MESC PROGRAM | `docs/strategy/mesc_health_model_program_2026-09-05.md` | RESERVED — individual questions require separate canonicalization |
| AMGE medical visual intelligence | `AMGE-RQ-<NNNN>` | PERFORMANCE-FIRST MESC PROGRAM | `docs/strategy/mesc_health_model_program_2026-09-05.md` | RESERVED — individual questions require separate canonicalization |
| Medical Omni | `OMNI-RQ-<NNNN>` | PERFORMANCE-FIRST MESC PROGRAM | `docs/strategy/mesc_health_model_program_2026-09-05.md` | RESERVED — individual questions require separate canonicalization |
| MESC Research Loop | `MRL-RQ-<NNNN>` | GOVERNED PROGRAM — MRL V1 | `specs/mesc-research-loop-v1/` | RESERVED — individual meta-research questions require separate canonicalization |

`<NNNN>` is four decimal digits starting at `0001` within each namespace. A namespace may
remain reserved with no accepted question records; reservation prevents future collisions
without fabricating scientific questions that the source documents do not yet define.

## Traceability policy

### Scientific claims

A task that is intended to answer, support, refute, or publish a scientific claim must
trace to at least one canonical question record. Until a later program has accepted
namespaced question records, its strategy text is not a substitute for a falsifiable
question.

### Governance and infrastructure work

Governance, security, reproducibility, schema, CI, and infrastructure work may instead
trace to an accepted ADR/specification/task gate when the work does not itself claim a
scientific result. This reconciles the historical "every ticket traces to a research
question" rule with later governance programs without pretending that an infrastructure
task is a scientific experiment.

Any work that produces a scientific conclusion must return to canonical question
traceability before that conclusion can be treated as research evidence.

## Status vocabulary for future question records

Canonical namespaced question records must use one of:

```text
PROPOSED
OPEN
BLOCKED
IN_PROGRESS
SUPPORTED
NULL_RESULT
FALSIFIED
INCONCLUSIVE
SUPERSEDED
```

`SUPPORTED` is not permanent truth. It means the currently accepted evidence supports the
question's hypothesis under its stated scope. New evidence may change the disposition.

## Adding a namespaced question

A later change must add a record containing at least:

```text
question_id
program
statement
why_it_matters
test_artifacts
falsified_or_null_if
status
canonical_source_path
```

The change must preserve the immutable identity of all prior records and pass the
applicable repository governance/review gates.

## Authority boundary

This registry grants no model, dataset, provider, credential, network, GPU, inference,
training, promotion, deployment, clinical-action, or release authority. It is a
traceability registry only.