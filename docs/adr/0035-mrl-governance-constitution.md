# ADR-0035 — Freeze the MESC Research Loop governance constitution

- **Status:** Accepted by Founder for MRL-0 governance; effective only if this exact package is canonically merged
- **Date:** 2026-08-27
- **Deciders:** Founder
- **Supersedes:** None
- **Superseded by:** None
- **Related:** ADR-0033, `docs/strategy/mesc_capability_realization_layer_2026-08-18.md`, `specs/mesc-research-loop-v1/`

## Context

The MESC Research Loop (MRL) planning package is now canonical. Before any autonomous
research loop or typed research artifact core is implemented, MRL-0 requires the
research-time authority boundary to be frozen so later code cannot silently expand what
an agent may learn from, mutate, evaluate, or authorize.

MCRL is a separate clinical/task-time capability-realization layer. ADR-0033 remains
controlling for model-promotion ownership and explicitly defers `PromotionDecision`,
`PROMOTED`, model-lineage, training-artifact, deployment, and related authority schemas
to later dedicated governance.

This ADR freezes MRL-0001, MRL-0002, MRL-0003, MRL-0004, MRL-0005, and MRL-0008 and
binds the companion research-program registry and project-state contract required by
MRL-0006 and MRL-0007.

## Decision

### 1. MRL and MCRL are different authority domains

MRL is the **research-time** layer for research objectives, hypotheses, bounded
experiment plans, experiment receipts, scientific decisions, campaign history,
replication, research procedures, and research-memory admission.

MCRL is the **clinical/task-time** layer for patient/task state, evidence carryover,
verification, uncertainty, tool use, recovery, and clinical-task completion.

The boundary is fail-closed:

- PHI, product telemetry, and clinical-runtime state are not MRL learning inputs;
- MCRL state, traces, patient invariants, tool traces, and recovery state cannot be
  imported into MRL observation, campaign history, procedure extraction, or search
  indexes as learning signals;
- a separately authorized MCRL output may be consumed only as external evaluation
  evidence when the applicable governance explicitly permits it;
- consuming external evaluation evidence does not grant MRL authority over the source
  clinical/runtime system;
- no MRL artifact may become a clinical assertion, clinical action, or MCRL state update
  merely because it exists in canonical research history.

### 2. Active evaluators and authority-bearing controls are immutable to the campaign agent

An MRL campaign agent has no write authority over the active scientific ruler or the
systems that confer authority. During an active campaign it cannot alter, replace,
weaken, shadow, or rebind:

- active evaluator code, evaluator identities, scoring rules, metric definitions, or
  hard-gate thresholds;
- sealed Tier 3 data, gold labels, item identities, or release conditions;
- governance documents, authorization records, founder/operator decisions, or CI/security
  qualification gates;
- trust registries, licensing decisions, credential policy, provider policy, or network
  policy;
- canonical Git history or accepted evidence records;
- the machine-readable project-state projection or the canonical sources from which that
  projection is derived;
- future model-promotion authority, deployment authority, or release authority.

A proposed change to any protected surface is a new governed change outside the active
campaign. It cannot retroactively modify the ruler used to judge prior or current work.

### 3. Adaptive evaluation uses five distinct tiers

The tiers are semantically different and may not be collapsed into a single result
stream:

| Tier | Name | Purpose | Agent-visible result policy |
|---|---|---|---|
| 0 | Development | deterministic fixtures, unit tests, local contract checks | detailed fixture/debug evidence permitted within the frozen development surface |
| 1 | Search | bounded adaptive experiment selection | only the frozen aggregate/result fields allowed by the objective contract; query and exposure budgets apply |
| 2 | Replication | independent confirmation of retained leads | narrower frozen aggregate summaries; separate query/exposure accounting; no search-surface item leakage |
| 3 | Sealed evaluation | independent evidence on quarantined evaluation material | no item-level search access and no iterative agent-consumable result stream; emits sealed evidence for an independent consumer |
| 4 | External / clinician assurance | independently governed external, expert, or clinical assurance | outside campaign-agent control; evidence and authority are governed separately |

Tier identity, evaluator identity, allowed result fields, query ceilings, and exposure
ceilings are frozen before the applicable work begins. Tier 3 is evidence, not a
promotion decision.

### 4. Evidence floors dominate optimization and promotion remains deferred

MRL scientific comparison is ordered as follows:

1. validity and reproducibility requirements;
2. contamination and lineage requirements;
3. medical safety and harmful-overconfidence floors;
4. abstention, evidence-fidelity, and critical-subgroup non-regression floors;
5. only after all applicable hard floors pass: capability, latency, compute, token,
   storage, and monetary-cost optimization.

An aggregate gain cannot compensate for a failed hard floor.

MRL V1 `ResearchDecision` is restricted to:

```text
INVALID
REJECT
REPLICATE
RETAIN_LEAD
EVIDENCE_CANDIDATE
BLOCKED
```

`EVIDENCE_CANDIDATE` is non-authoritative research evidence. MRL V1 cannot construct,
encode, alias, or imply `PROMOTED`, `PromotionDecision`, or an equivalent terminal
model-promotion authority. ADR-0033 remains controlling until a separately accepted
dedicated promotion-ownership/evidence ADR exists.

### 5. Campaign resources and adaptive exposure are frozen outside agent control

Before a bounded campaign starts, the objective contract must freeze all applicable
ceilings for:

- compute or accelerator consumption;
- wall-clock duration;
- generated/input token consumption where applicable;
- storage and artifact growth;
- monetary/provider cost where applicable;
- retry counts and known-failure retry ceilings;
- Tier 1 and Tier 2 query counts;
- result-exposure counts and the exact result fields that may be revealed;
- any separately governed evaluator invocation ceiling.

The campaign agent may consume but may not raise, reset, reinterpret, or transfer these
ceilings between tiers. Unknown accounting, counter rollback, ceiling exhaustion, or an
attempt to self-expand a ceiling yields `BLOCKED` for further use of the affected
resource/tier. Additional budget requires a new externally governed objective or campaign;
it is never an in-campaign self-amendment.

### 6. Research-program identity is namespaced without rewriting RQ1-RQ7

`docs/research/research_program_registry.md` is the reconciliation contract for
research-program identity.

The foundational `RQ1` through `RQ7` identifiers remain byte/name-stable and retain their
existing statements, falsification conditions, tests, and statuses. Later MESC, MCRL,
Arabic, AMGE, Omni, and MRL research questions must use their registered namespace.
Strategy prose does not become a canonical research question merely because it is
published in the repository.

### 7. Machine-readable project state is a non-authoritative deterministic projection

`specs/mesc-research-loop-v1/project-state-v1.schema.json` and
`specs/mesc-research-loop-v1/project-state-contract.md` define the MRL V1 projection
contract.

Canonical source documents and Git objects always outrank the projection. A projection:

- binds one exact repository commit and tree;
- records the exact source paths and source hashes used to derive it;
- is deterministically serialized;
- contains no wall-clock generation timestamp in its semantic bytes;
- declares `can_authorize = false`;
- fails closed as stale when the bound repository/source identities no longer match;
- cannot mark a task `CLOSED_CANONICAL` solely from its own prior state;
- cannot create execution, training, model/data access, promotion, release, or clinical
  authority.

Manual edits to a projection are non-authoritative and must be discarded/rebuilt from
canonical sources.

### 8. Research-input admission is explicit and fail-closed

MRL learning-input classes are:

**Admissible when otherwise authorized**

- canonical MRL research artifacts and receipts;
- deterministic fixture outputs produced inside an authorized MRL fixture surface;
- canonical negative/null/invalid research results;
- separately authorized external evaluation evidence, identified as external evidence
  rather than campaign learning state.

**Rejected as MRL learning signals under current governance**

- PHI;
- patient-level product data or product telemetry;
- MCRL clinical/task-time state;
- clinical-runtime traces, patient invariants, or action state;
- credentials, secrets, provider-control state, or hidden operational telemetry;
- sealed Tier 3 item-level content not explicitly released by its independent evaluator.

Unknown or ambiguously classified input is rejected until a separate governance decision
classifies it. An index, cache, embedding, summary, or transformed derivative does not
launder a rejected input into an admissible class.

## Consequences

**Positive**

- research-time and clinical/task-time feedback paths are structurally separated;
- an autonomous researcher cannot improve its score by rewriting the evaluator or its
  governance;
- adaptive optimization cannot silently consume an unlimited holdout;
- safety/reproducibility floors remain prior to aggregate optimization;
- MRL research evidence cannot silently become model-promotion authority;
- project-state automation can be added later without making a derived cache authoritative;
- later research programs gain collision-free identifiers while RQ1-RQ7 remain intact.

**Negative / costs**

- useful clinical/product traces cannot be recycled into research memory without new
  explicit governance;
- sealed evaluation gives the search process less debugging information by design;
- additional research budget requires an external decision rather than agent self-service;
- project-state tooling must reproduce exact source identities and deterministic bytes;
- future promotion, lineage, training, and deployment work still require separate ADRs.

## Alternatives considered

- **One combined MRL/MCRL memory plane.** Rejected because patient/task-time state would
  become an uncontrolled research-learning channel and would conflate clinical authority
  with research evidence.
- **Allow the agent to tune evaluators while it searches.** Rejected because the campaign
  could optimize the ruler rather than the underlying capability.
- **Expose Tier 3 results iteratively.** Rejected because sealed evaluation would become an
  adaptive search surface.
- **Use a single scalar objective.** Rejected because aggregate gains could hide medical,
  contamination, abstention, subgroup, or reproducibility regressions.
- **Allow automatic budget extension when results are promising.** Rejected because the
  agent would gain self-expanding resource and holdout authority.
- **Rename foundational RQ1-RQ7 into a new namespace.** Rejected because it would break
  historical traceability.
- **Treat generated project-state JSON as authoritative.** Rejected because stale or
  manually changed derived state could then manufacture eligibility.
- **Create a placeholder promotion schema now.** Rejected by ADR-0033 and by the MRL V1
  planning contract.

## Compliance

MRL-0 compliance is reviewed against:

- this ADR;
- `docs/research/research_program_registry.md`;
- `specs/mesc-research-loop-v1/project-state-contract.md`;
- `specs/mesc-research-loop-v1/project-state-v1.schema.json`;
- the canonical MRL V1 specification/plan/task ledger;
- ADR-0033 and the MCRL strategy boundary.

MRL-0099 requires exact-head repository checks and governance review before the
`MRL_CONSTITUTION_FROZEN` exit may be claimed.

## Authorization boundary

This ADR and MRL-0 authorize governance reconciliation only. They do not authorize:

- real model or corpus access;
- gated-term acceptance;
- provider credentials or network activation;
- GPU/accelerator execution;
- inference;
- training or fine-tuning;
- autonomous real experiments;
- PHI/product-data learning;
- model promotion;
- release or deployment.

`MRL_CONSTITUTION_FROZEN` is a governance state, not an execution state.