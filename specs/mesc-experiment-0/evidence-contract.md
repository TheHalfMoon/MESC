# MESC Experiment-0 — Evidence Contract

Status: **DESIGN CONTRACT / NO RUNTIME EVIDENCE PRESENT**

Schema family:

```text
MESC-EXPERIMENT-0-CONFIG-V1
MESC-EXPERIMENT-0-RUNTIME-V1
MESC-EXPERIMENT-0-CANDIDATE-RESULT-V1
MESC-EXPERIMENT-0-BUNDLE-V1
```

## 1. Principles

Evidence must be:

- metadata-first;
- deterministic where practical;
- content-addressed;
- bound to exact repository/model/data/evaluator/config identities;
- free of credentials and PHI;
- explicit about missing/blocked states;
- independently verifiable without access to hidden notebook state.

No screenshot, copied console text, or manually edited metric table is sufficient evidence by
itself.

## 2. Frozen experiment config

Before model acquisition, the execution input must include a canonical JSON object with at
least:

```text
schema_version
experiment_id
objective_id
repository_sha
repository_tree
strategy_decision_id
candidate_roster
candidate_revisions
candidate_processor_identities
candidate_license_identities
dataset_identities
evaluator_identities
prompt_template_identities
generation_configs
runtime_policy
network_policy
filesystem_policy
credential_policy
resource_budget
query_budget
result_exposure_budget
hard_floor_policy
decision_rule
sealed_evaluation_policy
```

The config must have a SHA-256 over canonical UTF-8 JSON bytes. Any mutation after freeze
creates a new config identity and invalidates prior results for combined decision use.

## 3. Runtime receipt

Required fields:

```text
schema_version = MESC-EXPERIMENT-0-RUNTIME-V1
experiment_config_sha256
repository_sha
repository_tree
execution_started_at_utc
execution_completed_at_utc
runtime_provider
runtime_class
python_version
platform_string
torch_version
transformers_version
cuda_available
cuda_version
gpu_count
gpu_models
gpu_total_memory_bytes
colab_release_tag_or_image_identity_if_observable
installed_environment_manifest_sha256
network_policy_observation
credential_surface_observation
final_runtime_disposition
stop_reason
```

Allowed runtime dispositions:

```text
PASS_RUNTIME_PREFLIGHT
BLOCKED_RUNTIME_IDENTITY
BLOCKED_CUDA_UNAVAILABLE
BLOCKED_RESOURCE_POLICY
BLOCKED_DEPENDENCY_DRIFT
BLOCKED_REPOSITORY_IDENTITY
BLOCKED_OTHER
```

## 4. Candidate snapshot receipt

Every active candidate requires:

```text
candidate_id
candidate_revision
resolved_revision
processor_or_tokenizer_identity
model_config_sha256
snapshot_manifest_sha256
snapshot_file_count
snapshot_total_bytes
license_identity
notice_identity
usage_policy_identity
trust_remote_code
remote_code_exception_identity
load_disposition
failure_stage
failure_class
failure_message_sha256
allocated_memory_after_load_bytes
reserved_memory_after_load_bytes
peak_allocated_memory_bytes
peak_reserved_memory_bytes
```

`resolved_revision` must equal the frozen candidate revision. A moving branch such as
`main`, `master`, or `latest` is not an admissible execution identity.

## 5. Dataset/evaluator binding

Each evaluation lane result must bind:

```text
dataset_id
dataset_revision
dataset_manifest_sha256
split_id
split_manifest_sha256
heldout_tier
evaluator_id
evaluator_revision
evaluator_manifest_sha256
scoring_policy_sha256
prompt_template_sha256
generation_config_sha256
```

For medical imaging, the dataset admission record must also bind the applicable rights,
custody, DICOM/private-tag/burned-in-text, de-identification, patient/study grouping, and
leakage-assessment evidence identities required by the MESC strategy.

## 6. Candidate result record

Schema:

```text
MESC-EXPERIMENT-0-CANDIDATE-RESULT-V1
```

Required fields:

```text
experiment_config_sha256
runtime_receipt_sha256
candidate_snapshot_receipt_sha256
candidate_id
candidate_revision
lane
metric_vector
hard_floor_vector
item_count
invalid_item_count
abstention_count
resource_usage
query_budget_used
result_exposure_used
result_manifest_sha256
candidate_disposition
limitations
```

Allowed candidate dispositions:

```text
PASS_LANE
FAIL_HARD_FLOOR
BLOCKED_RUNTIME
BLOCKED_RIGHTS
BLOCKED_CONTAMINATION
BLOCKED_EVALUATOR
INVALID_RESULT
```

A missing result is never serialized as zero.

## 7. Decision record

Allowed decision dispositions:

```text
RETAIN_PREFERRED_CANDIDATE
SELECT_CHALLENGER
INCONCLUSIVE_OR_BLOCKED
INVALID_EXPERIMENT
```

Required fields:

```text
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

`selected_candidate_id` and `selected_candidate_revision` must be null unless disposition is
`RETAIN_PREFERRED_CANDIDATE` or `SELECT_CHALLENGER`.

This decision is research evidence only. It is not model promotion and not training
authority.

## 8. Evidence bundle

The final returned archive should be a deterministic ZIP where practical and contain only
metadata/evaluation artifacts permitted by the frozen exposure policy.

Proposed layout:

```text
mesc-experiment-0-evidence/
  experiment-config.json
  runtime-receipt.json
  environment-manifest.json
  candidate-snapshots/
    <candidate-safe-id>.json
  lane-results/
    <candidate-safe-id>/<lane>.json
  decision/
    foundation-decision.json
  manifests/
    bundle-manifest.json
```

The outer archive filename should be stable and include no secrets:

```text
mesc-experiment-0-evidence.zip
```

`bundle-manifest.json` must list every archive member **except itself** with:

```text
path
size_bytes
sha256
media_type
```

The manifest cannot hash itself because that would create a self-referential digest. The
outer ZIP hash is recorded separately after archive construction and is not an entry inside
`bundle-manifest.json`.

The bundle verifier must reject:

- duplicate paths;
- path traversal;
- unexpected executable/binary payloads;
- credentials/tokens by explicit forbidden-field checks;
- model weights/tokenizer snapshot bytes;
- raw PHI or unapproved medical-image bytes;
- missing mandatory files;
- hash mismatches;
- schema/version mismatch;
- inconsistent experiment/repository/candidate identities;
- a manifest entry that attempts to list/hash `bundle-manifest.json` itself.

## 9. Repository evidence boundary

Canonical Git may store:

- hashes;
- sizes;
- immutable upstream identities;
- aggregate metrics permitted by the exposure contract;
- reviewed decision/acceptance dispositions;
- verifier output;
- external-custody artifact identity.

Canonical Git must not store by default:

- provider credentials;
- Hugging Face tokens;
- model weights;
- private dataset bytes;
- PHI;
- sealed Tier 3 item-level content;
- raw chain-of-thought;
- generated data that exceeds the frozen result-exposure policy.

## 10. Fail-closed rule

If an evidence field required to establish identity, rights, contamination, evaluator state,
runtime state, or sealed isolation is absent or ambiguous, the affected candidate/lane is
`BLOCKED` or the experiment is `INVALID_EXPERIMENT`. Missing evidence cannot be filled with
assumptions after execution.
