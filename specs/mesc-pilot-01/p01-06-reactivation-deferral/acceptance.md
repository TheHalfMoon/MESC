# P01-06 Reactivation Deferral — Acceptance Contract

Status: **CANDIDATE / GOVERNANCE ONLY**

Decision: `FD-P01-06-REACTIVATION-DEFER-1`

Issue roles:

```text
AUTHORIZATION_ISSUE = #360
EXECUTION_LEDGER = #362
DEFERRAL_GOVERNANCE_ISSUE = #364
DEFERRAL_PR = #363
```

#364 is the explicit governance ledger whose acceptance criteria authorize this proposed administrative deferral. It does not replace #362 or convert #362 into a successful execution record.

## Package acceptance

This package is eligible for Founder Ready and Founder Merge only if every item below is true on one exact candidate head:

1. the candidate descends from verified canonical `main` `53207977904ba01c89cb72dfa90be534af0c0d79` or a later mechanically verified descendant that does not materially change the decision basis;
2. the diff is documentation/governance only;
3. the historical Pilot-01 closeout adopted through PR #125 remains preserved and is not rewritten;
4. the package accurately records #360 / PR #361 / `FD-P01-06-COLAB-1` as the bounded P01-06 authorization and #362 as its separate execution ledger;
5. governance issue #364 remains the explicit ledger for candidate decision `FD-P01-06-REACTIVATION-DEFER-1` and PR #363;
6. no Google Colab execution, GPU allocation, Hugging Face gated access, model download/load/generation, CUDA-memory observation, or evidence ZIP is claimed without genuine evidence;
7. the terminal disposition is exactly `DEFERRED / NOT EXECUTED`, not successful completion or scientific failure;
8. no alternate runtime/provider/model/revision is silently substituted;
9. P01-07, QLoRA, Unsloth training, adapter creation, B1 scientific execution, retrieval, benchmark/test-partition inspection, publication, clinical use, and production use remain unauthorized;
10. future P01-06 work requires a new explicit founder decision and cannot reuse `FD-P01-06-COLAB-1` as open-ended authority;
11. exact-head required CI passes;
12. exact-head CodeQL passes;
13. any required optional-backend check passes;
14. a fresh independent substantive semantic review of the exact head reports no unresolved blocking findings;
15. every material review finding and review thread is resolved or explicitly dispositioned with evidence;
16. canonical `main`, the PR base, the exact candidate head, and current repository ruleset are reverified immediately before Founder Ready/Merge;
17. the founder separately exercises Founder Ready for the exact reviewed head;
18. the founder separately exercises Founder Merge for the exact expected head;
19. merge uses the repository-supported merge method and an exact expected-head guard or equivalent fail-closed protection;
20. post-merge mechanical verification proves the resulting canonical main SHA, tree, and ordered parents;
21. execution ledger #362 remains open until item 20 is complete;
22. governance issue #364 remains open until item 20 is complete and the #362 terminal disposition is recorded.

## Post-merge terminal state

If all acceptance items pass and the package is canonically adopted:

```text
P01_06_REACTIVATION_EPISODE = DEFERRED / NOT EXECUTED
P01_06_EXECUTION = NOT PERFORMED
P01_06_EVIDENCE = NOT PRODUCED
P01_06_FEASIBILITY_RESULT = NOT ESTABLISHED
P01_07 = NOT AUTHORIZED
```

Execution ledger #362 may then be closed with state reason `not_planned`. After that terminal disposition is recorded, governance issue #364 may be closed as `completed`.

## Fail-closed conditions

Stop and do not merge if any of the following occurs:

- genuine P01-06 execution evidence appears before merge and materially changes the decision basis;
- canonical main moves to a materially different P01-06 authority state;
- a reviewer identifies a substantive governance, precedence, or authority defect that is not resolved;
- required CI/CodeQL fails or is not bound to the exact candidate head;
- a review thread remains materially unresolved;
- the package would need to claim execution facts that were not observed;
- the package would grant P01-07 or another successor merely because P01-06 is deferred;
- the expected head changes after the final Founder Merge disposition.

## Non-acceptance meanings

Passing this acceptance contract does not establish:

- Colab feasibility;
- model fit or memory sufficiency;
- model-access rights;
- a successful or failed scientific experiment;
- P01-06 scientific completion;
- P01-07 eligibility;
- publication readiness.

It establishes only a truthful, canonically adopted administrative deferral of the separately authorized reactivation episode.