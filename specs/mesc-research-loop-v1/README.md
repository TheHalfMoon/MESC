# MESC Research Loop V1

Status: **CANONICAL PLANNING / MRL-0 QUALIFYING / NOT EXECUTION AUTHORITY**

Canonical planning acceptance and current MRL-0 qualification base:

```text
MRL_PLANNING_ACCEPTANCE_MERGE_SHA = 74a800447ff251fa70027e0590ba2150c1e70e65
MRL_PLANNING_ACCEPTANCE_TREE = 0507920e5e6d62d73484f558451a871a7dc52bcc
MRL_0_QUALIFICATION_BASE_SHA = 74a800447ff251fa70027e0590ba2150c1e70e65
MRL_0_EXACT_HEAD = RESOLVED_EXTERNALLY_BY_MRL_0099_PR_AND_CHECK_EVIDENCE
TRAINING_EXECUTION = NOT_AUTHORIZED_BY_THIS PROGRAM
REAL_MODEL_OR_DATA_ACCESS = NOT_AUTHORIZED_BY_THIS PROGRAM
AUTONOMOUS_GPU_EXPERIMENTATION = NOT_AUTHORIZED_BY_THIS PROGRAM
MODEL_PROMOTION = NOT_OWNED_BY_MRL_V1
```

The planning-acceptance SHA/tree above identify the already-canonical MRL V1 planning
package and the base from which the current MRL-0 governance change started. They are **not**
the identity of the MRL-0 package under review.

The MRL-0 exact candidate head is intentionally not embedded in this file because adding a
commit identity to bytes that are themselves committed would immediately create a new head
and make the embedded value stale. `MRL-0099` therefore binds the final exact head through
immutable PR/check/review evidence outside the candidate's semantic bytes. Before Ready and
again before merge, live GitHub truth must prove that the reviewed/check-qualified head is
the current PR head and contains the complete MRL-0 package. A head mutation invalidates all
prior exact-head qualification evidence.

## Purpose

MESC already has strong foundations for reproducible research: explicit research
questions, deterministic experiment manifests, content-addressed artifacts,
contamination controls, negative-result policy, fail-closed authorization boundaries,
a frozen Backbone Tournament protocol, a broad MESC-Eval strategy, and the proposed
MCRL clinical capability-realization layer.

MRL connects:

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

The intended end state is **governed self-improving research**, not uncontrolled
self-modifying training.

## Relationship to existing MESC components

MRL does not replace:

- `medscale.modelkit.manifests.ExperimentManifest`;
- the MESC reproducibility policy;
- foundational research questions;
- Backbone Tournament contracts;
- training-readiness / launch / execution gates;
- MESC-Eval;
- MCRL;
- future model-promotion governance.

MRL stops at research evidence. ADR-0033 explicitly defers model-promotion ownership and
evidence to a later dedicated ADR, so MRL V1 must not create `PromotionDecision`,
`PROMOTED`, or equivalent promotion authority under another name.

MCRL remains the patient/task-time clinical state, evidence, verification, uncertainty,
tool, and recovery layer. MRL is a separate research-time layer for hypotheses,
experiments, scientific decisions, research memory, and procedure admission.
PHI, patient/product telemetry, and clinical-runtime state are not MRL learning signals
under current governance.

## Core principles

1. **The researcher may modify the experiment; it may never modify the ruler.** Frozen
   evaluators, sealed evaluation data, governance, trust registries, authorization,
   canonical history, and future promotion authority are outside the autonomous mutation
   surface.
2. **Search feedback is not final evidence.** Development, search, replication, sealed
   evaluation, and external/clinician assurance are distinct tiers with frozen
   query/result-exposure budgets.
3. **Safety gates dominate aggregate optimization.** No scalar score may hide a material
   regression in safety, harmful overconfidence, abstention, evidence fidelity, critical
   subgroups, contamination, or reproducibility.
4. **Research memory is admitted, not merely accumulated.** Reusable procedures require
   replay, representative transfer testing, negative controls, typed applicability limits,
   and independent review.
5. **Failures remain first-class artifacts.** Rejected, invalid, null, unsafe, and
   non-reproducible experiments remain in canonical campaign history.
6. **Content identity is non-self-referential.** `content_sha256` is derived from canonical
   semantic bytes and is excluded from its own preimage.
7. **No silent authority expansion.** MRL grants no model access, dataset access, GPU use,
   training, provider/credential access, promotion, deployment, or release authority.
8. **Derived state cannot self-authorize.** Machine-readable project-state projections are
   deterministic, exact-source-bound views; stale or manually altered projections fail
   closed.

## Canonical planning package

- `research.md` — external research synthesis and adoption decisions;
- `spec.md` — normative requirements and invariants;
- `plan.md` — dependency-ordered implementation program;
- `tasks.md` — concrete task ledger.

## MRL-0 constitution candidate

MRL-0001 through MRL-0008 are implemented as a governance candidate on the active
MRL-0 branch through:

- `docs/adr/0035-mrl-governance-constitution.md` — MRL/MCRL boundary, immutable evaluator
  rule, adaptive tiers, evidence floors, resource/query governance, promotion deferral,
  and research-input admission;
- `docs/research/research_program_registry.md` — preserves foundational `RQ1..RQ7` and
  reserves explicit MESC/MCRL/Arabic/AMGE/Omni/MRL namespaces without fabricating new
  scientific questions;
- `project-state-contract.md` — precedence, deterministic serialization, source binding,
  identity uniqueness, mandatory admission validation, and anti-staleness rules;
- `project-state-v1.schema.json` — closed machine-readable shape requiring
  `DERIVED_NON_AUTHORITATIVE` and `can_authorize=false`;
- `docs/research/README.md` — index/traceability reconciliation.

Candidate deliverables are **QUALIFYING**, not `CLOSED_CANONICAL`. `MRL-0099` remains open
until the exact final head passes repository checks and independent governance review.
No later MRL task may treat this branch state as `MRL_CONSTITUTION_FROZEN` before that
canonical gate closes.

## Current sequencing

Do not begin with an autonomous GPU agent.

First close `MRL-0099`. Only after `MRL_CONSTITUTION_FROZEN` is canonically proven does
MRL-0100 become eligible, beginning the typed artifact core. Real model, corpus, network,
GPU, provider, inference, training, and promotion work remain outside this MRL-0 package
and require their own later gates.