"""MRL-0409 tests for deterministic memory-vs-no-memory fixture research cost."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_procedure_memory_cost_comparison_v1 import (
    ProcedureMemoryCostComparisonError,
    compare_procedure_memory_fixture_cost,
)
from medscale.mesc._mrl_procedure_registry_v1 import (
    ProcedureRegistry,
    register_procedure_admission,
)
from medscale.mesc._mrl_procedure_search_index_v1 import build_procedure_search_index
from medscale.mesc._mrl_research_decision_v1 import ResearchDecisionState
from test_mesc_mrl_fixture_loop_v1 import _complete
from test_mesc_mrl_procedure_registry_v1 import _gate_result
from test_mesc_mrl_procedure_search_index_v1 import (
    _admission_for_result,
    _allow_index_fixture_admission,
)


def _memory_index(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    _allow_index_fixture_admission(monkeypatch)
    result = _gate_result("memory-cost")
    registry = register_procedure_admission(ProcedureRegistry(), result)
    admission = _admission_for_result("memory-cost", result)
    index = build_procedure_search_index(registry, (admission,))
    procedure = result.admitted_procedure
    assert procedure is not None
    query = procedure.applicability_bounds.task_types[0]
    return index, query, result.procedure_sha256


def _passing_comparison(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    index, query, procedure_sha256 = _memory_index(monkeypatch)
    no_memory_results = (
        _complete(alpha=0, beta=0),
        _complete(alpha=1, beta=0),
        _complete(),
    )
    memory_results = (_complete(),)
    return compare_procedure_memory_fixture_cost(
        no_memory_results,
        memory_results,
        index,
        search_query=query,
        selected_procedure_sha256=procedure_sha256,
    )


def test_memory_comparison_is_deterministic_and_proves_strict_cost_gain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _passing_comparison(monkeypatch)
    second = _passing_comparison(monkeypatch)

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.no_memory_cost.experiment_count == 3
    assert first.memory_cost.experiment_count == 1
    assert first.no_memory_cost.operation_count == 3
    assert first.memory_cost.operation_count == 1
    assert first.no_memory_cost.evaluator_invocations == 3
    assert first.memory_cost.evaluator_invocations == 1
    assert first.no_memory_cost.storage_bytes == 192
    assert first.memory_cost.storage_bytes == 64
    assert first.memory_cost.invalid_experiment_count == 0
    assert first.memory_cost.false_evidence_candidate_count == 0
    assert first.no_memory_results[-1].content_sha256 == first.memory_results[-1].content_sha256
    payload = first.semantic_dict()
    assert payload["same_final_fixture_result"] is True
    assert payload["strict_cost_improvement"] is True
    assert payload["invalid_behavior_non_regression"] is True
    assert payload["false_evidence_candidate_non_regression"] is True
    assert payload["fixture_only"] is True
    assert payload["non_evidence"] is True
    assert first.can_admit_procedure is False
    assert first.can_authorize_real_execution is False
    assert first.can_authorize_training is False
    assert first.can_authorize_model_promotion is False


def test_comparison_requires_a_strict_cost_improvement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index, query, procedure_sha256 = _memory_index(monkeypatch)
    result = _complete()

    with pytest.raises(ProcedureMemoryCostComparisonError, match="strictly reduce"):
        compare_procedure_memory_fixture_cost(
            (result,),
            (result,),
            index,
            search_query=query,
            selected_procedure_sha256=procedure_sha256,
        )


def test_comparison_requires_same_final_fixture_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index, query, procedure_sha256 = _memory_index(monkeypatch)

    with pytest.raises(ProcedureMemoryCostComparisonError, match="same final fixture result"):
        compare_procedure_memory_fixture_cost(
            (_complete(alpha=0, beta=0), _complete()),
            (_complete(alpha=1, beta=0),),
            index,
            search_query=query,
            selected_procedure_sha256=procedure_sha256,
        )


def test_comparison_rejects_increased_false_evidence_candidate_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index, query, procedure_sha256 = _memory_index(monkeypatch)
    rejected = _complete(alpha=1, beta=0)
    forged_decision = replace(
        rejected.decision,
        state=ResearchDecisionState.EVIDENCE_CANDIDATE,
        reason="Fixture-only adversarial false evidence candidate.",
    )
    forged = replace(rejected, decision=forged_decision)
    final = _complete()

    with pytest.raises(ProcedureMemoryCostComparisonError, match="false evidence-candidate"):
        compare_procedure_memory_fixture_cost(
            (_complete(alpha=0, beta=0), rejected, final),
            (forged, final),
            index,
            search_query=query,
            selected_procedure_sha256=procedure_sha256,
        )


def test_selected_procedure_must_be_returned_by_exact_memory_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index, query, _ = _memory_index(monkeypatch)

    with pytest.raises(ProcedureMemoryCostComparisonError, match="not returned"):
        compare_procedure_memory_fixture_cost(
            (_complete(alpha=0, beta=0), _complete()),
            (_complete(),),
            index,
            search_query=query,
            selected_procedure_sha256="f" * 64,
        )


def test_result_trajectory_cannot_mix_fixture_plans_or_surfaces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _passing_comparison(monkeypatch)
    mutated = comparison.no_memory_results[0]
    object.__setattr__(
        mutated.proposal,
        "experiment_plan_sha256",
        "f" * 64,
    )

    with pytest.raises(ProcedureMemoryCostComparisonError):
        _ = comparison.content_sha256


def test_search_index_mutation_invalidates_existing_comparison(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _passing_comparison(monkeypatch)
    object.__setattr__(
        comparison.procedure_search_index.entries[0],
        "procedure_sha256",
        "e" * 64,
    )

    with pytest.raises(ProcedureMemoryCostComparisonError, match="search index failed"):
        _ = comparison.semantic_dict()


def test_caller_cannot_replace_derived_cost_with_smaller_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    comparison = _passing_comparison(monkeypatch)
    object.__setattr__(comparison.no_memory_cost, "experiment_count", 1)

    with pytest.raises(ProcedureMemoryCostComparisonError):
        _ = comparison.content_sha256
