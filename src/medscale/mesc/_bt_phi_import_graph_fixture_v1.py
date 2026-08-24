"""Fixture-only Phi reachable-import-graph producer.

Inputs are parser-validated manifest objects plus caller-supplied in-memory fixture bytes.
No filesystem, network, repository/model, remote-code, process, prompt, inference, or
training action is performed.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
from dataclasses import dataclass
from typing import Final, Never

from medscale.mesc._bt_phi_remote_code_fixture_v1 import (
    PhiRemoteCodeManifest,
    canonical_phi_remote_code_manifest_bytes,
    parse_phi_remote_code_manifest,
)

_VERSION: Final = "MESC-BT-PHI-REACHABLE-IMPORT-GRAPH-ARTIFACT-V1"
_MANIFEST: Final = "MANIFEST_FILE"
_RUNTIME: Final = "PYTHON_RUNTIME_MODULE"
_DEPENDENCY: Final = "LOCKED_DEPENDENCY_MODULE"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_OCI: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
_MODULE: Final = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_BOM: Final = b"\xef\xbb\xbf"


class PhiImportGraphFixtureError(ValueError):
    """Fail-closed fixture producer or verifier error."""


@dataclass(frozen=True, slots=True)
class PhiImportGraphRuntimeBinding:
    base_container_oci_digest: str
    python_version: str
    dependency_lock_sha256: str


@dataclass(frozen=True, slots=True)
class PhiImportGraphBoundaryPolicy:
    python_runtime_roots: tuple[str, ...]
    locked_dependency_roots: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PhiReachableImportGraphArtifact:
    canonical_bytes: bytes
    sha256: str


RemoteIndex = dict[str, tuple[str, bool]]
Edge = tuple[str, str, str, str, str]
Node = tuple[str, str]


def produce_phi_reachable_import_graph_fixture(
    manifest: PhiRemoteCodeManifest,
    sources: dict[str, bytes],
    runtime_binding: PhiImportGraphRuntimeBinding,
    boundary_policy: PhiImportGraphBoundaryPolicy,
) -> PhiReachableImportGraphArtifact:
    """Produce exact V1 graph bytes from fixture source bytes only."""
    manifest = _manifest(manifest)
    binding = _binding(runtime_binding)
    remote = _remote_index(manifest)
    policy = _policy(boundary_policy, tuple(remote))
    _sources(manifest, sources)

    nodes: set[Node] = {(_MANIFEST, entry.path) for entry in manifest.entries}
    edges: set[Edge] = set()
    for entry in manifest.entries:
        source_module, is_package = _module_from_path(entry.path)
        tree = _source_tree(entry.path, sources[entry.path])
        _reject_unsupported(entry.path, tree)
        for statement in tree.body:
            if isinstance(statement, ast.Import):
                for alias in statement.names:
                    _record(entry.path, alias.name, remote, policy, nodes, edges)
            elif isinstance(statement, ast.ImportFrom):
                base = _from_base(
                    source_module,
                    is_package,
                    statement.module,
                    statement.level,
                )
                for alias in statement.names:
                    target = _from_target(base, alias.name, remote, policy)
                    _record_target(entry.path, target, nodes, edges)

    document: dict[str, object] = {
        "artifact_version": _VERSION,
        "base_container_oci_digest": binding.base_container_oci_digest,
        "completeness_disposition": "PASS",
        "dependency_lock_sha256": binding.dependency_lock_sha256,
        "edges": [
            {
                "source_kind": edge[0],
                "source_identity": edge[1],
                "import_name": edge[2],
                "target_kind": edge[3],
                "target_identity": edge[4],
            }
            for edge in sorted(edges)
        ],
        "nodes": [{"kind": kind, "identity": identity} for kind, identity in sorted(nodes)],
        "python_version": binding.python_version,
        "roots": [entry.path for entry in manifest.entries],
        "source_manifest_sha256": manifest.sha256,
        "unresolved_dynamic_imports": [],
        "unresolved_imports": [],
    }
    payload = _canonical(document)
    return PhiReachableImportGraphArtifact(payload, hashlib.sha256(payload).hexdigest())


def verify_phi_reachable_import_graph_fixture(
    payload: bytes,
    manifest: PhiRemoteCodeManifest,
    sources: dict[str, bytes],
    runtime_binding: PhiImportGraphRuntimeBinding,
    boundary_policy: PhiImportGraphBoundaryPolicy,
) -> None:
    """Require exact canonical bytes and exact producer relationship equality."""
    if type(payload) is not bytes or payload.startswith(_BOM):
        raise PhiImportGraphFixtureError("artifact must be exact UTF-8 bytes without BOM")
    parsed = _load_json(payload)
    if not isinstance(parsed, dict) or payload != _canonical(parsed):
        raise PhiImportGraphFixtureError("artifact is not exact canonical JSON")
    expected = produce_phi_reachable_import_graph_fixture(
        manifest,
        sources,
        runtime_binding,
        boundary_policy,
    )
    if payload != expected.canonical_bytes:
        raise PhiImportGraphFixtureError(
            "artifact differs from the reviewed fixture producer relationship set"
        )


def _manifest(manifest: PhiRemoteCodeManifest) -> PhiRemoteCodeManifest:
    if type(manifest) is not PhiRemoteCodeManifest:
        raise PhiImportGraphFixtureError("manifest is not parser-validated")
    try:
        canonical = canonical_phi_remote_code_manifest_bytes(manifest.entries)
        reparsed = parse_phi_remote_code_manifest(canonical)
    except Exception as error:
        raise PhiImportGraphFixtureError("manifest content is not canonical") from error
    if reparsed != manifest:
        raise PhiImportGraphFixtureError("manifest identity is forged or stale")
    return manifest


def _binding(value: PhiImportGraphRuntimeBinding) -> PhiImportGraphRuntimeBinding:
    if type(value) is not PhiImportGraphRuntimeBinding:
        raise PhiImportGraphFixtureError("runtime binding has wrong type")
    if (
        type(value.base_container_oci_digest) is not str
        or _OCI.fullmatch(value.base_container_oci_digest) is None
    ):
        raise PhiImportGraphFixtureError("invalid base container OCI digest")
    if (
        type(value.dependency_lock_sha256) is not str
        or _SHA256.fullmatch(value.dependency_lock_sha256) is None
    ):
        raise PhiImportGraphFixtureError("invalid dependency lock digest")
    if type(value.python_version) is not str or not value.python_version:
        raise PhiImportGraphFixtureError("python_version must be non-empty")
    try:
        encoded = value.python_version.encode("ascii")
    except UnicodeEncodeError as error:
        raise PhiImportGraphFixtureError("python_version must be printable ASCII") from error
    if any(byte < 0x20 or byte > 0x7E or byte in {0x22, 0x5C} for byte in encoded):
        raise PhiImportGraphFixtureError("python_version violates runtime identity grammar")
    return value


def _policy(
    value: PhiImportGraphBoundaryPolicy,
    remote_modules: tuple[str, ...],
) -> PhiImportGraphBoundaryPolicy:
    if type(value) is not PhiImportGraphBoundaryPolicy:
        raise PhiImportGraphFixtureError("boundary policy has wrong type")
    groups = (value.python_runtime_roots, value.locked_dependency_roots)
    for roots in groups:
        if type(roots) is not tuple or any(type(root) is not str for root in roots):
            raise PhiImportGraphFixtureError("boundary roots must be exact string tuples")
        if roots != tuple(sorted(roots)) or len(roots) != len(set(roots)):
            raise PhiImportGraphFixtureError("boundary roots must be unique and sorted")
        if any(_MODULE.fullmatch(root) is None for root in roots):
            raise PhiImportGraphFixtureError("boundary root has invalid module grammar")
    all_roots = value.python_runtime_roots + value.locked_dependency_roots
    for index, left in enumerate(all_roots):
        for right in all_roots[index + 1 :]:
            if _under(left, right) or _under(right, left):
                raise PhiImportGraphFixtureError("boundary roots overlap")
        if any(_under(left, module) or _under(module, left) for module in remote_modules):
            raise PhiImportGraphFixtureError("boundary overlaps remote manifest namespace")
    return value


def _remote_index(manifest: PhiRemoteCodeManifest) -> RemoteIndex:
    result: RemoteIndex = {}
    for entry in manifest.entries:
        name, is_package = _module_from_path(entry.path)
        if name in result:
            raise PhiImportGraphFixtureError("duplicate remote module identity")
        result[name] = (entry.path, is_package)
    return result


def _module_from_path(path: str) -> tuple[str, bool]:
    if not path.endswith(".py"):
        raise PhiImportGraphFixtureError("fixture producer supports Python manifest files only")
    parts = path.split("/")
    is_package = parts[-1] == "__init__.py"
    if is_package:
        parts = parts[:-1]
    else:
        parts[-1] = parts[-1][:-3]
    if not parts or any(not part.isascii() or not part.isidentifier() for part in parts):
        raise PhiImportGraphFixtureError("manifest path cannot map to a Python module")
    return ".".join(parts), is_package


def _sources(manifest: PhiRemoteCodeManifest, sources: dict[str, bytes]) -> None:
    if type(sources) is not dict or any(
        type(path) is not str or type(payload) is not bytes for path, payload in sources.items()
    ):
        raise PhiImportGraphFixtureError("sources must be exact dict[str, bytes]")
    if set(sources) != {entry.path for entry in manifest.entries}:
        raise PhiImportGraphFixtureError("source paths must equal manifest paths")
    for entry in manifest.entries:
        payload = sources[entry.path]
        if len(payload) != entry.byte_length or hashlib.sha256(payload).hexdigest() != entry.sha256:
            raise PhiImportGraphFixtureError(f"fixture source identity mismatch: {entry.path!r}")


def _source_tree(path: str, payload: bytes) -> ast.Module:
    try:
        return ast.parse(payload.decode("utf-8", errors="strict"), filename=path)
    except (UnicodeDecodeError, SyntaxError, ValueError) as error:
        raise PhiImportGraphFixtureError(f"invalid fixture Python source: {path!r}") from error


def _reject_unsupported(path: str, tree: ast.Module) -> None:
    for statement in tree.body:
        if not isinstance(statement, (ast.Import, ast.ImportFrom)):
            raise PhiImportGraphFixtureError(
                f"source statement is outside reviewed import-only fixture grammar: {path!r}"
            )


def _from_base(
    source_module: str,
    is_package: bool,
    module: str | None,
    level: int,
) -> str:
    if level == 0:
        if module is None or _MODULE.fullmatch(module) is None:
            raise PhiImportGraphFixtureError("invalid absolute from-import")
        return module
    package = source_module if is_package else source_module.rpartition(".")[0]
    parts = package.split(".") if package else []
    ascend = level - 1
    if ascend > len(parts):
        raise PhiImportGraphFixtureError("relative import escapes remote package")
    result = parts[: len(parts) - ascend]
    if module:
        result.extend(module.split("."))
    if not result:
        raise PhiImportGraphFixtureError("relative import resolves to no module")
    return ".".join(result)


def _from_target(
    base: str,
    imported: str,
    remote: RemoteIndex,
    policy: PhiImportGraphBoundaryPolicy,
) -> tuple[str, str]:
    if imported == "*":
        if base in remote:
            raise PhiImportGraphFixtureError("star import from remote module is ambiguous")
        return _resolve(base, remote, policy)
    candidate = f"{base}.{imported}"
    if candidate in remote:
        return _resolve(candidate, remote, policy)
    if base in remote:
        path, is_package = remote[base]
        if is_package:
            raise PhiImportGraphFixtureError(f"remote submodule is not manifested: {candidate!r}")
        return _MANIFEST, path
    return _resolve(base, remote, policy)


def _resolve(
    name: str,
    remote: RemoteIndex,
    policy: PhiImportGraphBoundaryPolicy,
) -> tuple[str, str]:
    if _MODULE.fullmatch(name) is None:
        raise PhiImportGraphFixtureError(f"invalid absolute import name: {name!r}")
    if name in remote:
        return _MANIFEST, remote[name][0]
    runtime = any(_under(name, root) for root in policy.python_runtime_roots)
    dependency = any(_under(name, root) for root in policy.locked_dependency_roots)
    if runtime == dependency:
        raise PhiImportGraphFixtureError(f"unresolved or ambiguous import target: {name!r}")
    return (_RUNTIME if runtime else _DEPENDENCY), name


def _under(name: str, root: str) -> bool:
    return name == root or name.startswith(root + ".")


def _record(
    source_path: str,
    import_name: str,
    remote: RemoteIndex,
    policy: PhiImportGraphBoundaryPolicy,
    nodes: set[Node],
    edges: set[Edge],
) -> None:
    _record_target(source_path, _resolve(import_name, remote, policy), nodes, edges)


def _record_target(
    source_path: str,
    target: tuple[str, str],
    nodes: set[Node],
    edges: set[Edge],
) -> None:
    kind, identity = target
    if kind == _MANIFEST:
        import_name = _module_from_path(identity)[0]
    else:
        import_name = identity
        nodes.add((kind, identity))
    edges.add((_MANIFEST, source_path, import_name, kind, identity))


def _canonical(document: dict[str, object]) -> bytes:
    try:
        return json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, UnicodeEncodeError, ValueError) as error:
        raise PhiImportGraphFixtureError("artifact cannot be canonical ASCII JSON") from error


def _load_json(payload: bytes) -> object:
    try:
        text = payload.decode("utf-8", errors="strict")
        parsed: object = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        return parsed
    except PhiImportGraphFixtureError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as error:
        raise PhiImportGraphFixtureError(
            "artifact is not valid duplicate-safe UTF-8 JSON"
        ) from error


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise PhiImportGraphFixtureError(f"duplicate JSON member: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> Never:
    raise PhiImportGraphFixtureError(f"non-standard JSON constant is prohibited: {value}")
