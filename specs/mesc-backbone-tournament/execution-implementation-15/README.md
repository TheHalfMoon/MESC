# MESC Backbone Tournament — Execution Implementation 15

Status: **DRAFT / FIXTURE-ONLY CORPUS-PROJECTION VERIFIER / NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded implementation slice addresses only the still-open pre-prompt
Section D requirement for canonical corpus projection against the frozen
Repair-2 corpus identity and audit evidence.

Canonical base:

```text
BASE_MAIN_SHA = 9c36987add4c0c66f5b0eadce7a81be345618382
BASE_MAIN_TREE = e85c677914bc4f32af2c09ab245a64c43e7c3ae2
PR_157 = CLOSED_CANONICAL
IMPLEMENTATION_14_FIXTURE_EXECUTOR_EXECUTED_SET_VERIFIER = CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-15/README.md
src/medscale/mesc/_bt_corpus_projection_fixture_v1.py
tests/test_mesc_bt_corpus_projection_fixture_v1.py
```

No dependency, lockfile, workflow, credential, provider/model, real corpus,
scoring-key, prompt-template, execution-result, runtime, telemetry, activation,
or ranking path is changed.

## Canonical requirement

The frozen Repair-2 reproducibility contract requires corpus verification before
reading or serializing any case. It requires the future execution path to bind:

```text
CORPUS_SPEC_SHA256 = 49f554d57e29da4b1d04223d43f1630731e5f8c9b72e7a1e15f959e38c00643b
MATERIALIZED_CORPUS_ITEM_COUNT = 240
MATERIALIZED_CORPUS_SHA256 = 48fba9119f0170eb40775c75f12916e277cb3953abe22357e0b22497dadbbebd
MATERIALIZED_CORPUS_GZIP_SHA256 = 667cd68e5ccc9356321eb5857c6e9203e1320ec33d866ccf514411c211ceb632
CORPUS_MANIFEST_SHA256 = 201fa1351923a72097ff7e467b6dce2eb8bd0cfa1e88c73157788f77dd89e745
R2_PROVENANCE_AUDIT_SHA256 = a8f6fd8d9c9f60c5a1a2bedc0bbb49182e635772cf50dae1e9e9028a4eb09398
CORPUS_SPEC_CONFORMANCE_AUDIT_SHA256 = 842f2e0dbeaea59087223ddd94c8a95844c8f14822a16e1549e67c0c850c67f2
```

Both audits must be `PASS` before projection. The corpus specification freezes
240 items with IDs `BT-{axis}-{001..040}` over axes A-F and freezes
`prompt_projection = payload only`.

The reproducibility contract additionally requires canonical order, exactly 40
items per axis, zero gold leakage, and no prompt serialization before the
pre-prompt corpus checks are complete.

## Deliberately fixture-only

Implementation 15 does **not** open, decompress, parse, or hash the real frozen
corpus. It does not read scoring-key shards, prompt templates, model-visible case
content, or audit artifact bytes. It performs no Git, filesystem, network,
provider, model, subprocess, or hardware access.

Instead it validates two caller-supplied fixture objects:

```text
CorpusProjectionIdentityEvidence
CorpusProjectionObservation
```

`CorpusProjectionIdentityEvidence` binds the exact frozen corpus/spec/manifest
identities, exact item count, both exact preflight audit SHA-256 values, and
`PASS` dispositions.

`CorpusProjectionObservation` binds a complete fixture representation of the
canonical projected item-ID sequence and requires explicit pre-projection facts:

```text
projection_complete = True
frozen_identity_verified_before_projection = True
audits_verified_before_projection = True
payload_only_model_visibility = True
metadata_projection_events = 0
gold_or_scoring_projection_events = 0
unattributed_projection_events = 0
prompt_serialization_events = 0
```

The canonical fixture item sequence is exactly axes A-F, each with items
001-040. Missing, extra, duplicated, reordered, non-string, or subclass-spoofed
item IDs fail closed.

## Snapshot / mutation boundary

Frozen dataclasses do not constitute immutable security state in Python because
a caller can still use mechanisms such as `object.__setattr__`.

The verifier therefore:

1. requires exact caller object/container/scalar types;
2. copies caller fields into new local fixture snapshots;
3. validates only those local snapshots;
4. performs the final count binding only between the validated identity snapshot
   and validated observation snapshot;
5. never rereads caller-owned identity or observation state after the respective
   snapshot has been returned.

Synchronized regression tests mutate both caller-owned inputs after snapshotting
and prove that post-snapshot mutation cannot change the verification result.
These tests use bounded event synchronization and no sleep-based race timing.

This snapshot property is only an in-process verifier integrity guarantee. It
does not establish that a future producer observed or projected real corpus
content atomically.

## Deliberate non-claims

This slice does **not**:

- read `materialized-corpus.jsonl.gz` or its decompressed bytes;
- independently recompute the corpus or audit SHA-256 values;
- independently reproduce either preflight audit;
- inspect real corpus records or scoring keys;
- serialize a real `payload` object;
- construct `{{ITEM_PAYLOAD}}` or any task/system prompt;
- qualify a future corpus reader, decompressor, audit producer, projection
  producer, or prompt builder;
- establish that real model-visible bytes contain only payload content;
- access gated resources or model weights;
- access Phi remote code;
- dispatch prompts or run inference/generation;
- score, rank, or select a winner;
- execute the Backbone Tournament;
- train or fine-tune a model;
- grant execution activation.

The fixture observation facts are assertions from a future separately reviewed
producer. Acceptance here does not turn them into real-world execution evidence.

## Relationship to adjacent slices

Execution Implementation 2 identified canonical corpus projection as an
independent incomplete prerequisite while providing only fixture executor-core
control flow.

Execution Implementations 12-14 separately validate fixture evidence for
runtime-object identity, execution-code commit/tree relation, and the complete
executor/harness executed/imported path set. Implementation 15 does not weaken
or collapse any of those predicates.

A future activation path must still perform the real pre-prompt corpus
verification, independently bind both PASS audits, project real case content
payload-only, and then pass every remaining activation predicate before any
prompt may be serialized to a model.

## Qualification rule

Keep any PR for this slice Draft until one unchanged exact head has:

1. stable canonical base and exact three-file scope;
2. exact-head CI PASS;
3. exact-head CodeQL PASS;
4. fresh exact-head internal technical/security/governance review PASS;
5. fresh independent external exact-head review with no blocker;
6. zero unresolved blocking review threads.

Any head mutation burns prior head-specific evidence. Do not mark Ready or merge
until all exact-head gates are re-proven.

## Hard boundary

```text
REAL_CORPUS_READ = NOT_PERFORMED
REAL_CORPUS_PROJECTION = NOT_PERFORMED
REAL_PROMPT_CONSTRUCTION = NOT_PERFORMED
CORPUS_PROJECTION_PRODUCER_QUALIFICATION = NOT_ESTABLISHED
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
