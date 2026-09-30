# MRL-0809 Successor (v2) — Smaller-Roster Runtime-Feasibility Contract

- **Status:** successor contract implementation. No Stage-4 attempt has run. MRL-0809 stays `PLANNED`.
- **Authority:** [Founder decision FD-MRL-0809-SUCCESSOR-V2-1](founder-decision.md), which resolves Issue #450 (option 3) and is recorded machine-readably in [`../mrl-0809-successor-v2-authorization.json`](../mrl-0809-successor-v2-authorization.json).
- **Controlling task:** MRL-0809 in [`specs/mesc-research-loop-v1/tasks.md`](../../mesc-research-loop-v1/tasks.md) (Issue #429).
- **Runbook:** [`docs/execution/mrl_0809_runtime_feasibility_runbook_v2.md`](../../../docs/execution/mrl_0809_runtime_feasibility_runbook_v2.md).

```text
MRL-0809 v1 runtime feasibility = INFEASIBLE_ON_FROZEN_STANDARD_T4_CONTRACT (preserved)
MRL-0809 v2 runtime-feasibility slot = ABSENT
MRL-0809 = PLANNED
MRL-0899 = BLOCKED behind MRL-0809
SCIENTIFIC_RQ1_EXECUTION = NOT_YET_AUTHORIZED
```

This package makes the successor contract implementable and verifiable. It runs no model, downloads no weights into the repository, and grants no model, training, promotion, publication, PHI or paid-compute authority. Successor candidates exist for RQ1 executable research, runtime feasibility and grammar/FHIR evaluation only. They are **not** a flagship, training or deployment selection. ADR-0036 and its preferred foundation candidate `Qwen/Qwen3.8-27B` are unchanged.

## 1. Why v1 cannot close MRL-0809

The v1 contract froze these conditions:
- `Qwen/Qwen3.8-27B` and `google/gemma-4-31B-it`;
- `bitsandbytes-nf4-v1`, all weights on CUDA device 0;
- one Colab STANDARD Tesla T4 (14.56 GiB usable);
- zero cost, no offload, no fallback.

The second Founder-authorized Stage-4 attempt at `4da5b4cc` failed. The Qwen probe hit CUDA OOM at about 59% of 1184 loading units, with about 14.23 GiB allocated, and Gemma was never staged or probed (Issue #429 comments 5747163063 and 5747325008).

[`../mrl-0809-v1-infeasibility-record.json`](../mrl-0809-v1-infeasibility-record.json) preserves that result. It binds:
- both comments by body digest;
- the attempt commit and tree;
- the launch packet and the preserved log digests;
- the byte digests of every v1 contract file at the successor base.

`pass_claimed`, `gemma_tested` and `retry_authorized` are all `false`.

## 2. Impact map (what is versioned, what is preserved)

| Surface | v1 (preserved byte-identical) | v2 (new successor identity) |
|---|---|---|
| Candidate roster | `candidate-roster-v1.json` | `candidate-roster-v2.json` |
| Candidate/runtime contract validator | `_mrl_0809_runtime_feasibility_v1.py` | `_mrl_0809_runtime_feasibility_v2.py` |
| Runtime-feasibility worker / observation / receipt / independent verifier | `scripts/mesc_mrl_0809_runtime_feasibility.py` (schemas V1) | `scripts/mesc_mrl_0809_runtime_feasibility_v2.py` (schemas V2) |
| Static prerequisite manifest | `mrl-0809-static-prerequisites-v1.json` | `mrl-0809-static-prerequisites-v2.json` |
| Trust root | `mrl-0809-runtime-feasibility-trust-v1.json` (empty) | `mrl-0809-runtime-feasibility-trust-v2.json` (empty) |
| Evidence slot | `mrl-0809-runtime-feasibility-slot-v1.json` (ABSENT) | `mrl-0809-runtime-feasibility-slot-v2.json` (ABSENT) |
| Prerequisite gate | `_mrl_0809_prerequisite_gate_v1.py` | `_mrl_0809_successor_gate_v2.py` |
| Machine-state binding | `_mrl_machine_state_generation_closeout_v1.py` (v1 gate) | composed in `_mrl_machine_state_generation_v1.py`: v1 gate first, successor only if v1 is not satisfied |
| MRL-0806 candidate-bound authorization | `mrl-0806-objective-budgets-authorization-v1.json` | `mrl-0806-objective-budgets-authorization-v2.json` |
| RQ1 protocol | `mrl-0806-rq1-protocol-v1.json` | `mrl-0806-rq1-protocol-v2.json` |
| Runbook | `docs/execution/mrl_0809_runtime_feasibility_runbook.md` | `docs/execution/mrl_0809_runtime_feasibility_runbook_v2.md` |
| Closeout evidence | — | future, after a verified successor PASS |

**Unchanged and not versioned:**
- the runtime class (Colab STANDARD T4) and the MRL-0804 runtime identity;
- the MRL-0808 sandbox policy and bubblewrap/seccomp isolation;
- the dependency lock (`uv.lock` and `pyproject.toml`, byte-identical) and the pinned runtime packages;
- the `bitsandbytes-nf4-v1` representation (NF4, double quantization, float16 compute, all on CUDA device 0);
- the synthetic prompt text and the 12-token generation bound;
- ADR-0001 and the frozen RQ1 grammar.

The successor gate refuses to pass unless the v1 static prerequisites still validate and every v1 file listed in the infeasibility record is byte-identical. That includes the ABSENT v1 slot and the empty v1 trust root. A trusted successor PASS therefore cannot coexist with a rewritten v1 result.

## 3. Candidate selection

### 3.1 Evidence collected (public metadata only, no weights)

The shortlist was collected from the public Hugging Face Hub API on 2026-09-30. For each candidate:
- **Tensor counts:** exact per-tensor parameter counts, read from SafeTensors headers by HTTP range requests (header bytes only).
- **Weight identity:** file digests from the Hub LFS metadata.
- **Small metadata files:** `config.json`, the tokenizer and processor files and the chat template were downloaded. Tokenizer, processor and chat-template loading was checked locally on CPU with the exact pinned `transformers==5.16.1`, `torch==2.13.0`, `torchvision==0.28.0` and `pillow==12.3.0`, with `trust_remote_code=False`.

No model weights were downloaded and no model was executed.

**Footprint model.** Embeddings, an untied `lm_head`, per-layer embeddings and vision/audio towers stay fp16 (2 bytes/param). Language-model tensors are NF4 with double quantization and quantization state (0.535 bytes/param). The model is calibrated against the v1 failure. It estimates `Qwen/Qwen3.8-27B` at 17.94 GiB and `google/gemma-4-31B-it` at 18.29 GiB, both far above the 14.56 GiB usable. That is consistent with the observed OOM of Qwen at about 59% loaded. These figures are estimates only; Stage-4 measures the real peak.

### 3.2 Shortlist and dispositions

| Candidate | Params | Est. NF4 weights | Disposition | Reason |
|---|---|---|---|---|
| `google/gemma-4-12B-it` | 11.96 B | 7.40 GiB | **SELECTED** | Apache-2.0, ungated, no remote code. Smaller sibling of the v1 Gemma family. Canonical single SafeTensors file. Processor and chat template load under the pinned stack |
| `Qwen/Qwen3-8B` | 8.19 B | 5.78 GiB | **SELECTED** | Apache-2.0, ungated, no remote code. Qwen family (the v1 flagship family). Canonical 5-shard layout. Text-only, tokenizer policy |
| `Qwen/Qwen3.5-9B` | 9.65 B | 8.21 GiB | REJECTED | Shards are named `model.safetensors-0000N-of-00004.safetensors`, which the canonical `MESC-HF-SAFETENSORS-WEIGHT-IDENTITY-V1` contract rejects. It is also above the 8 GiB preference |
| `google/gemma-4-E4B-it` | 8.00 B | 9.40 GiB | REJECTED | 2.82 B per-layer-embedding parameters stay fp16, above the 8 GiB preference |
| `mistralai/Ministral-3-8B-Instruct-2512` | 8.92 B | — | REJECTED | The repository ships both `consolidated.safetensors` and a sharded set, an ambiguous weight layout under the canonical identity contract |
| `Intelligent-Internet/II-Medical-8B` | 8.19 B | 5.78 GiB | REJECTED | Derivative fine-tune of Qwen3-8B (same family as a selected candidate) with undisclosed training-data overlap with medical evaluation sets, a contamination risk |
| `allenai/Olmo-3-7B-Instruct` | 7.30 B | 4.76 GiB | ELIGIBLE ALTERNATE | Fully open training data (useful for contamination auditing); outside the v1 roster families |
| `ibm-granite/granite-4.2-8b` | 8.79 B | 5.50 GiB | ELIGIBLE ALTERNATE | Apache-2.0, ungated; outside the v1 roster families |

**Excluded without shortlisting:**
- gated repositories, such as Gemma 3, MedGemma and Llama (credential policy);
- models above 12 B total parameters;
- repositories that need remote code.

### 3.3 How the selection criteria were applied

- **Medical/biomedical reasoning potential.** No candidate has repository-verified medical evidence. The pair was chosen as the newest general instruction models of the two v1 families that satisfy every hard rule. This is a prior, not a result, and RQ1 will measure it.
- **Structured/FHIR and grammar compatibility.** Both load their tokenizers under the pinned stack, and XGrammar builds tokenizer information from Hugging Face tokenizers. The RQ1 adapter design is unchanged.
- **Reproducibility and licensing.** Both are Apache-2.0, ungated, with exact 40-hex revisions and content-addressed weight identities.
- **Runtime feasibility.** Estimated weights of 7.40 and 5.78 GiB leave about 7 and 8.8 GiB below the 14.56 GiB usable. A receipt is rejected if either candidate peaks above 12 GiB.
- **Family diversity.** The two are from different families (Gemma, Qwen), and each mirrors a v1 family at a T4-feasible size.

### 3.4 Differences the new roster forces (declared, not hidden)

- **Processor policy:** it is now per candidate. `google/gemma-4-12B-it` loads `AutoProcessor` (`AUTO_PROCESSOR_EXACT_REVISION`). `Qwen/Qwen3-8B` is text-only and has no processor file (`TOKENIZER_ONLY_TEXT_MODEL`).
- **Prompt construction:** the prompt text is unchanged, but it is built with each model's own chat template (`CHAT_TEMPLATE_ADD_GENERATION_PROMPT`). Each candidate's exact prompt-token digest is frozen. A raw tokenizer call would give Gemma no BOS token, which makes a feasibility generation unrepresentative.
- **Evidence and receipt checks:**
  - `all_generated_logits_finite` must be `true`, so a generation with NaN or Inf logits can never pass as "generation succeeded";
  - `offload_performed` is an explicit receipt field;
  - `all_modules_on_cuda_device_0` is an explicit candidate field;
  - peak GPU memory is capped at 12 GiB.
- **Attempt evidence:** `probe` writes a `.probe-start.json` marker before the isolated worker launches. It proves whether a candidate load began, which the attempt-consumption rule needs.

## 4. MRL-0806 successor rebinding

[`../mrl-0806-objective-budgets-authorization-v2.json`](../mrl-0806-objective-budgets-authorization-v2.json) binds the preserved v1 authorization and the successor authorization.

**Carried forward byte-for-byte:**
- the research objective, evaluation contract, evaluator identity and sealed Tier-3 identity;
- the policy block, the research question and the RQ1 candidate/experiment identities;
- the MRL-0802, MRL-0803, MRL-0804 and MRL-0807 predecessor evidence.

[`../mrl-0806-rq1-protocol-v2.json`](../mrl-0806-rq1-protocol-v2.json) is the v1 protocol with only the candidate binding changed:
- `candidate_roster_sha256`;
- `candidates`;
- the roster-bound `preflight_evidence_sha256` entries.

The protocol therefore keeps unchanged:
- seeds 17, 29 and 43, and greedy decoding;
- 384 generation calls and the token ceilings;
- the constraint and prompting conditions, and the tier configuration counts;
- the statistical analysis, result-exposure and sealed-confirmation policies;
- the corpus and Tier-3 digests.

The MRL-0801 (model/weights custody) and MRL-0805 (no-training authority) evidence is roster-bound to v1. Both are recorded as `null`, with `pending_successor_evidence_before_mrl_0899 = ["MRL-0801", "MRL-0805"]`. They must be produced for the successor roster before any MRL-0899 decision. This unit does not claim them.

## 5. Attempt consumption

The Founder authorized exactly one successor Stage-4 attempt. It may run only after this contract is merged under Founder exact-head approval and fresh-main qualified.

**Attempt consumed:** once any candidate's `.probe-start.json` marker exists, any genuine runtime, model or probe failure consumes the attempt. That includes OOM, non-finite logits, exceeding the headroom ceiling, a prompt-token mismatch, offload detection and cleanup failure. The result is `SUCCESSOR_STAGE4 = FAIL`: the evidence is recorded and the attempt stops. There is no substitution, offload, quantization change or retry without a new governed decision.

**Not consumed:** only a provider/session failure with no probe-start marker for any candidate may be classified `INFRASTRUCTURE_NON_EXECUTION`. This distinction must not be used to obtain unlimited retries.

## 6. Non-grants

```text
SCIENTIFIC_RQ1_EXECUTION = NOT_YET_AUTHORIZED
SCIENTIFIC_CORPUS_ACCESS (feasibility) = FALSE
SEALED_TIER3_ACCESS = FALSE
TRAINING = FALSE
WEIGHT_MUTATION = FALSE
LORA / QLORA / DISTILLATION / RL = NOT_AUTHORIZED
MODEL_PROMOTION = FALSE
CPU_OFFLOAD / DISK_OFFLOAD / AUTOMATIC_DEVICE_MAP = NOT_AUTHORIZED
HIGHER_MEMORY_GPU = NOT_AUTHORIZED
PAID_COMPUTE = NOT_AUTHORIZED
PHI = NOT_AUTHORIZED
CW_021 = NOT_AUTHORIZED
```
