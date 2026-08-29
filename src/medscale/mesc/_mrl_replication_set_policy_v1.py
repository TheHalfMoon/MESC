"""Frozen Tier 2 replication-set policy for MESC Research Loop V1.

MRL-0303 derives replication query/result-exposure limits from one already-frozen
``ResearchObjectiveContract``. Tier 2 may not expose broader result fields or a larger
result-exposure budget than Tier 1 SEARCH.

This module is pure and non-authoritative. It grants no model, data, runtime, GPU,
training, promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    ResearchObjectiveContract,
    TierResultExposure,
)
from medscale.mesc._mrl_tier_evaluation_contract_v1 import TierEvaluationContract

__all__ = [
    "ReplicationSet",
    "ReplicationSetMember",
    "ReplicationSetPolicy",
    "ReplicationSetPolicyError",
    "build_replication_set",
]

_MEMBER_ID: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


class ReplicationSetPolicyError(ValueError):
    """Fail-closed validation error for MRL-0303 replication policy."""


@dataclass(frozen=True, slots=True)
class ReplicationSetMember:
    """One exact candidate/receipt identity admitted to a replication set."""

    member_id: str
    artifact_sha256: str

    def __post_init__(self) -> None:
        if type(self.member_id) is not str or _MEMBER_ID.fullmatch(self.member_id) is None:
            raise ReplicationSetPolicyError("member_id must be canonical lowercase kebab-case")
        if type(self.artifact_sha256) is not str or _SHA256.fullmatch(self.artifact_sha256) is None:
            raise ReplicationSetPolicyError("artifact_sha256 must be 64 lowercase hex")

    def _validated_snapshot(self) -> ReplicationSetMember:
        if type(self) is not ReplicationSetMember:
            raise ReplicationSetPolicyError(
                "member must be an exact ReplicationSetMember"
            )
        return ReplicationSetMember(
            member_id=self.member_id,
            artifact_sha256=self.artifact_sha256,
        )

    def _to_dict_validated(self) -> dict[str, str]:
        return {"artifact_sha256": self.artifact_sha256, "member_id": self.member_id}

    def to_dict(self) -> dict[str, str]:
        """Return freshly revalidated deterministic member identity."""
        snapshot = ReplicationSetMember._validated_snapshot(self)
        return snapshot._to_dict_validated()


@dataclass(frozen=True, slots=True)
class ReplicationSetPolicy:
    """Exact Tier 2 bounds derived from one frozen objective."""

    objective: ResearchObjectiveContract
    _bound_objective_sha256: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        if type(self.objective) is not ResearchObjectiveContract:
            raise ReplicationSetPolicyError("objective must be an exact ResearchObjectiveContract")
        self.objective.semantic_dict()
        object.__setattr__(self, "_bound_objective_sha256", self.objective.content_sha256)
        self.search_contract.semantic_dict()
        self.replication_contract.semantic_dict()
        replication = self.replication_exposure
        search = self.search_exposure
        if replication.max_exposures > search.max_exposures:
            raise ReplicationSetPolicyError("Tier 2 exposure ceiling cannot exceed Tier 1")
        if not set(replication.allowed_result_fields).issubset(search.allowed_result_fields):
            raise ReplicationSetPolicyError("Tier 2 result fields must be a subset of Tier 1")

    def _validated_objective(self) -> ResearchObjectiveContract:
        if type(self) is not ReplicationSetPolicy:
            raise ReplicationSetPolicyError("policy must be an exact ReplicationSetPolicy")
        if type(self.objective) is not ResearchObjectiveContract:
            raise ReplicationSetPolicyError("objective must be an exact ResearchObjectiveContract")
        self.objective.semantic_dict()
        _require_sha256(self._bound_objective_sha256, "bound objective_sha256")
        if self.objective.content_sha256 != self._bound_objective_sha256:
            raise ReplicationSetPolicyError(
                "objective identity changed after replication policy construction"
            )
        return self.objective

    @property
    def search_contract(self) -> TierEvaluationContract:
        """Return a fresh Tier 1 contract from the same validated objective."""
        return TierEvaluationContract(
            objective=self._validated_objective(),
            tier=EvaluationTier.SEARCH,
        )

    @property
    def replication_contract(self) -> TierEvaluationContract:
        """Return a fresh Tier 2 contract from the same validated objective."""
        return TierEvaluationContract(
            objective=self._validated_objective(),
            tier=EvaluationTier.REPLICATION,
        )

    @property
    def max_replication_queries(self) -> int:
        """Return the frozen Tier 2 adaptive-query ceiling."""
        return self._validated_objective().adaptive_query_budget.tier_2_queries

    @property
    def search_exposure(self) -> TierResultExposure:
        """Return the exact frozen Tier 1 result-exposure policy."""
        return _exposure_for(self._validated_objective(), EvaluationTier.SEARCH)

    @property
    def replication_exposure(self) -> TierResultExposure:
        """Return the exact frozen Tier 2 result-exposure policy."""
        return _exposure_for(self._validated_objective(), EvaluationTier.REPLICATION)

    @property
    def can_authorize(self) -> bool:
        """Replication policy is never an authority artifact."""
        return False

    def to_dict(self) -> dict[str, object]:
        """Return deterministic policy semantics from the bound objective identity."""
        objective = self._validated_objective()
        return {
            "allowed_summary_fields": list(self.replication_exposure.allowed_result_fields),
            "can_authorize": False,
            "max_replication_queries": self.max_replication_queries,
            "max_summary_exposures": self.replication_exposure.max_exposures,
            "objective_sha256": objective.content_sha256,
            "replication_tier_contract_sha256": self.replication_contract.content_sha256,
            "search_tier_contract_sha256": self.search_contract.content_sha256,
        }


@dataclass(frozen=True, slots=True)
class ReplicationSet:
    """One immutable replication set bounded by the frozen Tier 2 policy."""

    objective_sha256: str
    members: tuple[ReplicationSetMember, ...]
    max_replication_queries: int
    allowed_summary_fields: tuple[str, ...]
    max_summary_exposures: int

    def __post_init__(self) -> None:
        _require_sha256(self.objective_sha256, "objective_sha256")
        if type(self.members) is not tuple or not self.members:
            raise ReplicationSetPolicyError("members must be a non-empty exact tuple")
        if any(type(member) is not ReplicationSetMember for member in self.members):
            raise ReplicationSetPolicyError("members contains an invalid member type")
        member_snapshots = tuple(
            ReplicationSetMember._validated_snapshot(member) for member in self.members
        )
        keys = tuple(member.member_id for member in member_snapshots)
        if keys != tuple(sorted(set(keys))):
            raise ReplicationSetPolicyError("members must be sorted and identity-unique")
        artifacts = tuple(member.artifact_sha256 for member in member_snapshots)
        if len(set(artifacts)) != len(artifacts):
            raise ReplicationSetPolicyError("replication members must bind distinct artifacts")
        _require_nonnegative_int(self.max_replication_queries, "max_replication_queries")
        _require_nonnegative_int(self.max_summary_exposures, "max_summary_exposures")
        _require_sorted_unique_text(self.allowed_summary_fields)

    def _validated_snapshot(self) -> ReplicationSet:
        if type(self) is not ReplicationSet:
            raise ReplicationSetPolicyError("replication set must be an exact ReplicationSet")
        if type(self.members) is not tuple:
            raise ReplicationSetPolicyError("members must be an exact tuple")
        return ReplicationSet(
            objective_sha256=self.objective_sha256,
            members=tuple(
                ReplicationSetMember._validated_snapshot(member) for member in self.members
            ),
            max_replication_queries=self.max_replication_queries,
            allowed_summary_fields=self.allowed_summary_fields,
            max_summary_exposures=self.max_summary_exposures,
        )

    def _to_dict_validated(self) -> dict[str, object]:
        return {
            "allowed_summary_fields": list(self.allowed_summary_fields),
            "can_authorize": False,
            "max_replication_queries": self.max_replication_queries,
            "max_summary_exposures": self.max_summary_exposures,
            "members": [member._to_dict_validated() for member in self.members],
            "objective_sha256": self.objective_sha256,
        }

    def to_dict(self) -> dict[str, object]:
        """Return freshly revalidated bounded replication-set semantics."""
        snapshot = ReplicationSet._validated_snapshot(self)
        return snapshot._to_dict_validated()


def build_replication_set(
    policy: ReplicationSetPolicy,
    members: tuple[ReplicationSetMember, ...],
) -> ReplicationSet:
    """Build one set only when its size fits the frozen Tier 2 query ceiling."""
    if type(policy) is not ReplicationSetPolicy:
        raise ReplicationSetPolicyError("policy must be an exact ReplicationSetPolicy")
    if type(members) is not tuple:
        raise ReplicationSetPolicyError("members must be an exact tuple")
    policy._validated_objective()
    member_snapshots = tuple(
        ReplicationSetMember._validated_snapshot(member) for member in members
    )
    if len(member_snapshots) > policy.max_replication_queries:
        raise ReplicationSetPolicyError("replication set exceeds the frozen Tier 2 query ceiling")
    exposure = policy.replication_exposure
    return ReplicationSet(
        objective_sha256=policy._bound_objective_sha256,
        members=member_snapshots,
        max_replication_queries=policy.max_replication_queries,
        allowed_summary_fields=exposure.allowed_result_fields,
        max_summary_exposures=exposure.max_exposures,
    )


def _exposure_for(
    objective: ResearchObjectiveContract,
    tier: EvaluationTier,
) -> TierResultExposure:
    matches = [policy for policy in objective.tier_result_exposure_policy if policy.tier is tier]
    if len(matches) != 1:
        raise ReplicationSetPolicyError(
            "objective must define exactly one exposure policy per tier"
        )
    policy = matches[0]
    return TierResultExposure(
        tier=policy.tier,
        max_exposures=policy.max_exposures,
        allowed_result_fields=policy.allowed_result_fields,
    )


def _require_nonnegative_int(value: object, label: str) -> None:
    if type(value) is not int or value < 0:
        raise ReplicationSetPolicyError(f"{label} must be a non-negative exact integer")


def _require_sorted_unique_text(values: tuple[str, ...]) -> None:
    if type(values) is not tuple:
        raise ReplicationSetPolicyError("allowed_summary_fields must be an exact tuple")
    if any(type(value) is not str or not value or value.strip() != value for value in values):
        raise ReplicationSetPolicyError("allowed_summary_fields must contain canonical strings")
    if values != tuple(sorted(set(values))):
        raise ReplicationSetPolicyError("allowed_summary_fields must be sorted and unique")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ReplicationSetPolicyError(f"{label} must be 64 lowercase hex")
