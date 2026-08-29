"""Deterministic non-authoritative MRL capability-matrix projection.

MRL-0702 defines the typed projection surface for ``CAPABILITY_MATRIX.json``.
The later MRL-0704 generator/check command will derive concrete rows from exact
canonical repository sources. This module performs no filesystem, Git, network,
model, data, runtime, GPU, or training access.

A capability row may report externally established authority, but the projection
itself can never create or extend authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from medscale.mesc._canonical_json_v1 import canonical_json_bytes, canonical_sha256

_SCHEMA_VERSION: Final = "MRL-CAPABILITY-MATRIX-V1"
_PROJECTION_KIND: Final = "DERIVED_NON_AUTHORITATIVE"
_GIT_SHA_PATTERN: Final = re.compile(r"^[0-9a-f]{40}$")
_SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
_CAPABILITY_ID_PATTERN: Final = re.compile(r"^[A-Z][A-Z0-9_]*$")
_IMPLEMENTATION_STATES: Final = frozenset(
    {
        "NOT_STARTED",
        "PARTIAL",
        "IMPLEMENTED",
        "BLOCKED",
        "HISTORICAL",
    }
)
_EVIDENCE_STATES: Final = frozenset(
    {
        "UNPROVEN",
        "PARTIAL",
        "PROVEN",
        "BLOCKED",
    }
)
_AUTHORITY_STATES: Final = frozenset(
    {
        "NOT_APPLICABLE",
        "NOT_AUTHORIZED",
        "AUTHORIZED_EXTERNALLY",
    }
)


class CapabilityMatrixError(ValueError):
    """Raised when a capability projection violates the MRL-0702 contract."""


@dataclass(frozen=True, slots=True)
class CapabilityRepositoryBinding:
    """Exact repository commit/tree represented by the projection."""

    commit_sha: str
    tree_sha: str

    def __post_init__(self) -> None:
        _require_git_sha(self.commit_sha, "commit_sha")
        _require_git_sha(self.tree_sha, "tree_sha")

    def to_dict(self) -> dict[str, str]:
        """Return the deterministic JSON representation."""
        return {"commit_sha": self.commit_sha, "tree_sha": self.tree_sha}


@dataclass(frozen=True, slots=True)
class CapabilitySourceBinding:
    """Exact canonical source identity used to derive the projection."""

    path: str
    git_blob_sha: str
    sha256: str

    def __post_init__(self) -> None:
        _require_source_path(self.path)
        _require_git_sha(self.git_blob_sha, "git_blob_sha")
        _require_sha256(self.sha256, "sha256")

    def to_dict(self) -> dict[str, str]:
        """Return the deterministic JSON representation."""
        return {
            "git_blob_sha": self.git_blob_sha,
            "path": self.path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class CapabilityMatrixEntry:
    """One derived capability claim with separated implementation/evidence/authority state."""

    capability_id: str
    implementation_state: str
    evidence_state: str
    authority_state: str
    canonical_source_paths: tuple[str, ...]
    evidence_refs: tuple[str, ...] = ()
    authority_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            type(self.capability_id) is not str
            or _CAPABILITY_ID_PATTERN.fullmatch(self.capability_id) is None
        ):
            raise CapabilityMatrixError("capability_id must be canonical uppercase identifier text")
        _require_state(
            self.implementation_state,
            "implementation_state",
            _IMPLEMENTATION_STATES,
        )
        _require_state(self.evidence_state, "evidence_state", _EVIDENCE_STATES)
        _require_state(self.authority_state, "authority_state", _AUTHORITY_STATES)
        _require_sorted_unique_paths(self.canonical_source_paths, "canonical_source_paths")
        _require_sorted_unique_refs(self.evidence_refs, "evidence_refs")
        _require_sorted_unique_refs(self.authority_refs, "authority_refs")
        if self.evidence_state == "PROVEN" and not self.evidence_refs:
            raise CapabilityMatrixError("PROVEN evidence_state requires evidence_refs")
        if self.authority_state == "AUTHORIZED_EXTERNALLY" and not self.authority_refs:
            raise CapabilityMatrixError("AUTHORIZED_EXTERNALLY requires authority_refs")
        if self.authority_state != "AUTHORIZED_EXTERNALLY" and self.authority_refs:
            raise CapabilityMatrixError(
                "authority_refs are only valid for AUTHORIZED_EXTERNALLY capability rows"
            )

    def to_dict(self) -> dict[str, object]:
        """Return the deterministic JSON representation."""
        return {
            "authority_refs": list(self.authority_refs),
            "authority_state": self.authority_state,
            "canonical_source_paths": list(self.canonical_source_paths),
            "capability_id": self.capability_id,
            "evidence_refs": list(self.evidence_refs),
            "evidence_state": self.evidence_state,
            "implementation_state": self.implementation_state,
        }


@dataclass(frozen=True, slots=True)
class CapabilityMatrixProjection:
    """MRL-0702 machine-readable capability matrix projection."""

    repository: CapabilityRepositoryBinding
    sources: tuple[CapabilitySourceBinding, ...]
    capabilities: tuple[CapabilityMatrixEntry, ...]

    def __post_init__(self) -> None:
        if type(self.repository) is not CapabilityRepositoryBinding:
            raise CapabilityMatrixError("repository must be an exact CapabilityRepositoryBinding")
        if type(self.sources) is not tuple:
            raise CapabilityMatrixError("sources must be an exact tuple")
        if type(self.capabilities) is not tuple:
            raise CapabilityMatrixError("capabilities must be an exact tuple")
        if not self.sources:
            raise CapabilityMatrixError("sources cannot be empty")
        if any(type(source) is not CapabilitySourceBinding for source in self.sources):
            raise CapabilityMatrixError("sources contains an invalid member type")
        if any(type(row) is not CapabilityMatrixEntry for row in self.capabilities):
            raise CapabilityMatrixError("capabilities contains an invalid member type")
        _require_unique_sorted_sources(self.sources)
        _require_unique_sorted_capabilities(self.capabilities)
        _require_projection_sources_cover_rows(self.sources, self.capabilities)

    @property
    def can_authorize(self) -> bool:
        """Capability projections can never grant authority."""
        return False

    @property
    def source_set_sha256(self) -> str:
        """Return SHA-256 over the canonical ordered source-binding array."""
        return canonical_sha256([source.to_dict() for source in self.sources])

    @property
    def semantic_bytes(self) -> bytes:
        """Return deterministic canonical JSON bytes for the projection."""
        return canonical_json_bytes(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """Return the complete non-authoritative projection payload."""
        return {
            "can_authorize": self.can_authorize,
            "capabilities": [row.to_dict() for row in self.capabilities],
            "projection_kind": _PROJECTION_KIND,
            "repository": self.repository.to_dict(),
            "schema_version": _SCHEMA_VERSION,
            "source_set_sha256": self.source_set_sha256,
            "sources": [source.to_dict() for source in self.sources],
        }


def _require_git_sha(value: object, field: str) -> None:
    if type(value) is not str or _GIT_SHA_PATTERN.fullmatch(value) is None:
        raise CapabilityMatrixError(f"{field} must be 40 lowercase hex characters")


def _require_sha256(value: object, field: str) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise CapabilityMatrixError(f"{field} must be 64 lowercase hex characters")


def _require_state(value: object, field: str, allowed: frozenset[str]) -> None:
    if type(value) is not str or value not in allowed:
        raise CapabilityMatrixError(f"{field} is outside the frozen vocabulary")


def _require_source_path(path: object) -> None:
    if type(path) is not str or not path or not path.isascii():
        raise CapabilityMatrixError("source path must be non-empty ASCII text")
    if path.startswith("/") or "\\" in path:
        raise CapabilityMatrixError("source path must be repository-relative POSIX form")
    components = path.split("/")
    if any(component in ("", ".", "..") for component in components):
        raise CapabilityMatrixError("source path contains an ambiguous component")
    if path.strip() != path or "\n" in path or "\r" in path:
        raise CapabilityMatrixError("source path must use canonical text")


def _require_reference(value: object, field: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise CapabilityMatrixError(f"{field} must contain canonical non-empty text")
    if "\n" in value or "\r" in value:
        raise CapabilityMatrixError(f"{field} must contain canonical non-empty text")


def _require_sorted_unique_paths(values: tuple[str, ...], field: str) -> None:
    if type(values) is not tuple:
        raise CapabilityMatrixError(f"{field} must be an exact tuple")
    if not values:
        raise CapabilityMatrixError(f"{field} cannot be empty")
    for value in values:
        _require_source_path(value)
    if tuple(sorted(values)) != values or len(set(values)) != len(values):
        raise CapabilityMatrixError(f"{field} must be sorted and unique")


def _require_sorted_unique_refs(values: tuple[str, ...], field: str) -> None:
    if type(values) is not tuple:
        raise CapabilityMatrixError(f"{field} must be an exact tuple")
    for value in values:
        _require_reference(value, field)
    if tuple(sorted(values)) != values or len(set(values)) != len(values):
        raise CapabilityMatrixError(f"{field} must be sorted and unique")


def _require_unique_sorted_sources(sources: tuple[CapabilitySourceBinding, ...]) -> None:
    paths = tuple(source.path for source in sources)
    if tuple(sorted(paths)) != paths or len(set(paths)) != len(paths):
        raise CapabilityMatrixError("sources must be sorted by path and path-unique")


def _require_unique_sorted_capabilities(capabilities: tuple[CapabilityMatrixEntry, ...]) -> None:
    identifiers = tuple(row.capability_id for row in capabilities)
    if tuple(sorted(identifiers)) != identifiers or len(set(identifiers)) != len(identifiers):
        raise CapabilityMatrixError(
            "capabilities must be sorted by capability_id and identity-unique"
        )


def _require_projection_sources_cover_rows(
    sources: tuple[CapabilitySourceBinding, ...],
    capabilities: tuple[CapabilityMatrixEntry, ...],
) -> None:
    source_paths = {source.path for source in sources}
    referenced_paths = {path for row in capabilities for path in row.canonical_source_paths}
    missing = sorted(referenced_paths - source_paths)
    if missing:
        raise CapabilityMatrixError(
            f"projection source bindings omit referenced canonical source: {missing[0]}"
        )
