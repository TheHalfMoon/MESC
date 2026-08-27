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

A projection may derive `ELIGIBLE` only when every declared dependency and separately
required authority gate is satisfied by the bound canonical sources.

A projection may derive `CLOSED_CANONICAL` only when canonical evidence outside the
projection proves closure. The projection's previous state is never closure evidence.

A task with unknown, contradictory, missing, or stale dependency evidence is not
`ELIGIBLE`; it is represented as `BLOCKED` when an applicable blocker is known or remains
`PLANNED` when prerequisites are merely incomplete.

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
7. task dependencies in the projection disagree with the canonical task ledger;
8. a required authority/evidence source was omitted;
9. the projection was manually edited rather than deterministically rebuilt;
10. the projection claims `can_authorize = true` or any equivalent authority-bearing state.

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
canonical force. A consumer must validate the schema, reproduce repository/source
bindings, reproduce `source_set_sha256`, and apply the anti-staleness rules before using a
projection for navigation.

Search indexes, dashboards, caches, agent memories, and status summaries built from the
projection inherit the same non-authoritative status.

## MRL-0 acceptance

MRL-0007 is satisfied when this contract and its JSON Schema are canonically accepted and
review confirms that stale/manual projections cannot authorize work.

Implementation of a generator/validator is intentionally deferred to the later MRL
implementation stage authorized by the task ledger. This MRL-0 contract itself performs no
runtime execution.