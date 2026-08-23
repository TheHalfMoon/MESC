# Backbone Tournament execution implementation 5 — fixture activation identity verifier

Status: **DRAFT / FIXTURE-ONLY / NO EXECUTION AUTHORITY**

This clean replacement slice is based directly on the current canonical `main`:

```text
BASE_MAIN_SHA = be3aea7617eba279dda31eff8752764ed1b90bf9
BASE_MAIN_TREE = c611bb03be77b9751bb59484b46f1a04470a9803
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
PR_145 = CLOSED_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The source and test blobs are byte-identical to the final source and test blobs from superseded PR #144. They were transplanted onto the current canonical base without force-push, rebase, merge-forward history, or destructive rewriting. All qualification evidence from PR #144 is historical only; this replacement requires fresh exact-head qualification.

## Scope

This implementation covers only pure, deterministic validation of the Section I/J
`RUNTIME_BINDING` and `identity_preimage` serialization contracts using synthetic
in-memory bytes and injected independently-recomputed fixture values.

The verifier:

- rejects duplicate JSON members before mapping construction;
- requires canonical ASCII JSON bytes with lexically sorted keys, exact compact
  separators, no BOM, and no trailing newline;
- requires the exact closed `RUNTIME_BINDING` key set and scalar/array types;
- enforces exact `RunPod Secure Cloud`, one-GPU, sequential execution, and
  `NVIDIA H100 80GB HBM3` identity values without contacting a provider;
- validates non-empty runtime identity strings using the authorization's printable
  ASCII restrictions;
- requires unique, byte-sorted acceleration runtime identities;
- validates exact OCI digest, dependency-lock digest, checkout SHA/tree, numeric
  descriptor identities, and canonical checkout-root path grammar;
- recomputes `runtime_binding_sha256` over the accepted exact bytes;
- requires the exact closed `identity_preimage` scalar schema;
- validates the fixed activation decision and receipt-version identifiers;
- compares every externally bound activation value against an injected
  `IndependentActivationBindings` fixture object;
- requires the runtime checkout SHA/tree to equal independently supplied fixture
  values;
- derives `ACTIVATION_ID` as lowercase SHA-256 over the exact canonical
  `identity_preimage` bytes;
- derives the external and repository result-root strings deterministically from
  that activation ID.

## Deliberate non-claims

This is not the activation executor and does not authenticate or retrieve any
GitHub commit, tree, Founder comment, gated-access attestation, telemetry
qualification, Phi manifest, sandbox qualification, or executor allowlist.

`IndependentActivationBindings` represents values that a future activation
verifier must independently recompute through separately reviewed mechanisms.
This fixture primitive only proves that canonical activation bytes bind exactly
to those injected values.

This slice does not:

- perform the Section I.1 descriptor-relative filesystem bootstrap;
- call `openat2`, `mkdirat`, NVML, RunPod, Docker, or subprocesses;
- allocate an H100 or prove a live GPU/provider instance;
- create activation directories or artifacts;
- access/download/load model weights;
- request or accept gated model access;
- read frozen Repair-2 prompt/corpus/scoring-key contents;
- serialize prompts to a model;
- run inference, generation, ranking, winner selection, or training.

The race-safe filesystem bootstrap, exact-instance telemetry qualification,
Git/comment authentication, remote-code controls, gated-access authority, final
activation receipt, and production executor integration remain separate,
independently reviewed work.

## Qualification

Historical CI, CodeQL, and review evidence from PR #144 is superseded for merge qualification. Only fresh evidence bound to the current replacement head may qualify this slice.

## Hard boundary

```text
EXECUTION_ACTIVATION = REQUIRED
MODEL_WEIGHT_ACCESS = NOT_AUTHORIZED
GATED_ACCESS_REQUEST_OR_ACCEPTANCE = NOT_AUTHORIZED
MODEL_RETRIEVAL = NOT_AUTHORIZED
PROMPT_SERIALIZATION_TO_MODEL = NOT_AUTHORIZED
INFERENCE = NOT_AUTHORIZED
GENERATION = NOT_AUTHORIZED
RANKING = NOT_AUTHORIZED
WINNER_SELECTION = NOT_AUTHORIZED
BACKBONE_TOURNAMENT_EXECUTION = NOT_AUTHORIZED
TRAINING = NOT_AUTHORIZED
```

Keep this work Draft until GitHub-native scope reconciliation, fresh exact-head CI,
CodeQL, permitted exact-head technical review, permitted external review, and zero
blocking review threads are all proven. Any head mutation burns prior head-specific
evidence.
