# MESC Experiment-0 — Foundation Decision Contract

Status: **DESIGN CONTRACT / NON-PROMOTIONAL**

Schema:

```text
MESC-EXPERIMENT-0-DECISION-V1
```

The Experiment-0 decision records foundation-selection research evidence only. It is not a
model-promotion decision, training authorization, checkpoint release, or clinical-use
approval.

## Required fields

```text
schema_version
experiment_config_sha256
candidate_result_sha256s
hard_floor_summary
metric_vector_summary
resource_summary
rights_summary
contamination_summary
sealed_evaluation_receipt_identity
selected_candidate_id
selected_candidate_revision
rationale
limitations
decision_disposition
```

Allowed dispositions:

```text
RETAIN_PREFERRED_CANDIDATE
SELECT_CHALLENGER
INCONCLUSIVE_OR_BLOCKED
INVALID_EXPERIMENT
```

## Candidate-result reconciliation

`candidate_result_sha256s` must be a deterministic unique list that exactly equals the
SHA-256 set of all `MESC-EXPERIMENT-0-CANDIDATE-RESULT-V1` JSON files in the evidence
bundle. The decision cannot omit an unfavorable result or cite a result that is not in the
bundle.

## Hard-floor summary

The decision must expose at least:

```json
{
  "all_mandatory_passed": false,
  "failed_floor_ids": []
}
```

For a positive foundation selection, the only valid state is:

```json
{
  "all_mandatory_passed": true,
  "failed_floor_ids": []
}
```

If any mandatory floor failed, is unresolved, or lacks evidence, the decision must not use a
selection disposition even when aggregate capability metrics are high.

## Selection consistency

Selection fields must be non-null only for `RETAIN_PREFERRED_CANDIDATE` or
`SELECT_CHALLENGER`. They must be null for `INCONCLUSIVE_OR_BLOCKED` and
`INVALID_EXPERIMENT`.

A positive selection additionally requires:

- the exact selected identity exists once in the frozen candidate roster;
- the candidate class is `SELECTABLE_FOUNDATION`, never `REFERENCE_ONLY`;
- the selected candidate has a successfully bound snapshot/load receipt;
- at least one candidate result for that exact selected identity exists;
- `candidate_result_sha256s` exactly reconciles all result files;
- `sealed_evaluation_receipt_identity` is non-null and non-empty;
- `hard_floor_summary.all_mandatory_passed` is `true`;
- `hard_floor_summary.failed_floor_ids` is an empty list.

A selected foundation remains subject to later training authorization and does not inherit
any release/promotion status from this record.
