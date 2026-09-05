# P01-06 Deferral Adoption Reconciliation — Acceptance

Status: **CANDIDATE / GOVERNANCE ONLY**

Decision: `FD-P01-06-DEFERRAL-ADOPTION-RECONCILE-1`

This acceptance contract governs only the reconciliation package under `p01-06-deferral-adoption-reconciliation/`.

## Required pre-merge gates

All of the following must be true on one exact candidate head:

1. base is the mechanically verified canonical `main` descendant of merge `227ee9d81ca6d0ba76c563a92038ea072beb174d` with no materially conflicting P01-06 authority change;
2. diff is documentation/governance only;
3. PR #363 process history is represented truthfully, including the absence of repository evidence for separate final-head Founder Ready and Founder Merge dispositions;
4. no retroactive claim is made that missing pre-merge dispositions existed;
5. no P01-06 runtime evidence, Colab session, GPU fact, Hugging Face access, model execution, memory result, or scientific result is fabricated;
6. no alternate runtime/provider/model/revision is substituted;
7. historical Pilot-01 closeout and accepted B0 evidence remain preserved;
8. P01-07, QLoRA, Unsloth training, adapters, B1 scientific execution, retrieval, benchmark/test-partition execution, publication, clinical use, and production use remain unauthorized;
9. exact-head `quality (py3.11)` passes;
10. exact-head `quality (py3.12)` passes;
11. exact-head `analyze (python)` passes;
12. exact-head CodeQL passes;
13. any applicable optional-backend qualification passes;
14. a fresh independent substantive semantic/governance review of the exact candidate head reports no blocking finding;
15. every material review finding and thread is resolved or explicitly dispositioned with evidence;
16. current `main`, PR base, exact candidate head, and ruleset `20172239` are reverified immediately before Founder Ready;
17. the Founder explicitly records `FOUNDER_READY = EXERCISED` for the exact reviewed reconciliation head;
18. the candidate head remains unchanged after Founder Ready;
19. current `main`, PR base, exact candidate head, required checks, review state, and ruleset are reverified again immediately before Founder Merge;
20. the Founder explicitly records `FOUNDER_MERGE = EXERCISED` and `EXPECTED_HEAD = <exact head>`;
21. merge uses method `merge` with the exact expected-head guard;
22. post-merge mechanical verification proves canonical merge SHA, tree, and ordered parents;
23. post-merge CI, CodeQL, and applicable optional-backend workflows are observed and recorded truthfully;
24. only after item 22 may issue-state reconciliation be finalized.

## Accepted terminal meaning

If every item above succeeds and the package is canonically adopted:

```text
P01_06_REACTIVATION_EPISODE = DEFERRED / NOT EXECUTED
P01_06_EXECUTION = NOT PERFORMED
P01_06_EVIDENCE = NOT PRODUCED
P01_06_FEASIBILITY_RESULT = NOT ESTABLISHED
FD_P01_06_COLAB_1_CURRENT_AUTHORITY = SUPERSEDED
FD_P01_06_COLAB_1_HISTORICAL_RECORD = PRESERVED
P01_07 = NOT AUTHORIZED
```

The accepted meaning is administrative deferral only. It is not P01-06 scientific completion and does not satisfy any P01-07 prerequisite.

## Fail-closed conditions

Do not merge if:

- canonical `main` moves to a materially different P01-06 authority state;
- genuine P01-06 runtime evidence appears and changes the decision basis;
- any required check fails or is missing on the exact head;
- substantive review has an unresolved blocking finding;
- any material review thread remains unresolved;
- Founder Ready or Founder Merge is not explicitly recorded for the exact reconciliation head;
- expected head changes after Founder Merge;
- merge cannot be guarded by exact expected head;
- the package would rewrite history, fabricate compliance, or create successor authority.

## Non-acceptance meanings

Adoption does not establish Colab feasibility, model fit, gated-access rights, GPU memory sufficiency, a scientific success/failure, P01-06 scientific completion, P01-07 eligibility, publication readiness, or production readiness.