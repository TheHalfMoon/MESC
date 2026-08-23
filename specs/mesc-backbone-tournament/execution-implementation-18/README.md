# MESC Backbone Tournament — Execution Implementation 18

Status: **DRAFT / NORMATIVE FIXTURE-BYTES OUTPUT PARSER / NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded implementation slice begins the strict output-processing
implementations left open by Execution Implementations 2 and 16. It implements
only the normative `MESC-BT-PARSER-V1` parsing and normalization behavior for
caller-supplied fixture bytes.

Canonical base:

```text
BASE_MAIN_SHA = 8b5e22ddfddf0f1b2f02c0268766cd7a9b0c7c42
BASE_MAIN_TREE = 5dd658c6adb599dc305168b48ca0286b2b40f438
PR_160 = CLOSED_CANONICAL
IMPLEMENTATION_17_FIXTURE_ARTIFACT_MANIFEST_COVERAGE_VERIFIER = CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-18/README.md
src/medscale/mesc/_bt_normalized_output_parser_v1.py
tests/test_mesc_bt_normalized_output_parser_v1.py
```

No dependency, lockfile, workflow, credential, provider/model, corpus, prompt,
scoring-key, runtime, remote-code, execution-result, ranking, activation, or
training path is changed.

## Frozen source contract

The canonical Repair-2 parser artifact is:

```text
PARSER_VERSION = MESC-BT-PARSER-V1
PARSER_CONTRACT_SHA256 =
  9905096b491ddc3bce2b5d668c1f8726f638dde9dba383ac1bb755f1b6b42071
NORMALIZED_OUTPUT_SCHEMA_ID = MESC-BT-NORMALIZED-OUTPUT-V1
NORMALIZED_OUTPUT_SCHEMA_SHA256 =
  3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4
MAX_RAW_OUTPUT_BYTES = 262144
INPUT_ENCODING = UTF-8
DUPLICATE_OBJECT_KEYS = REJECT
MARKDOWN_FENCES = REJECT
SINGLE_JSON_OBJECT_ONLY = true
LEADING_CONTENT = ALLOW_ASCII_WHITESPACE_ONLY
TRAILING_CONTENT = ALLOW_ASCII_WHITESPACE_ONLY
NORMALIZATION = CANONICAL_COMPACT_SORTED_KEY_JSON_UTF8
SEMANTIC_REPAIR = PROHIBITED
```

The frozen failure mapping classifies these parser conditions as
`PARSE_FAILURE`:

```text
invalid_utf8
oversize_output
markdown_fence
invalid_json
duplicate_key
trailing_non_whitespace
```

Normalized-schema and cross-item violations are deliberately separate
`SCHEMA_FAILURE` outcomes and are not parser failures.

## Implemented parser behavior

`parse_normalized_output_fixture(raw_output)` accepts only exact built-in
`bytes`. It then applies the frozen parser boundary in fail-closed order:

1. reject any input larger than exactly 262,144 raw bytes;
2. decode strict UTF-8 with no replacement or repair;
3. consume leading ASCII whitespace only (`SP`, `HTAB`, `CR`, `LF`);
4. reject exterior Markdown code fences rather than stripping them;
5. parse exactly one JSON value with duplicate-object-key rejection at every
   object nesting level;
6. reject non-standard JSON constants such as `NaN` and infinities;
7. reject any top-level value that is not a JSON object;
8. permit only ASCII whitespace after the parsed object and reject any second
   value or other trailing content;
9. normalize the parsed object as compact, lexically sorted-key JSON with
   `ensure_ascii=False`, strict finite JSON values, and UTF-8 encoding;
10. return the parsed object, exact normalized bytes, and SHA-256 of those
    normalized bytes.

The normalized bytes contain no added terminal newline. Non-ASCII Unicode text
is represented directly in UTF-8 rather than being transformed into `\uXXXX`
escapes.

## Markdown-fence boundary

The contract rejects Markdown fences but does not prohibit backtick characters
inside JSON strings. The parser therefore rejects an exterior triple-backtick
prefix or suffix after removing only permitted trailing ASCII whitespace. It
does not scan arbitrary string contents for backticks.

This avoids both semantic repair and an overbroad rule that would reject a valid
JSON string merely because its data contains ````` ``.

## Stage separation

This implementation intentionally stops after normative parser normalization.
It does **not** apply `normalized-output-schema.json` and does not perform the
cross-item checks from `parser-contract.json`.

That separation is required by the frozen pipeline:

```text
parser
normalized_schema_validator
scorer
report_validator
```

Accordingly, a syntactically valid JSON object may pass this parser even when it
would later fail the normalized schema or cross-item evidence checks. Tests
explicitly preserve this boundary so a future change cannot silently convert a
`SCHEMA_FAILURE` into a parser rejection.

## Failure surface

`NormalizedOutputParseError.kind` uses only the frozen parser failure-mapping
keys listed above. The module does not expose raw JSON-decoder, UTF-8-decoder,
normalization, recursion, or numeric-overflow exceptions as protocol outcomes.

Exact input-type checking also prevents `bytearray` or `bytes` subclasses from
silently crossing the parser byte boundary. Type-boundary misuse is a caller
contract error and is not represented as a tournament `PARSE_FAILURE`.

## Deliberate non-claims

This slice does **not**:

- parse any real model output;
- obtain output from a provider, model, file, network, subprocess, or runtime;
- read the canonical parser-contract or schema artifact from disk at runtime;
- prove the activated parser artifact identity or a production parser producer;
- validate a parsed object against `normalized-output-schema.json`;
- perform cross-item evidence-reference validation;
- read any corpus payload or evidence IDs;
- read scoring keys or score any item;
- implement the normative scorer;
- implement or execute report validation;
- construct or serialize any prompt;
- access model weights, gated resources, Phi remote code, providers, or GPUs;
- run inference or generation;
- rank candidates or select a winner;
- execute the Backbone Tournament;
- train or fine-tune a model;
- grant execution activation.

The frozen parser-contract identity is recorded as a code constant and the
behavior is derived from that canonical contract. This does not substitute for
a future activation-time artifact-identity verifier or prove that a live
execution process used these exact source bytes.

## Relationship to adjacent slices

Execution Implementation 16 binds the frozen output-contract identities and the
canonical successful-output processing order, but explicitly does not implement
the normative parser, schema validator, scorer, or report validator.

Implementation 18 supplies only the first of those behavioral primitives. The
normalized-schema validator, cross-item validation, normative scoring,
report-validation implementation, production producer qualification, and live
pipeline integration remain separate future work.

Implementation 17 validates only injected coverage declarations for a future
execution artifact manifest. It does not create or qualify a live output
pipeline and is not weakened or expanded by this slice.

## Qualification rule

Keep any PR for this slice Draft until one unchanged exact head has:

1. stable canonical base and exact three-file scope;
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
NORMALIZED_SCHEMA_VALIDATION = NOT_IMPLEMENTED_BY_THIS_SLICE
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
```
