"""Deterministic non-authoritative MRL research-program index projection.

MRL-0701 defines the typed projection that will later be generated from canonical
repository sources by MRL-0704. This module deliberately performs no filesystem,
Git, network, model, data, runtime, or training access. Callers must inject exact
repository/source bindings and already-derived research-program records.

The projection can summarize canonical research-program identity, but it can never
grant execution, model/data access, training, promotion, deployment, release, or
clinical authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from medscale.mesc._canonical_json_v1 import canonical_json_bytes, canonical_sha256

_SCHEMA_VERSION: Final = "MRL-RESEARCH-PROGRAM-INDEX-V1"
_PROJECTION_KIND: Final = "DERIVED_NON_AUTHORITATIVE"
_GIT_SHA_PATTERN: Final = re.compile(r"^[0-9a-f]{40}$")
_SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
_FOUNDATIONAL_ID_PATTERN: Final = re.compile(r"^RQ[1-7]$")
_NAMESPACE_PATTERN: Final = re.compile(r"^[A-Z][A-Z0-9-]*-RQ-<NNNN>$")
_NAMESPACED_QUESTION_PATTERN: Final = re.compile(r"^[A-Z][A-Z0-9-]*-RQ-[0-9]{4}$")
_ALLOWED_QUESTION_STATUSES: Final = frozenset(
    {
        "PROPOSED",
        "OPEN",
        "BLOCKED",
        "IN_PROGRESS",
        "SUPPORTED",
        "NULL_RESULT",
        "FALSIFIED",
        "INCONCLUSIVE",
        "SUPERSEDED",
    }
)


class ResearchProgramIndexError(ValueError):
    """Raised when a research-program projection violates the MRL-0701 contract."""


@dataclass(frozen=True, slots=True)
class RepositoryBinding:
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
class SourceBinding:
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
            "path": self.path,
            "git_blob_sha": self.git_blob_sha,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class ResearchQuestionIndexEntry:
    """One accepted research-question identity exposed by the index."""

    question_id: str
    program: str
    status: str
    canonical_source_path: str

    def __post_init__(self) -> None:
        _require_text(self.program, "program")
        _require_source_path(self.canonical_source_path)
        if self.status not in _ALLOWED_QUESTION_STATUSES:
            raise ResearchProgramIndexError("question status is outside the frozen vocabulary")
        is_foundational = _FOUNDATIONAL_ID_PATTERN.fullmatch(self.question_id) is not None
        is_namespaced = _NAMESPACED_QUESTION_PATTERN.fullmatch(self.question_id) is not None
        if not is_foundational and not is_namespaced:
            raise ResearchProgramIndexError(
                "question_id is not a canonical MRL research identifier"
            )

    @property
    def is_foundational(self) -> bool:
        """Return whether the identity is one of the preserved bare RQ1-RQ7 IDs."""
        return _FOUNDATIONAL_ID_PATTERN.fullmatch(self.question_id) is not None

    def to_dict(self) -> dict[str, object]:
        """Return the deterministic JSON representation."""
        return {
            "canonical_source_path": self.canonical_source_path,
            "is_foundational": self.is_foundational,
            "program": self.program,
            "question_id": self.question_id,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class ResearchProgramNamespace:
    """One reserved later-program namespace without fabricated question records."""

    program: str
    question_namespace: str
    program_status: str
    canonical_source_paths: tuple[str, ...]
    question_catalog_status: str

    def __post_init__(self) -> None:
        _require_text(self.program, "program")
        _require_text(self.program_status, "program_status")
        _require_text(self.question_catalog_status, "question_catalog_status")
        if _NAMESPACE_PATTERN.fullmatch(self.question_namespace) is None:
            raise ResearchProgramIndexError(
                "question_namespace is not a registered namespace shape"
            )
        if type(self.canonical_source_paths) is not tuple:
            raise ResearchProgramIndexError("canonical_source_paths must be an exact tuple")
        if not self.canonical_source_paths:
            raise ResearchProgramIndexError("canonical_source_paths cannot be empty")
        sorted_paths = tuple(sorted(self.canonical_source_paths))
        unique_path_count = len(set(self.canonical_source_paths))
        if sorted_paths != self.canonical_source_paths:
            raise ResearchProgramIndexError("canonical_source_paths must be sorted and unique")
        if unique_path_count != len(self.canonical_source_paths):
            raise ResearchProgramIndexError("canonical_source_paths must be sorted and unique")
        for path in self.canonical_source_paths:
            if type(path) is not str:
                raise ResearchProgramIndexError("canonical_source_paths must contain exact strings")
            _require_source_path(path)

    @property
    def namespace_prefix(self) -> str:
        """Return the concrete prefix preceding the four-digit question number."""
        return self.question_namespace.removesuffix("<NNNN>")

    def to_dict(self) -> dict[str, object]:
        """Return the deterministic JSON representation."""
        return {
            "canonical_source_paths": list(self.canonical_source_paths),
            "program": self.program,
            "program_status": self.program_status,
            "question_catalog_status": self.question_catalog_status,
            "question_namespace": self.question_namespace,
        }


@dataclass(frozen=True, slots=True)
class ResearchProgramIndexProjection:
    """MRL-0701 machine-readable research-program index projection."""

    repository: RepositoryBinding
    sources: tuple[SourceBinding, ...]
    questions: tuple[ResearchQuestionIndexEntry, ...]
    namespaces: tuple[ResearchProgramNamespace, ...]

    def __post_init__(self) -> None:
        if type(self.repository) is not RepositoryBinding:
            raise ResearchProgramIndexError("repository must be an exact RepositoryBinding")
        if type(self.sources) is not tuple:
            raise ResearchProgramIndexError("sources must be an exact tuple")
        if type(self.questions) is not tuple:
            raise ResearchProgramIndexError("questions must be an exact tuple")
        if type(self.namespaces) is not tuple:
            raise ResearchProgramIndexError("namespaces must be an exact tuple")
        if not self.sources:
            raise ResearchProgramIndexError("sources cannot be empty")
        if any(type(source) is not SourceBinding for source in self.sources):
            raise ResearchProgramIndexError("sources contains an invalid member type")
        invalid_question_type = any(
            type(question) is not ResearchQuestionIndexEntry for question in self.questions
        )
        if invalid_question_type:
            raise ResearchProgramIndexError("questions contains an invalid member type")
        invalid_namespace_type = any(
            type(namespace) is not ResearchProgramNamespace for namespace in self.namespaces
        )
        if invalid_namespace_type:
            raise ResearchProgramIndexError("namespaces contains an invalid member type")
        _require_unique_sorted_sources(self.sources)
        _require_unique_sorted_questions(self.questions)
        _require_unique_sorted_namespaces(self.namespaces)
        _require_foundational_identity_set(self.questions)
        _require_namespaced_questions_registered(self.questions, self.namespaces)
        _require_projection_sources_cover_records(
            self.sources,
            self.questions,
            self.namespaces,
        )

    @property
    def can_authorize(self) -> bool:
        """Research-program projections can never grant authority."""
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
            "namespaces": [namespace.to_dict() for namespace in self.namespaces],
            "projection_kind": _PROJECTION_KIND,
            "questions": [question.to_dict() for question in self.questions],
            "repository": self.repository.to_dict(),
            "schema_version": _SCHEMA_VERSION,
            "source_set_sha256": self.source_set_sha256,
            "sources": [source.to_dict() for source in self.sources],
        }


def _require_git_sha(value: object, field: str) -> None:
    if type(value) is not str or _GIT_SHA_PATTERN.fullmatch(value) is None:
        raise ResearchProgramIndexError(f"{field} must be 40 lowercase hex characters")


def _require_sha256(value: object, field: str) -> None:
    if type(value) is not str or _SHA256_PATTERN.fullmatch(value) is None:
        raise ResearchProgramIndexError(f"{field} must be 64 lowercase hex characters")


def _require_text(value: object, field: str) -> None:
    if (
        type(value) is not str
        or not value
        or value.strip() != value
        or "\n" in value
        or "\r" in value
    ):
        raise ResearchProgramIndexError(f"{field} must be canonical non-empty text")


def _require_source_path(path: object) -> None:
    if type(path) is not str or not path or not path.isascii():
        raise ResearchProgramIndexError("source path must be non-empty ASCII text")
    if path.startswith("/") or "\\" in path:
        raise ResearchProgramIndexError("source path must be repository-relative POSIX form")
    components = path.split("/")
    if any(component in ("", ".", "..") for component in components):
        raise ResearchProgramIndexError("source path contains an ambiguous component")
    if path.strip() != path or "\n" in path or "\r" in path:
        raise ResearchProgramIndexError("source path must use canonical text")


def _require_unique_sorted_sources(sources: tuple[SourceBinding, ...]) -> None:
    paths = tuple(source.path for source in sources)
    if tuple(sorted(paths)) != paths or len(set(paths)) != len(paths):
        raise ResearchProgramIndexError("sources must be sorted by path and path-unique")


def _require_unique_sorted_questions(
    questions: tuple[ResearchQuestionIndexEntry, ...],
) -> None:
    ids = tuple(question.question_id for question in questions)
    if tuple(sorted(ids)) != ids or len(set(ids)) != len(ids):
        raise ResearchProgramIndexError(
            "questions must be sorted by question_id and identity-unique"
        )


def _require_unique_sorted_namespaces(
    namespaces: tuple[ResearchProgramNamespace, ...],
) -> None:
    names = tuple(namespace.question_namespace for namespace in namespaces)
    if tuple(sorted(names)) != names or len(set(names)) != len(names):
        raise ResearchProgramIndexError(
            "namespaces must be sorted by question_namespace and identity-unique"
        )
    prefixes = tuple(namespace.namespace_prefix for namespace in namespaces)
    if len(set(prefixes)) != len(prefixes):
        raise ResearchProgramIndexError("namespace prefixes must be unique")


def _require_foundational_identity_set(
    questions: tuple[ResearchQuestionIndexEntry, ...],
) -> None:
    foundational = tuple(question.question_id for question in questions if question.is_foundational)
    expected = ("RQ1", "RQ2", "RQ3", "RQ4", "RQ5", "RQ6", "RQ7")
    if foundational != expected:
        raise ResearchProgramIndexError("projection must preserve foundational RQ1-RQ7 exactly")


def _require_namespaced_questions_registered(
    questions: tuple[ResearchQuestionIndexEntry, ...],
    namespaces: tuple[ResearchProgramNamespace, ...],
) -> None:
    prefixes = tuple(namespace.namespace_prefix for namespace in namespaces)
    for question in questions:
        if question.is_foundational:
            continue
        if not any(question.question_id.startswith(prefix) for prefix in prefixes):
            raise ResearchProgramIndexError(
                "namespaced question is not covered by a registered namespace"
            )


def _require_projection_sources_cover_records(
    sources: tuple[SourceBinding, ...],
    questions: tuple[ResearchQuestionIndexEntry, ...],
    namespaces: tuple[ResearchProgramNamespace, ...],
) -> None:
    source_paths = {source.path for source in sources}
    referenced_paths = {question.canonical_source_path for question in questions}
    namespace_paths = {
        path for namespace in namespaces for path in namespace.canonical_source_paths
    }
    referenced_paths.update(namespace_paths)
    missing = sorted(referenced_paths - source_paths)
    if missing:
        message = "projection source bindings omit referenced canonical source"
        raise ResearchProgramIndexError(f"{message}: {missing[0]}")
