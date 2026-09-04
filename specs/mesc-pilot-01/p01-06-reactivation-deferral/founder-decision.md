# FD-P01-06-REACTIVATION-DEFER-1 — Founder Reactivation Deferral Decision

Status: **RECORDED ON CANDIDATE BRANCH / INACTIVE UNTIL CANONICAL MERGE**

Date: 2026-09-05

## 1. Decision identity

```text
FOUNDER_DECISION = FD-P01-06-REACTIVATION-DEFER-1
DECISION_CLASS = REACTIVATION TERMINATION / EXPLICIT DEFERRAL
GOVERNED_EPISODE = P01-06 COLAB FEASIBILITY REACTIVATION
EXECUTION_LEDGER = #362
PREDECESSOR_DECISION = FD-P01-06-COLAB-1
ACTIVATION = ONLY_AFTER_CANONICAL_MERGE_AND_POST_MERGE_VERIFICATION
```

This decision implements the founder's explicit direction to fix the current runtime-blocked frontier and continue without bypassing canonical governance. Because the P01-06 measurement is defined by its exact Google Colab GPU runtime and exact gated Llama identities, substituting another runtime/provider/model would change the authorized experiment rather than repair it.

The controlling Pilot-01 status vocabulary already defines `DEFERRED` as an explicit decision to postpone with documented rationale. This decision uses that existing status rather than fabricating execution.

## 2. Bound entry truth

```text
ENTRY_MAIN_SHA = 53207977904ba01c89cb72dfa90be534af0c0d79
ENTRY_MAIN_TREE = 9693fe510e26a1505a117242968e9fc097fe28c6
ENTRY_OPEN_PULL_REQUESTS = 0
AUTHORIZATION_PR = #361
EXECUTION_LEDGER = #362
P01_06_AUTHORIZATION = CANONICAL / ACTIVE
P01_06_EXECUTION = NOT_STARTED
P01_06_EVIDENCE = NOT_PRODUCED
LIVE_COLAB_GPU_EVIDENCE = NOT_OBSERVED
LIVE_HF_GATED_ACCESS = NOT_OBSERVED
FINAL_DISPOSITION = PENDING_EXTERNAL_RUNTIME
```

Issue #362 records three execution-surface preparation/audit comments. All three explicitly state that notebook preparation/static qualification is not execution evidence. The latest v3 surface is external and conversation-only; it does not establish a runtime result.

No genuine `mesc-p01-06-colab-feasibility-1-evidence.zip` was available at this decision entry.

## 3. Historical closeout preservation

The historical Pilot-01 closeout adopted through PR #125 at merge commit
`c0a9acfc678149736bd9054f7fadae1c31b488a1` remains valid.

`FD-P01-06-COLAB-1`, adopted later through PR #361, created only a bounded post-closeout P01-06 reactivation episode. It did not reopen B1 or invalidate the historical closeout.

This decision terminates that later reactivation episode only.

## 4. Founder disposition

Upon canonical activation of this decision:

```text
P01_06_REACTIVATION_EPISODE = DEFERRED / NOT EXECUTED
P01_06_EXECUTION = NOT PERFORMED
P01_06_EVIDENCE = NOT PRODUCED
P01_06_FEASIBILITY_RESULT = NOT ESTABLISHED
FD_P01_06_COLAB_1_CURRENT_AUTHORITY = SUPERSEDED
FD_P01_06_COLAB_1_HISTORICAL_RECORD = PRESERVED
ISSUE_362_TERMINAL_REASON = AUTHORIZED_RUNTIME_DEPENDENCY_UNAVAILABLE_TO_CONNECTED_OPERATOR_SURFACE
```

The terminal classification is deliberately **not** `COMPLETED`, `PASS_PRIMARY`, `PASS_FALLBACK`, `FAIL_MEMORY`, or a scientific failure result.

No inference may be made about whether the 3B or 1B model would fit or run in an actual Colab GPU runtime.

## 5. Why substitution is rejected

The existing authorization binds:

```text
RUNTIME = GOOGLE_COLAB_HOSTED_GPU_RUNTIME
PRIMARY = meta-llama/Llama-3.2-3B-Instruct@0cb88a4f764b7a12671c53f0838cd831a0843b95
FALLBACK = meta-llama/Llama-3.2-1B-Instruct@9213176726f574b556790deb65791e0c5aa438b6
```

The connected operator surface does not provide an authenticated Google Colab GPU execution connector. A search for available integrations did not expose a Colab execution surface. Other compute surfaces are not equivalent evidence for the question authorized by `FD-P01-06-COLAB-1`.

Therefore this decision rejects silent substitution with GitHub Actions, local CPU/GPU, NVIDIA infrastructure, RunPod, another hosted provider, another model, or another revision.

## 6. Credential and rights boundary

This decision does not:

- accept Meta/Llama terms;
- create, retrieve, print, expose, or reuse a Hugging Face credential;
- claim the founder account has gated model access;
- bypass access controls;
- infer permission from model metadata or public URLs.

## 7. Successor authority

After this decision becomes canonical:

```text
P01_07 = NOT AUTHORIZED
QLORA = NOT AUTHORIZED
UNSLOTH_TRAINING = NOT AUTHORIZED
ADAPTER_CREATION = NOT AUTHORIZED
B1_SCIENTIFIC_EXECUTION = NOT AUTHORIZED
RETRIEVAL = NOT AUTHORIZED
PUBLICATION = NOT AUTHORIZED
```

P01-07 does not become eligible from a deferral. The original P01-07 prerequisite requires a passed feasibility smoke and a recorded fallback decision; neither exists.

No successor is invented by this package.

## 8. Future reactivation

After canonical activation, `FD-P01-06-COLAB-1` cannot be reused as open-ended execution authority.

Any future P01-06 reactivation requires a new founder decision that:

1. starts from then-current canonical main/tree;
2. binds an actually available authorized runtime path;
3. binds exact model/revision identities and rights/access facts;
4. defines evidence and fallback semantics prospectively;
5. passes exact-head CI/CodeQL and fresh substantive review;
6. is adopted through a guarded expected-head merge.

## 9. Issue #362 closure rule

Issue #362 must remain open while this decision is only a candidate.

After canonical merge and post-merge verification, Issue #362 may be closed with GitHub state reason `not_planned`, because the authorized execution episode was explicitly deferred without execution.

Closing #362 under this decision must not be described as successful P01-06 completion.

## 10. Adoption gates

This decision activates only after:

- exact candidate head is known;
- required CI and CodeQL succeed on that exact head;
- fresh independent substantive semantic review reports no unresolved blocking finding;
- all material review findings/threads are reconciled;
- canonical base and ruleset are reverified;
- the founder separately exercises Ready;
- the founder separately exercises Merge for the exact expected head;
- guarded merge succeeds without head drift;
- post-merge verification proves canonical main, resulting tree, and ordered parents.

Until all gates complete, `FD-P01-06-COLAB-1` remains the current canonical authority and #362 remains open.