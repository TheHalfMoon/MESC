# Acceptance — Phi Activation Artifact Contracts 1

Status: **DRAFT / GOVERNANCE-ONLY / NO EXECUTION AUTHORITY**

Every predicate is fail-closed. Unknown, ambiguous, stale, or unreviewed contract
semantics => `BLOCKED`.

## A. Canonical prerequisite

Before this package may become Ready, require:

```text
BASE_MAIN_SHA = 42615ad465eada4ede814d7f7de1e0703dafe137
BASE_MAIN_TREE = 0dbe3dc7a43f2dd8bc5be174c33b5986b87a6caf
PR_171 = CLOSED_CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The package must remain a descendant of the exact base with `behind=0` unless a
separately reviewed base reconciliation is performed. No force-push, rebase, or
destructive history rewrite is permitted.

## B. Scope confinement

The intended package scope is exactly:

```text
specs/mesc-backbone-tournament/phi-artifact-contracts-1/README.md
specs/mesc-backbone-tournament/phi-artifact-contracts-1/security-review-artifact-contract.md
specs/mesc-backbone-tournament/phi-artifact-contracts-1/sandbox-qualification-artifact-contract.md
specs/mesc-backbone-tournament/phi-artifact-contracts-1/acceptance.md
```

No source code, test, workflow, dependency, lockfile, corpus, scoring-key,
prompt, model/provider, credential, runtime, activation receipt, execution
result, or training path may be changed by this package.

Any scope expansion requires a new review decision; it may not be silently folded
into this package.

## C. Contract consistency

Independent review must verify that the proposed artifact formats do not weaken
or reinterpret `FD-MESC-BT-EXEC-1`.

At minimum, reviewers must prove:

1. the security-review artifact binds the exact Phi remote-code manifest digest;
2. it requires one exact PASS disposition for every manifest path;
3. it requires independent-review and complete-import-graph PASS claims;
4. its reachable-import-graph evidence is digest-bound rather than left as an
   unbound narrative claim;
5. the sandbox artifact binds the exact runtime identity field categories already
   required by `FD-MESC-BT-EXEC-1`;
6. it preserves every exact Section C.3 isolation-control value;
7. both formats reject duplicate JSON member names and noncanonical byte
   serialization;
8. neither format treats a syntactic parser PASS as proof that the producer or
   live observation is trustworthy;
9. neither format grants model access, gated-access authority, execution
   activation, ranking, winner selection, or tournament execution.

A conflict with the existing conditional authorization contract is a blocker.

## D. Deliberately unresolved dependency

`security-review-artifact-contract.md` binds a
`reachable_import_graph_artifact_sha256`, but this package does not freeze the
byte-level schema or completeness semantics of the import-graph materialization
itself.

Therefore canonical adoption of this package must preserve:

```text
REACHABLE_IMPORT_GRAPH_ARTIFACT_CONTRACT = REQUIRED_BEFORE_ACTIVATION_RELIANCE
REAL_IMPORT_GRAPH_COMPLETENESS = NOT_ESTABLISHED
```

The security-review artifact cannot satisfy activation while its bound graph
artifact lacks a separately reviewed canonical contract and producer.

This is intentional fail-closed dependency exposure, not an implied completion
claim.

## E. Exact-head qualification

Keep the PR Draft until one unchanged exact head has all of:

1. exact changed-file reconciliation against canonical `main`;
2. `behind=0`;
3. CI PASS on the repository's required Python matrix;
4. CodeQL PASS;
5. fresh exact-head technical/security/governance review;
6. fresh independent exact-head review when available;
7. zero unresolved technical/security/contract/governance blocker threads.

Any head mutation burns head-specific qualification evidence.

No Founder execution attestation is requested or required for this package,
because this package authenticates no Founder decision and grants no execution
or access authority.

## F. Merge and canonical adoption

If the Draft package later satisfies every gate and is explicitly advanced to
Ready, merge must use expected-head protection. After merge, mechanically verify:

- merge commit SHA and tree;
- ordered parents;
- hosting signature validity;
- exact four-file delta;
- exact canonical blob identity for every package file;
- no unexpected canonical path changes.

Only after that verification may the package be described as
`CLOSED_CANONICAL`.

Canonical adoption freezes only the two proposed artifact serialization
contracts. It does not establish either real artifact, its digest, its producer,
or any live qualification result.

## G. Hard boundary

```text
REAL_PHI_SOURCE_READ = NOT_PERFORMED
REAL_PHI_IMPORT_GRAPH_CONSTRUCTION = NOT_PERFORMED
REAL_PHI_SECURITY_REVIEW = NOT_PERFORMED
REAL_PHI_SANDBOX_QUALIFICATION = NOT_PERFORMED
REAL_ACTIVATION_PACKAGE_READ = NOT_PERFORMED
PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256 = NOT_ESTABLISHED
PHI_SANDBOX_QUALIFICATION_SHA256 = NOT_ESTABLISHED
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
FINE_TUNING = NOT_AUTHORIZED
```