"""Deterministic fixture-only procedure-memory cost comparison for MRL-0409.

The comparison binds exact completed fixture-loop results for a no-memory arm and an
admitted-procedure-memory arm. Cost and safety counters are derived from those canonical
results rather than accepted from callers. A passing comparison requires the memory arm
to reach the exact same final fixture result with no greater invalid or false-evidence-
candidate behavior and with a strict reduction in at least one bounded research-cost
measure.

This artifact is fixture-only and non-authoritative. It grants no procedure admission,
model, data, network, GPU, training, promotion, deployment, release, or clinical
authority.
"""

from __future__ import annotations

import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_fixture_loop_v1 import FixtureLoopError, FixtureLoopResult
from medscale.mesc._mrl_procedure_search_index_v1 import (
    ProcedureSearchIndex,
    ProcedureSearchIndexError,
)
from medscale.mesc._mrl_research_decision_v1 import ResearchDecisionState
from medscale.mesc._mrl_structured_fixture_observation_v1 import FixtureObservationRunStatus

__all__ = [
    "ProcedureMemoryCostComparison",
    "ProcedureMemoryCostComparisonError",
    "ProcedureMemoryResearchCost",
    "compare_procedure_memory_fixture_cost",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)


class ProcedureMemoryCostComparisonError(ValueError):
    """Fail-closed validation error for MRL-0409 fixture cost comparison."""


def _make_identity_registry() -> tuple[
    Callable[[object, str], None],
    Callable[[object, str], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: object, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ProcedureMemoryCostComparisonError(
                "procedure-memory comparison construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: object, label: str) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ProcedureMemoryCostComparisonError(f"{label} construction identity is missing")
        return identity

    return store, load


_store_identity, _load_identity = _make_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureMemoryResearchCost:
    """Cost and safety counters derived from one exact fixture-result sequence."""

    result_sha256s: tuple[str, ...]
    experiment_count: int
    operation_count: int
    evaluator_invocations: int
    storage_bytes: int
    invalid_experiment_count: int
    evidence_candidate_count: int
    false_evidence_candidate_count: int

    def __post_init__(self) -> None:
        _validate_cost(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> ProcedureMemoryResearchCost:
        if type(self) is not ProcedureMemoryResearchCost:
            raise ProcedureMemoryCostComparisonError(
                "cost must be an exact ProcedureMemoryResearchCost"
            )
        bound = _load_identity(self, "procedure-memory research cost")
        _require_sha256(bound, "bound cost content_sha256")
        _validate_cost(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise ProcedureMemoryCostComparisonError(
                "procedure-memory research cost changed after construction"
            )
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-PROCEDURE-MEMORY-RESEARCH-COST-V1",
            "result_sha256s": list(self.result_sha256s),
            "experiment_count": self.experiment_count,
            "operation_count": self.operation_count,
            "evaluator_invocations": self.evaluator_invocations,
            "storage_bytes": self.storage_bytes,
            "invalid_experiment_count": self.invalid_experiment_count,
            "evidence_candidate_count": self.evidence_candidate_count,
            "false_evidence_candidate_count": self.false_evidence_candidate_count,
            "fixture_only": True,
            "non_evidence": True,
        }

    def semantic_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureMemoryCostComparison:
    """Construction-bound evidence that procedure memory reduced fixture research cost."""

    no_memory_results: tuple[FixtureLoopResult, ...]
    memory_results: tuple[FixtureLoopResult, ...]
    procedure_search_index: ProcedureSearchIndex
    search_query: str
    selected_procedure_sha256: str
    no_memory_cost: ProcedureMemoryResearchCost
    memory_cost: ProcedureMemoryResearchCost
    fixture_only: bool = True
    non_evidence: bool = True

    def __post_init__(self) -> None:
        _validate_comparison(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> ProcedureMemoryCostComparison:
        if type(self) is not ProcedureMemoryCostComparison:
            raise ProcedureMemoryCostComparisonError(
                "comparison must be an exact ProcedureMemoryCostComparison"
            )
        bound = _load_identity(self, "procedure-memory cost comparison")
        _require_sha256(bound, "bound comparison content_sha256")
        _validate_comparison(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise ProcedureMemoryCostComparisonError(
                "procedure-memory cost comparison changed after construction"
            )
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        index = _validated_index(self.procedure_search_index)
        no_memory = self.no_memory_cost._validated_snapshot()
        memory = self.memory_cost._validated_snapshot()
        return {
            "format": "MRL-PROCEDURE-MEMORY-COST-COMPARISON-V1",
            "no_memory_result_sha256s": [item.content_sha256 for item in self.no_memory_results],
            "memory_result_sha256s": [item.content_sha256 for item in self.memory_results],
            "procedure_search_index_sha256": index.content_sha256,
            "search_query": self.search_query,
            "selected_procedure_sha256": self.selected_procedure_sha256,
            "no_memory_cost_sha256": no_memory.content_sha256,
            "memory_cost_sha256": memory.content_sha256,
            "same_final_fixture_result": True,
            "strict_cost_improvement": True,
            "invalid_behavior_non_regression": True,
            "false_evidence_candidate_non_regression": True,
            "fixture_only": self.fixture_only,
            "non_evidence": self.non_evidence,
            "can_admit_procedure": False,
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data

    @property
    def can_admit_procedure(self) -> bool:
        return False

    @property
    def can_authorize_real_execution(self) -> bool:
        return False

    @property
    def can_authorize_training(self) -> bool:
        return False

    @property
    def can_authorize_model_promotion(self) -> bool:
        return False


def compare_procedure_memory_fixture_cost(
    no_memory_results: tuple[FixtureLoopResult, ...],
    memory_results: tuple[FixtureLoopResult, ...],
    procedure_search_index: ProcedureSearchIndex,
    *,
    search_query: str,
    selected_procedure_sha256: str,
) -> ProcedureMemoryCostComparison:
    """Compare two exact fixture trajectories and require a safe strict memory cost gain."""
    no_memory_snapshots = _validated_results(no_memory_results, "no_memory_results")
    memory_snapshots = _validated_results(memory_results, "memory_results")
    index = _validated_index(procedure_search_index)
    _require_text(search_query, "search_query")
    _require_sha256(selected_procedure_sha256, "selected_procedure_sha256")

    matches = index.search(search_query)
    if selected_procedure_sha256 not in {item.procedure_sha256 for item in matches}:
        raise ProcedureMemoryCostComparisonError(
            "selected procedure is not returned by the exact procedure-memory search query"
        )

    no_memory_cost = _derive_cost(no_memory_snapshots)
    memory_cost = _derive_cost(memory_snapshots)
    comparison = ProcedureMemoryCostComparison(
        no_memory_results=no_memory_results,
        memory_results=memory_results,
        procedure_search_index=procedure_search_index,
        search_query=search_query,
        selected_procedure_sha256=selected_procedure_sha256,
        no_memory_cost=no_memory_cost,
        memory_cost=memory_cost,
    )
    return comparison


def _derive_cost(results: tuple[FixtureLoopResult, ...]) -> ProcedureMemoryResearchCost:
    snapshots = _validated_results(results, "results")
    return ProcedureMemoryResearchCost(
        result_sha256s=tuple(item.content_sha256 for item in snapshots),
        experiment_count=len(snapshots),
        operation_count=sum(item.observation.resource_use.operation_count for item in snapshots),
        evaluator_invocations=sum(
            item.observation.resource_use.evaluator_invocations for item in snapshots
        ),
        storage_bytes=sum(item.observation.resource_use.storage_bytes for item in snapshots),
        invalid_experiment_count=sum(
            item.decision.state is ResearchDecisionState.INVALID for item in snapshots
        ),
        evidence_candidate_count=sum(
            item.decision.state is ResearchDecisionState.EVIDENCE_CANDIDATE for item in snapshots
        ),
        false_evidence_candidate_count=sum(
            _is_false_evidence_candidate(item) for item in snapshots
        ),
    )


def _is_false_evidence_candidate(result: FixtureLoopResult) -> bool:
    if result.decision.state is not ResearchDecisionState.EVIDENCE_CANDIDATE:
        return False
    observation = result.observation
    if observation.run_status is not FixtureObservationRunStatus.SUCCEEDED:
        return True
    evaluation = observation.evaluation
    if evaluation is None or evaluation.score != evaluation.max_score:
        return True
    guardrails = result.receipt.guardrail_results
    return not guardrails or not all(item.passed for item in guardrails)


def _validate_comparison(comparison: ProcedureMemoryCostComparison) -> None:
    no_memory = _validated_results(comparison.no_memory_results, "no_memory_results")
    memory = _validated_results(comparison.memory_results, "memory_results")
    index = _validated_index(comparison.procedure_search_index)
    _require_text(comparison.search_query, "search_query")
    _require_sha256(comparison.selected_procedure_sha256, "selected_procedure_sha256")
    if type(comparison.fixture_only) is not bool or comparison.fixture_only is not True:
        raise ProcedureMemoryCostComparisonError("fixture_only must be exact True")
    if type(comparison.non_evidence) is not bool or comparison.non_evidence is not True:
        raise ProcedureMemoryCostComparisonError("non_evidence must be exact True")

    matches = index.search(comparison.search_query)
    if comparison.selected_procedure_sha256 not in {
        item.procedure_sha256 for item in matches
    }:
        raise ProcedureMemoryCostComparisonError(
            "selected procedure is not returned by the exact procedure-memory search query"
        )

    expected_no_memory = _derive_cost(no_memory)
    expected_memory = _derive_cost(memory)
    if comparison.no_memory_cost.semantic_dict() != expected_no_memory.semantic_dict():
        raise ProcedureMemoryCostComparisonError(
            "no-memory cost does not match the exact fixture results"
        )
    if comparison.memory_cost.semantic_dict() != expected_memory.semantic_dict():
        raise ProcedureMemoryCostComparisonError(
            "memory cost does not match the exact fixture results"
        )

    if no_memory[-1].content_sha256 != memory[-1].content_sha256:
        raise ProcedureMemoryCostComparisonError(
            "memory and no-memory arms must reach the exact same final fixture result"
        )
    if no_memory[-1].decision.state is not ResearchDecisionState.EVIDENCE_CANDIDATE:
        raise ProcedureMemoryCostComparisonError(
            "comparison must terminate at an exact fixture evidence candidate"
        )

    no_cost = comparison.no_memory_cost
    memory_cost = comparison.memory_cost
    cost_pairs = (
        (memory_cost.experiment_count, no_cost.experiment_count),
        (memory_cost.operation_count, no_cost.operation_count),
        (memory_cost.evaluator_invocations, no_cost.evaluator_invocations),
        (memory_cost.storage_bytes, no_cost.storage_bytes),
    )
    if any(memory_value > no_memory_value for memory_value, no_memory_value in cost_pairs):
        raise ProcedureMemoryCostComparisonError(
            "procedure memory cannot increase a bounded fixture research-cost measure"
        )
    if not any(memory_value < no_memory_value for memory_value, no_memory_value in cost_pairs):
        raise ProcedureMemoryCostComparisonError(
            "procedure memory must strictly reduce at least one fixture research-cost measure"
        )
    if memory_cost.invalid_experiment_count > no_cost.invalid_experiment_count:
        raise ProcedureMemoryCostComparisonError(
            "procedure memory cannot increase invalid experiment behavior"
        )
    if (
        memory_cost.false_evidence_candidate_count
        > no_cost.false_evidence_candidate_count
    ):
        raise ProcedureMemoryCostComparisonError(
            "procedure memory cannot increase false evidence-candidate behavior"
        )


def _validated_results(
    results: tuple[FixtureLoopResult, ...],
    label: str,
) -> tuple[FixtureLoopResult, ...]:
    if type(results) is not tuple:
        raise ProcedureMemoryCostComparisonError(f"{label} must be an exact tuple")
    if not results:
        raise ProcedureMemoryCostComparisonError(f"{label} cannot be empty")
    snapshots: list[FixtureLoopResult] = []
    for item in results:
        if type(item) is not FixtureLoopResult:
            raise ProcedureMemoryCostComparisonError(
                f"{label} must contain exact FixtureLoopResult values"
            )
        try:
            snapshots.append(item._validated_snapshot())
        except FixtureLoopError as exc:
            raise ProcedureMemoryCostComparisonError(
                f"{label} contains a fixture result that failed canonical revalidation"
            ) from exc
    plan_sha256s = {item.proposal.experiment_plan_sha256 for item in snapshots}
    surface_sha256s = {item.proposal.research_surface_sha256 for item in snapshots}
    if len(plan_sha256s) != 1 or len(surface_sha256s) != 1:
        raise ProcedureMemoryCostComparisonError(
            f"{label} must remain within one exact fixture plan and research surface"
        )
    return tuple(snapshots)


def _validated_index(index: ProcedureSearchIndex) -> ProcedureSearchIndex:
    if type(index) is not ProcedureSearchIndex:
        raise ProcedureMemoryCostComparisonError(
            "procedure_search_index must be an exact ProcedureSearchIndex"
        )
    try:
        return index._validated_snapshot()
    except ProcedureSearchIndexError as exc:
        raise ProcedureMemoryCostComparisonError(
            "procedure search index failed canonical revalidation"
        ) from exc


def _validate_cost(cost: ProcedureMemoryResearchCost) -> None:
    if type(cost.result_sha256s) is not tuple or not cost.result_sha256s:
        raise ProcedureMemoryCostComparisonError(
            "result_sha256s must be a non-empty exact tuple"
        )
    for value in cost.result_sha256s:
        _require_sha256(value, "result_sha256s")
    for label, value in (
        ("experiment_count", cost.experiment_count),
        ("operation_count", cost.operation_count),
        ("evaluator_invocations", cost.evaluator_invocations),
        ("storage_bytes", cost.storage_bytes),
        ("invalid_experiment_count", cost.invalid_experiment_count),
        ("evidence_candidate_count", cost.evidence_candidate_count),
        ("false_evidence_candidate_count", cost.false_evidence_candidate_count),
    ):
        if type(value) is not int or value < 0:
            raise ProcedureMemoryCostComparisonError(
                f"{label} must be an exact nonnegative integer"
            )
    if cost.experiment_count != len(cost.result_sha256s):
        raise ProcedureMemoryCostComparisonError(
            "experiment_count must equal the number of result identities"
        )
    if cost.false_evidence_candidate_count > cost.evidence_candidate_count:
        raise ProcedureMemoryCostComparisonError(
            "false evidence-candidate count cannot exceed evidence-candidate count"
        )


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ProcedureMemoryCostComparisonError(f"{label} must be 64 lowercase hex")


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise ProcedureMemoryCostComparisonError(f"{label} must be canonical non-empty text")
    if any(character in value for character in "\x00\r\n\t"):
        raise ProcedureMemoryCostComparisonError(f"{label} cannot contain control characters")
