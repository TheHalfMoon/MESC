# Implementation backlog

- **Status:** Proposed delivery units; all tasks below remain open.
- **Date:** 2026-09-09.
- **Parent:** [implementation roadmap](implementation_roadmap_2026-09-09.md).

This is a planning decomposition, not a second canonical execution ledger. Before each
task, map it to the existing applicable spec and record exact dependencies there. New
irreversible architecture decisions follow R6. Owners below are roles to assign, not
claims that reviewers or staff have been recruited. Founder owns prioritization and task
assignment. One task per session; acceptance includes the executed command output and
artifact identity. Proposed test filenames below do not exist until their tasks implement them.

## MS-01 — One complete synthetic verification walkthrough

- **Priority / effort / owner:** P0; 2–4 days; toolkit maintainer.
- **Dependencies:** none for source inspection and model-free implementation; reuse existing
  package APIs and accepted synthetic fixtures.
- **Deliver:** `examples/synthetic_verification/` with synthetic input, recorded output,
  expected report and a runnable Python entry point; add a task-first guide linked from
  README. Clearly label cached fixture output and the checks actually performed.
- **Reuse:** `src/medscale/fhirkit`, `src/medscale/bench`, current replay/report contracts.
  Inspect existing examples first; extend a matching example instead of duplicating it.
- **Acceptance:** successful example emits a reproducible report; a deliberately unsupported
  field or corrupted artifact fails; missing optional validator reports unavailable; no
  model download or credentials; second run yields the same canonical identity.
- **Verification:** `uv run python examples/synthetic_verification/run.py` and proposed
  `uv run pytest -q tests/test_synthetic_verification_example.py`; run docs-link check.
- **Done evidence:** both run hashes, negative-case output and guide; record independent
  first-use timings at MS-09. A fixture pass is not a model-performance result.

## MS-02 — Frozen task, gold and comparison contracts

- **Priority / effort / owner:** P0; 5–8 days; benchmark maintainer plus independent bilingual
  domain reviewers for semantic gold.
- **Dependencies:** MS-01; applicable benchmark spec and API stability review.
- **Deliver:** versioned task/envelope mapping for the roadmap's proposed fields; synthetic
  corpus generation manifest, source/scenario splits, label map, abstention policy and metric
  denominators. Begin with 100 development scenarios spanning the listed failure classes;
  this is a fixture target, not a statistically powered final benchmark.
- **Gold:** two independent reviewers annotate semantic targets; adjudicate disagreements
  before freeze. Track reviewer provenance and agreement. A translator or teacher cannot
  grade its own outputs. Deterministic fixture gold covers engineering checks only.
- **Evaluation:** development-only pilot estimates variance and determines final grouped
  sample size and non-inferiority margins before evaluation. Freeze seeds, bootstrap method,
  primary endpoint, missing-output policy and evaluator identities in the applicable spec.
- **Acceptance:** duplicates/translations cannot cross splits; source offsets round-trip;
  a zero-output system scores zero recall; oracle and intentionally wrong systems produce
  expected metrics; unsupported slices yield inconclusive rather than fabricated scores.
- **Verification:** existing `uv run pytest -q tests/test_bench_tasks.py tests/test_bench_engine.py
  tests/test_bench_replay.py` plus proposed `tests/test_clinical_comparison_contract.py`.
- **Done evidence:** reviewed contract, fixture rights/split manifests and metric test outputs.

## MS-03 — Supported FHIR generation and semantic verification

- **Priority / effort / owner:** P0; 6–10 days; FHIR maintainer.
- **Dependencies:** MS-02; canonical T2/spec eligibility and any required architecture decision.
- **Deliver:** the roadmap's explicit R4 subset, grammar artifact/identity, resource reference
  checks and field-to-source support ledger through existing FHIR/modelkit boundaries.
  Choose one qualified grammar backend first; record the choice in the applicable spec.
- **Acceptance:** enforce grammar or raise on unsupported backend; reject truncation and
  unsupported profiles; distinguish syntactic success from incorrect negation, subject,
  dose/unit, chronology or invented fields. External validation uses a pinned locally
  provisioned validator/profile set; absence is not success.
- **Verification:** existing `uv run pytest -q tests/test_fhirkit.py tests/test_modelkit_interfaces.py`
  plus proposed `tests/test_fhir_generation_contract.py`; separate qualified validator run.
- **Done evidence:** supported-field table, positive/negative fixtures, structural and semantic
  reports. Actual model inference remains subject to MRL; fixture tests can complete earlier.

## MS-04 — Fair optional OpenMed extraction adapter

- **Priority / effort / owner:** P1; 3–5 days; modelkit maintainer.
- **Dependencies:** MS-02; ADR-0007 T3 eligibility; artifact/license qualification before real use.
- **Deliver:** optional `medscale[openmed]` adapter implementing existing `SpanExtractor`,
  locked SDK/model/tokenizer identities, explicit label and offset conversion, offline cache
  preflight and cached synthetic extraction artifacts. Package/model rights are separate.
- **Fairness:** choose the matching clinical task model on development data; disclose settings,
  token limits, batching, overlap resolution and any postprocessing. Freeze before test use.
  Never use OpenMed predictions as gold. Keep assisted metrics secondary per ADR-0007.
- **Acceptance:** core imports and tests pass without OpenMed; Arabic offsets round-trip;
  missing cache errors without network fallback; identical cached outputs replay identically;
  invalid spans/unknown labels follow the frozen error policy.
- **Verification:** `uv run pytest -q tests/test_modelkit_interfaces.py tests/test_modelkit_backends.py`
  plus proposed `tests/test_openmed_adapter.py` in absent/present-extra environments.
- **Done evidence:** adapter contract and dependency absence checks; separately qualified real
  baseline receipt if available. Adapter implementation alone is not comparison evidence.

## MS-05 — Reproducible comparison and failure report

- **Priority / effort / owner:** P0; 6–10 days; evaluation maintainer.
- **Dependencies:** MS-02, MS-03, MS-04; real execution gates for non-fixture runs.
- **Deliver:** extend existing benchmark/replay/reporting surfaces with lane-specific scores,
  per-label recall, paired intervals, seed variability, failure taxonomy and resource metadata.
  Compare shared extraction independently from generation/evidence capabilities.
- **Acceptance:** common corpus and budgets; failed/missing items remain in denominators;
  comparator unsupported tasks are N/A; synthetic and real-model runs cannot be confused;
  a deliberately degraded candidate fails the comparison rule; report retains null results.
- **Verification:** existing bench replay/engine tests plus proposed
  `uv run pytest -q tests/test_clinical_comparison_report.py`; replay a committed fixture bundle
  in network-disabled CI and verify canonical hashes.
- **Done evidence:** reproducible fixture report; real head-to-head claims only after a
  separately qualified, frozen run and independent review.

## MS-06 — English, Arabic and code-switching evidence

- **Priority / effort / owner:** P0; 4–7 days; bilingual evaluation lead.
- **Dependencies:** MS-02; qualified independent reviewers.
- **Deliver:** synthetic slice registry distinguishing original language, translation and
  code-switching; language-specific annotations for negation, transliteration, units, names
  and temporality. Reserve dialect/speech claims until separate data exists.
- **Acceptance:** translations share split groups; Unicode mapping tests pass; adjudicated
  gold and slice denominators are complete; underpowered slices explicitly inconclusive.
- **Verification:** proposed `uv run pytest -q tests/test_bilingual_fixture_contract.py` and
  reviewer agreement/adjudication report checked against the frozen annotation protocol.
- **Done evidence:** rights-qualified fixtures and review receipts; no unreviewed translation
  is treated as equivalent medical ground truth.

## MS-07 — Close Experiment-0 preparation gaps through existing MRL gates

- **Priority / effort / owner:** P0; 4–8 engineering days plus external lead time; research
  operator with independent evaluator/runtime/rights reviewers.
- **Dependencies:** MS-05, MS-06 for this new workflow's evaluation evidence; existing
  Experiment-0 prerequisites still govern the canonical tournament. This roadmap does not
  retroactively add gates to an already frozen experiment; adopt scope changes explicitly.
- **Deliver:** gap-to-evidence checklist for MRL-0801–0808 referencing actual candidate,
  corpus, contamination, hardware, authority, objective/budgets, evaluator and sandbox receipts.
  Reuse `specs/mesc-experiment-0/` and its verifier; do not implement another orchestrator.
- **Acceptance:** every receipt binds exact assets and objective; missing real evidence remains
  blocked. Thresholds and numeric compute ceilings are frozen before exposure. The selected
  candidate may lose; capacity failure does not become scientific rejection.
- **Verification:** `uv run pytest -q tests/test_verify_mesc_experiment_0_evidence.py
  tests/test_verify_mesc_experiment_0_evidence_integrity.py tests/test_mesc_experiment_0_protocol.py`;
  then the canonical runbook's real evidence checks when independently eligible.
- **Done evidence:** actual MRL closeout through canonical procedure, or a precise blocker
  report. No synthetic receipt, status edit or roadmap checkbox satisfies a real gate.

## MS-08 — First bounded model-improvement experiment

- **Priority / effort / owner:** P1; 10–20 days after qualification; training researcher.
- **Dependencies:** accepted Experiment-0 foundation decision, MS-07 and separate canonical
  training qualification/authorization. Review existing training executor before any new code.
- **Deliver:** one ground-truth SFT pilot targeting the largest verified development failure
  class. Compare untuned, retrieval-assisted, grammar-assisted and SFT arms. Keep data, prompt,
  decoding and compute differences explicit. Teacher distillation remains a later hypothesis.
- **Acceptance:** three seeds, frozen hard floors, no sealed feedback into tuning, immutable
  train/evaluation lineage, reproducible checkpoints and full null/stop reporting. Stop after
  the fixed budget even if improvement is absent; never quietly enlarge the search.
- **Verification:** applicable training-contract tests and the accepted experiment's exact
  execution/replay commands. Define these in its spec before launch; no placeholder run is evidence.
- **Done evidence:** independently reviewed improvement or null result and a model-card
  candidate. Promotion is a separate decision.

## MS-09 — Researcher-facing release candidate

- **Priority / effort / owner:** P1; 4–7 days plus review; release maintainer.
- **Dependencies:** MS-01–MS-06 for a toolkit candidate; MS-08 plus all existing release gates
  for a model candidate. Toolkit usability is not blocked on winning model performance.
- **Deliver:** task-first API examples, supported-feature matrix, migration notes, model/data
  terms, artifact checksums, reproducibility instructions and failure/limitations report.
- **Acceptance:** two external reproductions; three first-use walkthrough records; clean
  install without optional backends; release claims point to reviewed artifacts; clinical
  validity and full FHIR coverage are not implied. Inspect existing release workflow first.
- **Verification:** full current CI, docs-link hygiene and applicable release checks under
  `docs/releases/`; record exact revision/environment for external reproductions.
- **Done evidence:** a reviewable release candidate. Publication/promotion uses existing authority.

## MS-10 — Evidence-triggered expansion

- **Priority / effort / owner:** P2; estimate after MS-08; modality research lead.
- **Dependencies:** demonstrated text/evidence loop, qualified modality-specific data and a
  reviewed hypothesis explaining the next most valuable failure class.
- **Deliver:** choose one vision task before expanding to multiple imaging domains; treat
  speech ASR and physiologic acoustics as separate later projects per ADR-0036.
- **Acceptance:** independent per-modality gold, licensing/scope admission, medical grounding
  metrics, language/subgroup coverage, budget and hard non-regression rule for existing lanes.
- **Verification:** define modality-specific acceptance and execution commands in the successor
  spec before implementation. Generic captioning or ASR success cannot validate auscultation.
- **Done evidence:** qualified proposal or measured modality result with bounded claims; no
  automatic foundation migration and no feature-count-driven expansion.
