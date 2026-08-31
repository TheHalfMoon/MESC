"""Deterministic fixture-only researcher comparison report for MRL-0510.

This module compares the four MRL-0506..0509 context-bound researcher benchmark arms.
All quantitative observations are derived from MRL-0505 benchmark metrics. Metrics that
the fixture contract does not represent are reported explicitly as unavailable rather
than replaced with invented proxies.

The report is deterministic, content-addressed, and non-authoritative. It grants no real
model/data/network/GPU/training/promotion/deployment/release or clinical authority.
"""

from __future__ import annotations

import enum
import weakref
from collections.abc import Callable
from dataclasses import dataclass

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_researcher_arm_context_v1 import (
    ResearcherArmContext,
    ResearcherArmContextError,
)
from medscale.mesc._mrl_researcher_benchmark_v1 import ResearcherBenchmarkArm

__all__ = [
    "ResearcherComparisonReport",
    "ResearcherComparisonReportError",
    "ResearcherMetricDirection",
    "ResearcherMetricObservation",
    "build_researcher_comparison_report",
]


class ResearcherComparisonReportError(ValueError):
    """Fail-closed validation error for the MRL-0510 comparison report."""


class ResearcherMetricDirection(enum.Enum):
    """Optimization direction used only for fixture Pareto comparison."""

    MINIMIZE = "MINIMIZE"
    MAXIMIZE = "MAXIMIZE"


_REQUIRED_ARM_ORDER = (
    ResearcherBenchmarkArm.STATELESS,
    ResearcherBenchmarkArm.HISTORY_ONLY,
    ResearcherBenchmarkArm.ADMITTED_PROCEDURE_MEMORY,
    ResearcherBenchmarkArm.PORTFOLIO_TREE_SEARCH,
)

_METRIC_ORDER = (
    "validated_gain_per_compute_unit",
    "experiments_to_first_replicated_gain",
    "invalid_experiment_rate",
    "false_evidence_candidate_rate",
    "repeated_known_failure_rate",
    "hypothesis_diversity",
    "procedure_transfer_success_rate",
    "human_correction_count",
    "reproducibility_failure_rate",
    "wasted_compute_on_known_failures",
)


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
            raise ResearcherComparisonReportError("comparison identity already exists")
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: object, label: str) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ResearcherComparisonReportError(f"{label} construction identity is missing")
        return identity

    return store, load


_store_identity, _load_identity = _make_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ResearcherMetricObservation:
    """One exact rational metric observation or an explicit unavailable marker."""

    metric: str
    direction: ResearcherMetricDirection
    numerator: int | None
    denominator: int | None
    unavailable_reason: str | None = None

    def __post_init__(self) -> None:
        _validate_observation(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    @property
    def available(self) -> bool:
        return self.numerator is not None

    def _validated_snapshot(self) -> ResearcherMetricObservation:
        if type(self) is not ResearcherMetricObservation:
            raise ResearcherComparisonReportError(
                "observation must be an exact ResearcherMetricObservation"
            )
        bound = _load_identity(self, "researcher metric observation")
        _validate_observation(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise ResearcherComparisonReportError(
                "researcher metric observation changed after construction"
            )
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "metric": self.metric,
            "direction": self.direction.value,
            "availability": (
                "AVAILABLE" if self.numerator is not None else "NOT_AVAILABLE_FROM_FIXTURE_CONTRACT"
            ),
            "numerator": self.numerator,
            "denominator": self.denominator,
            "unavailable_reason": self.unavailable_reason,
        }

    def semantic_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ResearcherComparisonReport:
    """Deterministic four-arm MRL-0510 fixture comparison."""

    contexts: tuple[ResearcherArmContext, ...]
    fixture_only: bool = True
    non_evidence: bool = True

    def __post_init__(self) -> None:
        _validate_report(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_semantic_dict(self) -> dict[str, object]:
        if type(self) is not ResearcherComparisonReport:
            raise ResearcherComparisonReportError(
                "report must be an exact ResearcherComparisonReport"
            )
        bound = _load_identity(self, "researcher comparison report")
        _validate_report(self)
        data = self._semantic_dict_validated()
        current = derive_content_sha256(data)
        if current != bound:
            raise ResearcherComparisonReportError(
                "researcher comparison report changed after construction"
            )
        return data

    def _validated_snapshot(self) -> ResearcherComparisonReport:
        self._validated_semantic_dict()
        return self

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self._validated_semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_semantic_bytes(self._validated_semantic_dict())

    @property
    def pareto_frontier_arms(self) -> tuple[ResearcherBenchmarkArm, ...]:
        report = self._validated_snapshot()
        observations = _observations_by_arm(report.contexts)
        universal_metrics = _universally_available_metric_names(observations)
        result: list[ResearcherBenchmarkArm] = []
        for candidate in _REQUIRED_ARM_ORDER:
            if not any(
                other is not candidate
                and _dominates(
                    observations[other],
                    observations[candidate],
                    universal_metrics,
                )
                for other in _REQUIRED_ARM_ORDER
            ):
                result.append(candidate)
        return tuple(result)

    def _semantic_dict_validated(self) -> dict[str, object]:
        contexts = tuple(_validated_context(item) for item in self.contexts)
        observations = _observations_by_arm(contexts)
        universal_metrics = _universally_available_metric_names(observations)
        pareto = _pareto_frontier_from_observations(observations, universal_metrics)
        first_run = contexts[0].benchmark_run._validated_snapshot()
        return {
            "format": "MRL-RESEARCHER-COMPARISON-REPORT-V1",
            "campaign_id": first_run.campaign.campaign_id,
            "objective_sha256": first_run.campaign.objective_sha256,
            "arm_context_sha256s": {
                context.benchmark_run.arm.value: context.content_sha256 for context in contexts
            },
            "metrics": {
                arm.value: [
                    observation._semantic_dict_validated() for observation in observations[arm]
                ]
                for arm in _REQUIRED_ARM_ORDER
            },
            "pareto_metric_names": list(universal_metrics),
            "pareto_frontier_arms": [arm.value for arm in pareto],
            "fixture_only": self.fixture_only,
            "non_evidence": self.non_evidence,
            "can_execute_agent": False,
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        return self._validated_semantic_dict()

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data

    def render_markdown(self) -> str:
        """Render a deterministic human-readable fixture comparison report."""
        semantic = self._validated_semantic_dict()
        observations = _observations_by_arm(self.contexts)
        universal_metrics = _universally_available_metric_names(observations)
        pareto = _pareto_frontier_from_observations(observations, universal_metrics)
        first_run = self.contexts[0].benchmark_run._validated_snapshot()
        report_sha256 = derive_content_sha256(semantic)

        lines = [
            "# MRL Researcher Comparison Report V1",
            "",
            f"- Campaign: `{first_run.campaign.campaign_id}`",
            f"- Objective SHA-256: `{first_run.campaign.objective_sha256}`",
            f"- Report SHA-256: `{report_sha256}`",
            "- Scope: deterministic fixture-only benchmark evidence",
            (
                "- Authority: non-authoritative; no real execution, training, promotion, "
                "deployment, release, or clinical authority"
            ),
            "",
            "## Metrics",
            "",
            "| Metric | Stateless | History only | Procedure memory | Portfolio/tree search |",
            "| --- | --- | --- | --- | --- |",
        ]
        for metric in _METRIC_ORDER:
            row = [metric]
            for arm in _REQUIRED_ARM_ORDER:
                observation = _observation_by_name(observations[arm], metric)
                row.append(_format_observation(observation))
            lines.append("| " + " | ".join(row) + " |")

        lines.extend(
            [
                "",
                "## Pareto comparison",
                "",
                "Only metrics available for all four fixture arms participate in Pareto dominance.",
                "Unavailable contract dimensions are never replaced with inferred proxies.",
                "",
                (
                    "- Comparable metrics: "
                    + (", ".join(universal_metrics) if universal_metrics else "none")
                ),
                "- Pareto frontier: " + ", ".join(f"`{arm.value}`" for arm in pareto),
                "",
                "## Interpretation boundary",
                "",
                (
                    "This report compares deterministic fixture artifacts. It does not prove "
                    "hidden agent cognition, real-world scientific efficacy, model promotion, "
                    "training readiness, or clinical suitability."
                ),
                "",
            ]
        )
        return "\n".join(lines)

    @property
    def can_execute_agent(self) -> bool:
        return False

    @property
    def can_authorize_real_execution(self) -> bool:
        return False

    @property
    def can_authorize_training(self) -> bool:
        return False

    @property
    def can_authorize_promotion(self) -> bool:
        return False


def build_researcher_comparison_report(
    contexts: tuple[ResearcherArmContext, ...],
) -> ResearcherComparisonReport:
    """Build the deterministic MRL-0510 four-arm fixture comparison."""
    return ResearcherComparisonReport(contexts=_canonicalize_contexts(contexts))


def _validate_report(report: ResearcherComparisonReport) -> None:
    if type(report.fixture_only) is not bool or report.fixture_only is not True:
        raise ResearcherComparisonReportError("fixture_only must be exact True")
    if type(report.non_evidence) is not bool or report.non_evidence is not True:
        raise ResearcherComparisonReportError("non_evidence must be exact True")
    contexts = _canonicalize_contexts(report.contexts)
    if report.contexts != contexts:
        raise ResearcherComparisonReportError("contexts must use canonical researcher-arm order")

    campaign_ids = {
        context.benchmark_run._validated_snapshot().campaign.campaign_id for context in contexts
    }
    objectives = {
        context.benchmark_run._validated_snapshot().campaign.objective_sha256
        for context in contexts
    }
    if len(campaign_ids) != 1:
        raise ResearcherComparisonReportError(
            "all researcher arms must share one campaign namespace"
        )
    if len(objectives) != 1:
        raise ResearcherComparisonReportError("all researcher arms must share one frozen objective")


def _canonicalize_contexts(
    contexts: tuple[ResearcherArmContext, ...],
) -> tuple[ResearcherArmContext, ...]:
    if type(contexts) is not tuple:
        raise ResearcherComparisonReportError("contexts must be an exact tuple")
    snapshots = tuple(_validated_context(item) for item in contexts)
    by_arm: dict[ResearcherBenchmarkArm, ResearcherArmContext] = {}
    for context in snapshots:
        arm = context.benchmark_run._validated_snapshot().arm
        if arm in by_arm:
            raise ResearcherComparisonReportError(f"duplicate researcher arm context: {arm.value}")
        by_arm[arm] = context
    if set(by_arm) != set(_REQUIRED_ARM_ORDER):
        raise ResearcherComparisonReportError(
            "comparison requires exactly one context for each required researcher arm"
        )
    return tuple(by_arm[arm] for arm in _REQUIRED_ARM_ORDER)


def _validated_context(context: ResearcherArmContext) -> ResearcherArmContext:
    if type(context) is not ResearcherArmContext:
        raise ResearcherComparisonReportError("context has an invalid type")
    try:
        return context._validated_snapshot()
    except ResearcherArmContextError as exc:
        raise ResearcherComparisonReportError(
            "researcher arm context failed canonical revalidation"
        ) from exc


def _observations_by_arm(
    contexts: tuple[ResearcherArmContext, ...],
) -> dict[ResearcherBenchmarkArm, tuple[ResearcherMetricObservation, ...]]:
    return {context.benchmark_run.arm: _derive_observations(context) for context in contexts}


def _derive_observations(
    context: ResearcherArmContext,
) -> tuple[ResearcherMetricObservation, ...]:
    run = context.benchmark_run._validated_snapshot()
    metrics = run.metrics._validated_snapshot()
    experiment_count = metrics.experiment_count

    return (
        _available_or_unavailable_ratio(
            "validated_gain_per_compute_unit",
            ResearcherMetricDirection.MAXIMIZE,
            metrics.validated_replicated_gain_count,
            metrics.compute_unit_count,
            "compute_unit_count is zero",
        ),
        (
            _unavailable(
                "experiments_to_first_replicated_gain",
                ResearcherMetricDirection.MINIMIZE,
                "no validated replicated gain exists in this fixture trajectory",
            )
            if metrics.experiments_to_first_replicated_gain is None
            else _available(
                "experiments_to_first_replicated_gain",
                ResearcherMetricDirection.MINIMIZE,
                metrics.experiments_to_first_replicated_gain,
                1,
            )
        ),
        _available_or_unavailable_ratio(
            "invalid_experiment_rate",
            ResearcherMetricDirection.MINIMIZE,
            metrics.invalid_outcome_count,
            experiment_count,
            "experiment_count is zero",
        ),
        _unavailable(
            "false_evidence_candidate_rate",
            ResearcherMetricDirection.MINIMIZE,
            "MRL-0505 fixture metrics do not encode false-evidence-candidate count",
        ),
        _available_or_unavailable_ratio(
            "repeated_known_failure_rate",
            ResearcherMetricDirection.MINIMIZE,
            metrics.repeated_known_failure_count,
            experiment_count,
            "experiment_count is zero",
        ),
        _available_or_unavailable_ratio(
            "hypothesis_diversity",
            ResearcherMetricDirection.MAXIMIZE,
            metrics.frontier_hypothesis_root_count,
            metrics.hypothesis_count,
            "hypothesis_count is zero",
        ),
        _available_or_unavailable_ratio(
            "procedure_transfer_success_rate",
            ResearcherMetricDirection.MAXIMIZE,
            metrics.procedure_transfer_success_count,
            metrics.procedure_transfer_attempt_count,
            "procedure_transfer_attempt_count is zero",
        ),
        _unavailable(
            "human_correction_count",
            ResearcherMetricDirection.MINIMIZE,
            "MRL-0505 fixture metrics do not encode human correction count",
        ),
        _available_or_unavailable_ratio(
            "reproducibility_failure_rate",
            ResearcherMetricDirection.MINIMIZE,
            metrics.replication_count - metrics.validated_replicated_gain_count,
            metrics.replication_count,
            "replication_count is zero",
        ),
        _unavailable(
            "wasted_compute_on_known_failures",
            ResearcherMetricDirection.MINIMIZE,
            "MRL-0505 does not attribute compute units to individual known-failure retries",
        ),
    )


def _available(
    metric: str,
    direction: ResearcherMetricDirection,
    numerator: int,
    denominator: int,
) -> ResearcherMetricObservation:
    return ResearcherMetricObservation(
        metric=metric,
        direction=direction,
        numerator=numerator,
        denominator=denominator,
    )


def _unavailable(
    metric: str,
    direction: ResearcherMetricDirection,
    reason: str,
) -> ResearcherMetricObservation:
    return ResearcherMetricObservation(
        metric=metric,
        direction=direction,
        numerator=None,
        denominator=None,
        unavailable_reason=reason,
    )


def _available_or_unavailable_ratio(
    metric: str,
    direction: ResearcherMetricDirection,
    numerator: int,
    denominator: int,
    reason: str,
) -> ResearcherMetricObservation:
    if denominator == 0:
        return _unavailable(metric, direction, reason)
    return _available(metric, direction, numerator, denominator)


def _validate_observation(observation: ResearcherMetricObservation) -> None:
    if type(observation.metric) is not str or observation.metric not in _METRIC_ORDER:
        raise ResearcherComparisonReportError("metric must be a canonical comparison metric")
    if type(observation.direction) is not ResearcherMetricDirection:
        raise ResearcherComparisonReportError(
            "direction must be an exact ResearcherMetricDirection"
        )
    available = observation.numerator is not None
    if available:
        if type(observation.numerator) is not int or observation.numerator < 0:
            raise ResearcherComparisonReportError(
                "available metric numerator must be a non-negative exact int"
            )
        if type(observation.denominator) is not int or observation.denominator <= 0:
            raise ResearcherComparisonReportError(
                "available metric denominator must be a positive exact int"
            )
        if observation.unavailable_reason is not None:
            raise ResearcherComparisonReportError(
                "available metric cannot declare unavailable_reason"
            )
        return
    if observation.denominator is not None:
        raise ResearcherComparisonReportError("unavailable metric denominator must be None")
    if (
        type(observation.unavailable_reason) is not str
        or not observation.unavailable_reason
        or observation.unavailable_reason.strip() != observation.unavailable_reason
        or "\n" in observation.unavailable_reason
        or "\r" in observation.unavailable_reason
    ):
        raise ResearcherComparisonReportError(
            "unavailable metric requires canonical one-line reason"
        )


def _universally_available_metric_names(
    observations: dict[
        ResearcherBenchmarkArm,
        tuple[ResearcherMetricObservation, ...],
    ],
) -> tuple[str, ...]:
    result: list[str] = []
    for metric in _METRIC_ORDER:
        values = tuple(
            _observation_by_name(observations[arm], metric) for arm in _REQUIRED_ARM_ORDER
        )
        if all(value.available for value in values):
            result.append(metric)
    return tuple(result)


def _pareto_frontier_from_observations(
    observations: dict[
        ResearcherBenchmarkArm,
        tuple[ResearcherMetricObservation, ...],
    ],
    universal_metrics: tuple[str, ...],
) -> tuple[ResearcherBenchmarkArm, ...]:
    result: list[ResearcherBenchmarkArm] = []
    for candidate in _REQUIRED_ARM_ORDER:
        if not any(
            other is not candidate
            and _dominates(
                observations[other],
                observations[candidate],
                universal_metrics,
            )
            for other in _REQUIRED_ARM_ORDER
        ):
            result.append(candidate)
    return tuple(result)


def _dominates(
    first: tuple[ResearcherMetricObservation, ...],
    second: tuple[ResearcherMetricObservation, ...],
    metric_names: tuple[str, ...],
) -> bool:
    if not metric_names:
        return False
    strictly_better = False
    for metric in metric_names:
        left = _observation_by_name(first, metric)
        right = _observation_by_name(second, metric)
        comparison = _compare_available(left, right)
        if comparison < 0:
            return False
        if comparison > 0:
            strictly_better = True
    return strictly_better


def _compare_available(
    first: ResearcherMetricObservation,
    second: ResearcherMetricObservation,
) -> int:
    first_snapshot = first._validated_snapshot()
    second_snapshot = second._validated_snapshot()
    if first_snapshot.metric != second_snapshot.metric:
        raise ResearcherComparisonReportError("cannot compare different researcher metrics")
    if first_snapshot.direction is not second_snapshot.direction:
        raise ResearcherComparisonReportError("metric direction mismatch across researcher arms")
    if not first_snapshot.available or not second_snapshot.available:
        raise ResearcherComparisonReportError("Pareto comparison requires available metric values")
    assert first_snapshot.numerator is not None
    assert first_snapshot.denominator is not None
    assert second_snapshot.numerator is not None
    assert second_snapshot.denominator is not None
    left = first_snapshot.numerator * second_snapshot.denominator
    right = second_snapshot.numerator * first_snapshot.denominator
    if left == right:
        return 0
    raw = 1 if left > right else -1
    if first_snapshot.direction is ResearcherMetricDirection.MAXIMIZE:
        return raw
    return -raw


def _observation_by_name(
    observations: tuple[ResearcherMetricObservation, ...],
    metric: str,
) -> ResearcherMetricObservation:
    matches = tuple(item for item in observations if item.metric == metric)
    if len(matches) != 1:
        raise ResearcherComparisonReportError(f"metric observation missing or duplicated: {metric}")
    return matches[0]._validated_snapshot()


def _format_observation(observation: ResearcherMetricObservation) -> str:
    snapshot = observation._validated_snapshot()
    if not snapshot.available:
        return "N/A"
    assert snapshot.numerator is not None
    assert snapshot.denominator is not None
    if snapshot.denominator == 1:
        return str(snapshot.numerator)
    return f"{snapshot.numerator}/{snapshot.denominator}"
