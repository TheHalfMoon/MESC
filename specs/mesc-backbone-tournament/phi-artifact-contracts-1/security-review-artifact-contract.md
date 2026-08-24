# Phi Remote-Code Security Review Artifact Contract

Status: **DRAFT GOVERNANCE CONTRACT CANDIDATE / NO SECURITY-REVIEW CLAIM**

Contract ID:

```text
MESC-BT-PHI-SECURITY-REVIEW-ARTIFACT-V1
```

## Purpose

`FD-MESC-BT-EXEC-1` requires a future
`PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256` that explicitly binds the canonical
Phi remote-code manifest, records an independent PASS disposition for every
manifest file, and records a PASS disposition for the complete reachable import
graph.

This contract freezes only deterministic artifact bytes. It does not perform the
review and cannot establish that a supplied import graph is complete.

## Canonical JSON value

The top-level value is an object with exactly these keys:

```text
artifact_version
complete_reachable_import_graph_disposition
complete_reachable_import_graph_reviewed
file_dispositions
independent_review
manifest_sha256
overall_disposition
reachable_import_graph_artifact_sha256
reviewer_identity
```

Canonical serialization sorts them lexicographically as required by the package
envelope.

### Scalar fields

```text
artifact_version = MESC-BT-PHI-SECURITY-REVIEW-ARTIFACT-V1
manifest_sha256 = ^[0-9a-f]{64}$
independent_review = true
complete_reachable_import_graph_reviewed = true
complete_reachable_import_graph_disposition = PASS
overall_disposition = PASS
reachable_import_graph_artifact_sha256 = ^[0-9a-f]{64}$
reviewer_identity = ^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$
```

`reviewer_identity` is an audit label, not authentication. Its presence does not
prove reviewer identity, qualifications, or independence. Those remain
activation-package and independent-review predicates.

All strings above must be JSON strings containing literal ASCII bytes allowed by
the stated grammar. JSON escape sequences are prohibited in these fields.
`independent_review` and `complete_reachable_import_graph_reviewed` must be JSON
booleans, not numeric or string substitutes.

## File dispositions

`file_dispositions` is a JSON array. Every element is an object with exactly:

```text
disposition
path
```

Each element must satisfy:

```text
disposition = PASS
path = ^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$
```

Each slash-separated path component must be neither `.` nor `..`.

The array must contain exactly one entry for every path in the parser-validated
canonical `PHI_REMOTE_CODE_MANIFEST` bound by `manifest_sha256`, and no other
entry. Its ordering must equal the manifest's canonical ascending decoded-path
ASCII order. Duplicate paths are prohibited.

The security-review artifact is `BLOCKED` if the referenced manifest is absent,
its canonical bytes cannot be reproduced, its SHA-256 differs from
`manifest_sha256`, or `file_dispositions` is not an exact path-for-path PASS
mapping of that manifest.

## Reachable import graph artifact binding

The review artifact binds, but does not embed, a separate materialization of the
complete reachable import graph through:

```text
reachable_import_graph_artifact_sha256
```

The graph artifact itself is outside this V1 serialization contract. Before an
activation package may rely on this security-review artifact, a separately
reviewed graph-materialization contract and producer must establish canonical
bytes, provenance, completeness semantics, and the exact SHA-256 referenced
here.

Therefore a syntactically conformant V1 security-review artifact is necessary
but not sufficient for activation. If the graph artifact or its governing
contract is absent, stale, ambiguous, or cannot reproduce the bound digest, the
activation result is `BLOCKED`.

This explicit digest field prevents a future review artifact from claiming
"complete reachable import graph reviewed" while leaving the graph evidence
unbound.

## Canonical byte rules

The exact artifact bytes are:

- UTF-8 without BOM;
- one JSON object and no surrounding bytes;
- no duplicate member names at any depth;
- exact member sets defined above;
- lexicographically sorted object keys;
- `file_dispositions` ordered exactly as the bound canonical manifest;
- JSON separators exactly `,` and `:`;
- no insignificant whitespace;
- no JSON escape sequences in ASCII-grammar fields;
- no trailing newline.

Before hashing, a duplicate-member-rejecting JSON parser must parse the supplied
bytes. The verifier must validate every type, member set, grammar, ordering,
disposition, and manifest binding, then canonically reserialize the parsed value
and require byte-for-byte equality with the supplied bytes.

Only those validated canonical bytes may be hashed as:

```text
PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256 = SHA256(exact_validated_artifact_bytes)
```

## Required negative conformance fixtures

A future parser/conformance implementation must prove `BLOCKED` for at least:

- malformed JSON;
- BOM or trailing newline;
- duplicate top-level member;
- duplicate `path` or `disposition` member inside one file disposition;
- extra or missing top-level member;
- extra or missing file-disposition member;
- wrong JSON scalar type;
- noncanonical key order or whitespace;
- escaped ASCII value where literal ASCII is required;
- malformed SHA-256;
- invalid or traversal-like path;
- duplicate file path;
- reordered file dispositions;
- missing manifest path;
- extra path not present in the manifest;
- any file disposition other than `PASS`;
- `independent_review != true`;
- incomplete graph-review flag;
- graph or overall disposition other than `PASS`;
- manifest SHA-256 mismatch;
- missing or unreproducible reachable-import-graph artifact binding.

## Non-claims

Conformance to this byte format does not prove:

- the supplied manifest was produced from real Phi source;
- the reachable import graph is complete;
- a human or tool actually reviewed the files or graph;
- the reviewer identity string is authenticated;
- reviewer independence or competence;
- absence of malicious behavior;
- sandbox qualification;
- any model access or execution authority.