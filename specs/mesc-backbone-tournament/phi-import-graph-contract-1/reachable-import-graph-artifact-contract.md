# Phi Reachable Import Graph Artifact Contract

Status: **DRAFT GOVERNANCE CONTRACT / NO GRAPH-COMPLETENESS CLAIM**

Contract ID:

```text
MESC-BT-PHI-REACHABLE-IMPORT-GRAPH-ARTIFACT-V1
```

## Purpose

PR #174 requires a future graph artifact whose exact canonical bytes contain
`source_manifest_sha256`, whose SHA-256 is bound by the Phi security-review artifact,
and whose producer/completeness semantics are separately reviewed before activation may
rely on it.

This contract freezes candidate artifact bytes and fail-closed graph semantics. It does
not construct a graph and cannot prove producer correctness or real graph completeness.

## Canonical JSON value

The top-level value is one object with exactly these keys:

```text
artifact_version
base_container_oci_digest
completeness_disposition
dependency_lock_sha256
edges
nodes
python_version
roots
source_manifest_sha256
unresolved_dynamic_imports
unresolved_imports
```

Canonical serialization sorts top-level keys lexicographically by literal ASCII bytes.

### Scalar fields

```text
artifact_version = MESC-BT-PHI-REACHABLE-IMPORT-GRAPH-ARTIFACT-V1
base_container_oci_digest = ^sha256:[0-9a-f]{64}$
completeness_disposition = PASS
dependency_lock_sha256 = ^[0-9a-f]{64}$
source_manifest_sha256 = ^[0-9a-f]{64}$
```

`python_version` must use the exact scalar grammar already imposed by the canonical
`RUNTIME_BINDING`: a non-empty JSON string whose bytes are printable ASCII `0x20..0x7e`
excluding `"` (`0x22`) and `\` (`0x5c`). No JSON escape sequence is permitted. The graph
contract deliberately does not narrow this field to a semantic-version token.

All other strings governed by an ASCII grammar are literal ASCII JSON strings; JSON
escape sequences are prohibited for them.

## Roots

`roots` is a JSON array of path strings. It must equal the exact path sequence in the
parser-validated canonical `PHI_REMOTE_CODE_MANIFEST` bound by
`source_manifest_sha256`, once each, in canonical manifest order.

Each path must satisfy the canonical manifest path grammar:

```text
^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$
```

Each slash-separated component must be neither `.` nor `..`.

Absent/noncanonical manifest bytes, failure to reproduce `source_manifest_sha256`, or
any root-sequence mismatch => `BLOCKED`.

## Nodes

`nodes` is a JSON array. Every node is an object with exactly:

```text
identity
kind
```

Allowed `kind` values are exactly:

```text
MANIFEST_FILE
PYTHON_RUNTIME_MODULE
LOCKED_DEPENDENCY_MODULE
```

For `MANIFEST_FILE`, `identity` is one exact canonical manifest path.

For `PYTHON_RUNTIME_MODULE` and `LOCKED_DEPENDENCY_MODULE`, `identity` is an absolute
Python module name matching:

```text
^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$
```

Every manifest path must appear exactly once as a `MANIFEST_FILE` node. No
`MANIFEST_FILE` node may name a path outside the bound manifest.

Runtime/dependency nodes are terminal trust-boundary nodes for this V1 artifact. Their
internal import graphs are not asserted to be Phi remote-code review scope. Future
activation binds those boundaries to an immutable environment through exact equality of
`base_container_oci_digest`, `python_version`, and `dependency_lock_sha256` to the
canonical `RUNTIME_BINDING`.

Every `PYTHON_RUNTIME_MODULE` and `LOCKED_DEPENDENCY_MODULE` node must be the target of
at least one canonical edge. Unreferenced boundary nodes are prohibited so identical
closure cannot acquire arbitrary extra nodes and therefore arbitrary graph digests.

The same module `identity` must not occur under both `PYTHON_RUNTIME_MODULE` and
`LOCKED_DEPENDENCY_MODULE`. Such dual classification is ambiguous and => `BLOCKED`.

Nodes are sorted by `(kind, identity)` using literal ASCII byte ordering. Duplicate
`(kind, identity)` pairs are prohibited.

## Edges

`edges` is a JSON array. Every edge is an object with exactly:

```text
import_name
source_identity
source_kind
target_identity
target_kind
```

The source restriction is exact:

```text
source_kind = MANIFEST_FILE
```

`source_identity` must identify an existing `MANIFEST_FILE` node. Edges whose source is
`PYTHON_RUNTIME_MODULE` or `LOCKED_DEPENDENCY_MODULE` are prohibited because those
nodes are terminal boundaries in V1.

`target_kind` is one of the three exact node-kind values and `target_identity` must
identify an existing node of that exact kind.

`import_name` is the absolute module name after the future producer's deterministic
resolution of relative-import syntax and must match the module-name grammar above.

If an import from a manifest file resolves to another remotely sourced model-repository
Python file, `target_kind` must be `MANIFEST_FILE` and `target_identity` must be that
exact manifest path. A remotely sourced target absent from the manifest is `BLOCKED`;
it may not be relabeled as a runtime or locked-dependency module.

Imports resolving to the bound Python runtime use `PYTHON_RUNTIME_MODULE`. Imports
resolving to the immutable dependency environment use `LOCKED_DEPENDENCY_MODULE`. If
the producer cannot determine exactly which boundary owns a target, the relationship is
unresolved and the artifact cannot claim PASS.

Edges represent unique module-dependency relationships rather than import-site
occurrences. Repeated syntactic imports resolving to the same relationship are encoded
once. Edges are sorted by:

```text
(source_kind, source_identity, import_name, target_kind, target_identity)
```

using literal ASCII byte ordering. Duplicate edge tuples are prohibited.

## Dynamic and unresolved imports

For an accepted V1 artifact:

```text
unresolved_imports = []
unresolved_dynamic_imports = []
```

The arrays are present inside the hashed artifact so absence of unresolved relationships
is an explicit claim rather than omitted metadata.

A future producer must classify any relationship it cannot resolve exactly as unresolved
rather than guessing. Any non-literal or data-dependent import target, runtime code
generation capable of introducing an import not represented by a canonical edge, or
other import mechanism the reviewed producer cannot close mechanically must prevent a V1
PASS artifact.

V1 defines no permissive encoding for unresolved entries because accepted artifacts
require both arrays to be empty. Supporting unresolved evidence without blocking
requires a separately reviewed contract version.

## Completeness semantics

`completeness_disposition = PASS` is valid only when all of the following hold:

1. the canonical manifest is independently parsed and its digest equals
   `source_manifest_sha256`;
2. `roots` equals every manifest path exactly once in manifest order;
3. `nodes` contains every manifest path exactly once and no remote model-repository file
   outside that manifest;
4. every edge has `source_kind = MANIFEST_FILE`, its source is an existing manifest node,
   and its target is an existing node classified without ambiguity;
5. every runtime/dependency boundary node is referenced by at least one edge and no
   module identity is classified under both boundary kinds;
6. closure exhausts every import relationship originating from every manifest file until
   the target is another manifest file or one explicit runtime/dependency terminal node;
7. every remote model-repository Python target discovered by closure is in the manifest;
8. `unresolved_imports` and `unresolved_dynamic_imports` are exact empty arrays;
9. graph `base_container_oci_digest`, `python_version`, and `dependency_lock_sha256`
   exactly match the complete canonical activation `RUNTIME_BINDING` before activation
   reliance; and
10. a separately reviewed producer/verifier implementation proves its extraction and
    resolution algorithm satisfies items 1–9 against the exact source/runtime identities.

The literal `PASS`, parser conformance, empty unresolved arrays, or security-review PASS
cannot self-attest item 10. Missing producer qualification, incomplete import-mechanism
coverage, ambiguous resolution, or inability to reproduce closure => `BLOCKED`.

## Graph-to-manifest binding

The provenance member is inside the exact graph bytes:

```text
source_manifest_sha256
```

The published graph identifier is exactly 64 lowercase ASCII hexadecimal characters:

```text
REACHABLE_IMPORT_GRAPH_ARTIFACT_SHA256 =
  lowercase_hex(SHA256(exact_validated_canonical_graph_artifact_bytes))
```

A future activation verifier must parse/validate the exact graph bytes, reproduce that
digest, extract `source_manifest_sha256`, and require:

```text
graph.source_manifest_sha256 == security_review.manifest_sha256
```

Detached provenance, sidecars, narrative assertions, separately hashed envelopes,
signatures over different bytes, or any relation outside the exact hashed graph bytes do
not satisfy V1.

## Runtime binding

Before activation reliance require:

```text
graph.base_container_oci_digest == RUNTIME_BINDING.base_container_oci_digest
graph.python_version == RUNTIME_BINDING.python_version
graph.dependency_lock_sha256 == RUNTIME_BINDING.dependency_lock_sha256
```

This is not a runtime attestation. It prevents graph reuse across a different immutable
container/Python/dependency environment without review.

## Canonical byte rules

The exact artifact bytes are:

- UTF-8 without BOM;
- one JSON object and no surrounding bytes;
- duplicate member names prohibited at every depth;
- exact member sets defined above;
- object keys sorted lexicographically by literal ASCII bytes;
- arrays ordered exactly by contract rules;
- JSON separators exactly `,` and `:`;
- insignificant whitespace prohibited;
- JSON escape sequences prohibited in ASCII-grammar fields;
- no trailing newline.

Before hashing, a duplicate-member-rejecting parser must validate every member set,
type, enum, grammar, manifest relation, node/edge reference, source-kind restriction,
boundary-node minimality/classification, ordering rule, duplicate prohibition, empty
unresolved arrays, and PASS predicate. It must canonically reserialize and require
byte-for-byte equality.

Only those exact validated canonical bytes may be hashed.

## Required negative conformance fixtures

A future parser/producer conformance implementation must prove `BLOCKED` for at least:

- malformed JSON, BOM, trailing newline, duplicate member, or extra/missing member;
- wrong JSON scalar/container type;
- malformed digest, OCI digest, path, module name, enum, or runtime-bound identity value;
- `python_version` containing non-ASCII, control, quote, backslash, or empty content;
- noncanonical object-key or array ordering;
- duplicate root, node, or edge;
- roots not exactly equal to manifest paths;
- missing manifest node or extra remote-file node;
- edge source or target absent from `nodes`;
- edge whose `source_kind != MANIFEST_FILE`;
- unreferenced runtime/dependency boundary node;
- one module identity classified as both runtime and dependency;
- remote model-repository target absent from the manifest;
- remote target mislabeled as runtime/dependency boundary;
- ambiguous runtime-versus-dependency boundary;
- non-empty `unresolved_imports` or `unresolved_dynamic_imports`;
- non-literal dynamic import the producer cannot close mechanically;
- graph `source_manifest_sha256` mismatch;
- graph base-container digest mismatch with `RUNTIME_BINDING`;
- graph Python-version mismatch with `RUNTIME_BINDING`;
- graph dependency-lock mismatch with `RUNTIME_BINDING`;
- valid graph bytes produced by an unreviewed or incomplete extraction algorithm.

## Deliberate non-claims

Conformance to this byte format does not prove:

- real Phi source was read or matches a manifest;
- the graph is complete;
- the future producer discovered every import relationship correctly;
- runtime/dependency boundary internals are independently security reviewed here;
- a Phi security review or sandbox qualification occurred;
- model access or execution activation exists.
