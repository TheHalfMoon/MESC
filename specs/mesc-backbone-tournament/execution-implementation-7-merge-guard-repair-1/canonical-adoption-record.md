# MESC Backbone Tournament — Execution Implementation 7 Merge-Guard Repair 1

Status: **DRAFT CANONICAL-ADOPTION REPAIR — NO EXECUTION AUTHORITY**

Date: 2026-08-23

This document reconciles canonical truth after PR #149 merged the exact fully reviewed implementation head, but before the intended manual merge step could prove use of an `expected_head_sha` guard and complete the full post-Ready requalification checklist.

This is documentation and governance reconciliation only. It authorizes nothing. It does not rewrite Git history, does not claim an unobserved API guard was used, and does not grant execution activation.

## 1. Canonical merge identity

```text
IMPLEMENTATION_PR = #149
IMPLEMENTATION_BASE_SHA = 2d9c73b372f0135d74d996d6023444ab0ee93a78
IMPLEMENTATION_BASE_TREE = 8e3d2fbc471bbebe70e6dd6816c8b353eea5fa8e
IMPLEMENTATION_REVIEWED_HEAD_SHA = d44250f1cafb4a205cd0efcfceeb6f07d7a1777c
IMPLEMENTATION_MERGE_SHA = 7ea21892cb1a9796436129864576f13e0e134eb4
IMPLEMENTATION_MERGE_TREE = 1bb079dd679e3340eeb0a3c23d731e7ced048bc9
IMPLEMENTATION_MERGE_PARENT_0 = 2d9c73b372f0135d74d996d6023444ab0ee93a78
IMPLEMENTATION_MERGE_PARENT_1 = d44250f1cafb4a205cd0efcfceeb6f07d7a1777c
IMPLEMENTATION_MERGED_AT = 2026-08-23T04:20:01Z
IMPLEMENTATION_MERGE_SIGNATURE_VERIFIED = true
IMPLEMENTATION_MERGE_SIGNATURE_REASON = valid
```

The merge therefore contains exactly the intended canonical baseline as first parent and the exact reviewed implementation head as second parent. The adopted implementation delta is exactly:

```text
specs/mesc-backbone-tournament/execution-implementation-7/README.md
src/medscale/mesc/_bt_protocol_policy_fixture_v1.py
tests/test_mesc_bt_protocol_policy_fixture_v1.py
```

No rollback, force-push, rebase, destructive history rewrite, source replacement, or compensating implementation mutation is performed by this repair.

## 2. Pre-Ready and pre-merge content qualification

Unlike the historical PR #146 ordering defect, PR #149 had a completed independent external exact-head review before it was marked Ready.

The final implementation head was:

```text
FINAL_HEAD = d44250f1cafb4a205cd0efcfceeb6f07d7a1777c
AHEAD_OF_BASE = 2
BEHIND_BASE = 0
CHANGED_FILES = 3
```

Exact-head automated evidence was complete and successful:

```text
CI_RUN_ID = 32617242197
CI_RUN_NUMBER = 575
CI_RESULT = SUCCESS
PYTHON_3_11_QUALITY = SUCCESS
PYTHON_3_12_QUALITY = SUCCESS
RUFF_LINT = SUCCESS
RUFF_FORMAT = SUCCESS
MYPY_STRICT = SUCCESS
PYTEST = SUCCESS
LITDB_INTEGRITY = SUCCESS

CODEQL_RUN_ID = 32617242220
CODEQL_RUN_NUMBER = 581
CODEQL_RESULT = SUCCESS
```

Fresh internal exact-head technical/security review completed with:

```text
INTERNAL_EXACT_HEAD_REVIEW = PASS
INTERNAL_BLOCKING_FINDINGS = 0
INTERNAL_SOURCE_MUTATION_REQUIRED = NO
```

The fresh independent external CodeRabbit review was bound to the exact canonical base, exact final head, and exact three-file scope:

```text
CODERABBIT_RUN_ID = 9e77cc24-8e08-47d2-8e36-4f51db1be2eb
CODERABBIT_BASE = 2d9c73b372f0135d74d996d6023444ab0ee93a78
CODERABBIT_HEAD = d44250f1cafb4a205cd0efcfceeb6f07d7a1777c
CODERABBIT_SELECTED_FILES = 3
CODERABBIT_FINAL_UPDATED_AT = 2026-08-23T04:19:03Z
CODERABBIT_DISPOSITION = NO_ACTIONABLE_COMMENTS
CODERABBIT_MERGE_RISK = MINIMAL
```

The review therefore completed before the Ready transition. No blocking review thread existed at the final pre-Ready check.

The Ready transition returned the unchanged exact head and unchanged three-file scope at approximately the PR update recorded at:

```text
READY_STATE_OBSERVED = true
READY_RESPONSE_UPDATED_AT = 2026-08-23T04:19:51Z
READY_HEAD = d44250f1cafb4a205cd0efcfceeb6f07d7a1777c
```

The canonical merge followed at `2026-08-23T04:20:01Z` and its second parent proves that the merged bytes were the exact reviewed head.

## 3. Historical process-evidence gap

The intended merge procedure required both:

1. a complete post-Ready requalification before merge; and
2. a merge request protected by exact `expected_head_sha`.

The merge occurred before the manual merge step was issued. Git history proves the resulting merge contains the exact reviewed head, but Git history does not prove which API race guard was or was not supplied to the merge request.

Therefore the following predicates must remain conservative:

```text
EXPECTED_HEAD_API_GUARD_USED = NOT_PROVEN
FULL_POST_READY_REQUALIFICATION_COMPLETED_BEFORE_MERGE = NOT_PROVEN
MERGED_CONTENT_EQUALS_EXACT_REVIEWED_HEAD = PROVEN
MERGE_PARENT_0_EQUALS_PREMERGE_CANONICAL_MAIN = PROVEN
MERGE_PARENT_1_EQUALS_EXACT_REVIEWED_HEAD = PROVEN
MERGE_SIGNATURE_VALID = PROVEN
```

This record does not infer causation for the merge and does not attribute it to a particular external process. The GitHub REST record identifies the repository owner account as `merged_by`, but that does not establish which client or automation initiated the action.

Because the intended guarded-merge and complete post-Ready process properties cannot both be proven from durable evidence, the historical process classification is:

```text
IMPLEMENTATION_7_PREMERGE_CONTENT_QUALIFICATION = PASS
IMPLEMENTATION_7_PREMERGE_EXTERNAL_REVIEW_ORDERING = PASS
IMPLEMENTATION_7_MERGED_BYTES_IDENTITY = EXACT_HEAD_PROVEN
IMPLEMENTATION_7_EXPECTED_HEAD_GUARD = NOT_PROVEN
IMPLEMENTATION_7_FULL_POST_READY_REQUALIFICATION = NOT_PROVEN
IMPLEMENTATION_7_MERGE_PROCESS_CONFORMANCE = NONCONFORMING_NOT_PROVEN
```

`NONCONFORMING_NOT_PROVEN` is an evidence classification. It does not assert that the exact-head guard was definitely absent; it records that required use of that guard and the complete post-Ready checklist cannot be independently proven.

## 4. Content and authority remain unchanged

The implementation itself is a fixture-only frozen protocol-policy binder. It validates caller-supplied canonical `protocol-config.json` bytes and reconstructs frozen policy controls. It does not perform the execution behavior that it describes.

The merged source does not:

```text
read the frozen corpus or scoring keys
serialize a candidate prompt
execute timeout or retry behavior
instantiate a tokenizer or processor
instantiate or load a model
access provider infrastructure
allocate a GPU
access model weights
request or accept gated access
perform remote-code import or execution
run inference or generation
score a real model response
rank candidates
select a winner
execute the backbone tournament
train or fine-tune a model
activate execution
```

The content review result remains clean. This repair records a process-evidence gap only; it does not identify or repair a source defect.

## 5. Repair rule

Until this repair package itself receives fresh qualification and is canonically adopted, record the current state as:

```text
PR_149 = MERGED
IMPLEMENTATION_7_PREMERGE_CONTENT_QUALIFICATION = PASS
IMPLEMENTATION_7_PREMERGE_EXTERNAL_REVIEW_ORDERING = PASS
IMPLEMENTATION_7_MERGED_BYTES_IDENTITY = EXACT_HEAD_PROVEN
IMPLEMENTATION_7_EXPECTED_HEAD_GUARD = NOT_PROVEN
IMPLEMENTATION_7_FULL_POST_READY_REQUALIFICATION = NOT_PROVEN
IMPLEMENTATION_7_CANONICAL_QUALIFICATION = PENDING_MERGE_GUARD_ADOPTION_REPAIR
```

If, and only if, this documentation-only repair receives on one unchanged exact head:

- stable canonical base and one-file documentation-only scope;
- exact-head CI PASS and CodeQL PASS as applicable;
- fresh exact-head internal technical/governance review PASS;
- fresh independent external exact-head review completed before Ready/merge;
- zero unresolved blocking review threads;
- Ready transition without head mutation;
- guarded merge with an explicitly supplied expected-head SHA;
- post-merge verification of merge SHA, tree, ordered parents, signature, and canonical record blob;

then the current canonical classification may be recorded as:

```text
PR_149 = MERGED_WITH_HISTORICAL_MERGE_PROCESS_EVIDENCE_GAP
IMPLEMENTATION_7_CANONICAL_QUALIFICATION = REPAIRED_BY_POST_MERGE_ADOPTION_RECORD
IMPLEMENTATION_7_EXPECTED_HEAD_GUARD = HISTORICAL_NOT_PROVEN
IMPLEMENTATION_7_FULL_POST_READY_REQUALIFICATION = HISTORICAL_NOT_PROVEN
IMPLEMENTATION_7_MERGED_BYTES_IDENTITY = EXACT_HEAD_PROVEN
```

That repaired classification does not retroactively claim that the original guarded-merge process was proven. It means canonical governance contains an independently reviewed record of the gap and the exact content that was adopted.

## 6. Repair scope and non-claims

This repair changes documentation only. It does not modify or re-approve Implementation 7 source/tests and does not expand their authority.

It does not authorize the next implementation slice, provider allocation, model acquisition, gated access, remote-code import, prompt serialization, inference, ranking, winner selection, or tournament execution.

## 7. Authorization boundary

```text
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
MODEL_WEIGHT_ACCESS = NOT_AUTHORIZED
GATED_ACCESS_REQUEST_OR_ACCEPTANCE = NOT_AUTHORIZED
MODEL_RETRIEVAL = NOT_AUTHORIZED
PHI_REMOTE_CODE_IMPORT_OR_EXECUTION = NOT_AUTHORIZED
PROMPT_SERIALIZATION_TO_MODEL = NOT_AUTHORIZED
INFERENCE = NOT_AUTHORIZED
GENERATION = NOT_AUTHORIZED
RANKING = NOT_AUTHORIZED
WINNER_SELECTION = NOT_AUTHORIZED
BACKBONE_TOURNAMENT_EXECUTION = NOT_AUTHORIZED
TRAINING = NOT_AUTHORIZED
```

Canonical adoption of this record, if it occurs, is governance reconciliation only. It grants no execution authority and satisfies no production activation predicate by itself.

## 8. Repair commit identity

The commit that introduces or repairs this record is identified outside this document in the PR qualification record and independent review request. Its SHA is intentionally not embedded inside the content it would have to identify.
