# MESC Backbone Tournament — Execution Implementation 7

Status: **DRAFT / FIXTURE-ONLY FROZEN PROTOCOL-POLICY BINDER / NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded implementation slice closes one explicit fixture gap left by
Execution Implementation 2: the executor control-flow fixture models one
infrastructure retry but does not itself reconstruct the exact timeout/retry and
equal-treatment controls from the frozen Repair-2 `protocol-config.json`.

Canonical base for this slice:

```text
BASE_MAIN_SHA = 2d9c73b372f0135d74d996d6023444ab0ee93a78
BASE_MAIN_TREE = 8e3d2fbc471bbebe70e6dd6816c8b353eea5fa8e
PR_148 = CLOSED_CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-7/README.md
src/medscale/mesc/_bt_protocol_policy_fixture_v1.py
tests/test_mesc_bt_protocol_policy_fixture_v1.py
```

No dependency, lockfile, workflow, credential, provider, model-weight,
tokenizer, processor, corpus, prompt, scoring-key, sandbox, runtime-acquisition,
or execution-result path is changed.

## Canonical source contract

The binder is tied to the already-frozen Repair-2 protocol configuration:

```text
PROTOCOL_ID = MESC-BT-PROTOCOL-V1
PROTOCOL_CONFIG_SHA256 =
  097cdd11f5389203cf432760ec316a78b12d157c0676477de69dde707e058203
```

The frozen policy requires, among other controls:

```text
timeout_seconds = 180
infrastructure_retries = 1
parse_retries = 0
schema_retries = 0
semantic_retries = 0
single_turn = true
input_tokens = 8192
output_tokens = 1024
tools = false
retrieval = false
web = false
function_calls = false
candidate_specific_prompt_optimization = PROHIBITED
do_sample = false
seed = 0
temperature = 0.0
top_p = 1.0
top_k = DISABLED_WHERE_SUPPORTED
score_hidden_cot = false
gpt_oss_reasoning_effort = medium_native_required_value
```

## Implemented fixture contract

The pure binder:

- accepts only caller-supplied exact bytes;
- rejects UTF-8 BOMs, malformed UTF-8, duplicate JSON members, non-standard
  JSON constants, oversized-integer parser failures, and excessive nesting
  through a typed fail-closed error surface;
- requires a JSON object with the exact frozen top-level key set;
- canonically reserializes with lexical object-key ordering, compact separators,
  ASCII output, and no trailing newline, then requires byte-for-byte equality;
- checks exact JSON scalar/container types before value equality so Python
  equality such as `True == 1` cannot satisfy an integer policy field;
- reconstructs and verifies the exact frozen timeout, retry, token-limit,
  single-turn, no-tools/no-retrieval/no-web/no-function-call, decoding,
  reasoning, terminal-error-class, and tie-policy values;
- requires the SHA-256 of the complete canonical `protocol-config.json` bytes to
  equal the frozen Repair-2 digest, thereby also binding the artifact identities
  outside the execution-policy subset;
- returns an immutable `FrozenExecutionPolicy` value whose
  `maximum_generation_attempts_per_item` is deterministically the initial
  attempt plus the one permitted infrastructure retry.

The module itself performs no repository read, file open, network operation,
subprocess, timeout, retry, prompt construction, model load, model call,
inference, scoring, ranking, or training.

## Deliberate non-claims

This slice does **not** integrate the policy with a production executor and does
not prove that a real model invocation is terminated at 180 seconds or that a
runtime actually performs no more than one infrastructure retry.

It does not:

- read the canonical Repair-2 protocol file from disk at runtime;
- read or expose the frozen corpus, task prompts, system prompt, or scoring keys;
- project a real corpus item into a prompt;
- serialize any prompt to a candidate model;
- instantiate a tokenizer, processor, model, or provider client;
- implement model-specific prompt orchestration;
- invoke parser, schema, scoring, or report-validation code on a real response;
- execute a retry or timeout;
- prove runtime sandbox, remote-code, telemetry, gated-access, or activation
  predicates;
- grant execution authority.

A future production executor must consume a separately verified canonical policy
binding and mechanically prove that its actual runtime behavior obeys these
values. This fixture is only the deterministic frozen-policy reconstruction and
binding primitive.

## Hard boundary

```text
EXECUTION_ACTIVATION = REQUIRED
MODEL_WEIGHT_ACCESS = NOT_AUTHORIZED
GATED_ACCESS_REQUEST_OR_ACCEPTANCE = NOT_AUTHORIZED
MODEL_RETRIEVAL = NOT_AUTHORIZED
PHI_REMOTE_CODE_IMPORT_OR_EXECUTION = NOT_AUTHORIZED
PROMPT_SERIALIZATION_TO_MODEL = NOT_AUTHORIZED
INFERENCE = NOT_AUTHORIZED
GENERATION = NOT_AUTHORIZED
RANKING = NOT_AUTHORIZED
WINNER_SELECTION = NOT_AUTHORIZED
BACKBONE_TOURNAMENT_EXECUTION = NOT_AUTHORIZED
TRAINING = NOT_AUTHORIZED
```

Keep any PR for this slice Draft until GitHub-native scope reconciliation,
fresh exact-head CI, fresh exact-head CodeQL, fresh exact-head internal
technical/security review, at least one independent external exact-head review,
and zero unresolved blocking review threads are all proven. Any head mutation
burns prior head-specific qualification evidence.
