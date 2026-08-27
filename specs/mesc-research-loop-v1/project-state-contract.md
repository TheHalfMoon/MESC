# MRL Project-State Projection Contract V1

Status: **MRL-0 GOVERNANCE CONTRACT / NON-AUTHORITATIVE DERIVED STATE**

Schema:

`specs/mesc-research-loop-v1/project-state-v1.schema.json`

## Purpose

Define a deterministic, machine-readable view of MRL task state without allowing a cache,
projection, dashboard, agent memory, or manually edited JSON file to become a source of
authority.

The projection exists to help tools answer questions such as:

- which MRL tasks are currently eligible;
- which dependencies are still open;
- which exact repository/source identities were used to derive the view;
- whether a previously generated view is stale.

It does not decide whether authority exists.

## Source precedence

Authority precedence is fixed:

```text
canonical Git commit/tree
  -> canonical source files and accepted governance/evidence records at that commit
  -> mechanically derived task-state interpretation
  -> project-state projection
  -> UI/cache/index presentation
```

A lower layer can never override a higher layer.

In particular:

```text
PROJECT_STATE_PROJECTION != CANONICAL_AUTHORITY
PROJECT_STATE_PROJECTION != EXECUTION_AUTHORIZATION
PROJECT_STATE_PROJECTION != TRAINING_AUTHORIZATION
PROJECT_STATE_PROJECTION != MODEL_PROMOTION
PROJECT_STATE_PROJECTION != CLINICAL_AUTHORITY
```

## Exact repository binding

Every projection must bind:

- `repository.commit_sha`: the exact 40-lowercase-hex commit used for derivation;
- `repository.tree_sha`: that commit's exact tree;
- every canonical source path used to derive task state;
- the Git blob SHA for each source path at the bound commit;
- SHA-256 of the exact source bytes for each source path.

The projection must not read an unpinned working-tree file and then claim a different Git
commit as its source.

A source `path` is a repository-relative ASCII path. It must not be absolute, contain an
empty component, contain `.` or `..` components, contain backslashes, or use an alternate
spelling that could resolve to the same repository path. Symlink/gitlink/non-regular-object
semantics are not inferred from a string path: when object type matters, the deriving
implementation must resolve the bound Git object and fail closed on an unacceptable type.

## Required canonical sources

At minimum, an MRL V1 task-state projection must bind the canonical versions of:

- `specs/mesc-research-loop-v1/README.md`;
- `specs/mesc-research-loop-v1/spec.md`;
- `specs/mesc-research-loop-v1/plan.md`;
- `specs/mesc-research-loop-v1/tasks.md`;
- all accepted ADRs or companion contracts directly required to interpret the task states
  represented in the projection;
- any immutable evidence record used to justify `CLOSED_CANONICAL` for a represented task.

A projection may bind additional sources, but it must not silently omit a source whose
semantics affect the represented state.

## Identity uniqueness

Identity-bearing arrays are fail-closed:

- each `sources[].path` must appear exactly once;
- each `tasks[].task_id` must appear exactly once;
- each task's dependency IDs must be unique;
- each task's evidence references must be unique.

A duplicate source path is invalid even when the duplicate entries carry different blob or
byte hashes. A duplicate task ID is invalid even when the duplicate entries carry different
states or evidence. Ambiguity is never resolved by first-wins, last-wins, array order, or
merging duplicate records.

JSON Schema `uniqueItems` provides an additional structural duplicate check, but consumers
must also enforce the identity-specific uniqueness rules above because two unequal JSON
objects can still claim the same `path` or `task_id`.

## Mandatory projection-admission validator

Schema validation alone is insufficient to admit a projection for use.

Every component that wants to use MRL project state for task eligibility, dependency
navigation, closeout status, or automation must pass the bytes through **one canonical
projection-admission validator** before consumption. Direct use of raw JSON, use after only
JSON Schema validation, or consumer-specific first/last-wins reconciliation is prohibited.

The admission validator must, at minimum:

1. parse with duplicate JSON member rejection;
2. validate `project-state-v1.schema.json`;
3. enforce source-path normalization and reject absolute, empty, `.`, `..`, backslash, or
   alternate-path ambiguity;
4. reject repeated `sources[].path` even when the objects differ;
5. reject repeated `tasks[].task_id` even when states/evidence differ;
6. reject repeated dependency IDs or evidence references;
7. resolve and verify the bound commit/tree and every required source Git object;
8. reproduce every source byte SHA-256 and `source_set_sha256`;
9. independently recompute the complete expected `tasks[]` array from the bound canonical
   sources and evidence, without trusting any projected task field as an input;
10. compare the supplied `tasks[]` with that independently recomputed array and reject any
    semantic or canonical-byte mismatch;
11. enforce all anti-staleness rules in this contract;
12. require `projection_kind = DERIVED_NON_AUTHORITATIVE` and `can_authorize = false`.

Until that validator is separately implemented, tested, reviewed, and canonically accepted,
project-state examples may be inspected as contract fixtures but **must not be used to make
an eligibility or closure decision**. Canonical source inspection remains the required
decision path.

## Complete task-array derivation

`tasks[]` is output-only derived state. A validator or generator must never accept the
projection's own `task_id`, `state`, `dependencies`, or `evidence_refs` as evidence for what
those fields should be.

The canonical derivation procedure must operate only on the bound canonical sources and
independently bound evidence:

1. enumerate every task record from the bound canonical task ledger;
2. require each task identifier to match `MRL-[0-9]{4}` and occur exactly once;
3. derive `dependencies` from the task ledger's explicit `Depends on:` / `Requires:`
   clauses, expanding closed task-ID ranges such as `MRL-0001..0008` deterministically and
   rejecting malformed, reversed, cross-prefix, unknown, or ambiguous ranges;
4. discover the independently bound evidence required by that task's acceptance/gate
   semantics; the projected `evidence_refs` array is not a discovery source;
5. derive `state` from the canonical task ledger plus independently verified dependency,
   authority, review, check, and closeout evidence required by the task;
6. if the canonical sources do not contain enough information to determine one exact state
   or one exact evidence-reference set, return an indeterminate derivation failure and
   reject the projection rather than trusting the projected value;
7. sort dependencies and evidence references uniquely as required by this contract;
8. sort the complete expected task records by `task_id`;
9. canonicalize the independently derived array and require semantic equality and
   byte-for-byte canonical equality with the supplied `tasks[]` array.

State derivation is fail-closed:

- `CLOSED_CANONICAL` requires independent canonical closure evidence satisfying the task's
  own gate; a checkbox, projected prior state, or downstream task is not sufficient by
  itself;
- `ELIGIBLE` requires every declared dependency plus every separately applicable authority
  gate to be independently proven at the bound source identity;
- incomplete prerequisites remain `PLANNED` unless a canonical blocker establishes
  `BLOCKED`;
- `QUALIFYING` and `IN_PROGRESS` require independently bound canonical evidence of those
  states rather than self-assertion by the projection;
- contradictory evidence, ambiguous status, or evidence that cannot be reproduced causes
  derivation failure rather than state selection.

This full recomputation rule makes semantic manual edits detectable even when an attacker or
operator leaves `repository`, `sources`, hashes, ordering, `projection_kind`, and
`can_authorize` unchanged. Changing a projected task state, dependency, or evidence
reference without changing canonical sources necessarily disagrees with the independently
recomputed expected array and is rejected.

The later validator implementation must include negative fixtures proving rejection of at
least:

- two unequal source objects with the same `path` and conflicting hashes;
- two unequal task objects with the same `task_id` and conflicting state/evidence;
- duplicated dependency IDs;
- duplicated evidence references;
- absolute, empty-component, `.`, `..`, and backslash source paths;
- stale commit/tree/source hashes;
- omitted required authority/evidence sources;
- a manually altered task `state` with every repository/source hash left unchanged;
- a manually altered dependency/evidence reference with every repository/source hash left
  unchanged;
- an indeterminate state for which the projection attempts to supply its own answer;
- `can_authorize=true` or an equivalent authority-bearing variant.

MRL-0 freezes these validator and derivation requirements; it does not implement the
validator.

## Deterministic serialization

Semantic projection bytes use UTF-8, no BOM, LF line endings, and canonical JSON with:

- object keys sorted lexicographically by Unicode code point;
- no insignificant whitespace;
- JSON arrays with deterministic ordering defined below;
- no wall-clock timestamps, random IDs, local filesystem paths, usernames, hostnames, or
  other environment-specific values in semantic bytes.

Array ordering is:

- `sources`: ascending by `path` ASCII bytes;
- `tasks`: ascending by `task_id` ASCII bytes;
- each task's `dependencies`: ascending unique task IDs;
- each task's `evidence_refs`: ascending unique canonical reference strings.

A serializer that cannot reproduce these bytes exactly must fail rather than emit a
non-deterministic canonical projection.

## Source-set digest

`source_set_sha256` is derived from the canonical ordered `sources` array only.

The digest preimage is the canonical JSON serialization of the `sources` array under the
rules above. `source_set_sha256` is outside that preimage, preventing self-reference.

## Task-state derivation

The allowed states are:

```text
PLANNED
ELIGIBLE
IN_PROGRESS
BLOCKED
QUALIFYING
CLOSED_CANONICAL
```

The complete task-array derivation rules above control how these states are computed. A
projection never supplies its own authoritative state.

## Anti-staleness rules

A projection is stale and non-usable for eligibility decisions if any of the following is
true:

1. the repository's current decision base no longer equals `repository.commit_sha` for the
   decision being made;
2. the bound commit does not resolve to `repository.tree_sha`;
3. any source path is missing at the bound commit;
4. any source Git blob SHA differs from the recorded value;
5. any source byte SHA-256 differs from the recorded value;
6. `source_set_sha256` cannot be reproduced;
7. the supplied complete `tasks[]` array differs from the independently recomputed expected
   array;
8. a required authority/evidence source was omitted;
9. a source path or task identity is duplicated or ambiguously encoded;
10. the projection was manually edited and therefore cannot reproduce canonical derived
   bytes;
11. the projection claims `can_authorize = true` or any equivalent authority-bearing state.

Staleness is fail-closed. A stale projection is discarded and rebuilt from canonical
sources; it is not patched by hand.

## No authority amplification

The schema requires:

```json
{
  "projection_kind": "DERIVED_NON_AUTHORITATIVE",
  "can_authorize": false
}
```

No consumer may reinterpret the projection as permission to:

- access real model weights or corpora;
- accept gated terms;
- activate provider credentials or network access;
- use a GPU or accelerator;
- run inference or training;
- execute real autonomous experiments;
- read PHI/product telemetry/clinical-runtime learning inputs;
- mint training authorization;
- promote a model;
- deploy or release;
- make a clinical assertion or action.

The absence of a blocker in the projection is not positive authority.

## Manual edits and derived tooling

Generated project-state JSON may be stored for inspection, but manual edits have no
canonical force. A consumer must use the canonical projection-admission validator and
complete task-array recomputation before using a projection for navigation or state
decisions.

Search indexes, dashboards, caches, agent memories, and status summaries built from the
projection inherit the same non-authoritative status and must not bypass validator
admission.

## MRL-0 acceptance

MRL-0007 is satisfied when this contract and its JSON Schema are canonically accepted and
review confirms that stale/manual/ambiguous projections cannot authorize work, cannot be
consumed for eligibility without the required validator gate, and cannot preserve a
manually fabricated task state because the entire task array must be independently
recomputed.

Implementation of the validator/generator and its negative fixtures is intentionally
deferred to the later machine-state implementation stage authorized by the task ledger.
This MRL-0 contract itself performs no runtime execution.