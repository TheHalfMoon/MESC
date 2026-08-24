# MESC Backbone Tournament — Phi Import Graph Producer Fixture 1

Status: **DRAFT / FIXTURE-ONLY PRODUCER QUALIFICATION / NO REAL PHI SOURCE AUTHORITY**

Date: 2026-08-24

## Canonical base

```text
BASE_MAIN_SHA = ac1d42f7fab38a51a68f394d5f8006ffdf946fa3
BASE_MAIN_TREE = be7c1d9305bd4c6d6e1df3f751d10f4c14273e56
PR_175 = CLOSED_CANONICAL
PHI_REACHABLE_IMPORT_GRAPH_ARTIFACT_CONTRACT_1 = CANONICAL
FD_MESC_BT_EXEC_1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

`execution-authorization-1/plan.md` permits separately reviewed Phase 2 implementation
and qualification with fixtures/mocks only and no model-weight access. Canonical
`phi-import-graph-contract-1/acceptance.md` requires the future producer implementation
to be a separate package with fail-closed negative fixtures before activation may rely
on a graph digest.

This package implements the smallest fixture-only producer slice after PR #175. It does
not read, download, inspect, or construct a graph from real Phi source and therefore does
not establish real-Phi producer qualification or real graph completeness.

## Exact intended scope

Exactly:

```text
specs/mesc-backbone-tournament/phi-import-graph-producer-fixture-1/README.md
src/medscale/mesc/_bt_phi_import_graph_fixture_v1.py
tests/test_mesc_bt_phi_import_graph_fixture_v1.py
```

No workflow, dependency, lockfile, provider/model, credential, corpus, scoring-key,
prompt, runtime-state, activation-receipt, execution-result, or training path changes.

## Fixture producer boundary

The producer accepts only:

1. an already parser-validated canonical `PhiRemoteCodeManifest`;
2. an exact in-memory `dict[str, bytes]` whose paths, byte lengths, and SHA-256 values
   match that manifest;
3. exact fixture `base_container_oci_digest`, `python_version`, and
   `dependency_lock_sha256` identity values; and
4. a closed, sorted, non-overlapping fixture policy classifying Python-runtime and
   locked-dependency module roots.

It performs no filesystem traversal, repository/model fetch, network access, process
launch, source import/execution, model access, prompt serialization, inference,
generation, scoring, ranking, winner selection, tournament execution, training, or
fine-tuning.

## Reviewed source grammar

The fixture producer deliberately uses a closed allowlist rather than attempting to
blacklist every possible Python dynamic-import or reflection mechanism.

After UTF-8 decoding and `ast.parse`, every top-level source statement must be exactly
one of:

```text
ast.Import
ast.ImportFrom
```

Any other top-level statement is `BLOCKED`, including function/class definitions,
assignments, expression statements/calls, control flow, runtime code generation,
dynamic-import calls, import-state mutation, executable module docstrings, or any future
Python construct outside this two-statement allowlist.

Comments are not executable AST statements and therefore do not expand the accepted
source grammar.

This restriction is intentionally narrower than general Python. Passing fixture tests
under this grammar does **not** prove that real Phi source fits the grammar. Real Phi
source remains unread and unqualified.

## Extraction and resolution behavior

For accepted fixture inputs, the producer:

- maps every manifest `.py` path deterministically to one absolute Python module identity;
- parses fixture bytes with Python `ast` without importing or executing them;
- extracts only top-level static `import` and `from ... import ...` relationships;
- resolves relative imports from the source module/package identity;
- maps exact manifested targets to `MANIFEST_FILE` nodes;
- maps only explicitly classified runtime/dependency names to terminal
  `PYTHON_RUNTIME_MODULE` or `LOCKED_DEPENDENCY_MODULE` nodes;
- blocks unknown or ambiguous targets instead of guessing;
- blocks remote package submodules that are not themselves manifested;
- blocks remote star imports whose target is a remote manifest module;
- emits unique deterministic node/edge sets in canonical order; and
- emits exact canonical ASCII JSON bytes for
  `MESC-BT-PHI-REACHABLE-IMPORT-GRAPH-ARTIFACT-V1` with empty
  `unresolved_imports` and `unresolved_dynamic_imports` arrays.

The verifier duplicate-safely parses supplied artifact bytes, requires exact canonical
JSON reserialization, reruns the fixture producer from the same exact inputs, and
requires byte-for-byte equality. Therefore omitted relationships, spurious
relationships, altered roots/nodes/edges/bindings, malformed/duplicate/noncanonical
JSON, non-empty unresolved arrays, or any other artifact mutation cannot pass fixture
verification.

This verifier is intentionally bound to this producer's fixture qualification. It is not
a claim that a production activation parser or a real-Phi source/runtime producer has
been qualified.

## Negative fixture qualification

The tests exercise fail-closed cases including:

- any source statement outside the import-only allowlist, including nested imports,
  dynamic-import/code-loading calls, assignments/import-state mutation, control flow,
  function/class definitions, and ordinary executable expressions;
- unknown imports and ambiguous/missing remote-package targets;
- relative-import escape and remote star imports;
- source-set or source-identity mismatch and forged manifest identity;
- unsupported manifest-to-module paths;
- malformed runtime identities and overlapping/ambiguous boundary policy;
- BOM, trailing newline, duplicate JSON members, and noncanonical artifact bytes;
- manifest/runtime/unresolved-field artifact mutations;
- missing or extra graph nodes/relationships; and
- omitted and spurious producer relationships that remain otherwise canonical JSON.

Passing these fixtures qualifies only the bounded extraction/reproduction mechanics in
this package. It does not prove that real Phi source fits the accepted import-only subset,
that all real Phi import mechanisms are covered, or that a real Phi graph is complete.

## Qualification rule

Keep the PR Draft until one unchanged exact head has all of:

1. stable canonical base, exact three-file scope, and `behind=0`;
2. exact-head CI PASS;
3. exact-head CodeQL PASS;
4. fresh exact-head internal technical/security/governance review PASS;
5. fresh independent exact-head review with no blocker; and
6. zero unresolved technical/security/contract/governance blocker threads.

Any head mutation burns all head-specific qualification evidence. Do not mark Ready or
merge until every exact-head gate is genuinely re-proven.

## Deliberate non-claims

This package does **not**:

- read, download, clone, inspect, or construct a graph from real Phi source;
- establish a real `PHI_REMOTE_CODE_MANIFEST` or real graph digest;
- prove that real Phi source fits the fixture producer's accepted import-only subset;
- establish real source/runtime identity qualification;
- perform the independent Phi remote-code security review;
- establish `PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256`;
- qualify a real Phi sandbox or establish `PHI_SANDBOX_QUALIFICATION_SHA256`;
- access model weights, gated resources, providers, credentials, or secrets;
- import or execute Phi remote code;
- serialize prompts, infer, generate, score, rank, select a winner, execute the Backbone
  Tournament, train, or fine-tune; or
- grant execution activation.

## Hard boundary

```text
PHI_IMPORT_GRAPH_FIXTURE_PRODUCER_IMPLEMENTATION = PRESENT_IN_THIS_DRAFT
PHI_IMPORT_GRAPH_FIXTURE_PRODUCER_QUALIFICATION = PENDING_EXACT_HEAD_GATES
REACHABLE_IMPORT_GRAPH_PRODUCER_QUALIFICATION = NOT_ESTABLISHED_FOR_REAL_PHI
REAL_PHI_SOURCE_READ = NOT_PERFORMED
REAL_PHI_IMPORT_GRAPH_CONSTRUCTION = NOT_PERFORMED
REAL_IMPORT_GRAPH_COMPLETENESS = NOT_ESTABLISHED
REAL_PHI_SECURITY_REVIEW = NOT_PERFORMED
REAL_PHI_SANDBOX_QUALIFICATION = NOT_PERFORMED
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
