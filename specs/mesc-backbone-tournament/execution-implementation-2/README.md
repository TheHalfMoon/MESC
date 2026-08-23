# Backbone Tournament Executor Core — Fixture Qualification Slice 1

Status: **DRAFT IMPLEMENTATION SLICE — NO EXECUTION AUTHORITY**

This directory documents the second bounded implementation slice after canonical adoption of
`FD-MESC-BT-EXEC-1`. The slice is intentionally independent of PR #140 and is based directly on
canonical `main` at:

```text
BASE_MAIN_SHA = ab4d64f8708f649d33e494a4bed0272a2a526d9c
BASE_MAIN_TREE = 8fb0ccb9377a97b024e674b99f4d5ff89e34099e
```

## Purpose

Provide a fixture-only executor core that exercises Section D control flow without creating a
live model execution path.

The implementation provides:

- the exact four-candidate identity/order frozen by Section C;
- deterministic fixture payload serialization with model-visible and gold bytes held separately;
- recursive rejection of declared gold/scoring keys from model-visible fixture payloads;
- a hard maximum of two attempts, representing the initial attempt plus at most one retry;
- an activation-bindable retry policy that permits a second attempt only after an
  `infrastructure_error`; `timeout` is terminal and cannot trigger a retry;
- injected monotonic nanosecond timing around the adapter call only;
- per-attempt start/end timestamps, elapsed time, disposition, raw response, and response SHA-256;
- terminal item latency equal to the sum of all attempted generation-call durations;
- strict successful-output hook order: parser -> schema validator -> scorer -> report validator;
- exact sequential traversal of the four candidate identities;
- exact 240-item latency-summary enforcement with the even-count median rule from Section F.2;
- deterministic artifact SHA-256 and byte-length inventory helpers.

## Fixture-only construction

`src/medscale/mesc/_bt_executor_core_fixture_v1.py` contains no model loader, Transformers import,
provider client, credential reader, network access, filesystem acquisition, subprocess execution,
RunPod integration, NVML integration, prompt template, frozen Repair-2 loader, ranking, or winner
selection.

The generation boundary is a dependency-injected `FixtureAttemptAdapter`. The executor refuses an
adapter unless it explicitly declares `fixture_only=True`. Tests use deterministic in-memory fake
adapters and injected clocks only.

No canonical Repair-2 corpus bytes, task prompts, scoring-key bytes, or gated repository content are
read by this slice.

## What remains incomplete

This slice does **not** complete Section D. Before execution activation, later separately reviewed
work must still provide and prove at least:

- canonical corpus projection against post-claim frozen inputs;
- exact frozen prompt construction and model-specific adapter implementation;
- exact timeout value reconstructed from the frozen protocol configuration;
- strict canonical parser/schema/scoring/report-validator implementations rather than fixture
  hooks;
- runtime executor/harness allowlist binding to the final execution commit/tree;
- descriptor-relative runtime byte verification and executable/import closure;
- NVML peak-VRAM telemetry and exact-instance no-model H100 qualification;
- complete execution artifact manifest production;
- Phi remote-code acquisition, manifest, sandbox qualification, and independent security review;
- separately authorized gated-access actions for Apertus and MedGemma;
- activation receipt and every remaining activation predicate.

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

Merging this slice later, by itself, must not be interpreted as activation or as authority to read
frozen pre-claim content, acquire a model, accept terms, allocate an execution runtime, send a
prompt, or run the tournament.
