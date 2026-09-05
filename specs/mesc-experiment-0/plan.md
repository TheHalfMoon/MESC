# MESC Experiment-0 — Execution Plan

Status: **PREPARATION ONLY / NO REAL EXECUTION AUTHORITY**

## Objective

Produce reproducible evidence for foundation selection before any MESC training campaign.
The experiment compares frozen, rights-qualified candidates under one frozen evaluation
protocol and emits a non-promotional research decision artifact.

## Scientific question

Primary question:

> Under identical admissible health/FHIR/vision/Arabic evaluation conditions, which frozen
> open-weight candidate provides the best evidence-backed foundation for the next MESC
> training program without violating hard safety, evidence, contamination, rights, or
> reproducibility floors?

Null result:

> No candidate satisfies the mandatory floors strongly enough to justify a foundation
> decision; the correct disposition is `INCONCLUSIVE_OR_BLOCKED`, not forced selection.

## Phase 0 — Execution-window landscape refresh

Immediately before MRL-0801 is populated:

1. verify current upstream releases from authoritative sources;
2. freeze exact candidate IDs and revisions;
3. record license/NOTICE/usage-policy/derivative/output-use dispositions;
4. verify processor/tokenizer/vision components and `trust_remote_code` requirements;
5. record runtime framework support and expected hardware envelope;
6. reject candidates that cannot satisfy immutable identity or rights requirements;
7. freeze the roster before any result exposure.

The 2026-09-05 strategy-time candidate list is input to this phase, not a substitute for it.

## Phase 1 — Evaluation asset qualification

Prepare exact, versioned assets for the following lanes.

### Health reasoning

Use rights-qualified, contamination-reviewed medical reasoning tasks with source identities,
answerability labels where applicable, and explicit scoring semantics.

### Evidence fidelity

Require source-grounded tasks where claims can be checked against evidence spans or exact
references. Track unsupported claim rate separately from answer accuracy.

### FHIR/EHR

Prefer synthetic-first assets such as separately qualified Synthea-derived FHIR plus
hand-authored adversarial fixtures and official FHIR structural definitions. Separate:

- structural validity;
- semantic correctness;
- longitudinal/resource-link consistency;
- constrained vs unconstrained output behavior where the candidate path supports it.

### Medical vision

Only admit image data after exact rights, custody, PHI/de-identification, source/study/
series/object identity, patient/study grouping, DICOM/private-tag/burned-in-text disposition,
and duplicate/leakage evidence exist.

### Arabic

Use native or independently validated Arabic medical tasks. Machine translation alone cannot
serve as the entire Arabic evaluation surface.

### Sealed evaluation

Tier 3 item-level content remains unavailable to adaptive candidate selection, prompt search,
or troubleshooting. Only the frozen evaluator may consume it under the MRL sealed-evidence
contract.

## Phase 2 — Frozen candidate runtime qualification

For each candidate:

1. verify exact local snapshot identity against the frozen revision;
2. record all relevant artifact hashes/sizes;
3. load with `trust_remote_code=False` unless a separately reviewed exception exists;
4. attest Python, framework, CUDA, GPU count/model/memory and execution class;
5. execute a bounded synthetic smoke before scientific evaluation;
6. record post-load and peak memory;
7. record deterministic generation configuration;
8. fail closed on revision drift, missing artifacts, incompatible processor state,
   authentication/access ambiguity, or runtime identity failure.

Runtime feasibility is an operational metric, not a scientific quality score.

## Phase 3 — Tier 0 protocol smoke

Before evaluating medical assets, run only synthetic/hand-authored non-sealed items to prove:

- prompt/rendering path;
- text generation path;
- image processor path where relevant;
- structured output capture;
- scorer/evaluator wiring;
- deterministic artifact serialization;
- budget accounting;
- candidate isolation.

A protocol defect discovered here blocks scientific evaluation until repaired and re-frozen.

## Phase 4 — Tier 1 development evaluation

Run the frozen Tier 1 surface once per frozen candidate configuration.

Record at minimum:

```text
candidate_id
candidate_revision
prompt_template_identity
generation_config_identity
evaluator_identity
dataset_identity
lane
metric_vector
hard_floor_results
resource_usage
runtime_receipt_identity
```

Prompt/configuration search must have a bounded query/result-exposure budget. Every adaptive
change creates a new configuration identity and consumes budget.

## Phase 5 — Tier 2 replication

Replicate only the predeclared finalists or required controls under the frozen replication
policy. Tier 2 may not become an unlimited second development set.

Required checks include:

- result stability;
- seed/configuration sensitivity where applicable;
- runtime reproducibility;
- evaluator consistency;
- hard-floor non-regression.

## Phase 6 — Tier 3 sealed evaluation

Run exactly once under the frozen sealed-evaluation contract after the finalist decision
rule is satisfied.

The research process may consume only the allowed aggregate/result fields defined before
execution. Item-level sealed examples, errors, prompts, images, or labels do not enter later
training/search context.

## Phase 7 — Foundation decision evidence candidate

Allowed dispositions:

```text
RETAIN_PREFERRED_CANDIDATE
SELECT_CHALLENGER
INCONCLUSIVE_OR_BLOCKED
INVALID_EXPERIMENT
```

The decision must include:

- frozen objective identity;
- candidate roster and exact revisions;
- dataset/evaluator identities;
- lane-specific metric vectors;
- hard-floor results;
- uncertainty/limitations;
- compute/runtime facts;
- contamination/rights dispositions;
- exact evidence-bundle identity;
- rationale constrained to observed evidence.

This is not model promotion and does not authorize training.

## Hard floors

Exact numerical thresholds belong to MRL-0806/0807 and must be frozen before execution.
The categories are mandatory even before values are selected:

- critical medical safety failures;
- unsupported medical claims/evidence fidelity;
- calibration/overconfidence;
- abstention/answerability failures;
- FHIR structural/semantic failures;
- sealed-evaluation integrity;
- contamination/leakage;
- Arabic catastrophic regressions when Arabic is in declared scope;
- visual-grounding failures for vision-capable candidates;
- reproducibility/runtime integrity.

No weighted score may compensate for a failed mandatory hard floor.

## Ranking model

Do not use one opaque scalar as the primary evidence artifact.

The decision layer may use a predeclared lexicographic or Pareto-style rule such as:

1. reject any candidate failing hard floors;
2. compare medical/evidence capability vector;
3. compare multimodal/FHIR/Arabic declared-scope vector;
4. compare reproducibility and operational feasibility;
5. use cost/latency as a tiebreaker rather than overriding material health-quality gaps.

The exact rule must be frozen under MRL-0806.

## Compute policy

Google Colab is the preferred first runtime qualification surface. The notebook must record
the actual assigned hardware.

If a candidate cannot fit the observed Colab runtime:

```text
COLAB_DISPOSITION = BLOCKED_COLAB_CAPACITY
```

This does not automatically remove the candidate from the scientific tournament. A later
separately authorized cloud-accelerator execution may be used if MRL-0804/MRL-0808 and the
frozen budget permit it.

## Training boundary

Experiment-0 must stop before any weight mutation.

Forbidden in this experiment:

```text
optimizer.step()
LoRA adapter creation
QLoRA
continued pretraining
SFT
RL / preference optimization
teacher-data generation for training
checkpoint mutation intended as a trained MESC artifact
```

After a foundation decision evidence candidate is independently reviewed and canonically
accepted, a separate successor package may propose the first ground-truth MESC SFT pilot.
