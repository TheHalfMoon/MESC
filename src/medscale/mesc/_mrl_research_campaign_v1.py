"""Immutable, content-addressed MRL V1 research campaign DAG.

A campaign preserves the canonical research graph and cumulative accounting across
content-addressed snapshots. Failed, null, invalid, and rejected branches are append-only
history: later snapshots may move the current frontier, but they cannot delete or rewrite
prior nodes, branch outcomes, or replication relationships. Cumulative resource, query,
and result-exposure counters may only increase relative to the exact parent campaign.

This artifact records research state only. It grants no filesystem, network, model,
dataset, GPU, inference, training, promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_objective_v1 import EvaluationTier

__all__ = [
    "CampaignBranchOutcome",
    "CampaignBranchOutcomeKind",
    "CampaignNode",
    "CampaignNodeKind",
    "CampaignReplicationRelation",
    "CampaignResourceTotals",
    "CampaignTierTotals",
    "ResearchCampaign",
    "ResearchCampaignError",
]

_CAMPAIGN_ID: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NODE_ID: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


class ResearchCampaignError(ValueError):
    """Fail-closed validation error for one MRL research campaign snapshot."""


class CampaignNodeKind(enum.Enum):
    """Canonical artifact roles that may participate in the campaign DAG."""

    HYPOTHESIS = "HYPOTHESIS"
    EXPERIMENT_PLAN = "EXPERIMENT_PLAN"
    RECEIPT = "RECEIPT"
    DECISION = "DECISION"
    PROCEDURE_CANDIDATE = "PROCEDURE_CANDIDATE"


class CampaignBranchOutcomeKind(enum.Enum):
    """Negative or terminal branch outcomes that canonical history must preserve."""

    FAILED = "FAILED"
    NULL = "NULL"
    INVALID = "INVALID"
    REJECTED = "REJECTED"


@dataclass(frozen=True, slots=True)
class CampaignNode:
    """One content-addressed artifact node and its direct DAG ancestry."""

    node_id: str
    kind: CampaignNodeKind
    artifact_sha256: str
    parent_node_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_node_id(self.node_id, "node_id")
        _require_exact_enum(self.kind, CampaignNodeKind, "kind")
        _require_sha256(self.artifact_sha256, "artifact_sha256")
        _require_sorted_unique_node_ids(self.parent_node_ids, "parent_node_ids")
        if self.node_id in self.parent_node_ids:
            raise ResearchCampaignError("campaign node cannot reference itself as a parent")

    def to_dict(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "kind": self.kind.value,
            "artifact_sha256": self.artifact_sha256,
            "parent_node_ids": list(self.parent_node_ids),
        }


@dataclass(frozen=True, slots=True)
class CampaignReplicationRelation:
    """One explicit replication relationship between two known campaign nodes."""

    source_node_id: str
    replica_node_id: str
    evidence_sha256s: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_node_id(self.source_node_id, "source_node_id")
        _require_node_id(self.replica_node_id, "replica_node_id")
        if self.source_node_id == self.replica_node_id:
            raise ResearchCampaignError("replication source and replica must be different nodes")
        _require_sorted_unique_sha256s(
            self.evidence_sha256s,
            "replication evidence_sha256s",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "source_node_id": self.source_node_id,
            "replica_node_id": self.replica_node_id,
            "evidence_sha256s": list(self.evidence_sha256s),
        }


@dataclass(frozen=True, slots=True)
class CampaignBranchOutcome:
    """Append-only negative/null branch disposition for one known terminal node."""

    terminal_node_id: str
    outcome: CampaignBranchOutcomeKind
    evidence_sha256s: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        _require_node_id(self.terminal_node_id, "terminal_node_id")
        _require_exact_enum(self.outcome, CampaignBranchOutcomeKind, "outcome")
        _require_sorted_unique_sha256s(
            self.evidence_sha256s,
            "branch outcome evidence_sha256s",
        )
        _require_text(self.reason, "branch outcome reason")

    def to_dict(self) -> dict[str, object]:
        return {
            "terminal_node_id": self.terminal_node_id,
            "outcome": self.outcome.value,
            "evidence_sha256s": list(self.evidence_sha256s),
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class CampaignResourceTotals:
    """Monotonic cumulative resource totals for one campaign snapshot."""

    wall_clock_seconds: int
    compute_seconds: int
    input_tokens: int
    generated_tokens: int
    storage_bytes: int
    monetary_cost_microunits: int
    retries: int
    known_failure_retries: int
    evaluator_invocations: int

    def __post_init__(self) -> None:
        for label, value in self._items():
            _require_nonnegative_int(value, label)
        if self.known_failure_retries > self.retries:
            raise ResearchCampaignError("known_failure_retries cannot exceed retries")

    def _items(self) -> tuple[tuple[str, int], ...]:
        return (
            ("wall_clock_seconds", self.wall_clock_seconds),
            ("compute_seconds", self.compute_seconds),
            ("input_tokens", self.input_tokens),
            ("generated_tokens", self.generated_tokens),
            ("storage_bytes", self.storage_bytes),
            ("monetary_cost_microunits", self.monetary_cost_microunits),
            ("retries", self.retries),
            ("known_failure_retries", self.known_failure_retries),
            ("evaluator_invocations", self.evaluator_invocations),
        )

    def to_dict(self) -> dict[str, int]:
        return dict(self._items())


@dataclass(frozen=True, slots=True)
class CampaignTierTotals:
    """Monotonic cumulative adaptive-query and result-exposure totals for one tier."""

    tier: EvaluationTier
    queries_used: int
    result_exposures_used: int

    def __post_init__(self) -> None:
        _require_exact_enum(self.tier, EvaluationTier, "tier")
        _require_nonnegative_int(self.queries_used, "queries_used")
        _require_nonnegative_int(self.result_exposures_used, "result_exposures_used")

    def to_dict(self) -> dict[str, int]:
        return {
            "tier": int(self.tier),
            "queries_used": self.queries_used,
            "result_exposures_used": self.result_exposures_used,
        }


@dataclass(frozen=True, slots=True)
class ResearchCampaign:
    """One immutable campaign snapshot linked to its exact canonical parent snapshot."""

    campaign_id: str
    objective_sha256: str
    parent: ResearchCampaign | None
    nodes: tuple[CampaignNode, ...]
    replications: tuple[CampaignReplicationRelation, ...]
    retained_alternative_node_ids: tuple[str, ...]
    branch_outcomes: tuple[CampaignBranchOutcome, ...]
    current_frontier_node_ids: tuple[str, ...]
    procedure_candidate_node_ids: tuple[str, ...]
    cumulative_resource_usage: CampaignResourceTotals
    cumulative_tier_usage: tuple[CampaignTierTotals, ...]

    def __post_init__(self) -> None:
        _validate_campaign(self)

    def _validated_snapshot(self) -> ResearchCampaign:
        """Rebuild all reachable semantic state before every trust-bearing view."""
        _require_exact_campaign(self)
        _require_parent_chain_acyclic(self)
        parent = None if self.parent is None else self.parent._validated_snapshot()
        return ResearchCampaign(
            campaign_id=self.campaign_id,
            objective_sha256=self.objective_sha256,
            parent=parent,
            nodes=tuple(_rebuild_node(node) for node in self.nodes),
            replications=tuple(_rebuild_replication(item) for item in self.replications),
            retained_alternative_node_ids=self.retained_alternative_node_ids,
            branch_outcomes=tuple(_rebuild_branch_outcome(item) for item in self.branch_outcomes),
            current_frontier_node_ids=self.current_frontier_node_ids,
            procedure_candidate_node_ids=self.procedure_candidate_node_ids,
            cumulative_resource_usage=_rebuild_resource_totals(self.cumulative_resource_usage),
            cumulative_tier_usage=tuple(
                _rebuild_tier_totals(item) for item in self.cumulative_tier_usage
            ),
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        """Serialize one campaign snapshot that has already passed complete validation."""
        parent_sha256 = None if self.parent is None else self.parent.content_sha256
        return {
            "format": "MRL-RESEARCH-CAMPAIGN-V1",
            "campaign_id": self.campaign_id,
            "objective_sha256": self.objective_sha256,
            "parent_campaign_sha256": parent_sha256,
            "nodes": [node.to_dict() for node in self.nodes],
            "replications": [item.to_dict() for item in self.replications],
            "retained_alternative_node_ids": list(self.retained_alternative_node_ids),
            "branch_outcomes": [item.to_dict() for item in self.branch_outcomes],
            "current_frontier_node_ids": list(self.current_frontier_node_ids),
            "procedure_candidate_node_ids": list(self.procedure_candidate_node_ids),
            "cumulative_resource_usage": self.cumulative_resource_usage.to_dict(),
            "cumulative_tier_usage": [item.to_dict() for item in self.cumulative_tier_usage],
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return complete semantics from one freshly revalidated campaign snapshot."""
        snapshot = self._validated_snapshot()
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical UTF-8 bytes for one freshly revalidated campaign snapshot."""
        snapshot = self._validated_snapshot()
        return canonical_semantic_bytes(snapshot._semantic_dict_validated())

    @property
    def content_sha256(self) -> str:
        """Derive campaign identity outside its own semantic preimage."""
        snapshot = self._validated_snapshot()
        return derive_content_sha256(snapshot._semantic_dict_validated())

    def to_dict(self) -> dict[str, object]:
        """Return semantic envelope plus the derived campaign identity."""
        snapshot = self._validated_snapshot()
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def _validate_campaign(campaign: ResearchCampaign) -> None:
    _require_campaign_id(campaign.campaign_id)
    _require_sha256(campaign.objective_sha256, "objective_sha256")
    _require_parent_chain_acyclic(campaign)
    _require_nodes(campaign.nodes)
    node_by_id = {node.node_id: node for node in campaign.nodes}
    _require_dag(node_by_id)
    _require_replications(campaign.replications, node_by_id)
    _require_known_node_ids(
        campaign.retained_alternative_node_ids,
        "retained_alternative_node_ids",
        node_by_id,
    )
    _require_branch_outcomes(campaign.branch_outcomes, node_by_id)
    _require_known_node_ids(
        campaign.current_frontier_node_ids,
        "current_frontier_node_ids",
        node_by_id,
    )
    _require_known_node_ids(
        campaign.procedure_candidate_node_ids,
        "procedure_candidate_node_ids",
        node_by_id,
    )
    for node_id in campaign.procedure_candidate_node_ids:
        if node_by_id[node_id].kind is not CampaignNodeKind.PROCEDURE_CANDIDATE:
            raise ResearchCampaignError(
                "procedure_candidate_node_ids must reference PROCEDURE_CANDIDATE nodes"
            )
    if type(campaign.cumulative_resource_usage) is not CampaignResourceTotals:
        raise ResearchCampaignError("cumulative_resource_usage has an invalid type")
    _ = _rebuild_resource_totals(campaign.cumulative_resource_usage)
    _require_tier_totals(campaign.cumulative_tier_usage)

    if campaign.parent is None:
        return
    if type(campaign.parent) is not ResearchCampaign:
        raise ResearchCampaignError("parent must be an exact ResearchCampaign or None")
    parent = campaign.parent._validated_snapshot()
    if parent.campaign_id != campaign.campaign_id:
        raise ResearchCampaignError("parent campaign_id must match the child campaign_id")
    if parent.objective_sha256 != campaign.objective_sha256:
        raise ResearchCampaignError("parent objective identity must match the child campaign")
    _require_append_only_nodes(parent.nodes, campaign.nodes)
    _require_append_only_replications(parent.replications, campaign.replications)
    _require_append_only_branch_outcomes(
        parent.branch_outcomes,
        campaign.branch_outcomes,
    )
    _require_resource_monotonic(
        parent.cumulative_resource_usage,
        campaign.cumulative_resource_usage,
    )
    _require_tier_monotonic(
        parent.cumulative_tier_usage,
        campaign.cumulative_tier_usage,
    )


def _require_parent_chain_acyclic(campaign: ResearchCampaign) -> None:
    seen: set[int] = set()
    current: ResearchCampaign | None = campaign
    while current is not None:
        if type(current) is not ResearchCampaign:
            raise ResearchCampaignError("campaign parent chain contains an invalid type")
        identity = id(current)
        if identity in seen:
            raise ResearchCampaignError("campaign parent chain cannot contain a cycle")
        seen.add(identity)
        current = current.parent


def _require_nodes(nodes: tuple[CampaignNode, ...]) -> None:
    if type(nodes) is not tuple:
        raise ResearchCampaignError("nodes must be an exact tuple")
    if any(type(node) is not CampaignNode for node in nodes):
        raise ResearchCampaignError("nodes contain invalid item types")
    rebuilt = tuple(_rebuild_node(node) for node in nodes)
    node_ids = tuple(node.node_id for node in rebuilt)
    if node_ids != tuple(sorted(set(node_ids))):
        raise ResearchCampaignError("nodes must be unique and strictly sorted by node_id")


def _require_dag(node_by_id: dict[str, CampaignNode]) -> None:
    for node in node_by_id.values():
        for parent_id in node.parent_node_ids:
            if parent_id not in node_by_id:
                raise ResearchCampaignError(
                    f"node {node.node_id!r} references unknown parent node {parent_id!r}"
                )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visited:
            return
        if node_id in visiting:
            raise ResearchCampaignError("campaign node graph must be acyclic")
        visiting.add(node_id)
        for parent_id in node_by_id[node_id].parent_node_ids:
            visit(parent_id)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in node_by_id:
        visit(node_id)


def _require_replications(
    replications: tuple[CampaignReplicationRelation, ...],
    node_by_id: dict[str, CampaignNode],
) -> None:
    if type(replications) is not tuple:
        raise ResearchCampaignError("replications must be an exact tuple")
    if any(type(item) is not CampaignReplicationRelation for item in replications):
        raise ResearchCampaignError("replications contain invalid item types")
    rebuilt = tuple(_rebuild_replication(item) for item in replications)
    keys = tuple((item.source_node_id, item.replica_node_id) for item in rebuilt)
    if keys != tuple(sorted(set(keys))):
        raise ResearchCampaignError(
            "replications must be unique and strictly sorted by source/replica node"
        )
    for item in rebuilt:
        if item.source_node_id not in node_by_id or item.replica_node_id not in node_by_id:
            raise ResearchCampaignError("replication relationship references an unknown node")


def _require_branch_outcomes(
    outcomes: tuple[CampaignBranchOutcome, ...],
    node_by_id: dict[str, CampaignNode],
) -> None:
    if type(outcomes) is not tuple:
        raise ResearchCampaignError("branch_outcomes must be an exact tuple")
    if any(type(item) is not CampaignBranchOutcome for item in outcomes):
        raise ResearchCampaignError("branch_outcomes contain invalid item types")
    rebuilt = tuple(_rebuild_branch_outcome(item) for item in outcomes)
    node_ids = tuple(item.terminal_node_id for item in rebuilt)
    if node_ids != tuple(sorted(set(node_ids))):
        raise ResearchCampaignError(
            "branch_outcomes must be unique and strictly sorted by terminal_node_id"
        )
    for item in rebuilt:
        if item.terminal_node_id not in node_by_id:
            raise ResearchCampaignError("branch outcome references an unknown terminal node")


def _require_tier_totals(values: tuple[CampaignTierTotals, ...]) -> None:
    if type(values) is not tuple:
        raise ResearchCampaignError("cumulative_tier_usage must be an exact tuple")
    if any(type(item) is not CampaignTierTotals for item in values):
        raise ResearchCampaignError("cumulative_tier_usage contains invalid item types")
    rebuilt = tuple(_rebuild_tier_totals(item) for item in values)
    tiers = tuple(int(item.tier) for item in rebuilt)
    if tiers != tuple(sorted(set(tiers))):
        raise ResearchCampaignError(
            "cumulative_tier_usage must be unique and strictly sorted by tier"
        )


def _require_known_node_ids(
    values: tuple[str, ...],
    label: str,
    node_by_id: dict[str, CampaignNode],
) -> None:
    _require_sorted_unique_node_ids(values, label)
    for node_id in values:
        if node_id not in node_by_id:
            raise ResearchCampaignError(f"{label} references unknown node {node_id!r}")


def _require_append_only_nodes(
    previous: tuple[CampaignNode, ...],
    current: tuple[CampaignNode, ...],
) -> None:
    current_by_id = {node.node_id: node for node in current}
    for node in previous:
        candidate = current_by_id.get(node.node_id)
        if candidate is None:
            raise ResearchCampaignError("campaign history cannot delete a prior node")
        if candidate.to_dict() != node.to_dict():
            raise ResearchCampaignError("campaign history cannot rewrite a prior node")


def _replication_key(
    item: CampaignReplicationRelation,
) -> tuple[str, str, tuple[str, ...]]:
    return (
        item.source_node_id,
        item.replica_node_id,
        item.evidence_sha256s,
    )


def _require_append_only_replications(
    previous: tuple[CampaignReplicationRelation, ...],
    current: tuple[CampaignReplicationRelation, ...],
) -> None:
    current_semantics = {_replication_key(item) for item in current}
    for item in previous:
        if _replication_key(item) not in current_semantics:
            raise ResearchCampaignError(
                "campaign history cannot delete or rewrite a prior replication relationship"
            )


def _require_append_only_branch_outcomes(
    previous: tuple[CampaignBranchOutcome, ...],
    current: tuple[CampaignBranchOutcome, ...],
) -> None:
    current_by_node = {item.terminal_node_id: item for item in current}
    for item in previous:
        candidate = current_by_node.get(item.terminal_node_id)
        if candidate is None:
            raise ResearchCampaignError("campaign history cannot delete a prior branch outcome")
        if candidate.to_dict() != item.to_dict():
            raise ResearchCampaignError("campaign history cannot rewrite a prior branch outcome")


def _require_resource_monotonic(
    previous: CampaignResourceTotals,
    current: CampaignResourceTotals,
) -> None:
    previous_items = dict(previous._items())
    for label, value in current._items():
        if value < previous_items[label]:
            raise ResearchCampaignError(f"cumulative resource counter {label} cannot move backward")


def _require_tier_monotonic(
    previous: tuple[CampaignTierTotals, ...],
    current: tuple[CampaignTierTotals, ...],
) -> None:
    current_by_tier = {item.tier: item for item in current}
    for prior in previous:
        candidate = current_by_tier.get(prior.tier)
        if candidate is None:
            raise ResearchCampaignError("cumulative tier accounting cannot delete a prior tier")
        if candidate.queries_used < prior.queries_used:
            raise ResearchCampaignError("cumulative tier query accounting cannot move backward")
        if candidate.result_exposures_used < prior.result_exposures_used:
            raise ResearchCampaignError(
                "cumulative tier result-exposure accounting cannot move backward"
            )


def _rebuild_node(node: CampaignNode) -> CampaignNode:
    if type(node) is not CampaignNode:
        raise ResearchCampaignError("campaign node has an invalid type")
    return CampaignNode(
        node_id=node.node_id,
        kind=node.kind,
        artifact_sha256=node.artifact_sha256,
        parent_node_ids=node.parent_node_ids,
    )


def _rebuild_replication(
    item: CampaignReplicationRelation,
) -> CampaignReplicationRelation:
    if type(item) is not CampaignReplicationRelation:
        raise ResearchCampaignError("replication relationship has an invalid type")
    return CampaignReplicationRelation(
        source_node_id=item.source_node_id,
        replica_node_id=item.replica_node_id,
        evidence_sha256s=item.evidence_sha256s,
    )


def _rebuild_branch_outcome(item: CampaignBranchOutcome) -> CampaignBranchOutcome:
    if type(item) is not CampaignBranchOutcome:
        raise ResearchCampaignError("branch outcome has an invalid type")
    return CampaignBranchOutcome(
        terminal_node_id=item.terminal_node_id,
        outcome=item.outcome,
        evidence_sha256s=item.evidence_sha256s,
        reason=item.reason,
    )


def _rebuild_resource_totals(value: CampaignResourceTotals) -> CampaignResourceTotals:
    if type(value) is not CampaignResourceTotals:
        raise ResearchCampaignError("cumulative resource usage has an invalid type")
    return CampaignResourceTotals(
        wall_clock_seconds=value.wall_clock_seconds,
        compute_seconds=value.compute_seconds,
        input_tokens=value.input_tokens,
        generated_tokens=value.generated_tokens,
        storage_bytes=value.storage_bytes,
        monetary_cost_microunits=value.monetary_cost_microunits,
        retries=value.retries,
        known_failure_retries=value.known_failure_retries,
        evaluator_invocations=value.evaluator_invocations,
    )


def _rebuild_tier_totals(value: CampaignTierTotals) -> CampaignTierTotals:
    if type(value) is not CampaignTierTotals:
        raise ResearchCampaignError("cumulative tier usage has an invalid type")
    return CampaignTierTotals(
        tier=value.tier,
        queries_used=value.queries_used,
        result_exposures_used=value.result_exposures_used,
    )


def _require_exact_campaign(value: ResearchCampaign) -> None:
    if type(value) is not ResearchCampaign:
        raise ResearchCampaignError(
            "research campaign semantic views require an exact ResearchCampaign instance"
        )


def _require_campaign_id(value: str) -> None:
    _require_text(value, "campaign_id")
    if not _CAMPAIGN_ID.fullmatch(value):
        raise ResearchCampaignError("campaign_id must use lowercase kebab-case semantics")


def _require_node_id(value: str, label: str) -> None:
    _require_text(value, label)
    if not _NODE_ID.fullmatch(value):
        raise ResearchCampaignError(f"{label} must use lowercase kebab-case semantics")


def _require_sorted_unique_node_ids(values: tuple[str, ...], label: str) -> None:
    if type(values) is not tuple:
        raise ResearchCampaignError(f"{label} must be an exact tuple")
    for value in values:
        _require_node_id(value, label)
    if values != tuple(sorted(set(values))):
        raise ResearchCampaignError(f"{label} must be unique and strictly sorted")


def _require_sorted_unique_sha256s(
    values: tuple[str, ...],
    label: str,
) -> None:
    if type(values) is not tuple:
        raise ResearchCampaignError(f"{label} must be an exact tuple")
    for value in values:
        _require_sha256(value, label)
    if values != tuple(sorted(set(values))):
        raise ResearchCampaignError(f"{label} must be unique and strictly sorted")


def _require_sha256(value: str, label: str) -> None:
    _require_text(value, label)
    if not _SHA256.fullmatch(value):
        raise ResearchCampaignError(f"{label} must be 64 lowercase hex")


def _require_nonnegative_int(value: int, label: str) -> None:
    if type(value) is not int or value < 0:
        raise ResearchCampaignError(f"{label} must be an exact non-negative integer")


def _require_text(value: str, label: str) -> None:
    if type(value) is not str:
        raise ResearchCampaignError(f"{label} must be an exact string")
    if not value or value != value.strip() or any(char in value for char in "\x00\r\n\t"):
        raise ResearchCampaignError(f"{label} must be non-empty canonical text")


def _require_exact_enum(
    value: object,
    enum_type: type[enum.Enum],
    label: str,
) -> None:
    if type(value) is not enum_type:
        raise ResearchCampaignError(f"{label} has an invalid enum type")
