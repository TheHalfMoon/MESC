# MESC Backbone Tournament — Phi Security Review Artifact Fixture 1

Status: **DRAFT / FIXTURE-ONLY CONFORMANCE VERIFIER / NO SECURITY-REVIEW OR EXECUTION AUTHORITY**

Date: 2026-08-24

## Purpose

This bounded package implements only parser/conformance verification for
caller-supplied fixture bytes shaped as the canonical Phi remote-code security-review
artifact. It does not perform a security review and does not create evidence that a
review occurred.

Canonical base:

```text
BASE_MAIN_SHA = 4cb0715de37d842f20e0281d718cd998e1c1485f
BASE_MAIN_TREE = 62a4a19e6685aa0b26591b19728955a91cba8574
PR_176 = CLOSED_CANONICAL
PHI_REACHABLE_IMPORT_GRAPH_FIXTURE_PRODUCER = CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

Exact intended scope:

```text
specs/mesc-backbone-tournament/phi-security-review-artifact-fixture-1/README.md
src/medscale/mesc/_bt_phi_security_review_artifact_fixture_v1.py
tests/test_mesc_bt_phi_security_review_artifact_fixture_v1.py
```

No workflow, dependency, lockfile, credential, provider/model, corpus, scoring-key,
prompt, runtime, real Phi source, remote-code execution, activation, tournament
result, or training path is changed.

## Canonical source contracts

Security-review artifact contract:

```text
MESC-BT-PHI-SECURITY-REVIEW-ARTIFACT-V1
specs/mesc-backbone-tournament/phi-artifact-contracts-1/security-review-artifact-contract.md
```

Reachable-import-graph artifact contract and canonical fixture verifier:

```text
MESC-BT-PHI-REACHABLE-IMPORT-GRAPH-ARTIFACT-V1
specs/mesc-backbone-tournament/phi-import-graph-contract-1/
src/medscale/mesc/_bt_phi_import_graph_fixture_v1.py
```

Canonical manifest parser:

```text
src/medscale/mesc/_bt_phi_remote_code_fixture_v1.py
```

## Implemented fixture behavior

`verify_phi_security_review_artifact_fixture(...)` accepts only caller-supplied
in-memory values:

- candidate security-review artifact bytes;
- a parser-validated canonical `PhiRemoteCodeManifest`;
- candidate reachable-import-graph artifact bytes;
- exact fixture source bytes used to reproduce that graph;
- the graph runtime binding; and
- the graph boundary policy.

The verifier then:

1. reserializes and reparses the manifest and rejects forged/stale dataclass objects;
2. reruns the canonical fixture graph verifier against the same exact fixture inputs;
3. reproduces SHA-256 over the exact validated graph bytes;
4. requires the graph's in-artifact `source_manifest_sha256` binding;
5. duplicate-safely parses the candidate security-review JSON at every object depth;
6. requires the exact top-level member set and exact scalar types/values;
7. requires literal `PASS`/JSON `true` controls frozen by the artifact contract;
8. requires `manifest_sha256` to equal the canonical manifest identity;
9. requires `reachable_import_graph_artifact_sha256` to reproduce the graph bytes;
10. requires graph `source_manifest_sha256 == artifact manifest_sha256`;
11. requires `file_dispositions` to be an exact path-for-path PASS mapping in canonical
    manifest order;
12. validates reviewer-label grammar without treating the label as authentication;
13. canonically reserializes the complete artifact and requires byte-for-byte equality;
14. returns only the validated canonical bytes and their SHA-256 identity.

The implementation intentionally has **no security-review artifact producer**. Test
helpers may construct PASS-shaped fixture bytes solely to prove conformance and
negative rejection behavior; those bytes are not evidence of a real review.

## Fail-closed fixture coverage

The test package covers the contract's required rejection families, including:

- malformed JSON, non-object top level, and non-standard constants;
- BOM, terminal newline, insignificant whitespace, and escaped ASCII;
- duplicate members at top level and inside file-disposition objects;
- missing or extra top-level/file members;
- wrong PASS/boolean scalar values or types;
- malformed or mismatched manifest and graph SHA-256 values;
- invalid reviewer labels;
- missing, extra, duplicated, reordered, malformed, traversal-like, or non-PASS file
  dispositions;
- absent/unreproducible graph artifacts;
- graph bytes lacking the required in-artifact source-manifest binding;
- changed/detached graph-manifest provenance;
- graph reproduction against changed fixture sources; and
- forged/stale manifest objects.

## Security and governance boundary

Passing this fixture verifier means only:

```text
SUPPLIED_FIXTURE_SECURITY_REVIEW_ARTIFACT_BYTES = CONTRACT_CONFORMANT
SUPPLIED_FIXTURE_GRAPH_BYTES = REPRODUCIBLE_FROM_SUPPLIED_FIXTURE_INPUTS
GRAPH_TO_MANIFEST_BINDING = PRESENT_AND_EQUAL_FOR_FIXTURE_INPUTS
```

It does **not** mean:

- the manifest was produced from real Phi source;
- the fixture graph is complete for real Phi;
- any human or tool actually reviewed any Phi file;
- the reviewer label is authenticated or independent;
- malicious behavior is absent;
- the real security-review artifact exists;
- sandbox qualification exists; or
- execution activation is satisfied.

## Qualification rule

Keep this PR Draft until one unchanged exact head has all of:

1. stable canonical base, exact three-file scope, and `behind=0`;
2. exact-head CI PASS;
3. exact-head CodeQL PASS;
4. fresh exact-head internal technical/security/governance review PASS;
5. fresh independent exact-head review with no blocker when available; and
6. zero unresolved blocking review threads.

Any head mutation burns all prior head-specific evidence. Do not mark Ready or merge
until every gate is genuinely re-proven.

## Hard boundary

```text
PHI_SECURITY_REVIEW_ARTIFACT_FIXTURE_CONFORMANCE = IMPLEMENTED_IN_THIS_DRAFT
REAL_PHI_SOURCE_READ = NOT_PERFORMED
REAL_PHI_IMPORT_GRAPH_CONSTRUCTION = NOT_PERFORMED
REAL_IMPORT_GRAPH_COMPLETENESS = NOT_ESTABLISHED
REAL_PHI_SECURITY_REVIEW = NOT_PERFORMED
REAL_PHI_SECURITY_REVIEW_ARTIFACT = NOT_PRODUCED
PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256 = NOT_ESTABLISHED_FOR_REAL_PHI
REAL_PHI_SANDBOX_QUALIFICATION = NOT_PERFORMED
REACHABLE_IMPORT_GRAPH_PRODUCER_QUALIFICATION = NOT_ESTABLISHED_FOR_REAL_PHI
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
