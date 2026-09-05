# MESC Backbone Tournament — Current Status and Supersession Boundary

- **Date:** 2026-09-05
- **Status:** HISTORICAL PROGRAM / NOT A CURRENT EXECUTION AUTHORITY
- **Current strategy:** `docs/adr/0036-performance-first-health-model-strategy.md`
- **Current implementation map:** `docs/strategy/mesc_health_model_program_2026-09-05.md`
- **Current execution governance:** `specs/mesc-research-loop-v1/`

## Purpose

The `specs/mesc-backbone-tournament/` tree contains a large historical chain of readiness,
authorization-candidate, fixture, implementation, repair, and evidence-governance artifacts.
Those artifacts must remain preserved because they record the exact assumptions and bounds
of their time.

They are **not** the current model-selection authority for future MESC training.

## Superseded future-facing assumptions

Once ADR-0036 is canonically merged, the following future-facing assumptions found in the
historical tournament tree are superseded and must not be revived as current policy:

- selecting separate public `MESC-Compact` and `MESC-Reasoner / Flagship` identities;
- optimizing model size/deployability ahead of maximum validated health-model quality;
- the original fixed design-time roster of `gpt-oss-20b`, Apertus 1.5 8B,
  Phi-4 Multimodal, and MedGemma 1.5 4B;
- the blanket exclusion of Chinese model families from future core candidacy;
- any implication that historical readiness evidence qualifies a newly selected model,
  revision, tokenizer/processor, runtime, dataset, evaluator, teacher, or training plan.

Historical statements remain true descriptions of the governance that applied to those
historical artifacts. Supersession is forward-looking and does not rewrite their audit
meaning.

## Current foundation-selection rule

The current preferred foundation candidate is recorded in ADR-0036 and the 2026-09-05 MESC
Health Model Program. As of that strategy package the preferred candidate is:

```text
Qwen/Qwen3.8-27B
```

That value is a **strategy candidate only**. It is intentionally refreshable immediately
before real preflight because model releases, licenses, runtime support, and evidence can
change.

No future model becomes an executable MESC foundation through this file or any historical
Backbone Tournament artifact.

## Required path for any future real foundation experiment

A future real foundation experiment must use the canonical MRL real-preflight path and
produce genuine evidence for the applicable tasks, including:

```text
MRL-0801  exact model/weights identity
MRL-0802  corpus rights and exact identity
MRL-0803  contamination and held-out isolation
MRL-0804  runtime/GPU qualification
MRL-0805  applicable training authorization
MRL-0806  frozen objective and budgets
MRL-0807  evaluator and sealed Tier 3 identities
MRL-0808  execution sandbox
MRL-0809  exact-head preflight qualification
MRL-0899  MRL_REAL_EXPERIMENT_READY decision
```

Historical tournament readiness, fixture execution, repair evidence, or founder candidates
cannot be reused as evidence for a different model/revision/runtime/objective unless a
current canonical contract explicitly proves that reuse valid. Default disposition is
non-reusable.

## Current naming rule

The public model identity is:

```text
MESC
```

Parameter count, generation, modality coverage, foundation lineage, training stage, and
quantization remain transparent metadata. They are not separate public model identities by
default.

## Current admission rule

Model candidacy is evidence-based, not country-based. Every candidate must independently
pass applicable checks for:

- exact immutable identity;
- license, naming, redistribution, and derivative compatibility;
- provenance and contamination risk;
- security and remote-code posture;
- runtime feasibility;
- health-domain quality and safety;
- reproducibility;
- current MRL/training governance.

Passing candidacy review grants no model access, inference, training, promotion, release,
or deployment authority.

## Preservation rule

Do not delete, rewrite, or relabel historical tournament artifacts merely because the
strategy changed. When historical text conflicts with ADR-0036 on **future strategy**, the
newer accepted ADR controls. When reconstructing a **historical decision**, the exact
historical artifact and its contemporaneous governance remain the evidence source.