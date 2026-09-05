# MESC Experiment-0 — Google Colab Runbook

Status: **PROTOCOL TEMPLATE / EXECUTION BLOCKED UNTIL MRL REAL-PREFLIGHT GATES PASS**

This runbook reuses the strongest execution-engineering lessons from historical P01-06 but
has independent scope and authority.

## 1. Required prerequisites

Do not start model acquisition unless all of the following are true in live canonical
repository truth:

```text
STRATEGY_PR_373 = MERGED_CANONICAL
MRL_0801 = QUALIFIED_FOR_ACTIVE_CANDIDATES
MRL_0802 = QUALIFIED_FOR_ACTIVE_EVALUATION_ASSETS
MRL_0803 = QUALIFIED_FOR_CONTAMINATION_AND_ISOLATION
MRL_0804 = QUALIFIED_FOR_SELECTED_RUNTIME
MRL_0805 = APPLICABLE_NO_TRAINING_EXECUTION_AUTHORITY_PRESENT
MRL_0806 = OBJECTIVE_ROSTER_BUDGETS_FROZEN
MRL_0807 = EVALUATORS_AND_SEALED_TIER3_FROZEN
MRL_0808 = EXECUTION_SANDBOX_VERIFIED
MRL_0809 = EXACT_HEAD_PREFLIGHT_QUALIFIED
MRL_0899 = MRL_REAL_EXPERIMENT_READY
```

If any prerequisite is absent:

```text
FINAL_DISPOSITION = BLOCKED
STOP_REASON = MRL_REAL_PREFLIGHT_INCOMPLETE
```

Do not edit the notebook or config to bypass the gate.

## 2. Prepare the frozen config

The notebook must consume an exact canonical JSON config satisfying
`MESC-EXPERIMENT-0-CONFIG-V1`.

The config must contain immutable:

- repository SHA/tree;
- candidate roster and revisions;
- processor/tokenizer identities;
- dataset/split/evaluator identities;
- generation configs;
- budgets and result-exposure ceilings;
- hard floors and decision rule;
- network/filesystem/credential policy;
- sealed-evaluation policy.

Do not use `main`, `latest`, floating tags, or provider aliases as model/dataset/evaluator
revisions.

## 3. Start Google Colab

1. Open `notebooks/MESC_Experiment_0_Colab.ipynb`.
2. Select a Google-hosted GPU runtime.
3. Do not use a local runtime.
4. Do not assume the assigned GPU class.
5. Provide only the credentials explicitly allowed by the frozen credential policy through
   Colab Secrets or equivalent non-printing mechanisms.
6. Never paste secrets into notebook source, printed output, Git, or evidence files.

## 4. Runtime attestation

Before repository clone or model acquisition, record:

```text
runtime_provider
runtime_class
python_version
platform_string
torch_version
cuda_available
cuda_version
gpu_count
gpu_models
gpu_total_memory_bytes
```

Fail closed if the frozen runtime policy cannot be verified.

## 5. Bind canonical repository identity

Clone the repository and checkout only the exact frozen canonical SHA.

Verify:

```text
HEAD == frozen repository_sha
TREE == frozen repository_tree
```

Do not execute Experiment-0 from an unmerged planning/authorization branch.

## 6. Reproduce the environment

Prefer the repository lock and canonical setup path. Record an environment manifest after
installation.

Do not silently install a different framework version because a candidate fails. A required
dependency change is a protocol/config change and must be separately frozen before
scientific result combination.

## 7. Candidate acquisition

For each active candidate:

1. resolve the exact pinned upstream revision;
2. require resolved revision equality;
3. preserve a metadata-only file manifest with SHA-256 and size for downloaded artifacts;
4. verify processor/tokenizer/config identities;
5. use `trust_remote_code=False` by default;
6. if remote code is required, stop unless an exact reviewed exception identity is present;
7. never fall back to another model/revision automatically.

## 8. Synthetic smoke

Before any medical evaluation, execute only frozen synthetic/non-sealed smoke inputs.

Verify:

- model load;
- text input/output path;
- image path for vision-capable candidates where required;
- structured result capture;
- deterministic generation configuration;
- evaluator/scorer wiring;
- GPU memory accounting;
- evidence serialization.

A smoke failure is not a quality score.

## 9. Scientific evaluation order

Execute only the frozen lanes and tiers:

```text
Tier 0 protocol smoke
Tier 1 development evaluation
Tier 2 replication
Tier 3 sealed evaluation (only after predeclared finalist rule)
```

Do not inspect Tier 3 item-level content manually to debug a low score.

## 10. Budget enforcement

Before every candidate/tier transition, check remaining:

```text
compute_budget
wall_time_budget
query_budget
result_exposure_budget
storage_budget
retry_budget
```

Budget exhaustion must stop the run with a typed `BLOCKED` disposition.

## 11. No-training enforcement

The notebook must not instantiate an optimizer or create mutable training artifacts.

Forbidden modules/actions for Experiment-0 execution include training uses of:

- PEFT/LoRA/QLoRA;
- Unsloth trainers;
- TRL trainers;
- `optimizer.step()`;
- backward passes intended to modify model parameters;
- checkpoint/adapter creation;
- teacher-generation loops intended for later training.

Framework libraries may only be present if required by a separately frozen inference
runtime and do not mutate weights.

## 12. Evidence bundle

At completion, emit:

```text
mesc-experiment-0-evidence.zip
```

The archive must satisfy `evidence-contract.md` and be returned unchanged for independent
verification/review.

Do not unzip/repack the evidence bundle before its outer hash is recorded.

## 13. Allowed terminal dispositions

```text
FOUNDATION_DECISION_EVIDENCE_CANDIDATE
INCONCLUSIVE_OR_BLOCKED
INVALID_EXPERIMENT
BLOCKED
```

Even the strongest positive disposition does not mean:

```text
MESC_MODEL_PROMOTED
TRAINING_READY
RELEASE_READY
CLINICALLY_VALIDATED
```

## 14. Stop boundary

After the Experiment-0 evidence artifact is emitted, stop.

A separate canonical successor must decide whether the foundation evidence is accepted and
whether any first ground-truth SFT experiment becomes eligible.
