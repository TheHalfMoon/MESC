# MESC Training Corpus Binding V1

Status: **IMPLEMENTATION / T5↔SFT BINDING / NO TRAINING EXECUTION**

Canonical base:

```text
BASE_MAIN_SHA = aa04df3611d23818712116aef0af396eeab657b5
PR_183 = CLOSED_CANONICAL
TRAINING_EXAMPLE_CONTRACT = CANONICAL
TRAINING_EXECUTION = NOT_PERFORMED
```

## Purpose

T5 qualification proves the exact training-record membership and its governance evidence.
The supervised-example contract proves how eligible SFT examples are represented. These
are intentionally different identities: a corpus may contain multiple supervised examples
derived from one qualified training record, and corpus metadata may change without
changing T5 membership.

This gate binds those layers before any local artifact or trainer can consume the corpus.
It proves exact T5 record-set equality and freezes both the semantic corpus identity and
the exact UTF-8 bytes of canonical JSONL.

## Scope

Exactly three paths are introduced:

```text
specs/mesc-training-corpus-binding-v1/README.md
src/medscale/mesc/_training_corpus_binding_v1.py
tests/test_mesc_training_corpus_binding_v1.py
```

No dependency, workflow, CLI, dataset-builder, readiness, launch-plan, provider, model,
or trainer configuration is changed.

## Required canonical inputs

`bind_training_corpus(...)` accepts only exact canonical base types:

- `TrainingDatasetQualificationReport`; and
- `TrainingCorpusV1`.

Subclasses are rejected. This prevents overridden serialization or stale/forged object
behavior from entering a content-addressed training boundary.

The qualification may be `BLOCKED`, but a blocked qualification can never produce a PASS
binding.

## Exact T5 record-set identity

The binding recomputes the corpus membership hash using the exact T5 algorithm introduced
by Training Dataset Qualification V1:

```python
content_hash(
    {
        "kind": "mesc.training_dataset.record_ids.v1",
        "record_ids": sorted(corpus.training_record_ids),
    }
)
```

PASS requires exact equality with:

```text
qualification.training_record_ids_sha256
```

This is set-level membership identity because `TrainingCorpusV1.training_record_ids`
contains unique sorted T5 record IDs. Multiple SFT examples may reference the same
qualified training record without changing membership identity.

Missing and extra T5 record identifiers both fail closed.

Unicode and other record identifiers accepted by `SplitAssignmentFreeze` are preserved
and hashed exactly; this gate performs no normalization or alternate identifier grammar.

## Three distinct content identities

The binding intentionally records three different identities rather than substituting one
for another.

### 1. T5 training dataset identity

```text
training_dataset_sha256
```

Copied from the exact PASS T5 qualification. This covers the released dataset identity,
split freeze, and T5 training membership.

### 2. Semantic SFT corpus identity

```text
corpus_sha256
```

Copied from `TrainingCorpusV1`. This covers the complete auditable SFT records: source,
license, provenance, evidence references, T5 record identity, targets, uncertainty,
review state, prompt, completion, and all other canonical fields.

Changing metadata can therefore change this identity even when T5 membership remains
unchanged.

### 3. Canonical JSONL byte identity

The exact output of:

```python
corpus.canonical_jsonl().encode("utf-8")
```

is frozen as:

```text
canonical_jsonl_sha256
canonical_jsonl_byte_count
```

`canonical_jsonl_sha256` is ordinary SHA-256 over the raw bytes. It is deliberately not
`content_hash`, because downstream local artifact attestation must verify exact file
bytes, not merely semantic JSON content.

No file is written by this PR. The raw digest and byte count define what a later local
materialization must match.

## Binding report

`TrainingCorpusBindingReport` records:

- disposition (`BLOCKED` or `PASS`);
- exact T5 qualification SHA;
- exact T5 training-dataset SHA;
- qualified T5 record-set SHA;
- semantic corpus SHA;
- recomputed corpus T5 record-set SHA;
- canonical JSONL raw SHA;
- canonical JSONL byte count;
- SFT example count;
- blockers; and
- exact binding version.

The complete report has deterministic `binding_sha256`.

`can_attest_local_artifact` is true only for PASS with no blockers. It does **not** mean
training is authorized or ready; it only allows the next local-artifact attestation gate
to consume this evidence.

## Forged-PASS hardening

A directly constructed PASS report is rejected when:

- blockers are present;
- qualified and corpus training-record identities differ;
- canonical JSONL byte count is zero; or
- SFT example count is zero.

All SHA fields require exact 64-character lowercase hexadecimal strings. Counts require
real non-negative integers, excluding booleans. Blockers must be an immutable tuple of
non-empty strings.

The authoritative binding function computes the semantic/raw identities itself from exact
canonical inputs.

## Security and execution boundary

This package performs no:

- filesystem read or write;
- external dataset read or download;
- provider or credential access;
- license or gated-term acceptance;
- model-weight access or retrieval;
- tokenizer/model construction;
- remote-code loading;
- inference or generation;
- GPU execution;
- trainer import; or
- fine-tuning/training.

Tests use synthetic/hand-authored contract objects only.

## Next gate

After this binding becomes canonical, the next repository-only gate is **Local Training
Asset Attestation V1**. It should verify already-local model/tokenizer assets and an
already-materialized corpus file against:

- the selected launch-plan model/revision/weights identities;
- this binding's `canonical_jsonl_sha256` and byte count; and
- this binding's semantic corpus/T5 dataset identities.

That gate must remain local-only and must not download weights, accept gated terms, or
infer training authorization.

Real training still requires real tournament finalists, real T5-qualified training data,
licensed locally available weights, runtime qualification, and the explicit training
authorization receipt required by Training Readiness V1.
