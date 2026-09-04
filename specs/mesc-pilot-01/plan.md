# MESC Pilot-01 — Plan

Status: **foundation plan**
Authorization: Foundation authorized; execution is phase-specific and separately gated
Freeze date: 2026-07-17

---

## Phase overview

```text
P01-01 — Foundation contracts
P01-02 — Dataset acquisition and immutable revision
P01-03 — Dataset transformation and validation
P01-04 — Frozen split and leakage audit
P01-05 — B0/B1 baseline runner
P01-06 — Colab feasibility smoke run
P01-07 — First QLoRA run
P01-08 — B2/B3 evaluation
P01-09 — Clinical and external comparators
P01-10 — Retrieval-assisted experiments
P01-11 — Evidence Judge validation
P01-12 — Paper evidence package
```

---

## P01-01 — Foundation contracts

- Prerequisites: frozen model selection, dataset selection, architecture registration.
- Outputs: deterministic source contracts, split contracts, manifest contracts, evaluation metrics, smoke fixture, architecture tests, typing clean, lint clean.
- Acceptance criteria: all required files present; all required contracts present; full Pytest passes; Mypy passes; Ruff passes; format check passes; `git diff --check` passes; staging empty.
- Stop conditions: prohibited imports detected; architecture enforcement weakened; contract semantics changed; stale test counts accepted without evidence.
- Authorization status: COMPLETED.

## P01-02 — Dataset identity, rights, and immutable revision lock

- Prerequisites: dataset license review finalized; dataset rights documented.
- Outputs: pinned dataset revision identity; immutable acquisition record; provenance metadata.
- Acceptance criteria: dataset ID, revision, configuration, and license recorded; content-hash inputs stable; no downloaded artifacts in unauthorized scope.
- Stop conditions: license or rights review incomplete; revision strategy absent.
- Authorization status: COMPLETED.

Note: P01-02 completed dataset identity, rights documentation, and immutable revision locking. Dataset acquisition, content retrieval, and transformation were not performed in P01-02.

## P01-03 — Dataset transformation and validation

- Prerequisites: dataset identity and immutable revision complete; schema finalized; acquisition authorization recorded.
- Outputs: transformed PilotRecord set; validation report; schema versioning record.
- Acceptance criteria: deterministic transformation from source IDs; example IDs unique; content hashes reproducible; abstract-only data boundary preserved; no full-text claims outside rights.
- Stop conditions: schema revision uncontrolled; full copyrighted content introduced; annotation fields fabricated without authorization.
- Authorization status: PLANNING AUTHORIZED / EXECUTION NOT AUTHORIZED.

## P01-04A — P01-04 split and leakage specification

- Prerequisites: P01-03G promotion merged and verified; P01-03G handoff package complete on canonical main.
- Outputs: `specs/mesc-pilot-01/p01-04/*` specification and policy documents.
- Acceptance criteria: all eight required documents present and validated; creator policy decisions reflected; no execution claims present.
- Stop conditions: execution claims introduced; source-data redistribution claims asserted beyond canonical rights record; paths exceed `specs/mesc-pilot-01/p01-04/**` plus minimum necessary `plan.md`/`tasks.md` updates.
- Authorization status: DOCUMENTATION STAGE ONLY — EXECUTION NOT AUTHORIZED.

## P01-04 — Frozen split and leakage audit

- Prerequisites: P01-04A specification ratified; P01-04B tooling implemented and accepted; P01-04C fixture qualification accepted.
- Outputs: deterministic grouped split manifest; leakage audit report; split hash.
- Acceptance criteria: source-document-grouped deterministic splitting; exact/normalized/near-duplicate leakage detection; cross-split overlap reported; split hash reproducible; split assignment does not affect scientific identity.
- Stop conditions: split randomness introduced outside documented seed; leakage findings suppressed.
- Authorization status: NOT AUTHORIZED.

## P01-04B — P01-04 tooling and contract implementation

- Prerequisites: P01-04A specification ratified; founder authorization for tooling implementation.
- Outputs (adopted): private deterministic split core; canonical artifacts and fingerprinting; private fixture facade; leakage primitives; three-fixture synthetic qualification; atomic publication boundary; write-path protections; cross-platform qualification.
- Acceptance criteria: implementation is consistent with ratified P01-04A policy; deterministic serialization and fingerprinting behavior are fixture-validated; execution safety controls are reviewable; no real split artifacts are produced during implementation or qualification.
- Acceptance summary: all ten P01-04B acceptance criteria are SATISFIED on canonical main `d5a6ac1654cabd33b6a795756d2796bceaf1652a`; the three synthetic qualification fixtures (`exact-reference-1000-v1`, `constraint-stress-1000-v1`, `leakage-positive-v1`) are accepted; qualification is deterministic and byte-identical across the supported Linux, Windows and macOS runtimes; no real partition membership was generated or disclosed.
- Stop conditions: implementation diverges from ratified specification; execution controls allow unauthorized seeding, mutation, or writeback; fixtures contain real partition membership; scope expands beyond contracts and tooling without separate authorization.
- Authorization status: COMPLETED AND ACCEPTED — REAL EXECUTION NOT AUTHORIZED.

Note: P01-04B acceptance is tooling acceptance only. It does not authorize any real split, real partition membership, canonical leakage execution, evidence publication, model access, inference, retrieval, training or fine-tuning, and it does not authorize P01-04 overall, P01-04C, P01-04D or any later phase.

## P01-04C — Fixture Qualification

- Prerequisites: P01-04B canonically accepted; separate founder authorization for P01-04C.
- Outputs: fixture qualification record for synthetic small inputs; repeated-run byte-identity evidence; edge-case qualification evidence.
- Acceptance criteria: all fixture tests pass for synthetic small input; artifacts are byte-identical on repeated runs; empty, single-example, and all-one-label edge cases pass; no real dataset partition membership is generated.
- Ratified edge-case semantics — `pass` does not mean every edge case produces a successful split:
  - empty: expected fail-closed
  - single-example: expected success
  - all-one-label: expected success
- Stop conditions: real dataset partition membership generated; qualification performed without separate founder authorization; fixtures substituted with real data.
- Acceptance summary: all four P01-04C criteria SATISFIED; canonical acceptance baseline `b20dbe0000a129f3019d6f7d2895622ce0560069`; reviewed candidate head `c9cf1cc58b3ff89c39327c328a10308c0a9dbf4d`; PR #85 merged; post-merge CI, CodeQL and Optional Extras / Backends all successful; no real dataset membership generated.
- Authorization status: COMPLETED AND ACCEPTED — REAL DATASET EXECUTION NOT AUTHORIZED.

Note: P01-04C acceptance accepts synthetic qualification only. It does not authorize P01-04D, real split generation, real membership, canonical leakage execution or any later phase.

## P01-05 — B0/B1 baseline runner

- Prerequisites: frozen split and leakage audit complete; primary model gated access reviewed.
- Outputs: deterministic runner scaffold; run manifests; baseline result schema.
- Acceptance criteria: runner does not download weights by default; missing metrics report `not_applicable`; abstention behavior preserved; no experimental results claimed in foundation contract.
- Stop conditions: weights access attempted without explicit authorization; runner mutates scientific identity.
- Authorization status: HISTORICAL ROOT-PLAN STATUS; current P01-05 implementation/execution truth is governed by `specs/mesc-pilot-01/p01-05/` and its accepted successor packages.

## P01-06 — Colab feasibility smoke run

- Prerequisites: B0/B1 baseline runner complete; low-memory fallback decision recorded.
- Outputs: feasibility report; memory usage record; fallback decision.
- Acceptance criteria: run confined to authorized environment; fallback decision explicit; no persistent adapter or published output.
- Stop conditions: Colab OOM or disconnection patterns ignored; fallback substituted without documented authorization.
- Authorization status: **AUTHORIZED ON CANONICAL MERGE OF `FD-P01-06-COLAB-1` — NOT EXECUTED**.
- Controlling authorization package: `specs/mesc-pilot-01/p01-06-colab-feasibility-authorization/`.
- Execution boundary: Google Colab feasibility only; exact primary/fallback model revisions; no scientific benchmark run, QLoRA, Unsloth training, adapter creation, retrieval, publication, or test-partition inspection.

## P01-07 — First QLoRA run

- Prerequisites: Colab feasibility smoke run passes; fallback decision recorded.
- Outputs: QLoRA adapter metadata; training manifest; evaluation manifest.
- Acceptance criteria: adapter created only under explicit authorization; no public release; no overclaiming from adapter metadata.
- Stop conditions: adapter accepted as production artifact; training executed without authorization record.
- Authorization status: NOT AUTHORIZED.

## P01-08 — B2/B3 evaluation

- Prerequisites: B2/B3 artifacts complete; Layer 2 gold subset ready.
- Outputs: Layer 1 and Layer 2 evaluation reports; abstention precision/recall; supported-claim metrics.
- Acceptance criteria: Layer 2 metrics gated behind gold subset; judge bias documented; no experimental results from incomplete gold subsets.
- Stop conditions: Layer 2 metrics reported without gold subset; judge substituted for manual review.
- Authorization status: NOT AUTHORIZED.

## P01-09 — Clinical and external comparators

- Prerequisites: B2/B3 evaluation complete; clinical model gated access finalized.
- Outputs: comparator result schema; MedGemma access record; clinical-use restriction record.
- Acceptance criteria: clinical use boundary documented; gated-access terms accepted; comparator results never used as clinical evidence.
- Stop conditions: clinical model used in production-like routing; gated-access terms ignored.
- Authorization status: NOT AUTHORIZED.

## P01-10 — Retrieval-assisted experiments

- Prerequisites: B0/B1 deterministic runner complete; retrieval boundary finalized.
- Outputs: retrieval configuration; evidence coverage metrics; retrieval boundary test.
- Acceptance criteria: retrieval is optional; evidence-coverage metrics grounded in gold subset; deterministic reranker behavior.
- Stop conditions: retrieval forced into B0 baseline; retrieval evidence treated as gold without validation.
- Authorization status: NOT AUTHORIZED.

## P01-11 — Evidence Judge validation

- Prerequisites: SciFact auxiliary dataset license review complete; Layer 1 metrics stable.
- Outputs: Evidence Judge validation report; SciFact result schema; judge bias log.
- Acceptance criteria: judge validated against auxiliary dataset only; PubMedQA gold labels not replaced; judge does not become silent ground truth.
- Stop conditions: judge overrides manual gold labels; SciFact results treated as primary benchmark.
- Authorization status: NOT AUTHORIZED.

## P01-12 — Paper evidence package

- Prerequisites: all prior phases complete or explicitly deferred with documented rationale.
- Outputs: research evidence package; reproducibility record; public-facing accuracy claims.
- Acceptance criteria: claims match executed and authorized work; reproducibility preserved; clinical and production claims explicitly absent.
- Stop conditions: claims exceed executed phases; full article text included outside documented rights.
- Authorization status: NOT AUTHORIZED.
