# MESC Research Loop V1 — Implementation Plan

Status: **PROPOSED / DEPENDENCY-ORDERED / NO REAL EXPERIMENT EXECUTION AUTHORITY**

## Program goal

Build the research substrate in small, independently reviewable stages so that MESC can
later support autonomous research without weakening scientific validity, security,
medical safety, or canonical authority boundaries.

## Sequencing rule

Do not skip ahead to a real GPU/LLM loop.

Each stage must become canonically accepted before the next stage that depends on it can
claim eligibility. Strategy/planning acceptance does not itself authorize implementation
or execution where a separate founder/operator gate is required.

## MRL-0 — Research constitution and governance reconciliation

### Goal

Freeze the conceptual boundaries before implementing an agent loop.

### Deliverables

- accept/revise this MRL V1 specification;
- record MRL vs MCRL separation;
- define the immutable evaluator rule;
- define adaptive evaluation tiers 0-4;
- define hard medical promotion gates vs optimization metrics;
- define research resource ceilings;
- reconcile foundational RQ1-RQ7 with later MESC research programs;
- define canonical project-state projection requirements.

### Acceptance

- no ambiguous source of execution authority;
- no path by which MRL can learn from PHI/product telemetry under current governance;
- no research-agent write authority over governance, sealed evals, evaluators, trust,
  authorization, licensing decisions, or canonical history;
- all later stages have explicit dependencies and gates.

### Exit state

`MRL_CONSTITUTION_FROZEN`

This state still grants no training or autonomous execution authority.

---

## MRL-1 — Typed canonical research artifacts

Depends on: `MRL-0`

### Goal

Implement the content-addressed scientific decision graph without any autonomous model
or GPU execution.

### Deliverables

Implement deterministic typed artifacts for:

- `ResearchObjectiveContract`;
- `ResearchHypothesis`;
- `ResearchExperimentPlan`;
- `ResearchExperimentReceipt`;
- `ResearchDecision`;
- `ResearchCampaign`;
- `ResearchProcedure`;
- `ResearchProcedureAdmissionReport`.

Reuse the existing `ExperimentManifest` for runtime experiment identity.

### Required tests

- canonical serialization is byte-stable;
- duplicate/unknown/malformed fields fail closed where closed schemas are used;
- content hashes change when material semantics change;
- campaign DAG references are valid and acyclic where required;
- failed/null/invalid results cannot be deleted by a later campaign projection;
- promotion cannot be constructed from a search-set result alone;
- `PROMOTION_CANDIDATE != PROMOTED` is enforced structurally.

### Exit state

`MRL_ARTIFACT_CORE_READY`

---

## MRL-2 — Fixture-only governed closed loop

Depends on: `MRL-1`

### Goal

Prove loop semantics without real model weights, corpora, network access, provider calls,
GPU use, or training.

### Fixture campaign

Use a deterministic toy objective where a bounded fake experiment surface can be edited
or parameterized and scored by a separately frozen evaluator.

Required loop:

```text
hypothesis
  -> experiment plan
  -> bounded fixture execution
  -> ExperimentManifest-compatible runtime identity
  -> structured receipt
  -> decision
  -> reject / replicate / retain
  -> campaign update
```

### Mandatory adversarial tests

- attempted scorer mutation;
- attempted promotion-threshold mutation;
- attempted sealed-data read during search;
- attempted write outside allow-listed experiment surface;
- resource-budget escape;
- raw-log prompt-injection string;
- fabricated metric value without bound metric artifact;
- stale experiment receipt;
- mismatched plan/manifest/code identity;
- repeated known failure beyond configured retry ceiling.

Every case must fail closed without manufacturing a valid promotion.

### Exit state

`MRL_FIXTURE_LOOP_PROVEN`

---

## MRL-3 — Adaptive evaluation and promotion control

Depends on: `MRL-2`

### Goal

Make high-volume iterative research statistically and scientifically safer than repeated
optimization against one visible validation set.

### Deliverables

- tier-aware evaluation contract;
- search-set result exposure policy;
- replication-set result exposure policy;
- sealed-promotion evaluator interface;
- independent promotion report;
- hard non-regression gates;
- Pareto comparison support;
- campaign-level adaptive-query accounting;
- explicit rule that sealed item-level results never become agent search context.

### Required medical guardrail model

The system must be able to represent mandatory floors for relevant axes such as:

- safety;
- harmful overconfidence;
- abstention;
- evidence fidelity;
- contamination;
- reproducibility;
- critical subgroups.

The exact active floors belong to each frozen objective contract.

### Exit state

`MRL_PROMOTION_CONTROL_READY`

---

## MRL-4 — Governed research memory and procedure admission

Depends on: `MRL-3`

### Goal

Add Hermes-style learning from prior work without allowing repeated success to silently
become scientific truth.

### Deliverables

- campaign-history query/projection;
- procedure-candidate extraction interface;
- procedure replay harness;
- transfer-test contract;
- negative/failure-control contract;
- admission report;
- admitted-procedure registry;
- rejected/superseded procedure history;
- rebuildable non-authoritative search index.

### Admission rule

```text
DISCOVERED
  -> CANDIDATE
  -> REPLAYED
  -> TRANSFER_TESTED
  -> REVIEWED
  -> ADMITTED
```

No stage may be skipped.

### Required comparison

Demonstrate on fixture research tasks that admitted procedure memory reduces at least one
research-cost measure without increasing invalid/false-promotion behavior.

### Exit state

`MRL_PROCEDURE_MEMORY_READY`

---

## MRL-5 — Research portfolio and researcher benchmark

Depends on: `MRL-4`

### Goal

Move beyond a single linear keep/discard loop and evaluate whether MRL actually improves
research quality and efficiency.

### Deliverables

- portfolio/DAG frontier policy;
- branch diversity controls;
- replication branch semantics;
- failure-signature deduplication;
- retained-alternative semantics;
- research-agent benchmark;
- deterministic benchmark reports.

### Benchmark arms

At minimum:

1. stateless researcher;
2. campaign-history-only researcher;
3. admitted-procedure-memory researcher;
4. portfolio/tree-search researcher.

### Meta-metrics

At minimum where applicable:

- validated gain per compute unit;
- experiments to first replicated gain;
- invalid experiment rate;
- false-promotion rate;
- repeated-known-failure rate;
- hypothesis diversity;
- procedure transfer success;
- human correction count;
- reproducibility failure rate;
- wasted compute on known failures.

### Exit state

`MRL_RESEARCHER_EVAL_READY`

---

## MRL-6 — Contamination lineage and temporal canaries

Depends on: `MRL-3`; can proceed in parallel with portions of MRL-4/5 after dependency
review.

### Goal

Strengthen scientific isolation for synthetic-teacher and repeated research workflows.

### Deliverables

- lineage model for generated/transformed examples;
- exact/near/semantic contamination assessment interfaces;
- teacher/prompt/source transformation bindings;
- benchmark-derived-generation detection hooks;
- temporal-canary manifest contract;
- sealed post-freeze synthetic/hand-authored canary workflow;
- explicit prohibition on recycling canaries into training/search data.

### Exit state

`MRL_CONTAMINATION_V2_READY`

---

## MRL-7 — Machine-readable research/project state

Depends on: `MRL-0`; implementation ordering may be parallelized with MRL-1 after the
schema is frozen.

### Goal

Prevent future agents and humans from following stale narrative roadmaps.

### Proposed projections

- `PROJECT_STATE.json`;
- `CAPABILITY_MATRIX.json`;
- `RESEARCH_PROGRAM_INDEX.json`.

### Rules

- generated from canonical repository/spec state where practical;
- deterministic;
- content-addressable or bound to an exact repository SHA;
- human-readable roadmaps remain explanatory, not competing operational truth;
- foundational RQ1-RQ7 remain preserved with explicit historical namespace/meaning.

### Exit state

`MESC_MACHINE_STATE_READY`

---

## MRL-8 — Real autonomous research preflight

Depends on: `MRL-2`, `MRL-3`, `MRL-4`, `MRL-5`, applicable `MRL-6`, and current
training/runtime governance.

### Goal

Determine whether MESC is allowed and technically prepared to connect the proven research
substrate to a real bounded model experiment runner.

### Required preflight evidence

- exact selected model and weights identity;
- corpus identity and rights evidence;
- training/evaluation contamination evidence;
- runtime/GPU qualification;
- dependency lock and exact code tree;
- applicable training authorization;
- frozen research objective;
- frozen evaluator identities;
- sealed promotion set identity;
- resource budget;
- sandbox policy;
- allowed mutation paths;
- output destinations;
- rollback/stop conditions;
- exact-head CI/security qualification.

### Mandatory status distinction

```text
MRL_CODE_READY != MRL_REAL_EXPERIMENT_READY
MRL_REAL_EXPERIMENT_READY != TRAINING_EXECUTION_COMPLETE
TRAINING_EXECUTION_COMPLETE != RELEASE_READY
```

### Exit state

Only a separately authorized and evidenced gate may declare
`MRL_REAL_EXPERIMENT_READY`.

This planning package cannot declare it.

---

## Long-term follow-ons — not V1 commitments

After evidence from MRL V1 exists, later proposals may evaluate:

- multi-agent scientist/reviewer roles;
- independent hypothesis-generation models;
- cost-aware Bayesian or bandit allocation;
- cross-campaign procedure transfer;
- stronger sequential/adaptive statistical controls;
- clinician-calibrated evaluation orchestration;
- Arabic/longitudinal/FHIR-specific research agents;
- controlled automated literature-to-hypothesis assistance;
- weight-level self-improvement only under a separate scientific and safety program.

None is authorized merely by appearing in this section.
