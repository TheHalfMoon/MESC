"""MRL-0301 tests for tier-aware evaluation semantics."""

from __future__ import annotations

from dataclasses import fields, replace
from typing import cast

import pytest

from medscale.mesc._mrl_research_objective_v1 import (
    AdaptiveQueryBudget,
    EvaluationTier,
    EvaluationTierPolicy,
    ResearchObjectiveContract,
    TierResultExposure,
)
from medscale.mesc._mrl_tier_evaluation_contract_v1 import (
    TierEvaluationContract,
    TierEvaluationContractError,
    TierInteractionMode,
)
from test_mesc_mrl_research_objective_v1 import _objective


def _all_tier_objective() -> ResearchObjectiveContract:
    return replace(
        _objective(),
        evaluation_tier_policy=EvaluationTierPolicy(allowed_tiers=tuple(EvaluationTier)),
        adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=5, tier_2_queries=2),
        tier_result_exposure_policy=(
            TierResultExposure(
                tier=EvaluationTier.DEVELOPMENT,
                max_exposures=1,
                allowed_result_fields=("fixture_score",),
            ),
            TierResultExposure(
                tier=EvaluationTier.SEARCH,
                max_exposures=5,
                allowed_result_fields=("aggregate_score", "cost_microunits"),
            ),
            TierResultExposure(
                tier=EvaluationTier.REPLICATION,
                max_exposures=2,
                allowed_result_fields=("aggregate_score",),
            ),
            TierResultExposure(
                tier=EvaluationTier.SEALED,
                max_exposures=0,
                allowed_result_fields=(),
            ),
            TierResultExposure(
                tier=EvaluationTier.EXTERNAL_ASSURANCE,
                max_exposures=0,
                allowed_result_fields=(),
            ),
        ),
    )


def test_contract_is_deterministic_content_addressed_and_non_authoritative() -> None:
    first = TierEvaluationContract(objective=_objective(), tier=EvaluationTier.SEARCH)
    second = TierEvaluationContract(objective=_objective(), tier=EvaluationTier.SEARCH)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.to_dict()["content_sha256"] == first.content_sha256
    assert first.can_authorize is False
    assert first.to_dict()["can_authorize"] is False
    assert first.to_dict()["can_authorize_real_execution"] is False
    assert first.to_dict()["can_authorize_training"] is False
    assert first.to_dict()["can_authorize_model_promotion"] is False
    assert b"PROMOTED" not in first.semantic_bytes


def test_search_tier_derives_exact_frozen_query_exposure_evaluator_and_metric_policy() -> None:
    contract = TierEvaluationContract(objective=_objective(), tier=EvaluationTier.SEARCH)
    payload = contract.to_dict()
    evaluators = cast(list[dict[str, object]], payload["evaluator_identities"])
    metrics = cast(list[dict[str, object]], payload["metric_contracts"])

    assert payload["objective_sha256"] == _objective().content_sha256
    assert payload["tier"] == 1
    assert payload["tier_name"] == "SEARCH"
    assert payload["interaction_mode"] == TierInteractionMode.ADAPTIVE_SEARCH.value
    assert payload["adaptive_query_ceiling"] == 5
    assert payload["result_exposure"] == {
        "tier": 1,
        "max_exposures": 5,
        "allowed_result_fields": ["aggregate_score", "cost_microunits"],
    }
    assert [item["evaluator_id"] for item in evaluators] == ["eval.search"]
    assert [item["metric_id"] for item in metrics] == ["search-score"]
    assert payload["iterative_agent_result_stream"] is True
    assert payload["sealed_item_level_search_context"] is False


def test_sealed_tier_has_no_adaptive_query_or_iterative_result_stream() -> None:
    contract = TierEvaluationContract(objective=_objective(), tier=EvaluationTier.SEALED)
    payload = contract.to_dict()
    evaluators = cast(list[dict[str, object]], payload["evaluator_identities"])
    metrics = cast(list[dict[str, object]], payload["metric_contracts"])

    assert payload["interaction_mode"] == TierInteractionMode.SEALED_INDEPENDENT_EVIDENCE.value
    assert payload["adaptive_query_ceiling"] == 0
    assert payload["result_exposure"] == {
        "tier": 3,
        "max_exposures": 0,
        "allowed_result_fields": [],
    }
    assert [item["evaluator_id"] for item in evaluators] == ["eval.sealed"]
    assert [item["metric_id"] for item in metrics] == ["safety"]
    assert payload["iterative_agent_result_stream"] is False
    assert payload["sealed_item_level_search_context"] is False


@pytest.mark.parametrize(
    ("tier", "expected_mode", "expected_queries", "stream"),
    (
        (
            EvaluationTier.DEVELOPMENT,
            TierInteractionMode.FIXTURE_DEVELOPMENT,
            0,
            True,
        ),
        (EvaluationTier.SEARCH, TierInteractionMode.ADAPTIVE_SEARCH, 5, True),
        (
            EvaluationTier.REPLICATION,
            TierInteractionMode.BOUNDED_REPLICATION,
            2,
            True,
        ),
        (
            EvaluationTier.SEALED,
            TierInteractionMode.SEALED_INDEPENDENT_EVIDENCE,
            0,
            False,
        ),
        (
            EvaluationTier.EXTERNAL_ASSURANCE,
            TierInteractionMode.EXTERNAL_ASSURANCE,
            0,
            False,
        ),
    ),
)
def test_all_canonical_tiers_have_distinct_permanent_interaction_semantics(
    tier: EvaluationTier,
    expected_mode: TierInteractionMode,
    expected_queries: int,
    stream: bool,
) -> None:
    payload = TierEvaluationContract(objective=_all_tier_objective(), tier=tier).to_dict()

    assert payload["interaction_mode"] == expected_mode.value
    assert payload["adaptive_query_ceiling"] == expected_queries
    assert payload["iterative_agent_result_stream"] is stream


def test_disallowed_tier_fails_closed() -> None:
    with pytest.raises(TierEvaluationContractError, match="not admitted"):
        TierEvaluationContract(objective=_objective(), tier=EvaluationTier.REPLICATION)


def test_material_objective_policy_change_changes_tier_contract_identity() -> None:
    original = TierEvaluationContract(objective=_objective(), tier=EvaluationTier.SEARCH)
    changed_objective = replace(
        _objective(),
        adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=4, tier_2_queries=0),
    )
    changed = TierEvaluationContract(objective=changed_objective, tier=EvaluationTier.SEARCH)

    assert changed.content_sha256 != original.content_sha256
    assert changed.semantic_bytes != original.semantic_bytes
    assert changed.to_dict()["adaptive_query_ceiling"] == 4


def test_callers_cannot_supply_replacement_budget_evaluator_or_exposure_fields() -> None:
    assert tuple(field.name for field in fields(TierEvaluationContract)) == ("objective", "tier")


def test_exact_objective_and_tier_types_are_required() -> None:
    with pytest.raises(TierEvaluationContractError, match="exact ResearchObjectiveContract"):
        TierEvaluationContract(
            objective=cast(ResearchObjectiveContract, object()),
            tier=EvaluationTier.SEARCH,
        )

    with pytest.raises(TierEvaluationContractError, match="exact EvaluationTier"):
        TierEvaluationContract(
            objective=_objective(),
            tier=cast(EvaluationTier, 1),
        )
