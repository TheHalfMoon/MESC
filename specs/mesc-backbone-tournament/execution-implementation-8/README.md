# MESC Backbone Tournament — Execution Implementation 8

Status: **DRAFT / FIXTURE-ONLY PHI RUNTIME IDENTITY EVIDENCE VERIFIER / NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded implementation slice closes one fixture-level part of the
`FD-MESC-BT-EXEC-1` Section C.3 trusted-acquisition gap left deliberately open
by Execution Implementation 6.

Canonical base for this slice:

```text
BASE_MAIN_SHA = 3438f0a056fa036570365bccefdfdc7de1069bf5
BASE_MAIN_TREE = 1d515f73f162ac35f72c5ddc5497bcb6394b60e6
PR_150 = CLOSED_CANONICAL
IMPLEMENTATION_7_CANONICAL_QUALIFICATION =
    REPAIRED_BY_POST_MERGE_ADOPTION_RECORD
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-8/README.md
src/medscale/mesc/_bt_phi_runtime_identity_fixture_v1.py
tests/test_mesc_bt_phi_runtime_identity_fixture_v1.py
```

No dependency, lockfile, workflow, credential, provider, model-weight,
tokenizer, processor, corpus, prompt, scoring-key, real Phi source,
runtime-acquisition implementation, sandbox implementation, or execution-result
path is changed.

## Canonical source contract

Section C.3 requires the trusted acquisition verifier to resolve each acquired
Phi runtime code path descriptor-relatively from an approved read-only input
root and open it without following symlinks using:

```text
openat2(2)
RESOLVE_BENEATH
RESOLVE_NO_SYMLINKS
RESOLVE_NO_MAGICLINKS
O_RDONLY
O_CLOEXEC
O_NOFOLLOW
```

`fstat` on the exact opened descriptor must report a regular file. The exact
opened runtime object must match the canonical manifest byte length and SHA-256.
The model process must later import that same immutable object, or an object
whose identity is mechanically proven to be the same verified inode and bytes
on an immutable read-only mount immediately before import.

This slice implements only a pure verifier for injected evidence representing
those facts. It intentionally validates the exact `openat2` branch and the
same-inode/same-bytes immutable-read-only-handoff branch of the contract; it
does not attempt to qualify a separately reviewed equivalent or a same-open-file
descriptor handoff.

## Implemented fixture contract

The verifier:

- accepts only a parser-validated `PhiRemoteCodeManifest` from Execution
  Implementation 6 and revalidates its canonical bytes before any resolver call;
- resolves injected evidence once per canonical manifest path;
- requires exact path equality and `open_api = openat2`;
- requires the exact resolve-flag set
  `RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS`;
- requires the exact open-flag set `O_RDONLY | O_CLOEXEC | O_NOFOLLOW`;
- requires both flag containers to be exact `frozenset` objects and every flag
  member to have exact type `str`, preventing hash/equality-compatible objects
  from spoofing required flag names;
- requires exact-boolean evidence that resolution was descriptor-relative, the
  input root was approved and read-only, and `fstat` reported a regular file;
- rejects Python bool/int confusion for device, inode, and byte-length identity
  fields;
- requires non-negative device identifiers and positive inode identifiers;
- requires the verified runtime byte length and lowercase SHA-256 to equal the
  canonical manifest entry;
- requires handoff device, inode, byte length, and SHA-256 to equal the exact
  verified runtime object;
- requires the handoff mount to be both read-only and immutable;
- requires the identity check to be recorded as immediately before import;
- wraps resolver failures and malformed evidence in a typed fail-closed error
  surface.

The module performs no system call and obtains no filesystem facts itself. All
observations are caller-supplied fixture evidence from a separately reviewed
future acquisition/handoff layer.

## Deliberate non-claims

This slice does **not** call `openat2(2)`, `open(2)`, `fstat(2)`, hash a real
file, mount a filesystem, inspect a real inode, or acquire any Phi object.
Therefore it does not prove that a future runtime actually used the claimed
syscalls or flags; it proves only that supplied evidence satisfies this closed
fixture contract.

The boolean `handoff_mount_immutable` field is evidence supplied by a future
trusted acquisition/handoff layer. This fixture validates that the evidence is
present and exact; it does not establish mount immutability by itself.

It does not:

- inspect, download, clone, or otherwise access the real
  `microsoft/Phi-4-multimodal-instruct` repository or model files;
- establish a production `PHI_REMOTE_CODE_MANIFEST_SHA256`;
- establish completeness of the remote-code file set or import graph;
- establish `PHI_REMOTE_CODE_SECURITY_REVIEW = PASS` or its digest;
- execute or import remote code;
- prove the model process imported the verified object;
- establish sandbox, network, credential, or process-isolation controls;
- establish `PHI_SANDBOX_QUALIFICATION_SHA256`;
- establish gated-access authority or any access attestation;
- establish live H100 telemetry qualification;
- establish final activation receipt validity;
- integrate a production executor;
- serialize a prompt, run inference/generation, score, rank, select a winner, or
  execute the tournament;
- grant execution authority.

A future trusted acquisition implementation must itself receive separate review
and must produce mechanically trustworthy observations from the exact runtime
objects. This fixture cannot substitute for that implementation or review.

## Hard boundary

```text
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

Keep any PR for this slice Draft until GitHub-native scope reconciliation,
fresh exact-head CI, fresh exact-head CodeQL, fresh exact-head internal
technical/security review, at least one independent external exact-head review,
and zero unresolved blocking review threads are all proven. Any head mutation
burns prior head-specific qualification evidence.
