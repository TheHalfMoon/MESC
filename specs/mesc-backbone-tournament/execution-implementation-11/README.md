# MESC Backbone Tournament — Execution Implementation 11

Status: **DRAFT / FIXTURE-ONLY PHI SANDBOX-CONTROL EVIDENCE VERIFIER / NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded implementation slice addresses only the fixture-level structure of
the `FD-MESC-BT-EXEC-1` Section C.3 model-process isolation predicates that
remain after Execution Implementations 8–10.

Canonical base for this slice:

```text
BASE_MAIN_SHA = a07551e4bb63689390d64b4ae7f636fdb6546eb5
BASE_MAIN_TREE = f9012eb82013765fab16ef532f52a7c5ed3ab802
PR_153 = CLOSED_CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-11/README.md
src/medscale/mesc/_bt_phi_sandbox_fixture_v1.py
tests/test_mesc_bt_phi_sandbox_fixture_v1.py
```

No dependency, lockfile, workflow, credential, provider, model, tokenizer,
processor, corpus, prompt, scoring-key, real Phi source, acquisition,
instrumentation runtime, sandbox implementation, execution-result, or production
sandbox-qualification artifact path is changed.

## Canonical source contract

Section C.3 requires Phi model execution to occur in a dedicated model process
with all of these controls active before any remote-code import or model load:

```text
NETWORK_EGRESS = DENY_ALL
NETWORK_INGRESS = DENY_ALL
DNS = UNAVAILABLE_TO_MODEL_PROCESS
CREDENTIAL_ENVIRONMENT = EMPTY
CLOUD_METADATA_ACCESS = DENIED
HOST_OR_CONTAINER_CONTROL_SOCKETS = NONE
MODEL_AND_RUNTIME_INPUT_MOUNTS = READ_ONLY_ALLOWLIST_ONLY
FROZEN_GOLD_SCORING_INPUTS_VISIBLE_TO_MODEL_PROCESS = NO
WRITABLE_PATHS = ACTIVATION_SCOPED_SCRATCH_AND_OUTPUT_ONLY
REMOTE_FETCH_DURING_MODEL_PROCESS = PROHIBITED
```

The authorization also requires a future `PHI_SANDBOX_QUALIFICATION_SHA256`
artifact proving these controls on the exact runtime. The authorization does not
currently freeze a byte-level serialization schema for that artifact.

## Deliberately no artifact-format invention

This slice therefore does **not** define, parse, hash, or canonize a production
sandbox-qualification artifact and does not establish
`PHI_SANDBOX_QUALIFICATION_SHA256`.

Instead, it provides a pure fail-closed verifier for caller-supplied fixture
evidence. A future separately governed sandbox qualification producer and
artifact parser must establish trustworthy observations, exact runtime binding,
artifact provenance, canonical bytes, and the final qualification digest.

## Implemented fixture contract

`PhiSandboxControlEvidence` contains exactly the fixture facts required by this
slice:

```text
dedicated_model_process
controls_active_before_remote_code_import
controls_active_before_model_load
network_egress
network_ingress
dns
credential_environment
cloud_metadata_access
host_or_container_control_sockets
model_and_runtime_input_mounts
frozen_gold_scoring_inputs_visible_to_model_process
writable_paths
remote_fetch_during_model_process
```

The verifier requires the exact evidence dataclass type. The three process/timing
predicates must be exact Python `bool` values equal to `True`, preventing
bool/int-compatible substitutes.

Every control field must be an exact Python `str` and must equal the frozen
Section C.3 value shown above. String subclasses or equality-compatible objects
cannot satisfy an exact-string boundary.

The verifier returns normally only when every injected predicate exactly matches
the frozen isolation contract. Any false timing/process predicate, wrong scalar
type, string subclass, or control-value mismatch fails closed with a typed
`PhiSandboxEvidenceError`.

## Relationship to prior implementations

Execution Implementation 8 validates only injected trusted-acquisition/runtime
identity and immutable-handoff evidence. It deliberately does not establish
sandbox/network/credential/process-isolation qualification.

Execution Implementation 9 validates only injected full-model-process-lifecycle
executed-file-set observation evidence. It deliberately does not establish
sandbox qualification.

Execution Implementation 10 validates only injected manifest-bound independent
security-review evidence. It deliberately does not establish a sandbox artifact
or qualification digest.

Implementation 11 does not weaken, replace, or imply completion of any of those
independent predicates.

## Deliberate non-claims

This slice does **not**:

- construct, configure, start, stop, or inspect a real sandbox or model process;
- create or inspect network namespaces, firewall rules, DNS configuration,
  seccomp policies, cgroups, containers, VMs, mounts, or control sockets;
- prove that real network ingress or egress is denied;
- prove that DNS, cloud metadata, credentials, secrets, or control sockets are
  absent from a real process;
- inspect, acquire, mount, import, or execute real Phi source or model files;
- establish that a future evidence producer is trustworthy;
- establish trusted-acquisition provenance beyond the separate fixture primitive
  already provided by Implementation 8;
- define production sandbox-qualification artifact bytes;
- hash or establish `PHI_SANDBOX_QUALIFICATION_SHA256`;
- establish gated-access authority or any access attestation;
- allocate a provider instance or GPU;
- establish live H100 telemetry qualification;
- serialize prompts, load model weights, run inference/generation, score, rank,
  select a winner, execute the tournament, or train;
- grant execution authority.

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
