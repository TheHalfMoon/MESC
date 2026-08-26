# MESC Research Loop V1 — Task Ledger

Status: **PROPOSED TASK ORDER / NO EXECUTION AUTHORITY**

Task states:

```text
PLANNED
ELIGIBLE
IN_PROGRESS
BLOCKED
QUALIFYING
CLOSED_CANONICAL
```

A task becomes `ELIGIBLE` only when all declared dependencies and any separate authority
gates are satisfied by live repository truth.

## MRL-0 — Constitution and reconciliation

- [ ] **MRL-0001 — Freeze MRL/MCRL boundary**
  - Depends on: planning package acceptance.
  - Deliverable: ADR or equivalent canonical decision.
  - Acceptance: research-time and clinical-runtime learning paths cannot be conflated.

- [ ] **MRL-0002 — Freeze immutable evaluator rule**
  - Depends on: MRL-0001.
  - Acceptance: campaign agents cannot alter active evaluators, promotion rules, sealed
    evaluation data, governance, authorization, trust registries, or canonical history.

- [ ] **MRL-0003 — Freeze adaptive evaluation tiers**
  - Depends on: MRL-0002.
  - Acceptance: Tier 0 development, Tier 1 search, Tier 2 replication, Tier 3 sealed
    promotion, Tier 4 external/clinician assurance are semantically distinct.

- [ ] **MRL-0004 — Freeze medical promotion semantics**
  - Depends on: MRL-0003.
  - Acceptance: hard safety/reproducibility/contamination/subgroup floors precede
    capability/cost optimization; one scalar score cannot override a hard-gate failure.

- [ ] **MRL-0005 — Define campaign resource governance**
  - Depends on: MRL-0002.
  - Acceptance: compute/time/token/storage/cost/retry ceilings are frozen and cannot be
    self-expanded by an agent.

- [ ] **MRL-0006 — Reconcile research-program registry**
  - Depends on: MRL-0001.
  - Acceptance: foundational RQ1-RQ7 remain preserved while later MESC/MCRL/Arabic/AMGE/
    Omni/MRL questions receive explicit namespaces and status.

- [ ] **MRL-0007 — Define machine-readable project-state contract**
  - Depends on: MRL-0006.
  - Acceptance: operational status has one canonical machine-readable projection path;
    stale narrative roadmaps cannot silently override live spec state.

### MRL-0 gate

- [ ] **MRL-0099 — MRL constitution exact-head qualification**
  - Requires: MRL-0001..0007.
  - Evidence: exact-head review + repository checks.
  - Exit: `MRL_CONSTITUTION_FROZEN`.

---

## MRL-1 — Canonical research artifacts

- [ ] **MRL-0101 — Implement `ResearchObjectiveContract`**
  - Depends on: MRL-0099.
  - Test: deterministic canonical bytes/hash; immutable objective semantics.

- [ ] **MRL-0102 — Implement `ResearchHypothesis`**
  - Depends on: MRL-0101.
  - Test: mechanism, predicted effects, falsification criteria, evidence refs, parent
    relationships are required and content-addressed.

- [ ] **MRL-0103 — Implement `ResearchExperimentPlan`**
  - Depends on: MRL-0102.
  - Test: mutation allow-list, budget, evaluator identities, and evaluation tier are
    frozen before execution.

- [ ] **MRL-0104 — Bind existing `ExperimentManifest`**
  - Depends on: MRL-0103.
  - Acceptance: no duplicate competing runtime experiment manifest is introduced.

- [ ] **MRL-0105 — Implement `ResearchExperimentReceipt`**
  - Depends on: MRL-0104.
  - Test: plan/manifest/code/metrics/guardrail/resource identities cannot be mismatched.

- [ ] **MRL-0106 — Implement `ResearchDecision`**
  - Depends on: MRL-0105.
  - Required states: INVALID, REJECT, REPLICATE, RETAIN_LEAD, PROMOTION_CANDIDATE,
    PROMOTED, BLOCKED.
  - Test: promotion candidate cannot be interpreted as promotion.

- [ ] **MRL-0107 — Implement `ResearchCampaign` DAG**
  - Depends on: MRL-0106.
  - Test: failed/null/invalid branches remain canonical; reference integrity enforced.

- [ ] **MRL-0108 — Implement `ResearchProcedure` and admission report types**
  - Depends on: MRL-0107.
  - Test: procedure cannot claim `ADMITTED` without an admission report satisfying all
    lifecycle stages.

### MRL-1 gate

- [ ] **MRL-0199 — Artifact-core exact-head qualification**
  - Requires: MRL-0101..0108.
  - Gates: Ruff, format, strict mypy, focused tests, full pytest/coverage, `medscale check`,
    security review where applicable.
  - Exit: `MRL_ARTIFACT_CORE_READY`.

---

## MRL-2 — Fixture-only governed loop

- [ ] **MRL-0201 — Build deterministic fixture research surface**
  - Depends on: MRL-0199.
  - Constraint: no real model/data/network/GPU/training.

- [ ] **MRL-0202 — Build allow-listed mutation policy**
  - Depends on: MRL-0201.
  - Negative tests: evaluator/governance/sealed-data/authorization/trust paths rejected.

- [ ] **MRL-0203 — Build structured observation envelope**
  - Depends on: MRL-0201.
  - Acceptance: raw stdout/stderr is not automatically treated as trusted control input.

- [ ] **MRL-0204 — Implement fixture propose/run/receipt/decision loop**
  - Depends on: MRL-0202, MRL-0203.

- [ ] **MRL-0205 — Implement replication and retained-lead behavior**
  - Depends on: MRL-0204.

- [ ] **MRL-0206 — Add metric-tampering adversarial test**
  - Depends on: MRL-0204.
  - Must prove: agent-controlled metric fabrication/evaluator modification cannot produce
    valid promotion evidence.

- [ ] **MRL-0207 — Add sealed-data access adversarial test**
  - Depends on: MRL-0204.
  - Must prove: search process cannot read Tier 3 item-level content.

- [ ] **MRL-0208 — Add resource-budget escape test**
  - Depends on: MRL-0204.

- [ ] **MRL-0209 — Add raw-log prompt-injection test**
  - Depends on: MRL-0203.

- [ ] **MRL-0210 — Add stale/mismatched receipt tests**
  - Depends on: MRL-0204.

- [ ] **MRL-0211 — Add known-failure retry ceiling**
  - Depends on: MRL-0205.

### MRL-2 gate

- [ ] **MRL-0299 — Fixture loop exact-head qualification**
  - Requires: MRL-0201..0211.
  - Exit: `MRL_FIXTURE_LOOP_PROVEN`.

---

## MRL-3 — Adaptive evaluation and promotion control

- [ ] **MRL-0301 — Implement tier-aware evaluation contract**
  - Depends on: MRL-0299.

- [ ] **MRL-0302 — Implement bounded search-result exposure**
  - Depends on: MRL-0301.

- [ ] **MRL-0303 — Implement replication-set policy**
  - Depends on: MRL-0301.

- [ ] **MRL-0304 — Implement sealed promotion interface**
  - Depends on: MRL-0301.
  - Negative test: item-level sealed evidence never enters search context.

- [ ] **MRL-0305 — Implement independent promotion report**
  - Depends on: MRL-0304.

- [ ] **MRL-0306 — Implement hard medical non-regression gates**
  - Depends on: MRL-0305.

- [ ] **MRL-0307 — Implement Pareto/multi-objective comparison**
  - Depends on: MRL-0306.
  - Acceptance: aggregate gains cannot hide hard-gate regressions.

- [ ] **MRL-0308 — Add adaptive-query/campaign accounting**
  - Depends on: MRL-0302.

### MRL-3 gate

- [ ] **MRL-0399 — Promotion-control exact-head qualification**
  - Requires: MRL-0301..0308.
  - Exit: `MRL_PROMOTION_CONTROL_READY`.

---

## MRL-4 — Governed research memory

- [ ] **MRL-0401 — Build append-only campaign-history projection**
  - Depends on: MRL-0399.

- [ ] **MRL-0402 — Build procedure-candidate extraction interface**
  - Depends on: MRL-0401.

- [ ] **MRL-0403 — Build procedure replay harness**
  - Depends on: MRL-0402.

- [ ] **MRL-0404 — Build procedure transfer-test contract**
  - Depends on: MRL-0403.

- [ ] **MRL-0405 — Build negative/failure-control contract**
  - Depends on: MRL-0403.

- [ ] **MRL-0406 — Build procedure admission gate**
  - Depends on: MRL-0404, MRL-0405.
  - Lifecycle: DISCOVERED -> CANDIDATE -> REPLAYED -> TRANSFER_TESTED -> REVIEWED ->
    ADMITTED.

- [ ] **MRL-0407 — Build admitted/rejected/superseded procedure registry**
  - Depends on: MRL-0406.

- [ ] **MRL-0408 — Build rebuildable non-authoritative procedure search index**
  - Depends on: MRL-0407.

- [ ] **MRL-0409 — Compare memory vs no-memory fixture research cost**
  - Depends on: MRL-0408.
  - Acceptance: demonstrate a reproducible efficiency gain without increased invalid or
    false-promotion behavior.

### MRL-4 gate

- [ ] **MRL-0499 — Procedure-memory exact-head qualification**
  - Requires: MRL-0401..0409.
  - Exit: `MRL_PROCEDURE_MEMORY_READY`.

---

## MRL-5 — Portfolio research and researcher benchmark

- [ ] **MRL-0501 — Implement campaign frontier/portfolio policy**
  - Depends on: MRL-0499.

- [ ] **MRL-0502 — Implement retained-alternative branches**
  - Depends on: MRL-0501.

- [ ] **MRL-0503 — Implement replication branch semantics**
  - Depends on: MRL-0501.

- [ ] **MRL-0504 — Implement failure-signature deduplication**
  - Depends on: MRL-0501.

- [ ] **MRL-0505 — Implement research-agent benchmark harness**
  - Depends on: MRL-0502..0504.

- [ ] **MRL-0506 — Benchmark stateless researcher**
  - Depends on: MRL-0505.

- [ ] **MRL-0507 — Benchmark history-only researcher**
  - Depends on: MRL-0505.

- [ ] **MRL-0508 — Benchmark admitted-procedure-memory researcher**
  - Depends on: MRL-0505.

- [ ] **MRL-0509 — Benchmark portfolio/tree-search researcher**
  - Depends on: MRL-0505.

- [ ] **MRL-0510 — Publish deterministic researcher comparison report**
  - Depends on: MRL-0506..0509.

### MRL-5 gate

- [ ] **MRL-0599 — Researcher-evaluation exact-head qualification**
  - Requires: MRL-0501..0510.
  - Exit: `MRL_RESEARCHER_EVAL_READY`.

---

## MRL-6 — Contamination lineage and temporal canaries

- [ ] **MRL-0601 — Define training-example lineage contract**
  - Depends on: MRL-0399.

- [ ] **MRL-0602 — Add exact/near/semantic contamination interfaces**
  - Depends on: MRL-0601.

- [ ] **MRL-0603 — Add teacher/prompt/source transformation bindings**
  - Depends on: MRL-0601.

- [ ] **MRL-0604 — Add benchmark-derived-generation flags**
  - Depends on: MRL-0602, MRL-0603.

- [ ] **MRL-0605 — Define temporal-canary manifest**
  - Depends on: MRL-0601.

- [ ] **MRL-0606 — Build R2-compatible sealed canary fixture workflow**
  - Depends on: MRL-0605.
  - Constraint: synthetic/hand-authored only under current R2.

- [ ] **MRL-0607 — Enforce no canary recycling into training/search**
  - Depends on: MRL-0606.

### MRL-6 gate

- [ ] **MRL-0699 — Contamination-v2 exact-head qualification**
  - Requires: MRL-0601..0607.
  - Exit: `MRL_CONTAMINATION_V2_READY`.

---

## MRL-7 — Machine-readable project state

- [ ] **MRL-0701 — Implement `RESEARCH_PROGRAM_INDEX.json` projection**
  - Depends on: MRL-0006.

- [ ] **MRL-0702 — Implement `CAPABILITY_MATRIX.json` projection**
  - Depends on: MRL-0007.

- [ ] **MRL-0703 — Implement `PROJECT_STATE.json` projection**
  - Depends on: MRL-0701, MRL-0702.

- [ ] **MRL-0704 — Add deterministic generation/check command**
  - Depends on: MRL-0703.

- [ ] **MRL-0705 — Add CI drift check**
  - Depends on: MRL-0704.

- [ ] **MRL-0706 — Reconcile human-readable roadmap status**
  - Depends on: MRL-0705.
  - Acceptance: roadmap is explicitly explanatory/projection-based, not a competing live
    state authority.

### MRL-7 gate

- [ ] **MRL-0799 — Machine-state exact-head qualification**
  - Requires: MRL-0701..0706.
  - Exit: `MESC_MACHINE_STATE_READY`.

---

## MRL-8 — Real autonomous research preflight

- [ ] **MRL-0801 — Verify exact model/weights evidence**
  - Depends on: separate real-asset authorization/evidence.

- [ ] **MRL-0802 — Verify corpus rights and exact identity**
  - Depends on: separate real-asset authorization/evidence.

- [ ] **MRL-0803 — Verify contamination and held-out isolation evidence**
  - Depends on: MRL-0699 and actual corpus evidence.

- [ ] **MRL-0804 — Verify runtime/GPU qualification**
  - Depends on: real runtime evidence.

- [ ] **MRL-0805 — Verify applicable training authorization**
  - Depends on: independent authority artifact/trust path.

- [ ] **MRL-0806 — Freeze real research objective and budget**
  - Depends on: MRL-0599 plus selected real experiment.

- [ ] **MRL-0807 — Freeze evaluator and sealed promotion identities**
  - Depends on: MRL-0399 plus real evaluation assets.

- [ ] **MRL-0808 — Verify real execution sandbox**
  - Depends on: MRL-0299 and runtime evidence.

- [ ] **MRL-0809 — Exact-head preflight qualification**
  - Depends on: MRL-0801..0808.

### MRL-8 gate

- [ ] **MRL-0899 — Decide `MRL_REAL_EXPERIMENT_READY`**
  - Must fail closed unless all real evidence exists.
  - This task cannot fabricate model/corpus/GPU/founder/operator evidence.

---

## Permanent status distinctions

Never collapse these states:

```text
MRL_ARTIFACT_CORE_READY
MRL_FIXTURE_LOOP_PROVEN
MRL_PROMOTION_CONTROL_READY
MRL_PROCEDURE_MEMORY_READY
MRL_RESEARCHER_EVAL_READY
MRL_CONTAMINATION_V2_READY
MESC_MACHINE_STATE_READY
MRL_REAL_EXPERIMENT_READY
TRAINING_CODE_READY
TRAINING_READY
TRAINING_EXECUTION_COMPLETE
RELEASE_READY
```

Each requires its own exact evidence.
