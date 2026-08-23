# Backbone Tournament execution implementation 3 — fixture evidence bundle

Status: **DRAFT IMPLEMENTATION SLICE — NO EXECUTION AUTHORITY**

This package is the third bounded implementation slice after canonical adoption of
`FD-MESC-BT-EXEC-1`. It addresses only the Section D evidence/artifact surface
using caller-supplied fixture observations.

## Exact base

```text
BASE_MAIN_SHA = ab4d64f8708f649d33e494a4bed0272a2a526d9c
BASE_MAIN_TREE = 8fb0ccb9377a97b024e674b99f4d5ff89e34099e
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

This slice is intentionally independent of PR #140 and PR #141. It does not
import either branch and must remain reviewable directly against canonical main.

## Scope

The fixture evidence compiler/verifier provides:

- the exact four Section C candidate keys and deterministic candidate-major order;
- an exact expected-item matrix supplied by the caller, without reading frozen corpus bytes;
- one or two attempts per candidate/item pair, with contiguous attempt numbering;
- second-attempt admission only after `infrastructure_error`; `timeout` is terminal and cannot
  justify a second-attempt record;
- monotonic timestamp validation and exact `elapsed_ns = end - start` enforcement;
- successful-attempt raw-response byte presence;
- raw responses emitted as separate immutable `.bin` artifacts rather than embedded in ledgers;
- SHA-256 and byte length for every raw-response artifact;
- deterministic `attempts.jsonl` and `items.jsonl` fixture evidence ledgers;
- terminal item latency in integer nanoseconds as the sum of all recorded attempt durations;
- a deterministic manifest over every emitted evidence artifact with exact byte lengths and SHA-256;
- a SHA-256 over the exact manifest bytes;
- verifier-side recomputation of artifact lengths, artifact SHA-256 values, canonical manifest bytes,
  and manifest SHA-256;
- fail-closed rejection of missing candidate/item evidence, duplicates, unexpected items,
  invalid paths, invalid timing, invalid retry sequences, tampered artifacts, or manifest drift.

All operations are pure in-memory byte transformations. The module has no
filesystem reader/writer, subprocess, Git resolver, network client, provider
client, model loader, prompt builder, tokenizer, inference adapter, or credential
surface.

## Deliberate non-claims

This slice does **not** define the final activation evidence format. In particular:

- `terminal_item_latency_ns` is raw fixture timing evidence; the frozen Section F.2
  `terminal_item_latency_ms`/median contract remains to be integrated after the
  executor and evidence surfaces are canonicalized together;
- the manifest inventories only artifacts emitted by this fixture bundle and is
  not the future full tournament artifact manifest;
- this slice does not bind `EXECUTION_CODE_SHA`, `EXECUTION_CODE_TREE`, the final
  executor allowlist, runtime bytes, telemetry/NVML evidence, report-validation
  artifacts, Phi remote-code artifacts, gated-access attestations, or activation receipt;
- it does not read canonical Repair-2 corpus, prompt, scoring-key, parser-contract,
  scoring-contract, or report-contract bytes.

## Local fixture qualification before push

A standalone local harness over only this module and deterministic fixtures completed:

```text
py_compile = PASS
fixture tests = 24 passed
```

No network, provider, model, weights, credentials, inference, generation, ranking,
or frozen tournament inputs were used by that harness. Repository-integrated
GitHub CI and CodeQL remain authoritative exact-head gates after push.

## Hard boundary

```text
EXECUTION_ACTIVATION = REQUIRED
MODEL_WEIGHT_ACCESS = NOT_AUTHORIZED
GATED_ACCESS_REQUEST_OR_ACCEPTANCE = NOT_AUTHORIZED
MODEL_RETRIEVAL = NOT_AUTHORIZED
PROMPT_SERIALIZATION_TO_MODEL = NOT_AUTHORIZED
INFERENCE = NOT_AUTHORIZED
GENERATION = NOT_AUTHORIZED
RANKING = NOT_AUTHORIZED
WINNER_SELECTION = NOT_AUTHORIZED
BACKBONE_TOURNAMENT_EXECUTION = NOT_AUTHORIZED
TRAINING = NOT_AUTHORIZED
```

Keep any PR containing this slice Draft until exact-head CI, CodeQL, scope
reconciliation, and an independently permitted review are all proven. A head
change burns prior exact-head evidence.
