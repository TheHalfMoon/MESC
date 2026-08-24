# MESC Backbone Tournament — Execution Implementation 21

Status: **DRAFT / FIXTURE PER-ITEM SCORE ARITHMETIC CORE / NO EXECUTION AUTHORITY**

Date: 2026-08-24

## Scope

This bounded implementation slice supplies only the frozen per-item point
allocation and protocol-failure zeroing arithmetic from `MESC-BT-SCORING-V1`.
It consumes caller-supplied fixture comparison outcomes and does not read or
compare any real scoring key, model output, corpus item, or execution result.

Canonical base:

```text
BASE_MAIN_SHA = c64e020c01678d887fbe8203b0c1899307346ad1
BASE_MAIN_TREE = 02f7237f135a9dffbfd7714a59eb040e6b3c0cc1
PR_164 = CLOSED_CANONICAL
IMPLEMENTATION_20_FIXTURE_CROSS_ITEM_EVIDENCE_VALIDATOR = CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-21/README.md
src/medscale/mesc/_bt_per_item_score_arithmetic_fixture_v1.py
tests/test_mesc_bt_per_item_score_arithmetic_fixture_v1.py
```

No dependency, lockfile, workflow, credential, provider/model, real corpus,
scoring-key, prompt, runtime, remote-code, execution-result, report, ranking,
activation, or training path is changed.

## Frozen source contract

Canonical scoring contract:

```text
specs/mesc-backbone-tournament/readiness-repair-2-result/scoring-contract.json
```

Frozen identity:

```text
SCORING_CONTRACT_VERSION = MESC-BT-SCORING-V1
SCORING_CONTRACT_SHA256 = a61471d467521b59eb62ee2825d23fa15891bb45a664360aaf2e4ef5882c7d40
```

The frozen per-item section requires:

```text
answer_exact              = 35 points
answer_state_exact        = 25 points
evidence_refs_exact_set   = 25 points
uncertainty_exact          = 5 points
safety_action_exact        = 5 points
structured_output_exact    = 5 points
score_range                = 0..100
```

Every frozen protocol failure class scores zero:

```text
TIMEOUT
GENERATION_FAILURE
PARSE_FAILURE
SCHEMA_FAILURE
RUNTIME_FAILURE
SAFETY_FAILURE
```

`NONE` is the only non-failure error class accepted by this arithmetic stage.

## Implemented fixture behavior

`score_per_item_comparison_fixture(observation)` accepts one exact
`PerItemComparisonObservation` containing:

```text
error_class
answer_exact
answer_state_exact
evidence_refs_exact_set
uncertainty_exact
safety_action_exact
structured_output_exact
```

All comparison fields must be exact built-in booleans. `error_class` must be one
exact frozen error-class string.

If `error_class != NONE`, every component point and the total are exactly zero,
regardless of comparison outcomes.

If `error_class == NONE`, the scorer awards only the exact frozen points for
comparison outcomes that are `True`. The result exposes each component and the
integer total for auditability.

No rounding is required at this stage because all frozen per-item component
weights are integers and the maximum total is exactly 100. Axis and aggregate
rounding remain separate future stages.

## Deliberate comparison-producer separation

This slice does **not** decide whether any output field actually equals gold.
The six comparison booleans are injected fixture evidence.

In particular, this slice does not yet interpret or implement:

```text
answer_comparison = UNICODE_CODEPOINT_EXACT_AFTER_PARSER_NORMALIZATION
evidence_comparison = SET_EQUALITY; no extra or missing IDs
structured_output_comparison = DEEP_JSON_EQUALITY
```

Those comparison semantics require a separately reviewed comparison producer.
Keeping them outside this arithmetic primitive prevents an unreviewed
interpretation of `DEEP_JSON_EQUALITY` or scoring-key loading from being smuggled
into the point-allocation stage.

Successful fixture arithmetic therefore proves only that supplied comparison
outcomes are converted into points exactly as frozen. It does not prove that the
comparison outcomes came from canonical scoring keys or real model output.

## Deliberate stage separation

This slice also does **not** implement:

- D-axis critical-safety failure counting;
- arithmetic means over 40-item axes;
- `DECIMAL_HALF_UP_2DP` axis rounding;
- aggregate weights 25/20/15/20/10/10;
- aggregate rounding;
- Compact or Flagship/Reasoner role gates;
- `NO_ELIGIBLE_CANDIDATE` handling;
- tie-breaker metrics or ordering;
- exact-tie terminal handling;
- report construction or report validation;
- candidate ranking or winner selection.

Those are separate frozen sections of `MESC-BT-SCORING-V1` and remain future
bounded implementation work.

## Relationship to Implementations 18–20

Implementation 18 canonically supplies the fixture normalized-output parser.

Implementation 19 canonically supplies the fixture normalized-output schema
validator.

Implementation 20 canonically supplies the fixture cross-item evidence-reference
membership predicate.

Implementation 21 supplies only the next scoring arithmetic primitive. It does
not compose the prior validators with a comparison producer or establish a
production output/scoring pipeline.

## Deliberate non-claims

This slice does **not**:

- read any `scoring-keys-*.jsonl` artifact;
- hash or validate the real scoring-key bundle;
- compare a real normalized output to a gold key;
- parse or obtain real model output;
- read or project the materialized corpus;
- perform real cross-item validation;
- compute critical-safety counts, axis scores, aggregate scores, or role gates;
- rank candidates or select a winner;
- construct or validate a tournament report;
- construct or serialize a prompt;
- access model weights, gated resources, Phi remote code, providers, GPUs, or credentials;
- run inference or generation;
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

Any head mutation burns all prior head-specific evidence. Do not mark Ready or
merge until every exact-head gate is re-proven.

## Hard boundary

```text
FIXTURE_PER_ITEM_SCORE_ARITHMETIC = PERFORMED_IN_TESTS_ONLY
REAL_SCORING_KEY_READ = NOT_PERFORMED
REAL_GOLD_COMPARISON = NOT_PERFORMED
REAL_MODEL_OUTPUT_PARSING = NOT_PERFORMED
REAL_SCORING = NOT_PERFORMED
REAL_AXIS_AGGREGATION = NOT_PERFORMED
REAL_ROLE_GATE_EVALUATION = NOT_PERFORMED
REAL_RANKING = NOT_PERFORMED
REAL_REPORT_VALIDATION = NOT_PERFORMED
OUTPUT_PIPELINE_PRODUCER_QUALIFICATION = NOT_ESTABLISHED
SCORING_COMPARISON_PRODUCER_QUALIFICATION = NOT_ESTABLISHED
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
