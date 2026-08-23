# MESC Backbone Tournament — Execution Implementation 10

Status: **DRAFT / FIXTURE-ONLY PHI SECURITY-REVIEW EVIDENCE BINDER / NO EXECUTION AUTHORITY**

Date: 2026-08-23

## Scope

This bounded implementation slice addresses only the fixture-level structure of
the remaining `FD-MESC-BT-EXEC-1` Section C.3 security-review predicate:

```text
PHI_REMOTE_CODE_SECURITY_REVIEW explicitly binds PHI_REMOTE_CODE_MANIFEST_SHA256
and records an independent PASS disposition for every manifest file and for the
complete import graph reachable from those files.
```

Canonical base for this slice:

```text
BASE_MAIN_SHA = 0752365427ac1a89f16363ea9c2ead2a5e551962
BASE_MAIN_TREE = 745fe41e3e220a5a5a8657bd0b69f58a7ddab800
PR_152 = CLOSED_CANONICAL
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

The intended base-to-head scope is exactly three files:

```text
specs/mesc-backbone-tournament/execution-implementation-10/README.md
src/medscale/mesc/_bt_phi_security_review_fixture_v1.py
tests/test_mesc_bt_phi_security_review_fixture_v1.py
```

No dependency, lockfile, workflow, credential, provider, model, tokenizer,
processor, corpus, prompt, scoring key, real Phi source, acquisition,
instrumentation, sandbox, execution result, or production security-review
artifact path is changed.

## Deliberately no artifact-format invention

The authorization contract requires a future
`PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256` over the exact bytes of the accepted
security-review artifact, but it does not currently freeze a serialization
schema for those bytes.

This slice therefore does **not** invent or canonize a new artifact format. It
does not parse review-artifact bytes and it does not establish
`PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256`.

Instead, it provides a pure fail-closed verifier for dependency-injected review
evidence that a future separately governed artifact parser or review producer
may supply. Defining or adopting exact production review-artifact bytes remains
a separate governance step.

## Manifest boundary

Before any review evidence can be accepted, the supplied
`PhiRemoteCodeManifest` must preserve the exact parser-produced Python type
shape:

- exact `PhiRemoteCodeManifest`, not a subclass;
- exact tuple for `entries`;
- exact `PhiRemoteCodeManifestEntry` for every entry;
- exact `str` for manifest and entry identity strings;
- exact `int` for byte-length fields.

Only after those predicates pass does the verifier canonically serialize and
reparse the manifest and require the complete manifest dataclass identity to
match. This preserves the equality-subclass hardening established during
Execution Implementation 9 qualification.

## Injected review-evidence contract

`PhiRemoteCodeSecurityReviewEvidence` contains exactly:

```text
manifest_sha256
independent_review
file_dispositions
complete_reachable_import_graph_reviewed
complete_reachable_import_graph_disposition
```

The verifier requires:

```text
manifest_sha256 = exact canonical manifest SHA-256
independent_review = true
complete_reachable_import_graph_reviewed = true
complete_reachable_import_graph_disposition = PASS
```

`manifest_sha256` and all dispositions are exact Python strings; boolean fields
must be exact Python `bool` values equal to `True`.

`file_dispositions` is an exact tuple of exact
`PhiRemoteCodeFileSecurityDisposition` objects. Each object contains exact
string fields:

```text
path
disposition
```

The disposition tuple must use exactly the canonical manifest paths, once each,
in canonical manifest order. Missing, additional, duplicate, reordered,
non-string, equality-spoofed, or otherwise mismatching path representations fail
closed. Every canonical path must have disposition exactly `PASS`; no other
value or string subclass is accepted.

These conditions model the authorization requirement that every manifest file
and the complete reachable import graph receive an independent PASS review.
They do not establish that the injected producer actually performed such a
review.

## Deliberate non-claims

This module does **not**:

- inspect, download, clone, or access real Phi source or model files;
- construct, traverse, or prove completeness of a real Python import graph;
- perform static analysis, dynamic analysis, malware scanning, or human security
  review;
- establish reviewer identity, qualifications, organizational independence, or
  provenance beyond the exact injected boolean predicate;
- establish a production `PHI_REMOTE_CODE_MANIFEST_SHA256` beyond the supplied
  parser-validated manifest object;
- define the production security-review artifact serialization;
- hash or accept `PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256`;
- prove that a real security-review artifact records the injected evidence;
- establish runtime acquisition, executed-file-set observation, or sandbox
  qualification;
- import or execute Phi remote code;
- access a filesystem, network, model, provider, token, or credential;
- serialize prompts, run inference/generation, score, rank, select a winner,
  execute the tournament, or train;
- grant execution authority.

A future production artifact contract must independently bind exact artifact
bytes, provenance, reviewer identity/independence evidence, complete import-graph
materialization, per-file review results, and the resulting
`PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256` before activation can rely on it.

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
