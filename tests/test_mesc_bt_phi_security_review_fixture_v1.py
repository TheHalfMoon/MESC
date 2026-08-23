"""Fixture-only qualification for the Phi security-review evidence binder."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._bt_phi_remote_code_fixture_v1 import (
    PhiRemoteCodeManifest,
    PhiRemoteCodeManifestEntry,
    parse_phi_remote_code_manifest,
)
from medscale.mesc._bt_phi_security_review_fixture_v1 import (
    PhiRemoteCodeFileSecurityDisposition,
    PhiRemoteCodeSecurityReviewEvidence,
    PhiSecurityReviewEvidenceError,
    PhiSecurityReviewManifestError,
    verify_phi_security_review_evidence,
)

_BLOB_A = "a" * 40
_BLOB_B = "b" * 40
_DIGEST_A = "c" * 64
_DIGEST_B = "d" * 64


class _StringSubclass(str):
    """String subclass that compares equal to a canonical plain string."""


class _IntSubclass(int):
    """Integer subclass that compares equal to a canonical plain integer."""


class _PathSpoof:
    """Non-string equality spoof used to regression-test exact path typing."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, str) and other == self.value


def _entry(byte_length: int, blob_sha: str, path: str, sha256: str) -> str:
    return (
        f'{{"byte_length":{byte_length},"git_blob_sha":"{blob_sha}",'
        f'"path":"{path}","sha256":"{sha256}"}}'
    )


def _manifest() -> PhiRemoteCodeManifest:
    payload = (
        "["
        + ",".join(
            [
                _entry(12, _BLOB_A, "modeling_phi4mm.py", _DIGEST_A),
                _entry(34, _BLOB_B, "processing_phi4mm.py", _DIGEST_B),
            ]
        )
        + "]"
    ).encode("ascii")
    return parse_phi_remote_code_manifest(payload)


def _evidence(manifest: PhiRemoteCodeManifest) -> PhiRemoteCodeSecurityReviewEvidence:
    return PhiRemoteCodeSecurityReviewEvidence(
        manifest_sha256=manifest.sha256,
        independent_review=True,
        file_dispositions=tuple(
            PhiRemoteCodeFileSecurityDisposition(path=entry.path, disposition="PASS")
            for entry in manifest.entries
        ),
        complete_reachable_import_graph_reviewed=True,
        complete_reachable_import_graph_disposition="PASS",
    )


def test_valid_independent_security_review_evidence_passes() -> None:
    manifest = _manifest()

    verify_phi_security_review_evidence(manifest, _evidence(manifest))


def test_forged_manifest_digest_is_rejected_before_evidence_acceptance() -> None:
    manifest = _manifest()
    forged = PhiRemoteCodeManifest(
        entries=manifest.entries,
        sha256="0" * 64,
        byte_length=manifest.byte_length,
    )
    malformed_evidence = cast(PhiRemoteCodeSecurityReviewEvidence, object())

    with pytest.raises(PhiSecurityReviewManifestError, match="canonical bytes"):
        verify_phi_security_review_evidence(forged, malformed_evidence)


def test_manifest_revalidation_rejects_nested_string_subclass_spoof() -> None:
    manifest = _manifest()
    first, second = manifest.entries
    forged_first = PhiRemoteCodeManifestEntry(
        byte_length=first.byte_length,
        git_blob_sha=first.git_blob_sha,
        path=_StringSubclass(first.path),
        sha256=first.sha256,
    )
    forged = PhiRemoteCodeManifest(
        entries=(forged_first, second),
        sha256=manifest.sha256,
        byte_length=manifest.byte_length,
    )
    assert forged == manifest

    with pytest.raises(PhiSecurityReviewManifestError, match="non-exact field types"):
        verify_phi_security_review_evidence(forged, _evidence(manifest))


def test_manifest_revalidation_rejects_outer_integer_subclass_spoof() -> None:
    manifest = _manifest()
    forged = PhiRemoteCodeManifest(
        entries=manifest.entries,
        sha256=manifest.sha256,
        byte_length=_IntSubclass(manifest.byte_length),
    )
    assert forged == manifest

    with pytest.raises(PhiSecurityReviewManifestError, match="non-exact field types"):
        verify_phi_security_review_evidence(forged, _evidence(manifest))


def test_manifest_requires_exact_validated_type() -> None:
    manifest = _manifest()

    with pytest.raises(PhiSecurityReviewManifestError, match="parser-validated"):
        verify_phi_security_review_evidence(
            cast(PhiRemoteCodeManifest, object()),
            _evidence(manifest),
        )


def test_evidence_requires_exact_type() -> None:
    manifest = _manifest()

    with pytest.raises(PhiSecurityReviewEvidenceError, match="invalid type"):
        verify_phi_security_review_evidence(
            manifest,
            cast(PhiRemoteCodeSecurityReviewEvidence, object()),
        )


def test_manifest_sha_binding_requires_exact_string_and_exact_digest() -> None:
    manifest = _manifest()
    valid = _evidence(manifest)
    invalid_evidence = (
        replace(valid, manifest_sha256="0" * 64),
        replace(valid, manifest_sha256=_StringSubclass(manifest.sha256)),
    )

    for invalid in invalid_evidence:
        with pytest.raises(PhiSecurityReviewEvidenceError):
            verify_phi_security_review_evidence(manifest, invalid)


def test_independent_review_requires_exact_true() -> None:
    manifest = _manifest()
    valid = _evidence(manifest)
    invalid_evidence = (
        replace(valid, independent_review=False),
        replace(valid, independent_review=cast(bool, 1)),
    )

    for invalid in invalid_evidence:
        with pytest.raises(PhiSecurityReviewEvidenceError, match="independent"):
            verify_phi_security_review_evidence(manifest, invalid)


def test_file_dispositions_require_exact_tuple() -> None:
    manifest = _manifest()
    valid = _evidence(manifest)
    invalid = cast(
        tuple[PhiRemoteCodeFileSecurityDisposition, ...],
        list(valid.file_dispositions),
    )

    with pytest.raises(PhiSecurityReviewEvidenceError, match="exact tuple"):
        verify_phi_security_review_evidence(
            manifest,
            replace(valid, file_dispositions=invalid),
        )


def test_file_disposition_requires_exact_dataclass_type() -> None:
    manifest = _manifest()
    valid = _evidence(manifest)
    invalid = cast(
        tuple[PhiRemoteCodeFileSecurityDisposition, ...],
        (object(), valid.file_dispositions[1]),
    )

    with pytest.raises(PhiSecurityReviewEvidenceError, match="invalid type"):
        verify_phi_security_review_evidence(
            manifest,
            replace(valid, file_dispositions=invalid),
        )


def test_file_disposition_rejects_non_string_path_equality_spoof() -> None:
    manifest = _manifest()
    valid = _evidence(manifest)
    first, second = valid.file_dispositions
    spoofed = PhiRemoteCodeFileSecurityDisposition(
        path=cast(str, _PathSpoof(first.path)),
        disposition=first.disposition,
    )
    assert spoofed.path == first.path

    with pytest.raises(PhiSecurityReviewEvidenceError, match="exact strings"):
        verify_phi_security_review_evidence(
            manifest,
            replace(valid, file_dispositions=(spoofed, second)),
        )


@pytest.mark.parametrize(
    "paths",
    [
        ("modeling_phi4mm.py",),
        ("modeling_phi4mm.py", "processing_phi4mm.py", "extra.py"),
        ("processing_phi4mm.py", "modeling_phi4mm.py"),
        ("modeling_phi4mm.py", "modeling_phi4mm.py"),
    ],
)
def test_reviewed_paths_must_equal_manifest_exactly(paths: tuple[str, ...]) -> None:
    manifest = _manifest()
    valid = _evidence(manifest)
    dispositions = tuple(
        PhiRemoteCodeFileSecurityDisposition(path=path, disposition="PASS") for path in paths
    )

    with pytest.raises(PhiSecurityReviewEvidenceError, match="do not equal"):
        verify_phi_security_review_evidence(
            manifest,
            replace(valid, file_dispositions=dispositions),
        )


def test_every_manifest_file_requires_exact_pass_disposition() -> None:
    manifest = _manifest()
    valid = _evidence(manifest)
    first, second = valid.file_dispositions
    invalid_evidence = (
        replace(
            valid,
            file_dispositions=(replace(first, disposition="FAIL"), second),
        ),
        replace(
            valid,
            file_dispositions=(
                replace(first, disposition=_StringSubclass("PASS")),
                second,
            ),
        ),
    )

    for invalid in invalid_evidence:
        with pytest.raises(PhiSecurityReviewEvidenceError):
            verify_phi_security_review_evidence(manifest, invalid)


def test_complete_import_graph_review_requires_exact_true() -> None:
    manifest = _manifest()
    valid = _evidence(manifest)
    invalid_evidence = (
        replace(valid, complete_reachable_import_graph_reviewed=False),
        replace(valid, complete_reachable_import_graph_reviewed=cast(bool, 1)),
    )

    for invalid in invalid_evidence:
        with pytest.raises(PhiSecurityReviewEvidenceError, match="import graph review"):
            verify_phi_security_review_evidence(manifest, invalid)


def test_complete_import_graph_requires_exact_pass_disposition() -> None:
    manifest = _manifest()
    valid = _evidence(manifest)
    invalid_evidence = (
        replace(valid, complete_reachable_import_graph_disposition="FAIL"),
        replace(
            valid,
            complete_reachable_import_graph_disposition=_StringSubclass("PASS"),
        ),
    )

    for invalid in invalid_evidence:
        with pytest.raises(PhiSecurityReviewEvidenceError, match="import-graph disposition|PASS"):
            verify_phi_security_review_evidence(manifest, invalid)
