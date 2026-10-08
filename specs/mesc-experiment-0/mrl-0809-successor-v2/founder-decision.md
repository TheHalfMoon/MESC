# MRL-0809 Successor — Founder Decision Record

- **Decision ID:** `FD-MRL-0809-SUCCESSOR-V2-1`
- **Date:** 2026-09-30
- **Decision holder:** the Founder, as the decision reserved by Issue #450 ("This issue is planning/decision scope only until a separate explicit founder authorization selects a successor runtime/candidate policy")
- **Canonical base when decided:** `6e5d8ecf455d005805cbb9b4e4a84ca35cca5d70` (fresh-main CI 36730753216, CodeQL 36730753487, Optional Extras 36730753433, HF Publication 36730753232, all SUCCESS)
- **Machine-readable form:** [`../mrl-0809-successor-v2-authorization.json`](../mrl-0809-successor-v2-authorization.json)

This file records the Founder's explicit decision on Issue #450 as it was given, so that it is persisted canonically in the repository. It is the decision record, not an implementation or an evidence claim. It becomes canonical only when the pull request that adds it is merged under the Founder's exact-head approval.

## 1. Decision

```text
DECISION = AUTHORIZE A SEPARATELY VERSIONED SMALLER-ROSTER MRL-0809 SUCCESSOR
ISSUE_450_OPTION_3 = SELECTED
CURRENT_V1_EXPERIMENT_INFEASIBLE_EVIDENCE = PRESERVE_IMMUTABLY
```

The frozen MRL-0809 v1 runtime contract is **not** to be retried:

```text
STANDARD T4 + all-on-GPU + bitsandbytes-nf4-v1 + Qwen/Qwen3.8-27B + google/gemma-4-31B-it
```

The existing Qwen out-of-memory result is valid negative feasibility evidence. It must not be rewritten, erased, or converted into PASS. Gemma was never staged or probed, and must not be claimed as tested.

## 2. Strategic model policy is unchanged

ADR-0036 remains effective. `Qwen/Qwen3.8-27B` remains a strategic preferred foundation candidate unless a later evidence-based canonical decision changes that.

The successor roster exists for exactly these purposes:
- RQ1 executable research;
- runtime feasibility;
- grammar/FHIR scientific evaluation.

It is **not** any of the following:
- MESC flagship selection;
- model promotion;
- production, training or deployment selection;
- evidence that smaller models are scientifically superior.

No result from the smaller successor roster may be generalized into a claim that the larger flagship candidate is feasible or inferior.

## 3. Successor roster policy

- A new, separately versioned roster, with `CANDIDATE_COUNT = 2`. `candidate-roster-v1` is not mutated.
- The research implementation may select the two models under ADR-0036, without returning for another Founder model-name decision, **only** if both satisfy every rule below:
  1. open-weight and legally evaluable;
  2. exact immutable revision frozen;
  3. exact model, config and tokenizer identities frozen;
  4. no `trust_remote_code` requirement;
  5. compatible with the existing bounded Transformers + XGrammar RQ1 design, or with a separately reviewed compatible adapter that does not weaken grammar enforcement;
  6. no gated provider credential for the preferred path;
  7. no paid API or inference service;
  8. fits the zero-cost STANDARD Tesla T4 with material safety headroom;
  9. the same governed quantization/representation policy across both candidates, unless the successor contract proves an identical policy impossible;
  10. no CPU offload;
  11. no disk offload;
  12. no automatic device-map fallback;
  13. no remote inference;
  14. no training or weight mutation;
  15. no model promotion authority.
- Dense models: prefer `TOTAL_PARAMETER_CLASS <= 12B`, with evidence that the expected 4-bit footprint leaves substantial headroom below the approximately 14.56 GiB usable T4 capacity.
  - A theoretical 4-bit weight calculation alone is not admission evidence.
  - The estimate must account for quantization metadata, non-quantized modules, allocator fragmentation, loader transient peak, runtime/generation buffers and multimodal components.
  - Prefer an estimated quantized weight footprint of 8 GiB or less.
- If two scientifically defensible candidates cannot satisfy these constraints, **stop for a Founder decision**. The constraints must not be silently relaxed.
- Selection quality: do not choose the absolute smallest models merely to make CI green. Within the T4-feasible pool, choose the strongest defensible pair by these criteria:
  - medical/biomedical reasoning potential;
  - evidence-grounded generation;
  - structured/FHIR compatibility;
  - tokenizer/grammar-engine compatibility;
  - uncertainty/abstention relevance;
  - reproducibility;
  - licensing;
  - runtime feasibility;
  - model-family diversity where useful.
- Document the shortlist and the rejection reasons. Freeze the final roster before Stage-4.

## 4. MRL-0806

The scientific question and methodological intent carry forward unless a mechanical incompatibility is proven. That covers:
- the RQ1 question;
- evaluator semantics;
- the FHIR projection;
- the grammar-vs-unconstrained comparison;
- seeds and decoding policy;
- metric definitions and safety floors;
- contamination controls and the statistical plan;
- result-exposure limits;
- the scientific corpus identity and Tier-3 identities;
- the zero-cost ceiling.

The existing MRL-0806 authorization binds the old roster and must not be reused as though its candidate binding were unchanged. A separately versioned successor authorization must:
- preserve the old artifact immutably;
- identify the new roster and bind its digest;
- state which values carry forward byte-for-byte;
- state every unavoidable changed field;
- prove that candidate substitution does not alter the scientific question.

There must be no silent hash substitution.

## 5. Versioning and MRL-0809 semantics

- **No overwrites:** no v1 trust or evidence artifact is overwritten. Successor identities are created for every artifact whose semantics change.
- **v1 stays infeasible:** MRL-0809 v1 runtime feasibility remains historically `INFEASIBLE_ON_FROZEN_STANDARD_T4_CONTRACT`, and the v1 slot is never marked PASS.
- **How MRL-0809 can close:** only through a documented successor resolution that proves all of the following:
  - the v1 negative evidence is preserved;
  - the successor contract is canonically accepted;
  - a successor runtime-feasibility PASS is independently verified;
  - the successor evidence/trust is admitted;
  - all earlier MRL invariants are preserved.
- **If machine state can't express this:** version the machine-state/prerequisite contract rather than weakening it.

## 6. Runtime, network and credentials

```text
PROVIDER_CLASS = GOOGLE_COLAB_FREE
GPU_CLASS = STANDARD_T4
MONETARY_COST = EXACTLY_ZERO
NETWORK_FOR_ARTIFACT_ACQUISITION = AUTHORIZED_BOUNDED  (before the isolated phase only)
ISOLATED_MODEL_LOAD_NETWORK = FALSE
ISOLATED_GENERATION_NETWORK = FALSE
MODEL_ACQUISITION_CREDENTIALS = NONE (preferred)
```

- **No paid options:** no paid upgrade, Colab Pro purchase, rented A100/H100/B200, paid endpoint or paid inference.
- **T4 availability:** if a T4 is unavailable, no other GPU may be substituted and called equivalent.
- **Network:** during acquisition, the network may only obtain the exact selected revision, tokenizer/processor material, already-authorized runtime dependencies, and source metadata for custody verification.
- **No data leaves:** no scientific corpus access during feasibility, no telemetry, no external inference API, and no MESC prompt or result sent to a remote model service.
- **Credentials:** if a candidate would need gated-model acceptance, a new provider credential or a legal click-through, stop. Terms are never accepted autonomously.

## 7. Stage-4 successor authorization

```text
NEW_SUCCESSOR_STAGE4_ATTEMPT = AUTHORIZED_AFTER_CANONICAL_CONTRACT
MAX_SCIENTIFIC_CANDIDATES = 2
SCIENTIFIC_CORPUS_ACCESS = FALSE
SEALED_TIER3_ACCESS = FALSE
```

**When:** exactly one bounded, zero-cost Stage-4 successor runtime-feasibility attempt is authorized. It may run only after the successor contract has:
- been canonically specified;
- been exact-head qualified;
- been reviewed with Jev and with the Alibaba Open Code Review local lanes;
- passed CI and CodeQL;
- been merged under Founder exact-head approval;
- been fresh-main qualified.

**What it must prove, for both candidates:**
- the exact candidate ID, revision, and tokenizer/processor/config identities;
- the exact successor contract and quantization/runtime representation;
- the exact Colab session, runtime and GPU identity;
- zero monetary cost;
- model, tokenizer and (where applicable) processor load success;
- `trust_remote_code = false`, no offload, no fallback;
- isolated network = false;
- bounded synthetic generation success;
- cleanup;
- no training, no optimizer, no weight mutation, no persistent weight writeback.

**Input:** synthetic only. This is still not the scientific RQ1 experiment.

**Attempt consumption:** if either candidate runs out of memory or otherwise fails genuine runtime feasibility, then:
- `SUCCESSOR_STAGE4 = FAIL`;
- the evidence is recorded and the attempt stops;
- no substitution, no offload, no quantization change, no retry until a new governed decision exists.

A provider/session startup failure may be classified as infrastructure non-execution only if the canonical receipt contract proves that no candidate load began. That distinction must not be used to obtain unlimited retries.

## 8. Explicitly not selected or not authorized

```text
OFFLOAD_SUCCESSOR = NOT_SELECTED
CPU_OFFLOAD = NOT_AUTHORIZED
DISK_OFFLOAD = NOT_AUTHORIZED
AUTOMATIC_DEVICE_MAP = NOT_AUTHORIZED
HIGHER_MEMORY_GPU = NOT_AUTHORIZED
PAID_COMPUTE = NOT_AUTHORIZED
SCIENTIFIC_RQ1_EXECUTION = NOT_YET_AUTHORIZED
TRAINING = FALSE
WEIGHT_MUTATION = FALSE
LORA = NOT_AUTHORIZED
QLORA = NOT_AUTHORIZED
DISTILLATION = NOT_AUTHORIZED
RL = NOT_AUTHORIZED
MODEL_PROMOTION = FALSE
PHI = NOT_AUTHORIZED
CW_021 = NOT_AUTHORIZED
```

When the MRL-0809 successor resolution reaches `CLOSED_CANONICAL`, MRL-0899 is recomputed. If actual scientific execution then needs a new Founder authorization, the exact decision packet is prepared and work stops. RQ1 execution authority is never inferred.

## 9. Historical B0

The historical Llama-3.2-3B-Instruct B0 result stays descriptive historical evidence only. Its missing raw bundle is not fabricated. It is not used as a paper result until the raw artifact is recovered, or until it is explicitly treated as historical, non-reproducible context.
