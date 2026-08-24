# Acceptance — Phi Activation Artifact Contracts 1

Status: **DRAFT / GOVERNANCE-ONLY / NO EXECUTION AUTHORITY**

Every predicate is fail-closed. Unknown, ambiguous, stale, or unreviewed contract
semantics => `BLOCKED`.

## A. Canonical prerequisite

Before this governance package may become Ready, require:

```text
BASE_MAIN_SHA = 42615ad465eada4ede814d7f7de1e0703dafe137
BASE_MAIN_TREE = 0dbe3dc7a43f2dd8bc5be174c33b5986b87a6caf
PR_171 = CLOSED_CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
```

`EXECUTION_ACTIVATION = REQUIRED` remains a separate downstream prerequisite
before any later Phi access, remote-code import, model load, or tournament use.
Execution activation is **not** a prerequisite for this docs-only governance
package to become Ready or canonical, and canonical adoption of this package does
not satisfy execution activation.

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
5. the future graph-materialization contract must place a required
   `source_manifest_sha256` member **inside the exact canonical graph artifact
   bytes** whose SHA-256 equals `reachable_import_graph_artifact_sha256`, and the
   activation verifier must require that value to equal the security-review
   artifact's exact `manifest_sha256`; detached provenance or independent digest
   checks are insufficient;
6. the sandbox artifact binds `runtime_binding_sha256` to the SHA-256 of the
   **complete canonical activation `RUNTIME_BINDING` bytes**, rather than
   redeclaring a partial runtime schema;
7. a future activation verifier must independently validate and canonically
   reproduce the full runtime binding before comparing that digest;
8. the sandbox artifact contains exactly one `qualification_challenge` matching
   `^[0-9a-f]{64}$`, issued by the future activation verifier from exactly 32
   bytes of operating-system cryptographically secure random data only after the
   runtime binding is fixed and immediately before exactly one live qualification
   producer invocation;
9. the future activation verifier must maintain a current-process `ISSUED` record
   binding that exact challenge to the exact `runtime_binding_sha256`, expected
   `producer_identity`, and its live handle for that one producer invocation;
10. the artifact's challenge, runtime digest, and producer identity must equal the
    still-`ISSUED` verifier record, and the bound producer invocation must still be
    the same live invocation;
11. after all qualification checks pass, the verifier must atomically transition
    the run record from `ISSUED` to `CONSUMED` before exposing sandbox
    qualification PASS; unknown, reused, `CONSUMED`, `CANCELLED`, prior-process,
    prior-invocation, producer-chosen, or operator-supplied challenges remain
    `BLOCKED`;
12. verifier restart, producer exit, cancellation, or artifact rejection must not
    reconstruct or preserve an `ISSUED` record from artifact bytes or operator
    input; old artifacts therefore fail closed;
13. `qualification_challenge` must not be derived from `<ACTIVATION_ID>` and
    `<ACTIVATION_ID>` must not be required to issue it, avoiding circularity with
    the existing activation identity preimage that already binds
    `phi_sandbox_qualification_sha256`;
14. the sandbox artifact preserves every exact Section C.3 isolation-control value;
15. both formats reject duplicate JSON member names and noncanonical byte
    serialization;
16. neither format treats a syntactic parser PASS as proof that the producer or
    live observation is trustworthy;
17. each required negative fixture must PASS by proving replayed, detached,
    wrong-runtime, wrong-producer-invocation, unknown, `CONSUMED`, and
    `CANCELLED` challenge evidence reaches `BLOCKED`;
18. neither format grants model access, gated-access authority, execution
    activation, ranking, winner selection, or tournament execution.

A conflict with the existing conditional authorization contract is a blocker.

A sandbox format that copies only a subset of the canonical runtime fields is also
a blocker, because it could drift from the already-canonical runtime-binding
contract.

A sandbox freshness design that relies only on `runtime_binding_sha256`, an
operator-selected identifier, a producer-selected identifier, a timestamp window,
or `<ACTIVATION_ID>` is a blocker. Runtime equality alone cannot distinguish a
fresh qualification run from replay, and `<ACTIVATION_ID>` is derived only after
the sandbox artifact digest is established.

## D. Deliberately unresolved dependencies

### D.1 Reachable import graph

`security-review-artifact-contract.md` binds a
`reachable_import_graph_artifact_sha256`, but this package does not freeze the
full byte-level schema or completeness semantics of the import-graph
materialization itself.

Therefore canonical adoption of this package must preserve:

```text
REACHABLE_IMPORT_GRAPH_ARTIFACT_CONTRACT = REQUIRED_BEFORE_ACTIVATION_RELIANCE
REACHABLE_IMPORT_GRAPH_TO_MANIFEST_PROVENANCE = REQUIRED_BEFORE_ACTIVATION_RELIANCE
REAL_IMPORT_GRAPH_COMPLETENESS = NOT_ESTABLISHED
```

The future graph contract must define a required `source_manifest_sha256` member
inside the canonical graph artifact bytes, and those exact bytes must be the
bytes hashed to produce `reachable_import_graph_artifact_sha256`. The activation
verifier must parse and validate those exact bytes, reproduce the graph artifact
digest, and require:

```text
graph.source_manifest_sha256 == security_review.manifest_sha256
```

A detached provenance document, sidecar, narrative assertion, separately hashed
envelope, signature over different bytes, or any other relation outside the
exact hashed graph artifact bytes does not satisfy this requirement. A graph
digest valid in isolation but lacking the in-artifact `source_manifest_sha256`
binding remains `BLOCKED`.

The security-review artifact cannot satisfy activation while its bound graph
artifact lacks a separately reviewed canonical contract, producer, completeness
semantics, and this mechanically verifiable same-manifest binding.

### D.2 Live sandbox challenge verifier and producer

This package freezes the `qualification_challenge` byte field and its fail-closed
run-state semantics, but it does not implement or execute the future activation
verifier or live qualification producer.

Therefore canonical adoption of this package must preserve:

```text
PHI_SANDBOX_LIVE_PRODUCER = REQUIRED_BEFORE_ACTIVATION_RELIANCE
PHI_SANDBOX_CHALLENGE_VERIFIER = REQUIRED_BEFORE_ACTIVATION_RELIANCE
PHI_SANDBOX_REPLAY_NEGATIVE_FIXTURES = REQUIRED_BEFORE_ACTIVATION_RELIANCE
REAL_SANDBOX_QUALIFICATION_FRESHNESS = NOT_ESTABLISHED
```

A future implementation must prove the exact `ISSUED -> CONSUMED` lifecycle,
fail closed on every replay/cancellation mismatch listed by the sandbox contract,
and undergo separate review before any execution activation may rely on the
artifact.

These are intentional fail-closed dependency exposures, not implied completion
claims.

## E. Exact-head qualification

Keep the PR Draft until one unchanged exact head has all of:

1. exact changed-file reconciliation against canonical `main`;
2. `behind=0`;
3. CI PASS on the repository's required Python matrix;
4. CodeQL PASS;
5. fresh exact-head technical/security/governance review;
6. fresh independent exact-head review with no unresolved blocker;
7. zero unresolved technical/security/contract/governance blocker threads.

Independent exact-head review is mandatory. If an independent reviewer cannot be
obtained, the package remains `BLOCKED` and must not transition to Ready.

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
contracts and the sandbox artifact's run-scoped freshness field semantics. It
does not establish either real artifact, its digest, its producer, the challenge
verifier implementation, or any live qualification result.

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
