"""MRL-0406 tests for independent evidence-bound procedure admission."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace

import pytest

from medscale.mesc import _mrl_procedure_review_trust_v1 as review_trust
from medscale.mesc._mrl_procedure_admission_gate_v1 import (
    ProcedureAdmissionGateError,
    ProcedureAdmissionGateResult,
    ProcedureReviewReceipt,
    evaluate_procedure_admission,
)
from medscale.mesc._mrl_procedure_negative_control_v1 import (
    ProcedureNegativeControlReport,
    build_procedure_negative_control_report,
)
from medscale.mesc._mrl_procedure_transfer_test_v1 import (
    ProcedureTransferTestReport,
    build_procedure_transfer_test_report,
)
from medscale.mesc._mrl_research_procedure_v1 import (
    ProcedureAdmissionDecision,
    ProcedureAdmissionState,
    ProcedureReportAuthorKind,
    ResearchProcedure,
    ResearchProcedureAdmissionReport,
)
from test_mesc_mrl_procedure_negative_control_v1 import _passing_case
from test_mesc_mrl_procedure_transfer_test_v1 import _cases
from test_mesc_mrl_research_procedure_v1 import _candidate_procedure


def _evidence() -> tuple[
    ResearchProcedure,
    ProcedureTransferTestReport,
    ProcedureNegativeControlReport,
]:
    procedure = _candidate_procedure()
    transfer = build_procedure_transfer_test_report(procedure, _cases())
    negative = build_procedure_negative_control_report(
        procedure,
        (_passing_case(),),
    )
    return procedure, transfer, negative


def _review_receipt(
    procedure: ResearchProcedure,
    transfer: ProcedureTransferTestReport,
    negative: ProcedureNegativeControlReport,
    *,
    decision: ProcedureAdmissionDecision = ProcedureAdmissionDecision.ADMIT,
) -> ProcedureReviewReceipt:
    replay_sha256s = tuple(
        sorted(case.replay_receipt.content_sha256 for case in transfer.cases)
    )
    return ProcedureReviewReceipt(
        reviewer_authority_id="fixture-independent-reviewer",
        author_kind=ProcedureReportAuthorKind.INDEPENDENT_REVIEWER,
        procedure_sha256=procedure.admission_subject_sha256,
        applicability_bounds=procedure.applicability_bounds,
        replay_evidence_sha256s=replay_sha256s,
        transfer_evidence_sha256s=(transfer.content_sha256,),
        negative_control_evidence_sha256s=(negative.content_sha256,),
        decision=decision,
        reason="Independent fixture review completed against exact evidence.",
    )


@contextmanager
def _trusted_receipt(receipt: ProcedureReviewReceipt) -> Iterator[str]:
    previous = review_trust._replace_procedure_review_trust_registry_for_tests(
        frozenset({receipt.content_sha256})
    )
    try:
        yield review_trust.procedure_review_trust_registry_sha256()
    finally:
        review_trust._replace_procedure_review_trust_registry_for_tests(previous)


def _states(
    report: ResearchProcedureAdmissionReport,
) -> tuple[ProcedureAdmissionState, ...]:
    reverse: list[ProcedureAdmissionState] = []
    current: ResearchProcedureAdmissionReport | None = report
    while current is not None:
        reverse.append(current.state)
        current = current.parent_report
    return tuple(reversed(reverse))


def test_well_formed_review_receipt_cannot_self_create_trust() -> None:
    procedure, transfer, negative = _evidence()
    receipt = _review_receipt(procedure, transfer, negative)
    assert (
        review_trust.procedure_review_trust_snapshot().trusted_review_receipt_sha256
        == frozenset()
    )

    with pytest.raises(
        ProcedureAdmissionGateError,
        match="not trusted by canonical governance",
    ):
        evaluate_procedure_admission(
            procedure,
            transfer,
            negative,
            receipt,
            expected_review_trust_registry_sha256=(
                review_trust.procedure_review_trust_registry_sha256()
            ),
        )


def test_trusted_independent_review_admits_only_after_exact_evidence_chain() -> None:
    procedure, transfer, negative = _evidence()
    receipt = _review_receipt(procedure, transfer, negative)

    with _trusted_receipt(receipt) as registry_sha256:
        result = evaluate_procedure_admission(
            procedure,
            transfer,
            negative,
            receipt,
            expected_review_trust_registry_sha256=registry_sha256,
        )

    assert isinstance(result, ProcedureAdmissionGateResult)
    assert result.decision is ProcedureAdmissionDecision.ADMIT
    assert result.final_state is ProcedureAdmissionState.ADMITTED
    assert result.procedure_admitted is True
    assert result.can_authorize_model_promotion is False
    assert result.admitted_report is not None
    assert result.admitted_procedure is not None
    assert _states(result.admitted_report) == (
        ProcedureAdmissionState.DISCOVERED,
        ProcedureAdmissionState.CANDIDATE,
        ProcedureAdmissionState.REPLAYED,
        ProcedureAdmissionState.TRANSFER_TESTED,
        ProcedureAdmissionState.REVIEWED,
        ProcedureAdmissionState.ADMITTED,
    )
    assert result.reviewed_report.review_receipt_sha256 == receipt.content_sha256
    assert result.admitted_report.review_receipt_sha256 == receipt.content_sha256
    assert (
        result.admitted_procedure.admission_report_sha256
        == result.admitted_report.content_sha256
    )
    assert result.content_sha256


def test_trusted_rejection_stops_at_reviewed_without_admitted_artifacts() -> None:
    procedure, transfer, negative = _evidence()
    receipt = _review_receipt(
        procedure,
        transfer,
        negative,
        decision=ProcedureAdmissionDecision.REJECT,
    )

    with _trusted_receipt(receipt) as registry_sha256:
        result = evaluate_procedure_admission(
            procedure,
            transfer,
            negative,
            receipt,
            expected_review_trust_registry_sha256=registry_sha256,
        )

    assert result.decision is ProcedureAdmissionDecision.REJECT
    assert result.final_state is ProcedureAdmissionState.REVIEWED
    assert result.procedure_admitted is False
    assert result.admitted_report is None
    assert result.admitted_procedure is None
    assert _states(result.reviewed_report) == (
        ProcedureAdmissionState.DISCOVERED,
        ProcedureAdmissionState.CANDIDATE,
        ProcedureAdmissionState.REPLAYED,
        ProcedureAdmissionState.TRANSFER_TESTED,
        ProcedureAdmissionState.REVIEWED,
    )


@pytest.mark.parametrize(
    "author_kind",
    (
        ProcedureReportAuthorKind.RESEARCH_AGENT,
        ProcedureReportAuthorKind.CAMPAIGN_AGENT,
    ),
)
def test_review_receipt_rejects_agent_authors(
    author_kind: ProcedureReportAuthorKind,
) -> None:
    procedure, transfer, negative = _evidence()
    with pytest.raises(
        ProcedureAdmissionGateError,
        match="independent reviewer or operator",
    ):
        ProcedureReviewReceipt(
            reviewer_authority_id="fabricated-reviewer",
            author_kind=author_kind,
            procedure_sha256=procedure.admission_subject_sha256,
            applicability_bounds=procedure.applicability_bounds,
            replay_evidence_sha256s=tuple(
                sorted(
                    case.replay_receipt.content_sha256
                    for case in transfer.cases
                )
            ),
            transfer_evidence_sha256s=(transfer.content_sha256,),
            negative_control_evidence_sha256s=(negative.content_sha256,),
            decision=ProcedureAdmissionDecision.ADMIT,
            reason="Agent attempted to fabricate independent review.",
        )


def test_review_receipt_must_bind_exact_transfer_evidence() -> None:
    procedure, transfer, negative = _evidence()
    receipt = _review_receipt(procedure, transfer, negative)
    object.__setattr__(
        receipt,
        "transfer_evidence_sha256s",
        ("f" * 64,),
    )

    with pytest.raises(
        ProcedureAdmissionGateError,
        match="review receipt identity changed after construction",
    ):
        evaluate_procedure_admission(
            procedure,
            transfer,
            negative,
            receipt,
            expected_review_trust_registry_sha256="0" * 64,
        )


def test_gate_result_revalidates_original_transfer_evidence_after_admission() -> None:
    procedure, transfer, negative = _evidence()
    receipt = _review_receipt(procedure, transfer, negative)
    with _trusted_receipt(receipt) as registry_sha256:
        result = evaluate_procedure_admission(
            procedure,
            transfer,
            negative,
            receipt,
            expected_review_trust_registry_sha256=registry_sha256,
        )

    object.__setattr__(transfer.cases[0], "evidence_artifact_sha256", "f" * 64)

    with pytest.raises(
        ProcedureAdmissionGateError,
        match="gate result evidence failed canonical revalidation",
    ):
        _ = result.content_sha256


def test_gate_result_revalidates_original_review_receipt_after_admission() -> None:
    procedure, transfer, negative = _evidence()
    receipt = _review_receipt(procedure, transfer, negative)
    with _trusted_receipt(receipt) as registry_sha256:
        result = evaluate_procedure_admission(
            procedure,
            transfer,
            negative,
            receipt,
            expected_review_trust_registry_sha256=registry_sha256,
        )

    object.__setattr__(receipt, "reason", "Different valid independent reason.")

    with pytest.raises(
        ProcedureAdmissionGateError,
        match="review receipt identity changed after construction",
    ):
        _ = result.semantic_dict()


def test_failed_negative_controls_cannot_be_admitted() -> None:
    procedure, transfer, _ = _evidence()
    failed_case = replace(_passing_case(), observed_failure_mode=None)
    negative = build_procedure_negative_control_report(
        procedure,
        (failed_case,),
    )
    receipt = _review_receipt(procedure, transfer, negative)

    previous = review_trust._replace_procedure_review_trust_registry_for_tests(
        frozenset({receipt.content_sha256})
    )
    try:
        with pytest.raises(
            ProcedureAdmissionGateError,
            match="complete passing negative controls",
        ):
            evaluate_procedure_admission(
                procedure,
                transfer,
                negative,
                receipt,
                expected_review_trust_registry_sha256=(
                    review_trust.procedure_review_trust_registry_sha256()
                ),
            )
    finally:
        review_trust._replace_procedure_review_trust_registry_for_tests(previous)


def test_stale_review_trust_registry_identity_fails_closed() -> None:
    procedure, transfer, negative = _evidence()
    receipt = _review_receipt(procedure, transfer, negative)
    with _trusted_receipt(receipt):
        with pytest.raises(
            ProcedureAdmissionGateError,
            match="not trusted by canonical governance",
        ):
            evaluate_procedure_admission(
                procedure,
                transfer,
                negative,
                receipt,
                expected_review_trust_registry_sha256="0" * 64,
            )
