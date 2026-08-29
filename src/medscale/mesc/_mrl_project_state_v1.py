"""Deterministic non-authoritative MRL project-state projection.

MRL-0703 composes the canonical MRL-0701 research-program index and MRL-0702
capability matrix with derived task-state rows. It performs no filesystem, Git,
network, model, data, runtime, GPU, or training access.

The projection summarizes live canonical evidence but can never create execution,
training, promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from medscale.mesc._canonical_json_v1 import canonical_json_bytes, canonical_sha256
from medscale.mesc._mrl_capability_matrix_v1 import CapabilityMatrixProjection
from medscale.mesc._mrl_research_program_index_v1 import ResearchProgramIndexProjection

_SCHEMA_VERSION: Final = "MRL-PROJECT-STATE-V1"
_PROJECTION_KIND: Final = "DERIVED_NON_AUTHORITATIVE"
_GIT_SHA_PATTERN: Final = re.compile(r"^[0-9a-f]{40}$")
_SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
_STATE_ID_PATTERN: Final = re.compile(r"^[A-Z][A-Z0-9-]*$")
_LIFECYCLE_STATES: Final = frozenset(
    {
        "PLANNED",
        "ELIGIBLE",
        "IN_PROGRESS",
        "BLOCKED",
        "QUALIFYING",
        "CLOSED_CANONICAL",
    }
)


class ProjectStateProjectionError(ValueError):
    """Raised when an MRL-0703 project-state projection is invalid."""


@dataclass(frozen=True, slots=True)
class ProjectStateSourceBinding:
    """Exact canonical source identity used for project-state rows."""

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
class ProjectStateEntry:
    """One derived project-state row bound to canonical sources and evidence."""

    state_id: str
    lifecycle_state: str
    canonical_source_paths: tuple[str, ...]
    dependency_ids: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if type(self.state_id) is not str or _STATE_ID_PATTERN.fullmatch(self.state_id) is None:
            raise ProjectStateProjectionError(
                "state_id must be canonical uppercase identifier text"
            )
        if type(self.lifecycle_state) is not str or self.lifecycle_state not in _LIFECYCLE_STATES:
            raise ProjectStateProjectionError("lifecycle_state is outside the frozen vocabulary")
        _require_sorted_unique_paths(self.canonical_source_paths, "canonical_source_paths")
        _require_sorted_unique_ids(self.dependency_ids, "dependency_ids")
        _require_sorted_unique_refs(self.evidence_refs, "evidence_refs")
        if self.state_id in self.dependency_ids:
            raise ProjectStateProjectionError("state entry cannot depend on itself")
        if self.lifecycle_state == "CLOSED_CANONICAL" and not self.evidence_refs:
            raise ProjectStateProjectionError("CLOSED_CANONICAL requires exact evidence_refs")

    def to_dict(self) -> dict[str, object]:
        """Return the deterministic JSON representation."""
        return {
            "canonical_source_paths": list(self.canonical_source_paths),
            "dependency_ids": list(self.dependency_ids),
            "evidence_refs": list(self.evidence_refs),
            "lifecycle_state": self.lifecycle_state,
            "state_id": self.state_id,
        }


@dataclass(frozen=True, slots=True)
class ProjectStateProjection:
    """MRL-0703 machine-readable project-state projection."""

    research_program_index: ResearchProgramIndexProjection
    capability_matrix: CapabilityMatrixProjection
    sources: tuple[ProjectStateSourceBinding, ...]
    entries: tuple[ProjectStateEntry, ...]

    def __post_init__(self) -> None:
        if type(self.research_program_index) is not ResearchProgramIndexProjection:
            raise ProjectStateProjectionError(
                "research_program_index must be an exact ResearchProgramIndexProjection"
            )
        if type(self.capability_matrix) is not CapabilityMatrixProjection:
            raise ProjectStateProjectionError(
                "capability_matrix must be an exact CapabilityMatrixProjection"
            )
        if type(self.sources) is not tuple:
            raise ProjectStateProjectionError("sources must be an exact tuple")
        if type(self.entries) is not tuple:
            raise ProjectStateProjectionError("entries must be an exact tuple")
        if any(type(source) is not ProjectStateSourceBinding for source in self.sources):
            raise ProjectStateProjectionError("sources contains an invalid member type")
        if any(type(entry) is not ProjectStateEntry for entry in self.entries):
            raise ProjectStateProjectionError("entries contains an invalid member type")
        _require_component_repository_match(self.research_program_index, self.capability_matrix)
        _require_unique_sorted_sources(self.sources)
        _require_unique_sorted_entries(self.entries)
        _require_dependencies_exist(self.entries)
        _require_sources_cover_entries(
            self.research_program_index,
            self.capability_matrix,
            self.sources,
            self.entries,
        )

    @property
    def can_authorize(self) -> bool:
        """Project-state projections can never grant authority."""
        return False

    @property
    def repository(self) -> dict[str, str]:
        """Return the exact repository identity shared by both component projections."""
        repository = self.research_program_index.repository
        return {"commit_sha": repository.commit_sha, "tree_sha": repository.tree_sha}

    @property
    def source_set_sha256(self) -> str:
        """Return identity over component source sets plus project-state sources."""
        payload = {
            "capability_matrix_source_set_sha256": self.capability_matrix.source_set_sha256,
            "project_state_sources": [source.to_dict() for source in self.sources],
            "research_program_index_source_set_sha256": (
                self.research_program_index.source_set_sha256
            ),
        }
        return canonical_sha256(payload)

    @property
    def semantic_bytes(self) -> bytes:
        """Return deterministic canonical JSON bytes for the projection."""
        return canonical_json_bytes(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """Return the complete non-authoritative project-state payload."""
        return {
            "can_authorize": self.can_authorize,
            "components": {
                "capability_matrix_sha256": canonical_sha256(self.capability_matrix.to_dict()),
                "research_program_index_sha256": canonical_sha256(
                    self.research_program_index.to_dict()
                ),
            },
            "entries": [entry.to_dict() for entry in self.entries],
            "projection_kind": _PROJECTION_KIND,
            "repository": self.repository,
            "schema_version": _SCHEMA_VERSION,
            "source_set_sha256": self.source_set_sha256,
            "sources": [source.to_dict() for source in self.sources],
        }


def _require_component_repository_match(
    research_program_index: ResearchProgramIndexProjection,
    capability_matrix: CapabilityMatrixProjection,
) -> None:
    research_repository = research_program_index.repository
    capability_repository = capability_matrix.repository
    if research_repository.commit_sha != capability_repository.commit_sha:
        raise ProjectStateProjectionError("component projections bind different repository commits")
    if research_repository.tree_sha != capability_repository.tree_sha:
        raise ProjectStateProjectionError("component projections bind different repository trees")


def _require_git_sha(value: object, field: str) -> None:
    if type(value) is not str or _GIT_SHA_PATTERN.fullmatch(value) is None:
        raise ProjectStateProjectionError(f"{field} must be 40 lowercase hex characters")


def _require_sha256(value: object, field: str) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ProjectStateProjectionError(f"{field} must be 64 lowercase hex characters")


def _require_source_path(path: object) -> None:
    if type(path) is not str or not path or not path.isascii():
        raise ProjectStateProjectionError("source path must be non-empty ASCII text")
    if path.startswith("/") or "\\" in path:
        raise ProjectStateProjectionError("source path must be repository-relative POSIX form")
    components = path.split("/")
    if any(component in ("", ".", "..") for component in components):
        raise ProjectStateProjectionError("source path contains an ambiguous component")
    if path.strip() != path or "\n" in path or "\r" in path:
        raise ProjectStateProjectionError("source path must use canonical text")


def _require_reference(value: object, field: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise ProjectStateProjectionError(f"{field} must contain canonical non-empty text")
    if "\n" in value or "\r" in value:
        raise ProjectStateProjectionError(f"{field} must contain canonical non-empty text")


def _require_state_id(value: object, field: str) -> None:
    if type(value) is not str or _STATE_ID_PATTERN.fullmatch(value) is None:
        raise ProjectStateProjectionError(f"{field} must contain canonical state identifiers")


def _require_sorted_unique_paths(values: tuple[str, ...], field: str) -> None:
    if type(values) is not tuple or not values:
        raise ProjectStateProjectionError(f"{field} must be a non-empty exact tuple")
    for value in values:
        _require_source_path(value)
    if tuple(sorted(values)) != values or len(set(values)) != len(values):
        raise ProjectStateProjectionError(f"{field} must be sorted and unique")


def _require_sorted_unique_ids(values: tuple[str, ...], field: str) -> None:
    if type(values) is not tuple:
        raise ProjectStateProjectionError(f"{field} must be an exact tuple")
    for value in values:
        _require_state_id(value, field)
    if tuple(sorted(values)) != values or len(set(values)) != len(values):
        raise ProjectStateProjectionError(f"{field} must be sorted and unique")


def _require_sorted_unique_refs(values: tuple[str, ...], field: str) -> None:
    if type(values) is not tuple:
        raise ProjectStateProjectionError(f"{field} must be an exact tuple")
    for value in values:
        _require_reference(value, field)
    if tuple(sorted(values)) != values or len(set(values)) != len(values):
        raise ProjectStateProjectionError(f"{field} must be sorted and unique")


def _require_unique_sorted_sources(sources: tuple[ProjectStateSourceBinding, ...]) -> None:
    paths = tuple(source.path for source in sources)
    if tuple(sorted(paths)) != paths or len(set(paths)) != len(paths):
        raise ProjectStateProjectionError("sources must be sorted by path and path-unique")


def _require_unique_sorted_entries(entries: tuple[ProjectStateEntry, ...]) -> None:
    identifiers = tuple(entry.state_id for entry in entries)
    if tuple(sorted(identifiers)) != identifiers or len(set(identifiers)) != len(identifiers):
        raise ProjectStateProjectionError("entries must be sorted by state_id and identity-unique")


def _require_dependencies_exist(entries: tuple[ProjectStateEntry, ...]) -> None:
    identifiers = {entry.state_id for entry in entries}
    for entry in entries:
        missing = sorted(set(entry.dependency_ids) - identifiers)
        if missing:
            raise ProjectStateProjectionError(
                f"entry dependency is absent from project state: {missing[0]}"
            )


def _require_sources_cover_entries(
    research_program_index: ResearchProgramIndexProjection,
    capability_matrix: CapabilityMatrixProjection,
    sources: tuple[ProjectStateSourceBinding, ...],
    entries: tuple[ProjectStateEntry, ...],
) -> None:
    available = {source.path for source in research_program_index.sources}
    available.update(source.path for source in capability_matrix.sources)
    available.update(source.path for source in sources)
    referenced = {path for entry in entries for path in entry.canonical_source_paths}
    missing = sorted(referenced - available)
    if missing:
        raise ProjectStateProjectionError(
            f"project state source bindings omit referenced canonical source: {missing[0]}"
        )
