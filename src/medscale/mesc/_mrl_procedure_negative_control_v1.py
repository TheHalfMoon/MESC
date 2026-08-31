"""Negative and failure-control evidence for MRL research procedures.

MRL-0405 records whether declared procedure failure modes are exercised by independent
negative-control evidence. Unexpected success and wrong-failure outcomes remain first-
class evidence. This contract cannot advance procedure admission or authorize real model,
data, network, GPU, training, promotion, deployment, release, or clinical activity.
"""

from __future__ import annotations

import enum
import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_procedure_v1 import ResearchProcedure, ResearchProcedureError

__all__ = [
    "NegativeControlDisposition",
    "ProcedureNegativeControlCase",
    "ProcedureNegativeControlError",
    "ProcedureNegativeControlReport",
    "build_procedure_negative_control_report",
]

_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProcedureNegativeControlError(ValueError):
    """Fail-closed validation error for procedure negative-control evidence."""


class NegativeControlDisposition(enum.Enum):
    """Closed outcomes for one declared-failure negative control."""

    EXPECTED_FAILURE_OBSERVED = "EXPECTED_FAILURE_OBSERVED"
    UNEXPECTED_SUCCESS = "UNEXPECTED_SUCCESS"
    WRONG_FAILURE_MODE = "WRONG_FAILURE_MODE"


def _make_case_identity_registry() -> tuple[
    Callable[[ProcedureNegativeControlCase, str], None],
    Callable[[ProcedureNegativeControlCase], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: ProcedureNegativeControlCase, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ProcedureNegativeControlError(
                "negative-control case construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: ProcedureNegativeControlCase) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ProcedureNegativeControlError(
                "negative-control case construction identity is missing"
            )
        return identity

    return store, load


def _make_report_identity_registry() -> tuple[
    Callable[[ProcedureNegativeControlReport, str], None],
    Callable[[ProcedureNegativeControlReport], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: ProcedureNegativeControlReport, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ProcedureNegativeControlError(
                "negative-control report construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: ProcedureNegativeControlReport) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ProcedureNegativeControlError(
                "negative-control report construction identity is missing"
            )
        return identity

    return store, load


_store_case_identity, _load_case_identity = _make_case_identity_registry()
_store_report_identity, _load_report_identity = _make_report_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureNegativeControlCase:
    """One immutable negative-control observation for a declared procedure failure mode."""

    control_id: str
    expected_failure_mode: str
    observed_failure_mode: str | None
    evidence_artifact_sha256: str

    def __post_init__(self) -> None:
        _require_id(self.control_id, "control_id")
        _require_text(self.expected_failure_mode, "expected_failure_mode")
        if self.observed_failure_mode is not None:
            _require_text(self.observed_failure_mode, "observed_failure_mode")
        _require_sha256(self.evidence_artifact_sha256, "evidence_artifact_sha256")
        _store_case_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> ProcedureNegativeControlCase:
        if type(self) is not ProcedureNegativeControlCase:
            raise ProcedureNegativeControlError(
                "case must be an exact ProcedureNegativeControlCase"
            )
        bound_content_sha256 = _load_case_identity(self)
        _require_sha256(bound_content_sha256, "bound negative-control case content_sha256")
        snapshot = ProcedureNegativeControlCase(
            control_id=self.control_id,
            expected_failure_mode=self.expected_failure_mode,
            observed_failure_mode=self.observed_failure_mode,
            evidence_artifact_sha256=self.evidence_artifact_sha256,
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise ProcedureNegativeControlError(
                "negative-control case identity changed after construction"
            )
        return snapshot

    def _disposition_validated(self) -> NegativeControlDisposition:
        if self.observed_failure_mode is None:
            return NegativeControlDisposition.UNEXPECTED_SUCCESS
        if self.observed_failure_mode == self.expected_failure_mode:
            return NegativeControlDisposition.EXPECTED_FAILURE_OBSERVED
        return NegativeControlDisposition.WRONG_FAILURE_MODE

    @property
    def disposition(self) -> NegativeControlDisposition:
        snapshot = ProcedureNegativeControlCase._validated_snapshot(self)
        return snapshot._disposition_validated()

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "control_id": self.control_id,
            "disposition": self._disposition_validated().value,
            "evidence_artifact_sha256": self.evidence_artifact_sha256,
            "expected_failure_mode": self.expected_failure_mode,
            "observed_failure_mode": self.observed_failure_mode,
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = ProcedureNegativeControlCase._validated_snapshot(self)
        return snapshot._semantic_dict_validated()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureNegativeControlReport:
    """Immutable negative-control evidence bound to one procedure admission subject."""

    procedure_sha256: str
    declared_failure_modes: tuple[str, ...]
    cases: tuple[ProcedureNegativeControlCase, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.procedure_sha256, "procedure_sha256")
        _require_sorted_texts(
            self.declared_failure_modes,
            "declared_failure_modes",
            required=True,
        )
        if type(self.cases) is not tuple or not self.cases:
            raise ProcedureNegativeControlError("cases must be a non-empty exact tuple")
        if any(type(case) is not ProcedureNegativeControlCase for case in self.cases):
            raise ProcedureNegativeControlError("cases contains an invalid item type")
        case_snapshots = tuple(
            ProcedureNegativeControlCase._validated_snapshot(case) for case in self.cases
        )
        case_ids = tuple(case.control_id for case in case_snapshots)
        if case_ids != tuple(sorted(set(case_ids))):
            raise ProcedureNegativeControlError("cases must be unique and sorted by control_id")
        evidence_ids = tuple(case.evidence_artifact_sha256 for case in case_snapshots)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ProcedureNegativeControlError(
                "negative controls require distinct evidence artifact identities"
            )
        for case in case_snapshots:
            if case.expected_failure_mode not in self.declared_failure_modes:
                raise ProcedureNegativeControlError(
                    "negative control references an undeclared procedure failure mode"
                )
        _store_report_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> ProcedureNegativeControlReport:
        if type(self) is not ProcedureNegativeControlReport:
            raise ProcedureNegativeControlError(
                "report must be an exact ProcedureNegativeControlReport"
            )
        if type(self.cases) is not tuple:
            raise ProcedureNegativeControlError("cases must be an exact tuple")
        bound_content_sha256 = _load_report_identity(self)
        _require_sha256(bound_content_sha256, "bound report content_sha256")
        snapshot = ProcedureNegativeControlReport(
            procedure_sha256=self.procedure_sha256,
            declared_failure_modes=self.declared_failure_modes,
            cases=tuple(
                ProcedureNegativeControlCase._validated_snapshot(case) for case in self.cases
            ),
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise ProcedureNegativeControlError(
                "negative-control report identity changed after construction"
            )
        return snapshot

    def _coverage_complete_validated(self) -> bool:
        covered = {case.expected_failure_mode for case in self.cases}
        return covered == set(self.declared_failure_modes)

    @property
    def coverage_complete(self) -> bool:
        snapshot = ProcedureNegativeControlReport._validated_snapshot(self)
        return snapshot._coverage_complete_validated()

    def _all_controls_pass_validated(self) -> bool:
        return self._coverage_complete_validated() and all(
            case._disposition_validated() is NegativeControlDisposition.EXPECTED_FAILURE_OBSERVED
            for case in self.cases
        )

    @property
    def all_controls_pass(self) -> bool:
        snapshot = ProcedureNegativeControlReport._validated_snapshot(self)
        return snapshot._all_controls_pass_validated()

    @property
    def can_advance_admission(self) -> bool:
        return False

    @property
    def can_authorize(self) -> bool:
        return False

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "all_controls_pass": self._all_controls_pass_validated(),
            "can_advance_admission": False,
            "can_authorize": False,
            "cases": [case.semantic_dict() for case in self.cases],
            "coverage_complete": self._coverage_complete_validated(),
            "declared_failure_modes": list(self.declared_failure_modes),
            "format": "MRL-PROCEDURE-NEGATIVE-CONTROL-REPORT-V1",
            "procedure_sha256": self.procedure_sha256,
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = ProcedureNegativeControlReport._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

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


def build_procedure_negative_control_report(
    procedure: ResearchProcedure,
    cases: tuple[ProcedureNegativeControlCase, ...],
) -> ProcedureNegativeControlReport:
    """Bind supplied negative-control evidence to one freshly revalidated procedure."""
    if type(procedure) is not ResearchProcedure:
        raise ProcedureNegativeControlError("procedure must be an exact ResearchProcedure")
    if type(cases) is not tuple:
        raise ProcedureNegativeControlError("cases must be an exact tuple")
    try:
        procedure_snapshot = procedure._validated_snapshot()
        procedure_sha256 = procedure_snapshot.admission_subject_sha256
        declared_failure_modes = tuple(sorted(procedure_snapshot.known_failure_modes))
    except ResearchProcedureError as exc:
        raise ProcedureNegativeControlError("procedure failed canonical revalidation") from exc
    case_snapshots = tuple(ProcedureNegativeControlCase._validated_snapshot(case) for case in cases)
    return ProcedureNegativeControlReport(
        procedure_sha256=procedure_sha256,
        declared_failure_modes=declared_failure_modes,
        cases=case_snapshots,
    )


def _require_sorted_texts(
    values: tuple[str, ...],
    label: str,
    *,
    required: bool,
) -> None:
    if type(values) is not tuple:
        raise ProcedureNegativeControlError(f"{label} must be an exact tuple")
    if required and not values:
        raise ProcedureNegativeControlError(f"{label} cannot be empty")
    for value in values:
        _require_text(value, label)
    if values != tuple(sorted(set(values))):
        raise ProcedureNegativeControlError(f"{label} must be unique and strictly sorted")


def _require_id(value: object, label: str) -> None:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ProcedureNegativeControlError(f"{label} must use lowercase kebab-case semantics")


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ProcedureNegativeControlError(f"{label} must be canonical non-empty text")
    if any(character in value for character in "\x00\r\n\t"):
        raise ProcedureNegativeControlError(f"{label} cannot contain control characters")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ProcedureNegativeControlError(f"{label} must be 64 lowercase hex")
