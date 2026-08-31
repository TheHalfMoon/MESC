"""Rebuildable non-authoritative procedure search index for MRL-0408.

Only currently active MRL-0407 admitted procedures may be indexed. Every indexed
procedure additionally requires an exact research-input admission to the
RESEARCH_SEARCH_INDEX learning surface. The index is a derived cache: canonical procedure
state remains the append-only registry and its MRL-0406 evidence.

This module grants no procedure admission, model, data, network, GPU, training,
promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_procedure_registry_v1 import (
    ProcedureRegistry,
    ProcedureRegistryDisposition,
    ProcedureRegistryError,
)
from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
    ResearchInputAdmissionError,
    ResearchLearningSurface,
)
from medscale.mesc._mrl_research_procedure_v1 import ResearchProcedure, ResearchProcedureError

__all__ = [
    "ProcedureSearchIndex",
    "ProcedureSearchIndexEntry",
    "ProcedureSearchIndexError",
    "build_procedure_search_index",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_TOKEN: Final = re.compile(r"[a-z0-9]+(?:[-_.:/][a-z0-9]+)*", flags=re.ASCII)


class ProcedureSearchIndexError(ValueError):
    """Fail-closed validation error for procedure search-index derivation."""


def _make_identity_registry() -> tuple[
    Callable[[object, str], None],
    Callable[[object, str], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: object, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ProcedureSearchIndexError("search-index construction identity already exists")
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: object, label: str) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ProcedureSearchIndexError(f"{label} construction identity is missing")
        return identity

    return store, load


_store_identity, _load_identity = _make_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureSearchIndexEntry:
    """One deterministic derived row for an active admitted procedure."""

    procedure_sha256: str
    admitted_procedure_sha256: str
    procedure_id: str
    version: int
    research_program_refs: tuple[str, ...]
    task_types: tuple[str, ...]
    search_terms: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_entry(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> ProcedureSearchIndexEntry:
        if type(self) is not ProcedureSearchIndexEntry:
            raise ProcedureSearchIndexError("entry must be an exact ProcedureSearchIndexEntry")
        bound = _load_identity(self, "procedure search-index entry")
        _require_sha256(bound, "bound entry content_sha256")
        _validate_entry(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise ProcedureSearchIndexError("search-index entry changed after construction")
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-PROCEDURE-SEARCH-INDEX-ENTRY-V1",
            "procedure_sha256": self.procedure_sha256,
            "admitted_procedure_sha256": self.admitted_procedure_sha256,
            "procedure_id": self.procedure_id,
            "version": self.version,
            "research_program_refs": list(self.research_program_refs),
            "task_types": list(self.task_types),
            "search_terms": list(self.search_terms),
            "authoritative": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureSearchIndex:
    """One rebuildable derived index bound to registry and input-admission identities."""

    registry: ProcedureRegistry
    input_admissions: tuple[ResearchInputAdmissionContract, ...]
    entries: tuple[ProcedureSearchIndexEntry, ...]

    def __post_init__(self) -> None:
        _validate_index(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> ProcedureSearchIndex:
        if type(self) is not ProcedureSearchIndex:
            raise ProcedureSearchIndexError("index must be an exact ProcedureSearchIndex")
        bound = _load_identity(self, "procedure search index")
        _require_sha256(bound, "bound search-index content_sha256")
        _validate_index(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise ProcedureSearchIndexError("procedure search index changed after construction")
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        registry = _validated_registry(self.registry)
        admission_sha256s = tuple(admission.content_sha256 for admission in self.input_admissions)
        return {
            "format": "MRL-PROCEDURE-SEARCH-INDEX-V1",
            "registry_sha256": registry.content_sha256,
            "input_admission_sha256s": list(admission_sha256s),
            "entries": [entry._semantic_dict_validated() for entry in self.entries],
            "authoritative": False,
            "can_admit_procedure": False,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data

    def search(self, query: str) -> tuple[ProcedureSearchIndexEntry, ...]:
        """Return deterministic lexical matches from the freshly revalidated derived index."""
        snapshot = self._validated_snapshot()
        tokens = _query_tokens(query)
        scored: list[tuple[int, str, ProcedureSearchIndexEntry]] = []
        for entry in snapshot.entries:
            terms = set(entry.search_terms)
            score = sum(1 for token in tokens if token in terms)
            if score == len(tokens):
                scored.append((-score, entry.procedure_sha256, entry))
        scored.sort(key=lambda item: (item[0], item[1]))
        return tuple(item[2]._validated_snapshot() for item in scored)

    @property
    def can_admit_procedure(self) -> bool:
        return False

    @property
    def can_authorize_model_promotion(self) -> bool:
        return False


def build_procedure_search_index(
    registry: ProcedureRegistry,
    input_admissions: tuple[ResearchInputAdmissionContract, ...],
) -> ProcedureSearchIndex:
    """Rebuild a complete non-authoritative index from current canonical registry state."""
    registry_snapshot = _validated_registry(registry)
    _require_admission_tuple(input_admissions)
    entries, ordered_admissions = _derive_entries_and_admissions(
        registry_snapshot,
        input_admissions,
    )
    return ProcedureSearchIndex(
        registry=registry,
        input_admissions=ordered_admissions,
        entries=entries,
    )


def _derive_entries_and_admissions(
    registry: ProcedureRegistry,
    input_admissions: tuple[ResearchInputAdmissionContract, ...],
) -> tuple[tuple[ProcedureSearchIndexEntry, ...], tuple[ResearchInputAdmissionContract, ...]]:
    admission_by_artifact: dict[str, ResearchInputAdmissionContract] = {}
    for admission in input_admissions:
        _require_exact_admission(admission)
        source_artifact_sha256 = admission.source_artifact_sha256
        if source_artifact_sha256 is None:
            raise ProcedureSearchIndexError(
                "search-index admission requires a concrete source artifact identity"
            )
        _require_sha256(source_artifact_sha256, "source_artifact_sha256")
        if source_artifact_sha256 in admission_by_artifact:
            raise ProcedureSearchIndexError(
                "search-index admissions must bind unique source artifacts"
            )
        admission_by_artifact[source_artifact_sha256] = admission

    entries: list[ProcedureSearchIndexEntry] = []
    used_admissions: list[ResearchInputAdmissionContract] = []
    active_subjects = registry.active_admitted_procedure_sha256s
    for subject in active_subjects:
        event = registry.current_event(subject)
        if event.disposition is not ProcedureRegistryDisposition.ADMITTED:
            raise ProcedureSearchIndexError(
                "active registry projection contains non-admitted state"
            )
        result = event.admission_result._validated_snapshot()
        procedure = result.admitted_procedure
        if type(procedure) is not ResearchProcedure:
            raise ProcedureSearchIndexError(
                "active admitted registry event lacks an exact admitted procedure"
            )
        try:
            procedure_snapshot = procedure._validated_snapshot()
        except ResearchProcedureError as exc:
            raise ProcedureSearchIndexError(
                "admitted procedure failed canonical revalidation"
            ) from exc
        if procedure_snapshot.admission_subject_sha256 != subject:
            raise ProcedureSearchIndexError("registry subject does not bind the admitted procedure")
        admitted_sha256 = procedure_snapshot.content_sha256
        matched_admission = admission_by_artifact.get(admitted_sha256)
        if matched_admission is None:
            raise ProcedureSearchIndexError(
                "every active admitted procedure requires research-input admission"
            )
        _stable_search_admission_sha256(matched_admission)
        entries.append(_entry_from_procedure(subject, procedure_snapshot))
        used_admissions.append(matched_admission)

    if len(used_admissions) != len(input_admissions):
        raise ProcedureSearchIndexError(
            "search-index admissions cannot include non-active procedure artifacts"
        )
    paired = sorted(
        zip(entries, used_admissions, strict=True),
        key=lambda item: item[0].procedure_sha256,
    )
    return (
        tuple(item[0] for item in paired),
        tuple(item[1] for item in paired),
    )


def _stable_search_admission_sha256(admission: ResearchInputAdmissionContract) -> str:
    _require_exact_admission(admission)
    try:
        before = admission.content_sha256
        admission.require_learning_admission(ResearchLearningSurface.RESEARCH_SEARCH_INDEX)
        after = admission.content_sha256
    except ResearchInputAdmissionError as exc:
        raise ProcedureSearchIndexError(
            "procedure source is not canonically admitted to the research search index"
        ) from exc
    if before != after:
        raise ProcedureSearchIndexError(
            "research-input admission identity changed during search-index admission"
        )
    return before


def _entry_from_procedure(
    subject: str,
    procedure: ResearchProcedure,
) -> ProcedureSearchIndexEntry:
    bounds = procedure.applicability_bounds
    terms = _search_terms_for_procedure(procedure)
    return ProcedureSearchIndexEntry(
        procedure_sha256=subject,
        admitted_procedure_sha256=procedure.content_sha256,
        procedure_id=procedure.procedure_id,
        version=procedure.version,
        research_program_refs=bounds.research_program_refs,
        task_types=bounds.task_types,
        search_terms=terms,
    )


def _search_terms_for_procedure(procedure: ResearchProcedure) -> tuple[str, ...]:
    values: tuple[str, ...] = (
        procedure.procedure_id,
        *procedure.applicability_bounds.research_program_refs,
        *procedure.applicability_bounds.task_types,
        *procedure.applicability_bounds.model_classes,
        *procedure.applicability_bounds.data_classes,
        *procedure.preconditions,
        *procedure.allowed_tools,
        *procedure.steps,
        *procedure.expected_artifacts,
        *procedure.verification_steps,
        *procedure.known_failure_modes,
    )
    tokens: set[str] = set()
    for value in values:
        tokens.update(_TOKEN.findall(value.lower()))
    if not tokens:
        raise ProcedureSearchIndexError("admitted procedure produced no searchable terms")
    return tuple(sorted(tokens))


def _query_tokens(query: str) -> tuple[str, ...]:
    if type(query) is not str or not query or query != query.strip():
        raise ProcedureSearchIndexError("query must be canonical non-empty text")
    if any(character in query for character in "\x00\r\n\t"):
        raise ProcedureSearchIndexError("query cannot contain control characters")
    tokens = tuple(sorted(set(_TOKEN.findall(query.lower()))))
    if not tokens:
        raise ProcedureSearchIndexError("query must contain searchable tokens")
    return tokens


def _validate_entry(entry: ProcedureSearchIndexEntry) -> None:
    _require_sha256(entry.procedure_sha256, "procedure_sha256")
    _require_sha256(entry.admitted_procedure_sha256, "admitted_procedure_sha256")
    _require_text(entry.procedure_id, "procedure_id")
    if type(entry.version) is not int or entry.version < 1:
        raise ProcedureSearchIndexError("version must be an exact positive integer")
    _require_sorted_texts(entry.research_program_refs, "research_program_refs")
    _require_sorted_texts(entry.task_types, "task_types")
    _require_sorted_texts(entry.search_terms, "search_terms", required=True)


def _validate_index(index: ProcedureSearchIndex) -> None:
    registry = _validated_registry(index.registry)
    _require_admission_tuple(index.input_admissions)
    if type(index.entries) is not tuple:
        raise ProcedureSearchIndexError("entries must be an exact tuple")
    for entry in index.entries:
        if type(entry) is not ProcedureSearchIndexEntry:
            raise ProcedureSearchIndexError("entries contains an invalid item type")
        entry._validated_snapshot()
    if index.entries != tuple(sorted(index.entries, key=lambda item: item.procedure_sha256)):
        raise ProcedureSearchIndexError("entries must be strictly sorted by procedure identity")
    if len({entry.procedure_sha256 for entry in index.entries}) != len(index.entries):
        raise ProcedureSearchIndexError("entries must contain unique procedure identities")
    expected_entries, expected_admissions = _derive_entries_and_admissions(
        registry,
        index.input_admissions,
    )
    if tuple(entry.semantic_dict() for entry in index.entries) != tuple(
        entry.semantic_dict() for entry in expected_entries
    ):
        raise ProcedureSearchIndexError(
            "search index does not match a complete rebuild from canonical registry state"
        )
    if tuple(admission.content_sha256 for admission in index.input_admissions) != tuple(
        admission.content_sha256 for admission in expected_admissions
    ):
        raise ProcedureSearchIndexError(
            "search index input-admission ordering does not match deterministic rebuild"
        )


def _validated_registry(registry: ProcedureRegistry) -> ProcedureRegistry:
    if type(registry) is not ProcedureRegistry:
        raise ProcedureSearchIndexError("registry must be an exact ProcedureRegistry")
    try:
        return registry._validated_snapshot()
    except ProcedureRegistryError as exc:
        raise ProcedureSearchIndexError("procedure registry failed canonical revalidation") from exc


def _require_admission_tuple(
    admissions: tuple[ResearchInputAdmissionContract, ...],
) -> None:
    if type(admissions) is not tuple:
        raise ProcedureSearchIndexError("input_admissions must be an exact tuple")
    for admission in admissions:
        _require_exact_admission(admission)


def _require_exact_admission(admission: ResearchInputAdmissionContract) -> None:
    if type(admission) is not ResearchInputAdmissionContract:
        raise ProcedureSearchIndexError(
            "input admission must be an exact ResearchInputAdmissionContract"
        )


def _require_sorted_texts(
    values: tuple[str, ...],
    label: str,
    *,
    required: bool = False,
) -> None:
    if type(values) is not tuple:
        raise ProcedureSearchIndexError(f"{label} must be an exact tuple")
    if required and not values:
        raise ProcedureSearchIndexError(f"{label} cannot be empty")
    for value in values:
        _require_text(value, label)
    if values != tuple(sorted(set(values))):
        raise ProcedureSearchIndexError(f"{label} must be unique and strictly sorted")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ProcedureSearchIndexError(f"{label} must be 64 lowercase hex")


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ProcedureSearchIndexError(f"{label} must be canonical non-empty text")
    if any(character in value for character in "\x00\r\n\t"):
        raise ProcedureSearchIndexError(f"{label} cannot contain control characters")
