# MESC Backbone Tournament — Phi Activation Artifact Contracts 1

Status: **DRAFT GOVERNANCE CONTRACT CANDIDATE / NO EXECUTION AUTHORITY**

Date: 2026-08-24

## Canonical base

```text
BASE_MAIN_SHA = 42615ad465eada4ede814d7f7de1e0703dafe137
BASE_MAIN_TREE = 0dbe3dc7a43f2dd8bc5be174c33b5986b87a6caf
PR_171 = CLOSED_CANONICAL
REPORT_CONFORMANCE_COMPLETION_BATCH_1 = CLOSED_CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

## Purpose

`FD-MESC-BT-EXEC-1` requires two Phi-specific activation artifacts but deliberately
left their byte-level production serialization undefined:

```text
PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256
PHI_SANDBOX_QUALIFICATION_SHA256
```

Execution Implementations 10 and 11 therefore stopped at fixture-only evidence
binders and explicitly deferred exact production artifact bytes to a separate
governance step.

This package is that governance step. It proposes deterministic canonical JSON
serialization contracts for those two artifacts without reading Phi source,
constructing an import graph, configuring a sandbox, accessing a provider, or
activating execution.

## Package contents

```text
security-review-artifact-contract.md
sandbox-qualification-artifact-contract.md
acceptance.md
```

The package does not modify `FD-MESC-BT-EXEC-1`. It narrows two previously
unbound artifact-serialization surfaces so a later separately reviewed verifier
can parse and hash exact bytes fail-closed.

## Governing design rules

Both proposed artifacts use the same deterministic envelope rules:

- UTF-8 bytes only;
- no BOM;
- one top-level JSON object;
- duplicate JSON member names are invalid;
- object member sets are exact at every level;
- object keys serialize in lexicographic ASCII order;
- arrays use the contract-specific ordering rule;
- separators are exactly `,` and `:`;
- insignificant whitespace is prohibited;
- JSON escape sequences are prohibited for fields whose grammar is ASCII-only;
- no trailing newline;
- a duplicate-member-rejecting parser must parse the supplied bytes;
- the parsed value must be canonically reserialized and match the supplied bytes
  byte-for-byte before its SHA-256 is accepted.

Malformed JSON, duplicate members, extra or missing fields, wrong scalar types,
non-canonical serialization, ordering drift, unsupported values, or inability to
reproduce the exact bytes => `BLOCKED`.

## Security-review artifact

`security-review-artifact-contract.md` defines a bounded artifact that binds:

- the exact canonical Phi remote-code manifest SHA-256;
- explicit independent-review attestation;
- one PASS disposition for every manifest path, in canonical manifest order;
- a digest-bound materialization of the complete reachable import graph reviewed;
- explicit complete-graph review and PASS disposition;
- an overall PASS disposition.

The artifact format cannot prove that a reviewer is independent or that a supplied
import graph is complete. Those are producer/provenance obligations for the future
activation package and independent review. The format only makes the claimed
evidence exact, closed, hashable, and replayable.

## Sandbox-qualification artifact

`sandbox-qualification-artifact-contract.md` binds the sandbox evidence to the
SHA-256 of the **complete canonical `RUNTIME_BINDING` bytes already defined by the
activation identity layer**, rather than redeclaring a partial copy of runtime
fields. It also freezes the exact Phi model-process isolation controls required
before remote-code import or model load.

A future activation path must independently validate the complete canonical
`RUNTIME_BINDING`, recompute its SHA-256, and require exact equality to the digest
inside the sandbox artifact. This prevents schema drift between sandbox evidence
and the canonical activation runtime identity.

The package does not allocate or inspect a provider instance, create namespaces
or firewall rules, start a model process, or test network behavior. A future live
qualification producer must generate the observations; this package only freezes
how accepted observations are serialized and bound to one exact validated runtime.

## Deliberate non-claims

This package does **not**:

- inspect, download, clone, or access Phi source or model files;
- construct or traverse a real import graph;
- perform a security review;
- define reviewer qualifications or authenticate a reviewer;
- configure, launch, or inspect a sandbox or model process;
- access provider APIs, GPUs, credentials, gated terms, or model weights;
- establish either production artifact digest;
- establish `PHI_REMOTE_CODE_SECURITY_REVIEW = PASS`;
- establish `PHI_SANDBOX_QUALIFICATION = PASS`;
- satisfy execution activation;
- serialize prompts, run inference/generation, score, rank, select winners, or
  execute the Backbone Tournament;
- train or fine-tune a model.

## Hard boundary

```text
REAL_PHI_SOURCE_READ = NOT_PERFORMED
REAL_PHI_IMPORT_GRAPH_CONSTRUCTION = NOT_PERFORMED
REAL_PHI_SECURITY_REVIEW = NOT_PERFORMED
REAL_PHI_SANDBOX_QUALIFICATION = NOT_PERFORMED
PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256 = NOT_ESTABLISHED
PHI_SANDBOX_QUALIFICATION_SHA256 = NOT_ESTABLISHED
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

Canonical adoption of this package, if it later passes every exact-head gate,
freezes artifact **formats only**. It grants no execution or access authority.
