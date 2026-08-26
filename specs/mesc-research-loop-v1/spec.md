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
- scientific decisions;
- campaign DAGs / portfolios;
- adaptive-evaluation tiers;
- immutable evaluator and sealed-data boundaries;
- research-procedure extraction and admission;
- research-agent evaluation;
- semantic/lineage contamination metadata;
- research-program and project-state reconciliation.

MRL V1 does not itself perform real training, download models, acquire corpora, accept
licenses/terms, access providers, use credentials, execute GPU jobs, access PHI, or
promote a model release.

## 3. Non-goals

MRL V1 is not:

- a replacement for MCRL;
- a clinical decision-making agent;
- an autonomous production deployment system;
- a recursive self-training system;
- an authority source for training or release;
- permission to expose sealed evaluation material to a research agent;
- permission to use real patient/product data;
- permission to let an agent edit governance or evaluation rules.

## 4. Required canonical artifacts

### 4.1 `ResearchObjectiveContract`

Minimum fields:

- `objective_id`;
- `research_program_refs`;
- `target_capabilities`;
- `hard_guardrails`;
- `search_metrics`;
- `promotion_metrics`;
- `subgroup_floors`;
- `resource_budget`;
- `allowed_mutation_surfaces`;
- `forbidden_mutation_surfaces`;
- `evaluation_tier_policy`;
- `content_sha256`.

An objective contract must be frozen before the first experiment in its campaign.

### 4.2 `ResearchHypothesis`

Minimum fields:

- `hypothesis_id`;
- `objective_sha256`;
- `mechanism`;
- `predicted_effects`;
- `predicted_failure_modes`;
- `falsification_criteria`;
- `evidence_refs`;
- `parent_hypothesis_ids`;
- `created_from_campaign_state_sha256`;
- `content_sha256`.

A hypothesis must be evaluable and falsifiable. Free-form "try this" entries cannot
become canonical hypotheses without explicit expected effects and failure criteria.

### 4.3 `ResearchExperimentPlan`

Minimum fields:

- `experiment_plan_id`;
- `hypothesis_sha256`;
- exact allowed patch/mutation scope;
- exact model/data/config identities where applicable;
- seed plan;
- resource ceiling;
- expected `ExperimentManifest` bindings;
- evaluator identities;
- evaluation tiers permitted for this run;
- expected result destinations;
- stop/failure conditions;
- `content_sha256`.

The plan must fail closed if it attempts to alter any forbidden surface.

### 4.4 Existing `ExperimentManifest`

The current `medscale.modelkit.manifests.ExperimentManifest` remains the canonical
runtime experiment manifest. MRL must reference it rather than create a competing
runtime identity system.

### 4.5 `ResearchExperimentReceipt`

Minimum fields:

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
- `content_sha256`.

Raw logs are not canonical scientific conclusions and must not be treated as trusted
agent instructions.

### 4.6 `ResearchDecision`

Allowed terminal/non-terminal states:

- `INVALID`;
- `REJECT`;
- `REPLICATE`;
- `RETAIN_LEAD`;
- `PROMOTION_CANDIDATE`;
- `PROMOTED`;
- `BLOCKED`.

A decision must bind the exact evidence/receipt identities and state the reason.

`PROMOTION_CANDIDATE` is not `PROMOTED`.

### 4.7 `ResearchCampaign`

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
- cumulative resource usage.

The campaign must preserve negative/null results and cannot delete failed branches from
canonical history.

### 4.8 `ResearchProcedure`

Minimum fields:

- `procedure_id`;
- `version`;
- `applicability`;
- `preconditions`;
- `allowed_tools`;
- `forbidden_actions`;
- `steps`;
- `expected_artifacts`;
- `verification_steps`;
- `known_failure_modes`;
- `source_campaign_refs`;
- `admission_report_sha256`;
- `content_sha256`.

### 4.9 `ResearchProcedureAdmissionReport`

A procedure may progress only through:

```text
DISCOVERED
  -> CANDIDATE
  -> REPLAYED
  -> TRANSFER_TESTED
  -> REVIEWED
  -> ADMITTED
```

Admission requires evidence that the procedure works beyond the exact trajectory from
which it was extracted.

## 5. Evaluation hierarchy

MRL must separate adaptive search feedback from scientific promotion evidence.

### Tier 0 — Unit / synthetic development fixtures

Purpose: implementation debugging and contract tests.

Agent access: full permitted fixture visibility.

### Tier 1 — Research Search Set

Purpose: iterative hypothesis search and optimization.

Agent access: permitted according to the objective contract.

### Tier 2 — Replication Set

Purpose: test whether a retained result survives a less-adaptive evaluation surface.

Agent access: restricted. The contract may expose only bounded result summaries.

### Tier 3 — Sealed Promotion Set

Purpose: final model/research promotion evidence.

Agent access: no item-level access during optimization. No repeated tuning against
sealed outcomes.

### Tier 4 — External / Clinician Assurance

Purpose: independent high-stakes claim calibration, human review, external replication,
or future clinician-authored evaluation where separately authorized.

MRL automation must not treat Tier 4 as a substitute for real independent review.

## 6. Promotion and optimization rules

A single scalar score is insufficient for medical research promotion.

The promotion contract must implement:

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

## 7. Immutable research-agent boundary

The autonomous research mutation surface must be explicit and allow-listed.

The research agent must never directly mutate:

- governance documents that define active authority;
- sealed evaluation data;
- evaluator/scorer implementations frozen for the campaign;
- promotion thresholds/rules after campaign start;
- trust registries;
- authorization/training-readiness code;
- license or rights decisions;
- canonical experiment history;
- CI/security gates used to qualify its work;
- PHI/data-boundary policies.

Any attempted mutation outside the allow-list fails closed and produces an auditable
invalid-attempt artifact.

## 8. Structured observation boundary

Model/training/tool output is untrusted data.

Research agents should consume typed result summaries rather than raw logs by default.
A result envelope should minimally expose:

- run status;
- metric artifact identities;
- selected metric values;
- guardrail outcomes;
- resource usage;
- failure class;
- artifact hashes;
- bounded diagnostic fields.

Raw stdout/stderr may be retained for human diagnosis but must not automatically become
trusted research instructions.

## 9. Resource governance

Every campaign must freeze ceilings such as:

- wall-clock/GPU minutes;
- maximum experiments;
- token budget;
- storage budget;
- monetary budget where relevant;
- maximum repeated failures per failure signature.

A campaign exceeding its ceiling becomes `BLOCKED`; the agent cannot silently expand
its own budget.

## 10. Research memory requirements

MRL memory must not be an opaque hidden agent database that becomes scientific truth.

Canonical memory is:

- append-only where history is concerned;
- content-addressed;
- reconstructible from repository artifacts;
- typed;
- inspectable;
- versioned;
- admission-gated for reusable procedures.

Derived indexes/search stores are rebuildable and non-authoritative.

## 11. Contamination and lineage expansion

Future MRL/data work must distinguish at least:

- exact duplicate contamination;
- near-duplicate contamination;
- semantic/paraphrase contamination;
- prompt-derived contamination;
- teacher-derived contamination;
- benchmark-derived synthetic contamination;
- transformation-lineage contamination.

Where synthetic or teacher-generated training items are later authorized, provenance
should be able to bind:

- generation parent ids;
- teacher model id/revision;
- teacher prompt identity;
- source evidence ids;
- transformation chain;
- benchmark-similarity flags;
- contamination assessment identity.

This specification does not authorize generation or ingestion of such data.

## 12. Temporal canary track

MRL should support a future sealed temporal-canary evaluation surface consisting only of
R2-compatible synthetic/hand-authored fixtures unless governance changes.

Canaries must:

- be created after the relevant training/data freeze;
- receive independent content identity;
- remain unavailable as training/search material;
- exercise updated guideline/version combinations, new FHIR compositions, or fresh
  adversarial combinations;
- never be silently recycled into later training data.

## 13. Research-agent benchmark

MRL must evaluate the researcher, not only the produced model.

Candidate meta-metrics:

- validated gain per GPU-hour;
- experiments to first replicated gain;
- invalid experiment rate;
- false-promotion rate;
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

## 14. Research-program registry reconciliation

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

## 15. Canonical project-state projection

Before autonomous research execution, MESC should expose machine-readable canonical
status projections, for example:

- `PROJECT_STATE.json`;
- `CAPABILITY_MATRIX.json`;
- `RESEARCH_PROGRAM_INDEX.json`.

These should be generated from canonical repository/spec state where practical.
Human-readable roadmap documents should become projections or explicitly dated
narratives rather than an independent operational truth source.

## 16. Security requirements

Before any real autonomous experiment execution:

- network is default-deny unless the exact run requires separately authorized access;
- no ambient credentials;
- no provider/model/data download authority implied by the agent loop;
- tool outputs and model outputs are treated as untrusted;
- execution environment must enforce allowed write paths;
- evaluator/sealed-data paths must be read-only or unavailable;
- all authority-bearing artifacts remain independently validated;
- failed/blocked attempts remain auditable.

## 17. Acceptance criteria for MRL V1 research substrate

The repository-side substrate is considered implementation-complete only when all are
true on an exact qualified head:

- canonical typed artifacts exist for objective, hypothesis, plan, receipt, decision,
  campaign, procedure, and procedure admission;
- deterministic canonical serialization and content hashing are tested;
- existing `ExperimentManifest` is reused rather than replaced;
- an allow-listed mutation policy rejects evaluator/governance/sealed-data mutation;
- a fixture-only campaign can propose, execute a bounded fake experiment, retain or
  reject, replicate, and close without real model/data/GPU access;
- an end-to-end negative test proves metric/evaluator tampering cannot produce a valid
  promotion;
- an end-to-end negative test proves sealed promotion data cannot be read during search;
- a procedure cannot become `ADMITTED` without replay + transfer + review evidence;
- resource-ceiling escape fails closed;
- raw-log prompt-injection content cannot become trusted control instructions through
  the structured observation interface;
- failed/null/invalid branches remain in canonical campaign history;
- project/RQ status reconciliation is explicit;
- CI, static typing, formatting, tests, and repository checks pass;
- no real training, provider/model download, PHI, credential, or release action is
  performed as part of qualification.

## 18. Future execution boundary

Connecting MRL to real model training is a separate future gate.

Real experimentation requires independently proven:

- model/corpus rights and exact identities;
- runtime/GPU qualification;
- applicable training authorization;
- campaign/objective freeze;
- evaluator and sealed-evaluation freeze;
- resource budget;
- execution sandbox;
- exact-head qualification.

No artifact in this planning package satisfies those conditions by itself.
