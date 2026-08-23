# MESC Backbone Tournament — Execution Implementation 13

Status: **DRAFT / FIXTURE-ONLY EXECUTION-CODE COMMIT-TREE VERIFIER / NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded implementation slice addresses only the Section D predicate that
`EXECUTION_CODE_SHA` resolve exactly to `EXECUTION_CODE_TREE`.

Canonical base:

```text
BASE_MAIN_SHA = ed595954d56cce346ee5eea9014ccb7614a56629
BASE_MAIN_TREE = dc5c3ad121ceec74e2fda0c5137e452737bacf59
PR_155 = CLOSED_CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-13/README.md
src/medscale/mesc/_bt_execution_code_tree_fixture_v1.py
tests/test_mesc_bt_execution_code_tree_fixture_v1.py
```

No dependency, lockfile, workflow, credential, provider/model, corpus/prompt,
scoring-key, real Git checkout, executor runtime, execution-result, or
activation-artifact path is changed.

## Canonical requirement

Section D requires, before activation, a mechanical verification that the exact
`EXECUTION_CODE_SHA` resolves to the exact `EXECUTION_CODE_TREE`.

The existing activation-identity fixture binds independently supplied execution
commit/tree and repository checkout commit/tree identities, but that equality
binding is not itself proof of the Git commit-to-tree relation. Execution
Implementation 12 explicitly preserves this distinction.

No existing canonical Backbone Tournament implementation currently provides a
separate verifier for this relation.

## Deliberately fixture-only

Implementation 13 performs no Git lookup. It does not invoke `git`, GitHub, a
filesystem, a checkout, or a subprocess. Instead, it validates metadata returned
by a dependency-injected resolver representing a future separately reviewed
mechanical Git-object lookup.

The verifier accepts:

```text
execution_code_sha
execution_code_tree
resolve(execution_code_sha) -> ResolvedExecutionCodeCommit
```

Both expected identities must be exact built-in lowercase 40-hex strings.
The resolver result must be exact `ResolvedExecutionCodeCommit` with:

```text
object_type = commit
commit_sha = execution_code_sha
tree_sha = execution_code_tree
```

Resolved scalar values require exact built-in strings. Wrong object type,
malformed Git identities, resolver failure, commit mismatch, tree mismatch,
subclass substitution, and equality-compatible non-string spoof values fail
closed.

## Deliberate non-claims

This slice does **not**:

- perform a real Git commit lookup;
- prove that the future resolver is trustworthy or mechanically correct;
- establish the future `EXECUTION_CODE_SHA` or `EXECUTION_CODE_TREE` values;
- inspect or acquire executor/harness files;
- replace Execution Implementation 1's canonical executor allowlist primitive;
- replace Execution Implementation 12's runtime-object identity/handoff verifier;
- establish the complete executed/imported executor-and-harness path-set equality
  predicate; that remains an independent Section D prerequisite;
- access providers, model weights, gated resources, or Phi remote code;
- serialize prompts, run inference/generation, score, rank, select a winner,
  execute the tournament, or train;
- grant execution authority.

## Relationship to adjacent slices

Execution Implementation 1 validates the canonical executor/harness allowlist
and injected exact-commit Git object metadata for allowlisted paths.

Execution Implementation 12 validates injected runtime-object acquisition and
immutable-handoff evidence against expected execution-code identities, while
explicitly not proving the commit-to-tree relation.

Implementation 13 fills only that missing relation primitive at the fixture
evidence boundary. The future activation producer must still perform the real
mechanical Git lookup and supply evidence to this pure verifier.

The complete executed/imported executor-and-harness path-set equality remains a
separate future prerequisite and is not collapsed into this slice.

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
