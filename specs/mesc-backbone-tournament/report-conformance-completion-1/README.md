# MESC Backbone Tournament — Report Conformance Completion Batch 1

Status: **DRAFT / FIXTURE-ONLY REPORT CONFORMANCE / NO LIVE EXECUTION AUTHORITY**

Date: 2026-08-24

## Canonical base

```text
BASE_MAIN_SHA = 020433b9c3167254d8c49cef001d028b36217821
BASE_MAIN_TREE = b5f283dcce6628ab2e5bdc678d06261db57ab6f4
PR_167 = CLOSED_CANONICAL
TOURNAMENT_ENGINE_COMPLETION_BATCH_1 = CLOSED_CANONICAL
```

Frozen contract identities:

```text
REPORT_SCHEMA_VERSION = MESC-BT-REPORT-V1
REPORT_SCHEMA_SHA256 = cb3fc506b41cc6236959bb4a89bce249db13c99aeb0c7178ff233f6de44e026d

REPORT_VALIDATION_CONTRACT_VERSION = MESC-BT-REPORT-VALIDATION-V1
REPORT_VALIDATION_CONTRACT_SHA256 = c68fcac507e4ebc164632370d2392631b9fec9c388369eb5b8bfa495e5877c1a

SCORING_CONTRACT_VERSION = MESC-BT-SCORING-V1
SCORING_CONTRACT_SHA256 = a61471d467521b59eb62ee2825d23fa15891bb45a664360aaf2e4ef5882c7d40
```

## Purpose

This batch closes the remaining deterministic fixture-side report-validation gap after
Tournament Engine Completion Batch 1. It does not create or consume a real tournament
report. It validates only caller-supplied normalized fixture objects and injected
fixture evidence.

The implementation is split into two layers:

1. `_bt_report_schema_fixture_v1.py`
   - mirrors the frozen `MESC-BT-REPORT-V1` shape and schema-level constraints;
   - rejects additional properties, malformed frozen identities, invalid candidate or
     role-result variants, invalid item IDs, and out-of-range values;
   - represents non-integer normalized JSON numbers as `Decimal` and rejects float so
     later threshold/tie logic cannot inherit binary floating-point ambiguity.
2. `_bt_report_conformance_fixture_v1.py`
   - applies the frozen semantic validation order available from fixture evidence;
   - verifies injected activation-binding facts and pre-execution corpus-audit PASS facts;
   - validates candidate identity, terminal accounting, exclusions, and canonical item
     partition evidence;
   - reuses the canonical tournament scoring engine to recompute aggregate scores,
     Compact/Flagship gates, and role results;
   - composes the report validator with the already-canonical parser -> normalized schema
     -> scorer -> report-validator pipeline observation contract.

No new dependency is admitted.

## Validation order

The implementation preserves the frozen report-validation order:

```text
JSON_SCHEMA
FROZEN_STATIC_BINDINGS
ACTIVATION_BINDINGS
CORPUS_AUDITS
CANONICAL_ITEM_MEMBERSHIP
CANDIDATE_IDENTITY
ACCOUNTING
GATE_RECOMPUTATION
ROLE_SELECTION
```

### JSON schema

The shape validator enforces the exact frozen object fields for:

- top-level report;
- candidate reports;
- six axis scores;
- terminal error counters;
- exclusions;
- candidate negative results;
- operational metrics;
- top-level negative results;
- Compact and Flagship/Reasoner role results.

It also enforces the schema-level frozen constants and exact candidate/revision enum
sets.

### Frozen static bindings

The report fixture must contain the frozen identities already embedded in the report
schema, including:

```text
MESC-BT-PROTOCOL-V1
protocol-config SHA-256
prompt-bundle SHA-256
system-prompt SHA-256
prompt-protocol SHA-256
corpus-spec SHA-256
materialized corpus logical + gzip SHA-256
canonical item count = 240
corpus-manifest SHA-256
scoring-keys SHA-256
normalized-output-schema SHA-256
parser-contract SHA-256
scoring-contract SHA-256
report-validation-contract SHA-256
```

This is identity checking only. The implementation does not open the bound corpus,
scoring keys, prompt bundle, or any other real artifact.

### Activation bindings

`ActivationBindingFixture` is deliberately named as fixture evidence. A caller must
inject:

- MESC execution commit SHA;
- MESC execution tree SHA;
- protocol-config SHA-256;
- scoring-contract SHA-256;
- report-schema SHA-256;
- artifact-manifest SHA-256;
- 2..4 admitted canonical candidate ID/revision pairs;
- exact boolean fixture evidence that those bindings passed.

The validator compares report fields against that injected fixture. This does **not**
activate the tournament and does not prove a real founder authorization package exists.

### Corpus audits

`CorpusAuditFixture` requires exact boolean fixture PASS evidence for:

- R2 provenance audit;
- corpus/spec conformance audit;
- audit-artifact binding before prompt serialization.

These booleans are test fixtures only. The validator does not read, decompress, hash,
or inspect the real 240-item corpus.

### Canonical terminal disposition and accounting

For each reported candidate, `CandidateTerminalDispositionFixture` injects a complete
240-item terminal partition:

```text
completed_item_ids
failed_items(item_id, terminal_error_class)
```

The validator requires:

- the completed and failed sets to be disjoint;
- their union to equal exactly `BT-A-001..040` through `BT-F-001..040`;
- no duplicate IDs;
- report `items_completed` to equal injected completed count;
- `items_completed + errors.total == 240`;
- `errors.total` to equal the six typed error counters;
- exclusions to equal the injected failed item IDs and terminal classes exactly;
- each typed error count to equal the matching failed-item/exclusion count;
- no completed ID to appear in exclusions.

This is the explicit producer boundary needed to validate the frozen
`exclusion_identity` rule without reading real execution output.

### Gate recomputation

Every candidate report is transformed into the canonical
`CandidateSelectionFixture`. The existing scoring engine then revalidates:

- candidate ID/revision mapping;
- all six axis scores as normalized `Decimal` values;
- weighted aggregate recomputation;
- Compact gate recomputation;
- Flagship/Reasoner gate recomputation;
- non-negative finite peak VRAM and median latency inputs needed by tie-breaking.

The report validator does not duplicate scoring arithmetic.

### Role selection recomputation

The existing canonical role-selection engine is called for both roles. Reported results
must match the recomputed outcome, candidate, and reason exactly. For an exact tie,
`tied_candidate_ids` is compared as the exact recomputed candidate set because the
frozen report contract requires set membership, not an additional post-output ordering
rule.

## End-to-end fixture composition

`validate_fixture_output_pipeline_to_report()` composes:

```text
canonical output-contract identity evidence
  -> canonical pipeline-order/retry observation verification
  -> report schema validation
  -> activation/corpus fixture evidence
  -> terminal accounting
  -> scoring/gate recomputation
  -> role-result recomputation
```

The output-pipeline observation remains the canonical evidence-only contract introduced
before real execution. This function does not deserialize a real model output or produce
a real tournament result.

## Tests

The batch tests:

- one fully conformant two-candidate report;
- end-to-end fixture composition;
- exact top-level/additional-property rejection;
- float rejection at the normalized report-number boundary;
- noncanonical item-ID rejection;
- frozen identity mismatch;
- invalid role-result variants;
- unproven activation fixture;
- failed corpus-audit fixture;
- activation roster subset enforcement;
- candidate revision mismatch;
- one exact terminal TIMEOUT accounting/exclusion case;
- exclusion identity mismatch;
- incomplete 240-item terminal partition;
- gate recomputation mismatch;
- role-result recomputation mismatch.

## Execution-readiness matrix after this batch

| Obligation | Safe deterministic code after this batch | Real/live status |
| --- | --- | --- |
| Parser contract | Canonical | Live output not authorized |
| Normalized-output schema | Canonical | Live output not authorized |
| Cross-item evidence membership | Canonical fixture predicate | Real corpus producer not qualified |
| Per-item scoring | Canonical | Real scoring-key read not authorized |
| Axis/aggregate/gates | Canonical | Real candidate scoring not authorized |
| Role selection | Canonical fixture logic | Real ranking/winner selection not authorized |
| Report schema | Implemented by this batch if qualified | Real report artifact not produced |
| Report semantic conformance | Implemented by this batch if qualified | Real activation/audit evidence absent |
| Pipeline composition | Fixture evidence composition only | Real pipeline execution not authorized |
| Artifact manifest | Identity field validated only | Real run artifact manifest absent |
| Candidate runtime | No change | Model retrieval/inference not authorized |
| Training/fine-tuning | No change | Not authorized |

## Deliberate non-claims

This batch does **not**:

- read any real scoring-key payload;
- read or decompress the materialized tournament corpus;
- inspect real corpus item content;
- read or validate a real execution report file;
- read a real activation package;
- establish founder execution authority;
- validate real corpus-audit artifacts;
- access model providers, weights, credentials, or gated terms;
- construct or serialize a real model prompt;
- execute inference or generation;
- score real model output;
- rank real candidates;
- select a real winner;
- create a real execution artifact manifest;
- execute the Backbone Tournament;
- train or fine-tune a model.

## Hard boundary

```text
REAL_REPORT_READ = NOT_PERFORMED
REAL_REPORT_VALIDATION = NOT_PERFORMED
REAL_ACTIVATION_PACKAGE_READ = NOT_PERFORMED
REAL_CORPUS_AUDIT_READ = NOT_PERFORMED
REAL_SCORING_KEY_READ = NOT_PERFORMED
REAL_CORPUS_READ = NOT_PERFORMED
REAL_MODEL_OUTPUT_PARSING = NOT_PERFORMED
REAL_SCORING = NOT_PERFORMED
REAL_RANKING = NOT_PERFORMED
REAL_WINNER_SELECTION = NOT_PERFORMED
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
FINE_TUNING = NOT_AUTHORIZED
```

## Qualification

Keep the PR Draft until one unchanged exact head has:

1. `behind=0` against canonical main;
2. exact changed-file reconciliation;
3. CI PASS on Python 3.11 and 3.12;
4. CodeQL PASS;
5. fresh exact-head technical/security/governance review;
6. fresh independent exact-head review when available;
7. zero unresolved technical/security/contract/governance blocker threads.

Any head mutation burns head-specific qualification evidence.
