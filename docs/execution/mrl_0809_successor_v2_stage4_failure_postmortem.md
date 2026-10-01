# MRL-0809 successor (v2) Stage-4 failure postmortem

Status: EVIDENCE_RECORD / NO_RETRY_AUTHORITY

## Purpose

Record the consumed MRL-0809 successor (v2) Stage-4 attempt exactly as observed, distinguish the failure from the historical v1 CUDA OOM, and define the bounded repository-side repair target without authorizing another hosted attempt.

This document does not authorize Stage-4 execution, scientific RQ1 execution, model substitution, revision substitution, quantization changes, offload, a different GPU class, paid compute, training, weight mutation, promotion, release, deployment, or PHI access.

## Canonical contract executed

```text
CANONICAL_MAIN = b59a3d976f94f78f3e97644e9efc5e12f33fa74e
CANONICAL_TREE = 9bd68750675b4e43ec625d08804bbb096f63aeb9
PROVIDER = GOOGLE_COLAB
MACHINE_SHAPE = STANDARD
GPU = Tesla T4
RUNTIME_REPRESENTATION = bitsandbytes-nf4-v1
MONETARY_COST = 0
```

The frozen successor candidates remained:

1. `Qwen/Qwen3-8B` at `b968826d9c46dd6066d109eabc6255188de91218`.
2. `google/gemma-4-12B-it` at `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`.

The runtime package set observed in the governed preflight matched the frozen contract, including `bitsandbytes==0.50.2`, `torch==2.13.0`, `transformers==5.16.1`, and `xgrammar==0.2.7`.

## Local evidence anchors

The retained local evidence was hashed immediately after the hosted session was lost:

```text
mrl0809-v2-stage4-session.ipynb
sha256 = 8e4040a1479795c5138c0a2a87ee27a899238bfdd8ad3a632e751e85cf4cca17

mrl0809-v2-stage4-colab-cli-attempt.log
sha256 = 847a39471cae40f4e5ab1894979ffa76de0f75688277a8a6dea060746a9459e6

MRL-0809-v2-Stage4.ipynb
sha256 = d3d7e7708d6d701fa159b0dbe64442d73e83bdfdf156e842b1e2b340a52a12a5
```

The Colab VM session disappeared before the custody directory could be copied back. Therefore the raw `/content/mrl0809-v2-custody` files, including the on-VM `.probe-start.json` marker and detailed per-cell log files, were not recovered. The exported session history nonetheless contains the decisive execution trace described below.

## Execution facts

### Preflight

The governed preflight completed on a Tesla T4 with 15360 MiB reported VRAM and the exact canonical repository commit. It ended with `PREFLIGHT_OK`.

### Qwen stage

The Qwen frozen payload downloaded and the stage command completed successfully:

```text
QWEN_STAGE = PASS
QWEN_STAGE_RECEIPT_SHA256 = dc3055ef258570d1f7f394e90f0bc16f75663705441739c4f9e6f87b472561b1
```

### Qwen probe

The Qwen probe command entered the canonical v2 `probe_candidate(...)` path, wrote the attempt-start marker before launching the isolated worker by contract, and reached `_run_worker(...)`.

The isolated worker completed the model weight-loading progress to `399/399`. No CUDA OOM was observed in the retained output.

The worker then failed at the placement-audit check:

```text
HarnessError: loaded model did not expose an auditable device map
```

The failing v2 code path was:

```python
model = model_class.from_pretrained(
    str(snapshot),
    local_files_only=True,
    trust_remote_code=False,
    quantization_config=quantization,
    device_map={"": 0},
    torch_dtype=torch.float16,
    low_cpu_mem_usage=True,
)
torch.cuda.synchronize()
device_map = getattr(model, "hf_device_map", None)
if type(device_map) is not dict or not device_map:
    raise HarnessError("loaded model did not expose an auditable device map")
```

Observed classification:

```text
QWEN_STAGE = PASS
QWEN_WEIGHTS_LOAD = COMPLETED_399_OF_399
QWEN_PROBE = FAIL
QWEN_OOM = NOT_OBSERVED
QWEN_CAPACITY_INFEASIBILITY = NOT_ESTABLISHED
QWEN_FAILURE_CLASS = HARNESS_RUNTIME_AUDIT_COMPATIBILITY_FAILURE
QWEN_FAILURE = loaded model did not expose an auditable device map
```

This result must not be relabeled as either a Qwen runtime PASS or a T4 capacity FAIL. The worker loaded the frozen model under the governed loader call and then failed the harness's audit-interface requirement.

### Attempt consumption

The v2 harness writes `<observation>.probe-start.json` immediately before `_run_worker(...)`. The retained traceback proves execution reached `_run_worker(...)`. Therefore the governed attempt-start boundary was crossed even though the marker file itself was lost with the Colab VM.

```text
SUCCESSOR_STAGE4_ATTEMPT = CONSUMED
SUCCESSOR_STAGE4 = FAIL
RETRY = NOT_AUTHORIZED
```

### Gemma

The notebook orchestration continued after the Qwen cell exception instead of fail-stopping the remaining notebook cells. Gemma staging subsequently completed successfully, after which the Gemma probe cell began and was manually interrupted.

```text
GEMMA_STAGE = PASS
GEMMA_PROBE = STARTED_THEN_INTERRUPTED
GEMMA_RESULT = NOT_ESTABLISHED
```

No Gemma PASS or FAIL claim is admitted from this partial execution.

The notebook orchestration behavior is a separate operational finding: future governed notebooks must fail-stop at the first candidate probe failure and must never rely on a multi-cell execution driver that automatically advances after a failed cell.

## Root cause

The direct failure was not model capacity. It was an audit-compatibility assumption in the v2 worker:

- the loader explicitly requested `device_map={"": 0}`;
- the model load completed;
- the harness then required a non-empty `model.hf_device_map` attribute as the only accepted placement-audit source;
- the observed Transformers/model combination did not expose that attribute after load;
- the harness failed closed, as required.

Failing closed was correct. The single-source audit assumption was too narrow.

## Repair objective

A repository repair may strengthen placement auditing without weakening the no-offload/no-fallback contract.

The repaired audit must prove actual materialized model state rather than treating `hf_device_map` presence as mandatory. A compliant design must:

1. preserve the exact loader request `device_map={"": 0}`;
2. inspect `hf_device_map` when present and reject every target other than CUDA device 0;
3. independently inspect every materialized model parameter and buffer and require CUDA device 0;
4. fail closed on CPU, disk, meta, missing-device, mixed-device, or non-auditable materialized tensors;
5. require at least one auditable parameter or buffer so an empty model cannot pass;
6. preserve all existing sandbox, seccomp, offline, `local_files_only`, `trust_remote_code=False`, NF4, prompt-token, generation, finite-logit, 12 GiB peak, and cleanup requirements;
7. emit deterministic placement evidence into the worker observation so an independent verifier can distinguish `hf_device_map` evidence from parameter/buffer evidence;
8. add adversarial tests for: no `hf_device_map` but all tensors on `cuda:0`; CPU parameter; CUDA device 1 parameter; meta parameter; CPU buffer; mixed devices; forged permissive `hf_device_map` conflicting with actual tensor placement; and empty/no-auditable tensors;
9. preserve the historical v1 harness and v1 evidence bytes unchanged;
10. not authorize a new hosted attempt by itself.

## Governance disposition

```text
MRL-0809 = NOT_CLOSED
MRL-0899 = BLOCKED
NEW_STAGE4_ATTEMPT = NOT_AUTHORIZED
OFFLOAD = NOT_AUTHORIZED
QUANTIZATION_CHANGE = NOT_AUTHORIZED
MODEL_SUBSTITUTION = NOT_AUTHORIZED
REVISION_SUBSTITUTION = NOT_AUTHORIZED
GPU_CLASS_SUBSTITUTION = NOT_AUTHORIZED
PAID_COMPUTE = NOT_AUTHORIZED
SCIENTIFIC_RQ1_EXECUTION = NOT_AUTHORIZED
```

A repaired harness must be implemented and qualified through ordinary repository governance. Any later hosted retry requires a new explicit Founder decision that names the exact repaired contract and grants exactly one new bounded attempt.