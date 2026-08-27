"""Immutable, content-addressed MRL V1 research objective contract.

The objective freezes the scientific target, evaluator identities, hard evidence floors,
mutation envelope, resource ceilings, adaptive-query ceilings, and result-exposure policy
before campaign experiments begin. It is a declarative research artifact only: it grants
no model, data, network, GPU, inference, training, promotion, deployment, or clinical
authority.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)

__all__ = [
    "AdaptiveQueryBudget",
    "BudgetExhaustionDisposition",
    "EvaluationTier",
    "EvaluationTierPolicy",
    "EvaluatorIdentity",
    "EvidenceFloor",
    "FloorComparator",
    "MetricContract",
    "MetricDirection",
    "ResearchObjectiveContract",
    "ResearchObjectiveContractError",
    "ResourceBudget",
    "TierResultExposure",
]

_OBJECTIVE_ID: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TOKEN_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_RESEARCH_PROGRAM_REF: Final = re.compile(
    r"^(?:RQ[1-7]|(?:MESC|MCRL|ARABIC|AMGE|OMNI|MRL)-RQ-[0-9]{4})$"
)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_CANONICAL_DECIMAL: Final = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$")


class ResearchObjectiveContractError(ValueError):
    """Fail-closed validation error for MRL objective semantics."""


class MetricDirection(enum.Enum):
    MAXIMIZE = "MAXIMIZE"
    MINIMIZE = "MINIMIZE"


class FloorComparator(enum.Enum):
    GTE = "GTE"
    LTE = "LTE"


class BudgetExhaustionDisposition(enum.Enum):
    BLOCKED = "BLOCKED"


class EvaluationTier(enum.IntEnum):
    DEVELOPMENT = 0
    SEARCH = 1
    REPLICATION = 2
    SEALED = 3
    EXTERNAL_ASSURANCE = 4


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    """Externally frozen campaign resource ceilings.

    Integer units avoid floating-point accounting ambiguity. ``None`` means the resource
    is not applicable to this objective, not that consumption is unlimited.
    """

    wall_clock_seconds: int
    compute_seconds: int | None
    input_tokens: int | None
    generated_tokens: int | None
    storage_bytes: int
    monetary_cost_microunits: int | None
    retries: int
    known_failure_retries: int
    evaluator_invocations: int | None

    def __post_init__(self) -> None:
        _require_positive_int(self.wall_clock_seconds, "wall_clock_seconds")
        _require_optional_nonnegative_int(self.compute_seconds, "compute_seconds")
        _require_optional_nonnegative_int(self.input_tokens, "input_tokens")
        _require_optional_nonnegative_int(self.generated_tokens, "generated_tokens")
        _require_nonnegative_int(self.storage_bytes, "storage_bytes")
        _require_optional_nonnegative_int(self.monetary_cost_microunits, "monetary_cost_microunits")
        _require_nonnegative_int(self.retries, "retries")
        _require_nonnegative_int(self.known_failure_retries, "known_failure_retries")
        _require_optional_nonnegative_int(self.evaluator_invocations, "evaluator_invocations")
        if self.known_failure_retries > self.retries:
            raise ResearchObjectiveContractError("known_failure_retries cannot exceed retries")

    def to_dict(self) -> dict[str, object]:
        return {
            "wall_clock_seconds": self.wall_clock_seconds,
            "compute_seconds": self.compute_seconds,
            "input_tokens": self.input_tokens,
            "generated_tokens": self.generated_tokens,
            "storage_bytes": self.storage_bytes,
            "monetary_cost_microunits": self.monetary_cost_microunits,
            "retries": self.retries,
            "known_failure_retries": self.known_failure_retries,
            "evaluator_invocations": self.evaluator_invocations,
        }


@dataclass(frozen=True, slots=True)
class AdaptiveQueryBudget:
    """Frozen adaptive-query ceilings for the only adaptive feedback tiers."""

    tier_1_queries: int
    tier_2_queries: int

    def __post_init__(self) -> None:
        _require_nonnegative_int(self.tier_1_queries, "tier_1_queries")
        _require_nonnegative_int(self.tier_2_queries, "tier_2_queries")

    def to_dict(self) -> dict[str, int]:
        return {
            "tier_1_queries": self.tier_1_queries,
            "tier_2_queries": self.tier_2_queries,
        }


@dataclass(frozen=True, slots=True)
class EvaluationTierPolicy:
    """The exact evaluation tiers admitted by the frozen objective."""

    allowed_tiers: tuple[EvaluationTier, ...]

    def __post_init__(self) -> None:
        if not self.allowed_tiers:
            raise ResearchObjectiveContractError("evaluation_tier_policy cannot be empty")
        _require_exact_instances(self.allowed_tiers, EvaluationTier, "allowed_tiers")
        numeric = tuple(int(tier) for tier in self.allowed_tiers)
        if numeric != tuple(sorted(set(numeric))):
            raise ResearchObjectiveContractError(
                "evaluation tiers must be unique and strictly ascending"
            )

    def to_dict(self) -> dict[str, object]:
        return {"allowed_tiers": [int(tier) for tier in self.allowed_tiers]}


@dataclass(frozen=True, slots=True)
class EvaluatorIdentity:
    """Immutable identity of one evaluator artifact and the tiers it may judge."""

    evaluator_id: str
    artifact_sha256: str
    tiers: tuple[EvaluationTier, ...]

    def __post_init__(self) -> None:
        _require_token(self.evaluator_id, "evaluator_id")
        _require_sha256(self.artifact_sha256, "artifact_sha256")
        if not self.tiers:
            raise ResearchObjectiveContractError("evaluator tiers cannot be empty")
        _require_exact_instances(self.tiers, EvaluationTier, "evaluator tiers")
        numeric = tuple(int(tier) for tier in self.tiers)
        if numeric != tuple(sorted(set(numeric))):
            raise ResearchObjectiveContractError(
                "evaluator tiers must be unique and strictly ascending"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluator_id": self.evaluator_id,
            "artifact_sha256": self.artifact_sha256,
            "tiers": [int(tier) for tier in self.tiers],
        }


@dataclass(frozen=True, slots=True)
class MetricContract:
    """Metric identity bound to a frozen evaluator and optimization direction."""

    metric_id: str
    evaluator_id: str
    direction: MetricDirection

    def __post_init__(self) -> None:
        _require_token(self.metric_id, "metric_id")
        _require_token(self.evaluator_id, "evaluator_id")
        _require_exact_enum(self.direction, MetricDirection, "direction")

    def to_dict(self) -> dict[str, str]:
        return {
            "metric_id": self.metric_id,
            "evaluator_id": self.evaluator_id,
            "direction": self.direction.value,
        }


@dataclass(frozen=True, slots=True)
class EvidenceFloor:
    """A hard evidence/non-regression floor represented with canonical decimal text."""

    floor_id: str
    metric_id: str
    comparator: FloorComparator
    threshold_decimal: str
    subgroup: str | None = None

    def __post_init__(self) -> None:
        _require_token(self.floor_id, "floor_id")
        _require_token(self.metric_id, "metric_id")
        _require_exact_enum(self.comparator, FloorComparator, "comparator")
        _require_canonical_decimal(self.threshold_decimal, "threshold_decimal")
        if self.subgroup is not None:
            _require_text(self.subgroup, "subgroup")

    def to_dict(self) -> dict[str, object]:
        return {
            "floor_id": self.floor_id,
            "metric_id": self.metric_id,
            "comparator": self.comparator.value,
            "threshold_decimal": self.threshold_decimal,
            "subgroup": self.subgroup,
        }


@dataclass(frozen=True, slots=True)
class TierResultExposure:
    """Exact agent-visible result fields and exposure ceiling for one allowed tier."""

    tier: EvaluationTier
    max_exposures: int
    allowed_result_fields: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_exact_enum(self.tier, EvaluationTier, "tier")
        _require_nonnegative_int(self.max_exposures, "max_exposures")
        _require_sorted_unique_text(
            self.allowed_result_fields, "allowed_result_fields", allow_empty=True
        )
        if self.tier in (EvaluationTier.SEALED, EvaluationTier.EXTERNAL_ASSURANCE) and (
            self.max_exposures != 0 or self.allowed_result_fields
        ):
            raise ResearchObjectiveContractError(
                "Tier 3/4 cannot expose iterative agent-visible result fields"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "tier": int(self.tier),
            "max_exposures": self.max_exposures,
            "allowed_result_fields": list(self.allowed_result_fields),
        }


@dataclass(frozen=True, slots=True)
class ResearchObjectiveContract:
    """Frozen content-addressed scientific objective envelope for one MRL campaign."""

    objective_id: str
    research_program_refs: tuple[str, ...]
    target_capabilities: tuple[str, ...]
    hard_guardrails: tuple[EvidenceFloor, ...]
    search_metrics: tuple[MetricContract, ...]
    evaluation_metrics: tuple[MetricContract, ...]
    subgroup_floors: tuple[EvidenceFloor, ...]
    resource_budget: ResourceBudget
    allowed_mutation_surfaces: tuple[str, ...]
    forbidden_mutation_surfaces: tuple[str, ...]
    evaluation_tier_policy: EvaluationTierPolicy
    adaptive_query_budget: AdaptiveQueryBudget
    tier_result_exposure_policy: tuple[TierResultExposure, ...]
    budget_exhaustion_disposition: BudgetExhaustionDisposition
    evaluator_identities: tuple[EvaluatorIdentity, ...]

    def __post_init__(self) -> None:
        _require_text(self.objective_id, "objective_id")
        if not _OBJECTIVE_ID.fullmatch(self.objective_id):
            raise ResearchObjectiveContractError(
                "objective_id must be lowercase kebab-case [a-z0-9-]"
            )
        _require_sorted_unique_program_refs(self.research_program_refs)
        _require_sorted_unique_text(self.target_capabilities, "target_capabilities")
        _require_sorted_unique_text(
            self.allowed_mutation_surfaces, "allowed_mutation_surfaces", allow_empty=True
        )
        _require_sorted_unique_text(self.forbidden_mutation_surfaces, "forbidden_mutation_surfaces")
        _require_exact_instance(self.resource_budget, ResourceBudget, "resource_budget")
        _require_exact_instance(
            self.evaluation_tier_policy, EvaluationTierPolicy, "evaluation_tier_policy"
        )
        _require_exact_instance(
            self.adaptive_query_budget, AdaptiveQueryBudget, "adaptive_query_budget"
        )
        _require_exact_enum(
            self.budget_exhaustion_disposition,
            BudgetExhaustionDisposition,
            "budget_exhaustion_disposition",
        )
        _require_exact_instances(self.hard_guardrails, EvidenceFloor, "hard_guardrails")
        _require_exact_instances(self.search_metrics, MetricContract, "search_metrics")
        _require_exact_instances(self.evaluation_metrics, MetricContract, "evaluation_metrics")
        _require_exact_instances(self.subgroup_floors, EvidenceFloor, "subgroup_floors")
        _require_exact_instances(
            self.tier_result_exposure_policy,
            TierResultExposure,
            "tier_result_exposure_policy",
        )
        _require_exact_instances(
            self.evaluator_identities, EvaluatorIdentity, "evaluator_identities"
        )

        overlap = set(self.allowed_mutation_surfaces) & set(self.forbidden_mutation_surfaces)
        if overlap:
            raise ResearchObjectiveContractError(
                f"mutation surfaces cannot be both allowed and forbidden: {sorted(overlap)!r}"
            )
        if self.budget_exhaustion_disposition is not BudgetExhaustionDisposition.BLOCKED:
            raise ResearchObjectiveContractError("budget exhaustion disposition must be BLOCKED")

        evaluator_ids = tuple(identity.evaluator_id for identity in self.evaluator_identities)
        _require_strictly_sorted_ids(evaluator_ids, "evaluator_identities")
        allowed_tiers = set(self.evaluation_tier_policy.allowed_tiers)
        for identity in self.evaluator_identities:
            if not set(identity.tiers).issubset(allowed_tiers):
                raise ResearchObjectiveContractError(
                    f"evaluator {identity.evaluator_id!r} references a tier outside "
                    "the objective policy"
                )

        if not self.search_metrics:
            raise ResearchObjectiveContractError("search_metrics cannot be empty")
        if not self.evaluation_metrics:
            raise ResearchObjectiveContractError("evaluation_metrics cannot be empty")
        search_metric_ids = tuple(metric.metric_id for metric in self.search_metrics)
        evaluation_metric_ids_ordered = tuple(
            metric.metric_id for metric in self.evaluation_metrics
        )
        _require_strictly_sorted_ids(search_metric_ids, "search_metrics")
        _require_strictly_sorted_ids(evaluation_metric_ids_ordered, "evaluation_metrics")
        metric_ids = search_metric_ids + evaluation_metric_ids_ordered
        if len(metric_ids) != len(set(metric_ids)):
            raise ResearchObjectiveContractError(
                "metric_id cannot be reused across search and evaluation metrics"
            )
        known_evaluators = set(evaluator_ids)
        for metric in self.search_metrics + self.evaluation_metrics:
            if metric.evaluator_id not in known_evaluators:
                raise ResearchObjectiveContractError(
                    f"metric {metric.metric_id!r} references unknown evaluator "
                    f"{metric.evaluator_id!r}"
                )

        if not self.hard_guardrails:
            raise ResearchObjectiveContractError("hard_guardrails cannot be empty")
        hard_floor_ids = tuple(floor.floor_id for floor in self.hard_guardrails)
        subgroup_floor_ids = tuple(floor.floor_id for floor in self.subgroup_floors)
        _require_strictly_sorted_ids(hard_floor_ids, "hard_guardrails")
        if subgroup_floor_ids:
            _require_strictly_sorted_ids(subgroup_floor_ids, "subgroup_floors")
        floor_ids = hard_floor_ids + subgroup_floor_ids
        if len(floor_ids) != len(set(floor_ids)):
            raise ResearchObjectiveContractError(
                "floor_id cannot be reused across global and subgroup floors"
            )
        evaluation_metric_ids = set(evaluation_metric_ids_ordered)
        for floor in self.hard_guardrails:
            if floor.subgroup is not None:
                raise ResearchObjectiveContractError(
                    "hard_guardrails must be global; use subgroup_floors for "
                    "subgroup-specific floors"
                )
            if floor.metric_id not in evaluation_metric_ids:
                raise ResearchObjectiveContractError(
                    f"hard guardrail {floor.floor_id!r} must reference an evaluation metric"
                )
        for floor in self.subgroup_floors:
            if floor.subgroup is None:
                raise ResearchObjectiveContractError("subgroup_floors require a subgroup")
            if floor.metric_id not in evaluation_metric_ids:
                raise ResearchObjectiveContractError(
                    f"subgroup floor {floor.floor_id!r} must reference an evaluation metric"
                )

        exposure_tiers = tuple(policy.tier for policy in self.tier_result_exposure_policy)
        if tuple(int(tier) for tier in exposure_tiers) != tuple(
            sorted({int(tier) for tier in exposure_tiers})
        ):
            raise ResearchObjectiveContractError(
                "tier_result_exposure_policy must be unique and strictly ascending by tier"
            )
        if exposure_tiers != self.evaluation_tier_policy.allowed_tiers:
            raise ResearchObjectiveContractError(
                "tier_result_exposure_policy must define exactly every allowed evaluation tier"
            )

        if EvaluationTier.SEARCH not in allowed_tiers and self.adaptive_query_budget.tier_1_queries:
            raise ResearchObjectiveContractError(
                "tier_1_queries must be zero when Tier 1 SEARCH is not allowed"
            )
        if (
            EvaluationTier.REPLICATION not in allowed_tiers
            and self.adaptive_query_budget.tier_2_queries
        ):
            raise ResearchObjectiveContractError(
                "tier_2_queries must be zero when Tier 2 REPLICATION is not allowed"
            )

    @property
    def content_sha256(self) -> str:
        """Derived artifact identity, excluded from its semantic preimage."""
        return derive_content_sha256(self.semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        """Canonical UTF-8 semantic bytes used to derive ``content_sha256``."""
        return canonical_semantic_bytes(self.semantic_dict())

    def semantic_dict(self) -> dict[str, object]:
        """Return complete material semantics, deliberately excluding own identity."""
        return {
            "format": "MRL-RESEARCH-OBJECTIVE-V1",
            "objective_id": self.objective_id,
            "research_program_refs": list(self.research_program_refs),
            "target_capabilities": list(self.target_capabilities),
            "hard_guardrails": [floor.to_dict() for floor in self.hard_guardrails],
            "search_metrics": [metric.to_dict() for metric in self.search_metrics],
            "evaluation_metrics": [metric.to_dict() for metric in self.evaluation_metrics],
            "subgroup_floors": [floor.to_dict() for floor in self.subgroup_floors],
            "resource_budget": self.resource_budget.to_dict(),
            "allowed_mutation_surfaces": list(self.allowed_mutation_surfaces),
            "forbidden_mutation_surfaces": list(self.forbidden_mutation_surfaces),
            "evaluation_tier_policy": self.evaluation_tier_policy.to_dict(),
            "adaptive_query_budget": self.adaptive_query_budget.to_dict(),
            "tier_result_exposure_policy": [
                policy.to_dict() for policy in self.tier_result_exposure_policy
            ],
            "budget_exhaustion_disposition": self.budget_exhaustion_disposition.value,
            "evaluator_identities": [identity.to_dict() for identity in self.evaluator_identities],
        }

    def to_dict(self) -> dict[str, object]:
        """Return the artifact envelope with identity outside the semantic preimage."""
        data = self.semantic_dict()
        data["content_sha256"] = self.content_sha256
        return data


def _require_text(value: str, label: str) -> None:
    if type(value) is not str:
        raise ResearchObjectiveContractError(f"{label} must be an exact string")
    if not value or value != value.strip() or any(char in value for char in "\r\n\t"):
        raise ResearchObjectiveContractError(f"{label} must be non-empty canonical text")


def _require_token(value: str, label: str) -> None:
    _require_text(value, label)
    if not _TOKEN_ID.fullmatch(value):
        raise ResearchObjectiveContractError(f"{label} contains unsupported identifier characters")


def _require_sha256(value: str, label: str) -> None:
    _require_text(value, label)
    if not _SHA256.fullmatch(value):
        raise ResearchObjectiveContractError(f"{label} must be 64 lowercase hex")


def _require_sorted_unique_program_refs(values: tuple[str, ...]) -> None:
    _require_sorted_unique_text(values, "research_program_refs")
    for value in values:
        if not _RESEARCH_PROGRAM_REF.fullmatch(value):
            raise ResearchObjectiveContractError(
                f"research_program_refs contains unsupported reference {value!r}"
            )


def _require_sorted_unique_text(
    values: tuple[str, ...], label: str, *, allow_empty: bool = False
) -> None:
    if type(values) is not tuple:
        raise ResearchObjectiveContractError(f"{label} must be an exact tuple")
    if not values and not allow_empty:
        raise ResearchObjectiveContractError(f"{label} cannot be empty")
    for value in values:
        _require_text(value, label)
    if values != tuple(sorted(set(values))):
        raise ResearchObjectiveContractError(f"{label} must be unique and strictly sorted")


def _require_strictly_sorted_ids(values: tuple[str, ...], label: str) -> None:
    if not values:
        raise ResearchObjectiveContractError(f"{label} cannot be empty")
    if values != tuple(sorted(set(values))):
        raise ResearchObjectiveContractError(
            f"{label} identities must be unique and strictly sorted"
        )


def _require_nonnegative_int(value: int, label: str) -> None:
    if type(value) is not int or value < 0:
        raise ResearchObjectiveContractError(f"{label} must be a non-negative integer")


def _require_positive_int(value: int, label: str) -> None:
    if type(value) is not int or value <= 0:
        raise ResearchObjectiveContractError(f"{label} must be a positive integer")


def _require_optional_nonnegative_int(value: int | None, label: str) -> None:
    if value is not None:
        _require_nonnegative_int(value, label)


def _require_canonical_decimal(value: str, label: str) -> None:
    _require_text(value, label)
    if not _CANONICAL_DECIMAL.fullmatch(value):
        raise ResearchObjectiveContractError(
            f"{label} must be plain canonical decimal text without exponent/trailing zeroes"
        )
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ResearchObjectiveContractError(f"{label} must be a finite decimal") from exc
    if not parsed.is_finite() or (parsed == 0 and value != "0"):
        raise ResearchObjectiveContractError(f"{label} must be canonical finite decimal text")


def _require_exact_instance(value: object, expected_type: type[object], label: str) -> None:
    if type(value) is not expected_type:
        raise ResearchObjectiveContractError(f"{label} must be exact {expected_type.__name__}")


def _require_exact_instances(
    values: tuple[object, ...], expected_type: type[object], label: str
) -> None:
    if type(values) is not tuple:
        raise ResearchObjectiveContractError(f"{label} must be an exact tuple")
    for value in values:
        _require_exact_instance(value, expected_type, label)


def _require_exact_enum(value: object, expected_type: type[enum.Enum], label: str) -> None:
    if type(value) is not expected_type:
        raise ResearchObjectiveContractError(
            f"{label} must be exact {expected_type.__name__} member"
        )
