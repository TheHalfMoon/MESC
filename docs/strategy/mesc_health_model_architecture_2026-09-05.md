# MESC Health Model Architecture — Performance-First Blueprint

- **Date:** 2026-09-05
- **Status:** FOUNDER-DIRECTED ARCHITECTURE STRATEGY / NO EXECUTION AUTHORITY
- **Public model identity:** `MESC`
- **Decision:** `docs/adr/0036-performance-first-health-model-strategy.md`
- **Program:** `docs/strategy/mesc_health_model_program_2026-09-05.md`
- **Execution governance:** `specs/mesc-research-loop-v1/`

## 1. Architectural objective

MESC should be designed as a health intelligence architecture, not as a medical-chatbot
fine-tune.

The long-term capability envelope includes:

```text
text
medical documents
FHIR / structured EHR
longitudinal clinical timelines
2D medical images
3D / volumetric imaging
whole-slide pathology
image sequences / video
clinical speech
physiologic acoustics
ECG / PPG / EEG and other qualified waveforms
tabular and laboratory time series
evidence retrieval
tools
structured actions in synthetic/research environments
```

Not every modality must be trained in the first generation. The architecture must avoid a
dead end that would require discarding the reasoning model merely to add one later.

## 2. Design rule: one MESC identity, modular capability plane

The public model remains `MESC`, but the internal architecture may contain separately
qualified components.

```text
                         ┌─────────────────────┐
                         │        MESC         │
                         │ health intelligence │
                         └──────────┬──────────┘
                                    │
                 ┌──────────────────┼──────────────────┐
                 │                  │                  │
          reasoning core      evidence plane      verifier plane
                 │                  │                  │
      ┌──────────┼──────────┐       │        ┌─────────┼─────────┐
      │          │          │       │        │         │         │
    text       vision     audio/   provenance FHIR   citation  safety /
                       biosignal            checks  checks    calibration
      │          │          │
      └──────────┴────┬─────┘
                     │
              grounded evidence
                     │
             tools / retrieval
                     │
            MCRL task-time layer
```

The diagram expresses interfaces, not current implementation authority.

## 3. Reasoning core

### 3.1 Current preferred candidate

As of 2026-09-05:

```text
Qwen/Qwen3.8-27B
```

is the preferred candidate for the first performance-first MESC reasoning/vision core.

It remains a candidate until the canonical MRL evidence path qualifies an exact immutable
revision and the frozen foundation comparison retains it.

### 3.2 Core responsibilities

The reasoning core should eventually provide:

- medical and biomedical language reasoning;
- evidence synthesis;
- uncertainty and abstention behavior;
- longitudinal reasoning;
- native image/video reasoning where the selected foundation supports it;
- tool selection and structured invocation planning;
- FHIR/EHR semantic reasoning;
- Arabic and English medical reasoning;
- integration of grounded observations from specialist perception modules.

### 3.3 Core non-responsibilities

Do not require the language model itself to directly learn every raw medical signal if a
specialist encoder provides a more reproducible and scientifically defensible interface.

Examples:

- raw 3D CT/MRI volumes may require a volume encoder rather than flattening arbitrary image
  slices into a generic VLM prompt;
- whole-slide pathology may require patch/slide aggregation;
- ECG/PPG/EEG require waveform-aware encoders;
- heart/lung sounds require physiologic-acoustic encoders distinct from speech ASR.

## 4. Medical perception plane

### 4.1 Native general vision

Use the selected foundation's native image/video encoder as the baseline visual surface.
It establishes the control condition for deciding whether specialist medical encoders add
value.

Never assume a specialist encoder is necessary without an ablation, and never assume a
general vision encoder is sufficient because it can accept pixels.

### 4.2 Specialist image encoders

Candidate domains that may justify specialists:

```text
chest X-ray
CT
MRI
ultrasound
echocardiography
histopathology / WSI
fundus / OCT
dermatology
endoscopy
nuclear medicine / PET
clinical photography
medical documents / charts
```

Each specialist must expose grounded findings through an explicit interface that preserves
source location and uncertainty where technically possible.

A preferred conceptual representation is:

```text
PerceptionEvidence {
  modality
  source_id
  source_revision
  time
  anatomical_region
  observation
  localization
  measurement
  confidence
  uncertainty
  quality_flags
  provenance
}
```

This is a strategy-level shape, not an implemented schema.

### 4.3 3D and longitudinal imaging

3D and longitudinal imaging are first-class problems.

MESC should be evaluated on:

- cross-slice / cross-volume consistency;
- temporal comparison;
- lesion/findings localization;
- measurement change;
- acquisition-quality limitations;
- prior-study reconciliation;
- disagreement between modalities.

A stack of unrelated 2D captions is not a valid substitute for volumetric reasoning.

## 5. Audio and physiologic-signal plane

### 5.1 Clinical speech

Clinical speech includes:

- physician dictation;
- clinician-patient conversation;
- patient history speech;
- radiology/pathology dictation;
- spoken medical questions;
- Arabic and English terminology.

Required capability dimensions:

- ASR;
- medical terminology accuracy;
- speaker/context awareness where rights-qualified;
- semantic reasoning from audio;
- uncertainty when audio quality is poor;
- preservation of timestamps where relevant.

### 5.2 Physiologic acoustics

Physiologic audio is not speech.

Potential domains:

- heart sounds;
- lung sounds;
- breathing;
- cough;
- digital stethoscope signals;
- other separately qualified acoustic biomarkers.

The model must not use speech-ASR performance as evidence of physiologic-acoustic
competence.

### 5.3 Waveforms and biosignals

Future MESC generations should reserve a capability path for:

```text
ECG
PPG
EEG
continuous vital-sign waveforms
wearable sensor streams
other clinically justified physiologic time series
```

Every waveform family requires exact sampling/device/preprocessing provenance. Device and
site domain shift must be treated as an evaluation dimension.

### 5.4 Audio/omni teacher role

`Qwen/Qwen3-Omni-30B-A3B-Instruct` is the current preferred omni/audio teacher candidate,
not a physiologic-audio ground-truth source.

It may contribute speech/audio capability only after source-specific teacher admission.
Physiologic-acoustic labels require independent ground truth or domain-specific validation.

## 6. Structured health-data plane

### 6.1 FHIR

FHIR remains the canonical interoperability surface already established by repository
governance.

MESC should distinguish:

- schema validity;
- semantic validity;
- resource relationship reasoning;
- temporal reasoning;
- tool/API correctness;
- provenance;
- missing-resource behavior.

A structurally valid FHIR object can still be medically wrong. Both layers must be scored.

### 6.2 Longitudinal EHR

Longitudinal reasoning must preserve:

- event time;
- episode boundaries;
- medication start/stop/change;
- problems and state transitions;
- laboratory trends;
- imaging chronology;
- procedures;
- interventions;
- response to treatment;
- stale vs current information;
- provenance of every observation.

The training representation must not collapse a timeline into an unordered note pile.

### 6.3 Tables and laboratory data

MESC should support structured and semi-structured laboratory/measurement reasoning,
including units, reference ranges, trends, missingness, and conflicting measurements.

Deterministic calculation tools should be preferred over asking model weights to memorize
arithmetic procedures.

## 7. Evidence and retrieval plane

MESC's differentiator is not raw memorization.

The target behavior is:

```text
question / task
      │
      ▼
identify needed evidence
      │
      ▼
retrieve / inspect authorized sources
      │
      ▼
construct claims bound to evidence
      │
      ▼
verify claim-support relationship
      │
      ▼
answer / abstain / request more evidence
```

### 7.1 Evidence contract

Every high-stakes reasoning output should be able to represent:

```text
CLAIM
EVIDENCE
SOURCE
PROVENANCE
CONFIDENCE
UNCERTAINTY
CONTRADICTION
MISSING_INFORMATION
ABSTENTION
RECOMMENDED_NEXT_EVIDENCE
```

### 7.2 Retrieval is not automatic training authority

A source that may be retrieved for an authorized evaluation/runtime task is not
necessarily licensed for training. Retrieval rights, training rights, redistribution
rights, and benchmark-use rights remain separate fields.

## 8. Tool plane

MESC should learn when to use deterministic tools instead of hallucinating an answer.

Potential tool classes include:

- FHIR validators;
- terminology services;
- unit conversion;
- clinical calculators where appropriately governed;
- evidence search/retrieval;
- structured database queries;
- image measurement/localization tools;
- signal-analysis tools;
- citation verification.

Tool-use training must include failures, missing tools, stale results, contradictory tool
outputs, and retry ceilings.

The MRL research agent and MCRL task-time layer retain their existing authority boundaries.
A model-generated tool call does not grant the tool permission to act.

## 9. Verifier plane

The verifier plane should become a central MESC research contribution.

### 9.1 Deterministic verifiers

Prefer deterministic validation when available:

- FHIR structural validation;
- JSON/schema validation;
- unit/dimensional checks;
- exact citation/source identity;
- retrieval provenance;
- executable calculations;
- checksum/artifact identity.

### 9.2 Learned or expert-calibrated verifiers

Use learned/expert evaluation only where deterministic truth is unavailable:

- medical factuality;
- claim-evidence entailment;
- clinical reasoning quality;
- visual grounding;
- safety;
- communication quality.

Learned judges must be calibrated against human/expert or higher-confidence evidence on the
scope where their scores are used.

### 9.3 Hard floors

The optimization function must keep hard non-regression floors for:

```text
medical safety
evidence fidelity
harmful overconfidence
abstention
contamination
reproducibility
critical subgroups
```

A general benchmark gain cannot compensate for violating a hard floor.

## 10. Teacher council architecture

Current strategic candidates:

```text
Health / general reasoning:
  openai/gpt-oss-120b

Audio / omni:
  Qwen/Qwen3-Omni-30B-A3B-Instruct

Medical vision:
  lingshu-medical-mllm/Lingshu-32B
  only after provenance qualification

Medical benchmark/reference:
  MedGemma variants
  not a distillation source by default

Independent multimodal controls:
  Phi-4 Multimodal
  applicable Gemma 4 checkpoints
```

Teacher specialization does not mean teacher voting establishes truth.

### 10.1 Teacher disagreement

When admitted teachers disagree:

1. prefer trusted ground truth if available;
2. prefer deterministic verifier evidence;
3. inspect source evidence;
4. retain disagreement as a training/evaluation signal;
5. do not majority-vote an uncertain medical statement into the corpus.

### 10.2 Teacher-generated examples

Every admitted teacher example must retain:

- exact teacher identity/revision;
- prompt/template hash;
- decoding/generation parameters;
- input source identities;
- verification results;
- rejection reason if filtered;
- contamination disposition.

## 11. Training architecture

The initial performance-first training sequence should be staged rather than one giant
mixture run.

### Phase A — Foundation characterization

Deliverables:

- exact base-model manifest;
- untuned health/FHIR/vision/Arabic baseline;
- runtime/memory measurements;
- error taxonomy;
- frozen challenger comparison.

### Phase B — Evidence/FHIR/medical ground-truth SFT

Train only on rights-clean, provenance-bearing data.

Objectives:

- evidence-grounded answers;
- uncertainty and abstention;
- FHIR/EHR structured reasoning;
- longitudinal reasoning;
- medical terminology;
- Arabic/English core competence.

### Phase C — Reasoning capability distillation

Use only admitted teacher roles and validated examples.

Objectives:

- difficult reasoning;
- evidence synthesis;
- missing-information handling;
- correction of observed MESC failures.

### Phase D — Medical vision specialization

Introduce medical-image datasets and specialist teachers/encoders only after their own
rights and evaluator gates.

### Phase E — On-policy failure curriculum

Generate current MESC failures on Tier 1/search material, classify them, obtain bounded
teacher/verifier feedback, and train on accepted corrections.

Do not adapt on Tier 3 item-level content.

### Phase F — Verifier-guided preference / RL

Use decomposed rewards with hard safety/evidence floors. Preference optimization without a
medical/verifiable rationale is not sufficient.

### Phase G — Clinical speech

Add speech only after exact speech datasets, runtime, evaluators, WER/CER policy, medical
terminology scoring, and Arabic/English test surfaces exist.

### Phase H — Physiologic acoustics and waveforms

Treat each signal family as a separately governed research program with domain-specific
metrics, device/preprocessing provenance, and OOD evaluation.

### Phase I — Independent sealed evaluation

Run only after all adaptive work is frozen. Tier 3 item-level content remains hidden from
the training/search process.

### Phase J — Compression / serving optimization

Only after the strongest validated MESC checkpoint is established:

- quantization;
- pruning where justified;
- smaller-student distillation;
- serving optimization.

Every compressed artifact needs its own medical non-regression evidence.

## 12. Data-mixture control

Do not create one opaque `medical_dataset.jsonl`.

Every training mixture must record exact lane weights and sampling policy.

Conceptual lanes:

```text
biomedical evidence
clinical reasoning
FHIR / structured EHR
longitudinal EHR
medical documents
medical vision by modality
Arabic medical text
clinical speech
physiologic acoustics
waveforms / biosignals
tool-use / verifier examples
abstention / uncertainty
safety / adversarial examples
teacher-generated accepted examples
```

Ablations must be able to remove a lane and measure its marginal value.

## 13. Contamination architecture

Contamination control must cover more than exact text matches.

Required approaches should include, where feasible:

- exact and normalized hashing;
- near-duplicate/minhash or equivalent similarity checks;
- benchmark-question paraphrase detection;
- image identity/perceptual duplicate checks;
- audio fingerprint/similarity checks;
- patient/case identity boundaries where applicable to rights-qualified de-identified data;
- teacher-prompt contamination tracking;
- temporal cutoff evaluation sets;
- hand-authored canaries.

Unknown contamination state means the example is not admitted to a sealed scientific
claim.

## 14. Evaluation matrix

No single score defines MESC quality.

| Axis | Minimum required evidence family |
|---|---|
| Health reasoning | realistic health conversations + difficult medical reasoning |
| Knowledge | medical QA plus broader biomedical knowledge |
| Evidence | claim support, citation entailment, contradiction, recency |
| Calibration | confidence/reliability, abstention, harmful overconfidence |
| Safety | emergency escalation, unsafe advice, medication-risk scenarios |
| FHIR | structure, semantics, longitudinal/resource reasoning, tool correctness |
| EHR | timeline consistency, trend and state-change reasoning |
| Vision | per-modality performance, grounding, multi-image, longitudinal, 3D where applicable |
| Documents | medical forms/reports/tables/charts |
| Arabic | native Arabic medical reasoning and communication, not translation-only |
| Speech | WER/CER, terminology, semantic reasoning, noisy/OOD audio |
| Acoustics | domain-specific physiologic metrics and calibration |
| Waveforms | domain-specific signal metrics, device/domain-shift robustness |
| Tools | selection, parameters, verification, failure recovery |
| Reproducibility | exact model/data/code/runtime/artifact identities |
| Contamination | train/eval isolation evidence |
| Subgroups/OOD | critical populations and distribution shift |

## 15. Definition of "best health model"

`MESC is the best health model` is not a strategy decision. It is a future evidence claim.

A serious leadership claim requires:

1. a pre-registered evaluation matrix;
2. strong contemporary open and proprietary comparators where terms permit;
3. independently controlled sealed evaluation;
4. no critical hard-floor regression;
5. clinician/expert calibration for subjective medical dimensions;
6. public reproducibility evidence for all publishable surfaces;
7. explicit declaration of unsupported modalities or populations.

If MESC leads only on a subset, the claim must be scoped to that subset.

## 16. Compute architecture

### Development

Default:

```text
Google Colab
+ repository-pinned environment
+ Unsloth where the exact selected model is supported and qualified
```

No powerful local Founder laptop/GPU is required.

### Flagship campaigns

Large runs may use separately authorized rented accelerators such as contemporary
A100/H100/B200-class or equivalent hardware.

Every campaign freezes:

- provider/runtime identity;
- accelerator type/count;
- maximum GPU-hours;
- token/query budget;
- storage budget;
- monetary ceiling;
- retry ceiling;
- checkpoint policy;
- stop conditions.

Performance-first does not mean unbounded compute.

## 17. Repository implementation surfaces — future only

When implementation authority exists, prefer extending existing MESC/MedScale contracts
rather than creating an unrelated training stack.

Future implementation should preserve separation between:

```text
model/data identity
training configuration
teacher admission
experiment plan
experiment receipt
evaluation evidence
promotion/release authority
```

Likely future surfaces may include:

```text
src/medscale/mesc/        model/research contracts and adapters
specs/mesc-research-loop-v1/  canonical MRL authority/evidence path
docs/research/            research questions and evaluation definitions
docs/models/              model cards / registry
```

These are architectural destinations, not permission to add code before the canonical task
ledger makes the work eligible.

## 18. Dependency-ordered realization

The architecture becomes real only through this order:

```text
strategy accepted
  ↓
research question / objective frozen
  ↓
model + data + runtime + evaluator evidence exists
  ↓
MRL-0801..0808 admitted
  ↓
MRL-0809 exact-head preflight
  ↓
MRL-0899 readiness decision
  ↓
separate training authority where required
  ↓
bounded experiment
  ↓
receipt + independent evaluation
  ↓
replication / sealed evaluation
  ↓
future promotion governance
  ↓
release
```

No arrow may be inferred merely because later architecture is described in this document.

## 19. Permanent anti-shortcuts

Future agents must not:

- make MESC smaller at the expense of medical quality merely for deployment marketing;
- choose a foundation solely because it already has every modality checkbox;
- concatenate incompatible model weights;
- treat teacher consensus as medical truth;
- ingest benchmark/test data into training;
- use PHI or patient telemetry as research learning input under current governance;
- equate ASR with physiologic-audio competence;
- equate 2D image captioning with volumetric medical reasoning;
- flatten longitudinal records into orderless text and claim temporal intelligence;
- let an LLM judge replace deterministic validation where deterministic validation exists;
- hide upstream model/data lineage because the public name is `MESC`;
- let Colab limitations decide the flagship model quality ceiling;
- reuse stale historical Backbone Tournament readiness for a new model;
- claim `MESC is best` without the independent evidence defined above.

## 20. Current architectural disposition

```text
PUBLIC_IDENTITY = MESC
OBJECTIVE = BEST_VALIDATED_HEALTH_MODEL_WITHIN_DECLARED_SCOPE
SIZE_PRIORITY = SECONDARY
PREFERRED_CORE_CANDIDATE = Qwen/Qwen3.8-27B
NATIVE_CORE_MODALITIES = TEXT + IMAGE + VIDEO
AUDIO_STRATEGY = SEPARATELY_QUALIFIED_ADAPTER_OR_FUTURE_NATIVE_MIGRATION
MEDICAL_VISION_STRATEGY = NATIVE_BASELINE + QUALIFIED_SPECIALIST_ENCODERS
PHYSIOLOGIC_AUDIO = DISTINCT_FROM_SPEECH
BIOSIGNALS = RESERVED_FUTURE_CAPABILITY
FHIR = CANONICAL_STRUCTURED_HEALTH_SURFACE
EVIDENCE_AND_VERIFIERS = FIRST_CLASS
ARABIC = FIRST_CLASS_CAPABILITY_AND_EVALUATION_DIMENSION
LOCAL_GPU_REQUIRED = FALSE
COLAB = DEFAULT_DEVELOPMENT_SURFACE
LARGE_RENTED_COMPUTE = ALLOWED_BY_STRATEGY_ONLY / REQUIRES SEPARATE AUTHORITY
MRL_REAL_EXPERIMENT_READY = FALSE
TRAINING_READY = FALSE
```

This blueprint records intended architecture only. It claims no runtime, training, medical,
multimodal, or clinical result.