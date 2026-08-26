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

Canonical ADR-0033 remains controlling for deferred model-promotion ownership. MRL V1
must not implement `PromotionDecision`, `PROMOTED`, or an equivalent promotion authority
under another name. It may produce only non-authoritative research evidence candidates
until a separately accepted dedicated promotion-ownership/evidence ADR exists.

## MRL-0 — Research constitution and governance reconciliation

### Goal

Freeze the conceptual and authority boundaries before implementing an agent loop.

### Deliverables

- accept/revise this MRL V1 specification;
- record MRL vs MCRL separation and research-input admission policy;
- record ADR-0033 promotion-ownership deferral;
- define the immutable evaluator rule;
- define adaptive evaluation tiers 0-4;
- define hard medical evidence gates vs optimization metrics;
- define frozen compute/query/result-exposure ceilings;
- reconcile foundational RQ1-RQ7 with later MESC research programs;
- define canonical project-state projection precedence and anti-staleness requirements.

### Acceptance

- no ambiguous source of execution or promotion authority;
- no path by which MRL can learn from PHI, product telemetry, or clinical-runtime state
  under current governance;
- MCRL remains a separate clinical/task-time layer;
- no research-agent write authority over governance, sealed evals, evaluators, trust,
  authorization, licensing decisions, canonical history, or machine-state authority;
- adaptive-query and result-exposure budgets are frozen outside agent control;
- all later stages have explicit dependencies and gates.

### Exit state

`MRL_CONSTITUTION_FROZEN`

This state still grants no training, autonomous execution, or model-promotion authority.

---

## MRL-1 — Typed canonical research artifacts

Depends on: `MRL-0`

### Goal

Implement the content-addressed scientific decision graph without any autonomous model
or GPU execution.

### Deliverables

Implement deterministic typed contracts/artifacts for:

- canonical content identity with `content_sha256` derived outside its own preimage;
- `ResearchInputAdmissionContract`;
- `ResearchObjectiveContract`;
- `ResearchHypothesis`;
- `ResearchExperimentPlan`;
- `ResearchExperimentReceipt`;
- `ResearchDecision`;
- `ResearchCampaign`;
- `ResearchProcedure`;
- `ResearchProcedureAdmissionReport`.

Reuse the existing `ExperimentManifest` for runtime experiment identity.

`ResearchDecision` V1 is restricted to:

```text
INVALID
REJECT
REPLICATE
RETAIN_LEAD
EVIDENCE_CANDIDATE
BLOCKED
```

`EVIDENCE_CANDIDATE` is a non-authoritative research recommendation. No MRL-1 artifact
may encode `PROMOTED`.

### Required tests

- canonical serialization is byte-stable;
- `content_sha256` is derived from canonical semantic bytes and excluded from its own
  preimage;
- duplicate/unknown/malformed fields fail closed where closed schemas are used;
- content hashes change when material semantics change;
- research input admission rejects PHI/product telemetry/clinical-runtime learning input;
- campaign DAG references are valid and acyclic where required;
- failed/null/invalid results cannot be deleted by a later campaign projection;
- `EVIDENCE_CANDIDATE` cannot be interpreted as promotion;
- `PROMOTED` cannot be constructed by the MRL V1 decision contract;
- procedure `REVIEWED`/`ADMITTED` requires an independent immutable review receipt and
  typed applicability bounds.

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
  -> reject / replicate / retain / evidence-candidate
  -> campaign update
```

### Mandatory adversarial tests

- attempted scorer mutation;
- attempted evidence-threshold mutation;
- attempted sealed-data read during search;
- attempted write outside allow-listed experiment surface;
- resource-budget escape;
- adaptive-query/result-exposure budget escape;
- PHI/product/clinical-runtime input admission attempt;
- raw-log prompt-injection string;
- fabricated metric value without bound metric artifact;
- stale experiment receipt;
- mismatched plan/manifest/code identity;
- repeated known failure beyond configured retry ceiling;
- attempted construction of `PROMOTED` or self-admitted procedure state.

Every case must fail closed without manufacturing valid sealed evidence, promotion, or
procedure admission.

### Exit state

`MRL_FIXTURE_LOOP_PROVEN`

---

## MRL-3 — Adaptive evaluation and sealed-evidence control

Depends on: `MRL-2`

### Goal

Make high-volume iterative research statistically and scientifically safer than repeated
optimization against one visible validation set without creating model-promotion
ownership.

### Deliverables

- tier-aware evaluation contract;
- frozen Tier 1 query/result-exposure budget;
- frozen Tier 2 query/result-exposure budget;
- exact allowed aggregate-result exposure policy;
- replication-set policy;
- sealed Tier 3 evaluator interface;
- independent sealed-evaluation evidence artifact/report;
- hard non-regression gates;
- Pareto comparison support;
- campaign-level adaptive-query accounting;
- fail-closed budget-exhaustion handling;
- explicit rule that sealed item-level results never become agent search context.

Tier 3 evidence is delivered to an independent consumer and is not an iterative agent
result stream. MRL-3 cannot emit `PROMOTED` or any equivalent promotion decision.

### Required medical guardrail model

The system must represent mandatory floors for relevant axes such as:

- safety;
- harmful overconfidence;
- abstention;
- evidence fidelity;
- contamination;
- reproducibility;
- critical subgroups.

The exact active floors and adaptive budgets belong to each frozen objective contract.
When a query/exposure budget is exhausted, the campaign becomes `BLOCKED` for further use
of that tier. The agent cannot enlarge its own budget.

### Exit state

`MRL_EVALUATION_CONTROL_READY`

---

## MRL-4 — Governed research memory and procedure admission

Depends on: `MRL-3`

### Goal

Add Hermes-style learning from prior work without allowing repeated success to silently
become scientific truth or allowing the research agent to self-admit procedures.

### Deliverables

- campaign-history query/projection;
- procedure-candidate extraction interface;
- procedure replay harness;
- representative transfer-test contract;
- negative/failure-control contract;
- typed applicability limits;
- independent reviewer/operator review receipt;
- admission report;
- admitted/rejected/superseded/invalidated procedure registry;
- rebuildable non-authoritative search index enforcing research-input admission.

### Admission rule

```text
DISCOVERED
  -> CANDIDATE
  -> REPLAYED
  -> TRANSFER_TESTED
  -> REVIEWED
  -> ADMITTED
```

No stage may be skipped. The campaign/research agent cannot be the sole producer of
`REVIEWED` or `ADMITTED`. Admission must bind independent review identity, replay and
representative transfer evidence, negative controls, and explicit applicability bounds.
A later known failure or boundary violation must support append-only invalidation or
supersession without deleting history.

### Required comparison

Demonstrate on fixture research tasks that admitted procedure memory reduces at least one
research-cost measure without increasing invalid or false-evidence-candidate behavior.

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
- false-evidence-candidate rate;
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

Depends on: `MRL-3`; implementation may proceed in parallel with portions of MRL-4/5
after dependency review.

### Goal

Strengthen scientific isolation for synthetic-teacher and repeated research workflows.
This stage is mandatory before any real MRL experiment preflight can pass.

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

Prevent future agents and humans from following stale narrative roadmaps or manually
edited projections.

### Proposed projections

- `PROJECT_STATE.json`;
- `CAPABILITY_MATRIX.json`;
- `RESEARCH_PROGRAM_INDEX.json`.

### Rules

- deterministic generation from canonical repository/spec/governance state is mandatory;
- each projection binds the exact repository commit it represents;
- each projection binds hashes of the canonical source artifacts used to derive it;
- projections are derived views, not independent authority sources;
- eligibility/preflight consumers reject stale projections;
- manually edited projections fail the generation/check contract;
- conflicting narrative status never overrides live canonical gate evidence;
- foundational RQ1-RQ7 remain preserved with explicit historical namespace/meaning.

### Required negative proof

Construct conflicting narrative/projection/canonical-gate states and prove downstream
eligibility follows the live canonical gate evidence and rejects stale/manual projections.

### Exit state

`MESC_MACHINE_STATE_READY`

---

## MRL-8 — Real autonomous research preflight

Depends on all of:

- `MRL_FIXTURE_LOOP_PROVEN`;
- `MRL_EVALUATION_CONTROL_READY`;
- `MRL_PROCEDURE_MEMORY_READY`;
- `MRL_RESEARCHER_EVAL_READY`;
- `MRL_CONTAMINATION_V2_READY`;
- `MESC_MACHINE_STATE_READY`;
- current training/runtime governance.

There is no optional MRL-6 bypass for real MRL experimentation.

### Goal

Determine whether MESC is allowed and technically prepared to connect the proven research
substrate to a real bounded model experiment runner.

### Required preflight evidence

- exact selected model and weights identity;
- corpus identity and rights evidence;
- completed contamination/lineage evidence from the canonical MRL-6 gate;
- held-out/sealed-evaluation isolation evidence;
- runtime/GPU qualification;
- dependency lock and exact code tree;
- applicable training authorization;
- frozen research objective;
- frozen evaluator identities;
- sealed Tier 3 evaluation identities;
- resource, adaptive-query, and result-exposure budgets;
- research-input admission policy identity;
- sandbox policy;
- allowed mutation paths;
- output destinations;
- rollback/stop conditions;
- current machine-state projection bound to the exact candidate commit;
- exact-head CI/security qualification.

### Mandatory status distinction

```text
MRL_CODE_READY != MRL_REAL_EXPERIMENT_READY
MRL_REAL_EXPERIMENT_READY != TRAINING_READY
MRL_REAL_EXPERIMENT_READY != TRAINING_EXECUTION_COMPLETE
TRAINING_EXECUTION_COMPLETE != RELEASE_READY
EVIDENCE_CANDIDATE != PROMOTED
```

`PROMOTED` is not an MRL V1 state. Any future promotion state belongs to the dedicated
promotion-ownership/evidence ADR required by ADR-0033.

### Exit state

Only a separately authorized and evidenced gate may declare
`MRL_REAL_EXPERIMENT_READY`.

This planning package cannot declare it.

---

## Long-term follow-ons — not V1 commitments

After evidence from MRL V1 exists, later proposals may evaluate:

- the dedicated promotion-ownership/evidence ADR required by ADR-0033;
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