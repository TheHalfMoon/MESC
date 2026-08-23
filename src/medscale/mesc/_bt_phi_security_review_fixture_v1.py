"""Fail-closed fixture validation for Phi remote-code security-review evidence.

This module validates only caller-supplied review evidence for the
``FD-MESC-BT-EXEC-1`` Section C.3 requirement that an independent security
review bind the canonical Phi remote-code manifest, record PASS for every
manifest file, and record PASS for the complete reachable import graph. It does
not inspect Phi source, construct an import graph, perform a security review,
access a filesystem or network, import or execute remote code, access a model
or provider, dispatch prompts, run inference, rank candidates, select a winner,
or train.
"""

from __future__ import annotations

from dataclasses import dataclass

from medscale.mesc._bt_phi_remote_code_fixture_v1 import (
    PhiRemoteCodeManifest,
    PhiRemoteCodeManifestEntry,
    canonical_phi_remote_code_manifest_bytes,
    parse_phi_remote_code_manifest,
)

_PASS = "PASS"


class PhiSecurityReviewError(ValueError):
    """Base class for fail-closed Phi security-review evidence violations."""


class PhiSecurityReviewManifestError(PhiSecurityReviewError):
    """The supplied manifest is not a parser-validated canonical manifest."""


class PhiSecurityReviewEvidenceError(PhiSecurityReviewError):
    """The supplied security-review evidence is malformed or incomplete."""


@dataclass(frozen=True, slots=True)
class PhiRemoteCodeFileSecurityDisposition:
    """Injected security-review disposition for one canonical manifest path."""

    path: str
    disposition: str


@dataclass(frozen=True, slots=True)
class PhiRemoteCodeSecurityReviewEvidence:
    """Injected independent security-review evidence bound to one manifest."""

    manifest_sha256: str
    independent_review: bool
    file_dispositions: tuple[PhiRemoteCodeFileSecurityDisposition, ...]
    complete_reachable_import_graph_reviewed: bool
    complete_reachable_import_graph_disposition: str


def verify_phi_security_review_evidence(
    manifest: PhiRemoteCodeManifest,
    evidence: PhiRemoteCodeSecurityReviewEvidence,
) -> None:
    """Verify injected security-review evidence against a canonical manifest."""
    _revalidate_manifest(manifest)
    _validate_evidence_shape(evidence)

    if evidence.manifest_sha256 != manifest.sha256:
        raise PhiSecurityReviewEvidenceError(
            "security-review evidence is not bound to the canonical manifest SHA-256"
        )

    expected_paths = tuple(entry.path for entry in manifest.entries)
    reviewed_paths = tuple(item.path for item in evidence.file_dispositions)
    if reviewed_paths != expected_paths:
        raise PhiSecurityReviewEvidenceError(
            "security-review file dispositions do not equal the canonical manifest paths"
        )

    if any(item.disposition != _PASS for item in evidence.file_dispositions):
        raise PhiSecurityReviewEvidenceError(
            "every canonical Phi remote-code file must have security-review disposition PASS"
        )


def _revalidate_manifest(manifest: PhiRemoteCodeManifest) -> None:
    if type(manifest) is not PhiRemoteCodeManifest:
        raise PhiSecurityReviewManifestError("manifest is not parser-validated")
    _validate_manifest_object_types(manifest)

    try:
        canonical = canonical_phi_remote_code_manifest_bytes(manifest.entries)
        reparsed = parse_phi_remote_code_manifest(canonical)
    except Exception as error:
        raise PhiSecurityReviewManifestError(
            "manifest object does not contain valid canonical manifest content"
        ) from error

    if reparsed != manifest:
        raise PhiSecurityReviewManifestError(
            "manifest object identity does not match its canonical bytes"
        )


def _validate_manifest_object_types(manifest: PhiRemoteCodeManifest) -> None:
    if type(manifest.entries) is not tuple:
        raise PhiSecurityReviewManifestError("manifest object contains non-exact field types")
    if type(manifest.sha256) is not str or type(manifest.byte_length) is not int:
        raise PhiSecurityReviewManifestError("manifest object contains non-exact field types")

    for entry in manifest.entries:
        if type(entry) is not PhiRemoteCodeManifestEntry:
            raise PhiSecurityReviewManifestError("manifest object contains non-exact field types")
        if type(entry.byte_length) is not int:
            raise PhiSecurityReviewManifestError("manifest object contains non-exact field types")
        if (
            type(entry.git_blob_sha) is not str
            or type(entry.path) is not str
            or type(entry.sha256) is not str
        ):
            raise PhiSecurityReviewManifestError("manifest object contains non-exact field types")


def _validate_evidence_shape(evidence: PhiRemoteCodeSecurityReviewEvidence) -> None:
    if type(evidence) is not PhiRemoteCodeSecurityReviewEvidence:
        raise PhiSecurityReviewEvidenceError("security-review evidence has invalid type")
    if type(evidence.manifest_sha256) is not str:
        raise PhiSecurityReviewEvidenceError("manifest SHA-256 binding must be an exact string")
    if type(evidence.independent_review) is not bool or evidence.independent_review is not True:
        raise PhiSecurityReviewEvidenceError("independent security review is not proven")

    dispositions = evidence.file_dispositions
    if type(dispositions) is not tuple:
        raise PhiSecurityReviewEvidenceError("file dispositions must be an exact tuple")
    for item in dispositions:
        if type(item) is not PhiRemoteCodeFileSecurityDisposition:
            raise PhiSecurityReviewEvidenceError("file disposition has invalid type")
        if type(item.path) is not str or type(item.disposition) is not str:
            raise PhiSecurityReviewEvidenceError("file disposition fields must be exact strings")

    if (
        type(evidence.complete_reachable_import_graph_reviewed) is not bool
        or evidence.complete_reachable_import_graph_reviewed is not True
    ):
        raise PhiSecurityReviewEvidenceError("complete reachable import graph review is not proven")
    if type(evidence.complete_reachable_import_graph_disposition) is not str:
        raise PhiSecurityReviewEvidenceError(
            "complete import-graph disposition must be an exact string"
        )
    if evidence.complete_reachable_import_graph_disposition != _PASS:
        raise PhiSecurityReviewEvidenceError(
            "complete reachable import graph must have security-review disposition PASS"
        )
