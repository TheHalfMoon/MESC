# ADR-0036 — Adopt a performance-first MESC health-model strategy

- **Status:** Accepted by Founder for strategy; effective only if this exact package is canonically merged
- **Date:** 2026-09-05
- **Deciders:** Founder
- **Supersedes:** the future-facing model-family and release-naming portions of `docs/strategy/mesc_strategic_model_roadmap_2026-08-18.md`
- **Superseded by:** None
- **Related:** ADR-0033, ADR-0035, `docs/strategy/mesc_health_model_program_2026-09-05.md`, `specs/mesc-research-loop-v1/`

## Context

MESC is intended to become the strongest health-focused open-weight research model that the
project can build and validate, not merely the smallest model that can be fine-tuned on a
single low-cost GPU. Model size is therefore a secondary optimization objective. Medical
quality, multimodal competence, evidence fidelity, calibration, reproducibility, and
scientific validity dominate compression and convenience.

Earlier strategy drafts preserved a historical Llama Pilot-01 control, proposed a compact
plus flagship split, reserved separate public names such as MESC-Compact and MESC-Omni,
and prohibited Chinese model families from the core model stack. Those decisions no longer
match the Founder-directed product/research goal recorded on 2026-09-05.

This ADR changes strategy only. It does not create model/data/runtime/training authority and
cannot satisfy MRL-0801 through MRL-0808 by itself.

## Decision

### 1. The public model identity is `MESC`

The public model name is exactly:

```text
MESC
```

Size, generation, modality coverage, checkpoint lineage, quantization, training stage, and
release channel belong in manifests, model-card metadata, repository tags, immutable
revision records, and release notes rather than in the public model name.

Examples of metadata that may exist without changing the public model name:

```text
model_name = MESC
generation = 1
foundation_candidate = Qwen/Qwen3.8-27B
parameter_class = 27B
modalities = text,image,video
```

This decision does not waive upstream attribution, NOTICE, license, trademark, or derivative
obligations. Any selected foundation must permit the intended naming and distribution model
before its weights or outputs are admitted to MESC training.

### 2. MESC is performance-first, not size-first

Optimization order is:

1. medical and biomedical correctness;
2. clinical reasoning quality under the non-clinical/research-use boundary;
3. evidence fidelity and source traceability;
4. harmful-overconfidence control, uncertainty calibration, and abstention;
5. medical multimodal grounding;
6. FHIR/EHR structured reasoning and deterministic validity;
7. Arabic and English medical competence;
8. reproducibility, contamination control, and provenance;
9. runtime efficiency and deployment cost;
10. model size and compression.

A smaller model must not replace a larger model merely because it is cheaper or easier to
run. Compression becomes eligible only after a stronger candidate establishes the quality
ceiling and the compressed candidate passes frozen non-regression gates.

### 3. Preserve the historical Llama Pilot-01 result only as scientific history/control

The accepted Llama-3.2-3B-Instruct Pilot-01 B0 result remains immutable historical evidence
and a useful general-model control. It is not the MESC flagship foundation and does not
constrain the future MESC public name.

No historical Pilot-01 evidence is rewritten, rerun, or reinterpreted by this ADR.

### 4. Remove the blanket model-family nationality exclusion

The prior strategy rule excluding Chinese model families from the MESC core stack is
replaced by an evidence-based admission rule.

A model family may be considered regardless of country of origin only if all applicable
requirements pass, including:

- exact model and immutable revision identity;
- license, naming, redistribution, derivative, and commercial-use compatibility;
- provenance and training-data disclosure assessment proportional to intended use;
- security and remote-code review;
- reproducible inference and training-tool compatibility;
- contamination and benchmark-leakage controls;
- medical safety and capability evaluation;
- current MRL/training governance.

This policy revision authorizes candidacy review only. It does not authorize downloading,
loading, executing, training, distilling, or distributing any model.

### 5. Preferred foundation candidate: Qwen3.8-27B, subject to qualification

As of 2026-09-05, the preferred foundation candidate is:

```text
Qwen/Qwen3.8-27B
```

Rationale:

- current official release is a 27B native vision-language dense model;
- image and video understanding are native rather than externally bolted on;
- official model card reports strong general/scientific reasoning and visual reasoning;
- native context length is 262,144 tokens;
- the model is published under Apache-2.0;
- the official Qwen project explicitly lists Unsloth among supported fine-tuning frameworks.

Primary source references:

- https://huggingface.co/Qwen/Qwen3.8-27B
- https://github.com/QwenLM/Qwen3.8

`Qwen/Qwen3.8-27B` is a preferred **candidate**, not a promoted or authorized MESC
checkpoint. Before real use, MRL-0801 must bind the exact model/processor/tokenizer/weights
revision and applicable license evidence, and all dependent gates must pass.

The much larger `Qwen/Qwen3.8-2.4T-A95B` is not the default foundation candidate because it
uses a different `qwen3.8-max` license and has materially different operational costs and
capabilities. It may be evaluated as a reference only after its separate legal and runtime
qualification.

### 6. Use a teacher council rather than a single teacher

Teacher roles are separated by demonstrated strength and rights compatibility.

Current preferred candidates are:

| Role | Candidate | Default disposition |
|---|---|---|
| Health / general reasoning teacher | `openai/gpt-oss-120b` | Preferred candidate after exact license/output-use/runtime qualification |
| Audio / omni teacher | `Qwen/Qwen3-Omni-30B-A3B-Instruct` | Preferred candidate after exact multimodal and output-use qualification |
| Medical vision teacher | `lingshu-medical-mllm/Lingshu-32B` | Candidate only after provenance and derivative-chain audit |
| Medical specialist benchmark | MedGemma 1.5 4B and applicable MedGemma variants | Benchmark/reference by default, not a distillation source |
| Independent multimodal control | `microsoft/Phi-4-multimodal-instruct` | Control / verifier candidate |
| General multimodal control | applicable Gemma 4 checkpoints | Control / benchmark candidate |

Primary references:

- https://developers.openai.com/api/docs/models/gpt-oss-120b
- https://deploymentsafety.openai.com/gpt-oss/a2
- https://huggingface.co/Qwen/Qwen3-Omni-30B-A3B-Instruct
- https://huggingface.co/lingshu-medical-mllm/Lingshu-32B
- https://developers.google.com/health-ai-developer-foundations/medgemma/model-card
- https://ai.google.dev/gemma/docs/core/model_card_4

Teacher use is not automatic. Each teacher must have a source-specific admission record
covering model revision, license, output-use/derivative implications, prompt/source
provenance, evaluation contamination, and allowed training role.

### 7. MedGemma remains a critical benchmark but is not a default distillation teacher

MedGemma is medically specialized and must remain in the evaluation suite. However,
Health AI Developer Foundations terms define model derivatives broadly enough that teacher
output distillation requires separate legal/provenance analysis.

Therefore, unless a later accepted decision explicitly qualifies a specific use:

```text
MEDGEMMA_BENCHMARK = ALLOWED_WHEN_EVALUATION_RIGHTS_PASS
MEDGEMMA_REFERENCE = ALLOWED_WHEN_EVALUATION_RIGHTS_PASS
MEDGEMMA_DISTILLATION_SOURCE = NOT_AUTHORIZED_BY_DEFAULT
```

This preserves a clean MESC training lineage while retaining a strong medical comparator.

### 8. Distillation means capability transfer first, compression second

The MESC program must not define distillation primarily as "large model to tiny model".
The preferred sequence is:

1. rights-clean ground-truth domain SFT;
2. verifier-backed medical/FHIR instruction tuning;
3. sequence-level teacher supervision on difficult examples;
4. probability/logit distillation where architectures and rights make it valid;
5. on-policy generalized knowledge distillation so teachers correct actual MESC failure
   modes rather than only generating ideal demonstrations;
6. medical-vision representation/grounding distillation where validated;
7. filtered audio pseudo-label/representation transfer where validated;
8. preference/RL stages driven by verifiable rewards and frozen medical safety gates;
9. compression/distillation to smaller checkpoints only after the flagship quality ceiling
   is established.

Teacher-generated content never outranks trusted ground truth. Unknown or unsupported
medical claims must be rejected rather than laundered into training data.

### 9. Multimodal roadmap is unified under one MESC identity

MESC capability growth remains staged, but the public identity does not fragment.

- Generation 1: text, evidence reasoning, FHIR/EHR, native image/video capability from the
  selected foundation where present.
- Generation 2: deep medical vision specialization across radiology, pathology,
  ophthalmology, dermatology, ultrasound, longitudinal and multi-image reasoning.
- Generation 3: clinical speech plus physiologic audio. Speech and physiologic acoustics
  remain separate training/evaluation domains.

Audio integration may use a separately qualified encoder/projector/codec or a future
foundation migration. The project must not choose a weaker base solely because it already
contains audio.

### 10. Colab is the development surface; rented accelerator bursts are allowed later

The Founder does not have a suitable local GPU and MESC must not require one.

Google Colab remains the default low-cost development and qualification environment for:

- pipeline development;
- small and medium LoRA/QLoRA experiments;
- data transformation and validation;
- evaluation harness work;
- ablations and reproducibility checks.

The flagship quality objective may require separately authorized rented A100/H100/B200 or
comparable accelerator capacity for large-model inference, teacher generation, multimodal
training, long-context runs, and verifier/RL stages.

No cloud provider, credential, GPU allocation, runtime, or training run is authorized by
this ADR.

### 11. MESC can be called "best" only after independent evidence

The program goal may be "best health model", but repository claims must remain evidence
bounded.

A future `MESC_BEST_HEALTH_MODEL` claim requires an independently reviewed, frozen,
pre-registered evaluation package covering at minimum:

- realistic health conversations;
- medical knowledge and reasoning;
- evidence entailment and citation fidelity;
- hallucination and unsupported-claim rate;
- uncertainty calibration and abstention;
- safety and emergency escalation;
- FHIR correctness and structured-output validity;
- longitudinal EHR reasoning;
- medical image grounding and multi-image reasoning;
- English and Arabic medical language;
- clinical speech where applicable;
- physiologic audio where applicable;
- critical subgroups and OOD robustness;
- reproducibility and contamination evidence.

The model must be compared against contemporaneous strong public/open and applicable
proprietary references where evaluation terms allow it. A single benchmark such as MedQA
or HealthBench is insufficient to establish the claim.

## Consequences

**Positive**

- model quality rather than parameter minimization becomes the controlling objective;
- the public identity remains simple and stable: `MESC`;
- future models are selected by evidence rather than geography or historical inertia;
- audio and medical vision can be specialized without weakening the reasoning foundation;
- multiple teachers can contribute only where their rights and competence are qualified;
- future agents have one explicit strategy source instead of reconstructing the plan from
  chat history.

**Costs / constraints**

- a genuinely best-in-class MESC may require rented accelerator compute;
- multiple teacher/evaluator pipelines create more provenance and contamination work;
- Qwen3.8-27B does not natively cover the final physiologic-audio objective;
- the preferred candidate can still lose the frozen backbone qualification and be
  replaced;
- medical benchmark leadership cannot be claimed before independent evidence exists.

## Authorization boundary

This ADR is strategy and candidacy governance only. It does **not** authorize:

- model or dataset acquisition;
- gated-term acceptance;
- teacher-output generation;
- network/provider/credential activation;
- GPU allocation;
- real inference;
- fine-tuning, continued pretraining, distillation, preference optimization, RL, or
  adapter creation;
- trust-registry mutation;
- MRL-0801..MRL-0809 or MRL-0899 closure;
- model promotion, release, clinical deployment, or production use.

All such work remains subject to the canonical MRL task order, real-preflight evidence,
current training governance, exact-head qualification, independent review, and the
promotion-ownership boundary preserved by ADR-0033.