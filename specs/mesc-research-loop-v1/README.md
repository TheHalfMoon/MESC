# MESC Research Loop V1

Status: **STRATEGY / PLANNING ONLY / NOT EXECUTION AUTHORITY**

Canonical planning base:

```text
BASE_MAIN_SHA = 89d5edf0035c7b659d20dd861ec501d7fef0d192
TRAINING_EXECUTION = NOT_AUTHORIZED_BY_THIS_PACKAGE
REAL_MODEL_OR_DATA_ACCESS = NOT_AUTHORIZED_BY_THIS_PACKAGE
AUTONOMOUS_GPU_EXPERIMENTATION = NOT_AUTHORIZED_BY_THIS_PACKAGE
MODEL_PROMOTION = NOT_OWNED_BY_MRL_V1
```

## Purpose

MESC already has unusually strong foundations for reproducible research: explicit
research questions, deterministic experiment manifests, content-addressed artifacts,
contamination controls, negative-result policy, fail-closed authorization boundaries,
a frozen Backbone Tournament protocol, a broad MESC-Eval strategy, and the proposed
MCRL clinical capability-realization layer.

The remaining strategic gap is not experiment recording. It is the absence of a
canonical research-time layer that connects:

```text
research objective
  -> hypothesis
  -> bounded experiment plan
  -> existing ExperimentManifest
  -> observed result
  -> statistical/safety decision
  -> replication or rejection
  -> next hypothesis
  -> reusable validated research procedure
  -> sealed evaluation evidence
  -> non-authoritative evidence candidate
```

`MESC Research Loop (MRL)` is the proposed layer for that gap.

## Design thesis

MESC should learn how to conduct better research over time without allowing the
research agent to corrupt the scientific method used to judge its work.

The intended end state is **governed self-improving research**, not uncontrolled
self-modifying training.

## Relationship to existing MESC components

MRL does not replace:

- `medscale.modelkit.manifests.ExperimentManifest`;
- the MESC reproducibility policy;
- existing research questions;
- Backbone Tournament contracts;
- training-readiness / launch / execution gates;
- MESC-Eval;
- MCRL;
- future model-promotion governance.

MRL stops at research evidence. Canonical ADR-0033 explicitly defers model-promotion
ownership and evidence to a later dedicated ADR, so MRL V1 must not create
`PromotionDecision`, `PROMOTED`, or an equivalent promotion authority under another
name.

MCRL remains the patient/task-time clinical state, evidence, verification, uncertainty,
tool, and recovery layer. MRL is a separate research-time layer for hypotheses,
experiments, scientific decisions, research memory, and procedure admission.
Patient/product/PHI data and clinical-runtime state must never become an MRL learning
signal under current governance.

## Core principles

1. **The researcher may modify the experiment; it may never modify the ruler.**
   Frozen evaluators, sealed evaluation data, governance, trust registries,
   authorization code, canonical history, and future promotion authority are outside the
   autonomous mutation surface.
2. **Search feedback is not final evidence.** Repeated adaptive experimentation uses
   separate search, replication, sealed evaluation, and external/clinician assurance
   tiers with frozen query/result-exposure budgets.
3. **Safety gates dominate aggregate optimization.** No scalar score may hide a material
   regression in safety, harmful overconfidence, abstention, evidence fidelity, critical
   subgroups, contamination, or reproducibility.
4. **Research memory is admitted, not merely accumulated.** A repeated successful
   workflow becomes a reusable `ResearchProcedure` only after replay, representative
   transfer testing, failure controls, typed applicability limits, and independent review.
5. **Failures remain first-class artifacts.** Rejected, invalid, null, unsafe, and
   non-reproducible experiments stay in the campaign graph so the system does not pay
   repeatedly for the same known failure.
6. **Content identity is non-self-referential.** `content_sha256` is derived from
   canonical semantic bytes and is excluded from its own hash preimage.
7. **No silent authority expansion.** This package grants no model access, dataset
   access, GPU use, training, retrieval, provider, credential, promotion, or release
   authority.
8. **Derived state cannot self-authorize.** Machine-readable project-state projections
   are deterministic views bound to exact repository/source identities; stale or manually
   altered projections fail closed.

## Planning package

This directory contains:

- `research.md` — external research synthesis and adoption decisions;
- `spec.md` — normative proposed requirements and invariants;
- `plan.md` — dependency-ordered implementation program;
- `tasks.md` — concrete followable task ledger.

## Current recommendation

Do not begin with an autonomous GPU agent.

First build and validate the canonical artifact/hash contract, typed research-input
admission boundary, immutable evaluator boundary, adaptive-evaluation hierarchy,
fixture-only closed loop, independently reviewed research-memory admission,
contamination/lineage gate, and anti-stale machine-state projections. Only after those
layers are independently qualified should a separately authorized real experiment runner
be considered. Model promotion remains outside MRL V1 until the dedicated ADR required
by ADR-0033 is separately accepted.
