from __future__ import annotations

import pytest

from medscale.mesc._mrl_research_experiment_plan_v1 import (
    PlanTierAllowance,
    ResearchExperimentPlanError,
)
from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
    ResearchInputAdmissionError,
    ResearchInputClassification,
    ResearchInputDisposition,
    ResearchInputParentRef,
    ResearchInputSourcePermission,
    ResearchLearningSurface,
)
from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    ResearchObjectiveContractError,
    TierResultExposure,
)


def _sealed_item() -> ResearchInputAdmissionContract:
    return ResearchInputAdmissionContract(
        input_id="sealed-tier3-item-001",
        classification_policy_sha256="a" * 64,
        classification=ResearchInputClassification.SEALED_TIER3_ITEM_CONTENT,
        source_artifact_sha256=None,
        source_contract_sha256=None,
        allowed_learning_surfaces=(),
    )


def test_mrl_0207_sealed_item_cannot_enter_research_search_index() -> None:
    sealed = _sealed_item()

    assert sealed.disposition is ResearchInputDisposition.REJECTED
    assert sealed.source_artifact_sha256 is None
    assert sealed.source_contract_sha256 is None
    with pytest.raises(ResearchInputAdmissionError, match="not admitted as an MRL learning"):
        sealed.require_learning_admission(ResearchLearningSurface.RESEARCH_SEARCH_INDEX)


def test_mrl_0207_permission_cannot_authorize_sealed_item_for_search() -> None:
    with pytest.raises(
        ResearchInputAdmissionError,
        match="source permissions cannot authorize a rejected classification",
    ):
        ResearchInputSourcePermission(
            permission_id="permission-sealed-search",
            source_artifact_sha256="b" * 64,
            source_contract_sha256="c" * 64,
            classification=ResearchInputClassification.SEALED_TIER3_ITEM_CONTENT,
            allowed_learning_surfaces=(ResearchLearningSurface.RESEARCH_SEARCH_INDEX,),
        )


def test_mrl_0207_sealed_item_cannot_be_laundered_into_search_artifact() -> None:
    sealed_parent = ResearchInputParentRef(parent_admission=_sealed_item())
    search_surfaces = (ResearchLearningSurface.RESEARCH_SEARCH_INDEX,)
    permission = ResearchInputSourcePermission(
        permission_id="permission-derived-search-artifact",
        source_artifact_sha256="d" * 64,
        source_contract_sha256="e" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=search_surfaces,
    )

    with pytest.raises(
        ResearchInputAdmissionError,
        match="rejected parent cannot be transformed into an admissible MRL input",
    ):
        ResearchInputAdmissionContract(
            input_id="derived-sealed-search-artifact",
            classification_policy_sha256="a" * 64,
            classification=ResearchInputClassification.RESEARCH_ARTIFACT,
            source_artifact_sha256="d" * 64,
            source_contract_sha256="e" * 64,
            allowed_learning_surfaces=search_surfaces,
            source_permission=permission,
            transformation_kind="sealed-item-summary",
            parent_inputs=(sealed_parent,),
        )


def test_mrl_0207_search_process_cannot_query_sealed_tier() -> None:
    with pytest.raises(
        ResearchExperimentPlanError,
        match="only Tier 1 SEARCH and Tier 2 REPLICATION may consume adaptive queries",
    ):
        PlanTierAllowance(
            tier=EvaluationTier.SEALED,
            max_queries=1,
            max_result_exposures=0,
            allowed_result_fields=(),
        )


def test_mrl_0207_sealed_tier_cannot_expose_item_level_fields() -> None:
    with pytest.raises(
        ResearchObjectiveContractError,
        match="Tier 3/4 cannot expose iterative agent-visible result fields",
    ):
        TierResultExposure(
            tier=EvaluationTier.SEALED,
            max_exposures=1,
            allowed_result_fields=("item_id", "item_text"),
        )
