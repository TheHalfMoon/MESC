# MESC Backbone Tournament — Execution Implementation 19

Status: **DRAFT / NORMATIVE NORMALIZED-OUTPUT SCHEMA VALIDATOR / CROSS-ITEM EVIDENCE VALIDATOR / NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded implementation slice implements the `MESC-BT-NORMALIZED-OUTPUT-V1` schema validator for caller-supplied parsed fixture objects, as well as the cross-item evidence-reference validator that ensures every evidence_refs value equals an evidence ID present in the item payload.

Canonical base:

```text
BASE_MAIN_SHA = 9c934fa779174dce82d5c5a12a389e6ad6147ee1
BASE_MAIN_TREE = 4969f7b6f2b5466ff25373fa16f9596bc4d00f1e
PR_161 = CLOSED_CANONICAL
IMPLEMENTATION_18_NORMATIVE_NORMALIZED_OUTPUT_PARSER = CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly four files:

```text
specs/mesc-backbone-tournament/execution-implementation-19/README.md
src/medscale/mesc/_bt_normalized_output_schema_v1.py
src/medscale/mesc/_bt_normalized_output_cross_item_validator_v1.py
tests/test_mesc_bt_normalized_output_cross_item_validator_v1.py
```

No dependency, lockfile, workflow, credential, provider/model, corpus, prompt,
scoring-key, runtime, remote-code, execution-result, ranking, activation, or
training path is changed.

## Frozen source contract

The canonical Repair-2 normalized output schema artifact is:

```text
NORMALIZED_OUTPUT_SCHEMA_ID = MESC-BT-NORMALIZED-OUTPUT-V1
NORMALIZED_OUTPUT_SCHEMA_SHA256 =
  3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4
```

The canonical Repair-2 parser contract classifies these as `SCHEMA_FAILURE`:

```text
normalized_schema_violation
cross_item_violation
```

Where:
- `normalized_schema_violation`: Violation of the normalized-output-schema.json constraints
- `cross_item_violation`: EVERY evidence_refs VALUE MUST EQUAL AN EVIDENCE ID PRESENT IN ITEM PAYLOAD

## Implemented schema validator behavior

`validate_normalized_output_fixture(value)` accepts a parsed fixture object and applies the frozen normalized schema constraints in fail-closed order:

1. reject if not an exact built-in dict;
2. reject if keys are not exact built-in strings;
3. reject if the set of keys does not exactly match the six required fields;
4. reject if answer_state is not an exact string from the frozen enum;
5. reject if answer is not an exact string or null;
6. reject if evidence_refs is not an exact built-in list;
7. reject if any evidence_refs element is not an exact string or has length < 1;
8. reject if evidence_refs contains duplicate elements;
9. reject if uncertainty is not an exact string or null;
10. reject if safety_action is not an exact string or null;
11. reject if structured_output is not an exact object or null.

This implementation intentionally stops before cross-item evidence-reference validation.
That is a separate `SCHEMA_FAILURE` stage in the frozen contract and must not be
silently collapsed into schema validation.

## Implemented cross-item validator behavior

`validate_cross_item_evidence_refs(value, item_payload_ids)` accepts a parsed fixture
object and a collection of item payload IDs from the corpus, and validates that
every evidence_refs value equals an evidence ID present in the item payload:

1. reject if value["evidence_refs"] is not a list (should already be caught by schema validation);
2. reject if any evidence_refs element is not present in the item_payload_ids collection;
3. reject if any evidence_refs element is not an exact string (should already be caught by schema validation).

The item_payload_ids collection is expected to be a frozenset of strings representing
all evidence IDs present in the current item's payload from the corpus.

## Failure surface

Both validators use fail-closed ValueError subclasses with specific kinds:

- `NormalizedOutputSchemaError.kind == "normalized_schema_violation"`
- `CrossItemEvidenceError.kind == "cross_item_violation"`

Each error includes a JSON Path indicating the location of the violation.

## Stage separation

This implementation correctly separates the frozen pipeline stages:

```text
parser
normalized_schema_validator
cross_item_evidence_validator
scorer
report_validator
```

Accordingly, a parsed object may pass the parser and normalized schema validation
but fail cross-item evidence validation if it references non-existent evidence IDs.

## Deliberate non-claims

This slice does **not**:

- parse any real model output;
- obtain output from a provider, model, file, network, subprocess, or runtime;
- read the canonical parser-contract or schema artifact from disk at runtime;
- prove the activated parser artifact identity or a production parser producer;
- implement the normative scorer;
- implement or execute report validation;
- construct or serialize any prompt;
- access model weights, gated resources, Phi remote code, providers, or GPUs;
- run inference or generation;
- rank candidates or select a winner;
- execute the Backbone Tournament;
- train or fine-tune a model;
- grant execution activation.

The frozen identities are recorded as code constants and the behavior is derived
from those canonical contracts. This does not substitute for a future activation-
time artifact-identity verifier or prove that a live execution process used these
exact source bytes.

## Qualification rule

Keep any PR for this slice Draft until one unchanged exact head has:

1. stable canonical base and exact four-file scope;
2. exact-head CI PASS;
3. exact-head CodeQL PASS;
4. fresh exact-head internal technical/security/governance review PASS;
5. fresh independent external exact-head review with no blocker;
6. zero unresolved blocking review threads.

Any head mutation burns prior head-specific evidence. Do not mark Ready or merge
until every exact-head gate is re-proven.

## Hard boundary

```text
FIXTURE_OUTPUT_PARSING = PERFORMED_IN_TESTS_ONLY
REAL_MODEL_OUTPUT_PARSING = NOT_PERFORMED
NORMALIZED_SCHEMA_VALIDATION = PERFORMED_IN_TESTS_ONLY
CROSS_ITEM_OUTPUT_VALIDATION = PERFORMED_IN_TESTS_ONLY
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
```
