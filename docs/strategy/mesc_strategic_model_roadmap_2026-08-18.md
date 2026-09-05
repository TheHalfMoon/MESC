# MESC Strategic Model Roadmap — Historical Strategy Draft

> **Supersession notice (2026-09-05):** The future-facing model-family selection,
> public model naming, size-first/compact-first assumptions, and blanket Chinese-model
> exclusion in this document are superseded by
> `docs/adr/0036-performance-first-health-model-strategy.md` and
> `docs/strategy/mesc_health_model_program_2026-09-05.md` once that exact package is
> canonically merged. Historical Pilot-01 B0 facts and provenance in this file remain
> preserved and are not rewritten by the new strategy. This file grants no execution
> authority.

Date: 2026-08-18
Status: SUPERSEDED FOR FUTURE MODEL STRATEGY / HISTORICAL B0 CONTEXT PRESERVED
Repository context: TheHalfMoon/MESC

> **Canonical reconciliation (2026-08-19):** Pilot-01 B0 was subsequently
> authorized separately, executed exactly once over the frozen 150-example
> validation input, and accepted canonically in PR #123 at merge commit
> `3f34b35daf4050d010a5f0061d6e8387f9649c10`. This strategy document does not
> authorize a second B0 run, B1, P01-06+, training, retrieval, test-partition
> execution or scientific-content inspection, fallback substitution, or
> quantization changes.

## North Star

MESC should become an open, auditable medical foundation-model family that can:
- reason over evidence,
- quantify uncertainty,
- abstain when evidence is insufficient,
- integrate multimodal clinical inputs,
- preserve training/evaluation provenance,
- and remain reproducible enough for serious scientific scrutiny.

Target positioning:

> MESC: an open, auditable medical intelligence that can read, see, listen, reason over evidence, quantify uncertainty, and know when to abstain.

## Product / Research Ladder

### MESC 1.0 — Evidence-Calibrated Medical Reasoning

Core capabilities:
- biomedical / clinical reasoning
- evidence grounding
- provenance-aware answers
- uncertainty calibration
- abstention
- contradiction handling
- safety
- structured clinical output
- tool/FHIR readiness

Model strategy:
- Preserve the completed Llama-3.2-3B-Instruct Pilot-01 B0 as the canonical scientific general-model control.
- Do not promote Llama-3.2-3B as the MESC flagship by default.
- After Pilot-01 closeout and only under separate authorization, run a bounded backbone tournament.

Proposed backbone tournament candidates (design-time only; no execution authority here):
1. OpenAI gpt-oss-20b — flagship reasoning candidate.
2. Swiss AI Apertus 1.5 8B — compact / long-term multimodal candidate.
3. Microsoft Phi-4 Multimodal 5.6B — native multimodal control.
4. Google MedGemma 1.5 4B IT — medical-specialist control.

Tournament goal:
- choose one Compact backbone,
- choose one Flagship/Reasoner backbone,
- avoid training every candidate deeply.

Training ladder:
1. Base-model baseline
2. Domain adaptation only if evidence justifies it
3. Evidence-grounded SFT
4. Clinical reasoning SFT
5. Uncertainty / abstention SFT
6. Preference optimization
7. Verifiable medical RL where appropriate
8. Safety / adversarial training
9. Calibration
10. Held-out evaluation

### MESC 1.1 — English + Arabic Medical Intelligence

Add:
- high-quality Arabic medical language support
- bilingual evidence grounding
- Arabic clinical communication
- Arabic/English terminology robustness
- culturally and regionally appropriate evaluation

This is a strategic differentiation layer, not a shortcut around core 1.0 quality.

### MESC 2.0 — AMGE Medical Visual Intelligence

AMGE = MESC medical visual perception subsystem.

Scope:
- chest X-ray
- CT / 3D imaging
- MRI
- pathology
- ophthalmology
- dermatology
- ultrasound
- segmentation / localization
- longitudinal image comparison

Architecture principle:
- do not force one generic vision encoder to solve every medical imaging domain;
- permit specialist encoders and modality-specific experts;
- convert grounded visual evidence into a common MESC reasoning/evidence contract.

Representative donor/reference families:
- MedSigLIP
- MerMED-FM
- RAD-DINO
- CT-FM
- MONAI/VISTA
- MedGemma medical vision capabilities

Licensing must be checked per donor. Non-commercial / no-derivatives dependencies must not silently become core commercial/open dependencies.

### MESC 3.0 — Medical Omni

Unify:
- text
- medical imaging
- 3D imaging
- clinical speech
- physician dictation
- heart sounds
- lung sounds
- breathing
- cough / respiratory sounds
- evidence
- tools / FHIR

Audio must be separated into two classes:

1. Semantic clinical speech:
   - doctor dictation
   - clinical conversation
   - patient speech
   - radiology dictation

2. Physiologic acoustic signals:
   - heart sounds
   - lung sounds
   - cough
   - breathing
   - auscultation signals

Physiologic audio is not merely speech transcription.

Representative donor/reference families:
- MedASR for clinical speech
- HeAR for health-acoustic representation learning
- StethoLM-style cardiopulmonary reasoning benchmarks / approaches

## Unified MESC Clinical Contract

Every MESC generation / reasoning layer should be capable of representing:

- CLAIM
- EVIDENCE
- SOURCE / PROVENANCE
- CONFIDENCE
- UNCERTAINTY
- CONTRADICTION
- MISSING_INFORMATION
- ABSTENTION
- RECOMMENDED_NEXT_EVIDENCE

The moat is not only medical knowledge.
The moat is reliable evidence use, uncertainty, contradiction handling, and knowing when not to answer.

## MESC Data Engine

Training examples should preserve, where applicable:

- example_id
- source_id
- source_revision
- source_license
- source_hash
- evidence_spans
- task_type
- difficulty
- specialty
- population
- language
- answer
- abstention_status
- uncertainty_class
- verification_status
- clinician_review_status
- contamination_status

Intentionally include:
- sufficient evidence
- insufficient evidence
- contradictory evidence
- outdated evidence
- irrelevant evidence
- missing context
- ambiguous patient state
- unsafe requests
- emergencies
- contraindications

## Evaluation Strategy

Do not optimize only for exam QA.

MESC-Eval should include:
- knowledge
- clinical reasoning
- evidence fidelity
- citation entailment
- uncertainty calibration
- abstention accuracy
- contradiction robustness
- safety
- emergency escalation
- hallucination resistance
- longitudinal reasoning
- tool / FHIR correctness
- patient communication
- researcher assistance
- OOD robustness
- worst-case reliability

External benchmark families to track:
- HealthBench
- MedHELM
- Medmarks
- standard medical QA benchmarks

Evaluation sets must be quarantined, hashed, and excluded from training where required.

## Hugging Face Strategy

Release model family, not one opaque checkpoint.

Planned public surfaces:
- MESC-Compact
- MESC-Reasoner
- MESC-AMGE
- MESC-Omni

Each serious release should ship with:
- model weights
- training recipe
- dataset manifest
- source/license provenance
- exact hashes
- decontamination report
- evaluation harness
- raw evaluation outputs where safe
- calibration report
- safety/model card
- Colab
- serving recipe
- fine-tuning recipe
- MESC-Eval
- reproducibility commands
- paper / technical report

Adoption strategy:
- Compact model for easy Colab / consumer-GPU use
- Flagship Reasoner for maximum research quality
- quantized derivatives only after canonical full-precision validation
- avoid a model so large that almost nobody can run it

## Hard Strategic Boundaries

- Preserve current Pilot-01 scientific provenance.
- Do not rewrite or rerun the accepted Llama B0 baseline because newer models exist.
- Do not train on held-out benchmark/test content.
- Do not fabricate provenance.
- Do not merge incompatible model-family weights arbitrarily.
- Do not silently add non-commercial or no-derivatives dependencies.
- Do not treat medical exam QA performance as sufficient clinical validation.
- Do not collapse speech and physiologic audio into one modality.
- Do not start AMGE or audio implementation before their own explicit gates.
- Maintain the existing project restriction excluding Chinese model families from the core model stack unless the founder explicitly revises that policy.

## Near-Term Execution Order

1. Preserve the completed, accepted Pilot-01 Llama-3.2-3B B0 baseline and its exact provenance.
2. Preserve the derived 150-record validation-only input identity.
3. Treat the historical remote-readiness gate as satisfied; do not reacquire or rerun B0 under this strategy PR.
4. Keep B1 execution and P01-06 blocked unless separately authorized.
5. Reconcile any remaining Pilot-01 closeout decisions under their own governance before declaring Pilot-01 complete.
6. Only after Pilot-01 closeout and separate authorization, open the MESC Backbone Tournament.
7. Select Compact + Flagship.
8. Build MESC 1.0.
9. Extend to MESC 1.1 Arabic.
10. Build MESC 2.0 AMGE.
11. Build MESC 3.0 Medical Omni.

## Current Pilot-01 Proven Validation Input

Preparation root:
C:\MESCExecutionEvidence\P01-05-B0-validation-input-prep-1

Artifact:
C:\MESCExecutionEvidence\P01-05-B0-validation-input-prep-1\b0-validation-input.jsonl

Byte size:
262968

SHA-256:
0cb55ad4de0eb831e2475030e889ad9a6f0701ea59adbdd6a30cc0d0115be8d3

Membership:
- train = 0
- validation = 150
- test = 0

Adopted B0 loader validation:
PASS

## Current Execution Boundary

B0 remote readiness: SATISFIED / HISTORICAL GATE

B0 real zero-shot validation execution: COMPLETE / ACCEPTED CANONICALLY

Canonical acceptance merge:
`3f34b35daf4050d010a5f0061d6e8387f9649c10`

Exact Pilot-01 model:
meta-llama/Llama-3.2-3B-Instruct

Exact revision:
0cb88a4f764b7a12671c53f0838cd831a0843b95

B1 execution: NOT AUTHORIZED

P01-06+: NOT AUTHORIZED

This strategy document grants no execution authority. Any next Pilot-01 action, backbone-tournament action, training, retrieval activation, or model-family change requires its own explicit authorization and applicable evidence gates.
