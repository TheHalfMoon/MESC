# MESC Health Model Program — Performance-First Strategy and Execution Map

- **Date:** 2026-09-05
- **Status:** FOUNDER-DIRECTED STRATEGY / NO REAL MODEL OR TRAINING EXECUTION AUTHORITY
- **Controlling decision:** `docs/adr/0036-performance-first-health-model-strategy.md`
- **Governance:** ADR-0033, ADR-0035, `specs/mesc-research-loop-v1/`
- **Public model identity:** `MESC`

## 1. North star

Build and independently validate the strongest health-focused open-weight research model
MESC can responsibly produce.

The target is not "the smallest medical model" and not "a fine-tuned copy of one upstream
model." The target is a health intelligence system whose measured medical quality,
evidence use, multimodal grounding, uncertainty behavior, FHIR/EHR competence, bilingual
English/Arabic competence, and reproducibility justify the `MESC` identity.

The desired public identity remains one name:

```text
MESC
```

Generation, parameter count, foundation lineage, modality state, quantization, and release
channel remain explicit in machine-readable metadata and model cards. They are not hidden,
but they do not fragment the public model name.

## 2. Non-negotiable principles

1. **Performance first.** Model size and cost are secondary until quality is established.
2. **Evidence before promotion.** No model is MESC merely because it is selected for
   experiments.
3. **Ground truth outranks teachers.** Teacher outputs are hypotheses/supervision, never
   medical truth by authority.
4. **No PHI.** Current MESC research/training remains synthetic, public, licensed,
   de-identified where explicitly permitted, or otherwise rights-qualified.
5. **Exact provenance.** Every training/evaluation record must retain source identity,
   revision, rights, transformation lineage, contamination disposition, and verification
   state where applicable.
6. **Sealed evaluation.** Training/search cannot consume Tier 3 item-level content.
7. **Verifier-first optimization.** Deterministic or independently checkable medical,
   FHIR, evidence, localization, ASR, calibration, and safety signals dominate subjective
   preference rewards where possible.
8. **Multimodality is medical, not decorative.** Medical images, speech, and physiologic
   acoustics have separate domain requirements.
9. **One MESC, explicit lineage.** Public naming stays simple while manifests remain fully
   transparent.
10. **Strategy is not authority.** This document does not satisfy any real-preflight or
    training gate by existing in the repository.

## 3. As-of-2026-09-05 model landscape decision

### 3.1 Preferred foundation candidate

```text
Qwen/Qwen3.8-27B
```

Current reasons for preference:

- 27B dense language model with native vision-language support;
- image and video understanding are part of the released architecture;
- official model card reports strong scientific/general reasoning and visual reasoning;
- native context is 262,144 tokens and can be extended in supported serving stacks;
- Apache-2.0 model license on the official Hugging Face artifact;
- official Qwen documentation lists Unsloth, Swift, and LLaMA-Factory as fine-tuning
  framework options;
- public derivative naming is not constrained by a Llama-style mandatory name prefix.

Primary sources:

- https://huggingface.co/Qwen/Qwen3.8-27B
- https://github.com/QwenLM/Qwen3.8

This is a **preferred candidate**, not a frozen MESC base. The real foundation may change
if a later model wins the same frozen qualification process.

### 3.2 Why not choose the largest available model by parameter count

`Qwen/Qwen3.8-2.4T-A95B` is materially larger and may be a useful reference, but it is not
the default foundation because:

- its model artifact currently uses a distinct `qwen3.8-max` license rather than the
  Apache-2.0 license attached to Qwen3.8-27B;
- its operational footprint is far beyond the intended iterative MESC development loop;
- its released open checkpoint is text-oriented while the managed Max service adds
  capabilities not identical to the weight release;
- any teacher/output use would require a separate rights and contamination analysis.

The program chooses the strongest **qualifiable** foundation, not the largest number on a
model card.

### 3.3 Foundation challenger set

Before a real foundation freeze, the candidate must be compared against contemporaneous
challengers that satisfy the applicable rights/runtime gates. Current strategic controls
include:

- applicable Gemma 4 multimodal checkpoints;
- `microsoft/Phi-4-multimodal-instruct`;
- applicable open-weight reasoning/vision models that emerge before the freeze;
- MedGemma as a medical specialist benchmark rather than the default lineage source.

The exact tournament roster must be frozen before execution. New models cannot be added
mid-evaluation merely because they score well on a visible subset.

## 4. Teacher council

MESC uses role-specialized teachers instead of pretending one model is strongest on every
health modality.

### 4.1 Health/general reasoning teacher candidate

```text
openai/gpt-oss-120b
```

Strategic role:

- difficult health conversation reasoning;
- evidence synthesis patterns;
- uncertainty and abstention examples;
- structured reasoning/tool-use examples where separately qualified;
- difficult negative and adversarial examples.

Why it is interesting:

- 117B total / approximately 5.1B active parameters;
- Apache-2.0 weights;
- fine-tunable open-weight model;
- official OpenAI evaluation reports strong HealthBench performance, including near-o3
  performance on HealthBench and HealthBench Hard at high reasoning effort.

Primary sources:

- https://developers.openai.com/api/docs/models/gpt-oss-120b
- https://deploymentsafety.openai.com/gpt-oss/a2
- https://openai.com/index/introducing-gpt-oss/

No gpt-oss output may enter MESC training until the exact version, usage policy,
output-use/derivative implications, prompting provenance, and contamination controls are
recorded.

### 4.2 Audio/omni teacher candidate

```text
Qwen/Qwen3-Omni-30B-A3B-Instruct
```

Strategic role:

- English/Arabic speech understanding where supported and independently verified;
- multimodal audio-text reasoning;
- audio/video grounding experiments;
- speech-output research references where relevant to future MESC interaction layers.

Primary source:

- https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Instruct

This teacher does not eliminate the need for medical acoustic models or verified
transcripts. Speech understanding and physiologic acoustics are different domains.

### 4.3 Medical vision teacher candidate

```text
lingshu-medical-mllm/Lingshu-32B
```

Strategic role after provenance qualification:

- radiology and multi-image reasoning;
- CT/MRI-oriented visual reasoning;
- histopathology, ophthalmology, dermatology, endoscopy, ultrasound, and other supported
  medical-image tasks;
- difficult medical visual grounding examples.

Primary source:

- https://huggingface.co/lingshu-medical-mllm/Lingshu-32B

The Hugging Face artifact currently declares MIT. That declaration alone is insufficient
for teacher admission. The full foundation lineage, training datasets, generated data,
licenses, and output/derivative chain must be audited before use.

### 4.4 MedGemma role

MedGemma remains one of the most important medical specialist comparators.

Current strategic default:

```text
MEDGEMMA_ROLE = BENCHMARK_AND_REFERENCE
MEDGEMMA_DISTILLATION = NOT_AUTHORIZED_BY_DEFAULT
```

Reason: Health AI Developer Foundations terms require separate analysis for derivative and
teacher-output use. MESC should not contaminate an otherwise clean lineage merely because a
medical teacher is convenient.

Primary source:

- https://developers.google.com/health-ai-developer-foundations/medgemma/model-card

### 4.5 Independent controls

At least one strong cross-family control should remain in every major evaluation campaign.
Candidate controls include:

- `microsoft/Phi-4-multimodal-instruct`;
- applicable Gemma 4 checkpoints;
- future open-weight challengers meeting the frozen admission rules.

A teacher does not grade its own success when an independent evaluator can be used.

## 5. Teacher-admission contract

Every teacher requires a record containing at minimum:

```text
teacher_id
exact_revision
weights_identity
processor_or_tokenizer_identity
license_identity
usage_policy_identity
output_use_disposition
derivative_disposition
training_data_provenance_assessment
known_benchmark_overlap
allowed_modalities
allowed_tasks
forbidden_tasks
prompt_template_identity
generation_parameters
teacher_output_schema
verification_pipeline
retention_policy
```

Possible dispositions:

```text
REJECTED
REFERENCE_ONLY
EVALUATION_ONLY
TEACHER_SEQUENCE_ONLY
TEACHER_LOGITS_ALLOWED
TEACHER_REPRESENTATIONS_ALLOWED
```

No teacher is admitted by brand reputation or benchmark score alone.

## 6. MESC data engine

### 6.1 Required data lanes

The training/data program is split into independent lanes with explicit join rules.

#### A. Biomedical evidence

Targets:

- evidence-grounded QA;
- literature synthesis;
- claim/evidence entailment;
- source-aware summarization;
- contradiction detection;
- recency and supersession handling.

Every usable record should preserve source revision and evidence spans when possible.

#### B. Clinical reasoning

Targets:

- differential reasoning under educational/research framing;
- missing-information identification;
- safe escalation and emergency recognition;
- contraindication/interaction reasoning where rights-qualified evidence exists;
- calibrated refusal/abstention;
- patient-facing and clinician-facing explanation styles without pretending deployment
  validation.

#### C. FHIR/EHR

Targets:

- FHIR R4 and later separately qualified versions;
- schema-constrained generation;
- structured extraction;
- resource linkage and longitudinal reasoning;
- deterministic validation;
- synthetic EHR workflows.

Preferred initial source family remains synthetic-first, including Synthea and
hand-authored fixtures, subject to exact version and rights qualification.

#### D. Medical vision

Separate datasets/benchmarks are required for:

- X-ray;
- CT;
- MRI;
- ultrasound;
- histopathology;
- fundus/OCT;
- dermatology;
- endoscopy;
- clinical photographs/documents;
- longitudinal and multi-image reasoning.

A single general image-caption dataset is not medical-vision training.

#### E. Clinical speech

Targets:

- dictation;
- clinician-patient conversation;
- medical terminology ASR;
- Arabic and English speech;
- spoken medical QA and evidence interaction.

#### F. Physiologic acoustics

Separate from speech:

- heart sounds;
- lung sounds;
- breathing;
- cough;
- auscultation and other validated physiologic audio tasks.

ASR metrics do not validate physiologic-acoustic competence.

#### G. Arabic medical intelligence

Arabic is a first-class evaluation/training dimension, not a translated afterthought.
Data must distinguish:

- Modern Standard Arabic;
- medically relevant terminology and transliteration;
- bilingual Arabic/English terminology;
- dialectal speech only where source quality and task definition justify it.

### 6.2 Per-record provenance fields

Training records should preserve at minimum where applicable:

```text
record_id
source_id
source_revision
source_uri
source_license
source_hash
source_date
acquisition_method
transformation_chain
teacher_id
teacher_revision
teacher_prompt_hash
teacher_generation_parameters
evidence_spans
language
modality
specialty
population
task_type
difficulty
answer_or_target
verification_status
clinician_review_status
contamination_status
heldout_membership
rights_disposition
```

Unknown rights or unknown held-out status means the record is not training-admissible.

### 6.3 Data quality pyramid

Priority order:

1. independently verified / expert or deterministic ground truth;
2. rights-clean primary medical evidence with exact citations;
3. deterministic synthetic/FHIR data;
4. carefully validated teacher-generated examples;
5. broad weak/synthetic examples only when they pass filtering and do not dominate the
   training mixture.

Volume must not compensate for uncertain rights or incorrect medical content.

## 7. Distillation and training program

Distillation is a capability-transfer mechanism. Compression is optional and late.

### Stage 0 — Untuned foundation characterization

Before training, freeze and run the exact base across the permitted development/benchmark
surface to establish:

- medical reasoning baseline;
- evidence-fidelity baseline;
- hallucination/abstention baseline;
- FHIR baseline;
- visual baseline;
- Arabic baseline;
- latency/memory/runtime baseline.

No post-training result is interpretable without this control.

### Stage 1 — Rights-clean domain adaptation, only if justified

Continued pretraining/domain adaptation is optional rather than automatic.

Eligibility requires:

- sufficiently large rights-clean corpus;
- contamination evidence;
- a hypothesis explaining why SFT/retrieval alone is insufficient;
- compute budget;
- frozen evaluation showing what improvement would justify the cost.

### Stage 2 — Ground-truth supervised fine-tuning

Prioritize:

- evidence-grounded answers;
- structured medical reasoning outputs;
- FHIR/EHR tasks;
- uncertainty/abstention examples;
- contradiction and missing-information cases;
- safe escalation;
- Arabic/English medical language.

Ground-truth examples remain weighted above teacher imitation.

### Stage 3 — Sequence-level teacher distillation

Use admitted teachers on difficult examples only after output validation.

Preferred stored target form:

```text
input
trusted_context
final_answer
concise_justification
evidence_refs
uncertainty
abstention_state
structured_output
verification_results
```

Do not require or publish raw hidden chain-of-thought as a medical training artifact.

### Stage 4 — Distribution/logit distillation where valid

When student/teacher architectures and rights permit, evaluate:

- forward/reverse KL variants;
- token-level teacher distributions;
- temperature and confidence calibration;
- mixture weighting with supervised truth.

Logit distillation is never assumed available across vendors. It must be explicitly
qualified per teacher.

### Stage 5 — On-policy generalized knowledge distillation

MESC generates from its own current policy. Teachers/evaluators then focus on the actual
failure distribution rather than only ideal demonstrations.

Required controls:

- frozen prompt/task distribution;
- bounded adaptive-query budget;
- no sealed Tier 3 item leakage;
- deduplication of repeated failures;
- verifier checks before accepted teacher corrections enter training.

### Stage 6 — Medical vision specialization

Use modality-specific ground truth and teacher candidates where qualified.

Training must distinguish:

- classification/report reasoning;
- localization/grounding;
- cross-image and longitudinal comparison;
- high-dimensional/volume-derived representations;
- document/chart understanding.

Where a medical specialist teacher and MESC use different visual tokenization, evaluate
representation/affinity distillation instead of relying only on text answers.

### Stage 7 — Verifier-guided preference/RL optimization

Rewards should be decomposed rather than collapsed into one style score.

Candidate verifiers include:

- FHIR validators;
- schema/JSON validation;
- exact evidence citation checks;
- claim/evidence entailment;
- answerability/abstention scoring;
- localization metrics;
- ASR WER/CER;
- calibration metrics;
- safety rule/evaluator outputs;
- contamination and provenance gates.

A hard safety/evidence failure cannot be offset by a higher average capability reward.

### Stage 8 — Audio integration

Clinical speech and physiologic acoustics are separate projects sharing MESC reasoning.

Possible architecture paths to evaluate:

1. qualified audio encoder + projector into the MESC language model;
2. distillation from an admitted omni teacher;
3. specialist physiologic-acoustic encoder producing grounded evidence tokens;
4. future migration to a stronger native-omni foundation only if the migration wins the
   full frozen evaluation suite.

Do not replace the reasoning foundation merely to gain an audio checkbox.

### Stage 9 — Compression only after quality leadership

Optional techniques:

- quantization;
- structured pruning where architecture permits;
- distillation to a smaller student;
- sparse/MoE migration only under a new qualification campaign.

A compressed artifact may be distributed only if its own medical non-regression gates
pass. It does not inherit the flagship evidence automatically.

## 8. Evaluation system

### 8.1 Evaluation families

The MESC evaluation package should cover:

#### Health conversation and reasoning

- realistic health conversations;
- medical QA as a component, not the whole benchmark;
- difficult evidence synthesis;
- uncertainty and missing information;
- emergency/escalation behavior.

#### Evidence fidelity

- citation entailment;
- source correctness;
- contradiction detection;
- unsupported-claim rate;
- evidence recency/supersession.

#### Safety and calibration

- harmful overconfidence;
- abstention accuracy;
- expected calibration error and task-appropriate calibration metrics;
- unsafe advice/refusal balance;
- critical subgroup performance.

#### FHIR/EHR

- structural validity;
- semantic correctness;
- longitudinal consistency;
- tool/function correctness;
- constrained vs unconstrained decoding comparisons.

#### Medical vision

- per-modality performance;
- visual grounding;
- multi-image integration;
- longitudinal comparison;
- document/chart reasoning.

#### Audio

Speech:

- WER/CER;
- medical terminology accuracy;
- semantic QA from audio;
- Arabic/English robustness.

Physiologic acoustics:

- domain-specific classification/detection/reasoning metrics;
- calibration and OOD behavior;
- evidence linkage to acoustic findings.

### 8.2 Competitor set

At freeze time, include strong contemporary references where rights and access permit.
The current strategic set includes:

- MedGemma variants appropriate to each task;
- gpt-oss-120b for health/reasoning reference;
- Lingshu-32B for medical vision after provenance qualification;
- Gemma 4 multimodal checkpoints;
- Phi-4 multimodal;
- the untuned MESC foundation;
- relevant Qwen general/omni references;
- appropriate proprietary references only where evaluation terms, privacy, and budgets
  permit.

### 8.3 Claim discipline

The following statement is a project aspiration, not a current result:

```text
GOAL: MESC becomes the best validated health model in its declared scope.
```

The following is forbidden until supported by independently reviewed evidence:

```text
CLAIM: MESC is the best health model.
```

## 9. Compute and development strategy

### 9.1 Founder workstation policy

The project must not require a powerful local laptop/GPU.

### 9.2 Google Colab

Colab is the default development surface for:

- notebooks and smoke tests;
- LoRA/QLoRA feasibility;
- dataset validation/transformation;
- compact ablations;
- evaluation harness runs that fit the runtime;
- reproducibility instructions.

Unsloth is a preferred optimization framework when it supports the exact frozen model and
does not alter evaluation semantics.

### 9.3 Rented accelerators

The performance-first objective permits separately authorized cloud accelerator bursts for:

- 27B multimodal fine-tuning where Colab is insufficient;
- gpt-oss-120b teacher inference;
- large teacher generation;
- medical-vision training;
- long-context evaluation;
- verifier/RL campaigns;
- audio/omni training.

Likely accelerator classes may include A100/H100/B200 or contemporary equivalents, but no
specific provider or hardware is authorized until MRL runtime evidence exists.

### 9.4 Cost discipline

Performance-first is not blank-check compute.

Every campaign freezes:

- GPU type/count;
- maximum GPU-hours;
- token budget;
- teacher-query budget;
- storage budget;
- monetary ceiling;
- retry ceiling;
- early-stop criteria.

## 10. Security and reproducibility

Before a model enters real execution:

- `trust_remote_code` posture must be explicit and fail closed by default;
- processor/tokenizer/model revisions must be immutable;
- all downloaded artifacts must be hashed or otherwise content-identified;
- dependency lock must be frozen;
- network policy must be explicit;
- credentials must never enter repository evidence;
- training outputs must be content-addressed and bound to the input manifest/code tree;
- experiment randomness must be recorded;
- resume/checkpoint behavior must preserve lineage;
- generated teacher data must record exact teacher and generation configuration.

## 11. MRL mapping — how this strategy becomes executable truth

This strategy intentionally maps to the existing canonical MRL real-preflight tasks rather
than creating a parallel authority path.

### MRL-0801 — Exact model/weights evidence

Must eventually bind:

- selected MESC foundation exact immutable revision;
- model config;
- tokenizer/processor;
- vision encoder/projector artifacts;
- all shard identities;
- license/NOTICE;
- access/custody evidence.

Current state remains `PLANNED / evidence absent`.

### MRL-0802 — Corpus rights and exact identity

Must bind every admitted data source and the exact transformed training corpus.

For medical imaging, admission additionally requires exact evidence for all applicable
privacy and custody surfaces, including:

- source, patient-grouping, study, series, and object identities sufficient to audit
  provenance without exposing PHI;
- data-custody chain from acquisition/receipt through every transformation and export;
- DICOM metadata inventory and disposition, including private tags where DICOM is used;
- burned-in text, overlays, annotations, screenshots, and pixel-region PHI inspection;
- the exact de-identification method/configuration plus evidence that it was applied to
  the admitted bytes;
- residual-PHI assessment after transformation, including any modality-specific risk;
- exact rights/license/consent or other applicable use authority for the admitted source
  and transformed corpus.

If any required medical-image identity, privacy, de-identification, rights, or custody
evidence is missing, ambiguous, stale, or cannot be bound to the exact bytes, the image
source is rejected from training/evaluation admission under this program. A dataset label
such as "de-identified" is not sufficient evidence by itself.

Current state remains `PLANNED / evidence absent`.

### MRL-0803 — Contamination and held-out isolation

Must prove:

- training corpus contamination assessment;
- benchmark/test exclusion;
- teacher-generation prompt/source lineage;
- sealed-evaluation isolation;
- temporal/hand-authored canaries where applicable.

For medical imaging, the proof must also bind patient/study-aware isolation rather than
file-level splitting alone. It must include, where applicable:

- patient-level and study-level split identities and grouping rules;
- series/view/instance grouping so related images cannot cross train/search/replication/
  sealed boundaries unintentionally;
- exact/perceptual near-duplicate detection across images and derived renditions;
- report-image, crop/patch, frame/clip, slice/volume, and augmentation lineage checks;
- explicit protection against the same patient, study, or derived clinical episode
  leaking across adaptive and sealed evaluation surfaces;
- evidence that teacher prompts, captions, reports, or generated supervision did not
  import held-out image content or labels into training.

If patient/study grouping, image-lineage, duplicate, or held-out evidence is unavailable or
ambiguous, the affected medical-image material is not admitted to a scientific training or
evaluation claim.

Current state remains `PLANNED / evidence absent`.

### MRL-0804 — Runtime/GPU qualification

Must record the actual Colab/cloud environment used for the selected experiment, including
GPU identity, Python/CUDA/framework versions, memory evidence, and bounded smoke results.

Current state remains `PLANNED / evidence absent`.

### MRL-0805 — Applicable training authorization

Must be a separate authority artifact. Founder standing approval and this strategy document
do not automatically satisfy the canonical training-authorization trust path.

Current state remains `PLANNED / evidence absent`.

### MRL-0806 — Frozen objective and budgets

The first real experiment must have exact:

- research question/hypothesis;
- foundation/teacher roles;
- trainable/frozen module set;
- dataset identities;
- hyperparameter search bounds;
- resource budget;
- adaptive-query budget;
- result-exposure budget;
- success, null, falsification, and stop conditions.

Current state remains `PLANNED / evidence absent`.

### MRL-0807 — Evaluator and sealed Tier 3 identities

Must freeze exact evaluator code, model/human evaluator identities where applicable,
sealed dataset identities, and allowed aggregate outputs.

Current state remains `PLANNED / evidence absent`.

### MRL-0808 — Execution sandbox

Must freeze allowed network/filesystem/mutation/output/rollback/stop surfaces.

Current state remains `PLANNED / evidence absent`.

### MRL-0809 and MRL-0899

Only after 0801..0808 have genuine admitted evidence may exact-head preflight qualification
run and the separate `MRL_REAL_EXPERIMENT_READY` decision be considered.

This document cannot make that decision.

## 12. First real experiment sequence after preflight becomes eligible

The intended dependency order, subject to future frozen objective evidence, is:

1. **Foundation baseline qualification** — untuned Qwen3.8-27B candidate vs frozen
   challengers on development/non-sealed health + FHIR + vision tasks.
2. **Foundation decision evidence candidate** — retain or reject Qwen3.8-27B without
   promotion language.
3. **Ground-truth medical/FHIR SFT pilot** — small bounded run, no teacher data.
4. **Teacher admission campaigns** — qualify gpt-oss, Qwen3-Omni, Lingshu, and controls
   separately.
5. **Reasoning capability-distillation pilot** — admitted health reasoning teacher on
   verified difficult examples.
6. **On-policy failure distillation** — bounded actual-MESC failure correction.
7. **Medical-vision specialization** — only after image corpus and evaluator gates exist.
8. **Arabic medical specialization** — text first, then speech under its own evidence.
9. **Verifier-guided optimization** — frozen decomposed rewards and safety floors.
10. **Audio program** — clinical speech before physiologic acoustic expansion unless the
    frozen research questions justify a different order.
11. **Independent sealed evaluation**.
12. **Promotion/release governance** — only under the future dedicated authority required
    by ADR-0033.

## 13. What future agents must not do

A future agent reading this plan must not:

- treat `Qwen/Qwen3.8-27B` as already downloaded, trusted, trained, or promoted;
- use latest-model marketing as a substitute for frozen evidence;
- silently switch to Qwen3.8-Max or another model with a different license;
- use MedGemma outputs as training data by default;
- use Lingshu outputs before provenance/derivative qualification;
- let any teacher see sealed Tier 3 item-level content during adaptive training;
- mix benchmark/test questions into synthetic training prompts;
- use PHI or private patient data;
- claim clinical validation from medical QA benchmarks;
- claim MESC is "best" before the required independent evaluation;
- require the Founder to own a local GPU;
- let Colab convenience force a weaker flagship architecture;
- compress MESC merely to make parameter-count marketing easier;
- hide upstream lineage because the public model is named only `MESC`;
- bypass MRL-0801..MRL-0899 or ADR-0033.

## 14. Strategy refresh rule

Model markets change quickly. The **goal and gate structure** are stable; specific upstream
candidates are time-sensitive.

Immediately before MRL-0801 evidence is created for the first real foundation, perform a
fresh model-landscape review dated to that execution window. Replace the preferred
candidate only if the replacement:

- satisfies naming/license/derivative requirements;
- is technically trainable under the available compute plan;
- wins or has a strong falsifiable reason to win the frozen pre-training tournament;
- improves MESC's health objective rather than general leaderboard prestige alone.

Any replacement must be recorded through canonical repository governance rather than a
chat-only decision.

## 15. Current disposition

As of this strategy package:

```text
PUBLIC_MODEL_NAME = MESC
PROGRAM_OBJECTIVE = PERFORMANCE_FIRST_HEALTH_MODEL
PREFERRED_FOUNDATION_CANDIDATE = Qwen/Qwen3.8-27B
PRIMARY_REASONING_TEACHER_CANDIDATE = openai/gpt-oss-120b
PRIMARY_OMNI_AUDIO_TEACHER_CANDIDATE = Qwen/Qwen3-Omni-30B-A3B-Instruct
PRIMARY_MEDICAL_VISION_TEACHER_CANDIDATE = lingshu-medical-mllm/Lingshu-32B
MEDGEMMA_DEFAULT_ROLE = BENCHMARK_REFERENCE
COLAB = DEVELOPMENT_SURFACE
LOCAL_GPU_REQUIRED = FALSE
RENTED_ACCELERATOR_BURSTS = STRATEGICALLY_ALLOWED_BUT_NOT_EXECUTION_AUTHORIZED
DISTILLATION_GOAL = CAPABILITY_TRANSFER_FIRST
COMPRESSION = OPTIONAL_AFTER_QUALITY_LEADERSHIP
MRL_REAL_EXPERIMENT_READY = FALSE
TRAINING_READY = FALSE
```

No scientific result, model promotion, runtime success, training success, or release is
claimed by this document.