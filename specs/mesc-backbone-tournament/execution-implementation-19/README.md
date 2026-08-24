# MESC Backbone Tournament — Execution Implementation 19

Status: **DRAFT / NORMATIVE FIXTURE NORMALIZED-SCHEMA VALIDATOR / NO EXECUTION AUTHORITY**

Date: 2026-08-24

## Scope

This bounded implementation slice supplies the second strict output-processing primitive left open after Execution Implementation 16. It implements only the frozen `MESC-BT-NORMALIZED-OUTPUT-V1` schema constraints over caller-supplied parsed fixture objects.

Canonical base:

```text
BASE_MAIN_SHA = 9c934fa779174dce82d5c5a12a389e6ad6147ee1
BASE_MAIN_TREE = 4969f7b6f2b5466ff25373fa16f9596bc4d00f1e
PR_161 = CLOSED_CANONICAL
IMPLEMENTATION_18_NORMATIVE_NORMALIZED_OUTPUT_PARSER = CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-19/README.md
src/medscale/mesc/_bt_normalized_output_schema_v1.py
tests/test_mesc_bt_normalized_output_schema_v1.py
```

No dependency, lockfile, workflow, credential, provider/model, corpus, prompt, scoring-key, runtime, remote-code, execution-result, ranking, activation, or training path is changed.

## Frozen source contract

Canonical schema artifact:

```text
specs/mesc-backbone-tournament/readiness-repair-2-result/normalized-output-schema.json
```

Frozen identity:

```text
NORMALIZED_OUTPUT_SCHEMA_ID = MESC-BT-NORMALIZED-OUTPUT-V1
NORMALIZED_OUTPUT_SCHEMA_SHA256 = 3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4
```

The canonical Repair-2 parser contract separately freezes:

```text
normalized_schema_violation -> SCHEMA_FAILURE
cross_item_violation        -> SCHEMA_FAILURE
```

and defines cross-item evidence-reference membership independently from the normalized JSON Schema.

## Implemented normalized-schema behavior

`validate_normalized_output_fixture(value)` enforces only the normalized schema boundary:

1. top-level value is an object;
2. all six required properties are present;
3. no additional top-level property is present;
4. `answer_state` equals one of the seven frozen enum values;
5. `answer`, `uncertainty`, and `safety_action` are string or null;
6. `evidence_refs` is an array;
7. every evidence reference is a non-empty string;
8. evidence references are unique;
9. `structured_output` is object or null.

A normalized-schema failure raises `NormalizedOutputSchemaError` with the only failure key owned by this stage:

```text
normalized_schema_violation
```

The validator does not repair, coerce, default, delete, rename, or otherwise alter caller data.

## Deliberate stage separation

This slice does **not** verify that `evidence_refs` values occur in the corresponding item payload. That is the frozen cross-item rule:

```text
EVERY_VALUE_MUST_EQUAL_AN_EVIDENCE_ID_PRESENT_IN_ITEM_PAYLOAD
```

and remains a separate future validation primitive. A reference such as `NOT-PRESENT-IN-ANY-ITEM-PAYLOAD` is therefore schema-valid here when it is a non-empty unique string; it must fail only at the later cross-item boundary.

This separation prevents a future implementation from losing the distinction between:

```text
normalized_schema_violation
cross_item_violation
```

while preserving their common tournament outcome class `SCHEMA_FAILURE`.

## Relationship to Implementation 18

Execution Implementation 18 canonically supplies `MESC-BT-PARSER-V1` for caller-supplied fixture bytes. Its parser preserves JSON numeric tokens losslessly through `ExactJsonNumber` and stops before schema validation.

Implementation 19 accepts the resulting parsed-object shape for fixture qualification and does not convert, normalize, serialize, or reinterpret numeric values. In particular, `structured_output` remains schema-constrained only as object-or-null, matching the frozen schema.

No parser-to-schema production composition is established by this PR.

## Deliberate non-claims

This slice does **not**:

- obtain or parse any real model output;
- establish a production parser-to-schema pipeline;
- perform cross-item evidence-reference membership validation;
- read a real corpus item or evidence identifiers;
- read scoring keys or score any item;
- implement or execute the normative scorer;
- implement or execute report validation;
- construct or serialize a prompt;
- access model weights, gated resources, Phi remote code, providers, GPUs, or credentials;
- run inference or generation;
- rank candidates or select a winner;
- execute the Backbone Tournament;
- train or fine-tune a model;
- grant execution activation.

The schema identity is a frozen code constant used for qualification evidence. This does not prove that any future activated executor used these exact source bytes or that a production schema-validator producer has been qualified.

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
FIXTURE_NORMALIZED_SCHEMA_VALIDATION = PERFORMED_IN_TESTS_ONLY
REAL_MODEL_OUTPUT_PARSING = NOT_PERFORMED
REAL_NORMALIZED_SCHEMA_VALIDATION = NOT_PERFORMED
CROSS_ITEM_OUTPUT_VALIDATION = NOT_IMPLEMENTED_BY_THIS_SLICE
REAL_SCORING = NOT_PERFORMED
REAL_REPORT_VALIDATION = NOT_PERFORMED
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
