"""Adversarial MRL-0205 tests for forged MRL-0204 decisions."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_fixture_loop_v1 import FixtureLoopResult
from medscale.mesc._mrl_fixture_replication_v1 import (
    FixtureReplicationError,
    assess_fixture_replication,
    request_fixture_replication,
)
from medscale.mesc._mrl_research_decision_v1 import (
    ResearchDecision,
    ResearchDecisionState,
)
from test_mesc_mrl_fixture_replication_v1 import _complete


def _forge_evidence_candidate(result: FixtureLoopResult) -> FixtureLoopResult:
    guardrail = result.receipt.guardrail_results[0]
    rejected_receipt = replace(
        result.receipt,
        guardrail_results=(replace(guardrail, passed=False),),
    )
    forged_decision = ResearchDecision(
        receipt_sha256=rejected_receipt.content_sha256,
        evidence_sha256s=(result.observation.content_sha256,),
        state=ResearchDecisionState.EVIDENCE_CANDIDATE,
        reason="Caller-forged evidence-candidate state for adversarial coverage.",
    )
    return FixtureLoopResult(
        proposal=result.proposal,
        observation=result.observation,
        receipt=rejected_receipt,
        decision=forged_decision,
    )


def test_primary_forged_evidence_candidate_is_recomputed_and_rejected() -> None:
    forged_primary = _forge_evidence_candidate(_complete("forged-primary"))

    with pytest.raises(
        FixtureReplicationError,
        match="primary decision does not match canonical MRL-0204 decision logic",
    ):
        request_fixture_replication(forged_primary)


def test_replica_forged_evidence_candidate_cannot_produce_retained_lead() -> None:
    primary = _complete("primary")
    request = request_fixture_replication(primary)
    forged_replica = _forge_evidence_candidate(_complete("forged-replica"))

    with pytest.raises(
        FixtureReplicationError,
        match="replica decision does not match canonical MRL-0204 decision logic",
    ):
        assess_fixture_replication(primary, request, forged_replica)
