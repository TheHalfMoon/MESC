"""Fixture-only qualification for Phi security-review artifact conformance."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._bt_phi_import_graph_fixture_v1 import (
    PhiImportGraphBoundaryPolicy,
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
from medscale.mesc._bt_phi_security_review_artifact_fixture_v1 import (
    PhiSecurityReviewArtifact,
    PhiSecurityReviewArtifactFixtureError,
    verify_phi_security_review_artifact_fixture,
)

_BLOB = "1" * 40
_OCI = "sha256:" + "2" * 64
_LOCK = "3" * 64


def _sources() -> dict[str, bytes]:
    return {
        "a.py": b"import json\n",
        "b.py": b"import os\n",
    }


def _manifest(sources: dict[str, bytes]) -> PhiRemoteCodeManifest:
    entries = tuple(
        PhiRemoteCodeManifestEntry(
            byte_length=len(source),
            git_blob_sha=_BLOB,
            path=path,
            sha256=hashlib.sha256(source).hexdigest(),
        )
        for path, source in sorted(sources.items())
    )
    return parse_phi_remote_code_manifest(canonical_phi_remote_code_manifest_bytes(entries))


def _binding() -> PhiImportGraphRuntimeBinding:
    return PhiImportGraphRuntimeBinding(_OCI, "3.11.9", _LOCK)


def _policy() -> PhiImportGraphBoundaryPolicy:
    return PhiImportGraphBoundaryPolicy(
        python_runtime_roots=("json", "os"),
        locked_dependency_roots=("torch",),
    )


def _graph(
    manifest: PhiRemoteCodeManifest,
    sources: dict[str, bytes],
) -> PhiReachableImportGraphArtifact:
    return produce_phi_reachable_import_graph_fixture(
        manifest,
        sources,
        _binding(),
        _policy(),
    )


def _document(
    manifest: PhiRemoteCodeManifest,
    graph: PhiReachableImportGraphArtifact,
) -> dict[str, object]:
    return {
        "artifact_version": "MESC-BT-PHI-SECURITY-REVIEW-ARTIFACT-V1",
        "complete_reachable_import_graph_disposition": "PASS",
        "complete_reachable_import_graph_reviewed": True,
        "file_dispositions": [
            {"disposition": "PASS", "path": entry.path} for entry in manifest.entries
        ],
        "independent_review": True,
        "manifest_sha256": manifest.sha256,
        "overall_disposition": "PASS",
        "reachable_import_graph_artifact_sha256": graph.sha256,
        "reviewer_identity": "fixture-reviewer-1",
    }


def _canonical(document: object) -> bytes:
    return json.dumps(
        document,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _fixture() -> tuple[
    dict[str, bytes],
    PhiRemoteCodeManifest,
    PhiReachableImportGraphArtifact,
    dict[str, object],
]:
    sources = _sources()
    manifest = _manifest(sources)
    graph = _graph(manifest, sources)
    return sources, manifest, graph, _document(manifest, graph)


def _verify(
    payload: bytes,
    sources: dict[str, bytes],
    manifest: PhiRemoteCodeManifest,
    graph_payload: bytes,
) -> PhiSecurityReviewArtifact:
    return verify_phi_security_review_artifact_fixture(
        payload,
        manifest,
        graph_payload,
        sources,
        _binding(),
        _policy(),
    )


def test_valid_artifact_is_canonical_and_digest_bound() -> None:
    sources, manifest, graph, document = _fixture()
    payload = _canonical(document)

    artifact = _verify(payload, sources, manifest, graph.canonical_bytes)

    assert artifact.canonical_bytes == payload
    assert artifact.sha256 == hashlib.sha256(payload).hexdigest()
    assert not payload.endswith(b"\n")


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (b"{", "not valid JSON"),
        (b"[]", "top level"),
        (b'{"x":NaN}', "non-standard JSON constant"),
    ],
)
def test_json_envelope_is_fail_closed(payload: bytes, match: str) -> None:
    sources, manifest, graph, _ = _fixture()

    with pytest.raises(PhiSecurityReviewArtifactFixtureError, match=match):
        _verify(payload, sources, manifest, graph.canonical_bytes)


def test_bom_trailing_newline_whitespace_and_escaped_ascii_are_noncanonical() -> None:
    sources, manifest, graph, document = _fixture()
    payload = _canonical(document)

    variants = (
        b"\xef\xbb\xbf" + payload,
        payload + b"\n",
        payload.replace(b"{", b"{ ", 1),
        payload.replace(b"fixture-reviewer-1", b"fixture-reviewer\\u002d1"),
    )
    for variant in variants:
        with pytest.raises(PhiSecurityReviewArtifactFixtureError):
            _verify(variant, sources, manifest, graph.canonical_bytes)


def test_duplicate_members_are_rejected_at_any_depth() -> None:
    sources, manifest, graph, _ = _fixture()
    payloads = (
        b'{"artifact_version":"x","artifact_version":"x"}',
        b'{"file_dispositions":[{"path":"a.py","path":"a.py"}]}',
        b'{"file_dispositions":[{"disposition":"PASS","disposition":"PASS"}]}',
    )

    for payload in payloads:
        with pytest.raises(PhiSecurityReviewArtifactFixtureError, match="duplicate JSON member"):
            _verify(payload, sources, manifest, graph.canonical_bytes)


def test_top_level_member_set_is_exact() -> None:
    sources, manifest, graph, document = _fixture()

    missing = dict(document)
    missing.pop("reviewer_identity")
    extra = dict(document)
    extra["detached_provenance"] = manifest.sha256

    for candidate in (missing, extra):
        with pytest.raises(PhiSecurityReviewArtifactFixtureError, match="top-level member set"):
            _verify(_canonical(candidate), sources, manifest, graph.canonical_bytes)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("artifact_version", "OTHER", "artifact_version"),
        ("independent_review", False, "independent_review"),
        ("independent_review", 1, "independent_review"),
        (
            "complete_reachable_import_graph_reviewed",
            False,
            "complete_reachable_import_graph_reviewed",
        ),
        (
            "complete_reachable_import_graph_disposition",
            "BLOCKED",
            "complete_reachable_import_graph_disposition",
        ),
        ("overall_disposition", "FAIL", "overall_disposition"),
    ],
)
def test_frozen_pass_controls_are_exact(field: str, value: object, match: str) -> None:
    sources, manifest, graph, document = _fixture()
    document[field] = value

    with pytest.raises(PhiSecurityReviewArtifactFixtureError, match=match):
        _verify(_canonical(document), sources, manifest, graph.canonical_bytes)


@pytest.mark.parametrize("reviewer", ["", " bad", "reviewer name", "x" * 257, 7])
def test_reviewer_identity_grammar_is_fail_closed(reviewer: object) -> None:
    sources, manifest, graph, document = _fixture()
    document["reviewer_identity"] = reviewer

    with pytest.raises(PhiSecurityReviewArtifactFixtureError, match="reviewer_identity"):
        _verify(_canonical(document), sources, manifest, graph.canonical_bytes)


def test_manifest_sha256_grammar_and_identity_are_bound() -> None:
    sources, manifest, graph, document = _fixture()

    malformed = dict(document)
    malformed["manifest_sha256"] = "bad"
    mismatch = dict(document)
    mismatch["manifest_sha256"] = "0" * 64

    with pytest.raises(PhiSecurityReviewArtifactFixtureError, match="64 lowercase hex"):
        _verify(_canonical(malformed), sources, manifest, graph.canonical_bytes)
    with pytest.raises(PhiSecurityReviewArtifactFixtureError, match="canonical supplied manifest"):
        _verify(_canonical(mismatch), sources, manifest, graph.canonical_bytes)


def test_graph_digest_grammar_and_exact_bytes_are_bound() -> None:
    sources, manifest, graph, document = _fixture()

    malformed = dict(document)
    malformed["reachable_import_graph_artifact_sha256"] = "bad"
    mismatch = dict(document)
    mismatch["reachable_import_graph_artifact_sha256"] = "0" * 64

    with pytest.raises(PhiSecurityReviewArtifactFixtureError, match="64 lowercase hex"):
        _verify(_canonical(malformed), sources, manifest, graph.canonical_bytes)
    with pytest.raises(
        PhiSecurityReviewArtifactFixtureError,
        match="does not reproduce graph bytes",
    ):
        _verify(_canonical(mismatch), sources, manifest, graph.canonical_bytes)


def test_file_dispositions_require_exact_manifest_mapping_and_order() -> None:
    sources, manifest, graph, document = _fixture()
    rows = cast(list[dict[str, object]], document["file_dispositions"])

    variants: list[dict[str, object]] = []

    missing = dict(document)
    missing["file_dispositions"] = rows[:-1]
    variants.append(missing)

    extra = dict(document)
    extra["file_dispositions"] = [*rows, {"disposition": "PASS", "path": "extra.py"}]
    variants.append(extra)

    reordered = dict(document)
    reordered["file_dispositions"] = list(reversed(rows))
    variants.append(reordered)

    duplicate = dict(document)
    duplicate["file_dispositions"] = [rows[0], rows[0]]
    variants.append(duplicate)

    for candidate in variants:
        with pytest.raises(PhiSecurityReviewArtifactFixtureError):
            _verify(_canonical(candidate), sources, manifest, graph.canonical_bytes)


def test_file_disposition_schema_path_and_pass_value_are_fail_closed() -> None:
    sources, manifest, graph, document = _fixture()
    rows = cast(list[dict[str, object]], document["file_dispositions"])

    wrong_members = dict(document)
    wrong_members["file_dispositions"] = [{"path": "a.py"}, rows[1]]

    wrong_disposition = dict(document)
    wrong_disposition["file_dispositions"] = [
        {"disposition": "FAIL", "path": "a.py"},
        rows[1],
    ]

    traversal = dict(document)
    traversal["file_dispositions"] = [
        {"disposition": "PASS", "path": "../a.py"},
        rows[1],
    ]

    with pytest.raises(PhiSecurityReviewArtifactFixtureError, match="invalid member set"):
        _verify(_canonical(wrong_members), sources, manifest, graph.canonical_bytes)
    with pytest.raises(PhiSecurityReviewArtifactFixtureError, match="disposition must be PASS"):
        _verify(_canonical(wrong_disposition), sources, manifest, graph.canonical_bytes)
    with pytest.raises(
        PhiSecurityReviewArtifactFixtureError,
        match=r"dot component|frozen grammar",
    ):
        _verify(_canonical(traversal), sources, manifest, graph.canonical_bytes)


def test_invalid_or_unreproducible_graph_artifact_is_blocked() -> None:
    sources, manifest, _, document = _fixture()

    with pytest.raises(PhiSecurityReviewArtifactFixtureError, match="graph artifact is not valid"):
        _verify(_canonical(document), sources, manifest, b"{}")


def test_graph_without_in_artifact_manifest_binding_is_blocked() -> None:
    sources, manifest, graph, document = _fixture()
    value: object = json.loads(graph.canonical_bytes)
    assert isinstance(value, dict)
    graph_document = cast(dict[str, object], value)
    graph_document.pop("source_manifest_sha256")
    detached_graph = _canonical(graph_document)

    document["reachable_import_graph_artifact_sha256"] = hashlib.sha256(detached_graph).hexdigest()

    with pytest.raises(PhiSecurityReviewArtifactFixtureError, match="graph artifact is not valid"):
        _verify(_canonical(document), sources, manifest, detached_graph)


def test_graph_manifest_binding_cannot_be_detached_or_changed() -> None:
    sources, manifest, graph, document = _fixture()
    value: object = json.loads(graph.canonical_bytes)
    assert isinstance(value, dict)
    graph_document = cast(dict[str, object], value)
    graph_document["source_manifest_sha256"] = "0" * 64
    wrong_graph = _canonical(graph_document)

    detached = dict(document)
    detached["detached_source_manifest_sha256"] = manifest.sha256
    detached["reachable_import_graph_artifact_sha256"] = hashlib.sha256(wrong_graph).hexdigest()

    with pytest.raises(PhiSecurityReviewArtifactFixtureError):
        _verify(_canonical(detached), sources, manifest, wrong_graph)


def test_graph_is_reverified_against_exact_fixture_sources_and_runtime() -> None:
    sources, manifest, graph, document = _fixture()
    changed_sources = dict(sources)
    changed_sources["a.py"] = b"import sys\n"

    with pytest.raises(PhiSecurityReviewArtifactFixtureError, match="graph artifact is not valid"):
        verify_phi_security_review_artifact_fixture(
            _canonical(document),
            manifest,
            graph.canonical_bytes,
            changed_sources,
            _binding(),
            _policy(),
        )


def test_forged_manifest_object_is_rejected() -> None:
    sources, manifest, graph, document = _fixture()
    forged = replace(manifest, sha256="0" * 64)

    with pytest.raises(PhiSecurityReviewArtifactFixtureError, match=r"forged|stale"):
        _verify(_canonical(document), sources, forged, graph.canonical_bytes)


def test_caller_manifest_mutation_after_snapshot_cannot_change_verification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources, manifest, graph, document = _fixture()
    payload = _canonical(document)
    original_sha256 = manifest.sha256

    def mutate_caller_then_verify(
        graph_payload: bytes,
        snapshot: PhiRemoteCodeManifest,
        graph_sources: dict[str, bytes],
        runtime_binding: PhiImportGraphRuntimeBinding,
        boundary_policy: PhiImportGraphBoundaryPolicy,
    ) -> None:
        object.__setattr__(manifest, "sha256", "0" * 64)
        verify_phi_reachable_import_graph_fixture(
            graph_payload,
            snapshot,
            graph_sources,
            runtime_binding,
            boundary_policy,
        )

    monkeypatch.setattr(
        "medscale.mesc._bt_phi_security_review_artifact_fixture_v1."
        "verify_phi_reachable_import_graph_fixture",
        mutate_caller_then_verify,
    )

    artifact = verify_phi_security_review_artifact_fixture(
        payload,
        manifest,
        graph.canonical_bytes,
        sources,
        _binding(),
        _policy(),
    )

    assert artifact.canonical_bytes == payload
    assert manifest.sha256 != original_sha256
