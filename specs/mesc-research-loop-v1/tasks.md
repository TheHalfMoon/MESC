# MESC Research Loop V1 — Task Ledger

Status: **CANONICAL TASK ORDER / MRL-0 CLOSEOUT CANDIDATE / NO EXECUTION AUTHORITY**

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

On an unmerged branch, an `[x]` in the MRL-0 closeout block records the intended canonical
closeout candidate only. It does not by itself establish `CLOSED_CANONICAL`. MRL-0 closure
attaches only if the final closeout head passes fresh exact-head repository checks and
independent governance review, remains the exact PR head through expected-head merge, and
is then present on canonical `main`. Any head mutation burns prior exact-head evidence.

## MRL-0 — Constitution and reconciliation

- [x] **MRL-0001 — Freeze MRL/MCRL boundary**
  - Depends on: planning package acceptance.
  - Deliverable: ADR or equivalent canonical decision.
  - Acceptance: research-time and clinical-runtime learning paths cannot be conflated.

- [x] **MRL-0002 — Freeze immutable evaluator rule**
  - Depends on: MRL-0001.
  - Acceptance: campaign agents cannot alter active evaluators, evaluation rules, sealed
    data, governance, authorization, trust registries, canonical history, or CI/security
    qualification gates.

- [x] **MRL-0003 — Freeze adaptive evaluation tiers**
  - Depends on: MRL-0002.
  - Acceptance: Tier 0 development, Tier 1 search, Tier 2 replication, Tier 3 sealed
    evaluation, and Tier 4 external/clinician assurance are semantically distinct.

- [x] **MRL-0004 — Freeze evidence semantics and promotion deferral**
  - Depends on: MRL-0003.
  - Acceptance: hard safety/reproducibility/contamination/subgroup floors precede
    capability/cost optimization.
  - Acceptance: ADR-0033 remains controlling; MRL V1 cannot implement `PromotionDecision`,
    `PROMOTED`, or an equivalent model-promotion authority. Its highest positive research
    outcome is non-authoritative `EVIDENCE_CANDIDATE`.

- [x] **MRL-0005 — Define campaign resource and adaptive-query governance**
  - Depends on: MRL-0002, MRL-0003.
  - Acceptance: compute/time/token/storage/cost/retry/query/result-exposure ceilings are
    frozen and cannot be self-expanded by an agent.
  - Acceptance: exhaustion has an explicit fail-closed `BLOCKED` disposition.

- [x] **MRL-0006 — Reconcile research-program registry**
  - Depends on: MRL-0001.
  - Acceptance: foundational RQ1-RQ7 remain preserved while later MESC/MCRL/Arabic/AMGE/
    Omni/MRL questions receive explicit namespaces and status.

- [x] **MRL-0007 — Define machine-readable project-state contract**
  - Depends on: MRL-0006.
  - Acceptance: projections are deterministic derived views bound to an exact repository
    commit and canonical source hashes; stale/manual projections cannot authorize work.

- [x] **MRL-0008 — Freeze research-input admission policy**
  - Depends on: MRL-0001.
  - Acceptance: PHI, product telemetry, and clinical-runtime state cannot enter MRL
    observation, history, procedure extraction, or indexes as learning signals.
  - Acceptance: MCRL outputs remain outside the MRL learning path and may be consumed only
    as separately authorized external evaluation evidence where governance permits.

### MRL-0 gate

- [x] **MRL-0099 — MRL constitution exact-head qualification**
  - Requires: MRL-0001..0008.
  - Evidence: exact-head review + repository checks.
  - Closeout rule: this checkbox is a branch closeout candidate until the exact final head
    containing it passes fresh CI, CodeQL, internal governance review, Qodo review,
    CodeRabbit status/review, and unresolved-thread checks, then merges with expected-head
    protection to canonical `main`.
  - Exit after canonical merge: `MRL_CONSTITUTION_FROZEN`.

---

## MRL-1 — Canonical research artifacts

- [x] **MRL-0100 — Implement canonical content-identity primitive**
  - Depends on: MRL-0099.
  - Test: deterministic canonical semantic bytes.
  - Test: `content_sha256` is derived outside its own preimage; no self-referential hash.
  - Closeout rule: this checkbox is a branch closeout candidate only. `MRL-0100` becomes
    `CLOSED_CANONICAL` only if the exact final head containing it passes fresh repository
    checks and independent review, remains the exact PR head through expected-head merge,
    and is then present on canonical `main`.
  - Eligibility effect: MRL-0101 remains ineligible until that canonical merge.

- [x] **MRL-0101 — Implement `ResearchObjectiveContract`**
  - Depends on: MRL-0100.
  - Test: immutable objective semantics, resource/query/result-exposure budgets, evaluator
    identities, and evidence floors are content-addressed.
  - Closeout rule: this checkbox is a branch closeout candidate only. `MRL-0101` becomes
    `CLOSED_CANONICAL` only if the exact final head containing it passes fresh repository
    checks and independent review, remains the exact PR head through expected-head merge,
    and is then present on canonical `main`.
  - Eligibility effect: MRL-0102 remains ineligible until that canonical merge.

- [x] **MRL-0102 — Implement `ResearchHypothesis`**
  - Depends on: MRL-0101.
  - Test: mechanism, predicted effects, falsification criteria, evidence refs, and parent
    relationships are required and content-addressed.
  - Closeout rule: this checkbox is a branch closeout candidate only. `MRL-0102` becomes
    `CLOSED_CANONICAL` only if the exact final head containing it passes fresh repository
    checks and independent review, remains the exact PR head through expected-head merge,
    and is then present on canonical `main`.
  - Eligibility effect: MRL-0103 remains ineligible until MRL-0109 is also
    `CLOSED_CANONICAL` on canonical `main`.

- [x] **MRL-0103 — Implement `ResearchExperimentPlan`**
  - Depends on: MRL-0102, MRL-0109.
  - Test: mutation allow-list, budget, evaluator identities, evaluation tier, and exposure
    allowance are frozen before execution.
  - Closeout rule: this checkbox is a branch closeout candidate only. `MRL-0103` becomes
    `CLOSED_CANONICAL` only if the exact final head containing it passes fresh repository
    checks and independent review, remains the exact PR head through expected-head merge,
    and is then present on canonical `main`.
  - Eligibility effect: MRL-0104 remains ineligible until MRL-0103 is
    `CLOSED_CANONICAL` on canonical `main`.

- [x] **MRL-0104 — Bind existing `ExperimentManifest`**
  - Depends on: MRL-0103.
  - Acceptance: no duplicate competing runtime experiment manifest is introduced.

- [x] **MRL-0105 — Implement `ResearchExperimentReceipt`**
  - Depends on: MRL-0104.
  - Test: plan/manifest/code/metrics/guardrail/resource/tier accounting identities cannot
    be mismatched.

- [x] **MRL-0106 — Implement `ResearchDecision`**
  - Depends on: MRL-0105.
  - Required states: INVALID, REJECT, REPLICATE, RETAIN_LEAD, EVIDENCE_CANDIDATE, BLOCKED.
  - Test: `EVIDENCE_CANDIDATE` cannot be interpreted as model promotion.
  - Negative test: `PROMOTED` and equivalent promotion-authority states are rejected.

- [x] **MRL-0107 — Implement `ResearchCampaign` DAG**
  - Depends on: MRL-0106.
  - Test: failed/null/invalid branches remain canonical; reference integrity enforced.
  - Test: cumulative resource/query/result-exposure accounting cannot move backward.

- [x] **MRL-0108 — Implement `ResearchProcedure` and admission report types**
  - Depends on: MRL-0107.
  - Test: procedure cannot claim `REVIEWED`/`ADMITTED` without replay evidence,
    representative transfer evidence, negative controls, typed applicability bounds, and
    an independent immutable review receipt.
  - Test: research/campaign agent cannot self-admit a procedure.

- [x] **MRL-0109 — Implement `ResearchInputAdmissionContract`**
  - Depends on: MRL-0100.
  - Test: research artifacts and separately authorized external evaluation evidence are
    distinguishable from rejected PHI/product/clinical-runtime learning inputs.
  - Test: MRL observation/history/procedure/index admission fails closed on rejected input.
  - Closeout rule: this checkbox is a branch closeout candidate only. `MRL-0109` becomes
    `CLOSED_CANONICAL` only if the exact final head containing it passes fresh repository
    checks and independent review, remains the exact PR head through expected-head merge,
    and is then present on canonical `main`.
  - Eligibility effect: MRL-0103 remains ineligible until that canonical merge.

### MRL-1 gate

- [x] **MRL-0199 — Artifact-core exact-head qualification**
  - Requires: MRL-0100..0109.
  - Gates: Ruff, format, strict mypy, focused tests, full pytest/coverage, `medscale check`,
    and security/governance review where applicable.
  - Exit: `MRL_ARTIFACT_CORE_READY`.

---

## MRL-2 — Fixture-only governed loop

- [x] **MRL-0201 — Build deterministic fixture research surface**
  - Depends on: MRL-0199.
  - Constraint: no real model/data/network/GPU/training.

- [x] **MRL-0202 — Build allow-listed mutation policy**
  - Depends on: MRL-0201.
  - Negative tests: evaluator/governance/sealed-data/authorization/trust/machine-state
    authority paths rejected.

- [x] **MRL-0203 — Build structured observation envelope**
  - Depends on: MRL-0201, MRL-0109.
  - Acceptance: raw stdout/stderr is not automatically treated as trusted control input.

- [x] **MRL-0204 — Implement fixture propose/run/receipt/decision loop**
  - Depends on: MRL-0202, MRL-0203.

- [x] **MRL-0205 — Implement replication and retained-lead behavior**
  - Depends on: MRL-0204.
- [x] **MRL-0206 — Add metric-tampering adversarial test**
  - Depends on: MRL-0204.
  - Must prove: agent-controlled metric fabrication/evaluator modification cannot produce
    valid sealed evidence or an authority-bearing state.

- [x] **MRL-0207 — Add sealed-data access adversarial test**
  - Depends on: MRL-0204.
  - Must prove: search process cannot read Tier 3 item-level content.

- [x] **MRL-0208 — Add resource/adaptive-budget escape test**
  - Depends on: MRL-0204.
  - Must prove: compute/query/result-exposure ceilings cannot be self-expanded.

- [x] **MRL-0209 — Add raw-log prompt-injection test**
  - Depends on: MRL-0203.

- [x] **MRL-0210 — Add stale/mismatched receipt tests**
  - Depends on: MRL-0204.

- [x] **MRL-0211 — Add known-failure retry ceiling**
  - Depends on: MRL-0205.

- [x] **MRL-0212 — Add forbidden research-input integration tests**
  - Depends on: MRL-0203.
  - Must prove: PHI, product telemetry, and clinical-runtime state cannot enter MRL
    observation, campaign history, procedure extraction, or search indexes.

- [x] **MRL-0213 — Add authority-fabrication negative tests**
  - Depends on: MRL-0204.
  - Must prove: fixture agent cannot construct `PROMOTED`, self-review, or self-admit a
    procedure.

### MRL-2 gate

- [x] **MRL-0299 — Fixture loop exact-head qualification**
  - Requires: MRL-0201..0213.
  - Exit: `MRL_FIXTURE_LOOP_PROVEN`.

---

## MRL-3 — Adaptive evaluation and sealed-evidence control

- [x] **MRL-0301 — Implement tier-aware evaluation contract**
  - Depends on: MRL-0299.

- [x] **MRL-0302 — Implement bounded Tier 1 result exposure**
  - Depends on: MRL-0301.
  - Acceptance: exact allowed aggregate fields and query/exposure budget are frozen.

- [x] **MRL-0303 — Implement replication-set policy**
  - Depends on: MRL-0301.
  - Acceptance: Tier 2 aggregate summaries and exposure budget are frozen and narrower
    than Tier 1 where required.

- [x] **MRL-0304 — Implement sealed Tier 3 evaluation interface**
  - Depends on: MRL-0301.
  - Negative test: item-level sealed evidence never enters search context.
  - Acceptance: no iterative agent-consumable result stream.

- [x] **MRL-0305 — Implement independent sealed-evaluation evidence report**
  - Depends on: MRL-0304.
  - Acceptance: report is evidence only and cannot encode `PROMOTED` or another promotion
    decision reserved by ADR-0033.

- [x] **MRL-0306 — Implement hard medical non-regression gates**
  - Depends on: MRL-0305.

- [x] **MRL-0307 — Implement Pareto/multi-objective comparison**
  - Depends on: MRL-0306.
  - Acceptance: aggregate gains cannot hide hard-gate regressions.

- [x] **MRL-0308 — Add adaptive-query/campaign accounting**
  - Depends on: MRL-0302, MRL-0303.

- [x] **MRL-0309 — Enforce adaptive-budget exhaustion**
  - Depends on: MRL-0308.
  - Acceptance: exhausted tier becomes `BLOCKED` for further adaptive use; the agent cannot
    amend the frozen objective or request additional sealed detail.

### MRL-3 gate

- [ ] **MRL-0399 — Evaluation-control exact-head qualification**
  - Requires: MRL-0301..0309.
  - Exit: `MRL_EVALUATION_CONTROL_READY`.

---

## MRL-4 — Governed research memory

- [x] **MRL-0401 — Build append-only campaign-history projection**
  - Depends on: MRL-0399.

- [x] **MRL-0402 — Build procedure-candidate extraction interface**
  - Depends on: MRL-0401, MRL-0109.

- [x] **MRL-0403 — Build procedure replay harness**
  - Depends on: MRL-0402.

- [x] **MRL-0404 — Build representative procedure transfer-test contract**
  - Depends on: MRL-0403.

- [x] **MRL-0405 — Build negative/failure-control contract**
  - Depends on: MRL-0403.

- [x] **MRL-0406 — Build independent procedure admission gate**
  - Depends on: MRL-0404, MRL-0405.
  - Lifecycle: DISCOVERED -> CANDIDATE -> REPLAYED -> TRANSFER_TESTED -> REVIEWED ->
    ADMITTED.
  - Acceptance: non-agent reviewer/operator identity and immutable review receipt required
    for `REVIEWED`/`ADMITTED`.
  - Acceptance: typed applicability bounds are mandatory.

- [x] **MRL-0407 — Build admitted/rejected/superseded/invalidated procedure registry**
  - Depends on: MRL-0406.
  - Acceptance: later known failure or boundary violation can invalidate/supersede without
    deleting historical admission evidence.

- [x] **MRL-0408 — Build rebuildable non-authoritative procedure search index**
  - Depends on: MRL-0407, MRL-0109.
  - Acceptance: index enforces research-input admission and is never canonical authority.

- [x] **MRL-0409 — Compare memory vs no-memory fixture research cost**
  - Depends on: MRL-0408.
  - Acceptance: demonstrate a reproducible efficiency gain without increased invalid or
    false-evidence-candidate behavior.

### MRL-4 gate

- [x] **MRL-0499 — Procedure-memory exact-head qualification**
  - Requires: MRL-0401..0409.
  - Exit: `MRL_PROCEDURE_MEMORY_READY`.

---

## MRL-5 — Portfolio research and researcher benchmark

- [x] **MRL-0501 — Implement campaign frontier/portfolio policy**
  - Depends on: MRL-0499.

- [x] **MRL-0502 — Implement retained-alternative branches**
  - Depends on: MRL-0501.

- [x] **MRL-0503 — Implement replication branch semantics**
  - Depends on: MRL-0501.

- [x] **MRL-0504 — Implement failure-signature deduplication**
  - Depends on: MRL-0501.

- [x] **MRL-0505 — Implement research-agent benchmark harness**
  - Depends on: MRL-0502..0504.

- [x] **MRL-0506 — Benchmark stateless researcher**
  - Depends on: MRL-0505.

- [x] **MRL-0507 — Benchmark history-only researcher**
  - Depends on: MRL-0505.

- [x] **MRL-0508 — Benchmark admitted-procedure-memory researcher**
  - Depends on: MRL-0505.

- [x] **MRL-0509 — Benchmark portfolio/tree-search researcher**
  - Depends on: MRL-0505.

- [x] **MRL-0510 — Publish deterministic researcher comparison report**
  - Depends on: MRL-0506..0509.

### MRL-5 gate

- [x] **MRL-0599 — Researcher-evaluation exact-head qualification**
  - Requires: MRL-0501..0510.
  - Exit: `MRL_RESEARCHER_EVAL_READY`.

---

## MRL-6 — Contamination lineage and temporal canaries

- [x] **MRL-0601 — Define training-example lineage contract**
  - Depends on: MRL-0399.

- [x] **MRL-0602 — Add exact/near/semantic contamination interfaces**
  - Depends on: MRL-0601.

- [x] **MRL-0603 — Add teacher/prompt/source transformation bindings**
  - Depends on: MRL-0601.

- [x] **MRL-0604 — Add benchmark-derived-generation flags**
  - Depends on: MRL-0602, MRL-0603.

- [x] **MRL-0605 — Define temporal-canary manifest**
  - Depends on: MRL-0601.

- [x] **MRL-0606 — Build R2-compatible sealed canary fixture workflow**
  - Depends on: MRL-0605.
  - Constraint: synthetic/hand-authored only under current R2.

- [x] **MRL-0607 — Enforce no canary recycling into training/search**
  - Depends on: MRL-0606.

### MRL-6 gate
- [x] **MRL-0699 — Contamination-v2 exact-head qualification**
  - Requires: MRL-0601..0607.
  - Exit: `MRL_CONTAMINATION_V2_READY`.
  - Real MRL preflight may not bypass this gate.

---

## MRL-7 — Machine-readable project state

- [x] **MRL-0701 — Implement `RESEARCH_PROGRAM_INDEX.json` projection**
  - Depends on: MRL-0006.

- [x] **MRL-0702 — Implement `CAPABILITY_MATRIX.json` projection**
  - Depends on: MRL-0007.

- [x] **MRL-0703 — Implement `PROJECT_STATE.json` projection**
  - Depends on: MRL-0701, MRL-0702.

- [x] **MRL-0704 — Add deterministic generation/check command**
  - Depends on: MRL-0703.
  - Acceptance: projections bind exact repository commit plus canonical source hashes.

- [x] **MRL-0705 — Add CI drift and manual-edit check**
  - Depends on: MRL-0704.
  - Acceptance: stale or manually edited projections fail closed.

- [x] **MRL-0706 — Reconcile human-readable roadmap status**
  - Depends on: MRL-0705.
  - Acceptance: roadmap is explanatory, not a competing live state authority.

- [x] **MRL-0707 — Add projection-precedence adversarial test**
  - Depends on: MRL-0705, MRL-0706.
  - Must prove: when narrative, projection, and canonical gate evidence conflict,
    downstream eligibility rejects stale projection/narrative claims and follows live
    canonical gate evidence.

### MRL-7 gate

- [ ] **MRL-0799 — Machine-state exact-head qualification**
  - Requires: MRL-0701..0707.
  - Exit: `MESC_MACHINE_STATE_READY`.

---

## MRL-8 — Real autonomous research preflight

All MRL repository-side gates below are mandatory. There is no optional MRL-6 bypass.
No task that reads, verifies, or accesses real model, corpus, runtime, GPU, sandbox, or
training-authorization evidence may begin before MRL-0800 is `CLOSED_CANONICAL`.

- [ ] **MRL-0800 — Enter real autonomous research preflight**
  - Depends on: MRL-0299, MRL-0399, MRL-0499, MRL-0599, MRL-0699, MRL-0799, and current
    training/runtime governance.
  - Acceptance: `MRL_FIXTURE_LOOP_PROVEN`, `MRL_EVALUATION_CONTROL_READY`,
    `MRL_PROCEDURE_MEMORY_READY`, `MRL_RESEARCHER_EVAL_READY`,
    `MRL_CONTAMINATION_V2_READY`, and `MESC_MACHINE_STATE_READY` are all proven by live
    canonical exact-head evidence.
  - Acceptance: this entry gate grants no model/data/runtime/GPU/training authority by
    itself; each later task still requires its own external evidence/authority.
  - Exit: `MRL_REAL_PREFLIGHT_ENTERED`.

- [ ] **MRL-0801 — Verify exact model/weights evidence**
  - Depends on: MRL-0800 and separate real-asset authorization/evidence.

- [ ] **MRL-0802 — Verify corpus rights and exact identity**
  - Depends on: MRL-0800 and separate real-asset authorization/evidence.

- [ ] **MRL-0803 — Verify contamination and held-out isolation evidence**
  - Depends on: MRL-0800, MRL-0699, and actual corpus/evaluation evidence.

- [ ] **MRL-0804 — Verify runtime/GPU qualification**
  - Depends on: MRL-0800 and real runtime evidence.

- [ ] **MRL-0805 — Verify applicable training authorization**
  - Depends on: MRL-0800, independent authority artifact/trust path, and current training
    governance.

- [ ] **MRL-0806 — Freeze real research objective and all budgets**
  - Depends on: MRL-0800 plus selected real experiment.
  - Acceptance: compute/resource/adaptive-query/result-exposure budgets are exact and
    externally frozen.

- [ ] **MRL-0807 — Freeze evaluator and sealed Tier 3 identities**
  - Depends on: MRL-0800 plus real evaluation assets.
  - Acceptance: evidence contract remains non-promotional; model promotion is outside MRL
    pending the dedicated ADR required by ADR-0033.

- [ ] **MRL-0808 — Verify real execution sandbox**
  - Depends on: MRL-0800 and real runtime/sandbox evidence.

- [ ] **MRL-0809 — Exact-head preflight qualification**
  - Depends on: MRL-0801..0808 and MRL-0800.
  - Acceptance: current machine-state projection is bound to the exact candidate commit
    and cannot substitute for underlying canonical gate evidence.

### MRL-8 gate

- [ ] **MRL-0899 — Decide `MRL_REAL_EXPERIMENT_READY`**
  - Depends on: MRL-0809.
  - Must fail closed unless all real evidence exists.
  - This task cannot fabricate model/corpus/GPU/founder/operator evidence.
  - This task cannot declare model promotion or replace future promotion authority.

---

## Permanent status distinctions

Never collapse these states:

```text
MRL_ARTIFACT_CORE_READY
MRL_FIXTURE_LOOP_PROVEN
MRL_EVALUATION_CONTROL_READY
MRL_PROCEDURE_MEMORY_READY
MRL_RESEARCHER_EVAL_READY
MRL_CONTAMINATION_V2_READY
MESC_MACHINE_STATE_READY
MRL_REAL_PREFLIGHT_ENTERED
MRL_REAL_EXPERIMENT_READY
TRAINING_CODE_READY
TRAINING_READY
TRAINING_EXECUTION_COMPLETE
RELEASE_READY
```

Also permanent:

```text
EVIDENCE_CANDIDATE != PROMOTED
MRL_REAL_PREFLIGHT_ENTERED != MRL_REAL_EXPERIMENT_READY
MRL_REAL_EXPERIMENT_READY != TRAINING_READY
```

`PROMOTED` is not an MRL V1 state. Promotion ownership/evidence remains deferred to the
dedicated ADR required by canonical ADR-0033.

Each listed state requires its own exact evidence.