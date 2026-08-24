# Acceptance — Phi Reachable Import Graph Contract 1

Status: **DRAFT / GOVERNANCE-ONLY / NO EXECUTION AUTHORITY**

Every predicate is fail-closed. Unknown, ambiguous, stale, unreviewed, or
unreproducible evidence => `BLOCKED`.

## A. Canonical prerequisite

Before this package may become Ready, require:

```text
BASE_MAIN_SHA = 9f7144c7a0e0ee5574aaa47bbbefc5727c64c8bd
BASE_MAIN_TREE = 86f63b05813cdfb536212c1dfe7f962c3dcaa39a
PR_174 = CLOSED_CANONICAL
PHI_ACTIVATION_ARTIFACT_CONTRACTS_1 = CANONICAL
FD_MESC_BT_EXEC_1 = CONDITIONAL_AUTHORIZATION_CANONICAL
```

The package must remain a descendant of the exact base with `behind=0` unless a
separately reviewed base reconciliation is performed.

`EXECUTION_ACTIVATION = REQUIRED` remains a separate downstream prerequisite. This
package does not require execution activation to become canonical and cannot satisfy
execution activation.

## B. Scope confinement

The intended package scope is exactly:

```text
specs/mesc-backbone-tournament/phi-import-graph-contract-1/README.md
specs/mesc-backbone-tournament/phi-import-graph-contract-1/reachable-import-graph-artifact-contract.md
specs/mesc-backbone-tournament/phi-import-graph-contract-1/acceptance.md
```

No source code, test, workflow, dependency, lockfile, provider/model, credential,
corpus, scoring-key, prompt, runtime, activation receipt, execution result, or training
path may change in this package.

Any scope expansion requires a separate review decision.

## C. Authority boundary

Reviewers must confirm that this package is only the separately reviewed Phase 2
governance/qualification work permitted by `execution-authorization-1/plan.md` and the
explicit graph-contract dependency canonically introduced by PR #174.

The package may freeze a graph artifact schema and fail-closed completeness semantics.
It may not read real Phi source, construct a real graph, qualify a producer, allocate a
runtime, access model weights, execute remote code, or perform a security review.

A conflict with `FD-MESC-BT-EXEC-1` or any expansion into live/runtime/model authority
is a blocker.

## D. Contract consistency

Independent review must verify at least:

1. `source_manifest_sha256` is a required member inside the exact graph bytes whose
   digest becomes `REACHABLE_IMPORT_GRAPH_ARTIFACT_SHA256`;
2. graph roots equal the exact parser-validated canonical manifest paths in manifest
   order;
3. every manifest path appears exactly once as a `MANIFEST_FILE` node and no remote
   model-repository path outside the manifest can appear as a valid remote node;
4. every edge has `source_kind = MANIFEST_FILE`, references an existing manifest source
   node and an existing target node, and cannot relabel a remote-file target as a trusted
   runtime/dependency boundary;
5. every runtime/dependency boundary node is referenced by at least one edge, no module
   identity appears under both boundary kinds, and no edge originates from a boundary
   node;
6. closure exhausts every import relationship originating from manifest files until it
   reaches another manifest file or an explicit runtime/dependency terminal boundary;
7. any remotely sourced Python target discovered by closure must be in the manifest;
8. accepted V1 artifacts require exact empty `unresolved_imports` and
   `unresolved_dynamic_imports` arrays;
9. a dynamic or data-dependent import the producer cannot resolve mechanically is
   `BLOCKED`, not guessed or silently omitted;
10. graph `base_container_oci_digest`, `python_version`, and `dependency_lock_sha256`
    are inside the hashed bytes and future activation requires all three to equal the
    complete canonical `RUNTIME_BINDING`; `python_version` must use the same printable
    ASCII identity grammar as that runtime binding rather than a narrower invented token;
11. parser conformance, empty unresolved arrays, or literal `PASS` do not self-attest
    graph completeness;
12. a separately reviewed future producer/verifier remains mandatory and must prove its
    extraction/module-resolution algorithm exhausts this contract's closure semantics;
13. graph-to-manifest provenance outside the exact hashed graph bytes is insufficient;
14. neither this contract nor its canonical adoption establishes a real graph, real Phi
    security review, sandbox qualification, model access, or execution authority.

Any ambiguity that could allow an unmanifested remote file, unresolved dynamic import,
runtime mismatch, non-minimal graph identity, or unreviewed producer to support
activation is a blocker.

## E. Deliberately unresolved producer dependency

Canonical adoption of this package must preserve:

```text
REACHABLE_IMPORT_GRAPH_ARTIFACT_CONTRACT = CANONICAL_IF_THIS_PACKAGE_MERGES
REACHABLE_IMPORT_GRAPH_PRODUCER = REQUIRED_BEFORE_ACTIVATION_RELIANCE
REACHABLE_IMPORT_GRAPH_PRODUCER_QUALIFICATION = NOT_ESTABLISHED
REAL_PHI_SOURCE_READ = NOT_PERFORMED
REAL_PHI_IMPORT_GRAPH_CONSTRUCTION = NOT_PERFORMED
REAL_IMPORT_GRAPH_COMPLETENESS = NOT_ESTABLISHED
```

The future producer implementation must be a separate package. It must be independently
reviewed against exact source/runtime identities and include negative fixtures for all
blocking cases listed by the artifact contract before activation may rely on a graph
digest.

No real Phi source read or graph construction is authorized by canonicalizing this
contract.

## F. Exact-head qualification

Keep the PR Draft until one unchanged exact head has all of:

1. exact three-file changed-path reconciliation against canonical `main`;
2. `behind=0`;
3. fresh CI PASS;
4. fresh CodeQL PASS;
5. fresh exact-head internal technical/security/governance review PASS;
6. fresh independent exact-head review with no blocker;
7. zero unresolved technical/security/contract/governance blocker threads.

Independent exact-head review is mandatory. Reviewer unavailability => `BLOCKED`.
Any head mutation burns all head-specific qualification evidence.

## G. Merge and canonical adoption

If every gate passes and the Draft is explicitly advanced to Ready, merge only with
expected-head protection. After merge verify:

- merge SHA/tree and ordered parents;
- hosting signature validity;
- exact three-file canonical delta;
- exact canonical blob identity for all package files;
- no unexpected canonical path change.

Only then may this package be described as `CLOSED_CANONICAL`.

## H. Hard boundary

```text
REAL_PHI_SOURCE_READ = NOT_PERFORMED
REAL_PHI_IMPORT_GRAPH_CONSTRUCTION = NOT_PERFORMED
REAL_PHI_SECURITY_REVIEW = NOT_PERFORMED
REAL_PHI_SANDBOX_QUALIFICATION = NOT_PERFORMED
REACHABLE_IMPORT_GRAPH_PRODUCER_QUALIFICATION = NOT_ESTABLISHED
REAL_IMPORT_GRAPH_COMPLETENESS = NOT_ESTABLISHED
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
