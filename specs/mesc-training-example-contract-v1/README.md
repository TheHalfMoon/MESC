# MESC Training Example Contract V1

Status: **IMPLEMENTATION / SUPERVISED-DATA CONTRACT / NO TRAINING EXECUTION**

Canonical base:

```text
BASE_MAIN_SHA = 4d893a9e4e25948bc898e07f59ab1e29fea43cea
PR_182 = CLOSED_CANONICAL
T5_DATASET_QUALIFICATION = CANONICAL
TRAINING_EXECUTION = NOT_PERFORMED
```

## Purpose

T5 now proves which exact record set is eligible to become MESC training data, but the
repository previously had no canonical supervised-training example format. A trainer
without that boundary would have to invent parsing, target, abstention, provenance, and
review semantics at execution time.

This package closes that gap. It turns the MESC frontier-program data requirements into
one deterministic, auditable supervised-training record and one trainer-neutral corpus.

The package does not train a model and does not access any model, tokenizer, provider,
credential, external dataset, GPU, or network resource.

## Scope

Exactly three paths are introduced:

```text
specs/mesc-training-example-contract-v1/README.md
src/medscale/mesc/_training_example_contract_v1.py
tests/test_mesc_training_example_contract_v1.py
```

No dependency, workflow, CLI, model registry, readiness schema, launch-plan schema, or
existing dataset-builder contract is modified.

## Program-rule boundary

Executable MESC training data remains restricted to Program Rule R2 inputs:

```text
synthetic
hand_authored_fixture
```

No external clinical record, PHI-bearing record, or unspecified origin can construct as
a valid `TrainingExampleV1`.

Synthetic examples require an exact `synthetic_provenance_sha256`. Hand-authored
fixtures must not claim synthetic provenance.

## Canonical example fields

`TrainingExampleV1` records the frontier-program data fields required for traceability
and trainable uncertainty:

- `example_id`;
- `training_record_id`;
- `source_id`;
- `source_revision`;
- `source_license`;
- `source_sha256`;
- `source_timestamp`;
- R2 `origin`;
- optional/required synthetic provenance according to origin;
- `evidence_refs`;
- `task_type`;
- `specialty`;
- `patient_population`;
- `language`;
- supervised training stage;
- conversational prompt;
- assistant completion target;
- uncertainty class;
- abstention target;
- contradiction state;
- verification state;
- clinician-review state; and
- contamination state.

Every complete record has a deterministic `example_sha256`.

### T5 membership identity

`training_record_id` is not a second provenance field. It is the exact stable record id
from the T5-qualified `SplitAssignmentFreeze.train` membership that authorized this
example's source record for training.

`source_id` remains the provenance/source identity and may differ from
`training_record_id`.

Multiple supervised examples may be derived from one qualified training record. The
corpus therefore permits repeated `training_record_id` values while still requiring
unique `example_id` values. `TrainingCorpusV1.training_record_ids` exposes the unique,
sorted T5 record-id set represented by the corpus. The next binding gate must hash this
set using the same T5 record-id identity algorithm and require exact equality with the
qualified `training_record_ids_sha256`.

No missing T5 record may be inferred from source metadata and no extra record may be
admitted merely because its provenance is valid.

### Immutable container boundary

The dataclasses are frozen, so nested containers that participate in scientific identity
must also be immutable at runtime rather than merely annotated as immutable.

V1 therefore requires:

- `evidence_refs` to be an actual tuple;
- `prompt` to be an actual tuple of `TrainingMessage` values; and
- direct `TrainingCorpusV1.examples` construction to use an actual tuple containing only
  `TrainingExampleV1` values.

`build_training_corpus(...)` may accept a normal sequence such as a list, but validates
all runtime members before sorting and freezes the result into a tuple. Invalid containers
or forged members fail with `TrainingExampleContractError` instead of leaking incidental
`AttributeError`/mutation behavior.

## Supervised stages

V1 intentionally covers the supervised generator stages that precede preference or RL
work:

```text
evidence_sft
clinical_reasoning_sft
uncertainty_sft
safety_sft
```

Preference optimization, verifier training, and verifiable RL require separate future
contracts rather than overloading the SFT record.

## Conversational target contract

A prompt is an ordered tuple of normalized `TrainingMessage` values.

Rules:

- prompt is non-empty;
- at most one `system` message is allowed and it must be first;
- prompt must end with `user`;
- completion is exactly one `assistant` message;
- message content must be non-empty and contain no NUL byte.

This produces a deterministic conversational prompt-completion projection suitable for
a later TRL `SFTTrainer` adapter. The canonical MESC record remains richer than the
trainer projection; provenance and review metadata are never discarded from the source
corpus merely because the trainer consumes only prompt/completion fields.

## Abstention targets

The exact V1 supervised targets are:

```text
ANSWER_SUPPORTED
ANSWER_WITH_UNCERTAINTY
REQUEST_MORE_INFORMATION
VERIFY_EVIDENCE
ABSTAIN_INSUFFICIENT_EVIDENCE
ABSTAIN_CONFLICTED_EVIDENCE
ESCALATE_SAFETY
```

V1 enforces hard consistency for targets whose state is unambiguous. For example:

- `ANSWER_SUPPORTED` requires `SUPPORTED` uncertainty and no contradiction;
- `ABSTAIN_INSUFFICIENT_EVIDENCE` requires `INSUFFICIENT`;
- `ABSTAIN_CONFLICTED_EVIDENCE` requires `CONFLICTED` plus contradiction present;
- `ESCALATE_SAFETY` requires `SAFETY_CRITICAL`;
- `REQUEST_MORE_INFORMATION` requires partial or insufficient evidence; and
- `ANSWER_WITH_UNCERTAINTY` requires partial or stale evidence.

`VERIFY_EVIDENCE` remains intentionally usable across several uncertainty states because
verification can be required for stale, contradictory, partial, or otherwise suspect
evidence.

## Corpus admission

Constructing an individual record is not enough to make it trainable.

`eligible_for_sft` is true only when:

```text
VERIFICATION_STATE = VERIFIED
CLINICIAN_REVIEW_STATE = REVIEWED_PASS
CONTAMINATION_STATE = CLEAR
```

`TrainingCorpusV1` refuses any record that does not satisfy all three conditions.

The corpus also requires:

- at least one example;
- unique stable `example_id` values; and
- canonical ordering by `example_id`.

`build_training_corpus(...)` supplies that canonical ordering. This means input ordering
cannot silently change the content identity.

## Content addressing

`TrainingCorpusV1.corpus_sha256` covers the full auditable records, not only the prompt
and target text. A change to T5 record identity, license, evidence references, source
identity, provenance, review state, contamination state, uncertainty label, abstention
target, prompt, or completion therefore changes the corpus identity.

`canonical_jsonl()` emits sorted, canonical, LF-terminated full-fidelity JSONL.

This corpus identity is distinct from the T5 dataset identity. A later materialization
gate must explicitly bind the canonical SFT corpus to the already-qualified T5 record
set; neither identity may be substituted for the other.

## Trainer projection

`to_trl_prompt_completion()` and `TrainingCorpusV1.to_trl_records()` expose only:

```text
prompt:      conversational messages
completion:  one assistant message
```

The later trainer adapter must pass an already-instantiated/local model and an in-memory
or local dataset representation. It must not turn a model identifier or dataset name
into an implicit Hub download.

## Security and governance

This package performs no:

- dataset download or external data read;
- provider or credential access;
- license or gated-term acceptance;
- model-weight access or retrieval;
- tokenizer/model construction;
- remote-code loading;
- inference or generation;
- Backbone Tournament execution;
- trainer import;
- GPU execution;
- fine-tuning or training.

Tests use hand-authored/synthetic contract objects only.

## Next gates

After this contract is canonical, repository readiness still requires:

1. **training corpus materialization/binding** — prove that the local canonical JSONL
   represents exactly the T5-qualified `training_record_id` membership, bind both the
   T5 training-dataset identity and SFT corpus identity, and freeze the raw file digest;
2. **fail-closed training executor** — consume the canonical launch plan and local
   attested assets, materialize the runtime `ExperimentManifest`, and call only an
   explicitly injected trainer backend; and
3. **optional Hugging Face SFT backend** — local-files-only Transformers + TRL/PEFT,
   with no implicit Hub access and QLoRA support isolated behind an optional dependency.

Real training still requires real tournament finalists, qualified real training data,
locally available licensed model weights, runtime qualification, and the explicit
training-authorization receipt already required by `MESC-TRAINING-READINESS-V1`.
