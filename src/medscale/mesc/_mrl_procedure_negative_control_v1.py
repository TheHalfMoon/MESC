"""Negative and failure-control evidence for MRL research procedures.

MRL-0405 records whether declared procedure failure modes are exercised by independent
negative-control evidence. Unexpected success and wrong-failure outcomes remain first-
class evidence. This contract cannot advance procedure admission or authorize real model,
data, network, GPU, training, promotion, deployment, release, or clinical activity.
"""

from __future__ import annotations

import enum
import re
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


@dataclass(frozen=True, slots=True)
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

    @property
    def disposition(self) -> NegativeControlDisposition:
        if self.observed_failure_mode is None:
            return NegativeControlDisposition.UNEXPECTED_SUCCESS
        if self.observed_failure_mode == self.expected_failure_mode:
            return NegativeControlDisposition.EXPECTED_FAILURE_OBSERVED
        return NegativeControlDisposition.WRONG_FAILURE_MODE

    def semantic_dict(self) -> dict[str, object]:
        return {
            "control_id": self.control_id,
            "disposition": self.disposition.value,
            "evidence_artifact_sha256": self.evidence_artifact_sha256,
            "expected_failure_mode": self.expected_failure_mode,
            "observed_failure_mode": self.observed_failure_mode,
        }


@dataclass(frozen=True, slots=True)
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
        case_ids = tuple(case.control_id for case in self.cases)
        if case_ids != tuple(sorted(set(case_ids))):
            raise ProcedureNegativeControlError("cases must be unique and sorted by control_id")
        evidence_ids = tuple(case.evidence_artifact_sha256 for case in self.cases)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ProcedureNegativeControlError(
                "negative controls require distinct evidence artifact identities"
            )
        for case in self.cases:
            if case.expected_failure_mode not in self.declared_failure_modes:
                raise ProcedureNegativeControlError(
                    "negative control references an undeclared procedure failure mode"
                )

    @property
    def coverage_complete(self) -> bool:
        covered = {case.expected_failure_mode for case in self.cases}
        return covered == set(self.declared_failure_modes)

    @property
    def all_controls_pass(self) -> bool:
        return self.coverage_complete and all(
            case.disposition is NegativeControlDisposition.EXPECTED_FAILURE_OBSERVED
            for case in self.cases
        )

    @property
    def can_advance_admission(self) -> bool:
        return False

    @property
    def can_authorize(self) -> bool:
        return False

    def semantic_dict(self) -> dict[str, object]:
        return {
            "all_controls_pass": self.all_controls_pass,
            "can_advance_admission": False,
            "can_authorize": False,
            "cases": [case.semantic_dict() for case in self.cases],
            "coverage_complete": self.coverage_complete,
            "declared_failure_modes": list(self.declared_failure_modes),
            "format": "MRL-PROCEDURE-NEGATIVE-CONTROL-REPORT-V1",
            "procedure_sha256": self.procedure_sha256,
        }

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
        procedure_sha256 = procedure.admission_subject_sha256
        declared_failure_modes = tuple(sorted(procedure.known_failure_modes))
    except ResearchProcedureError as exc:
        raise ProcedureNegativeControlError("procedure failed canonical revalidation") from exc
    return ProcedureNegativeControlReport(
        procedure_sha256=procedure_sha256,
        declared_failure_modes=declared_failure_modes,
        cases=cases,
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
