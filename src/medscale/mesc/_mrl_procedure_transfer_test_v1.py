"""Representative fixture transfer-test evidence for MRL research procedures.

MRL-0404 binds multiple independently identified fixture replay receipts to typed
applicability slices of one exact research-procedure candidate. Transfer evidence is
non-authoritative: it cannot advance the procedure-admission lifecycle, authorize model
promotion, or grant any real model/data/network/GPU/training authority.
"""

from __future__ import annotations

import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_procedure_replay_v1 import (
    ProcedureReplayDisposition,
    ProcedureReplayError,
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


def _make_case_identity_registry() -> tuple[
    Callable[[ProcedureTransferCaseEvidence, str], None],
    Callable[[ProcedureTransferCaseEvidence], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: ProcedureTransferCaseEvidence, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ProcedureTransferTestError(
                "transfer case construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: ProcedureTransferCaseEvidence) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ProcedureTransferTestError(
                "transfer case construction identity is missing"
            )
        return identity

    return store, load


def _make_report_identity_registry() -> tuple[
    Callable[[ProcedureTransferTestReport, str], None],
    Callable[[ProcedureTransferTestReport], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: ProcedureTransferTestReport, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ProcedureTransferTestError(
                "transfer report construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: ProcedureTransferTestReport) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ProcedureTransferTestError(
                "transfer report construction identity is missing"
            )
        return identity

    return store, load


_store_case_identity, _load_case_identity = _make_case_identity_registry()
_store_report_identity, _load_report_identity = _make_report_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
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
        _store_case_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> ProcedureTransferCaseEvidence:
        if type(self) is not ProcedureTransferCaseEvidence:
            raise ProcedureTransferTestError(
                "case evidence must be an exact ProcedureTransferCaseEvidence"
            )
        bound_content_sha256 = _load_case_identity(self)
        _require_sha256(bound_content_sha256, "bound transfer case content_sha256")
        snapshot = ProcedureTransferCaseEvidence(
            case_id=self.case_id,
            applicability_bounds=_rebuild_bounds(self.applicability_bounds),
            replay_receipt=_snapshot_replay(self.replay_receipt),
            evidence_artifact_sha256=self.evidence_artifact_sha256,
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise ProcedureTransferTestError(
                "transfer case identity changed after construction"
            )
        return snapshot

    def _semantic_dict_validated(self) -> dict[str, object]:
        replay = _snapshot_replay(self.replay_receipt)
        return {
            "applicability_bounds": _rebuild_bounds(self.applicability_bounds).to_dict(),
            "case_id": self.case_id,
            "evidence_artifact_sha256": self.evidence_artifact_sha256,
            "replay_receipt_sha256": replay.content_sha256,
            "replay_disposition": replay.disposition.value,
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = ProcedureTransferCaseEvidence._validated_snapshot(self)
        return snapshot._semantic_dict_validated()


@dataclass(frozen=True, slots=True, weakref_slot=True)
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
        case_snapshots = tuple(
            ProcedureTransferCaseEvidence._validated_snapshot(case) for case in self.cases
        )
        case_ids = tuple(case.case_id for case in case_snapshots)
        if case_ids != tuple(sorted(set(case_ids))):
            raise ProcedureTransferTestError("cases must be unique and sorted by case_id")
        evidence_ids = tuple(case.evidence_artifact_sha256 for case in case_snapshots)
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ProcedureTransferTestError(
                "representative cases require distinct evidence artifact identities"
            )
        replay_snapshots = tuple(_snapshot_replay(case.replay_receipt) for case in case_snapshots)
        replay_ids = tuple(replay.content_sha256 for replay in replay_snapshots)
        if len(replay_ids) != len(set(replay_ids)):
            raise ProcedureTransferTestError(
                "representative cases require distinct replay evidence identities"
            )
        candidate_ids = tuple(replay.candidate_sha256 for replay in replay_snapshots)
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ProcedureTransferTestError(
                "representative cases require distinct fixture candidate identities"
            )
        for replay in replay_snapshots:
            if replay.procedure_admission_subject_sha256 != self.procedure_sha256:
                raise ProcedureTransferTestError(
                    "transfer replay does not bind the report procedure identity"
                )
        _store_report_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> ProcedureTransferTestReport:
        if type(self) is not ProcedureTransferTestReport:
            raise ProcedureTransferTestError(
                "report must be an exact ProcedureTransferTestReport"
            )
        if type(self.cases) is not tuple:
            raise ProcedureTransferTestError("cases must be an exact tuple")
        bound_content_sha256 = _load_report_identity(self)
        _require_sha256(bound_content_sha256, "bound transfer report content_sha256")
        snapshot = ProcedureTransferTestReport(
            procedure_sha256=self.procedure_sha256,
            cases=tuple(
                ProcedureTransferCaseEvidence._validated_snapshot(case) for case in self.cases
            ),
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise ProcedureTransferTestError(
                "transfer report identity changed after construction"
            )
        return snapshot

    def _all_cases_reproduced_validated(self) -> bool:
        return all(
            _snapshot_replay(case.replay_receipt).disposition
            is ProcedureReplayDisposition.REPRODUCED
            for case in self.cases
        )

    @property
    def all_cases_reproduced(self) -> bool:
        snapshot = ProcedureTransferTestReport._validated_snapshot(self)
        return snapshot._all_cases_reproduced_validated()

    @property
    def can_advance_admission(self) -> bool:
        return False

    @property
    def can_authorize(self) -> bool:
        return False

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "all_cases_reproduced": self._all_cases_reproduced_validated(),
            "can_advance_admission": False,
            "can_authorize": False,
            "cases": [case.semantic_dict() for case in self.cases],
            "format": "MRL-PROCEDURE-TRANSFER-TEST-REPORT-V1",
            "procedure_sha256": self.procedure_sha256,
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = ProcedureTransferTestReport._validated_snapshot(self)
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
        procedure_snapshot = procedure._validated_snapshot()
        procedure_sha256 = procedure_snapshot.admission_subject_sha256
        procedure_bounds = _rebuild_bounds(procedure_snapshot.applicability_bounds)
    except ResearchProcedureError as exc:
        raise ProcedureTransferTestError("procedure failed canonical revalidation") from exc

    validated_cases: list[ProcedureTransferCaseEvidence] = []
    for case in cases:
        if type(case) is not ProcedureTransferCaseEvidence:
            raise ProcedureTransferTestError("cases contains an invalid item type")
        case_snapshot = ProcedureTransferCaseEvidence._validated_snapshot(case)
        case_bounds = _rebuild_bounds(case_snapshot.applicability_bounds)
        if not _bounds_within(case_bounds, procedure_bounds):
            raise ProcedureTransferTestError(
                "transfer case applicability must remain within procedure applicability"
            )
        replay = _snapshot_replay(case_snapshot.replay_receipt)
        if replay.procedure_admission_subject_sha256 != procedure_sha256:
            raise ProcedureTransferTestError(
                "transfer replay does not bind the supplied procedure candidate"
            )
        validated_cases.append(case_snapshot)

    return ProcedureTransferTestReport(
        procedure_sha256=procedure_sha256,
        cases=tuple(validated_cases),
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
        return ProcedureReplayReceipt._validated_snapshot(receipt)
    except ProcedureReplayError as exc:
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
