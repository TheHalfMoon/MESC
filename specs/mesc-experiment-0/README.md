# MESC Experiment-0 — Colab Foundation Tournament

Status: **STACKED PREPARATION / NO REAL MODEL OR TRAINING EXECUTION AUTHORITY**

Dependency:

- strategy PR `#373` must first be merged to canonical `main`;
- ADR-0036 and the 2026-09-05 performance-first MESC strategy must be canonical;
- MRL-0801..MRL-0808 remain unsatisfied until genuine external evidence exists;
- this package does not change `MRL_REAL_EXPERIMENT_READY`, `TRAINING_READY`, or any
  promotion/release state.

## Purpose

Define the first evidence-producing MESC successor experiment after the performance-first
strategy becomes canonical.

Experiment-0 is a **no-training foundation tournament**. It exists to answer one bounded
question before MESC spends compute on fine-tuning or distillation:

> Which currently qualifiable open-weight foundation provides the strongest starting point
> for the MESC health-model program under a frozen, medically relevant, reproducible
> evaluation protocol?

The tournament is not a product benchmark, marketing leaderboard, or model-promotion gate.
Its maximum positive outcome is a foundation decision evidence candidate for later governed
MESC work.

## Why this succeeds the historical P01-06 Colab work

P01-06 established useful execution-engineering patterns for Google Colab:

- attest the actual hosted runtime instead of assuming a GPU class;
- bind execution to an exact canonical repository commit/tree;
- pin exact model revisions;
- use fail-closed acquisition and `trust_remote_code=False` by default;
- record GPU memory/runtime facts;
- emit metadata-only evidence artifacts;
- preserve hashes and immutable identities;
- keep failures as `BLOCKED` rather than changing the protocol to force success.

Experiment-0 reuses those patterns but does **not** reuse the historical Llama candidate,
P01-06 authority, or Pilot-01 scientific scope.

## Non-goals

Experiment-0 does not authorize or perform:

- continued pretraining;
- SFT, LoRA, QLoRA, PEFT, Unsloth training, TRL, RL, preference optimization, or adapters;
- teacher-output generation for training;
- medical model promotion or release;
- clinical deployment or clinical-action validation;
- PHI, private patient data, or unqualified medical-image corpora;
- sealed Tier 3 item exposure to an adaptive process;
- automatic continuation into MESC training.

## Candidate policy

The strategy-time preferred candidate is currently:

```text
Qwen/Qwen3.8-27B
```

This identifier is **not** an Experiment-0 execution identity until MRL-0801 binds an exact
immutable model revision, processor/tokenizer identity, weights manifest, license/NOTICE,
and applicable usage/derivative disposition.

The final tournament roster must be frozen immediately before execution and may include:

- the qualified Qwen3.8-27B candidate;
- applicable Gemma 4 multimodal challenger(s);
- `microsoft/Phi-4-multimodal-instruct` where still technically/currently appropriate;
- MedGemma as a medical specialist reference under its separately qualified terms;
- newer open-weight challengers discovered during the required execution-window landscape
  refresh.

No candidate may be added after result exposure merely because it is expected to score
well.

## Evaluation lanes

Experiment-0 should measure a vector rather than one aggregate score.

Required lanes, subject to exact dataset/evaluator qualification:

1. health and clinical reasoning;
2. evidence fidelity and citation/entailment behavior;
3. hallucination, answerability, abstention, and calibration;
4. FHIR/EHR structured reasoning and deterministic structural validity;
5. medical vision and visual grounding where the candidate supports vision;
6. Arabic medical language capability;
7. English medical language capability;
8. structured output/tool-use behavior where supported;
9. runtime feasibility, VRAM, latency, and reproducibility.

A candidate cannot win solely through a weighted average if it violates a hard safety,
evidence, contamination, or reproducibility floor.

## Colab role

Google Colab remains the default development/runtime qualification surface when the frozen
candidate fits the available hosted GPU. Experiment-0 must record the **actual** allocated
GPU and must not assume T4, L4, A100, H100, or another class.

A candidate that cannot run on the observed Colab allocation may receive a runtime
`BLOCKED_COLAB_CAPACITY` disposition without being scientifically rejected. Separately
authorized rented accelerator execution may be evaluated later under MRL-0804/MRL-0808.

## Required package files

This specification family owns:

```text
specs/mesc-experiment-0/README.md
specs/mesc-experiment-0/plan.md
specs/mesc-experiment-0/evidence-contract.md
specs/mesc-experiment-0/decision-contract.md
specs/mesc-experiment-0/runbook.md
specs/mesc-experiment-0/experiment-config.template.json
notebooks/MESC_Experiment_0_Colab.ipynb
tools/verify_mesc_experiment_0_evidence.py
tests/test_verify_mesc_experiment_0_evidence.py
```

The notebook is a protocol implementation template. Its existence is not runtime evidence.
The verifier proves only structural/identity integrity of an evidence bundle; it does not
independently establish medical correctness, rights, or canonical acceptance.

## MRL mapping

Experiment-0 becomes executable only through the existing MRL real-preflight path:

- `MRL-0801` — exact model/weights evidence for every active candidate;
- `MRL-0802` — exact rights-qualified corpus/evaluation asset identity;
- `MRL-0803` — contamination, patient/study grouping, held-out and sealed isolation;
- `MRL-0804` — actual Colab/cloud runtime and GPU evidence;
- `MRL-0805` — applicable execution/training authority. For Experiment-0 this must
  explicitly distinguish no-training evaluation authority from later training authority;
- `MRL-0806` — exact objective, candidate roster, budgets, exposure ceilings, success/null/
  stop conditions;
- `MRL-0807` — exact evaluator and sealed Tier 3 identities;
- `MRL-0808` — exact sandbox/network/filesystem/credential/output policy;
- `MRL-0809` / `MRL-0899` — exact-head preflight qualification and separate readiness
  decision.

This package does not satisfy any of those tasks by being authored or merged.

## Dependency/merge boundary

This branch is intentionally stacked on PR `#373`.

It must not merge to `main` before the strategy package is canonical. After `#373` merges,
this change must be retargeted against the resulting canonical main without rewriting
reviewed history, then receive its own exact-head CI, CodeQL, review, thread, ruleset, and
guarded-merge qualification.
