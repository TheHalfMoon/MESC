# MESC Experiment-0 — Google Colab Runbook

Status: **PROTOCOL TEMPLATE / EXECUTION BLOCKED UNTIL MRL REAL-PREFLIGHT GATES PASS**

This runbook reuses execution-engineering lessons from historical P01-06 but has independent
scope and authority.

## 1. Required prerequisites

Do not start model acquisition unless live canonical repository truth proves:

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

If any prerequisite is absent, stop before model/data access and write only a metadata-only
blocked receipt:

```text
FINAL_DISPOSITION = BLOCKED
STOP_REASON = MRL_REAL_PREFLIGHT_INCOMPLETE
```

Do not edit the notebook/config to bypass the gate.

## 2. Prepare the frozen config

The notebook consumes exact canonical JSON satisfying `MESC-EXPERIMENT-0-CONFIG-V1`.

The committed `UNFROZEN_TEMPLATE_ONLY` file is intentionally non-executable. A real run
requires `FROZEN_EXECUTION_CONFIG` with immutable repository SHA/tree, exact candidate
revisions/classes, dataset/split/evaluator identities, generation settings, runtime/network/
filesystem/credential policies, explicit budgets, hard floors, decision rule, sealed Tier-3
policy, and every MRL-0801..MRL-0809 plus MRL-0899 binding populated.

Do not use `main`, `latest`, floating tags, or provider aliases as execution identities.

## 3. Start Google Colab

1. Open `notebooks/MESC_Experiment_0_Colab.ipynb`.
2. Select a Google-hosted GPU runtime.
3. Do not use a local runtime.
4. Do not assume the assigned GPU class.
5. Provide only credentials explicitly allowed by the frozen credential policy through a
   non-printing secret surface.
6. Never paste secrets into notebook source, printed output, Git, or evidence files.

## 4. Runtime attestation

Before repository clone or model acquisition, record the actual provider/class, Python,
platform, PyTorch, CUDA availability/version, GPU count/model/memory, and observable Colab
image/release identity.

`runtime_policy` must be an object and must be validated before reading any GPU-policy field.
A missing/malformed policy is a blocked preflight, never a Python exception accepted as
scientific evidence.

## 5. Bind canonical repository identity

Clone the repository and checkout only the frozen canonical SHA. Require:

```text
HEAD == frozen repository_sha
TREE == frozen repository_tree
```

Do not execute Experiment-0 from an unmerged planning/authorization branch.

## 6. Reproduce and record the environment

Prefer the repository lock and canonical setup path. Do not silently install a different
framework version because a candidate fails.

The environment evidence is metadata-only `MESC-EXPERIMENT-0-ENVIRONMENT-V1`. Record package
**name and version only**; do not persist `pip freeze` direct URLs, private indexes, editable
source URLs, or credential-bearing package metadata.

The runtime receipt must bind SHA-256 over the exact stored `environment-manifest.json`
bytes. Evidence writers must compute the digest over exactly the bytes they write.

## 7. Candidate acquisition

For every frozen candidate:

1. resolve the exact pinned upstream revision;
2. require resolved revision equality;
3. preserve a metadata-only snapshot manifest with SHA-256 and sizes;
4. verify processor/tokenizer/config identities;
5. use `trust_remote_code=False` by default;
6. require an exact reviewed exception before any remote code;
7. never fall back to another model/revision automatically;
8. emit an explicit candidate snapshot receipt even when acquisition/load is blocked.

## 8. Synthetic smoke

Before medical evaluation, run only frozen synthetic/non-sealed smoke inputs. Verify model
load, text path, vision path where required, structured result capture, deterministic
generation settings, evaluator wiring, GPU accounting, and evidence serialization.

A smoke failure is not a quality score.

## 9. Scientific evaluation order

Execute only frozen lanes and tiers:

```text
Tier 0 protocol smoke
Tier 1 development evaluation
Tier 2 replication
Tier 3 sealed evaluation (only after predeclared finalist rule)
```

Do not expose Tier-3 item-level content to the adaptive research process.

## 10. Budget enforcement

Before every candidate/tier transition, verify remaining compute, wall-time, query,
result-exposure, storage, and retry budgets. A null or missing execution budget means the
config was not genuinely frozen and the run is invalid. Budget exhaustion stops the run.

## 11. No-training enforcement

Experiment-0 must not instantiate an optimizer or create mutable training artifacts.
Forbidden training actions include PEFT/LoRA/QLoRA, Unsloth/TRL trainers, optimizer steps,
training backward passes, checkpoint/adapter creation, or teacher-generation loops intended
for later training.

Framework libraries may exist only when frozen inference runtime requirements need them and
must not mutate model weights.

## 12. Evidence bundle

A complete scientific run emits:

```text
mesc-experiment-0-evidence.zip
```

The archive satisfies `evidence-contract.md` and is returned unchanged for independent
verification. Do not unzip/repack it after its outer hash is recorded.

A preflight that blocks before a complete bundle exists may emit `blocked.json`; that local
blocked receipt is not a substitute for a contract-complete decision bundle.

## 13. Terminal disposition mapping

Two different fields exist and must not be conflated.

### 13.1 Execution/run disposition

`FINAL_DISPOSITION` is a runbook/control-plane disposition used when the execution cannot
reach a complete scientific decision record. Allowed runbook values are:

```text
FOUNDATION_DECISION_EVIDENCE_CANDIDATE
INCONCLUSIVE_OR_BLOCKED
INVALID_EXPERIMENT
BLOCKED
```

Use `BLOCKED` for fail-closed preflight stops such as missing MRL authority/evidence,
malformed frozen config, runtime-policy failure, unavailable CUDA, repository-identity
mismatch, or non-canonical candidate adapters.

### 13.2 Evidence decision disposition

`decision_disposition` belongs only to `MESC-EXPERIMENT-0-DECISION-V1` and must be one of:

```text
RETAIN_PREFERRED_CANDIDATE
SELECT_CHALLENGER
INCONCLUSIVE_OR_BLOCKED
INVALID_EXPERIMENT
```

**Never write `BLOCKED` into `decision_disposition`.** A run that blocks before a complete
scientific decision remains `FINAL_DISPOSITION = BLOCKED` and may have no decision record.
If a contract-complete experiment finishes but cannot select a foundation because admissible
evidence is incomplete or all candidates are blocked, use:

```text
FINAL_DISPOSITION = INCONCLUSIVE_OR_BLOCKED
decision_disposition = INCONCLUSIVE_OR_BLOCKED
```

A positive complete bundle maps to:

```text
FINAL_DISPOSITION = FOUNDATION_DECISION_EVIDENCE_CANDIDATE
decision_disposition = RETAIN_PREFERRED_CANDIDATE | SELECT_CHALLENGER
```

An invalid complete experiment maps to:

```text
FINAL_DISPOSITION = INVALID_EXPERIMENT
decision_disposition = INVALID_EXPERIMENT
```

Even the strongest positive disposition does not mean model promotion, `TRAINING_READY`,
release readiness, or clinical validation.

## 14. Stop boundary

After Experiment-0 evidence is emitted, stop. A separate canonical successor decides whether
the foundation evidence is accepted and whether any first ground-truth SFT experiment becomes
eligible.
