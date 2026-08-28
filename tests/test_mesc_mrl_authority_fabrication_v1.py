"""MRL-0213 negative tests for fixture-agent authority fabrication."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._mrl_fixture_replication_v1 import start_fixture_campaign
from medscale.mesc._mrl_research_decision_v1 import (
    ResearchDecision,
    ResearchDecisionError,
    ResearchDecisionState,
)
from medscale.mesc._mrl_research_procedure_v1 import (
    ProcedureAdmissionDecision,
    ProcedureAdmissionState,
    ProcedureReportAuthorKind,
    ResearchProcedureAdmissionReport,
    ResearchProcedureError,
)
from test_mesc_mrl_fixture_replication_v1 import _complete
from test_mesc_mrl_research_procedure_v1 import _candidate_procedure, _report

_REPLAY_SHA = "1" * 64
_TRANSFER_SHA = "2" * 64
_NEGATIVE_SHA = "3" * 64
_REVIEW_SHA = "4" * 64


def _fixture_bound_transferred_report() -> ResearchProcedureAdmissionReport:
    fixture = _complete("authority-fabrication")
    campaign = start_fixture_campaign("authority-fabrication-campaign", fixture)
    procedure = replace(
        _candidate_procedure(),
        source_campaign_sha256s=(campaign.content_sha256,),
    )
    subject = procedure.admission_subject_sha256
    discovered = _report(
        ProcedureAdmissionState.DISCOVERED,
        procedure_sha256=subject,
    )
    candidate = _report(
        ProcedureAdmissionState.CANDIDATE,
        procedure_sha256=subject,
        parent=discovered,
    )
    replayed = _report(
        ProcedureAdmissionState.REPLAYED,
        procedure_sha256=subject,
        parent=candidate,
        replay=(_REPLAY_SHA,),
    )
    return _report(
        ProcedureAdmissionState.TRANSFER_TESTED,
        procedure_sha256=subject,
        parent=replayed,
        replay=(_REPLAY_SHA,),
        transfer=(_TRANSFER_SHA,),
    )


def test_fixture_result_cannot_fabricate_promoted_decision() -> None:
    fixture = _complete("promoted-fabrication")

    assert fixture.decision.can_authorize_promotion is False
    with pytest.raises(
        ResearchDecisionError,
        match="promotion-authority states are not allowed",
    ):
        ResearchDecision(
            receipt_sha256=fixture.receipt.content_sha256,
            evidence_sha256s=(fixture.observation.content_sha256,),
            state=cast(ResearchDecisionState, "PROMOTED"),
            reason="Fixture agent attempted to fabricate promotion authority.",
        )


@pytest.mark.parametrize(
    "author_kind",
    (
        ProcedureReportAuthorKind.RESEARCH_AGENT,
        ProcedureReportAuthorKind.CAMPAIGN_AGENT,
    ),
    ids=lambda item: item.value.lower(),
)
def test_fixture_agent_cannot_self_review_procedure(
    author_kind: ProcedureReportAuthorKind,
) -> None:
    transferred = _fixture_bound_transferred_report()

    with pytest.raises(
        ResearchProcedureError,
        match="research/campaign agents cannot produce REVIEWED or ADMITTED reports",
    ):
        _report(
            ProcedureAdmissionState.REVIEWED,
            procedure_sha256=transferred.procedure_sha256,
            parent=transferred,
            author_kind=author_kind,
            author_id="fixture-agent",
            reviewer_authority_id="fabricated-reviewer-authority",
            review_receipt_sha256=_REVIEW_SHA,
            decision=ProcedureAdmissionDecision.ADMIT,
            replay=(_REPLAY_SHA,),
            transfer=(_TRANSFER_SHA,),
            negative=(_NEGATIVE_SHA,),
        )


@pytest.mark.parametrize(
    "author_kind",
    (
        ProcedureReportAuthorKind.RESEARCH_AGENT,
        ProcedureReportAuthorKind.CAMPAIGN_AGENT,
    ),
    ids=lambda item: item.value.lower(),
)
def test_fixture_agent_cannot_self_admit_procedure(
    author_kind: ProcedureReportAuthorKind,
) -> None:
    transferred = _fixture_bound_transferred_report()
    reviewed = _report(
        ProcedureAdmissionState.REVIEWED,
        procedure_sha256=transferred.procedure_sha256,
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

    with pytest.raises(
        ResearchProcedureError,
        match="research/campaign agents cannot produce REVIEWED or ADMITTED reports",
    ):
        _report(
            ProcedureAdmissionState.ADMITTED,
            procedure_sha256=reviewed.procedure_sha256,
            parent=reviewed,
            author_kind=author_kind,
            author_id="fixture-agent",
            reviewer_authority_id="reviewer-authority-1",
            review_receipt_sha256=_REVIEW_SHA,
            decision=ProcedureAdmissionDecision.ADMIT,
            replay=(_REPLAY_SHA,),
            transfer=(_TRANSFER_SHA,),
            negative=(_NEGATIVE_SHA,),
        )
