# MESC Research Loop V1 — Research Synthesis

Status: **EVIDENCE-BACKED STRATEGY INPUT / NO EXECUTION AUTHORITY**

Date: 2026-08-26

## Question

What should MESC adopt from autonomous-research systems and agent learning loops, and
what additional controls are required because MESC is medical, reproducibility-first,
and governed by fail-closed authority boundaries?

## Current MESC strengths that should be preserved

Live repository review shows that MESC already has strong foundations that should not be
reimplemented under a new agent framework:

- explicit falsifiable research questions;
- deterministic and content-addressed experiment manifests;
- clean-code-SHA and dataset/model identity binding;
- fixed seeds and reproducibility requirements;
- contamination policy and held-out-test isolation;
- negative/null results as first-class results;
- deterministic primary metrics rather than LLM-as-judge headline metrics;
- broad evidence, uncertainty, abstention, safety, longitudinal, FHIR, multimodal, and
  population/language evaluation strategy;
- Backbone Tournament protocol freeze before model output;
- MCRL design for typed clinical state, evidence, verification, uncertainty, recovery,
  and completion contracts;
- explicit separation between planning/readiness and real execution authority.

The primary gap is therefore **research orchestration and research learning**, not basic
provenance or experiment logging.

## External reference: Karpathy autoresearch

Source:

- https://github.com/karpathy/autoresearch

Useful design ideas:

- narrow mutation surface;
- fixed experiment budget;
- fast propose/run/evaluate/keep-or-discard loop;
- machine-readable objective;
- comparable experiments under a fixed resource envelope;
- human-authored research-organization instructions separated from agent-edited code.

Adopt for MESC:

- bounded mutation surfaces;
- explicit compute/token/time budgets;
- rapid experiment iteration after all safety/evaluation controls exist;
- structured keep/reject/replicate decisions;
- optimization for validated gain per unit of research compute.

Do not copy directly:

- one scalar metric as the complete objective;
- repeated exposure of the final promotion holdout;
- agent control over evaluation code;
- raw untrusted logs as direct agent context;
- unrestricted self-modification;
- automatic promotion from one apparent improvement.

MESC requirement derived from this comparison:

> The researcher may modify the experiment; it may never modify the ruler used to
> measure or authorize the experiment.

## External reference: Hermes Agent Learning Loop

Source:

- https://hermes-agent.ai/features/learning-loop

Useful design idea:

```text
observe -> distill -> reuse -> refine
```

Hermes demonstrates the value of turning repeated successful trajectories into explicit,
inspectable procedures/skills rather than forcing the agent to rediscover the same
workflow each time.

Adopt for MESC:

- extract reusable research-procedure candidates from campaign history;
- preserve known failure modes and verification steps;
- make learned procedures inspectable and versioned;
- reuse validated procedures to reduce repeated research cost.

Medical/research strengthening required by MESC:

A repeated workflow must not become canonical merely because it succeeded several times.
Procedure admission requires replay, transfer testing, negative/failure controls,
applicability bounds, and review.

Proposed lifecycle:

```text
DISCOVERED
  -> CANDIDATE
  -> REPLAYED
  -> TRANSFER_TESTED
  -> REVIEWED
  -> ADMITTED
```

## External research directions reviewed

The following research families materially support the proposed direction and should be
tracked as design references, not copied blindly:

### Autonomous scientific search

- AI Scientist / AI Scientist v2 style iterative hypothesis and experiment search.
- Darwin Gödel Machine style archive/tree exploration rather than one linear champion.
- MLGym-style evaluation of the research agent itself, not only the model produced.

Implication for MESC:

A research campaign should be a DAG/portfolio of hypotheses and attempts. The system
must preserve diverse promising branches and failed branches instead of only the current
best score.

### Workflow memory

Agent Workflow Memory and related workflow-learning work support extracting reusable
procedures from trajectories.

Implication for MESC:

Research memory should store validated abstractions, not a bag of raw conversations.
Canonical memory should be typed, content-addressed, reviewable, and reconstructible.

### Adaptive holdout risk

Repeated adaptive model changes against the same validation signal can overfit the
research process to the holdout even when the holdout is not directly trained on.

Implication for MESC:

The existing train/dev/test rule is necessary but insufficient for high-volume autonomous
experimentation. MRL requires separate search, replication, sealed promotion, and
external/clinician assurance tiers.

### Medical evaluation breadth

Recent medical evaluation work such as HealthBench, HealthBench Professional, MedHELM,
and abstention-focused evaluation supports MESC's existing direction away from medical
exam QA as a sufficient success criterion.

Implication for MESC:

Autonomous optimization must operate under a multi-axis medical evaluation contract with
hard safety and subgroup floors, not a single aggregate score.

### Temporal contamination resistance

Continuously refreshed or post-cutoff evaluation ideas motivate a MESC-native temporal
canary track.

Implication for MESC:

MESC should eventually generate or author sealed, R2-compatible synthetic/fixture cases
after each training/data freeze and prohibit their use as training/search material.

## Gap register

### G1 — Canonical hypothesis-to-decision graph

State: **MISSING**

MESC records experiments well but lacks first-class canonical objects for why an
experiment was proposed, what mechanism it tests, how it was judged, why it was rejected
or retained, and what should follow.

### G2 — Adaptive experimentation governance

State: **MISSING**

Current held-out discipline does not fully address hundreds of adaptive search cycles
against the same visible validation feedback.

### G3 — Immutable evaluator / restricted mutation boundary

State: **PARTIAL**

MESC has frozen protocols in important areas, but MRL needs a general research-agent
contract that makes evaluator, sealed data, governance, authorization, trust, and
canonical history explicitly non-mutable.

### G4 — Research procedure memory

State: **MISSING**

There is no canonical lifecycle for extracting, validating, and admitting reusable
research procedures from prior campaigns.

### G5 — Campaign portfolio / tree search

State: **MISSING**

There is no canonical research campaign graph that preserves alternative hypotheses,
failed branches, replications, and promotion candidates.

### G6 — Research-agent evaluation

State: **MISSING**

MESC evaluates model behavior but does not yet evaluate whether an autonomous researcher
is scientifically efficient, repetitive, unsafe, optimistic, or reproducible.

### G7 — Semantic and lineage contamination

State: **PARTIAL / EXPANSION NEEDED**

Exact split/hash contamination controls are strong. Future synthetic-teacher and
high-volume research workflows require provenance through transformations, prompts,
teachers, paraphrases, and benchmark-derived generations.

### G8 — Temporal canary evaluation

State: **MISSING / HIGH VALUE**

A sealed post-freeze synthetic/fixture track would provide stronger evidence against
static-benchmark adaptation.

### G9 — Research-program registry drift

State: **NEEDS RECONCILIATION**

The foundational RQ1-RQ7 registry is narrower than the later MESC strategy covering
abstention, calibration, MCRL, verifier training, longitudinal/FHIR agents, Arabic,
multimodality, AMGE, and Medical Omni.

### G10 — Human-readable roadmap drift

State: **NEEDS RECONCILIATION**

The legacy roadmap and the newer live capability/spec state can diverge. Autonomous
research must not rely on stale narrative status.

## Recommended strategic outcome

Add a new MESC moat:

**Governed Self-Improving Research**

This means MESC can conduct, remember, critique, reproduce, and improve medical-AI
research while preserving independent evaluation, sealed promotion evidence, safety
floors, provenance, and human/governance authority.

It does **not** mean autonomous clinical authority, autonomous production deployment, or
unrestricted recursive self-training.
