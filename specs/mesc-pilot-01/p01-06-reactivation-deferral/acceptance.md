# P01-06 Reactivation Deferral — Acceptance Contract

Status: **CANDIDATE / GOVERNANCE ONLY**

Decision: `FD-P01-06-REACTIVATION-DEFER-1`

## Package acceptance

This package is eligible for Ready and Merge only if every item below is true on one exact candidate head:

1. the candidate descends from verified canonical `main` `53207977904ba01c89cb72dfa90be534af0c0d79` or a later mechanically verified descendant that does not materially change the decision basis;
2. the diff is documentation/governance only;
3. the historical Pilot-01 closeout adopted through PR #125 remains preserved and is not rewritten;
4. the package accurately records PR #361 / `FD-P01-06-COLAB-1` as a later bounded P01-06-only reactivation;
5. no Google Colab execution, GPU allocation, Hugging Face gated access, model download/load/generation, CUDA-memory observation, or evidence ZIP is claimed without genuine evidence;
6. the terminal disposition is exactly `DEFERRED / NOT EXECUTED`, not successful completion or scientific failure;
7. no alternate runtime/provider/model/revision is silently substituted;
8. P01-07, QLoRA, Unsloth training, adapter creation, B1 scientific execution, retrieval, benchmark/test-partition inspection, publication, clinical use, and production use remain unauthorized;
9. future P01-06 work requires a new explicit founder decision and cannot reuse `FD-P01-06-COLAB-1` as open-ended authority;
10. exact-head required CI passes;
11. exact-head CodeQL passes;
12. any required optional-backend check passes;
13. a fresh independent substantive semantic review of the exact head reports no unresolved blocking findings;
14. every material review finding and review thread is resolved or explicitly dispositioned with evidence;
15. canonical `main`, the PR base, the exact candidate head, and current repository ruleset are reverified immediately before Ready/Merge;
16. the founder separately exercises Ready for the exact reviewed head;
17. the founder separately exercises Merge for the exact expected head;
18. merge uses the repository-supported merge method and an exact expected-head guard or equivalent fail-closed protection;
19. post-merge mechanical verification proves the resulting canonical main SHA, tree, and ordered parents;
20. Issue #362 remains open until item 19 is complete.

## Post-merge terminal state

If all acceptance items pass and the package is canonically adopted:

```text
P01_06_REACTIVATION_EPISODE = DEFERRED / NOT EXECUTED
P01_06_EXECUTION = NOT PERFORMED
P01_06_EVIDENCE = NOT PRODUCED
P01_06_FEASIBILITY_RESULT = NOT ESTABLISHED
P01_07 = NOT AUTHORIZED
```

Issue #362 may then be closed with state reason `not_planned`.

## Fail-closed conditions

Stop and do not merge if any of the following occurs:

- genuine P01-06 execution evidence appears before merge and materially changes the decision basis;
- canonical main moves to a materially different P01-06 authority state;
- a reviewer identifies a substantive governance, precedence, or authority defect that is not resolved;
- required CI/CodeQL fails or is not bound to the exact candidate head;
- a review thread remains materially unresolved;
- the package would need to claim execution facts that were not observed;
- the package would grant P01-07 or another successor merely because P01-06 is deferred;
- the expected head changes after the final founder Merge disposition.

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