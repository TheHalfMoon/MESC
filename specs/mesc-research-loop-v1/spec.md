# MESC Research Loop V1 — Specification

Status: **PROPOSED / PLANNING ONLY / NO EXECUTION AUTHORITY**

## 1. Objective

Define a reproducible, fail-closed research-time layer that allows MESC to conduct
bounded iterative research, preserve the complete scientific decision trail, learn
reusable research procedures, and improve research efficiency without permitting the
research process to mutate or bypass the controls that judge it.

## 2. Scope

MRL V1 covers:

- research objectives and hypotheses;
- bounded experiment planning;
- linkage to the existing `ExperimentManifest`;
- structured experiment outcomes;
- scientific decisions and campaign DAGs;
- adaptive-evaluation tiers and exposure budgets;
- immutable evaluator and sealed-data boundaries;
- research-procedure extraction and independently reviewed admission;
- research-agent evaluation;
- semantic/lineage contamination metadata;
- typed research-input admission;
- research-program and project-state reconciliation.

MRL V1 does not itself perform real training, download models, acquire corpora, accept
licenses/terms, access providers, use credentials, execute GPU jobs, access PHI, promote
a model, or define model-promotion authority.

## 3. Authority hierarchy and promotion-ownership deferral

Canonical `docs/adr/0033-modelkit-public-surface-and-runtime-governance.md` explicitly
defers promotion ownership and evidence to a later dedicated ADR and prohibits
placeholder `PromotionDecision` schemas.

MRL V1 therefore must not create a parallel promotion contract under another name.
Until a dedicated promotion-ownership/evidence ADR is separately accepted:

- `ResearchDecision` has no `PROMOTED` state;
- MRL may emit only non-authoritative research recommendations/evidence candidates;
- sealed evaluation produces evidence, never a promotion decision;
- no campaign agent may declare model promotion;
- MRL artifacts cannot satisfy or replace future promotion authority.

A later accepted promotion ADR may consume MRL evidence, but that authority remains
external to this specification.

## 4. Canonical content identity rule

All MRL canonical artifacts are content-addressed without self-referential hashing.

`content_sha256` is a **derived identity**, not part of the canonical semantic preimage.
Implementations must:

1. validate the semantic payload;
2. serialize the payload deterministically;
3. compute SHA-256 over those canonical payload bytes;
4. expose/store the digest outside the hashed payload or as a derived property.

A serialized payload must never require its own digest in order to compute that digest.
Tests must prove byte stability, semantic sensitivity, and absence of self-hash recursion.

## 5. Required canonical artifacts

### 5.1 `ResearchInputAdmissionContract`

The research boundary must classify every candidate input before it can enter MRL
observation, campaign history, procedure extraction, or a research search index.

Minimum classifications:

- `RESEARCH_ARTIFACT` — eligible only when its exact contract permits use;
- `EXTERNAL_EVALUATION_EVIDENCE` — read-only evidence, never automatically a learning
  signal;
- `CLINICAL_RUNTIME_STATE` — rejected as MRL learning input;
- `PRODUCT_TELEMETRY` — rejected;
- `PHI_OR_PATIENT_DATA` — rejected under current governance.

MCRL remains a separate clinical/task-time layer. MCRL output may be treated only as
separately authorized external evaluation evidence when its governing data boundary
permits that use; it must never silently become an MRL learning signal.

### 5.2 `ResearchObjectiveContract`

Minimum semantic fields:

- `objective_id`;
- `research_program_refs`;
- `target_capabilities`;
- `hard_guardrails`;
- `search_metrics`;
- `evaluation_metrics`;
- `subgroup_floors`;
- `resource_budget`;
- `allowed_mutation_surfaces`;
- `forbidden_mutation_surfaces`;
- `evaluation_tier_policy`;
- `adaptive_query_budget`;
- `tier_result_exposure_policy`;
- `budget_exhaustion_disposition`;
- frozen evaluator identities where applicable.

An objective contract must be frozen before the first experiment in its campaign. The
campaign agent cannot increase its own resource, query, or result-exposure budgets.

### 5.3 `ResearchHypothesis`

Minimum semantic fields:

- `hypothesis_id`;
- `objective_sha256`;
- `mechanism`;
- `predicted_effects`;
- `predicted_failure_modes`;
- `falsification_criteria`;
- `evidence_refs`;
- `parent_hypothesis_ids`;
- `created_from_campaign_state_sha256`.

A hypothesis must be evaluable and falsifiable. Free-form "try this" entries cannot
become canonical hypotheses without explicit expected effects and failure criteria.

### 5.4 `ResearchExperimentPlan`

Minimum semantic fields:

- `experiment_plan_id`;
- `hypothesis_sha256`;
- exact allowed patch/mutation scope;
- exact model/data/config identities where applicable;
- seed plan;
- resource ceiling;
- expected `ExperimentManifest` bindings;
- evaluator identities;
- evaluation tiers permitted for this run;
- query/result-exposure allowance for this run;
- expected result destinations;
- stop/failure conditions.

The plan must fail closed if it attempts to alter any forbidden surface or exceeds the
frozen objective envelope.

### 5.5 Existing `ExperimentManifest`

The current `medscale.modelkit.manifests.ExperimentManifest` remains the canonical
runtime experiment manifest. MRL must reference it rather than create a competing
runtime identity system.

### 5.6 `ResearchExperimentReceipt`

Minimum semantic fields:

- experiment plan SHA-256;
- experiment manifest SHA-256;
- code/tree/patch identities;
- observed resource use;
- deterministic metric artifacts;
- guardrail results;
- subgroup results;
- failure classification;
- contamination/lineage audit result;
- replay/reproduction status;
- raw-output artifact identities where permitted;
- exact evaluation-tier/query accounting used by the run.

Raw logs are not canonical scientific conclusions and must not be treated as trusted
agent instructions.

### 5.7 `ResearchDecision`

Allowed MRL V1 states:

- `INVALID`;
- `REJECT`;
- `REPLICATE`;
- `RETAIN_LEAD`;
- `EVIDENCE_CANDIDATE`;
- `BLOCKED`.

A decision must bind exact evidence/receipt identities and state the reason.

`EVIDENCE_CANDIDATE` is only a non-authoritative research recommendation for possible
future external review. It is not promotion, release, training authorization, or clinical
authority. `PROMOTED` is deliberately absent until the dedicated ADR required by
ADR-0033 exists.

### 5.8 `ResearchCampaign`

A campaign is a content-addressed DAG containing:

- objective identity;
- hypothesis nodes;
- experiment-plan nodes;
- receipts;
- decisions;
- replication relationships;
- retained alternatives;
- rejected/invalid branches;
- current frontier;
- procedure candidates;
- cumulative resource usage;
- cumulative adaptive-query/result-exposure usage.

The campaign must preserve negative/null results and cannot delete failed branches from
canonical history.

### 5.9 `ResearchProcedure`

Minimum semantic fields:

- `procedure_id`;
- `version`;
- typed applicability bounds;
- preconditions;
- allowed tools;
- forbidden actions;
- steps;
- expected artifacts;
- verification steps;
- known failure modes;
- source campaign refs;
- admission report SHA-256.

### 5.10 `ResearchProcedureAdmissionReport`

A procedure may progress only through:

```text
DISCOVERED
  -> CANDIDATE
  -> REPLAYED
  -> TRANSFER_TESTED
  -> REVIEWED
  -> ADMITTED
```

Admission requires evidence beyond the exact discovery trajectory. The report must bind:

- procedure SHA-256;
- replay evidence identities;
- representative transfer-test evidence identities;
- negative/failure-control evidence identities;
- typed applicability limits;
- independent reviewer/operator authority identity;
- immutable review receipt identity;
- decision and reason;
- supersession/invalidation references when applicable.

The campaign/research agent cannot be the sole producer of `REVIEWED` or `ADMITTED`.
Known boundary violations or newly established failure modes must be able to invalidate or
supersede an admitted procedure without deleting its history.

## 6. Evaluation hierarchy and adaptive-query governance

MRL must separate adaptive search feedback from sealed scientific evidence.

### Tier 0 — Unit / synthetic development fixtures

Purpose: implementation debugging and contract tests.

Agent access: full permitted fixture visibility.

### Tier 1 — Research Search Set

Purpose: iterative hypothesis search and optimization.

Agent access: only within the frozen objective's query and result-exposure budgets.

### Tier 2 — Replication Set

Purpose: test whether a retained result survives a less-adaptive evaluation surface.

Agent access: restricted. Only the explicitly frozen bounded summaries may be exposed,
and every exposure consumes the frozen Tier 2 budget.

### Tier 3 — Sealed Evaluation Set

Purpose: produce independent high-integrity evaluation evidence that may later be
consumed by an authority defined outside MRL.

Agent access: no item-level access during optimization and no iterative result stream.
Tier 3 produces a sealed evidence artifact/report for an independent consumer; it does
not emit an MRL promotion decision.

### Tier 4 — External / Clinician Assurance

Purpose: independent high-stakes claim calibration, human review, external replication,
or future clinician-authored evaluation where separately authorized.

MRL automation must not treat Tier 4 as a substitute for real independent review.

### Adaptive-query invariants

Each frozen objective must define:

- maximum Tier 1 queries/exposures;
- maximum Tier 2 queries/exposures;
- exactly which aggregate fields may be returned;
- whether repeated evaluation of the same candidate is permitted;
- stopping and invalidation rules;
- the disposition when any budget is exhausted.

Budget exhaustion is fail-closed: the campaign becomes `BLOCKED` for additional adaptive
use of that tier. The research agent cannot amend the frozen budget or request more detail
from sealed evidence. A new or amended objective requires external governance and a new
content identity.

## 7. Evaluation and evidence rules

A single scalar score is insufficient for medical research evidence.

MRL evidence control must apply, in order:

1. hard validity/reproducibility gates;
2. hard contamination gates;
3. hard safety and harmful-overconfidence gates;
4. hard abstention/evidence-fidelity gates where relevant;
5. critical subgroup floors;
6. only then capability/cost/latency/calibration comparison.

A candidate with a material hard-gate regression is `INVALID` or `REJECT` even if an
aggregate score improves.

Multi-objective comparison should prefer Pareto reasoning over hiding incompatible
trade-offs in one unconstrained scalar.

Passing these rules may create only `EVIDENCE_CANDIDATE` under MRL V1. It cannot create
`PROMOTED`.

## 8. Immutable research-agent boundary

The autonomous research mutation surface must be explicit and allow-listed.

The research agent must never directly mutate:

- governance documents that define active authority;
- sealed evaluation data;
- evaluator/scorer implementations frozen for the campaign;
- evaluation thresholds/rules after campaign start;
- trust registries;
- authorization/training-readiness code;
- license or rights decisions;
- canonical experiment history;
- CI/security gates used to qualify its work;
- PHI/data-boundary policies;
- machine-state generators or source authority in a way that can self-certify eligibility.

Any attempted mutation outside the allow-list fails closed and produces an auditable
invalid-attempt artifact.

## 9. Structured observation boundary

Model/training/tool output is untrusted data.

Research agents should consume typed result summaries rather than raw logs by default.
A result envelope should minimally expose:

- run status;
- metric artifact identities;
- selected metric values permitted by the exposure policy;
- guardrail outcomes;
- resource usage;
- failure class;
- artifact hashes;
- bounded diagnostic fields;
- tier/query-budget accounting.

Raw stdout/stderr may be retained for human diagnosis but must not automatically become
trusted research instructions.

## 10. Resource governance

Every campaign must freeze ceilings such as:

- wall-clock/GPU minutes;
- maximum experiments;
- token budget;
- storage budget;
- monetary budget where relevant;
- maximum repeated failures per failure signature;
- adaptive evaluation/query budgets;
- result-exposure budgets.

A campaign exceeding any ceiling becomes `BLOCKED`; the agent cannot silently expand its
own budget.

## 11. Research memory requirements

MRL memory must not be an opaque hidden agent database that becomes scientific truth.

Canonical memory is:

- append-only where history is concerned;
- content-addressed;
- reconstructible from repository artifacts;
- typed;
- inspectable;
- versioned;
- admission-gated for reusable procedures.

Derived indexes/search stores are rebuildable and non-authoritative. They must enforce
`ResearchInputAdmissionContract` and cannot index rejected PHI/product/clinical-runtime
inputs as research memory.

## 12. Contamination and lineage

Real MRL experimentation has no optional contamination bypass. Before
`MRL_REAL_EXPERIMENT_READY`, the repository must have canonically completed the MRL-6
contamination/lineage gate.

The contamination model must distinguish at least:

- exact duplicate contamination;
- near-duplicate contamination;
- semantic/paraphrase contamination;
- prompt-derived contamination;
- teacher-derived contamination;
- benchmark-derived synthetic contamination;
- transformation-lineage contamination.

Where synthetic or teacher-generated training items are later authorized, provenance
must be able to bind:

- generation parent ids;
- teacher model id/revision;
- teacher prompt identity;
- source evidence ids;
- transformation chain;
- benchmark-similarity flags;
- contamination assessment identity.

This specification does not authorize generation or ingestion of such data.

## 13. Temporal canary track

MRL should support a future sealed temporal-canary evaluation surface consisting only of
R2-compatible synthetic/hand-authored fixtures unless governance changes.

Canaries must:

- be created after the relevant training/data freeze;
- receive independent content identity;
- remain unavailable as training/search material;
- exercise updated guideline/version combinations, new FHIR compositions, or fresh
  adversarial combinations;
- never be silently recycled into later training data.

## 14. Research-agent benchmark

MRL must evaluate the researcher, not only the produced model.

Candidate meta-metrics:

- validated gain per compute unit;
- experiments to first replicated gain;
- invalid experiment rate;
- false-evidence-candidate rate;
- safety-regression attempt rate;
- repeated-known-failure rate;
- hypothesis diversity;
- procedure transfer success;
- human corrections per campaign;
- reproducibility failure rate;
- compute wasted on previously known failure signatures.

The benchmark should compare at minimum:

1. stateless research agent;
2. campaign-history-only agent;
3. admitted-procedure-memory agent;
4. portfolio/tree-search agent.

## 15. Research-program registry reconciliation

The project must preserve foundational RQ1-RQ7 while introducing a registry that can
represent later programs without pretending those later research questions are already
part of the original foundational set.

Suggested namespaces:

```text
FOUNDATION-RQ*
MESC1-RQ*
MCRL-RQ*
ARABIC-RQ*
AMGE-RQ*
OMNI-RQ*
MRL-RQ*
```

Every future experiment must trace to an active registered research question/objective.

## 16. Machine-readable project-state precedence and anti-staleness

Before autonomous research execution, MESC should expose deterministic projections such
as:

- `PROJECT_STATE.json`;
- `CAPABILITY_MATRIX.json`;
- `RESEARCH_PROGRAM_INDEX.json`.

These projections are not an independent authority source. Their canonical inputs are
repository/spec/governance artifacts and exact gate evidence.

Every projection must:

- be generated deterministically by the canonical generator;
- bind the exact repository commit it represents;
- bind the canonical source artifact hashes used to derive it;
- be rejected by eligibility/preflight consumers when stale;
- fail validation if manually edited without regeneration;
- lose to live canonical gate evidence when a narrative document disagrees.

CI must test conflicting narrative/projection/canonical-gate state and prove that stale or
manually altered projections cannot authorize work.

## 17. Security requirements

Before any real autonomous experiment execution:

- network is default-deny unless the exact run requires separately authorized access;
- no ambient credentials;
- no provider/model/data download authority is implied by the agent loop;
- tool outputs and model outputs are treated as untrusted;
- execution environment must enforce allowed write paths;
- evaluator/sealed-data paths must be read-only or unavailable;
- all authority-bearing artifacts remain independently validated;
- failed/blocked attempts remain auditable;
- research input admission rejects PHI/product/clinical-runtime learning inputs;
- MRL-6 contamination/lineage qualification and MRL-7 machine-state qualification are
  mandatory before real-experiment preflight can pass.

## 18. Acceptance criteria for the MRL V1 research substrate

The repository-side substrate is considered implementation-complete only when all are
true on an exact qualified head:

- canonical typed artifacts exist for input admission, objective, hypothesis, plan,
  receipt, decision, campaign, procedure, and procedure admission;
- deterministic canonical serialization and derived content hashing are tested, including
  explicit exclusion of `content_sha256` from its own preimage;
- existing `ExperimentManifest` is reused rather than replaced;
- `ResearchDecision` cannot encode `PROMOTED` and MRL exposes only non-authoritative
  `EVIDENCE_CANDIDATE` output pending the dedicated ADR required by ADR-0033;
- an allow-listed mutation policy rejects evaluator/governance/sealed-data mutation;
- a fixture-only campaign can propose, execute a bounded fake experiment, retain or
  reject, replicate, and close without real model/data/GPU access;
- metric/evaluator tampering cannot produce valid sealed evidence;
- sealed Tier 3 item-level data cannot be read during search;
- adaptive-query and result-exposure budgets fail closed when exhausted;
- MRL observation/history/procedure/search-index paths reject PHI, product telemetry, and
  clinical-runtime state as learning inputs;
- a procedure cannot become `ADMITTED` without replay, representative transfer testing,
  negative controls, typed applicability limits, and an independent review receipt;
- resource-ceiling escape fails closed;
- raw-log prompt-injection content cannot become trusted control instructions through
  the structured observation interface;
- failed/null/invalid branches remain in canonical campaign history;
- stale or manually altered machine-state projections cannot authorize eligibility;
- project/RQ status reconciliation is explicit;
- CI, static typing, formatting, tests, and repository checks pass;
- no real training, provider/model download, PHI, credential, promotion, or release action
  is performed as part of qualification.

## 19. Future execution boundary

Connecting MRL to real model training is a separate future gate.

Real experimentation requires independently proven:

- `MRL_FIXTURE_LOOP_PROVEN`;
- `MRL_EVALUATION_CONTROL_READY`;
- `MRL_PROCEDURE_MEMORY_READY`;
- `MRL_RESEARCHER_EVAL_READY`;
- `MRL_CONTAMINATION_V2_READY`;
- `MESC_MACHINE_STATE_READY`;
- model/corpus rights and exact identities;
- runtime/GPU qualification;
- applicable training authorization;
- campaign/objective freeze;
- evaluator and sealed-evaluation freeze;
- resource and adaptive-query budgets;
- execution sandbox;
- exact-head qualification.

No artifact in this planning package satisfies those conditions by itself. Model
promotion remains separately owned by the future dedicated ADR required by ADR-0033.