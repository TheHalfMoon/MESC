# Phi Sandbox Challenge Verifier Fixture 1

Status: **DRAFT IMPLEMENTATION / FIXTURE-ONLY / NO LIVE SANDBOX QUALIFICATION**

Canonical base:

```text
BASE_MAIN_SHA = 7461b2dbcee892206557f948df34bc4444c6d8f8
BASE_MAIN_TREE = 9ce73c353f78ca8e0824e53a14b52ce04d3b30ec
PR_178 = CLOSED_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

## Purpose

The canonical `MESC-BT-PHI-SANDBOX-QUALIFICATION-ARTIFACT-V1` contract requires a
future verifier-owned run-scoped freshness lifecycle in addition to byte-level
artifact conformance. PR #178 canonicalized only the fixture artifact parser and
runtime-binding digest reproduction. It deliberately did not implement challenge
state.

This package adds the smallest separately reviewable fixture implementation of the
challenge state machine required for negative conformance qualification:

```text
ISSUED -> CONSUMED
ISSUED -> CANCELLED
```

The implementation is current-process in-memory state only. It does not persist or
reconstruct an `ISSUED` record from artifact bytes, operator input, or any external
store.

## Exact scope

This package changes exactly three paths:

```text
specs/mesc-backbone-tournament/phi-sandbox-challenge-verifier-fixture-1/README.md
src/medscale/mesc/_bt_phi_sandbox_challenge_verifier_fixture_v1.py
tests/test_mesc_bt_phi_sandbox_challenge_verifier_fixture_v1.py
```

No workflow, dependency, lockfile, runtime, activation receipt, provider, model,
corpus, prompt, scoring key, or training path is changed.

## Fixture verifier semantics

`PhiSandboxChallengeVerifierFixture` owns one in-memory challenge ledger for its
Python object lifetime.

### Issue

`issue(...)`:

1. requires an exact 64-lowercase-hex already-fixed fixture
   `runtime_binding_sha256`;
2. requires the frozen `producer_identity` grammar;
3. requires an exact opaque `PhiSandboxProducerInvocationFixture` token;
4. obtains exactly 32 bytes through `secrets.token_bytes(32)` inside the verifier;
5. requires the returned value to be exact built-in `bytes` of length 32;
6. lower-hex encodes those bytes to the 64-character challenge;
7. rejects a challenge collision with any current-process challenge history;
8. rejects reuse of one fixture invocation token after any prior issue; and
9. records the challenge as `ISSUED`, bound to the runtime digest, producer label,
   and exact fixture invocation object identity.

The public issue API has no caller-supplied challenge parameter. This proves the
fixture implementation owns challenge generation. It does **not** prove challenge
generation happened immediately before a real producer process start because no
producer process is started by this package.

### Consume

`consume(...)` first requires a current `ISSUED` record for the exact fixture
invocation identity. It then reuses the canonical
`verify_phi_sandbox_qualification_artifact_fixture(...)` implementation from
PR `#178` to validate the supplied artifact bytes and exact fixture runtime-binding
bytes.

Only after artifact conformance passes does the lifecycle verifier require exact
equality of:

```text
artifact.qualification_challenge == ISSUED.challenge
artifact.runtime_binding_sha256 == ISSUED.runtime_binding_sha256
artifact.producer_identity == ISSUED.producer_identity
producer_invocation is ISSUED.producer_invocation
```

The final `ISSUED -> CONSUMED` transition occurs under the verifier lock before the
validated artifact is returned. A replay therefore cannot obtain a second
successful consume from the same record.

If artifact conformance fails, or the challenge/runtime/producer binding fails,
the still-current record is transitioned to `CANCELLED` before the verifier
returns a fail-closed error.

### Cancel

`cancel(...)` atomically transitions only an `ISSUED` record for the exact fixture
invocation to `CANCELLED`. A consumed or already-cancelled record cannot be
reopened, cancelled again, or reissued.

## Required fixture negatives covered here

The test package proves `BLOCKED` behavior for:

- replay after `CONSUMED`;
- explicit `CANCELLED` challenge presentation;
- wrong fixture producer invocation identity;
- wrong `qualification_challenge`;
- wrong runtime-binding digest despite a separately valid supplied runtime;
- wrong producer label;
- malformed/nonconforming artifact after issue, with cancellation of the record;
- duplicate CSPRNG challenge collision in current-process history;
- invocation-history reuse after cancellation;
- prior verifier object/process state not reconstructed from artifact bytes;
- detached prior artifact against a later challenge even when the runtime digest
  repeats;
- malformed or non-lowercase runtime digest / producer grammar;
- noncanonical challenge lookup; and
- malformed CSPRNG return shape.

## Deliberate unresolved live requirements

This package does **not** satisfy the complete live-verifier or producer contract.
The following remain required before activation reliance:

```text
PHI_SANDBOX_LIVE_PRODUCER = REQUIRED_BEFORE_ACTIVATION_RELIANCE
PHI_SANDBOX_LIVE_INVOCATION_HANDLE_BINDING = REQUIRED_BEFORE_ACTIVATION_RELIANCE
PHI_SANDBOX_CHALLENGE_TO_PROCESS_START_TIMING_PROOF = REQUIRED_BEFORE_ACTIVATION_RELIANCE
PHI_SANDBOX_LIVE_PROCESS_EXIT_OBSERVATION = REQUIRED_BEFORE_ACTIVATION_RELIANCE
PHI_SANDBOX_LIVE_ISOLATION_MEASUREMENT = REQUIRED_BEFORE_ACTIVATION_RELIANCE
REAL_SANDBOX_QUALIFICATION_FRESHNESS = NOT_ESTABLISHED
REAL_PHI_SANDBOX_QUALIFICATION = NOT_PERFORMED
PHI_SANDBOX_QUALIFICATION_SHA256 = NOT_ESTABLISHED_FOR_REAL_PHI
EXECUTION_ACTIVATION = REQUIRED
```

The opaque fixture invocation token proves only identity-binding state-machine
behavior. It is not a subprocess handle and does not prove that any process exists,
is live, exited, failed, or was isolated.

`secrets.token_bytes(32)` implements verifier-owned CSPRNG generation in this
fixture package. This does not prove the required temporal relationship to a live
producer invocation, because no live producer is launched.

## Security and execution non-claims

This package performs no:

- real Phi source read, download, clone, or inspection;
- filesystem traversal or sandbox construction;
- provider or credential access;
- model-weight access or retrieval;
- gated-access request or acceptance;
- Phi remote-code import or execution;
- model process launch;
- prompt serialization;
- inference or generation;
- scoring, ranking, or winner selection;
- Backbone Tournament execution;
- training or fine-tuning.

A fixture lifecycle PASS is not a real sandbox qualification and grants no
execution authority.

## Qualification gate

Keep the PR Draft until one unchanged exact head has all of:

1. canonical base remains `7461b2dbcee892206557f948df34bc4444c6d8f8` or a
   separately reviewed reconciliation is performed;
2. base-to-head `behind=0` and exactly the three intended paths above;
3. exact-head CI PASS on the repository Python matrix;
4. exact-head CodeQL PASS;
5. fresh exact-head internal technical/security/governance review PASS;
6. fresh independent exact-head review with no blocker; and
7. zero unresolved technical/security/governance review threads.

Any head mutation burns all head-specific qualification evidence. Ready and merge
must not be inferred from a generic implementation-completion signal.

## Hard authority boundary

```text
REAL_PHI_SOURCE_READ = NOT_PERFORMED
REAL_PHI_IMPORT_GRAPH_CONSTRUCTION = NOT_PERFORMED
REAL_PHI_SECURITY_REVIEW = NOT_PERFORMED
REAL_PHI_SANDBOX_QUALIFICATION = NOT_PERFORMED
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
