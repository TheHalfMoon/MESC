# MESC Experiment-0 — Current Status

```text
PACKAGE = MESC_EXPERIMENT_0_FOUNDATION_TOURNAMENT
STATE = PREPARATION_DRAFT
PARENT_STRATEGY_PR = 373
PARENT_STRATEGY_MERGED = TRUE
PARENT_STRATEGY_MERGE_SHA = 9e4ab03cf34f1e3a2ccb918fa9d9d861e2160177
PARENT_STRATEGY_QUALIFIED_HEAD = 243a3b2550208d679015ecdc967791b34aaab490
PARENT_STRATEGY_POSTMERGE_QUALIFICATION = PENDING
EXPERIMENT_0_PR = 374
EXPERIMENT_0_BASE = main
REAL_MODEL_EXECUTION = FALSE
REAL_DATA_EXECUTION = FALSE
REAL_GPU_EVIDENCE = FALSE
TRAINING = FALSE
MRL_0801_0808 = UNSATISFIED_BY_THIS_PACKAGE
MRL_0809 = BLOCKED_BY_REAL_PREFLIGHT_PREREQUISITES
MRL_0899 = BLOCKED_BY_MRL_0809
MRL_REAL_EXPERIMENT_READY = FALSE
TRAINING_READY = FALSE
```

`PARENT_STRATEGY_MERGED = TRUE` records only the mechanically verified merge of PR #373 into
canonical `main`. `PARENT_STRATEGY_POSTMERGE_QUALIFICATION` must not become `SUCCESS` until
the exact merge SHA has successful post-merge CI and CodeQL evidence.

Repository-side formatting is enforced by the canonical Ruff qualification gate. Formatting
success is code-quality evidence only and grants no execution, asset, evaluator, runtime,
training, promotion, or readiness authority.

This Experiment-0 package remains preparation-only and Draft. It does not satisfy or replace
any real MRL model, data, rights, contamination, runtime/GPU, objective/budget, evaluator,
sandbox, exact-head preflight, or readiness evidence. Live canonical repository truth and
MRL evidence gates control actual eligibility.
