# MRL Real Preflight Evidence V1

Status: **IMPLEMENTATION / FAIL-CLOSED ADMISSION SUBSTRATE / NO REAL EVIDENCE ADMITTED**

Canonical base for this implementation branch:

```text
BASE_MAIN_SHA = 262ee5dc54fe194037530baf4009981de23b4dd4
BASE_MAIN_TREE = 3ff64f938c3b421453873f95cf15895ba86cc9ec
MRL_REAL_PREFLIGHT_ENTERED = TRUE
MRL_REAL_EXPERIMENT_READY = FALSE
```

## Purpose

MRL-0801 through MRL-0808 require genuine evidence that cannot be manufactured from
repository-only closeout records. The current machine-state layer intentionally keeps those
tasks in the real-evidence class and refuses to close them from ordinary PR/CI evidence.

This package adds a strict semantic envelope and a separate repository-controlled trust
admission boundary for already-supplied real-preflight evidence. It does not add any real
evidence and does not change a task checkbox or task state.

The production trust registry is intentionally empty:

```text
TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256 = frozenset()
```

Therefore canonical JSON bytes, scalar hashes, a `PASS` string, or the existence of this
module cannot make any MRL-8 evidence task trusted.

## Evidence roles

The closed V1 role set is:

| Task | Evidence kind | Required semantic boundary |
|---|---|---|
| `MRL-0801` | `mesc.mrl.real_preflight.model_weights.v1` | exact model id, immutable revision, `weights_sha256`, artifact identity, custody, and access-authorization identities; actual asset presence |
| `MRL-0802` | `mesc.mrl.real_preflight.corpus_rights.v1` | exact corpus identity and bytes plus rights, provenance, and access-authorization identities |
| `MRL-0803` | `mesc.mrl.real_preflight.isolation.v1` | passing contamination evidence and explicit held-out/sealed exclusion from training |
| `MRL-0804` | `mesc.mrl.real_preflight.runtime.v1` | platform-qualified runtime/smoke identities with no remote-code or network-access claim in the evidence envelope |
| `MRL-0805` | `mesc.mrl.real_preflight.training_authorization.v1` | explicit `AUTHORIZED` training receipt/artifact/current trust-registry identities and `real_training_authorized=true` |
| `MRL-0806` | `mesc.mrl.real_preflight.objective_budgets.v1` | externally frozen research objective and resource/query/exposure budgets |
| `MRL-0807` | `mesc.mrl.real_preflight.evaluators.v1` | exact evaluator/Tier-3 identities with explicit non-promotional semantics |
| `MRL-0808` | `mesc.mrl.real_preflight.sandbox.v1` | qualified sandbox plus frozen network, mutation-path, output-destination, and stop-condition identities |

Every envelope is exact canonical JSON with one terminal LF and exactly this top-level
field set:

```text
disposition
kind
payload
schema_version
subject_sha256
task_id
```

`disposition` must be exactly `PASS`. `schema_version` must be exactly
`MRL-REAL-PREFLIGHT-EVIDENCE-V1`. The task and evidence kind must occupy the exact matching
role. Every task payload has a closed field set and fail-closed semantic checks.

### MRL-0806 objective-budget payload

`mesc.mrl.real_preflight.objective_budgets.v1` preserves the existing
`ResearchObjectiveContract` budget semantics without collapsing distinct ceilings into
ambiguous aggregate counters. Its payload is exactly:

```text
adaptive_query_budget
budget_exhaustion_disposition
evaluation_tier_policy
frozen_externally
research_objective_sha256
resource_budget
tier_result_exposure_policy
```

`resource_budget` reproduces the canonical `ResourceBudget` field set exactly:

```text
compute_seconds
evaluator_invocations
generated_tokens
input_tokens
known_failure_retries
max_experiments
monetary_cost_microunits
retries
storage_bytes
wall_clock_seconds
```

The nullable resource ceilings retain the canonical meaning of `None`: the resource is not
applicable to that objective; it never means unlimited. Retry relationships and all integer
semantics are validated through the canonical `ResourceBudget` contract.

`evaluation_tier_policy` contains only `allowed_tiers`. `adaptive_query_budget` contains
exactly `tier_1_queries` and `tier_2_queries`. `tier_result_exposure_policy` contains one
strictly ascending entry for every and only allowed tier, with each entry containing exactly
`tier`, `max_exposures`, and `allowed_result_fields`. Tier 3 and Tier 4 remain non-iterative:
they cannot expose result fields or a positive exposure count. A nonzero Tier-1 or Tier-2
query budget is invalid when the corresponding SEARCH or REPLICATION tier is absent.
`budget_exhaustion_disposition` must be exactly `BLOCKED`.

Legacy aggregate fields such as `compute_units`, `token_budget`, scalar
`adaptive_query_budget`, or scalar `result_exposure_budget` are not canonical MRL-0806
semantics and are rejected.

Parsing an MRL-0806 envelope proves only that its declared budget subset is internally valid.
Before a genuine envelope can be admitted as MRL-0806 evidence, independent verification must
also establish that `research_objective_sha256` identifies the exact frozen
`ResearchObjectiveContract` artifact and that every budget field in this payload exactly
reproduces that objective's resource, tier, adaptive-query, result-exposure, and exhaustion
semantics. This repository-side contract does not manufacture or infer that external binding.

## Trust boundary

Two operations are deliberately distinct:

```text
parse_mrl_real_preflight_evidence
  = canonical byte/schema/semantic validation only

admit_mrl_real_preflight_evidence
  = parse + exact current trust-registry membership
```

Neither operation means:

```text
MRL_TASK_CLOSED
MRL_REAL_EXPERIMENT_READY
TRAINING_READY
TRAINING_AUTHORIZED
TRAINING_EXECUTION_COMPLETE
RELEASE_READY
PROMOTED
```

Provisioning a production evidence digest into the trust registry is a separate canonical
governance mutation. It must be based on genuine external evidence for that exact role and
must receive the review/qualification required by live MRL governance. A self-authored
envelope is not made genuine by adding hashes to it.

For `MRL-0805`, this layer is additional to, not a replacement for, the canonical training
authorization trust path. A future trusted MRL envelope must bind the exact training
authorization receipt, exact authorization artifact, exact authorization subject, and the
exact current training-authorization trust-registry identity. This package does not add a
training-authorization trust root.

At `MRL-0805` admission time, the outer MRL evidence digest is necessary but not sufficient.
The admission path also invokes the canonical training-authorization trust validator so the
claimed authorization artifact must be trusted by the exact current registry snapshot.
Parsing remains independent of that authority check.

## Current disposition

```text
MRL-0801 = PLANNED
MRL-0802 = PLANNED
MRL-0803 = PLANNED
MRL-0804 = PLANNED
MRL-0805 = PLANNED
MRL-0806 = PLANNED
MRL-0807 = PLANNED
MRL-0808 = PLANNED

TRUSTED_REAL_PREFLIGHT_EVIDENCE_COUNT = 0
REAL_MODEL_OR_WEIGHTS_ACCESSED = FALSE
REAL_CORPUS_ACCESSED = FALSE
GATED_TERMS_ACCEPTED = FALSE
PROVIDER_OR_GPU_ACTIVATED = FALSE
INFERENCE_EXECUTED = FALSE
TRAINING_EXECUTED = FALSE
```

## Qualification transport boundary

Ruff formatting was applied only to the two Python files in this package under an
expected-head and exact-path guard. The subsequent `MRL-0805` trust-binding review repair
was also applied under an expected-head guard, qualified with focused Ruff, Mypy, and pytest,
and constrained to these same three package files. Those transport checks are not evidence,
authority, or task closure; only fresh qualification on the final user-authored PR head may
count.

## Authority boundary

This package does not:

- download or inspect real model weights;
- acquire real corpus bytes;
- accept gated model or dataset terms;
- use provider credentials;
- activate a GPU or external sandbox;
- run inference, retrieval, training, or fine-tuning;
- provision a Founder/operator authorization artifact;
- mutate the canonical training-authorization trust registry;
- freeze a real research objective or evaluator set;
- mark `MRL-0801..MRL-0808` complete;
- declare `MRL_REAL_EXPERIMENT_READY`;
- create promotion, release, deployment, or clinical authority.

The next legitimate MRL-8 transition remains evidence-driven. Real evidence must exist first;
then its exact canonical envelope may be independently verified and separately admitted by
canonical governance before any MRL task-closeout candidate is considered.
