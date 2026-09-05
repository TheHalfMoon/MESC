# MESC Experiment-0 — Tournament Contract

Status: **DESIGN CONTRACT / NO MODEL EXECUTION AUTHORITY**

## 1. Purpose

Prevent foundation selection from becoming an informal leaderboard comparison. Every
candidate must be evaluated under comparable, frozen conditions and its unsupported
capabilities must be represented explicitly rather than silently ignored or converted to
zero.

## 2. Candidate admission

Before result exposure, each candidate record must freeze:

```text
candidate_id
candidate_revision
architecture_family
parameterization_summary
context_limit_used
supported_input_modalities
supported_output_modalities
processor_or_tokenizer_identity
chat_or_instruction_template_identity
license_identity
usage_policy_identity
trust_remote_code_disposition
runtime_adapter_identity
quantization_or_dtype_identity
```

A candidate is not admitted on brand reputation or public benchmark score alone.

## 3. Minimum flagship-foundation suitability

Experiment-0 is selecting a foundation for the performance-first MESC flagship, not the
smallest deployable derivative.

At freeze time, a candidate must have either:

1. native text + vision support suitable for medical-image evaluation; or
2. a separately qualified, reproducible vision integration path that does not require
   unreviewed weight surgery or incompatible model merging.

Native audio is desirable but is **not** a mandatory foundation gate. The MESC strategy
permits later qualified audio integration rather than selecting a weaker reasoning/vision
foundation merely for an audio checkbox.

A text-only model may remain a reasoning/reference control but cannot silently be ranked as
if it had passed the flagship multimodal suitability gate.

## 4. Fair generation policy

For every comparable lane:

- use the same semantic task instructions;
- freeze family-specific rendering/chat templates before execution;
- freeze decoding parameters and any justified family-specific equivalents;
- use deterministic decoding where the scientific question permits;
- record all model-specific system/instruction wrappers;
- prohibit post-result prompt tailoring for one candidate without consuming the frozen
  adaptive-search budget and applying the same search policy to all candidates;
- keep maximum output and context budgets comparable unless a predeclared task requires
  otherwise.

Differences required by model APIs are allowed only when they preserve the same semantic
contract and are recorded in the candidate adapter identity.

## 5. Reasoning-mode policy

Models with explicit reasoning-effort controls must have the tested setting frozen before
result exposure.

The tournament must not compare a high-reasoning configuration for one candidate against a
low/default configuration for another merely because those are vendor defaults.

If multiple reasoning settings are scientifically relevant, they are separate frozen
configurations with separate resource accounting.

## 6. Modality policy

An unsupported modality is represented as:

```text
NOT_SUPPORTED_BY_CANDIDATE
```

not `0`, `FAIL`, or a fabricated score.

The decision layer then applies the predeclared flagship-suitability rule. This preserves the
difference between:

- poor performance on a capability the model claims/supports; and
- absence of that capability from the architecture.

For medical vision, evaluate per modality where qualified data exist rather than collapsing
all images into one score.

## 7. Medical quality vector

The primary scientific comparison is multidimensional. Required categories include:

```text
clinical_reasoning
evidence_fidelity
unsupported_claim_rate
answerability_and_abstention
calibration
critical_safety_failures
FHIR_structural_validity
FHIR_semantic_correctness
longitudinal_EHR_consistency
medical_vision_grounding
medical_multi_image_reasoning
Arabic_medical_language
English_medical_language
structured_output_and_tool_behavior
```

Exact metrics and thresholds belong to the frozen evaluator/objective records.

## 8. Hard-floor precedence

Candidate ranking is fail-closed:

1. rights/provenance/contamination/sealed-integrity failure blocks the affected candidate or
   experiment;
2. critical safety/evidence/reproducibility hard-floor failure rejects candidate leadership;
3. only candidates passing mandatory floors enter capability comparison;
4. operational cost/latency/VRAM may break close ties but cannot compensate for a material
   medical-quality deficit.

A high general benchmark score cannot override a failed medical hard floor.

## 9. Reference models vs selectable foundations

The roster may contain two classes:

```text
SELECTABLE_FOUNDATION
REFERENCE_ONLY
```

Reference-only models may establish useful ceilings or specialist baselines but are not
eligible for the foundation decision when rights, architecture, modality, or governance
constraints make them unsuitable lineage sources.

MedGemma may be admitted as `REFERENCE_ONLY` under its separately qualified terms without
becoming a MESC distillation/training source.

gpt-oss or another reasoning model may also be a reference even when it is not a suitable
multimodal foundation.

## 10. Resource-normalized secondary analysis

Because MESC is performance-first, raw quality is primary. Still record:

```text
peak_VRAM
wall_time
tokens_or_items_per_second
context_length_used
provider_GPU_hours
estimated_execution_cost
```

A secondary quality-per-resource analysis is useful for later deployment/compression work
but must not redefine the flagship winner unless the predeclared objective explicitly makes
resource feasibility a mandatory constraint.

## 11. No teacher contamination

Experiment-0 evaluates untuned foundations/reference models. Teacher-generated training data
or capability distillation must not enter candidate weights or evaluation assets during this
tournament.

Teacher council admission is a successor program after foundation evidence is accepted.

## 12. Decision discipline

The decision must explain:

- which candidates were selectable vs reference-only;
- which hard floors passed/failed;
- which modalities were unsupported vs evaluated and failed;
- confidence/uncertainty and missing evidence;
- why the chosen candidate best serves the MESC health objective rather than general model
  prestige.

If evidence does not separate candidates robustly, use `INCONCLUSIVE_OR_BLOCKED`.
