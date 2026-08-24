# MESC Backbone Tournament — Execution Implementation 20

Status: **DRAFT / FIXTURE CROSS-ITEM EVIDENCE-REFERENCE VALIDATOR / NO EXECUTION AUTHORITY**

Date: 2026-08-24

## Scope

This bounded implementation slice supplies the cross-item evidence-reference membership primitive frozen by `MESC-BT-PARSER-V1`. It operates only on caller-supplied fixture normalized output and a caller-supplied tuple of evidence IDs representing the corresponding fixture item payload.

Canonical base:

```text
BASE_MAIN_SHA = 66b0afeb0f5e9ac48a73488acd1bf32835c419bb
BASE_MAIN_TREE = eca280a5a5a97eace126a9fc41344b8d713722a1
PR_163 = CLOSED_CANONICAL
IMPLEMENTATION_19_NORMATIVE_NORMALIZED_OUTPUT_SCHEMA_VALIDATOR = CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-20/README.md
src/medscale/mesc/_bt_cross_item_evidence_validator_v1.py
tests/test_mesc_bt_cross_item_evidence_validator_v1.py
```

No dependency, lockfile, workflow, credential, provider/model, real corpus, prompt, scoring-key, runtime, remote-code, execution-result, ranking, activation, or training path is changed.

## Frozen source contract

Canonical parser contract:

```text
specs/mesc-backbone-tournament/readiness-repair-2-result/parser-contract.json
```

Frozen identity:

```text
PARSER_CONTRACT_VERSION = MESC-BT-PARSER-V1
PARSER_CONTRACT_SHA256 = 9905096b491ddc3bce2b5d668c1f8726f638dde9dba383ac1bb755f1b6b42071
```

Frozen cross-item rule:

```text
EVERY_VALUE_MUST_EQUAL_AN_EVIDENCE_ID_PRESENT_IN_ITEM_PAYLOAD
cross_item_violation -> SCHEMA_FAILURE
```

## Implemented membership behavior

`validate_cross_item_evidence_refs_fixture(normalized_output, item_payload_evidence_ids)`:

1. snapshots the caller-supplied normalized-output `evidence_refs` list;
2. snapshots the caller-supplied fixture payload evidence-ID tuple;
3. requires every output reference to equal one injected payload evidence ID exactly;
4. raises `CrossItemEvidenceValidationError` with `kind = cross_item_violation` and the exact offending output path when membership fails.

Membership is exact and case-sensitive.

An empty output `evidence_refs` list satisfies this membership rule. The payload may contain additional evidence IDs that the output did not cite.

## Deliberate rule separation

This validator implements **subset membership only**:

```text
output evidence_refs ⊆ injected item-payload evidence IDs
```

It deliberately does **not** require set equality. The frozen scoring contract separately defines scoring-time evidence comparison as:

```text
SET_EQUALITY; no extra or missing IDs
```

Adding set equality here would invent a stricter cross-item validity rule and collapse scoring semantics into schema validation.

The validator also deliberately does not re-run normalized-output schema validation. Duplicate output references, invalid answer-state fields, or unrelated extra fields belong to the preceding normalized-schema stage. Fixture caller-shape misuse is raised as `TypeError`, not misclassified as a tournament `cross_item_violation`.

## Producer boundary

The `item_payload_evidence_ids` argument is injected fixture evidence. This slice does not read `materialized-corpus.jsonl.gz`, does not inspect real corpus payloads, and does not establish a producer that extracts authoritative evidence IDs from an activated corpus item.

Therefore successful fixture qualification proves only the membership predicate over supplied values. It does **not** prove:

- that supplied IDs originated from the canonical corpus payload;
- corpus identity or conformance;
- payload extraction correctness;
- prompt projection correctness;
- production cross-item validator wiring.

Those remain separate producer/integration obligations.

## Relationship to Implementations 18 and 19

Implementation 18 canonically parses and normalizes caller-supplied fixture bytes.

Implementation 19 canonically validates the frozen normalized-output JSON Schema over caller-supplied parsed fixture objects.

Implementation 20 supplies only the next cross-item membership predicate. It does not compose these primitives into a production output pipeline and does not qualify any live producer.

## Deliberate non-claims

This slice does **not**:

- read the materialized corpus or any real corpus item;
- extract evidence IDs from a real payload;
- obtain or parse real model output;
- perform real normalized-schema validation;
- read scoring keys;
- score any real item;
- implement aggregate scoring or role gates;
- implement or execute report validation;
- construct or serialize prompts;
- access model weights, gated resources, Phi remote code, providers, GPUs, or credentials;
- run inference or generation;
- rank candidates or select a winner;
- execute the Backbone Tournament;
- train or fine-tune a model;
- grant execution activation.

## Qualification rule

Keep any PR for this slice Draft until one unchanged exact head has:

1. stable canonical base and exact three-file scope;
2. exact-head CI PASS;
3. exact-head CodeQL PASS;
4. fresh exact-head internal technical/security/governance review PASS;
5. fresh independent external exact-head review with no blocker when available;
6. zero unresolved blocking review threads.

Any head mutation burns all prior head-specific evidence. Do not mark Ready or merge until every exact-head gate is re-proven.

## Hard boundary

```text
FIXTURE_CROSS_ITEM_EVIDENCE_MEMBERSHIP = PERFORMED_IN_TESTS_ONLY
REAL_CORPUS_READ = NOT_PERFORMED
REAL_CORPUS_EVIDENCE_ID_EXTRACTION = NOT_PERFORMED
REAL_MODEL_OUTPUT_PARSING = NOT_PERFORMED
REAL_NORMALIZED_SCHEMA_VALIDATION = NOT_PERFORMED
REAL_CROSS_ITEM_OUTPUT_VALIDATION = NOT_PERFORMED
REAL_SCORING = NOT_PERFORMED
REAL_REPORT_VALIDATION = NOT_PERFORMED
CORPUS_PROJECTION_PRODUCER_QUALIFICATION = NOT_ESTABLISHED
OUTPUT_PIPELINE_PRODUCER_QUALIFICATION = NOT_ESTABLISHED

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
