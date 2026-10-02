# MRL-0809 successor v2 repair-1 runtime-feasibility runbook

Status: REPOSITORY_PREPARED_ONLY / NO_RUNTIME_AUTHORITY

Authority: `FD-MRL-0809-SUCCESSOR-V2-STAGE4-REPAIR-1` authorizes repository repair only. It does **not** authorize a hosted Stage-4 retry.

## Purpose

This runbook defines the repaired execution path that may be used only after a separate Founder decision binds one exact canonical repaired merge SHA/tree/static manifest and authorizes exactly one further zero-cost STANDARD-T4 attempt.

The consumed successor v2 attempt remains FAIL and is never overwritten or relabeled.

## Frozen runtime policy

The repair does not change the successor roster or runtime policy:

- `Qwen/Qwen3-8B` at `b968826d9c46dd6066d109eabc6255188de91218`;
- `google/gemma-4-12B-it` at `707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7`;
- Google Colab free tier, STANDARD Tesla T4, zero monetary cost;
- `bitsandbytes-nf4-v1`, NF4 double quantization, float16 compute;
- explicit `device_map={"": 0}`; no automatic map, CPU offload, disk offload or fallback;
- `trust_remote_code=False` and local-files-only inside the isolated worker;
- isolated worker network disabled;
- synthetic prompt only, greedy single-beam generation, 12 new tokens;
- peak GPU memory ceiling 12 GiB;
- bounded cleanup; no training, optimizer, weight mutation, scientific corpus or Tier-3 access.

## Placement-audit repair

The consumed v2 attempt proved that successful explicit CUDA-0 loading does not guarantee that Transformers exposes a non-empty `hf_device_map` attribute. Repair-1 therefore makes actual materialized tensor placement authoritative.

The repaired worker:

1. loads with the same explicit `device_map={"": 0}` policy;
2. enumerates every materialized `named_parameter` and `named_buffer`;
3. requires every audited tensor to be exactly CUDA device 0;
4. rejects CPU, disk, meta, CUDA device 1+, mixed, ambiguous, malformed or empty placement evidence;
5. additionally validates `hf_device_map` when the attribute exists and fails closed if it contains any non-CUDA-0 target;
6. never permits metadata to override contradictory actual tensor placement.

## Versioned repaired artifacts

The repaired path uses:

```text
scripts/mesc_mrl_0809_runtime_feasibility_v2_repair.py
scripts/mesc_mrl_0809_runtime_worker_v2_repair.py
scripts/mesc_mrl_0809_stage4_v2_repair_driver.py
src/medscale/mesc/_mrl_0809_device_placement_audit_v1.py
specs/mesc-experiment-0/mrl-0809-static-prerequisites-v2-repair-1.json
```

The historical `scripts/mesc_mrl_0809_runtime_feasibility_v2.py` remains byte-preserved and SHA-bound. Repair-1 does not rewrite consumed-v2 evidence.

## Fail-stop execution requirement

A future authorized attempt must use the governed repaired driver rather than multi-cell best-effort notebook continuation.

The exact order is:

```text
QWEN_STAGE
-> QWEN_PROBE
-> REMOVE_QWEN_SNAPSHOT
-> GEMMA_STAGE
-> GEMMA_PROBE
-> REMOVE_GEMMA_SNAPSHOT
-> ASSEMBLE
```

Any non-zero stage or probe result stops immediately. In particular:

```text
QWEN_PROBE_FAIL => NO_GEMMA_STAGE
QWEN_PROBE_FAIL => NO_GEMMA_PROBE
NO_AUTOMATIC_RETRY
```

Cleanup failure also stops before the next candidate.

## Static qualification before any future runtime decision

Before the Founder may consider a new runtime attempt, the repository repair must be merged under ordinary governance and the exact repaired canonical main must pass all required fresh-main lanes. The repair static gate must prove:

- historical v1 and successor v2 prerequisite contracts still validate;
- the repair Founder authority is exact and repository-repair-only;
- the repair static manifest and all bound source bytes are exact;
- the repaired runtime trust root is empty;
- the repaired runtime evidence slot is `ABSENT`;
- no existing v1 or v2 trust/evidence slot was mutated.

## Future execution command

**Do not run this command under the current authority.** It is documented only so the repaired execution surface is deterministic after a later exact-revision Founder authorization.

```text
.venv/bin/python scripts/mesc_mrl_0809_stage4_v2_repair_driver.py \
  --repository-root "$PWD" \
  --custody /content/mrl0809-v2-repair-1-custody \
  --python-executable "$PWD/.venv/bin/python"
```

A future authorization must separately prove the runtime is the exact free STANDARD T4 and must establish the provider/session identity and zero-cost attestation required by the preserved successor contract.

## Current stop condition

```text
NEW_STAGE4_ATTEMPT = NOT_AUTHORIZED
SCIENTIFIC_RQ1_EXECUTION = NOT_AUTHORIZED
MRL0809_CLOSEOUT = NOT_AUTHORIZED
MRL0899_CLOSEOUT = NOT_AUTHORIZED
```

Repository qualification may continue. Hosted runtime execution must not occur until a separate Founder decision explicitly authorizes it against an exact canonical repaired revision.
