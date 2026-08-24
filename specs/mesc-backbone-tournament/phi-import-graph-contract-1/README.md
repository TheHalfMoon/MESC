# MESC Backbone Tournament — Phi Reachable Import Graph Contract 1

Status: **DRAFT GOVERNANCE CONTRACT / NO EXECUTION AUTHORITY**

Date: 2026-08-24

## Canonical base

```text
BASE_MAIN_SHA = 9f7144c7a0e0ee5574aaa47bbbefc5727c64c8bd
BASE_MAIN_TREE = 86f63b05813cdfb536212c1dfe7f962c3dcaa39a
PR_174 = CLOSED_CANONICAL
PHI_ACTIVATION_ARTIFACT_CONTRACTS_1 = CANONICAL
FD_MESC_BT_EXEC_1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

## Authority and purpose

`execution-authorization-1/plan.md` authorizes a separately reviewed Phase 2
implementation/qualification path using fixtures or mocks only and without model-weight
access. PR #174 canonically added a narrower prerequisite before a future Phi security
review artifact may support activation:

```text
REACHABLE_IMPORT_GRAPH_ARTIFACT_CONTRACT = REQUIRED_BEFORE_ACTIVATION_RELIANCE
REACHABLE_IMPORT_GRAPH_TO_MANIFEST_PROVENANCE = REQUIRED_BEFORE_ACTIVATION_RELIANCE
REAL_IMPORT_GRAPH_COMPLETENESS = NOT_ESTABLISHED
```

This package addresses only the first governance gap. It freezes a candidate byte-level
artifact contract and fail-closed completeness boundary for the reachable Phi remote-code
import graph. It does not inspect Phi source, construct a graph, qualify a graph producer,
perform a security review, allocate a runtime, or activate execution.

## Exact package scope

Exactly:

```text
specs/mesc-backbone-tournament/phi-import-graph-contract-1/README.md
specs/mesc-backbone-tournament/phi-import-graph-contract-1/reachable-import-graph-artifact-contract.md
specs/mesc-backbone-tournament/phi-import-graph-contract-1/acceptance.md
```

No source code, test, workflow, dependency, lockfile, provider/model, credential,
corpus, scoring key, prompt, runtime state, activation receipt, execution result, or
training path is changed.

## Design boundary

The graph is rooted at every canonical Phi remote-code manifest path. Traversal is
closed recursively over remote model-repository Python files. Any remotely sourced
Python file required by an import must therefore be present in the exact bound manifest;
a remote target outside the manifest is `BLOCKED`.

Imports resolving to the bound Python runtime or immutable dependency environment are
explicit terminal boundary nodes rather than silently disappearing. Because module
resolution also depends on the immutable runtime image, the graph artifact binds exact
`base_container_oci_digest`, `python_version`, and `dependency_lock_sha256`; future
activation must require all three to equal the complete canonical `RUNTIME_BINDING`.

This package does not claim that Python-runtime or locked-dependency internals receive
the Phi remote-code file review. The graph records those boundaries so independent Phi
review can reason about them without pretending they are remote files. Changing that
trust boundary requires a separately reviewed contract amendment.

## Fail-closed completeness

An artifact may claim `completeness_disposition = PASS` only when:

- roots equal the exact canonical manifest paths in manifest order;
- every manifest path has one `MANIFEST_FILE` node;
- every edge source is a `MANIFEST_FILE` node;
- every remote target reached by import resolution is a manifest node;
- runtime/dependency imports terminate at explicit bound boundary nodes;
- `unresolved_imports = []`;
- `unresolved_dynamic_imports = []`;
- a separately reviewed future producer/verifier proves its extraction algorithm
  actually exhausts the relationships required by this contract.

Parser conformance or the literal `PASS` string is not proof of completeness.

## Deliberate non-claims

This package does **not**:

- read, download, clone, inspect, import, or execute Phi source;
- build, traverse, or validate a real import graph;
- establish the real Phi manifest or its digest;
- resolve a real runtime image, Python runtime, or dependency lock;
- qualify an import-graph producer or verifier;
- perform static analysis, dynamic analysis, malware scanning, or security review;
- establish `PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256`;
- establish `PHI_SANDBOX_QUALIFICATION_SHA256`;
- access model weights, providers, credentials, gated resources, GPUs, or secrets;
- serialize prompts, run inference/generation, score, rank, or select a winner;
- execute the Backbone Tournament;
- train or fine-tune a model;
- grant execution activation.

## Hard boundary

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
