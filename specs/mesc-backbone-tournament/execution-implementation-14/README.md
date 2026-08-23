# MESC Backbone Tournament — Execution Implementation 14

Status: **DRAFT / FIXTURE-ONLY EXECUTOR EXECUTED-SET VERIFIER / NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded implementation slice addresses only the Section D predicate that
the complete executed/imported executor-and-harness path set equals the
canonical executor allowlist exactly.

Canonical base:

```text
BASE_MAIN_SHA = d701efee3df7b9a6de313f3a65fba1b6eab3e50a
BASE_MAIN_TREE = 37be370745fa93abc0f1589b147ce6a9622062fb
PR_156 = CLOSED_CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-14/README.md
src/medscale/mesc/_bt_executor_executed_set_fixture_v1.py
tests/test_mesc_bt_executor_executed_set_fixture_v1.py
```

No dependency, lockfile, workflow, credential, provider/model, corpus/prompt,
scoring-key, real executor checkout, runtime instrumentation, harness execution,
execution-result, or activation-artifact path is changed.

## Canonical requirement

Section D requires the independently reviewed executable/imported
executor-and-harness path set to equal `EXECUTOR_PATHS_AND_BLOB_SHAS` exactly:

- no reviewed executable path may be absent;
- no extra allowlist entry may exist;
- no executor/harness file outside the allowlist may execute or be imported;
- missing, duplicate, extra, or omitted executable paths fail closed.

Execution Implementation 1 provides the canonical executor allowlist primitive.
Execution Implementation 12 validates injected runtime-object acquisition and
immutable-handoff evidence. Execution Implementation 13 validates injected
commit-to-tree resolution evidence. None of those slices establishes the
complete executed/imported path-set predicate.

## Deliberately fixture-only

Implementation 14 does **not** execute or import executor/harness code and does
not observe a real process. It validates caller-supplied observation evidence
from a future separately reviewed producer/instrumentation layer.

The verifier accepts:

- a parser-validated canonical `ExecutorAllowlist`;
- one exact `ExecutorHarnessExecutionObservation`.

Before observation evidence is accepted, the allowlist is revalidated with:

- exact `ExecutorAllowlist` outer type;
- exact tuple container;
- exact `ExecutorAllowlistEntry` entry types;
- exact built-in string metadata and path/blob scalar types;
- exact built-in integer byte length;
- canonical serialization and parse round-trip;
- full equality with the reparsed canonical allowlist, including digest and byte
  length.

Forged dataclass/subclass representations or metadata that does not reproduce
the canonical object fail closed.

## Observation contract

`ExecutorHarnessExecutionObservation` records only injected fixture facts:

```text
executed_or_imported_paths
observation_complete
observation_started_before_first_execution_or_import
observation_ended_after_last_execution_or_import
unattributed_execution_or_import_events
```

`executed_or_imported_paths` is a **canonical unique-set representation**, not a
chronological event log. Its tuple order is the same canonical path order as the
validated allowlist. The verifier requires the tuple to equal exactly:

```text
tuple(entry.path for entry in allowlist.entries)
```

Therefore missing paths, extra paths, duplicate path representations, reordered
representations, string-subclass values, and equality-compatible non-string
spoofs fail closed.

The verifier additionally requires exact built-in `bool` `True` for:

```text
observation_complete
observation_started_before_first_execution_or_import
observation_ended_after_last_execution_or_import
```

and requires:

```text
unattributed_execution_or_import_events = 0
```

as an exact built-in integer. Boolean/integer substitution and nonzero or
negative counters fail closed.

These fields are assertions supplied by the future evidence producer. Their
acceptance by this pure verifier does **not** establish that the producer,
instrumentation, process hooks, import hooks, tracing mechanism, or runtime
coverage are trustworthy or complete in reality.

## Deliberate non-claims

This slice does **not**:

- start or observe a real executor/harness process;
- import or execute executor/harness code;
- inspect Python import machinery or executable process events;
- qualify the future observation producer or instrumentation mechanism;
- perform a real Git lookup or independently establish the execution-code
  commit/tree relation; Implementation 13 provides only the adjacent fixture
  evidence primitive for that relation;
- perform runtime object acquisition or independently prove immutable handoff;
  Implementation 12 provides only the adjacent fixture evidence primitive;
- replace or weaken Execution Implementation 1's canonical allowlist parser;
- establish production `EXECUTION_CODE_SHA`, `EXECUTION_CODE_TREE`, or
  `EXECUTOR_ALLOWLIST_SHA256` values;
- access providers, model weights, gated resources, or Phi remote code;
- serialize prompts, run inference/generation, score, rank, select a winner,
  execute the tournament, or train;
- grant execution authority.

## Relationship to adjacent slices

Implementation 14 consumes the canonical allowlist representation from
Implementation 1 but does not duplicate its Git-tree object-resolution checks.
It complements Implementation 12's runtime-object identity/handoff evidence and
Implementation 13's commit/tree relation evidence without collapsing those
independent predicates.

A future activation/conformance producer must still generate trustworthy,
mechanically complete runtime evidence and bind all adjacent primitives on the
same activation-scoped identities before this Section D predicate can be treated
as real-world proof.

## Qualification rule

Keep any PR for this slice Draft until one unchanged exact head has:

1. stable canonical base and exact three-file scope;
2. exact-head CI PASS;
3. exact-head CodeQL PASS;
4. fresh exact-head internal technical/security review PASS;
5. fresh independent external exact-head review with no blocker;
6. zero unresolved blocking review threads.

Any head mutation burns prior head-specific evidence. Do not mark Ready or merge
until all exact-head gates are proven.

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
