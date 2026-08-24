"""Fixture-only qualification for the Phi reachable-import-graph producer."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._bt_phi_import_graph_fixture_v1 import (
    PhiImportGraphBoundaryPolicy,
    PhiImportGraphFixtureError,
    PhiImportGraphRuntimeBinding,
    PhiReachableImportGraphArtifact,
    produce_phi_reachable_import_graph_fixture,
    verify_phi_reachable_import_graph_fixture,
)
from medscale.mesc._bt_phi_remote_code_fixture_v1 import (
    PhiRemoteCodeManifest,
    PhiRemoteCodeManifestEntry,
    canonical_phi_remote_code_manifest_bytes,
    parse_phi_remote_code_manifest,
)

_BLOB = "1" * 40
_OCI = "sha256:" + "2" * 64
_LOCK = "3" * 64
_IMPORT_ONLY_ERROR = "outside reviewed import-only fixture grammar"


def _manifest(sources: dict[str, bytes]) -> PhiRemoteCodeManifest:
    entries = tuple(
        PhiRemoteCodeManifestEntry(
            byte_length=len(payload),
            git_blob_sha=_BLOB,
            path=path,
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        for path, payload in sorted(sources.items())
    )
    return parse_phi_remote_code_manifest(canonical_phi_remote_code_manifest_bytes(entries))


def _binding() -> PhiImportGraphRuntimeBinding:
    return PhiImportGraphRuntimeBinding(_OCI, "3.11.9", _LOCK)


def _policy() -> PhiImportGraphBoundaryPolicy:
    return PhiImportGraphBoundaryPolicy(
        python_runtime_roots=("json", "os", "sys"),
        locked_dependency_roots=("torch", "transformers"),
    )


def _produce(
    sources: dict[str, bytes],
    *,
    binding: PhiImportGraphRuntimeBinding | None = None,
    policy: PhiImportGraphBoundaryPolicy | None = None,
) -> tuple[PhiRemoteCodeManifest, PhiReachableImportGraphArtifact]:
    manifest = _manifest(sources)
    artifact = produce_phi_reachable_import_graph_fixture(
        manifest,
        sources,
        binding or _binding(),
        policy or _policy(),
    )
    return manifest, artifact


def _document(payload: bytes) -> dict[str, object]:
    value: object = json.loads(payload)
    assert isinstance(value, dict)
    return cast(dict[str, object], value)


def _canonical(document: dict[str, object]) -> bytes:
    return json.dumps(document, sort_keys=True, separators=(",", ":")).encode("ascii")


def test_producer_emits_canonical_exact_graph_and_digest() -> None:
    sources = {
        "pkg/__init__.py": b"import json\n",
        "pkg/helper.py": b"import os.path\n",
        "pkg/model.py": b"from . import helper\nimport torch.nn\n",
    }
    manifest, artifact = _produce(sources)
    doc = _document(artifact.canonical_bytes)

    assert doc["artifact_version"] == "MESC-BT-PHI-REACHABLE-IMPORT-GRAPH-ARTIFACT-V1"
    assert doc["roots"] == [entry.path for entry in manifest.entries]
    assert doc["source_manifest_sha256"] == manifest.sha256
    assert doc["unresolved_imports"] == []
    assert doc["unresolved_dynamic_imports"] == []
    assert artifact.sha256 == hashlib.sha256(artifact.canonical_bytes).hexdigest()
    assert not artifact.canonical_bytes.endswith(b"\n")
    verify_phi_reachable_import_graph_fixture(
        artifact.canonical_bytes,
        manifest,
        sources,
        _binding(),
        _policy(),
    )


def test_comments_do_not_expand_the_import_only_grammar() -> None:
    sources = {"model.py": b"# fixture comment\nimport json\n"}
    manifest, artifact = _produce(sources)

    verify_phi_reachable_import_graph_fixture(
        artifact.canonical_bytes,
        manifest,
        sources,
        _binding(),
        _policy(),
    )


def test_from_manifest_package_requires_exact_manifested_submodule() -> None:
    sources = {
        "pkg/__init__.py": b"from pkg import helper\n",
        "pkg/helper.py": b"import json\n",
    }
    _, artifact = _produce(sources)
    raw_edges = _document(artifact.canonical_bytes)["edges"]
    assert isinstance(raw_edges, list)
    edges = cast(list[dict[str, object]], raw_edges)
    assert any(edge["target_identity"] == "pkg/helper.py" for edge in edges)


@pytest.mark.parametrize(
    "source",
    [
        b"def f():\n    import json\n",
        b"if True:\n    import json\n",
        b"value = 1\n",
        b"class Example:\n    pass\n",
        b"print('x')\n",
        b'"module docstring"\nimport json\n',
    ],
)
def test_any_non_import_statement_is_blocked(source: bytes) -> None:
    with pytest.raises(PhiImportGraphFixtureError, match=_IMPORT_ONLY_ERROR):
        _produce({"model.py": source})


@pytest.mark.parametrize(
    "source",
    [
        b"__import__('json')\n",
        b"import importlib\nimportlib.import_module('json')\n",
        b"import runpy\nrunpy.run_module('x')\n",
        b"exec('import json')\n",
        b"compile('import json', 'x', 'exec')\n",
        b"import marshal\nmarshal.loads(b'x')\n",
        b"import types\ntypes.FunctionType(None, {})\n",
    ],
)
def test_dynamic_import_and_code_loading_are_blocked_by_closed_grammar(
    source: bytes,
) -> None:
    with pytest.raises(PhiImportGraphFixtureError, match=_IMPORT_ONLY_ERROR):
        _produce({"model.py": source})


@pytest.mark.parametrize(
    "source",
    [
        b"import sys\nsys.path = []\n",
        b"import sys\nsys.modules['x'] = object()\n",
        b"import sys\nsys.path.append('x')\n",
    ],
)
def test_import_state_mutation_is_blocked_by_closed_grammar(source: bytes) -> None:
    with pytest.raises(PhiImportGraphFixtureError, match=_IMPORT_ONLY_ERROR):
        _produce({"model.py": source})


def test_unknown_import_is_blocked_instead_of_guessed() -> None:
    with pytest.raises(PhiImportGraphFixtureError, match="unresolved"):
        _produce({"model.py": b"import unknown_package\n"})


def test_missing_remote_package_submodule_is_blocked() -> None:
    sources = {"pkg/__init__.py": b"from pkg import missing\n"}
    with pytest.raises(PhiImportGraphFixtureError, match="not manifested"):
        _produce(sources)


def test_remote_star_import_is_blocked() -> None:
    sources = {
        "model.py": b"from pkg import *\n",
        "pkg/__init__.py": b"import json\n",
    }
    with pytest.raises(PhiImportGraphFixtureError, match="star import"):
        _produce(sources)


@pytest.mark.parametrize(
    ("path", "source"),
    [
        ("pkg/model.py", b"from .. import x\n"),
        ("pkg/model.py", b"from ..json import x\n"),
        ("model.py", b"from .json import x\n"),
    ],
)
def test_relative_import_escape_is_blocked(path: str, source: bytes) -> None:
    with pytest.raises(PhiImportGraphFixtureError, match="relative import"):
        _produce({path: source})


def test_source_key_set_must_equal_manifest_paths() -> None:
    sources = {"model.py": b"import json\n"}
    manifest = _manifest(sources)
    with pytest.raises(PhiImportGraphFixtureError, match="source paths"):
        produce_phi_reachable_import_graph_fixture(
            manifest,
            {**sources, "extra.py": b""},
            _binding(),
            _policy(),
        )


def test_source_bytes_must_match_manifest_identity() -> None:
    sources = {"model.py": b"import json\n"}
    manifest = _manifest(sources)
    with pytest.raises(PhiImportGraphFixtureError, match="identity mismatch"):
        produce_phi_reachable_import_graph_fixture(
            manifest,
            {"model.py": b"import os\n"},
            _binding(),
            _policy(),
        )


def test_forged_manifest_identity_is_blocked() -> None:
    sources = {"model.py": b"import json\n"}
    parsed = _manifest(sources)
    forged = replace(parsed, sha256="0" * 64)
    with pytest.raises(PhiImportGraphFixtureError, match=r"forged|stale"):
        produce_phi_reachable_import_graph_fixture(forged, sources, _binding(), _policy())


def test_non_python_manifest_path_is_blocked() -> None:
    sources = {"config.json": b"{}"}
    manifest = _manifest(sources)
    with pytest.raises(PhiImportGraphFixtureError, match="Python manifest files"):
        produce_phi_reachable_import_graph_fixture(manifest, sources, _binding(), _policy())


@pytest.mark.parametrize(
    "binding",
    [
        PhiImportGraphRuntimeBinding("sha256:bad", "3.11.9", _LOCK),
        PhiImportGraphRuntimeBinding(_OCI, "", _LOCK),
        PhiImportGraphRuntimeBinding(_OCI, "3.11\\x", _LOCK),
        PhiImportGraphRuntimeBinding(_OCI, "3.11.9", "bad"),
    ],
)
def test_runtime_binding_grammar_is_fail_closed(binding: PhiImportGraphRuntimeBinding) -> None:
    with pytest.raises(PhiImportGraphFixtureError):
        _produce({"model.py": b"import json\n"}, binding=binding)


@pytest.mark.parametrize(
    "policy",
    [
        PhiImportGraphBoundaryPolicy(("sys", "os"), ("torch",)),
        PhiImportGraphBoundaryPolicy(("sys", "sys.path"), ("torch",)),
        PhiImportGraphBoundaryPolicy(("sys",), ("sys",)),
        PhiImportGraphBoundaryPolicy(("model",), ("torch",)),
    ],
)
def test_boundary_policy_must_be_closed_unique_nonoverlapping(
    policy: PhiImportGraphBoundaryPolicy,
) -> None:
    with pytest.raises(PhiImportGraphFixtureError):
        _produce({"model.py": b"import json\n"}, policy=policy)


def test_artifact_bom_and_trailing_newline_are_blocked() -> None:
    sources = {"model.py": b"import json\n"}
    manifest, artifact = _produce(sources)
    payloads = (
        b"\xef\xbb\xbf" + artifact.canonical_bytes,
        artifact.canonical_bytes + b"\n",
    )
    for payload in payloads:
        with pytest.raises(PhiImportGraphFixtureError):
            verify_phi_reachable_import_graph_fixture(
                payload,
                manifest,
                sources,
                _binding(),
                _policy(),
            )


def test_noncanonical_json_whitespace_is_blocked() -> None:
    sources = {"model.py": b"import json\n"}
    manifest, artifact = _produce(sources)
    payload = artifact.canonical_bytes.replace(b":", b": ", 1)

    with pytest.raises(PhiImportGraphFixtureError, match="canonical JSON"):
        verify_phi_reachable_import_graph_fixture(
            payload,
            manifest,
            sources,
            _binding(),
            _policy(),
        )


def test_duplicate_json_member_is_blocked() -> None:
    sources = {"model.py": b"import json\n"}
    manifest, artifact = _produce(sources)
    payload = artifact.canonical_bytes.replace(
        b'{"artifact_version":',
        b'{"artifact_version":"x","artifact_version":',
        1,
    )
    with pytest.raises(PhiImportGraphFixtureError, match="duplicate"):
        verify_phi_reachable_import_graph_fixture(
            payload,
            manifest,
            sources,
            _binding(),
            _policy(),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_manifest_sha256", "0" * 64),
        ("base_container_oci_digest", "sha256:" + "0" * 64),
        ("python_version", "9.9"),
        ("dependency_lock_sha256", "0" * 64),
        ("unresolved_imports", ["x"]),
        ("unresolved_dynamic_imports", ["x"]),
    ],
)
def test_bound_or_unresolved_artifact_mutations_are_blocked(
    field: str,
    value: object,
) -> None:
    sources = {"model.py": b"import json\n"}
    manifest, artifact = _produce(sources)
    doc = _document(artifact.canonical_bytes)
    doc[field] = value
    with pytest.raises(PhiImportGraphFixtureError):
        verify_phi_reachable_import_graph_fixture(
            _canonical(doc),
            manifest,
            sources,
            _binding(),
            _policy(),
        )


def test_missing_manifest_node_is_blocked() -> None:
    sources = {"model.py": b"import json\n"}
    manifest, artifact = _produce(sources)
    doc = _document(artifact.canonical_bytes)
    raw_nodes = doc["nodes"]
    assert isinstance(raw_nodes, list)
    nodes = cast(list[dict[str, object]], raw_nodes)
    doc["nodes"] = [node for node in nodes if node["kind"] != "MANIFEST_FILE"]
    with pytest.raises(PhiImportGraphFixtureError, match="producer relationship set"):
        verify_phi_reachable_import_graph_fixture(
            _canonical(doc),
            manifest,
            sources,
            _binding(),
            _policy(),
        )


def test_unreferenced_boundary_node_is_blocked() -> None:
    sources = {"model.py": b"import json\n"}
    manifest, artifact = _produce(sources)
    doc = _document(artifact.canonical_bytes)
    raw_nodes = doc["nodes"]
    assert isinstance(raw_nodes, list)
    nodes = cast(list[dict[str, object]], raw_nodes)
    nodes.append({"identity": "os", "kind": "PYTHON_RUNTIME_MODULE"})
    nodes.sort(key=lambda node: (node["kind"], node["identity"]))
    with pytest.raises(PhiImportGraphFixtureError, match="producer relationship set"):
        verify_phi_reachable_import_graph_fixture(
            _canonical(doc),
            manifest,
            sources,
            _binding(),
            _policy(),
        )


def test_omitted_producer_relationship_is_blocked_even_if_schema_valid() -> None:
    sources = {"model.py": b"import json\nimport os\n"}
    manifest, artifact = _produce(sources)
    doc = _document(artifact.canonical_bytes)
    raw_edges = doc["edges"]
    raw_nodes = doc["nodes"]
    assert isinstance(raw_edges, list) and isinstance(raw_nodes, list)
    edges = cast(list[dict[str, object]], raw_edges)
    nodes = cast(list[dict[str, object]], raw_nodes)
    doc["edges"] = [edge for edge in edges if edge["target_identity"] != "os"]
    doc["nodes"] = [node for node in nodes if node["identity"] != "os"]
    with pytest.raises(PhiImportGraphFixtureError, match="producer relationship set"):
        verify_phi_reachable_import_graph_fixture(
            _canonical(doc),
            manifest,
            sources,
            _binding(),
            _policy(),
        )


def test_spurious_producer_relationship_is_blocked_even_if_schema_valid() -> None:
    sources = {"model.py": b"import json\n"}
    manifest, artifact = _produce(sources)
    doc = _document(artifact.canonical_bytes)
    raw_nodes = doc["nodes"]
    raw_edges = doc["edges"]
    assert isinstance(raw_nodes, list) and isinstance(raw_edges, list)
    nodes = cast(list[dict[str, object]], raw_nodes)
    edges = cast(list[dict[str, object]], raw_edges)
    nodes.append({"identity": "os", "kind": "PYTHON_RUNTIME_MODULE"})
    edges.append(
        {
            "import_name": "os",
            "source_identity": "model.py",
            "source_kind": "MANIFEST_FILE",
            "target_identity": "os",
            "target_kind": "PYTHON_RUNTIME_MODULE",
        }
    )
    nodes.sort(key=lambda node: (node["kind"], node["identity"]))
    edges.sort(
        key=lambda edge: (
            edge["source_kind"],
            edge["source_identity"],
            edge["import_name"],
            edge["target_kind"],
            edge["target_identity"],
        )
    )
    with pytest.raises(PhiImportGraphFixtureError, match="producer relationship set"):
        verify_phi_reachable_import_graph_fixture(
            _canonical(doc),
            manifest,
            sources,
            _binding(),
            _policy(),
        )
