"""MRL-0106 tests for the immutable ResearchDecision artifact."""

from __future__ import annotations

import enum
from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._mrl_research_decision_v1 import (
    ResearchDecision,
    ResearchDecisionError,
    ResearchDecisionState,
)

_RECEIPT_SHA = "a" * 64
_EVIDENCE = ("b" * 64, "c" * 64)
_REASON = "The exact receipt satisfies the frozen research decision criteria."


def _decision(
    *,
    state: ResearchDecisionState = ResearchDecisionState.RETAIN_LEAD,
) -> ResearchDecision:
    return ResearchDecision(
        receipt_sha256=_RECEIPT_SHA,
        evidence_sha256s=_EVIDENCE,
        state=state,
        reason=_REASON,
    )


def test_state_set_is_exactly_the_mrl_v1_non_promotional_set() -> None:
    assert tuple(state.value for state in ResearchDecisionState) == (
        "INVALID",
        "REJECT",
        "REPLICATE",
        "RETAIN_LEAD",
        "EVIDENCE_CANDIDATE",
        "BLOCKED",
    )


@pytest.mark.parametrize("state", tuple(ResearchDecisionState))
def test_every_allowed_state_constructs_and_is_content_addressed(
    state: ResearchDecisionState,
) -> None:
    first = _decision(state=state)
    second = _decision(state=state)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert len(first.content_sha256) == 64


def test_decision_binds_exact_receipt_evidence_state_and_reason() -> None:
    decision = _decision()

    changed_receipt = replace(decision, receipt_sha256="d" * 64)
    changed_evidence = replace(decision, evidence_sha256s=("b" * 64, "e" * 64))
    changed_state = replace(decision, state=ResearchDecisionState.REPLICATE)
    changed_reason = replace(decision, reason="Replication is required before retention.")

    assert changed_receipt.content_sha256 != decision.content_sha256
    assert changed_evidence.content_sha256 != decision.content_sha256
    assert changed_state.content_sha256 != decision.content_sha256
    assert changed_reason.content_sha256 != decision.content_sha256


def test_content_identity_is_outside_semantic_preimage() -> None:
    decision = _decision()
    payload = decision.semantic_dict()

    assert "content_sha256" not in payload
    assert decision.to_dict()["content_sha256"] == decision.content_sha256


def test_evidence_candidate_is_explicitly_non_authoritative() -> None:
    decision = _decision(state=ResearchDecisionState.EVIDENCE_CANDIDATE)
    payload = decision.semantic_dict()

    assert payload["state"] == "EVIDENCE_CANDIDATE"
    assert payload["can_authorize_promotion"] is False
    assert decision.can_authorize_promotion is False


def test_promoted_string_is_rejected_as_a_state() -> None:
    with pytest.raises(ResearchDecisionError, match="promotion-authority states are not allowed"):
        ResearchDecision(
            receipt_sha256=_RECEIPT_SHA,
            evidence_sha256s=_EVIDENCE,
            state=cast(ResearchDecisionState, "PROMOTED"),
            reason=_REASON,
        )


def test_equivalent_promotion_authority_enum_is_rejected() -> None:
    class UnauthorizedDecisionState(enum.Enum):
        PROMOTED = "PROMOTED"
        PROMOTION_DECISION = "PromotionDecision"

    for unauthorized in UnauthorizedDecisionState:
        with pytest.raises(
            ResearchDecisionError,
            match="promotion-authority states are not allowed",
        ):
            ResearchDecision(
                receipt_sha256=_RECEIPT_SHA,
                evidence_sha256s=_EVIDENCE,
                state=cast(ResearchDecisionState, unauthorized),
                reason=_REASON,
            )


def test_evidence_identities_must_be_nonempty_sorted_unique_sha256s() -> None:
    with pytest.raises(ResearchDecisionError, match="cannot be empty"):
        ResearchDecision(
            receipt_sha256=_RECEIPT_SHA,
            evidence_sha256s=(),
            state=ResearchDecisionState.INVALID,
            reason=_REASON,
        )

    with pytest.raises(ResearchDecisionError, match="unique and strictly sorted"):
        ResearchDecision(
            receipt_sha256=_RECEIPT_SHA,
            evidence_sha256s=("c" * 64, "b" * 64),
            state=ResearchDecisionState.REJECT,
            reason=_REASON,
        )

    with pytest.raises(ResearchDecisionError, match="64 lowercase hex"):
        ResearchDecision(
            receipt_sha256=_RECEIPT_SHA,
            evidence_sha256s=("not-a-sha",),
            state=ResearchDecisionState.BLOCKED,
            reason=_REASON,
        )


def test_receipt_identity_must_be_exact_sha256() -> None:
    with pytest.raises(ResearchDecisionError, match="receipt_sha256"):
        ResearchDecision(
            receipt_sha256="A" * 64,
            evidence_sha256s=_EVIDENCE,
            state=ResearchDecisionState.INVALID,
            reason=_REASON,
        )


def test_reason_must_be_canonical_nonempty_text() -> None:
    for reason in ("", " leading", "trailing ", "line\nbreak"):
        with pytest.raises(ResearchDecisionError, match="reason"):
            ResearchDecision(
                receipt_sha256=_RECEIPT_SHA,
                evidence_sha256s=_EVIDENCE,
                state=ResearchDecisionState.REJECT,
                reason=reason,
            )


def test_post_construction_state_tampering_fails_on_next_trust_view() -> None:
    decision = _decision()
    object.__setattr__(decision, "state", cast(ResearchDecisionState, "PROMOTED"))

    with pytest.raises(ResearchDecisionError, match="promotion-authority states are not allowed"):
        _ = decision.content_sha256


def test_decision_subclass_cannot_produce_trust_bearing_views() -> None:
    class DecisionSubclass(ResearchDecision):
        pass

    decision = DecisionSubclass(
        receipt_sha256=_RECEIPT_SHA,
        evidence_sha256s=_EVIDENCE,
        state=ResearchDecisionState.RETAIN_LEAD,
        reason=_REASON,
    )

    with pytest.raises(ResearchDecisionError, match="exact ResearchDecision instance"):
        _ = decision.semantic_dict()
