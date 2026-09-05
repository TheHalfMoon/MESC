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

Selection fields must be non-null only for `RETAIN_PREFERRED_CANDIDATE` or
`SELECT_CHALLENGER`. They must be null for `INCONCLUSIVE_OR_BLOCKED` and
`INVALID_EXPERIMENT`.

A selected foundation remains subject to later training authorization and does not inherit
any release/promotion status from this record.
