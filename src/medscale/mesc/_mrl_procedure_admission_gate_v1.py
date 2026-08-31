"""Independent evidence-bound procedure-admission gate for MRL-0406.

The gate composes the existing six-stage ResearchProcedure admission lifecycle with the
canonical MRL-0403 replay, MRL-0404 representative-transfer, and MRL-0405 negative-control
evidence contracts. REVIEWED/ADMITTED output additionally requires an exact independent
review receipt trusted by the repository-controlled procedure-review trust registry.

The production review-trust registry starts empty, so well-formed reviewer strings or
receipt hashes cannot manufacture admission authority. This gate grants procedure-memory
admission only; it grants no model, data, network, GPU, training, promotion, deployment,
release, or clinical authority.
"""

from __future__ import annotations

import re
import weakref
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from typing import Final, Protocol

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_procedure_negative_control_v1 import (
    ProcedureNegativeControlError,
    ProcedureNegativeControlReport,
)
from medscale.mesc._mrl_procedure_replay_v1 import (
    ProcedureReplayDisposition,
    ProcedureReplayError,
    ProcedureReplayReceipt,
)
from medscale.mesc._mrl_procedure_review_trust_v1 import (
    ProcedureReviewTrustError,
    ProcedureReviewTrustSnapshot,
)
from medscale.mesc._mrl_procedure_review_trust_v1 import (
    hold_procedure_review_trust as _canonical_hold_procedure_review_trust,
)
from medscale.mesc._mrl_procedure_transfer_test_v1 import (
    ProcedureTransferTestError,
    ProcedureTransferTestReport,
)
from medscale.mesc._mrl_research_procedure_v1 import (
    ProcedureAdmissionDecision,
    ProcedureAdmissionState,
    ProcedureApplicabilityBounds,
    ProcedureReportAuthorKind,
    ResearchProcedure,
    ResearchProcedureAdmissionReport,
    ResearchProcedureError,
)

__all__ = [
    "ProcedureAdmissionGateError",
    "ProcedureAdmissionGateResult",
    "ProcedureReviewReceipt",
    "evaluate_procedure_admission",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)


class ProcedureAdmissionGateError(ValueError):
    """Fail-closed validation error for independent procedure admission."""


class _ProcedureReviewTrustLease(Protocol):
    def __call__(
        self,
        *,
        expected_registry_sha256: str,
        review_receipt_sha256: str,
    ) -> AbstractContextManager[ProcedureReviewTrustSnapshot]: ...


class _ProcedureAdmissionEvaluator(Protocol):
    def __call__(
        self,
        procedure: ResearchProcedure,
        transfer_report: ProcedureTransferTestReport,
        negative_control_report: ProcedureNegativeControlReport,
        review_receipt: ProcedureReviewReceipt,
        *,
        expected_review_trust_registry_sha256: str,
    ) -> ProcedureAdmissionGateResult: ...


def _bind_review_trust(
    hold_review_trust: _ProcedureReviewTrustLease,
) -> Callable[[Callable[..., ProcedureAdmissionGateResult]], _ProcedureAdmissionEvaluator]:
    """Capture canonical review trust outside ordinary module-level rebinding."""

    def decorate(
        method: Callable[..., ProcedureAdmissionGateResult],
    ) -> _ProcedureAdmissionEvaluator:
        def guarded(
            procedure: ResearchProcedure,
            transfer_report: ProcedureTransferTestReport,
            negative_control_report: ProcedureNegativeControlReport,
            review_receipt: ProcedureReviewReceipt,
            *,
            expected_review_trust_registry_sha256: str,
        ) -> ProcedureAdmissionGateResult:
            return method(
                hold_review_trust,
                procedure,
                transfer_report,
                negative_control_report,
                review_receipt,
                expected_review_trust_registry_sha256=(expected_review_trust_registry_sha256),
            )

        return guarded

    return decorate


def _make_receipt_identity_registry() -> tuple[
    Callable[[ProcedureReviewReceipt, str], None],
    Callable[[ProcedureReviewReceipt], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: ProcedureReviewReceipt, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ProcedureAdmissionGateError(
                "procedure review receipt construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: ProcedureReviewReceipt) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ProcedureAdmissionGateError(
                "procedure review receipt construction identity is missing"
            )
        return identity

    return store, load


def _make_result_identity_registry() -> tuple[
    Callable[[ProcedureAdmissionGateResult, str], None],
    Callable[[ProcedureAdmissionGateResult], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: ProcedureAdmissionGateResult, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ProcedureAdmissionGateError(
                "procedure admission gate result construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: ProcedureAdmissionGateResult) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ProcedureAdmissionGateError(
                "procedure admission gate result construction identity is missing"
            )
        return identity

    return store, load


_store_receipt_identity, _load_receipt_identity = _make_receipt_identity_registry()
_store_result_identity, _load_result_identity = _make_result_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureReviewReceipt:
    """Immutable independent-review disposition bound to exact procedure evidence."""

    reviewer_authority_id: str
    author_kind: ProcedureReportAuthorKind
    procedure_sha256: str
    applicability_bounds: ProcedureApplicabilityBounds
    replay_evidence_sha256s: tuple[str, ...]
    transfer_evidence_sha256s: tuple[str, ...]
    negative_control_evidence_sha256s: tuple[str, ...]
    decision: ProcedureAdmissionDecision
    reason: str

    def __post_init__(self) -> None:
        _require_text(self.reviewer_authority_id, "reviewer_authority_id")
        if self.author_kind not in (
            ProcedureReportAuthorKind.INDEPENDENT_REVIEWER,
            ProcedureReportAuthorKind.OPERATOR,
        ):
            raise ProcedureAdmissionGateError(
                "procedure review receipt requires independent reviewer or operator"
            )
        _require_sha256(self.procedure_sha256, "procedure_sha256")
        _rebuild_bounds(self.applicability_bounds)
        _require_sorted_sha256s(
            self.replay_evidence_sha256s,
            "replay_evidence_sha256s",
            required=True,
        )
        _require_sorted_sha256s(
            self.transfer_evidence_sha256s,
            "transfer_evidence_sha256s",
            required=True,
        )
        _require_sorted_sha256s(
            self.negative_control_evidence_sha256s,
            "negative_control_evidence_sha256s",
            required=True,
        )
        if self.decision not in (
            ProcedureAdmissionDecision.ADMIT,
            ProcedureAdmissionDecision.REJECT,
        ):
            raise ProcedureAdmissionGateError(
                "procedure review receipt must decide ADMIT or REJECT"
            )
        _require_text(self.reason, "reason")
        _store_receipt_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> ProcedureReviewReceipt:
        if type(self) is not ProcedureReviewReceipt:
            raise ProcedureAdmissionGateError(
                "review receipt must be an exact ProcedureReviewReceipt"
            )
        bound_sha256 = _load_receipt_identity(self)
        _require_sha256(bound_sha256, "bound review receipt content_sha256")
        snapshot = ProcedureReviewReceipt(
            reviewer_authority_id=self.reviewer_authority_id,
            author_kind=self.author_kind,
            procedure_sha256=self.procedure_sha256,
            applicability_bounds=_rebuild_bounds(self.applicability_bounds),
            replay_evidence_sha256s=self.replay_evidence_sha256s,
            transfer_evidence_sha256s=self.transfer_evidence_sha256s,
            negative_control_evidence_sha256s=self.negative_control_evidence_sha256s,
            decision=self.decision,
            reason=self.reason,
        )
        current_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_sha256 != bound_sha256:
            raise ProcedureAdmissionGateError(
                "procedure review receipt identity changed after construction"
            )
        return snapshot

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-PROCEDURE-REVIEW-RECEIPT-V1",
            "reviewer_authority_id": self.reviewer_authority_id,
            "author_kind": self.author_kind.value,
            "procedure_sha256": self.procedure_sha256,
            "applicability_bounds": _rebuild_bounds(self.applicability_bounds).to_dict(),
            "replay_evidence_sha256s": list(self.replay_evidence_sha256s),
            "transfer_evidence_sha256s": list(self.transfer_evidence_sha256s),
            "negative_control_evidence_sha256s": list(self.negative_control_evidence_sha256s),
            "decision": self.decision.value,
            "reason": self.reason,
            "can_authorize_by_itself": False,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = ProcedureReviewReceipt._validated_snapshot(self)
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


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureAdmissionGateResult:
    """Construction-bound result of one trusted independent admission evaluation."""

    procedure_sha256: str
    review_trust_registry_sha256: str
    review_receipt: ProcedureReviewReceipt
    transfer_report: ProcedureTransferTestReport
    negative_control_report: ProcedureNegativeControlReport
    reviewed_report: ResearchProcedureAdmissionReport
    admitted_report: ResearchProcedureAdmissionReport | None
    admitted_procedure: ResearchProcedure | None

    def __post_init__(self) -> None:
        _validate_gate_result(self)
        _store_result_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> ProcedureAdmissionGateResult:
        if type(self) is not ProcedureAdmissionGateResult:
            raise ProcedureAdmissionGateError(
                "gate result must be an exact ProcedureAdmissionGateResult"
            )
        bound_sha256 = _load_result_identity(self)
        _require_sha256(bound_sha256, "bound gate result content_sha256")
        _validate_gate_result(self)
        current_sha256 = derive_content_sha256(self._semantic_dict_validated())
        if current_sha256 != bound_sha256:
            raise ProcedureAdmissionGateError(
                "procedure admission gate result identity changed after construction"
            )
        return self

    @property
    def decision(self) -> ProcedureAdmissionDecision:
        snapshot = ProcedureAdmissionGateResult._validated_snapshot(self)
        return snapshot.review_receipt.decision

    @property
    def final_state(self) -> ProcedureAdmissionState:
        snapshot = ProcedureAdmissionGateResult._validated_snapshot(self)
        if snapshot.admitted_report is None:
            return ProcedureAdmissionState.REVIEWED
        return ProcedureAdmissionState.ADMITTED

    @property
    def procedure_admitted(self) -> bool:
        return self.final_state is ProcedureAdmissionState.ADMITTED

    @property
    def can_authorize_model_promotion(self) -> bool:
        return False

    def _semantic_dict_validated(self) -> dict[str, object]:
        review_receipt = ProcedureReviewReceipt._validated_snapshot(self.review_receipt)
        transfer = ProcedureTransferTestReport._validated_snapshot(self.transfer_report)
        negative = ProcedureNegativeControlReport._validated_snapshot(self.negative_control_report)
        reviewed_sha256 = self.reviewed_report.content_sha256
        admitted_sha256 = (
            None if self.admitted_report is None else self.admitted_report.content_sha256
        )
        admitted_procedure_sha256 = (
            None if self.admitted_procedure is None else self.admitted_procedure.content_sha256
        )
        return {
            "format": "MRL-PROCEDURE-ADMISSION-GATE-RESULT-V1",
            "procedure_sha256": self.procedure_sha256,
            "review_trust_registry_sha256": self.review_trust_registry_sha256,
            "review_receipt_sha256": review_receipt.content_sha256,
            "transfer_report_sha256": transfer.content_sha256,
            "negative_control_report_sha256": negative.content_sha256,
            "decision": review_receipt.decision.value,
            "final_state": (
                ProcedureAdmissionState.REVIEWED.value
                if self.admitted_report is None
                else ProcedureAdmissionState.ADMITTED.value
            ),
            "reviewed_report_sha256": reviewed_sha256,
            "admitted_report_sha256": admitted_sha256,
            "admitted_procedure_sha256": admitted_procedure_sha256,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = ProcedureAdmissionGateResult._validated_snapshot(self)
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


@_bind_review_trust(_canonical_hold_procedure_review_trust)
def evaluate_procedure_admission(
    hold_review_trust: _ProcedureReviewTrustLease,
    procedure: ResearchProcedure,
    transfer_report: ProcedureTransferTestReport,
    negative_control_report: ProcedureNegativeControlReport,
    review_receipt: ProcedureReviewReceipt,
    *,
    expected_review_trust_registry_sha256: str,
) -> ProcedureAdmissionGateResult:
    """Evaluate one candidate against exact evidence and independent review trust."""
    if type(procedure) is not ResearchProcedure:
        raise ProcedureAdmissionGateError("procedure must be an exact ResearchProcedure")
    if type(transfer_report) is not ProcedureTransferTestReport:
        raise ProcedureAdmissionGateError(
            "transfer_report must be an exact ProcedureTransferTestReport"
        )
    if type(negative_control_report) is not ProcedureNegativeControlReport:
        raise ProcedureAdmissionGateError(
            "negative_control_report must be an exact ProcedureNegativeControlReport"
        )
    if type(review_receipt) is not ProcedureReviewReceipt:
        raise ProcedureAdmissionGateError("review_receipt must be an exact ProcedureReviewReceipt")
    _require_sha256(
        expected_review_trust_registry_sha256,
        "expected_review_trust_registry_sha256",
    )

    try:
        procedure_snapshot = procedure._validated_snapshot()
        if (
            procedure_snapshot.admission_report_sha256 is not None
            or procedure_snapshot.admission_report is not None
        ):
            raise ProcedureAdmissionGateError(
                "procedure admission gate requires a pre-admission procedure candidate"
            )
        procedure_sha256 = procedure_snapshot.admission_subject_sha256
        applicability = _rebuild_bounds(procedure_snapshot.applicability_bounds)
        transfer_snapshot = ProcedureTransferTestReport._validated_snapshot(transfer_report)
        negative_snapshot = ProcedureNegativeControlReport._validated_snapshot(
            negative_control_report
        )
        review_snapshot = ProcedureReviewReceipt._validated_snapshot(review_receipt)
        replay_snapshots = tuple(
            ProcedureReplayReceipt._validated_snapshot(case.replay_receipt)
            for case in transfer_snapshot.cases
        )
    except (
        ResearchProcedureError,
        ProcedureTransferTestError,
        ProcedureNegativeControlError,
        ProcedureReplayError,
    ) as exc:
        raise ProcedureAdmissionGateError(
            "procedure admission evidence failed canonical revalidation"
        ) from exc

    if transfer_snapshot.procedure_sha256 != procedure_sha256:
        raise ProcedureAdmissionGateError("transfer evidence does not bind the supplied procedure")
    if negative_snapshot.procedure_sha256 != procedure_sha256:
        raise ProcedureAdmissionGateError(
            "negative-control evidence does not bind the supplied procedure"
        )
    if not transfer_snapshot.all_cases_reproduced:
        raise ProcedureAdmissionGateError(
            "procedure admission requires all representative transfer cases to reproduce"
        )
    if not negative_snapshot.coverage_complete or not negative_snapshot.all_controls_pass:
        raise ProcedureAdmissionGateError(
            "procedure admission requires complete passing negative controls"
        )
    if any(
        replay.disposition is not ProcedureReplayDisposition.REPRODUCED
        for replay in replay_snapshots
    ):
        raise ProcedureAdmissionGateError("procedure admission requires reproduced replay evidence")

    replay_evidence_sha256s = tuple(sorted(replay.content_sha256 for replay in replay_snapshots))
    transfer_evidence_sha256s = (transfer_snapshot.content_sha256,)
    negative_control_evidence_sha256s = (negative_snapshot.content_sha256,)

    if review_snapshot.procedure_sha256 != procedure_sha256:
        raise ProcedureAdmissionGateError("review receipt does not bind the supplied procedure")
    if review_snapshot.applicability_bounds.to_dict() != applicability.to_dict():
        raise ProcedureAdmissionGateError(
            "review receipt applicability does not match the procedure"
        )
    if review_snapshot.replay_evidence_sha256s != replay_evidence_sha256s:
        raise ProcedureAdmissionGateError("review receipt does not bind exact replay evidence")
    if review_snapshot.transfer_evidence_sha256s != transfer_evidence_sha256s:
        raise ProcedureAdmissionGateError("review receipt does not bind exact transfer evidence")
    if review_snapshot.negative_control_evidence_sha256s != negative_control_evidence_sha256s:
        raise ProcedureAdmissionGateError(
            "review receipt does not bind exact negative-control evidence"
        )

    review_receipt_sha256 = review_snapshot.content_sha256
    try:
        with hold_review_trust(
            expected_registry_sha256=expected_review_trust_registry_sha256,
            review_receipt_sha256=review_receipt_sha256,
        ) as trust_snapshot:
            result = _build_admission_result(
                procedure_snapshot=procedure_snapshot,
                applicability=applicability,
                replay_evidence_sha256s=replay_evidence_sha256s,
                transfer_evidence_sha256s=transfer_evidence_sha256s,
                negative_control_evidence_sha256s=negative_control_evidence_sha256s,
                review_receipt=review_receipt,
                transfer_report=transfer_report,
                negative_control_report=negative_control_report,
                review_trust_registry_sha256=trust_snapshot.registry_sha256,
            )
    except ProcedureReviewTrustError as exc:
        raise ProcedureAdmissionGateError(
            "independent procedure review is not trusted by canonical governance"
        ) from exc

    return result


del _bind_review_trust
del _canonical_hold_procedure_review_trust


def _build_admission_result(
    *,
    procedure_snapshot: ResearchProcedure,
    applicability: ProcedureApplicabilityBounds,
    replay_evidence_sha256s: tuple[str, ...],
    transfer_evidence_sha256s: tuple[str, ...],
    negative_control_evidence_sha256s: tuple[str, ...],
    review_receipt: ProcedureReviewReceipt,
    transfer_report: ProcedureTransferTestReport,
    negative_control_report: ProcedureNegativeControlReport,
    review_trust_registry_sha256: str,
) -> ProcedureAdmissionGateResult:
    subject = procedure_snapshot.admission_subject_sha256
    discovered = _make_report(
        procedure_sha256=subject,
        state=ProcedureAdmissionState.DISCOVERED,
        applicability=applicability,
        parent=None,
        replay=(),
        transfer=(),
        negative=(),
        author_kind=ProcedureReportAuthorKind.RESEARCH_AGENT,
        author_id="procedure-admission-gate",
        reviewer_authority_id=None,
        review_receipt_sha256=None,
        decision=ProcedureAdmissionDecision.CONTINUE,
        reason="Procedure discovered by the governed admission gate.",
    )
    candidate = _make_report(
        procedure_sha256=subject,
        state=ProcedureAdmissionState.CANDIDATE,
        applicability=applicability,
        parent=discovered,
        replay=(),
        transfer=(),
        negative=(),
        author_kind=ProcedureReportAuthorKind.RESEARCH_AGENT,
        author_id="procedure-admission-gate",
        reviewer_authority_id=None,
        review_receipt_sha256=None,
        decision=ProcedureAdmissionDecision.CONTINUE,
        reason="Procedure candidate entered governed replay qualification.",
    )
    replayed = _make_report(
        procedure_sha256=subject,
        state=ProcedureAdmissionState.REPLAYED,
        applicability=applicability,
        parent=candidate,
        replay=replay_evidence_sha256s,
        transfer=(),
        negative=(),
        author_kind=ProcedureReportAuthorKind.RESEARCH_AGENT,
        author_id="procedure-admission-gate",
        reviewer_authority_id=None,
        review_receipt_sha256=None,
        decision=ProcedureAdmissionDecision.CONTINUE,
        reason="Canonical replay evidence satisfied the replay stage.",
    )
    transferred = _make_report(
        procedure_sha256=subject,
        state=ProcedureAdmissionState.TRANSFER_TESTED,
        applicability=applicability,
        parent=replayed,
        replay=replay_evidence_sha256s,
        transfer=transfer_evidence_sha256s,
        negative=(),
        author_kind=ProcedureReportAuthorKind.RESEARCH_AGENT,
        author_id="procedure-admission-gate",
        reviewer_authority_id=None,
        review_receipt_sha256=None,
        decision=ProcedureAdmissionDecision.CONTINUE,
        reason="Representative transfer evidence satisfied the transfer stage.",
    )
    review_snapshot = ProcedureReviewReceipt._validated_snapshot(review_receipt)
    reviewed = _make_report(
        procedure_sha256=subject,
        state=ProcedureAdmissionState.REVIEWED,
        applicability=applicability,
        parent=transferred,
        replay=replay_evidence_sha256s,
        transfer=transfer_evidence_sha256s,
        negative=negative_control_evidence_sha256s,
        author_kind=review_snapshot.author_kind,
        author_id=review_snapshot.reviewer_authority_id,
        reviewer_authority_id=review_snapshot.reviewer_authority_id,
        review_receipt_sha256=review_snapshot.content_sha256,
        decision=review_snapshot.decision,
        reason=review_snapshot.reason,
    )

    admitted: ResearchProcedureAdmissionReport | None = None
    admitted_procedure: ResearchProcedure | None = None
    if review_snapshot.decision is ProcedureAdmissionDecision.ADMIT:
        admitted = _make_report(
            procedure_sha256=subject,
            state=ProcedureAdmissionState.ADMITTED,
            applicability=applicability,
            parent=reviewed,
            replay=replay_evidence_sha256s,
            transfer=transfer_evidence_sha256s,
            negative=negative_control_evidence_sha256s,
            author_kind=review_snapshot.author_kind,
            author_id=review_snapshot.reviewer_authority_id,
            reviewer_authority_id=review_snapshot.reviewer_authority_id,
            review_receipt_sha256=review_snapshot.content_sha256,
            decision=ProcedureAdmissionDecision.ADMIT,
            reason="Trusted independent review admitted the procedure.",
        )
        admitted_procedure = replace(
            procedure_snapshot,
            admission_report_sha256=admitted.content_sha256,
            admission_report=admitted,
        )

    return ProcedureAdmissionGateResult(
        procedure_sha256=subject,
        review_trust_registry_sha256=review_trust_registry_sha256,
        review_receipt=review_receipt,
        transfer_report=transfer_report,
        negative_control_report=negative_control_report,
        reviewed_report=reviewed,
        admitted_report=admitted,
        admitted_procedure=admitted_procedure,
    )


def _make_report(
    *,
    procedure_sha256: str,
    state: ProcedureAdmissionState,
    applicability: ProcedureApplicabilityBounds,
    parent: ResearchProcedureAdmissionReport | None,
    replay: tuple[str, ...],
    transfer: tuple[str, ...],
    negative: tuple[str, ...],
    author_kind: ProcedureReportAuthorKind,
    author_id: str,
    reviewer_authority_id: str | None,
    review_receipt_sha256: str | None,
    decision: ProcedureAdmissionDecision,
    reason: str,
) -> ResearchProcedureAdmissionReport:
    try:
        return ResearchProcedureAdmissionReport(
            procedure_sha256=procedure_sha256,
            state=state,
            applicability_bounds=applicability,
            replay_evidence_sha256s=replay,
            transfer_evidence_sha256s=transfer,
            negative_control_evidence_sha256s=negative,
            author_kind=author_kind,
            author_id=author_id,
            reviewer_authority_id=reviewer_authority_id,
            review_receipt_sha256=review_receipt_sha256,
            decision=decision,
            reason=reason,
            parent_report=parent,
        )
    except ResearchProcedureError as exc:
        raise ProcedureAdmissionGateError(
            "canonical procedure-admission lifecycle construction failed"
        ) from exc


def _validate_gate_result(result: ProcedureAdmissionGateResult) -> None:
    _require_sha256(result.procedure_sha256, "procedure_sha256")
    _require_sha256(
        result.review_trust_registry_sha256,
        "review_trust_registry_sha256",
    )
    review = ProcedureReviewReceipt._validated_snapshot(result.review_receipt)
    if type(result.transfer_report) is not ProcedureTransferTestReport:
        raise ProcedureAdmissionGateError(
            "transfer_report must be an exact ProcedureTransferTestReport"
        )
    if type(result.negative_control_report) is not ProcedureNegativeControlReport:
        raise ProcedureAdmissionGateError(
            "negative_control_report must be an exact ProcedureNegativeControlReport"
        )
    try:
        transfer = ProcedureTransferTestReport._validated_snapshot(result.transfer_report)
        negative = ProcedureNegativeControlReport._validated_snapshot(
            result.negative_control_report
        )
    except (ProcedureTransferTestError, ProcedureNegativeControlError) as exc:
        raise ProcedureAdmissionGateError(
            "gate result evidence failed canonical revalidation"
        ) from exc
    if review.procedure_sha256 != result.procedure_sha256:
        raise ProcedureAdmissionGateError("gate result review receipt changed procedure identity")
    if type(result.reviewed_report) is not ResearchProcedureAdmissionReport:
        raise ProcedureAdmissionGateError(
            "reviewed_report must be an exact ResearchProcedureAdmissionReport"
        )
    reviewed = result.reviewed_report._validated_snapshot()
    if reviewed.state is not ProcedureAdmissionState.REVIEWED:
        raise ProcedureAdmissionGateError("gate result reviewed_report must end at REVIEWED")
    if reviewed.procedure_sha256 != result.procedure_sha256:
        raise ProcedureAdmissionGateError("gate result reviewed report changed procedure identity")
    if transfer.procedure_sha256 != result.procedure_sha256:
        raise ProcedureAdmissionGateError("gate result transfer report changed procedure identity")
    if negative.procedure_sha256 != result.procedure_sha256:
        raise ProcedureAdmissionGateError(
            "gate result negative-control report changed procedure identity"
        )
    if review.transfer_evidence_sha256s != (transfer.content_sha256,):
        raise ProcedureAdmissionGateError(
            "gate result review receipt no longer binds transfer evidence"
        )
    if review.negative_control_evidence_sha256s != (negative.content_sha256,):
        raise ProcedureAdmissionGateError(
            "gate result review receipt no longer binds negative-control evidence"
        )
    if reviewed.review_receipt_sha256 != review.content_sha256:
        raise ProcedureAdmissionGateError(
            "gate result reviewed report does not bind the review receipt"
        )
    if reviewed.decision is not review.decision:
        raise ProcedureAdmissionGateError("gate result reviewed report changed the review decision")

    if review.decision is ProcedureAdmissionDecision.REJECT:
        if result.admitted_report is not None or result.admitted_procedure is not None:
            raise ProcedureAdmissionGateError("rejected procedure cannot carry admitted artifacts")
        return

    if type(result.admitted_report) is not ResearchProcedureAdmissionReport:
        raise ProcedureAdmissionGateError("ADMIT result requires an exact admitted report")
    admitted = result.admitted_report._validated_snapshot()
    if admitted.state is not ProcedureAdmissionState.ADMITTED:
        raise ProcedureAdmissionGateError("ADMIT result must end at ADMITTED")
    if admitted.procedure_sha256 != result.procedure_sha256:
        raise ProcedureAdmissionGateError("admitted report changed procedure identity")
    if admitted.review_receipt_sha256 != review.content_sha256:
        raise ProcedureAdmissionGateError("admitted report does not bind the review receipt")
    if type(result.admitted_procedure) is not ResearchProcedure:
        raise ProcedureAdmissionGateError("ADMIT result requires an exact admitted procedure")
    procedure = result.admitted_procedure._validated_snapshot()
    if procedure.admission_report_sha256 != admitted.content_sha256:
        raise ProcedureAdmissionGateError("admitted procedure does not bind the admitted report")
    if procedure.admission_subject_sha256 != result.procedure_sha256:
        raise ProcedureAdmissionGateError(
            "admitted procedure changed the admission subject identity"
        )


def _rebuild_bounds(
    bounds: ProcedureApplicabilityBounds,
) -> ProcedureApplicabilityBounds:
    if type(bounds) is not ProcedureApplicabilityBounds:
        raise ProcedureAdmissionGateError(
            "applicability bounds must be an exact ProcedureApplicabilityBounds"
        )
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
        raise ProcedureAdmissionGateError(
            "applicability bounds failed canonical revalidation"
        ) from exc


def _require_sorted_sha256s(
    values: tuple[str, ...],
    label: str,
    *,
    required: bool,
) -> None:
    if type(values) is not tuple:
        raise ProcedureAdmissionGateError(f"{label} must be an exact tuple")
    if required and not values:
        raise ProcedureAdmissionGateError(f"{label} cannot be empty")
    for value in values:
        _require_sha256(value, label)
    if values != tuple(sorted(set(values))):
        raise ProcedureAdmissionGateError(f"{label} must be unique and strictly sorted")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ProcedureAdmissionGateError(f"{label} must be 64 lowercase hex")


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ProcedureAdmissionGateError(f"{label} must be canonical non-empty text")
    if any(character in value for character in "\x00\r\n\t"):
        raise ProcedureAdmissionGateError(f"{label} cannot contain control characters")
