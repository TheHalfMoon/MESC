# FD-P01-06-COLAB-1 — Bounded Google Colab Feasibility Authorization

This is the controlling document for the P01-06 Colab feasibility authorization package.
On any conflict with older Pilot-01 prose about P01-06 authorization status, this decision
controls after canonical merge. Historical records remain historical evidence and are not
erased.

## 1. Decision identity

```text
FOUNDER_DECISION = FD-P01-06-COLAB-1
DECISION_CLASS = EXECUTION AUTHORIZATION — P01-06 FEASIBILITY SMOKE ONLY
ISSUE = #360
AUTHORIZATION_BECOMES_ACTIVE = ONLY_AFTER_CANONICAL_MERGE_OF_THIS_PACKAGE
```

## 2. Bound pre-authorization state

```text
BASE_CANONICAL_MAIN = 03ebeeb8f3fc01ff4456232939482628df9e02f6
BASE_CANONICAL_TREE = 6643624357fcb8ed4d0529f908287539c73e0b42
POST_PR_358_CI = SUCCESS
OPEN_PULL_REQUESTS_AT_AUTHORIZATION_ENTRY = 0
OPEN_ISSUES_BEFORE_ISSUE_360 = 0
```

The repository already records:

- B0 implementation and one historical accepted B0 validation execution;
- B1 implementation adopted and qualified with synthetic fixtures;
- Google Colab as an established project runner surface;
- a founder-frozen Pilot-01 primary target and low-memory fallback;
- P01-07 and all QLoRA/training execution as separately gated.

## 3. Authorized phase

This decision authorizes **P01-06 — Colab feasibility smoke run** only.

```text
P01-06 = AUTHORIZED_ON_CANONICAL_MERGE
P01-06_EXECUTED = FALSE
P01-06_COMPLETED = FALSE
P01-07 = NOT_AUTHORIZED
QLORA_TRAINING = NOT_AUTHORIZED
UNSLOTH_TRAINING = NOT_AUTHORIZED
ADAPTER_CREATION = NOT_AUTHORIZED
PUBLICATION = NOT_AUTHORIZED
```

Authorization is prospective. This document does not claim that a Colab session, GPU,
model acquisition, model load, smoke generation, memory measurement, or feasibility result
has already occurred.

## 4. Exact model identities

Primary feasibility target:

```text
MODEL_ID = meta-llama/Llama-3.2-3B-Instruct
MODEL_REVISION = 0cb88a4f764b7a12671c53f0838cd831a0843b95
ROLE = PRIMARY_PILOT_TARGET
```

Conditional low-memory fallback:

```text
MODEL_ID = meta-llama/Llama-3.2-1B-Instruct
MODEL_REVISION = 9213176726f574b556790deb65791e0c5aa438b6
ROLE = LOW_MEMORY_FALLBACK
```

No other model or revision is authorized by this decision.

## 5. Environment boundary

Authorized runtime class:

```text
GOOGLE_COLAB_HOSTED_GPU_RUNTIME
```

The exact GPU model is **not** predetermined. The execution record must observe and record
the GPU actually allocated by Colab. A claimed GPU identity that was not observed in the
live session is invalid evidence.

The runtime must use ephemeral Colab storage. Google Drive mounting is not required for the
feasibility gate and must not be used as a substitute for canonical evidence capture.

## 6. Hugging Face access boundary

The primary and fallback Llama repositories are gated. This decision authorizes model
acquisition only if the executing Hugging Face account already has legitimate access to the
exact repository and revision.

This decision does **not**:

- accept Meta/Llama license terms on behalf of the Founder;
- create or expose a Hugging Face token;
- bypass a gated-access denial;
- authorize another model because access is unavailable.

Missing gated access is a fail-closed blocker.

## 7. Permitted smoke operations

P01-06 may perform only the minimum operations required to determine Colab feasibility:

1. attest Python, PyTorch/CUDA, GPU model/count, and memory capacity;
2. bind the exact canonical repository commit used for the run;
3. install the locked repository environment plus the existing Transformers backend;
4. authenticate to Hugging Face without printing credentials;
5. resolve and acquire the exact authorized model revision;
6. validate local snapshot identity/provenance;
7. instantiate tokenizer/model with `trust_remote_code=False`;
8. perform a bounded non-scientific synthetic smoke sufficient to prove model load and
   generation-path viability;
9. record peak/allocated/reserved GPU memory and relevant host/runtime facts;
10. unload the model and stop.

P01-06 is a feasibility measurement, not a benchmark result.

## 8. Conditional fallback rule

The 1B fallback is authorized **only** when the primary 3B path fails for demonstrated
memory/resource feasibility reasons in the live Colab runtime.

Before fallback use, the evidence record must contain:

- actual Colab GPU identity;
- the primary model/revision attempted;
- the exact failure class;
- observed memory facts available before/at failure;
- explicit `PRIMARY_FEASIBILITY = FAIL_MEMORY` or equivalent fail-closed disposition;
- `FALLBACK_REASON = PRIMARY_MEMORY_LIMIT`.

A connection interruption, missing Hugging Face access, dependency failure, wrong revision,
or unrelated runtime error does **not** authorize fallback substitution.

## 9. Required output

A successful or blocked execution must produce a metadata-only feasibility record that
contains, at minimum:

```text
schema_version
repository_sha
repository_tree
colab_runtime_class
python_version
torch_version
cuda_version
gpu_model
gpu_count
gpu_total_memory_bytes
primary_model_id
primary_model_revision
primary_snapshot_identity
primary_load_disposition
primary_peak_memory_bytes
synthetic_smoke_disposition
fallback_used
fallback_model_id
fallback_model_revision
fallback_reason
fallback_peak_memory_bytes
final_disposition
stop_reason
```

Raw model weights, Hugging Face credentials, scientific dataset content, prompts derived
from benchmark examples, and generated benchmark outputs must not be committed.

## 10. Explicit prohibitions

P01-06 must not:

- run Pilot-01 benchmark evaluation or claim scientific metrics;
- inspect test-partition scientific content;
- perform B1 evidence-cue scientific execution;
- create a LoRA/QLoRA adapter;
- train or fine-tune;
- install or use Unsloth for training;
- use retrieval or RAG;
- publish weights, adapters, model artifacts, or scientific claims;
- change the frozen model identity because of convenience;
- treat a Colab disconnect as a successful feasibility result;
- fabricate GPU, model-access, memory, or snapshot evidence.

## 11. Unsloth boundary

Unsloth is a candidate implementation accelerator for **P01-07 — First QLoRA run**, not
for P01-06. P01-06 intentionally exercises the existing repository Transformers baseline so
its feasibility result is not confounded by a new training stack.

No dependency addition or Unsloth execution is authorized by this decision.

## 12. Completion and successor rule

Canonical merge of this package changes only the authorization state:

```text
P01-06 = AUTHORIZED
```

It does not change P01-06 to `COMPLETED`.

P01-06 closes only after genuine Colab execution evidence is produced, independently
reviewed, qualified, and adopted on canonical main. Only after that closeout may the
repository determine P01-07 eligibility and separately decide whether an Unsloth-based
Colab QLoRA path is appropriate.

Until then:

```text
P01-07 = NOT_AUTHORIZED
QLORA = NOT_AUTHORIZED
TRAINING = NOT_AUTHORIZED
```
