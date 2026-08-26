# MESC Research Loop V1

Status: **STRATEGY / PLANNING ONLY / NOT EXECUTION AUTHORITY**

Canonical planning base:

```text
BASE_MAIN_SHA = 9f7e8db2b47bad0e497edacfb00b749c4940a0c8
TRAINING_EXECUTION = NOT_AUTHORIZED_BY_THIS_PACKAGE
REAL_MODEL_OR_DATA_ACCESS = NOT_AUTHORIZED_BY_THIS_PACKAGE
AUTONOMOUS_GPU_EXPERIMENTATION = NOT_AUTHORIZED_BY_THIS_PACKAGE
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
  -> promotion gate
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
- MCRL.

MRL sits above experiment execution and below canonical scientific promotion.

MCRL remains the patient/task-time clinical state, evidence, verification,
uncertainty, tool, and recovery layer. MRL is a separate research-time layer for
hypotheses, experiments, scientific decisions, research memory, and procedure
admission. Patient/product/PHI data must never become an MRL learning signal under
current governance.

## Core principles

1. **The researcher may modify the experiment; it may never modify the ruler.**
   Frozen evaluators, sealed evaluation data, promotion rules, trust registries,
   authorization code, governance, and canonical experiment history are outside the
   autonomous mutation surface.
2. **Search feedback is not final evidence.** Repeated adaptive experimentation must
   use separate search, replication, sealed promotion, and external/clinician assurance
   tiers.
3. **Safety gates dominate aggregate optimization.** No scalar score may hide a
   material regression in safety, harmful overconfidence, abstention, evidence fidelity,
   critical subgroups, contamination, or reproducibility.
4. **Research memory is admitted, not merely accumulated.** A repeated successful
   workflow becomes a reusable `ResearchProcedure` only after replay, transfer testing,
   failure controls, and review.
5. **Failures remain first-class artifacts.** Rejected, invalid, null, unsafe, and
   non-reproducible experiments stay in the campaign graph so the system does not pay
   repeatedly for the same known failure.
6. **No silent authority expansion.** This package defines a future research substrate;
   it grants no model access, dataset access, GPU use, training, retrieval, provider,
   credential, or release authority.

## Planning package

This directory contains:

- `research.md` — external research synthesis and adoption decisions;
- `spec.md` — normative proposed requirements and invariants;
- `plan.md` — dependency-ordered implementation program;
- `tasks.md` — concrete followable task ledger.

## Current recommendation

Do not begin with an autonomous GPU agent.

First build and validate the typed research artifacts, immutable evaluator boundary,
adaptive-evaluation hierarchy, fixture-only closed loop, and research-memory admission
mechanism. Only after those layers are independently qualified should a separately
authorized real experiment runner be attached.
