# Phi Sandbox Qualification Artifact Contract

Status: **DRAFT GOVERNANCE CONTRACT CANDIDATE / NO SANDBOX-QUALIFICATION CLAIM**

Contract ID:

```text
MESC-BT-PHI-SANDBOX-QUALIFICATION-ARTIFACT-V1
```

## Purpose

`FD-MESC-BT-EXEC-1` requires a future `PHI_SANDBOX_QUALIFICATION_SHA256`
artifact proving the required model-process isolation controls on the exact
runtime. Execution Implementation 11 validates only injected fixture evidence
and deliberately leaves production artifact bytes undefined.

The activation identity layer already defines one canonical `RUNTIME_BINDING`
whose complete byte schema covers the provider, hardware, container, dependency,
checkout-root object identity, repository-result-parent object identity, checkout
SHA/tree, and sequential single-GPU execution predicates. This contract does not
redeclare any subset of that runtime schema. Instead it binds the sandbox
qualification to the SHA-256 of those exact validated canonical runtime-binding
bytes.

This contract also defines a verifier-issued run-scoped challenge so live
qualification evidence cannot be accepted merely because an older artifact binds
the same runtime. The challenge is freshness evidence only; it is not an
execution authorization, credential, or substitute for producer trust.

This contract freezes only deterministic sandbox-qualification artifact bytes and
the fail-closed verifier semantics required to bind those bytes to one live
qualification producer invocation. It does not configure or inspect a sandbox and
does not establish any live observation.

## Canonical JSON value

The top-level value is an object with exactly these keys, serialized in this
lexicographic ASCII order:

```text
artifact_version
controls
controls_active_before_model_load
controls_active_before_remote_code_import
dedicated_model_process
producer_identity
qualification_challenge
qualification_disposition
runtime_binding_sha256
```

### Top-level scalar fields

```text
artifact_version = MESC-BT-PHI-SANDBOX-QUALIFICATION-ARTIFACT-V1
dedicated_model_process = true
controls_active_before_remote_code_import = true
controls_active_before_model_load = true
producer_identity = ^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$
qualification_challenge = ^[0-9a-f]{64}$
qualification_disposition = PASS
runtime_binding_sha256 = ^[0-9a-f]{64}$
```

`producer_identity` is an audit label only. It does not authenticate the producer
or prove that the producer is trustworthy.

`qualification_challenge` is a verifier-issued freshness value. It is not an
authorization secret and possession of it grants no access or execution authority.

## Exact runtime binding

`runtime_binding_sha256` must equal the 64-character lowercase ASCII hexadecimal
representation of:

```text
SHA256(exact_validated_canonical_RUNTIME_BINDING_bytes)
```

where `RUNTIME_BINDING` is the complete canonical activation runtime-binding
object defined by `FD-MESC-BT-EXEC-1` and the already-canonical activation
identity verifier.

A future sandbox artifact verifier must not accept `runtime_binding_sha256` as a
self-asserted detached digest. Before the sandbox artifact can support activation,
the activation path must independently:

1. obtain the exact candidate `RUNTIME_BINDING` bytes through the separately
   reviewed activation producer;
2. parse them with the canonical duplicate-member-rejecting runtime-binding
   validator;
3. prove every complete runtime-binding predicate, including exact member set and
   ordering;
4. canonically reserialize and require byte-for-byte equality;
5. recompute SHA-256 from those exact validated bytes and encode the result as
   exactly 64 lowercase ASCII hexadecimal characters; and
6. require exact equality to this artifact's `runtime_binding_sha256`.

Missing, stale, malformed, partial, differently serialized, or unreproducible
runtime-binding bytes, or any digest mismatch, => `BLOCKED`.

This digest indirection is deliberate: the sandbox artifact cannot drift from the
full canonical runtime schema by copying only a subset of runtime fields.

## Run-scoped freshness binding

A matching `runtime_binding_sha256` is necessary but not sufficient for live
qualification freshness because separate activation attempts may legitimately use
the same validated runtime. Before a live sandbox qualification artifact can
support activation, the future activation verifier must implement this exact
fail-closed challenge lifecycle:

1. first complete the full `RUNTIME_BINDING` validation and fix the exact
   `runtime_binding_sha256`;
2. immediately before starting exactly one live qualification producer invocation,
   obtain exactly 32 bytes from an operating-system cryptographically secure
   random generator and encode those bytes as exactly 64 lowercase ASCII
   hexadecimal characters named `qualification_challenge`;
3. create verifier-owned current-process state for that one producer invocation
   with status `ISSUED`, binding the exact `qualification_challenge`, exact
   `runtime_binding_sha256`, exact expected `producer_identity`, and the verifier's
   live handle for that specific producer invocation;
4. pass that exact challenge to only that producer invocation through the
   verifier-controlled invocation channel; an operator-supplied, producer-chosen,
   previously observed, or pre-existing challenge is invalid;
5. require the returned canonical artifact to contain exact equality for
   `qualification_challenge`, `runtime_binding_sha256`, and `producer_identity`
   against the still-`ISSUED` verifier record, and require the bound producer
   invocation to still be the same live invocation;
6. after all artifact, runtime, isolation-control, and producer-invocation checks
   pass, atomically transition that verifier record from `ISSUED` to `CONSUMED`
   **before** exposing sandbox qualification PASS to the activation path; and
7. on producer exit, cancellation, timeout/failure owned by the future producer
   contract, verifier restart, artifact rejection, or any other unsuccessful end
   of that invocation, treat its issued challenge as `CANCELLED` or unknown and
   never accept it later.

Only a challenge in the verifier's current live `ISSUED` record for the exact
runtime and exact producer invocation can satisfy freshness. A challenge that is
unknown, copied from another invocation, bound to another runtime, already
`CONSUMED`, `CANCELLED`, supplied before issuance, or presented after the bound
producer invocation is no longer live => `BLOCKED`.

A verifier restart must not reconstruct an `ISSUED` record from artifact bytes or
operator input. Therefore artifacts from a prior verifier process are unknown and
fail closed unless a separately reviewed future contract explicitly replaces this
mechanism.

`qualification_challenge` must not be derived from `<ACTIVATION_ID>`, and
`<ACTIVATION_ID>` must not be required to issue the challenge. This avoids a
circular dependency because the existing activation identity preimage already
binds `phi_sandbox_qualification_sha256`; the artifact digest is established
before the canonical activation identifier is derived.

This run-scoped challenge does not authenticate the producer. Producer trust,
process ownership, and live isolation measurement remain separate prerequisites.

## Exact isolation controls

`controls` is an object with exactly these keys and values, in lexicographic ASCII
key order:

```text
cloud_metadata_access = DENIED
credential_environment = EMPTY
dns = UNAVAILABLE_TO_MODEL_PROCESS
frozen_gold_scoring_inputs_visible_to_model_process = NO
host_or_container_control_sockets = NONE
model_and_runtime_input_mounts = READ_ONLY_ALLOWLIST_ONLY
network_egress = DENY_ALL
network_ingress = DENY_ALL
remote_fetch_during_model_process = PROHIBITED
writable_paths = ACTIVATION_SCOPED_SCRATCH_AND_OUTPUT_ONLY
```

All control values are exact JSON strings containing the literal ASCII bytes
shown above. No aliases, case folding, escape sequences, or additional controls
are accepted by this V1 contract.

The three process/timing predicates at top level must be JSON booleans equal to
`true`, and `qualification_disposition` must be exactly `PASS`.

## Canonical byte rules

The exact artifact bytes are:

- UTF-8 without BOM;
- one top-level JSON object;
- duplicate JSON member names prohibited at every depth;
- exact member sets at top level and `controls`;
- object keys sorted lexicographically by literal ASCII bytes;
- JSON separators exactly `,` and `:`;
- no insignificant whitespace;
- no JSON escape sequences in literal-ASCII fields;
- no trailing newline.

A duplicate-member-rejecting parser must parse the supplied bytes. The verifier
must validate every member set, type, grammar, frozen control value, ordering
rule, challenge shape, and runtime-binding digest shape, then canonically
reserialize and require byte-for-byte equality before accepting the artifact
digest.

Only those validated canonical bytes may be hashed. The published identifier is
exactly 64 lowercase ASCII hexadecimal characters:

```text
PHI_SANDBOX_QUALIFICATION_SHA256 = lowercase_hex(SHA256(exact_validated_artifact_bytes))
```

## Required negative conformance fixtures

A future parser/conformance and live-verifier implementation must prove `BLOCKED`
for at least:

- malformed JSON;
- BOM or trailing newline;
- duplicate member at top level or inside `controls`;
- extra or missing member at any level;
- wrong JSON scalar/container type;
- noncanonical key order or whitespace;
- JSON escape sequence in a literal-ASCII field;
- malformed or non-lowercase-hex `runtime_binding_sha256`;
- malformed or non-lowercase-hex `qualification_challenge`;
- any isolation-control value mismatch;
- any process/timing predicate other than JSON boolean `true`;
- qualification disposition other than `PASS`;
- absent or noncanonical `RUNTIME_BINDING` bytes;
- independently recomputed runtime-binding digest mismatch;
- no current verifier-owned `ISSUED` record for the artifact's challenge;
- an `ISSUED` challenge bound to a different `runtime_binding_sha256`;
- an `ISSUED` challenge bound to a different `producer_identity` or producer
  invocation;
- a challenge generated or supplied by the producer or operator instead of the
  verifier;
- replay of the same artifact or challenge after the record becomes `CONSUMED`;
- presentation of a `CANCELLED`, unknown, prior-process, or prior-invocation
  challenge;
- producer exit or failure before the verifier atomically consumes the challenge;
- detached prior qualification evidence presented against a later activation
  that happens to reproduce the same runtime-binding digest.

## Live evidence boundary

A canonical artifact parser can prove only that supplied bytes satisfy this
format. Activation still requires a separately reviewed live qualification
producer that measures the exact runtime and proves the isolation controls were
active for the complete required model-process window.

The activation package must bind the exact
`PHI_SANDBOX_QUALIFICATION_SHA256` derived from these artifact bytes to the exact
validated runtime used by that activation **and** the future activation verifier
must prove the run-scoped `qualification_challenge` lifecycle above. Replayed,
stale, incomplete, or detached qualification evidence, a challenge without the
matching current `ISSUED` verifier record, or evidence whose bound runtime digest
cannot be reproduced from the activation runtime remains `BLOCKED`.

A parser PASS with untrusted, incomplete, stale, replayed, or detached
qualification evidence is not a sandbox qualification and must not activate
execution.

## Non-claims

Conformance to this byte format does not prove:

- a provider instance or GPU exists;
- the bound `RUNTIME_BINDING` reflects a real measured environment;
- the verifier challenge lifecycle is implemented or has run;
- network ingress/egress is actually denied;
- DNS, metadata, credentials, secrets, or control sockets are actually absent;
- mounts or writable paths are actually restricted;
- a model process was started;
- Phi remote code or model weights were accessed;
- any prompt was serialized;
- execution activation passed.
