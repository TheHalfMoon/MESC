# MESC Backbone Tournament — Execution Implementation 9

Status: **DRAFT / FIXTURE-ONLY PHI EXECUTED-FILE-SET EVIDENCE VERIFIER / NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded implementation slice addresses one fixture-level predicate in
`FD-MESC-BT-EXEC-1` Section C.3 that remains after Execution Implementations 6
and 8:

```text
the executed Phi remote-code file set equals PHI_REMOTE_CODE_MANIFEST exactly,
with no additional dynamically fetched or imported remote file
```

Canonical base for this slice:

```text
BASE_MAIN_SHA = bb198b3aac69ca8e89c29b3502997d529919b714
BASE_MAIN_TREE = 10ed859e9ae1343efc54d9e1102305397f98f9ac
PR_151 = CLOSED_CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-9/README.md
src/medscale/mesc/_bt_phi_executed_set_fixture_v1.py
tests/test_mesc_bt_phi_executed_set_fixture_v1.py
```

No dependency, lockfile, workflow, credential, provider, model, tokenizer,
processor, corpus, prompt, scoring-key, real Phi source, runtime acquisition,
sandbox, instrumentation runtime, or execution-result path changes.

## Fixture evidence contract

The verifier accepts:

1. a parser-validated canonical `PhiRemoteCodeManifest` from Execution
   Implementation 6; and
2. one caller-supplied `PhiRemoteCodeExecutionObservation` representing a
   separately produced full-lifecycle observation.

Before any observation value can be accepted, the verifier reserializes and
reparses the manifest under the canonical manifest rules and requires the full
manifest dataclass identity to match.

The observation must have exact type
`PhiRemoteCodeExecutionObservation` and contain:

```text
executed_remote_code_paths
observation_complete
observation_started_before_first_remote_code_import
observation_ended_after_model_process_exit
dynamic_remote_fetch_attempts
unattributed_remote_code_execution_events
```

`executed_remote_code_paths` is a canonical unique-set representation, not
runtime event order. It must be an exact Python tuple whose members are exact
Python strings, in the same canonical path order as the manifest. Therefore
missing paths, additional paths, duplicate paths, reordered/non-canonical
representations, non-string equality-spoof members, or any other mismatch fail
closed.

The supplied observation must additionally prove with exact booleans that:

```text
observation_complete = true
observation_started_before_first_remote_code_import = true
observation_ended_after_model_process_exit = true
```

and must report exact Python integer zero for:

```text
dynamic_remote_fetch_attempts = 0
unattributed_remote_code_execution_events = 0
```

Using `type(value) is bool` and `type(value) is int` prevents Python bool/int
substitution at these boundaries.

A positive or negative nonzero counter, a boolean counter, an incomplete
observation, an observation that begins after the first remote-code import, an
observation that ends before model-process exit, or any unattributed remote-code
execution event is `BLOCKED` under this fixture contract.

## Deliberate non-claims

This module does **not** instrument, start, observe, stop, or otherwise interact
with a real model process. It does not import or execute Phi remote code. It does
not fetch a remote file, access a network, inspect a filesystem, read a model,
access a provider, or access credentials.

The observation fields are injected evidence produced by a future separately
reviewed instrumentation/sandbox layer. Requiring
`observation_complete = true` does not make an untrusted producer complete;
this fixture only validates the closed shape and consistency of supplied
evidence. Production acceptance still requires independent trust in the
producer and its provenance.

This slice does not:

- establish a production `PHI_REMOTE_CODE_MANIFEST_SHA256`;
- prove that the real executed/imported file set was observed completely;
- establish or validate a production event log or instrumentation mechanism;
- prove that a real runtime made zero remote-fetch attempts;
- establish the complete Phi import graph;
- establish `PHI_REMOTE_CODE_SECURITY_REVIEW = PASS` or its digest;
- establish runtime same-inode/same-bytes acquisition beyond the fixture
  primitive already provided by Implementation 8;
- establish sandbox/network/credential/process-isolation qualification;
- establish `PHI_SANDBOX_QUALIFICATION_SHA256`;
- establish gated-access authority or any access attestation;
- establish live H100 telemetry qualification;
- establish final activation receipt validity;
- integrate a production executor;
- serialize prompts, run inference or generation, score, rank, select a winner,
  execute the tournament, or train;
- grant execution authority.

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
