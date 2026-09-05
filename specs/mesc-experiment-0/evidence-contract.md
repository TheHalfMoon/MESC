# MESC Experiment-0 — Evidence Contract

Status: **DESIGN CONTRACT / NO RUNTIME EVIDENCE PRESENT**

Schema family:

```text
MESC-EXPERIMENT-0-CONFIG-V1
MESC-EXPERIMENT-0-ENVIRONMENT-V1
MESC-EXPERIMENT-0-RUNTIME-V1
MESC-EXPERIMENT-0-CANDIDATE-SNAPSHOT-V1
MESC-EXPERIMENT-0-CANDIDATE-RESULT-V1
MESC-EXPERIMENT-0-DECISION-V1
MESC-EXPERIMENT-0-BUNDLE-V1
```

## 1. Principles

Evidence must be metadata-first, deterministic where practical, content-addressed, bound to
exact repository/model/data/evaluator/config identities, free of credentials and PHI,
explicit about blocked states, and independently verifiable without hidden notebook state.

A screenshot, copied console text, manually edited metric table, repository-authored claim,
or generic Founder approval is not sufficient real-experiment evidence by itself.

Hashes in this contract bind **exact stored bytes** unless a field explicitly says that it
binds canonicalized JSON. Evidence writers must not add or remove trailing newlines after a
digest is computed.

## 2. Frozen experiment config

Two states exist:

```text
UNFROZEN_TEMPLATE_ONLY
FROZEN_EXECUTION_CONFIG
```

The committed template may use `UNFROZEN_TEMPLATE_ONLY`, empty rosters/lists, null budgets,
and null `authority_bindings`. It is not executable.

Every state other than `UNFROZEN_TEMPLATE_ONLY` is invalid unless it is exactly
`FROZEN_EXECUTION_CONFIG` and all required execution fields are populated.

A frozen execution config requires at least:

```text
schema_version
experiment_id
status
objective_id
repository_sha
repository_tree
strategy_decision_id
candidate_roster
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
authority_bindings
```

A frozen config must have non-empty dataset, evaluator, prompt-template, and generation
identity lists; object-valued runtime/network/filesystem/credential policies; explicit
non-null compute, wall-time, storage, retry, query, and result-exposure budgets; an explicit
hard-floor policy; an explicit decision rule; and a sealed-evaluation policy.

Each `candidate_roster` entry requires:

```text
candidate_id
candidate_revision
candidate_class
evidence_key
supported_input_modalities
```

`candidate_revision` must be an immutable exact revision accepted by the execution contract.
The current V1 verifier requires a lowercase 40-hex revision identity. Moving aliases such as
`main`, `master`, `latest`, or provider aliases are inadmissible.

Allowed candidate classes:

```text
SELECTABLE_FOUNDATION
REFERENCE_ONLY
```

A selectable foundation must satisfy `tournament-contract.md`. A reference-only candidate
may establish a specialist/control ceiling but cannot be selected as the MESC foundation.

### Mandatory MRL authority/evidence bindings

`authority_bindings` must contain every key below:

```text
mrl_0801_evidence_id
mrl_0802_evidence_id
mrl_0803_evidence_id
mrl_0804_evidence_id
mrl_0805_authority_id
mrl_0806_objective_id
mrl_0807_evaluator_freeze_id
mrl_0808_sandbox_id
mrl_0809_preflight_id
mrl_0899_readiness_id
```

All ten values may be null **only** in the committed `UNFROZEN_TEMPLATE_ONLY` state. Every
value must be non-null in `FROZEN_EXECUTION_CONFIG`. Repository-authored placeholders do not
satisfy the underlying MRL evidence requirements.

The config identity is SHA-256 over canonical UTF-8 JSON bytes using sorted keys, compact
separators, UTF-8, and no NaN values. Any post-freeze mutation creates a new config identity
and invalidates prior results for combined decision use.

## 3. Environment manifest

Schema:

```text
MESC-EXPERIMENT-0-ENVIRONMENT-V1
```

Required fields:

```text
schema_version
python_version
platform
packages
```

`packages` contains metadata-only objects with package `name` and `version`. Direct install
URLs, credentials, tokens, private indexes, editable-source URLs, and secret-bearing package
metadata must not be persisted. The runtime receipt binds the SHA-256 of the **exact stored
`environment-manifest.json` bytes**.

## 4. Runtime receipt

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

Allowed `final_runtime_disposition` values:

```text
PASS_RUNTIME_PREFLIGHT
BLOCKED_RUNTIME_IDENTITY
BLOCKED_CUDA_UNAVAILABLE
BLOCKED_RESOURCE_POLICY
BLOCKED_DEPENDENCY_DRIFT
BLOCKED_REPOSITORY_IDENTITY
BLOCKED_OTHER
```

The verifier must require the runtime config hash, repository SHA/tree, and exact environment
manifest digest to agree with the corresponding evidence bytes.

## 5. Candidate snapshot receipt

Every frozen roster entry requires exactly one metadata snapshot receipt at:

```text
candidate-snapshots/<evidence_key>.json
```

Schema:

```text
MESC-EXPERIMENT-0-CANDIDATE-SNAPSHOT-V1
```

Required fields:

```text
schema_version
experiment_config_sha256
candidate_id
candidate_revision
candidate_class
evidence_key
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

A receipt exists even when acquisition/load is blocked. Blocked facts remain explicit nulls
where appropriate rather than being fabricated. `trust_remote_code` is false by default; a
true value requires an exact reviewed exception identity. A selected foundation must have a
successful frozen load disposition.

## 6. Dataset/evaluator binding

Every lane result must bind exact dataset, split, held-out tier, evaluator, scoring policy,
prompt-template, and generation-config identities.

For medical imaging, admission additionally binds the rights/custody,
DICOM/private-tag/burned-in-text, de-identification, patient/study grouping, leakage, and
held-out-isolation evidence required by the MESC strategy.

## 7. Candidate result record

Schema:

```text
MESC-EXPERIMENT-0-CANDIDATE-RESULT-V1
```

Each result lives under:

```text
lane-results/<evidence_key>/<lane>.json
```

Required fields:

```text
schema_version
experiment_config_sha256
runtime_receipt_sha256
candidate_snapshot_receipt_sha256
candidate_id
candidate_revision
evidence_key
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
NOT_SUPPORTED_BY_CANDIDATE
```

Missing evidence is never serialized as numeric zero. Unsupported modalities use the
explicit unsupported disposition. Every result hash must appear exactly once in the final
decision hash set.

## 8. Decision record

Schema:

```text
MESC-EXPERIMENT-0-DECISION-V1
```

Allowed `decision_disposition` values:

```text
RETAIN_PREFERRED_CANDIDATE
SELECT_CHALLENGER
INCONCLUSIVE_OR_BLOCKED
INVALID_EXPERIMENT
```

Required fields:

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

`candidate_result_sha256s` must equal the sorted unique set of exact candidate-result JSON
byte hashes in the bundle. No result may be omitted and no nonexistent result may be added.

`selected_candidate_id` and `selected_candidate_revision` are null unless the disposition is
`RETAIN_PREFERRED_CANDIDATE` or `SELECT_CHALLENGER`. Positive selection additionally
requires a selectable frozen roster identity, successful snapshot/load evidence, actual
candidate results, sealed-evaluation evidence, and no failed mandatory hard floor.

The decision is research evidence only. It is not model promotion or training authority.

## 9. Evidence bundle

The returned archive should be deterministic where practical and contain only
metadata/evaluation artifacts permitted by the frozen exposure policy:

```text
mesc-experiment-0-evidence/
  experiment-config.json
  runtime-receipt.json
  environment-manifest.json
  candidate-snapshots/
    <evidence_key>.json
  lane-results/
    <evidence_key>/<lane>.json
  decision/
    foundation-decision.json
  manifests/
    bundle-manifest.json
```

`bundle-manifest.json` lists every archive member **except itself** with:

```text
path
size_bytes
sha256
media_type
```

It cannot hash itself because that creates a self-referential digest. The outer ZIP hash is
recorded separately after archive construction.

The verifier must reject duplicate/case-colliding paths; traversal, absolute, backslash, NUL,
encrypted, or symlink members; excessive member counts or uncompressed sizes before member
bytes are retained; unexpected binary/executable payloads; credentials; model weights;
private/raw medical data; missing mandatory files; incomplete frozen configs or MRL bindings;
missing candidate snapshot receipts; result/decision hash mismatch; schema/version mismatch;
inconsistent identities; and selection of a reference-only candidate.

## 10. Repository evidence boundary

Canonical Git may store hashes, sizes, immutable upstream identities, aggregate metrics
permitted by the exposure contract, reviewed dispositions, verifier output, and
external-custody artifact identities.

Canonical Git must not store provider credentials, Hugging Face tokens, model weights,
private dataset bytes, PHI, sealed Tier-3 item-level content, raw chain-of-thought, or data
outside the frozen exposure policy.

## 11. Fail-closed rule

If identity, rights, contamination, evaluator, runtime, roster/result reconciliation,
budgets, or sealed-isolation evidence is absent or ambiguous, the affected lane/candidate is
blocked or the experiment is invalid. Missing evidence cannot be filled with assumptions
after execution.
