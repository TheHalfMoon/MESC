"""Representative fixture transfer-test evidence for MRL research procedures.

MRL-0404 binds multiple independently identified fixture replay receipts to typed
applicability slices of one exact research-procedure candidate. Transfer evidence is
non-authoritative: it cannot advance the procedure-admission lifecycle, authorize model
promotion, or grant any real model/data/network/GPU/training authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_procedure_replay_v1 import (
    ProcedureReplayDisposition,
    ProcedureReplayReceipt,
)
from medscale.mesc._mrl_research_procedure_v1 import (
    ProcedureApplicabilityBounds,
    ResearchProcedure,
    ResearchProcedureError,
)

__all__ = [
    "ProcedureTransferCaseEvidence",
    "ProcedureTransferTestError",
    "ProcedureTransferTestReport",
    "build_procedure_transfer_test_report",
]

_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProcedureTransferTestError(ValueError):
    """Fail-closed validation error for representative procedure transfer evidence."""


@dataclass(frozen=True, slots=True)
class ProcedureTransferCaseEvidence:
    """One representative applicability slice and its exact fixture replay evidence."""

    case_id: str
    applicability_bounds: ProcedureApplicabilityBounds
    replay_receipt: ProcedureReplayReceipt
    evidence_artifact_sha256: str

    def __post_init__(self) -> None:
        _require_id(self.case_id, "case_id")
        if type(self.applicability_bounds) is not ProcedureApplicabilityBounds:
            raise ProcedureTransferTestError(
                "applicability_bounds must be an exact ProcedureApplicabilityBounds"
            )
        _rebuild_bounds(self.applicability_bounds)
        if type(self.replay_receipt) is not ProcedureReplayReceipt:
            raise ProcedureTransferTestError(
                "replay_receipt must be an exact ProcedureReplayReceipt"
            )
        _snapshot_replay(self.replay_receipt)
        _require_sha256(self.evidence_artifact_sha256, "evidence_artifact_sha256")

    def semantic_dict(self) -> dict[str, object]:
        replay = _snapshot_replay(self.replay_receipt)
        return {
            "applicability_bounds": _rebuild_bounds(self.applicability_bounds).to_dict(),
            "case_id": self.case_id,
            "evidence_artifact_sha256": self.evidence_artifact_sha256,
            "replay_receipt_sha256": replay.content_sha256,
            "replay_disposition": replay.disposition.value,
        }


@dataclass(frozen=True, slots=True)
class ProcedureTransferTestReport:
    """Immutable representative transfer evidence for one procedure admission subject."""

    procedure_sha256: str
    cases: tuple[ProcedureTransferCaseEvidence, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.procedure_sha256, "procedure_sha256")
        if type(self.cases) is not tuple or len(self.cases) < 2:
            raise ProcedureTransferTestError(
                "representative transfer evidence requires at least two exact cases"
            )
        if any(type(case) is not ProcedureTransferCaseEvidence for case in self.cases):
            raise ProcedureTransferTestError("cases contains an invalid item type")
        case_ids = tuple(case.case_id for case in self.cases)
        if case_ids != tuple(sorted(set(case_ids))):
            raise ProcedureTransferTestError("cases must be unique and sorted by case_id")
        evidence_ids = tuple(case.evidence_artifact_sha256 for case in self.cases)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ProcedureTransferTestError(
                "representative cases require distinct evidence artifact identities"
            )
        replay_ids = tuple(_snapshot_replay(case.replay_receipt).content_sha256 for case in self.cases)
        if len(replay_ids) != len(set(replay_ids)):
            raise ProcedureTransferTestError(
                "representative cases require distinct replay evidence identities"
            )
        for case in self.cases:
            replay = _snapshot_replay(case.replay_receipt)
            if replay.procedure_admission_subject_sha256 != self.procedure_sha256:
                raise ProcedureTransferTestError(
                    "transfer replay does not bind the report procedure identity"
                )

    @property
    def all_cases_reproduced(self) -> bool:
        return all(
            _snapshot_replay(case.replay_receipt).disposition
            is ProcedureReplayDisposition.REPRODUCED
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
            "all_cases_reproduced": self.all_cases_reproduced,
            "can_advance_admission": False,
            "can_authorize": False,
            "cases": [case.semantic_dict() for case in self.cases],
            "format": "MRL-PROCEDURE-TRANSFER-TEST-REPORT-V1",
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


def build_procedure_transfer_test_report(
    procedure: ResearchProcedure,
    cases: tuple[ProcedureTransferCaseEvidence, ...],
) -> ProcedureTransferTestReport:
    """Bind representative transfer cases to one freshly revalidated procedure candidate."""
    if type(procedure) is not ResearchProcedure:
        raise ProcedureTransferTestError("procedure must be an exact ResearchProcedure")
    if type(cases) is not tuple:
        raise ProcedureTransferTestError("cases must be an exact tuple")
    try:
        procedure_sha256 = procedure.admission_subject_sha256
        procedure_bounds = _rebuild_bounds(procedure.applicability_bounds)
    except ResearchProcedureError as exc:
        raise ProcedureTransferTestError("procedure failed canonical revalidation") from exc

    for case in cases:
        if type(case) is not ProcedureTransferCaseEvidence:
            raise ProcedureTransferTestError("cases contains an invalid item type")
        case_bounds = _rebuild_bounds(case.applicability_bounds)
        if not _bounds_within(case_bounds, procedure_bounds):
            raise ProcedureTransferTestError(
                "transfer case applicability must remain within procedure applicability"
            )
        replay = _snapshot_replay(case.replay_receipt)
        if replay.procedure_admission_subject_sha256 != procedure_sha256:
            raise ProcedureTransferTestError(
                "transfer replay does not bind the supplied procedure candidate"
            )

    return ProcedureTransferTestReport(
        procedure_sha256=procedure_sha256,
        cases=cases,
    )


def _bounds_within(
    case: ProcedureApplicabilityBounds,
    procedure: ProcedureApplicabilityBounds,
) -> bool:
    return (
        set(case.research_program_refs).issubset(procedure.research_program_refs)
        and set(case.task_types).issubset(procedure.task_types)
        and set(case.model_classes).issubset(procedure.model_classes)
        and set(case.data_classes).issubset(procedure.data_classes)
        and set(case.evaluation_tiers).issubset(procedure.evaluation_tiers)
        and set(procedure.constraints).issubset(case.constraints)
    )


def _snapshot_replay(receipt: ProcedureReplayReceipt) -> ProcedureReplayReceipt:
    if type(receipt) is not ProcedureReplayReceipt:
        raise ProcedureTransferTestError("replay receipt has an invalid type")
    try:
        return ProcedureReplayReceipt(
            procedure_admission_subject_sha256=receipt.procedure_admission_subject_sha256,
            procedure_content_sha256=receipt.procedure_content_sha256,
            surface_sha256=receipt.surface_sha256,
            evaluator_sha256=receipt.evaluator_sha256,
            candidate_sha256=receipt.candidate_sha256,
            evaluation_sha256=receipt.evaluation_sha256,
            metric_id=receipt.metric_id,
            expected_score=receipt.expected_score,
            expected_max_score=receipt.expected_max_score,
            observed_score=receipt.observed_score,
            observed_max_score=receipt.observed_max_score,
            disposition=receipt.disposition,
        )
    except (ProcedureTransferTestError, ValueError) as exc:
        raise ProcedureTransferTestError("replay receipt failed canonical revalidation") from exc


def _rebuild_bounds(bounds: ProcedureApplicabilityBounds) -> ProcedureApplicabilityBounds:
    if type(bounds) is not ProcedureApplicabilityBounds:
        raise ProcedureTransferTestError("applicability bounds have an invalid type")
    try:
        return ProcedureApplicabilityBounds(
            research_program_refs=bounds.research_program_refs,
            task_types=bounds.task_types,
            model_classes=bounds.model_classes,
            data_classes=bounds.data_classes,
            evaluation_tiers=bounds.evaluation_tiers,
            constraints=bounds.constraints,
        )
    except ResearchProcedureError as exc:
        raise ProcedureTransferTestError("applicability bounds failed revalidation") from exc


def _require_id(value: object, label: str) -> None:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ProcedureTransferTestError(f"{label} must use lowercase kebab-case semantics")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ProcedureTransferTestError(f"{label} must be 64 lowercase hex")
