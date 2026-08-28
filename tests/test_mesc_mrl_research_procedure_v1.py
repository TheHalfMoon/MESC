"""MRL-0108 tests for ResearchProcedure and admission-report artifacts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_research_objective_v1 import EvaluationTier
from medscale.mesc._mrl_research_procedure_v1 import (
    ProcedureAdmissionDecision,
    ProcedureAdmissionState,
    ProcedureApplicabilityBounds,
    ProcedureReportAuthorKind,
    ResearchProcedure,
    ResearchProcedureAdmissionReport,
    ResearchProcedureError,
)

_REPLAY_SHA = "b" * 64
_TRANSFER_SHA = "c" * 64
_NEGATIVE_SHA = "d" * 64
_REVIEW_SHA = "e" * 64
_CAMPAIGN_SHA = "f" * 64


def _bounds() -> ProcedureApplicabilityBounds:
    return ProcedureApplicabilityBounds(
        research_program_refs=("RQ1",),
        task_types=("fixture-research",),
        model_classes=("fixture-model",),
        data_classes=("synthetic-fixture",),
        evaluation_tiers=(EvaluationTier.DEVELOPMENT,),
        constraints=("No real model, data, network, GPU, or training access.",),
    )


def _candidate_procedure() -> ResearchProcedure:
    return ResearchProcedure(
        procedure_id="fixture-procedure",
        version=1,
        applicability_bounds=_bounds(),
        preconditions=("A frozen fixture objective exists.",),
        allowed_tools=("fixture-evaluator",),
        forbidden_actions=("modify-governance", "read-sealed-item-level-data"),
        steps=("Run the fixture mutation.", "Evaluate the deterministic result."),
        expected_artifacts=("experiment-receipt",),
        verification_steps=("Verify the exact receipt identity.",),
        known_failure_modes=("budget-exhaustion",),
        source_campaign_sha256s=(_CAMPAIGN_SHA,),
    )


def _report(
    state: ProcedureAdmissionState,
    *,
    procedure_sha256: str,
    parent: ResearchProcedureAdmissionReport | None = None,
    author_kind: ProcedureReportAuthorKind = ProcedureReportAuthorKind.RESEARCH_AGENT,
    author_id: str = "research-agent",
    reviewer_authority_id: str | None = None,
    review_receipt_sha256: str | None = None,
    decision: ProcedureAdmissionDecision = ProcedureAdmissionDecision.CONTINUE,
    replay: tuple[str, ...] = (),
    transfer: tuple[str, ...] = (),
    negative: tuple[str, ...] = (),
) -> ResearchProcedureAdmissionReport:
    return ResearchProcedureAdmissionReport(
        procedure_sha256=procedure_sha256,
        state=state,
        applicability_bounds=_bounds(),
        replay_evidence_sha256s=replay,
        transfer_evidence_sha256s=transfer,
        negative_control_evidence_sha256s=negative,
        author_kind=author_kind,
        author_id=author_id,
        reviewer_authority_id=reviewer_authority_id,
        review_receipt_sha256=review_receipt_sha256,
        decision=decision,
        reason=f"Canonical {state.value.lower()} fixture disposition.",
        parent_report=parent,
    )


def _admitted_report(subject_sha256: str) -> ResearchProcedureAdmissionReport:
    discovered = _report(
        ProcedureAdmissionState.DISCOVERED,
        procedure_sha256=subject_sha256,
    )
    candidate = _report(
        ProcedureAdmissionState.CANDIDATE,
        procedure_sha256=subject_sha256,
        parent=discovered,
    )
    replayed = _report(
        ProcedureAdmissionState.REPLAYED,
        procedure_sha256=subject_sha256,
        parent=candidate,
        replay=(_REPLAY_SHA,),
    )
    transferred = _report(
        ProcedureAdmissionState.TRANSFER_TESTED,
        procedure_sha256=subject_sha256,
        parent=replayed,
        replay=(_REPLAY_SHA,),
        transfer=(_TRANSFER_SHA,),
    )
    reviewed = _report(
        ProcedureAdmissionState.REVIEWED,
        procedure_sha256=subject_sha256,
        parent=transferred,
        author_kind=ProcedureReportAuthorKind.INDEPENDENT_REVIEWER,
        author_id="independent-reviewer",
        reviewer_authority_id="reviewer-authority-1",
        review_receipt_sha256=_REVIEW_SHA,
        decision=ProcedureAdmissionDecision.ADMIT,
        replay=(_REPLAY_SHA,),
        transfer=(_TRANSFER_SHA,),
        negative=(_NEGATIVE_SHA,),
    )
    return _report(
        ProcedureAdmissionState.ADMITTED,
        procedure_sha256=subject_sha256,
        parent=reviewed,
        author_kind=ProcedureReportAuthorKind.INDEPENDENT_REVIEWER,
        author_id="independent-reviewer",
        reviewer_authority_id="reviewer-authority-1",
        review_receipt_sha256=_REVIEW_SHA,
        decision=ProcedureAdmissionDecision.ADMIT,
        replay=(_REPLAY_SHA,),
        transfer=(_TRANSFER_SHA,),
        negative=(_NEGATIVE_SHA,),
    )


def test_admission_state_set_is_exact() -> None:
    assert tuple(state.value for state in ProcedureAdmissionState) == (
        "DISCOVERED",
        "CANDIDATE",
        "REPLAYED",
        "TRANSFER_TESTED",
        "REVIEWED",
        "ADMITTED",
    )


def test_candidate_identity_is_deterministic_and_cycle_safe() -> None:
    first = _candidate_procedure()
    second = _candidate_procedure()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.admission_subject_sha256 == first.content_sha256
    assert first.semantic_dict()["admission_report_sha256"] is None
    assert "content_sha256" not in first.semantic_dict()


def test_full_admission_lifecycle_binds_subject_then_report() -> None:
    candidate = _candidate_procedure()
    admitted = _admitted_report(candidate.admission_subject_sha256)
    final = replace(
        candidate,
        admission_report_sha256=admitted.content_sha256,
        admission_report=admitted,
    )

    assert admitted.state is ProcedureAdmissionState.ADMITTED
    assert admitted.procedure_sha256 == candidate.admission_subject_sha256
    assert final.admission_subject_sha256 == candidate.content_sha256
    assert final.content_sha256 != final.admission_subject_sha256
    assert final.semantic_dict()["admission_report_sha256"] == admitted.content_sha256
    assert final.to_dict()["content_sha256"] == final.content_sha256


def test_lifecycle_cannot_skip_or_repeat_stages() -> None:
    subject = _candidate_procedure().admission_subject_sha256
    discovered = _report(ProcedureAdmissionState.DISCOVERED, procedure_sha256=subject)

    with pytest.raises(ResearchProcedureError, match="cannot skip or repeat"):
        _report(
            ProcedureAdmissionState.REPLAYED,
            procedure_sha256=subject,
            parent=discovered,
            replay=(_REPLAY_SHA,),
        )

    with pytest.raises(ResearchProcedureError, match="cannot skip or repeat"):
        _report(
            ProcedureAdmissionState.DISCOVERED,
            procedure_sha256=subject,
            parent=discovered,
        )


def test_replay_transfer_and_negative_control_evidence_are_required() -> None:
    subject = _candidate_procedure().admission_subject_sha256
    discovered = _report(ProcedureAdmissionState.DISCOVERED, procedure_sha256=subject)
    candidate = _report(
        ProcedureAdmissionState.CANDIDATE,
        procedure_sha256=subject,
        parent=discovered,
    )

    with pytest.raises(ResearchProcedureError, match="requires replay evidence"):
        _report(
            ProcedureAdmissionState.REPLAYED,
            procedure_sha256=subject,
            parent=candidate,
        )

    replayed = _report(
        ProcedureAdmissionState.REPLAYED,
        procedure_sha256=subject,
        parent=candidate,
        replay=(_REPLAY_SHA,),
    )
    with pytest.raises(ResearchProcedureError, match="requires representative transfer"):
        _report(
            ProcedureAdmissionState.TRANSFER_TESTED,
            procedure_sha256=subject,
            parent=replayed,
            replay=(_REPLAY_SHA,),
        )

    transferred = _report(
        ProcedureAdmissionState.TRANSFER_TESTED,
        procedure_sha256=subject,
        parent=replayed,
        replay=(_REPLAY_SHA,),
        transfer=(_TRANSFER_SHA,),
    )
    with pytest.raises(ResearchProcedureError, match="requires negative-control"):
        _report(
            ProcedureAdmissionState.REVIEWED,
            procedure_sha256=subject,
            parent=transferred,
            author_kind=ProcedureReportAuthorKind.INDEPENDENT_REVIEWER,
            author_id="independent-reviewer",
            reviewer_authority_id="reviewer-authority-1",
            review_receipt_sha256=_REVIEW_SHA,
            decision=ProcedureAdmissionDecision.ADMIT,
            replay=(_REPLAY_SHA,),
            transfer=(_TRANSFER_SHA,),
        )


def test_research_and_campaign_agents_cannot_self_review_or_admit() -> None:
    subject = _candidate_procedure().admission_subject_sha256
    admitted = _admitted_report(subject)
    transferred = admitted.parent_report
    assert transferred is not None
    reviewed = transferred.parent_report
    assert reviewed is not None
    transferred = reviewed

    for author_kind in (
        ProcedureReportAuthorKind.RESEARCH_AGENT,
        ProcedureReportAuthorKind.CAMPAIGN_AGENT,
    ):
        with pytest.raises(ResearchProcedureError, match="cannot produce REVIEWED"):
            _report(
                ProcedureAdmissionState.REVIEWED,
                procedure_sha256=subject,
                parent=transferred,
                author_kind=author_kind,
                reviewer_authority_id="reviewer-authority-1",
                review_receipt_sha256=_REVIEW_SHA,
                decision=ProcedureAdmissionDecision.ADMIT,
                replay=(_REPLAY_SHA,),
                transfer=(_TRANSFER_SHA,),
                negative=(_NEGATIVE_SHA,),
            )


def test_reviewed_requires_independent_authority_and_immutable_receipt() -> None:
    subject = _candidate_procedure().admission_subject_sha256
    admitted = _admitted_report(subject)
    reviewed = admitted.parent_report
    assert reviewed is not None
    transferred = reviewed.parent_report
    assert transferred is not None

    with pytest.raises(ResearchProcedureError, match="authority identity"):
        _report(
            ProcedureAdmissionState.REVIEWED,
            procedure_sha256=subject,
            parent=transferred,
            author_kind=ProcedureReportAuthorKind.INDEPENDENT_REVIEWER,
            author_id="independent-reviewer",
            review_receipt_sha256=_REVIEW_SHA,
            decision=ProcedureAdmissionDecision.ADMIT,
            replay=(_REPLAY_SHA,),
            transfer=(_TRANSFER_SHA,),
            negative=(_NEGATIVE_SHA,),
        )

    with pytest.raises(ResearchProcedureError, match="immutable review receipt"):
        _report(
            ProcedureAdmissionState.REVIEWED,
            procedure_sha256=subject,
            parent=transferred,
            author_kind=ProcedureReportAuthorKind.INDEPENDENT_REVIEWER,
            author_id="independent-reviewer",
            reviewer_authority_id="reviewer-authority-1",
            decision=ProcedureAdmissionDecision.ADMIT,
            replay=(_REPLAY_SHA,),
            transfer=(_TRANSFER_SHA,),
            negative=(_NEGATIVE_SHA,),
        )


def test_rejected_review_cannot_become_admitted() -> None:
    subject = _candidate_procedure().admission_subject_sha256
    admitted = _admitted_report(subject)
    reviewed = admitted.parent_report
    assert reviewed is not None
    rejected = replace(reviewed, decision=ProcedureAdmissionDecision.REJECT)

    with pytest.raises(ResearchProcedureError, match="parent to decide ADMIT"):
        _report(
            ProcedureAdmissionState.ADMITTED,
            procedure_sha256=subject,
            parent=rejected,
            author_kind=ProcedureReportAuthorKind.INDEPENDENT_REVIEWER,
            author_id="independent-reviewer",
            reviewer_authority_id="reviewer-authority-1",
            review_receipt_sha256=_REVIEW_SHA,
            decision=ProcedureAdmissionDecision.ADMIT,
            replay=(_REPLAY_SHA,),
            transfer=(_TRANSFER_SHA,),
            negative=(_NEGATIVE_SHA,),
        )


def test_admitted_cannot_rewrite_reviewer_identity_or_receipt() -> None:
    subject = _candidate_procedure().admission_subject_sha256
    admitted = _admitted_report(subject)
    reviewed = admitted.parent_report
    assert reviewed is not None

    with pytest.raises(ResearchProcedureError, match="cannot rewrite reviewer authority"):
        _report(
            ProcedureAdmissionState.ADMITTED,
            procedure_sha256=subject,
            parent=reviewed,
            author_kind=ProcedureReportAuthorKind.OPERATOR,
            author_id="operator",
            reviewer_authority_id="different-authority",
            review_receipt_sha256=_REVIEW_SHA,
            decision=ProcedureAdmissionDecision.ADMIT,
            replay=(_REPLAY_SHA,),
            transfer=(_TRANSFER_SHA,),
            negative=(_NEGATIVE_SHA,),
        )

    with pytest.raises(ResearchProcedureError, match="cannot rewrite the review receipt"):
        _report(
            ProcedureAdmissionState.ADMITTED,
            procedure_sha256=subject,
            parent=reviewed,
            author_kind=ProcedureReportAuthorKind.INDEPENDENT_REVIEWER,
            author_id="independent-reviewer",
            reviewer_authority_id="reviewer-authority-1",
            review_receipt_sha256="1" * 64,
            decision=ProcedureAdmissionDecision.ADMIT,
            replay=(_REPLAY_SHA,),
            transfer=(_TRANSFER_SHA,),
            negative=(_NEGATIVE_SHA,),
        )


def test_admission_evidence_is_append_only() -> None:
    subject = _candidate_procedure().admission_subject_sha256
    admitted = _admitted_report(subject)
    reviewed = admitted.parent_report
    assert reviewed is not None

    with pytest.raises(ResearchProcedureError, match="cannot delete prior replay evidence"):
        _report(
            ProcedureAdmissionState.ADMITTED,
            procedure_sha256=subject,
            parent=reviewed,
            author_kind=ProcedureReportAuthorKind.INDEPENDENT_REVIEWER,
            author_id="independent-reviewer",
            reviewer_authority_id="reviewer-authority-1",
            review_receipt_sha256=_REVIEW_SHA,
            decision=ProcedureAdmissionDecision.ADMIT,
            replay=(),
            transfer=(_TRANSFER_SHA,),
            negative=(_NEGATIVE_SHA,),
        )


def test_report_chain_cannot_change_applicability_or_subject_identity() -> None:
    procedure = _candidate_procedure()
    subject = procedure.admission_subject_sha256
    discovered = _report(ProcedureAdmissionState.DISCOVERED, procedure_sha256=subject)

    different_bounds = replace(_bounds(), task_types=("different-task",))
    with pytest.raises(ResearchProcedureError, match="changed applicability"):
        ResearchProcedureAdmissionReport(
            procedure_sha256=subject,
            state=ProcedureAdmissionState.CANDIDATE,
            applicability_bounds=different_bounds,
            replay_evidence_sha256s=(),
            transfer_evidence_sha256s=(),
            negative_control_evidence_sha256s=(),
            author_kind=ProcedureReportAuthorKind.RESEARCH_AGENT,
            author_id="research-agent",
            reviewer_authority_id=None,
            review_receipt_sha256=None,
            decision=ProcedureAdmissionDecision.CONTINUE,
            reason="Candidate with inconsistent applicability.",
            parent_report=discovered,
        )

    with pytest.raises(ResearchProcedureError, match="changed procedure identity"):
        _report(
            ProcedureAdmissionState.CANDIDATE,
            procedure_sha256="1" * 64,
            parent=discovered,
        )


def test_final_procedure_requires_exact_report_and_subject_bindings() -> None:
    candidate = _candidate_procedure()
    admitted = _admitted_report(candidate.admission_subject_sha256)

    with pytest.raises(ResearchProcedureError, match="does not match its SHA-256"):
        replace(
            candidate,
            admission_report_sha256="1" * 64,
            admission_report=admitted,
        )

    foreign_report = _admitted_report("1" * 64)
    with pytest.raises(ResearchProcedureError, match="does not bind the procedure"):
        replace(
            candidate,
            admission_report_sha256=foreign_report.content_sha256,
            admission_report=foreign_report,
        )


def test_allowed_and_forbidden_tool_overlap_fails_closed() -> None:
    candidate = _candidate_procedure()
    with pytest.raises(ResearchProcedureError, match="cannot overlap"):
        replace(candidate, forbidden_actions=("fixture-evaluator",))


def test_supersession_and_invalidation_references_are_validated() -> None:
    subject = _candidate_procedure().admission_subject_sha256
    with pytest.raises(ResearchProcedureError, match="supersedes_procedure_sha256s"):
        ResearchProcedureAdmissionReport(
            procedure_sha256=subject,
            state=ProcedureAdmissionState.DISCOVERED,
            applicability_bounds=_bounds(),
            replay_evidence_sha256s=(),
            transfer_evidence_sha256s=(),
            negative_control_evidence_sha256s=(),
            author_kind=ProcedureReportAuthorKind.RESEARCH_AGENT,
            author_id="research-agent",
            reviewer_authority_id=None,
            review_receipt_sha256=None,
            decision=ProcedureAdmissionDecision.CONTINUE,
            reason="Discovery with malformed supersession reference.",
            supersedes_procedure_sha256s=("not-a-sha",),
        )


def test_post_construction_report_tampering_fails_on_procedure_trust_view() -> None:
    candidate = _candidate_procedure()
    admitted = _admitted_report(candidate.admission_subject_sha256)
    final = replace(
        candidate,
        admission_report_sha256=admitted.content_sha256,
        admission_report=admitted,
    )
    object.__setattr__(admitted, "review_receipt_sha256", "not-a-sha")

    with pytest.raises(ResearchProcedureError, match="64 lowercase hex"):
        _ = final.content_sha256


def test_procedure_and_report_subclasses_cannot_produce_trust_views() -> None:
    class ProcedureSubclass(ResearchProcedure):
        pass

    class ReportSubclass(ResearchProcedureAdmissionReport):
        pass

    candidate = _candidate_procedure()
    with pytest.raises(ResearchProcedureError):
        ProcedureSubclass(
            procedure_id=candidate.procedure_id,
            version=candidate.version,
            applicability_bounds=candidate.applicability_bounds,
            preconditions=candidate.preconditions,
            allowed_tools=candidate.allowed_tools,
            forbidden_actions=candidate.forbidden_actions,
            steps=candidate.steps,
            expected_artifacts=candidate.expected_artifacts,
            verification_steps=candidate.verification_steps,
            known_failure_modes=candidate.known_failure_modes,
            source_campaign_sha256s=candidate.source_campaign_sha256s,
        ).semantic_dict()

    subject = candidate.admission_subject_sha256
    base = _report(ProcedureAdmissionState.DISCOVERED, procedure_sha256=subject)
    subclassed = ReportSubclass(
        procedure_sha256=base.procedure_sha256,
        state=base.state,
        applicability_bounds=base.applicability_bounds,
        replay_evidence_sha256s=base.replay_evidence_sha256s,
        transfer_evidence_sha256s=base.transfer_evidence_sha256s,
        negative_control_evidence_sha256s=base.negative_control_evidence_sha256s,
        author_kind=base.author_kind,
        author_id=base.author_id,
        reviewer_authority_id=base.reviewer_authority_id,
        review_receipt_sha256=base.review_receipt_sha256,
        decision=base.decision,
        reason=base.reason,
    )
    with pytest.raises(ResearchProcedureError, match="exact ResearchProcedureAdmissionReport"):
        _ = subclassed.content_sha256
