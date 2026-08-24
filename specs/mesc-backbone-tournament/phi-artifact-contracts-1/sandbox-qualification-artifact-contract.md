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

This contract freezes a deterministic serialization for a future qualification
producer. It does not configure or inspect a sandbox and does not establish any
live observation.

## Canonical JSON value

The top-level value is an object with exactly these keys:

```text
artifact_version
controls
controls_active_before_model_load
controls_active_before_remote_code_import
dedicated_model_process
producer_identity
qualification_disposition
runtime_identity
```

### Top-level scalar fields

```text
artifact_version = MESC-BT-PHI-SANDBOX-QUALIFICATION-ARTIFACT-V1
dedicated_model_process = true
controls_active_before_remote_code_import = true
controls_active_before_model_load = true
qualification_disposition = PASS
producer_identity = ^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$
```

`producer_identity` is an audit label only. It does not authenticate the producer
or prove that the producer is trustworthy.

## Exact runtime identity

`runtime_identity` is an object with exactly these keys:

```text
acceleration_runtime_identities
base_container_oci_digest
cuda_runtime_version
dependency_lock_sha256
gpu_model
gpu_uuid
nvidia_driver_version
provider_instance_or_pod_id
provider_region
python_version
pytorch_version
repository_checkout_sha
repository_checkout_tree
transformers_identity
```

The required values and grammars are:

```text
provider_region = non-empty ASCII string, length <= 255
provider_instance_or_pod_id = non-empty ASCII string, length <= 255
gpu_uuid = non-empty ASCII string, length <= 255
gpu_model = NVIDIA H100 80GB HBM3
nvidia_driver_version = non-empty ASCII string, length <= 255
cuda_runtime_version = non-empty ASCII string, length <= 255
base_container_oci_digest = ^sha256:[0-9a-f]{64}$
python_version = non-empty ASCII string, length <= 255
pytorch_version = non-empty ASCII string, length <= 255
transformers_identity = non-empty ASCII string, length <= 512
acceleration_runtime_identities = non-empty array of unique non-empty ASCII strings
                               sorted ascending by literal ASCII bytes
dependency_lock_sha256 = ^[0-9a-f]{64}$
repository_checkout_sha = ^[0-9a-f]{40}$
repository_checkout_tree = ^[0-9a-f]{40}$
```

For every free-form ASCII identity field above, permitted bytes are printable
ASCII `0x21..0x7e` except `"` and `\`. JSON escape sequences are therefore
prohibited. Empty strings, leading/trailing ASCII whitespace, control bytes, and
non-ASCII bytes are invalid.

This contract intentionally binds the runtime identity names already required by
`FD-MESC-BT-EXEC-1`. It does not infer or fabricate their live values.

Before this artifact can support activation, the activation verifier must
independently prove that `repository_checkout_sha` resolves to
`repository_checkout_tree` and that every other runtime identity equals the
separately measured activation environment. The artifact is not self-attesting.

## Exact isolation controls

`controls` is an object with exactly these keys and values:

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
`true` and `qualification_disposition` must be exactly `PASS`.

## Canonical byte rules

The exact artifact bytes are:

- UTF-8 without BOM;
- one top-level JSON object;
- duplicate JSON member names prohibited at every depth;
- exact member sets at top level, `runtime_identity`, and `controls`;
- object keys sorted lexicographically by literal ASCII bytes;
- `acceleration_runtime_identities` sorted ascending by literal ASCII bytes and
  duplicate-free;
- JSON separators exactly `,` and `:`;
- no insignificant whitespace;
- no JSON escape sequences in fields governed by literal ASCII grammars;
- no trailing newline.

A duplicate-member-rejecting parser must parse the supplied bytes. The verifier
must validate every member set, type, grammar, frozen value, ordering rule, and
runtime-binding shape, then canonically reserialize and require byte-for-byte
equality before accepting the digest.

Only those validated canonical bytes may be hashed as:

```text
PHI_SANDBOX_QUALIFICATION_SHA256 = SHA256(exact_validated_artifact_bytes)
```

## Required negative conformance fixtures

A future parser/conformance implementation must prove `BLOCKED` for at least:

- malformed JSON;
- BOM or trailing newline;
- duplicate member at top level, `runtime_identity`, or `controls`;
- extra or missing member at any level;
- wrong JSON scalar/container type;
- noncanonical key order, array order, or whitespace;
- duplicate acceleration-runtime identity;
- JSON escape sequence in a literal-ASCII field;
- empty, whitespace-padded, control-byte, or non-ASCII free-form identity;
- malformed repository SHA/tree, dependency-lock SHA-256, or OCI digest;
- GPU model other than exact `NVIDIA H100 80GB HBM3`;
- any isolation-control value mismatch;
- any process/timing predicate other than JSON boolean `true`;
- qualification disposition other than `PASS`;
- separately reproduced checkout SHA/tree mismatch;
- any separately measured runtime identity mismatch.

## Live evidence boundary

A canonical artifact parser can prove only that supplied bytes satisfy this
format. Activation still requires a separately reviewed live qualification
producer that measures the exact runtime and proves the isolation controls were
active for the complete required model-process window.

A parser PASS with an untrusted, incomplete, stale, or detached producer is not a
sandbox qualification and must not activate execution.

## Non-claims

Conformance to this byte format does not prove:

- a provider instance or GPU exists;
- network ingress/egress is actually denied;
- DNS, metadata, credentials, secrets, or control sockets are actually absent;
- mounts or writable paths are actually restricted;
- a model process was started;
- Phi remote code or model weights were accessed;
- any prompt was serialized;
- execution activation passed.