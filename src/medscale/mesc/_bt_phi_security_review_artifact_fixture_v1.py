"""Fixture-only Phi security-review artifact conformance verification.

The verifier accepts caller-supplied in-memory artifact, manifest, graph, and fixture
source bytes. It validates byte-level conformance and graph-to-manifest binding only.
It does not perform a security review, authenticate a reviewer, read real Phi source,
or access filesystem, network, provider, model, prompt, inference, or training paths.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Final, Never, cast

from medscale.mesc._bt_phi_import_graph_fixture_v1 import (
    PhiImportGraphBoundaryPolicy,
    PhiImportGraphFixtureError,
    PhiImportGraphRuntimeBinding,
    verify_phi_reachable_import_graph_fixture,
)
from medscale.mesc._bt_phi_remote_code_fixture_v1 import (
    PhiRemoteCodeManifest,
    canonical_phi_remote_code_manifest_bytes,
    parse_phi_remote_code_manifest,
)

_VERSION: Final = "MESC-BT-PHI-SECURITY-REVIEW-ARTIFACT-V1"
_PASS: Final = "PASS"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_PATH: Final = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$")
_REVIEWER: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")
_BOM: Final = b"\xef\xbb\xbf"
_TOP_LEVEL_KEYS: Final = frozenset(
    {
        "artifact_version",
        "complete_reachable_import_graph_disposition",
        "complete_reachable_import_graph_reviewed",
        "file_dispositions",
        "independent_review",
        "manifest_sha256",
        "overall_disposition",
        "reachable_import_graph_artifact_sha256",
        "reviewer_identity",
    }
)
_FILE_DISPOSITION_KEYS: Final = frozenset({"disposition", "path"})


class PhiSecurityReviewArtifactFixtureError(ValueError):
    """Fail-closed fixture security-review artifact conformance error."""


@dataclass(frozen=True, slots=True)
class PhiSecurityReviewArtifact:
    """Exact validated fixture artifact bytes and their SHA-256 identity."""

    canonical_bytes: bytes
    sha256: str


def verify_phi_security_review_artifact_fixture(
    payload: bytes,
    manifest: PhiRemoteCodeManifest,
    graph_payload: bytes,
    graph_sources: dict[str, bytes],
    runtime_binding: PhiImportGraphRuntimeBinding,
    boundary_policy: PhiImportGraphBoundaryPolicy,
) -> PhiSecurityReviewArtifact:
    """Validate one caller-supplied V1 fixture artifact without performing review."""
    manifest = _manifest(manifest)
    graph_sha256, graph_manifest_sha256 = _graph(
        graph_payload,
        manifest,
        graph_sources,
        runtime_binding,
        boundary_policy,
    )

    if type(payload) is not bytes:
        raise PhiSecurityReviewArtifactFixtureError("artifact must be exact built-in bytes")
    if payload.startswith(_BOM):
        raise PhiSecurityReviewArtifactFixtureError("UTF-8 BOM is prohibited")

    parsed = _load_json(payload)
    if type(parsed) is not dict:
        raise PhiSecurityReviewArtifactFixtureError("top level must be exactly one JSON object")
    document = cast(dict[str, object], parsed)
    _validate_document(
        document,
        manifest,
        graph_sha256=graph_sha256,
        graph_manifest_sha256=graph_manifest_sha256,
    )

    canonical = _canonical(document)
    if payload != canonical:
        raise PhiSecurityReviewArtifactFixtureError(
            "artifact is not the exact canonical ASCII JSON serialization"
        )

    return PhiSecurityReviewArtifact(
        canonical_bytes=canonical,
        sha256=hashlib.sha256(canonical).hexdigest(),
    )


def _manifest(manifest: PhiRemoteCodeManifest) -> PhiRemoteCodeManifest:
    if type(manifest) is not PhiRemoteCodeManifest:
        raise PhiSecurityReviewArtifactFixtureError("manifest is not parser-validated")
    try:
        canonical = canonical_phi_remote_code_manifest_bytes(manifest.entries)
        reparsed = parse_phi_remote_code_manifest(canonical)
    except Exception as error:
        raise PhiSecurityReviewArtifactFixtureError("manifest content is not canonical") from error
    if reparsed != manifest:
        raise PhiSecurityReviewArtifactFixtureError("manifest identity is forged or stale")
    return manifest


def _graph(
    graph_payload: bytes,
    manifest: PhiRemoteCodeManifest,
    graph_sources: dict[str, bytes],
    runtime_binding: PhiImportGraphRuntimeBinding,
    boundary_policy: PhiImportGraphBoundaryPolicy,
) -> tuple[str, str]:
    try:
        verify_phi_reachable_import_graph_fixture(
            graph_payload,
            manifest,
            graph_sources,
            runtime_binding,
            boundary_policy,
        )
    except PhiImportGraphFixtureError as error:
        raise PhiSecurityReviewArtifactFixtureError(
            "reachable import graph artifact is not valid for the supplied fixture inputs"
        ) from error

    value: object = json.loads(graph_payload)
    if type(value) is not dict:
        raise PhiSecurityReviewArtifactFixtureError("validated graph must be a JSON object")
    graph = cast(dict[str, object], value)
    source_manifest = graph.get("source_manifest_sha256")
    if type(source_manifest) is not str or _SHA256.fullmatch(source_manifest) is None:
        raise PhiSecurityReviewArtifactFixtureError(
            "validated graph lacks an in-artifact source_manifest_sha256 binding"
        )
    return hashlib.sha256(graph_payload).hexdigest(), source_manifest


def _validate_document(
    document: dict[str, object],
    manifest: PhiRemoteCodeManifest,
    *,
    graph_sha256: str,
    graph_manifest_sha256: str,
) -> None:
    if frozenset(document) != _TOP_LEVEL_KEYS:
        raise PhiSecurityReviewArtifactFixtureError("artifact has an invalid top-level member set")

    _require_exact_string(
        document["artifact_version"],
        field="artifact_version",
        expected=_VERSION,
    )
    _require_exact_true(document["independent_review"], field="independent_review")
    _require_exact_true(
        document["complete_reachable_import_graph_reviewed"],
        field="complete_reachable_import_graph_reviewed",
    )
    _require_exact_string(
        document["complete_reachable_import_graph_disposition"],
        field="complete_reachable_import_graph_disposition",
        expected=_PASS,
    )
    _require_exact_string(
        document["overall_disposition"],
        field="overall_disposition",
        expected=_PASS,
    )

    manifest_sha256 = _require_sha256(document["manifest_sha256"], field="manifest_sha256")
    if manifest_sha256 != manifest.sha256:
        raise PhiSecurityReviewArtifactFixtureError(
            "manifest_sha256 does not equal the canonical supplied manifest identity"
        )
    if graph_manifest_sha256 != manifest_sha256:
        raise PhiSecurityReviewArtifactFixtureError(
            "graph source_manifest_sha256 does not equal artifact manifest_sha256"
        )

    bound_graph_sha256 = _require_sha256(
        document["reachable_import_graph_artifact_sha256"],
        field="reachable_import_graph_artifact_sha256",
    )
    if bound_graph_sha256 != graph_sha256:
        raise PhiSecurityReviewArtifactFixtureError(
            "reachable_import_graph_artifact_sha256 does not reproduce graph bytes"
        )

    reviewer_identity = document["reviewer_identity"]
    if type(reviewer_identity) is not str or _REVIEWER.fullmatch(reviewer_identity) is None:
        raise PhiSecurityReviewArtifactFixtureError("reviewer_identity violates the frozen grammar")

    _validate_file_dispositions(document["file_dispositions"], manifest)


def _validate_file_dispositions(value: object, manifest: PhiRemoteCodeManifest) -> None:
    if type(value) is not list:
        raise PhiSecurityReviewArtifactFixtureError("file_dispositions must be an exact JSON array")
    rows = cast(list[object], value)
    if len(rows) != len(manifest.entries):
        raise PhiSecurityReviewArtifactFixtureError(
            "file_dispositions must contain exactly one row per manifest path"
        )

    for index, (raw_row, manifest_entry) in enumerate(zip(rows, manifest.entries, strict=True)):
        if type(raw_row) is not dict:
            raise PhiSecurityReviewArtifactFixtureError(
                f"file_dispositions[{index}] must be an exact JSON object"
            )
        row = cast(dict[str, object], raw_row)
        if frozenset(row) != _FILE_DISPOSITION_KEYS:
            raise PhiSecurityReviewArtifactFixtureError(
                f"file_dispositions[{index}] has an invalid member set"
            )

        disposition = row["disposition"]
        path = row["path"]
        if type(disposition) is not str or disposition != _PASS:
            raise PhiSecurityReviewArtifactFixtureError(
                f"file_dispositions[{index}].disposition must be PASS"
            )
        if type(path) is not str or _PATH.fullmatch(path) is None:
            raise PhiSecurityReviewArtifactFixtureError(
                f"file_dispositions[{index}].path violates the frozen grammar"
            )
        if any(component in {".", ".."} for component in path.split("/")):
            raise PhiSecurityReviewArtifactFixtureError(
                f"file_dispositions[{index}].path contains a dot component"
            )
        if path != manifest_entry.path:
            raise PhiSecurityReviewArtifactFixtureError(
                "file_dispositions must equal the canonical manifest path order exactly"
            )


def _require_exact_string(actual: object, *, field: str, expected: str) -> None:
    if type(actual) is not str or actual != expected:
        raise PhiSecurityReviewArtifactFixtureError(f"{field} must be exactly {expected!r}")


def _require_exact_true(actual: object, *, field: str) -> None:
    if type(actual) is not bool or actual is not True:
        raise PhiSecurityReviewArtifactFixtureError(f"{field} must be exact JSON true")


def _require_sha256(actual: object, *, field: str) -> str:
    if type(actual) is not str or _SHA256.fullmatch(actual) is None:
        raise PhiSecurityReviewArtifactFixtureError(f"{field} must be 64 lowercase hex characters")
    return actual


def _canonical(document: dict[str, object]) -> bytes:
    try:
        text = json.dumps(
            document,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        return text.encode("ascii")
    except (TypeError, UnicodeEncodeError, ValueError) as error:
        raise PhiSecurityReviewArtifactFixtureError(
            "artifact cannot be serialized as canonical ASCII JSON"
        ) from error


def _load_json(payload: bytes) -> object:
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise PhiSecurityReviewArtifactFixtureError("artifact must be valid UTF-8") from error

    try:
        return json.loads(
            text,
            object_pairs_hook=_object_from_unique_pairs,
            parse_constant=_reject_json_constant,
        )
    except PhiSecurityReviewArtifactFixtureError:
        raise
    except (ValueError, RecursionError) as error:
        raise PhiSecurityReviewArtifactFixtureError("artifact is not valid JSON") from error


def _object_from_unique_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    document: dict[str, object] = {}
    for key, value in pairs:
        if key in document:
            raise PhiSecurityReviewArtifactFixtureError(f"duplicate JSON member: {key!r}")
        document[key] = value
    return document


def _reject_json_constant(value: str) -> Never:
    raise PhiSecurityReviewArtifactFixtureError(
        f"non-standard JSON constant is prohibited: {value}"
    )
