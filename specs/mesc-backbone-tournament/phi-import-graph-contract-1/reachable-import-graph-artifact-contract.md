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
completeness_disposition = PASS
dependency_lock_sha256 = ^[0-9a-f]{64}$
python_version = ^[A-Za-z0-9][A-Za-z0-9._+/-]{0,127}$
source_manifest_sha256 = ^[0-9a-f]{64}$
```

All strings are literal ASCII JSON strings. JSON escape sequences are prohibited for
fields governed by an ASCII grammar.

## Roots

`roots` is a JSON array of path strings. It must equal the exact path sequence in the
parser-validated canonical `PHI_REMOTE_CODE_MANIFEST` bound by
`source_manifest_sha256`, once each, in canonical manifest order.

Each path must satisfy the manifest path grammar:

```text
^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$
```

Each slash-separated component must be neither `.` nor `..`.

The graph is `BLOCKED` if the manifest bytes are absent, noncanonical, cannot reproduce
`source_manifest_sha256`, or `roots` differs from the canonical manifest path sequence.

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
internal import graphs are not silently asserted to be Phi remote-code review scope;
future activation instead binds their environment through exact equality of
`python_version` and `dependency_lock_sha256` to the canonical `RUNTIME_BINDING`.

Nodes are sorted by the tuple `(kind, identity)` using literal ASCII byte ordering.
Duplicate `(kind, identity)` pairs are prohibited.

## Edges

`edges` is a JSON array. Every edge is an object with exactly:

```text
import_name
source_identity
source_kind
target_identity
target_kind
```

`source_kind` and `target_kind` use the same exact node-kind enum. The corresponding
`source_identity` and `target_identity` must identify nodes present in `nodes`.

`import_name` is the absolute module name after the future producer's deterministic
resolution of any relative import syntax and must match the module-name grammar above.

Only `MANIFEST_FILE` nodes may be traversed as remote-code sources by this V1 closure.
If an import from a manifest file resolves to another remotely sourced model-repository
Python file, `target_kind` must be `MANIFEST_FILE` and `target_identity` must be the exact
manifest path. A remotely sourced target absent from the canonical manifest is
`BLOCKED`; it may not be relabeled as a runtime or locked-dependency module.

Imports that resolve to the bound Python runtime use `PYTHON_RUNTIME_MODULE`. Imports
that resolve to the immutable dependency environment use `LOCKED_DEPENDENCY_MODULE`.
If the producer cannot determine exactly which boundary owns the target, the import is
unresolved and the artifact cannot claim PASS.

Edges form a set of module-dependency relationships, not import-site occurrences.
Repeated syntactic imports that resolve to the same canonical relationship are
represented once. Edges are sorted by the tuple:

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

The arrays are deliberately present in the hashed artifact so absence of unresolved
relationships is an explicit claim rather than omitted metadata.

A future producer must classify any import relationship it cannot resolve exactly as
unresolved rather than guessing. Any non-literal or data-dependent import target,
runtime code generation capable of introducing an import not already represented by a
canonical edge, or other import mechanism that the reviewed producer cannot close
mechanically must cause `unresolved_dynamic_imports` to be non-empty during producer
analysis and therefore prevent a V1 PASS artifact.

This V1 contract intentionally does not define a permissive encoding for unresolved
entries because an accepted artifact requires both arrays to be empty. A future need to
carry unresolved evidence without blocking requires a separately reviewed contract
version; it may not be smuggled into V1.

## Completeness semantics

`completeness_disposition = PASS` is valid only if all of the following hold:

1. the canonical manifest is independently parsed and its digest equals
   `source_manifest_sha256`;
2. `roots` equals every manifest path exactly once in manifest order;
3. `nodes` contains every manifest path exactly once and contains no remote model-repo
   file outside that manifest;
4. every edge endpoint exists in `nodes` and every edge target is classified without
   ambiguity;
5. closure recursively follows every import relationship originating from every
   `MANIFEST_FILE` node until the target is either another manifest file or one explicit
   runtime/dependency boundary node;
6. every remote model-repository Python target discovered by that closure is in the
   manifest and is recursively traversed;
7. `unresolved_imports` and `unresolved_dynamic_imports` are both exact empty arrays;
8. the graph's `python_version` and `dependency_lock_sha256` exactly match the complete
   canonical activation `RUNTIME_BINDING` before activation reliance; and
9. a separately reviewed producer/verifier implementation proves that its extraction
   and resolution algorithm satisfies items 1–8 against the exact source/runtime
   identities.

The artifact's literal `PASS` value, parser conformance, empty unresolved arrays, or a
security-review PASS cannot by themselves establish item 9. Missing producer identity,
unreviewed extraction logic, incomplete import-mechanism coverage, ambiguous module
resolution, or inability to reproduce closure => `BLOCKED`.

## Graph-to-manifest binding

The required provenance member is inside the exact graph bytes:

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
signatures over different bytes, or any relation outside the exact hashed graph bytes
do not satisfy this V1 binding.

## Runtime binding

Before activation reliance, the exact graph artifact must also satisfy:

```text
graph.python_version == RUNTIME_BINDING.python_version
graph.dependency_lock_sha256 == RUNTIME_BINDING.dependency_lock_sha256
```

This does not make the graph artifact a runtime attestation. It prevents a graph whose
module-resolution boundaries were produced for one Python/dependency environment from
being reused against another environment without review.

## Canonical byte rules

The exact artifact bytes are:

- UTF-8 without BOM;
- one JSON object and no surrounding bytes;
- duplicate member names prohibited at every depth;
- exact member sets defined above;
- object keys sorted lexicographically by literal ASCII bytes;
- arrays ordered exactly by their contract-specific rules;
- JSON separators exactly `,` and `:`;
- insignificant whitespace prohibited;
- JSON escape sequences prohibited in ASCII-grammar fields;
- no trailing newline.

Before hashing, a duplicate-member-rejecting parser must validate every member set,
type, enum, grammar, manifest relation, node/edge reference, ordering rule, duplicate
prohibition, empty unresolved arrays, and PASS predicate. It must canonically reserialize
and require byte-for-byte equality with the supplied bytes.

Only those exact validated canonical bytes may be hashed.

## Required negative conformance fixtures

A future parser/producer conformance implementation must prove `BLOCKED` for at least:

- malformed JSON, BOM, trailing newline, duplicate member, or extra/missing member;
- wrong JSON scalar/container type;
- malformed digest, path, module name, enum, or Python-version value;
- noncanonical object-key or array ordering;
- duplicate root, node, or edge;
- roots not exactly equal to manifest paths;
- missing manifest node or extra remote-file node;
- edge endpoint absent from `nodes`;
- remote model-repository target absent from the manifest;
- remote target mislabeled as runtime/dependency boundary;
- ambiguous runtime-versus-dependency boundary;
- non-empty `unresolved_imports`;
- non-empty `unresolved_dynamic_imports`;
- non-literal dynamic import that the producer cannot close mechanically;
- graph `source_manifest_sha256` mismatch;
- graph Python-version mismatch with `RUNTIME_BINDING`;
- graph dependency-lock mismatch with `RUNTIME_BINDING`;
- valid graph bytes produced by an unreviewed or incomplete extraction algorithm.

## Deliberate non-claims

Conformance to this byte format does not prove:

- the real Phi source was read or matches a manifest;
- the graph is complete;
- the future producer correctly discovered every import relationship;
- runtime/dependency boundary modules are independently security reviewed here;
- a Phi security review occurred or passed;
- a sandbox qualification occurred or passed;
- model access or execution activation exists.
