"""MRL-0304 tests for the sealed Tier 3 evaluation interface."""

from __future__ import annotations

from dataclasses import fields
from typing import cast

import pytest

from medscale.mesc._mrl_research_objective_v1 import EvaluationTier
from medscale.mesc._mrl_sealed_evaluation_interface_v1 import (
    SealedEvaluationHandoff,
    SealedEvaluationInterfaceError,
    SealedEvaluationRequest,
    build_sealed_evaluation_request,
    record_sealed_evidence_handoff,
)
from medscale.mesc._mrl_tier_evaluation_contract_v1 import TierEvaluationContract
from test_mesc_mrl_research_objective_v1 import _objective


def _sealed_contract() -> TierEvaluationContract:
    return TierEvaluationContract(objective=_objective(), tier=EvaluationTier.SEALED)


def _request() -> SealedEvaluationRequest:
    return build_sealed_evaluation_request(
        _sealed_contract(),
        candidate_sha256="a" * 64,
        source_receipt_sha256="b" * 64,
    )


def test_request_is_deterministic_identity_only_and_bound_to_sealed_evaluator() -> None:
    first = _request()
    second = _request()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.evaluator_ids == ("eval.sealed",)
    assert first.to_dict()["tier"] == 3
    assert b"score" not in first.semantic_bytes
    assert b"item_level" not in first.semantic_bytes


def test_handoff_is_opaque_non_iterative_and_non_authoritative() -> None:
    handoff = record_sealed_evidence_handoff(_request(), "c" * 64)
    payload = handoff.to_dict()

    assert payload["agent_visible_result_fields"] == []
    assert payload["iterative_agent_result_stream"] is False
    assert payload["sealed_item_level_search_context"] is False
    assert payload["can_authorize"] is False
    assert payload["can_authorize_model_promotion"] is False
    assert b"PROMOTED" not in handoff.semantic_bytes


def test_interface_surface_cannot_carry_sealed_item_content_or_scores() -> None:
    assert tuple(field.name for field in fields(SealedEvaluationRequest)) == (
        "tier_contract_sha256",
        "candidate_sha256",
        "source_receipt_sha256",
        "evaluator_ids",
    )
    assert tuple(field.name for field in fields(SealedEvaluationHandoff)) == (
        "request_sha256",
        "sealed_evidence_ref_sha256",
    )


def test_non_sealed_tier_contract_fails_closed() -> None:
    search = TierEvaluationContract(objective=_objective(), tier=EvaluationTier.SEARCH)

    with pytest.raises(SealedEvaluationInterfaceError, match="requires Tier 3 SEALED"):
        build_sealed_evaluation_request(search, "a" * 64, "b" * 64)


def test_hash_and_exact_type_validation_fail_closed() -> None:
    with pytest.raises(SealedEvaluationInterfaceError, match="candidate_sha256"):
        build_sealed_evaluation_request(_sealed_contract(), "A" * 64, "b" * 64)
    with pytest.raises(SealedEvaluationInterfaceError, match="request must be an exact"):
        record_sealed_evidence_handoff(
            cast(SealedEvaluationRequest, object()),
            "c" * 64,
        )
    with pytest.raises(SealedEvaluationInterfaceError, match="sealed_evidence_ref_sha256"):
        record_sealed_evidence_handoff(_request(), "not-a-sha")


def test_handoff_identity_changes_with_independent_evidence_reference() -> None:
    first = record_sealed_evidence_handoff(_request(), "c" * 64)
    second = record_sealed_evidence_handoff(_request(), "d" * 64)

    assert first.content_sha256 != second.content_sha256
    assert first.semantic_bytes != second.semantic_bytes
