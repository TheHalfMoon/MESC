# MESC Experiment-0 — Execution-Window Candidate Roster Freeze

Status: **FROZEN METADATA ONLY / NOT MRL-0801 EVIDENCE / NO MODEL EXECUTION AUTHORITY**

- Freeze timestamp: `2026-09-06T21:19:57Z`
- Canonical base SHA: `9a98eb6ac2966a68d3020b0ddba223c3ec081c59`
- Canonical base tree: `b719587c10f3775cb3db65d1fedec4645334daa0`
- Driving issue: `#383`
- Strategy decision: `ADR-0036`

## Purpose

This artifact executes Experiment-0 Phase 0 immediately before genuine MRL-0801
model/weights identity and custody qualification. It freezes the candidate roster from
current authoritative upstream metadata before any scientific result exposure.

This artifact is not a model snapshot, custody receipt, runtime receipt, evidence admission,
execution authorization, or training authorization.

## Frozen active roster

### Preferred foundation candidate

```text
candidate_id = Qwen/Qwen3.8-27B
candidate_revision = 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
candidate_class = SELECTABLE_FOUNDATION
role = PREFERRED_FOUNDATION_CANDIDATE
license_identity = Apache-2.0
published_pipeline = image-text-to-text
published_weight_size_label = 55.6 GB
supported_input_modalities = text, vision
trust_remote_code = false
```

Authoritative sources:

- https://huggingface.co/Qwen/Qwen3.8-27B
- https://huggingface.co/Qwen/Qwen3.8-27B/commit/1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
- https://github.com/QwenLM/Qwen3.8

Disposition:

```text
ACTIVE_FOR_MRL_0801_IDENTITY_CUSTODY_QUALIFICATION
```

### Primary challenger

```text
candidate_id = google/gemma-4-31B-it
candidate_revision = 842da3794eaa0b77d5f08bae87a17459d91ff475
candidate_class = SELECTABLE_FOUNDATION
role = PRIMARY_CHALLENGER
license_identity = Apache-2.0
published_pipeline = image-text-to-text
published_weight_size_label = 62.6 GB
supported_input_modalities = text, vision
trust_remote_code = false
```

Authoritative sources:

- https://huggingface.co/google/gemma-4-31B-it
- https://huggingface.co/google/gemma-4-31B-it/commit/842da3794eaa0b77d5f08bae87a17459d91ff475
- https://ai.google.dev/gemma/docs/core

Disposition:

```text
ACTIVE_FOR_MRL_0801_IDENTITY_CUSTODY_QUALIFICATION
```

## Rights-disposition record

Phase 0 records rights metadata conservatively. These observations are provenance inputs,
not legal advice, acquisition authority, downstream dataset rights, output ownership, or
permission to train.

### Qwen/Qwen3.8-27B

```text
license_disposition = APACHE_2_0_DECLARED_AND_LICENSE_FILE_OBSERVED
notice_disposition = NO_SEPARATE_NOTICE_FILE_OBSERVED_AT_PINNED_REVISION
usage_policy_disposition = NO_SEPARATE_CANDIDATE_SPECIFIC_USAGE_POLICY_IDENTIFIED_IN_PINNED_MODEL_MATERIALS
derivative_disposition = EXACT_APACHE_2_0_TERMS_MUST_BE_REEVALUATED_FOR_ANY_DERIVATIVE_OR_DISTRIBUTION_ACTION
output_use_disposition = NO_SEPARATE_OUTPUT_USE_TERM_IDENTIFIED_IN_PINNED_MODEL_MATERIALS_NO_OUTPUT_RIGHT_INFERRED
```

The pinned artifact tree exposes an Apache-2.0 `LICENSE` file. The inspected pinned model
materials did not expose a separate `NOTICE` file or a separate candidate-specific usage
policy. Phase 0 therefore records the absence of a separately identified term rather than
manufacturing a broader permission.

### google/gemma-4-31B-it

```text
license_disposition = APACHE_2_0_DECLARED_BY_PINNED_HUB_METADATA_NO_SEPARATE_LICENSE_FILE_OBSERVED
notice_disposition = NO_SEPARATE_NOTICE_FILE_OBSERVED_AT_PINNED_REVISION
usage_policy_disposition = MODEL_CARD_INTENDED_AND_RESPONSIBLE_USE_GUIDANCE_PRESENT_NO_SEPARATE_EXECUTION_AUTHORITY
derivative_disposition = EXACT_DECLARED_LICENSE_TERMS_MUST_BE_REEVALUATED_FOR_ANY_DERIVATIVE_OR_DISTRIBUTION_ACTION
output_use_disposition = NO_SEPARATE_OUTPUT_USE_TERM_IDENTIFIED_IN_PINNED_MODEL_MATERIALS_NO_OUTPUT_RIGHT_INFERRED
```

The pinned Hugging Face artifact metadata declares Apache-2.0. The inspected pinned tree did
not expose a separate `LICENSE` or `NOTICE` file. The model card includes intended-use,
limitations, ethics/safety, and responsible-use guidance. Those statements are recorded as
usage guidance only and do not grant Experiment-0 execution, training, downstream data, or
output-use authority.

Any later acquisition, derivative creation, redistribution, teacher-output use, or training
step must re-check the exact pinned rights materials applicable to that action. Unknown or
changed rights evidence fails closed rather than inheriting Phase 0 eligibility.

## Deferred control

```text
candidate_id = microsoft/Phi-4-multimodal-instruct
observed_revision = 450bd6eb5ed6a74e38a03ada0320c4fa07865c81
role = DEFERRED_CONTROL
license_identity = MIT
published_pipeline = multimodal/custom-code
published_weight_size_label = 12.9 GB
trust_remote_code_required_by_published_path = true
```

Authoritative sources:

- https://huggingface.co/microsoft/Phi-4-multimodal-instruct
- https://huggingface.co/microsoft/Phi-4-multimodal-instruct/commit/450bd6eb5ed6a74e38a03ada0320c4fa07865c81

Experiment-0 defaults to `trust_remote_code=False`. The published Transformers path for
this Phi-4 artifact still requires custom remote code. It therefore remains outside the
active roster unless a separate exact remote-code exception is canonically authorized,
reviewed, and bound before execution.

## Freeze rationale

The active roster is intentionally small:

1. `Qwen/Qwen3.8-27B` remains the current preferred candidate from ADR-0036 and has a
   current exact upstream revision with an Apache-2.0 model artifact.
2. `google/gemma-4-31B-it` is the strongest directly comparable current Gemma 4
   instruction-tuned vision-capable challenger identified in the execution-window refresh,
   also with an Apache-2.0 model artifact.
3. `microsoft/Phi-4-multimodal-instruct` remains scientifically useful as a control but its
   published custom-code requirement conflicts with the default Experiment-0 remote-code
   boundary, so it is deferred instead of silently broadening that boundary.
4. No later candidate may be inserted after result exposure merely because it is expected
   to score well. Any roster mutation after this freeze requires a new canonical unit and
   invalidates downstream roster-bound evidence.

## What this freeze proves

This package proves only that the repository has a deterministic, immutable metadata roster
for the next MRL-0801 step.

It does **not** prove:

- possession or custody of the exact model bytes;
- local snapshot hash manifests;
- tokenizer/processor artifact hashes;
- actual ability to load either candidate;
- runtime/GPU qualification;
- corpus or evaluation-data rights;
- contamination or held-out isolation;
- evaluator identities;
- execution sandbox readiness;
- real Experiment-0 authority;
- training authorization.

## Next canonical step

The immediate successor is genuine MRL-0801 identity/custody qualification for the two
active candidates. That successor must resolve the exact frozen revisions into actual
snapshot evidence and preserve exact artifact hashes/sizes without using floating refs.

Model acquisition remains blocked until the full canonical Experiment-0 preflight permits
it. If canonical governance requires a metadata-only custody authorization step before
bytes may be acquired, that step must be satisfied first rather than bypassed.

## Hard boundary

```text
RESULT_EXPOSURE_STARTED = FALSE
MRL_0801 = ABSENT
MRL_0802 = ABSENT
MRL_0803 = ABSENT
MRL_0804 = ABSENT
MRL_0805 = ABSENT
MRL_0806 = ABSENT
MRL_0807 = ABSENT
MRL_0808 = ABSENT
REAL_MODEL_EXECUTION_AUTHORIZED = FALSE
MRL_REAL_EXPERIMENT_READY = FALSE
TRAINING_READY = FALSE
TRAINING_EXECUTED = FALSE
```

The production real-preflight trust registry is unchanged by this artifact.
