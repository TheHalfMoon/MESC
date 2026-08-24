# MESC Backbone Tournament — Phi Sandbox Qualification Artifact Fixture 1

Status: **DRAFT / FIXTURE-ONLY CONFORMANCE VERIFIER / NO SANDBOX OR EXECUTION AUTHORITY**

Date: 2026-08-24

## Purpose

This bounded package implements only parser/conformance verification for caller-supplied
synthetic bytes shaped as the canonical Phi sandbox-qualification artifact. It also
binds the artifact's `runtime_binding_sha256` to exact canonical fixture
`RUNTIME_BINDING` bytes using the already-canonical activation identity validator.

It does **not** configure, inspect, or qualify a sandbox. It does not issue a live
qualification challenge, maintain verifier-owned `ISSUED` state, invoke a producer,
start a model process, read real Phi source, access model weights, or grant execution
activation.

Canonical base:

```text
BASE_MAIN_SHA = e28ee5669f665661c97d2f2bd7e271a4ff22991a
BASE_MAIN_TREE = 91490447edf3c591810218b4bd314f77fbe43531
PR_177 = CLOSED_CANONICAL
PHI_SECURITY_REVIEW_ARTIFACT_FIXTURE_CONFORMANCE = CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

Exact intended scope:

```text
specs/mesc-backbone-tournament/phi-sandbox-qualification-artifact-fixture-1/README.md
src/medscale/mesc/_bt_phi_sandbox_qualification_artifact_fixture_v1.py
tests/test_mesc_bt_phi_sandbox_qualification_artifact_fixture_v1.py
```

No workflow, dependency, lockfile, credential, provider/model, corpus, scoring-key,
prompt, runtime deployment, live sandbox, activation receipt, tournament result, or
training path is changed.

## Canonical source contracts

Sandbox artifact contract:

```text
MESC-BT-PHI-SANDBOX-QUALIFICATION-ARTIFACT-V1
specs/mesc-backbone-tournament/phi-artifact-contracts-1/
    sandbox-qualification-artifact-contract.md
```

Canonical activation runtime-binding validator:

```text
src/medscale/mesc/_bt_activation_identity_fixture_v1.py
```

The sandbox contract deliberately binds to the digest of the complete canonical
activation `RUNTIME_BINDING` bytes instead of copying a partial runtime schema. This
fixture verifier therefore reuses that canonical validator and does not define a
second runtime-binding schema.

## Implemented fixture behavior

`verify_phi_sandbox_qualification_artifact_fixture(...)` accepts only:

- caller-supplied synthetic candidate sandbox artifact bytes; and
- caller-supplied synthetic candidate canonical `RUNTIME_BINDING` bytes.

The verifier then:

1. validates the exact runtime bytes with the canonical activation runtime-binding
   validator;
2. computes SHA-256 over those exact validated runtime bytes;
3. duplicate-safely parses the candidate artifact JSON at every object depth;
4. requires the exact top-level member set and canonical lexicographic member order;
5. requires the exact `controls` member set and canonical lexicographic member order;
6. requires every frozen isolation-control string exactly as specified by the
   canonical sandbox artifact contract;
7. requires all three process/timing predicates to be JSON boolean `true`;
8. validates the producer audit-label grammar without treating that label as
   authentication;
9. validates the 64-lowercase-hex `qualification_challenge` shape without claiming
   it was verifier-issued or fresh;
10. requires `qualification_disposition` to be exactly `PASS`;
11. requires `runtime_binding_sha256` to equal SHA-256 of the exact validated
    canonical runtime-binding bytes;
12. canonically reserializes the complete artifact and requires byte-for-byte
    equality; and
13. returns only the validated canonical bytes, their SHA-256 identity, and parsed
    fixture binding values useful to later fixture tests.

## Deliberately not implemented

This package intentionally does **not** implement the live challenge lifecycle
required before activation reliance:

```text
ISSUED -> CONSUMED
ISSUED -> CANCELLED
```

It does not:

- obtain 32 bytes from an operating-system cryptographically secure RNG;
- issue or own a run-scoped challenge;
- bind a challenge to a live producer invocation handle;
- authenticate `producer_identity`;
- track verifier-process state;
- reject replay by consulting live `ISSUED`/`CONSUMED`/`CANCELLED` state;
- invoke or monitor a sandbox qualification producer;
- observe network, DNS, metadata, credentials, sockets, mounts, writable paths, or
  process timing;
- establish that any isolation control is actually active.

Those live-verifier and producer responsibilities remain separately required before
activation reliance. A conformance PASS from this package is not sandbox
qualification evidence.

## Fail-closed fixture coverage

The test package covers conformance rejection for:

- malformed JSON, non-object top level, and non-standard constants;
- BOM, trailing newline, insignificant whitespace, escaped ASCII, and noncanonical
  key ordering;
- duplicate JSON members at top level and inside `controls`;
- missing or extra top-level members;
- missing or extra control members;
- wrong top-level scalar values or JSON types;
- invalid producer labels;
- malformed, uppercase, non-string, or otherwise invalid qualification challenges;
- every frozen isolation-control value mismatch;
- absent, malformed, or noncanonical `RUNTIME_BINDING` bytes;
- independently recomputed runtime-binding digest mismatch; and
- malformed artifact `runtime_binding_sha256`.

Replay, wrong-live-producer, cancelled-run, prior-process, producer-issued challenge,
and atomic consume semantics are intentionally **not claimed** by these parser-only
tests. They remain required negative fixtures for the future live challenge verifier.

## Security and governance boundary

Passing this verifier means only:

```text
SUPPLIED_FIXTURE_SANDBOX_ARTIFACT_BYTES = CONTRACT_CONFORMANT
SUPPLIED_FIXTURE_RUNTIME_BINDING_BYTES = CANONICAL
ARTIFACT_RUNTIME_BINDING_SHA256 = REPRODUCED_FROM_SUPPLIED_FIXTURE_RUNTIME_BYTES
```

It does **not** mean:

- the runtime binding represents a real deployed runtime;
- the challenge was verifier-issued, fresh, secret, or bound to a live invocation;
- the producer identity is authenticated;
- any sandbox control was observed or enforced;
- a model process exists;
- a real sandbox qualification artifact exists;
- `PHI_SANDBOX_QUALIFICATION_SHA256` is established for real execution; or
- execution activation is satisfied.

## Qualification rule

Keep this PR Draft until one unchanged exact head has all of:

1. stable canonical base, exact three-file scope, and `behind=0`;
2. exact-head CI PASS;
3. exact-head CodeQL PASS;
4. fresh exact-head internal technical/security/governance review PASS;
5. fresh independent exact-head review with no blocker; and
6. zero unresolved blocking review threads.

Any head mutation burns all prior head-specific evidence. Do not merge until every
gate is genuinely re-proven on the same exact head.

## Hard boundary

```text
PHI_SANDBOX_QUALIFICATION_ARTIFACT_FIXTURE_CONFORMANCE = IMPLEMENTED_IN_THIS_DRAFT
PHI_SANDBOX_LIVE_PRODUCER = NOT_IMPLEMENTED
PHI_SANDBOX_CHALLENGE_VERIFIER = NOT_IMPLEMENTED
PHI_SANDBOX_REPLAY_NEGATIVE_FIXTURES = NOT_IMPLEMENTED
REAL_SANDBOX_QUALIFICATION_FRESHNESS = NOT_ESTABLISHED
REAL_PHI_SANDBOX_QUALIFICATION = NOT_PERFORMED
PHI_SANDBOX_QUALIFICATION_SHA256 = NOT_ESTABLISHED_FOR_REAL_PHI
REAL_PHI_SOURCE_READ = NOT_PERFORMED
REAL_PHI_IMPORT_GRAPH_CONSTRUCTION = NOT_PERFORMED
REAL_PHI_SECURITY_REVIEW = NOT_PERFORMED
REAL_ACTIVATION_PACKAGE_READ = NOT_PERFORMED
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
