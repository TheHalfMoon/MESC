"""Regression coverage for simultaneous MRL-0105 accounting overruns."""

import pytest

from medscale.mesc._mrl_research_experiment_plan_v1 import PlanFailureCondition
from medscale.mesc._mrl_research_experiment_receipt_v1 import (
    ResearchExperimentReceiptError,
    _require_overrun_classification,
)


def test_matching_primary_classification_allows_multiple_observed_overruns() -> None:
    accounting_overruns = (PlanFailureCondition.ADAPTIVE_QUERY_BUDGET_OVERRUN,)
    resource_overrun = ("wall_clock_seconds",)

    _require_overrun_classification(
        failure=PlanFailureCondition.RESOURCE_BUDGET_OVERRUN,
        resource_overrun=resource_overrun,
        accounting_overruns=accounting_overruns,
    )
    _require_overrun_classification(
        failure=PlanFailureCondition.ADAPTIVE_QUERY_BUDGET_OVERRUN,
        resource_overrun=resource_overrun,
        accounting_overruns=accounting_overruns,
    )


def test_unrelated_primary_classification_rejects_multiple_observed_overruns() -> None:
    with pytest.raises(
        ResearchExperimentReceiptError,
        match="matching failure classification",
    ):
        _require_overrun_classification(
            failure=PlanFailureCondition.MUTATION_SCOPE_VIOLATION,
            resource_overrun=("wall_clock_seconds",),
            accounting_overruns=(PlanFailureCondition.ADAPTIVE_QUERY_BUDGET_OVERRUN,),
        )
