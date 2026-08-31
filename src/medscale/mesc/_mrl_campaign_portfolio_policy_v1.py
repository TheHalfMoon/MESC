"""Deterministic campaign frontier/portfolio policy for MRL-0501.

The policy is a derived, content-addressed research view over one exact canonical
``ResearchCampaign`` snapshot. It limits active frontier breadth and hypothesis-root
concentration while also freezing retained-alternative and replication budgets for
subsequent MRL-5 branch semantics.

This module is non-authoritative. It grants no filesystem, network, model, data, GPU,
training, promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_campaign_v1 import (
    CampaignBranchOutcomeKind,
    CampaignNode,
    CampaignNodeKind,
    ResearchCampaign,
    ResearchCampaignError,
)

__all__ = [
    "CampaignPortfolioFrontier",
    "CampaignPortfolioFrontierEntry",
    "CampaignPortfolioPolicy",
    "CampaignPortfolioPolicyError",
    "build_campaign_portfolio_frontier",
]

_MAX_LIMIT: Final = 10_000


class CampaignPortfolioPolicyError(ValueError):
    """Fail-closed validation error for MRL-0501 portfolio policy semantics."""


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
            raise CampaignPortfolioPolicyError("portfolio construction identity already exists")
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: object, label: str) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise CampaignPortfolioPolicyError(f"{label} construction identity is missing")
        return identity

    return store, load


_store_identity, _load_identity = _make_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class CampaignPortfolioPolicy:
    """Frozen bounded policy for one campaign portfolio frontier."""

    max_frontier_size: int
    min_distinct_hypothesis_roots: int
    max_frontier_per_hypothesis_root: int
    max_retained_alternatives: int
    max_replication_relations: int

    def __post_init__(self) -> None:
        _validate_policy(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> CampaignPortfolioPolicy:
        if type(self) is not CampaignPortfolioPolicy:
            raise CampaignPortfolioPolicyError("policy must be an exact CampaignPortfolioPolicy")
        bound = _load_identity(self, "campaign portfolio policy")
        _validate_policy(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise CampaignPortfolioPolicyError("portfolio policy changed after construction")
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-CAMPAIGN-PORTFOLIO-POLICY-V1",
            "max_frontier_size": self.max_frontier_size,
            "min_distinct_hypothesis_roots": self.min_distinct_hypothesis_roots,
            "max_frontier_per_hypothesis_root": self.max_frontier_per_hypothesis_root,
            "max_retained_alternatives": self.max_retained_alternatives,
            "max_replication_relations": self.max_replication_relations,
            "non_authoritative": True,
        }

    def semantic_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())


@dataclass(frozen=True, slots=True, weakref_slot=True)
class CampaignPortfolioFrontierEntry:
    """One deterministic current-frontier node annotated for portfolio decisions."""

    node_id: str
    node_kind: CampaignNodeKind
    artifact_sha256: str
    hypothesis_root_node_ids: tuple[str, ...]
    terminal_outcome: CampaignBranchOutcomeKind | None
    expandable: bool
    depth: int

    def __post_init__(self) -> None:
        _validate_entry(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> CampaignPortfolioFrontierEntry:
        if type(self) is not CampaignPortfolioFrontierEntry:
            raise CampaignPortfolioPolicyError(
                "entry must be an exact CampaignPortfolioFrontierEntry"
            )
        bound = _load_identity(self, "campaign portfolio frontier entry")
        _validate_entry(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise CampaignPortfolioPolicyError(
                "portfolio frontier entry changed after construction"
            )
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "node_kind": self.node_kind.value,
            "artifact_sha256": self.artifact_sha256,
            "hypothesis_root_node_ids": list(self.hypothesis_root_node_ids),
            "terminal_outcome": (
                None if self.terminal_outcome is None else self.terminal_outcome.value
            ),
            "expandable": self.expandable,
            "depth": self.depth,
        }

    def to_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.to_dict())


@dataclass(frozen=True, slots=True, weakref_slot=True)
class CampaignPortfolioFrontier:
    """Construction-bound derived portfolio frontier over an exact campaign snapshot."""

    campaign: ResearchCampaign
    policy: CampaignPortfolioPolicy
    entries: tuple[CampaignPortfolioFrontierEntry, ...]

    def __post_init__(self) -> None:
        _validate_frontier(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> CampaignPortfolioFrontier:
        if type(self) is not CampaignPortfolioFrontier:
            raise CampaignPortfolioPolicyError(
                "frontier must be an exact CampaignPortfolioFrontier"
            )
        bound = _load_identity(self, "campaign portfolio frontier")
        _validate_frontier(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise CampaignPortfolioPolicyError(
                "campaign portfolio frontier changed after construction"
            )
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        campaign = _validated_campaign(self.campaign)
        policy = self.policy._validated_snapshot()
        entries = tuple(item._validated_snapshot() for item in self.entries)
        roots = tuple(
            sorted({root for entry in entries for root in entry.hypothesis_root_node_ids})
        )
        return {
            "format": "MRL-CAMPAIGN-PORTFOLIO-FRONTIER-V1",
            "campaign_sha256": campaign.content_sha256,
            "policy_sha256": policy.content_sha256,
            "entries": [item.to_dict() for item in entries],
            "distinct_hypothesis_root_node_ids": list(roots),
            "non_authoritative": True,
            "can_authorize_execution": False,
            "can_authorize_training": False,
            "can_authorize_promotion": False,
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
    def expandable_node_ids(self) -> tuple[str, ...]:
        frontier = self._validated_snapshot()
        return tuple(item.node_id for item in frontier.entries if item.expandable)

    @property
    def can_authorize_execution(self) -> bool:
        return False

    @property
    def can_authorize_training(self) -> bool:
        return False

    @property
    def can_authorize_promotion(self) -> bool:
        return False


def build_campaign_portfolio_frontier(
    campaign: ResearchCampaign,
    policy: CampaignPortfolioPolicy,
) -> CampaignPortfolioFrontier:
    """Build a deterministic bounded frontier over one exact campaign snapshot."""
    snapshot = _validated_campaign(campaign)
    policy_snapshot = policy._validated_snapshot()
    entries = _derive_entries(snapshot)
    frontier = CampaignPortfolioFrontier(
        campaign=campaign,
        policy=policy,
        entries=entries,
    )
    _enforce_policy(frontier.entries, snapshot, policy_snapshot)
    return frontier


def _validate_frontier(frontier: CampaignPortfolioFrontier) -> None:
    campaign = _validated_campaign(frontier.campaign)
    policy = frontier.policy._validated_snapshot()
    if type(frontier.entries) is not tuple:
        raise CampaignPortfolioPolicyError("entries must be an exact tuple")
    entries = tuple(item._validated_snapshot() for item in frontier.entries)
    node_ids = tuple(item.node_id for item in entries)
    if node_ids != tuple(sorted(set(node_ids))):
        raise CampaignPortfolioPolicyError("frontier entries must be unique and sorted by node_id")
    expected = _derive_entries(campaign)
    if tuple(item.to_dict() for item in entries) != tuple(item.to_dict() for item in expected):
        raise CampaignPortfolioPolicyError(
            "frontier entries do not match the exact canonical campaign frontier"
        )
    _enforce_policy(entries, campaign, policy)


def _derive_entries(
    campaign: ResearchCampaign,
) -> tuple[CampaignPortfolioFrontierEntry, ...]:
    node_by_id = {node.node_id: node for node in campaign.nodes}
    outcome_by_node = {item.terminal_node_id: item.outcome for item in campaign.branch_outcomes}
    entries = tuple(
        CampaignPortfolioFrontierEntry(
            node_id=node_id,
            node_kind=node_by_id[node_id].kind,
            artifact_sha256=node_by_id[node_id].artifact_sha256,
            hypothesis_root_node_ids=_hypothesis_roots(node_id, node_by_id),
            terminal_outcome=outcome_by_node.get(node_id),
            expandable=node_id not in outcome_by_node,
            depth=_node_depth(node_id, node_by_id),
        )
        for node_id in campaign.current_frontier_node_ids
    )
    return tuple(sorted(entries, key=lambda item: item.node_id))


def _hypothesis_roots(
    node_id: str,
    node_by_id: dict[str, CampaignNode],
) -> tuple[str, ...]:
    ancestors: set[str] = set()
    stack = [node_id]
    while stack:
        current_id = stack.pop()
        current = node_by_id[current_id]
        if current.kind is CampaignNodeKind.HYPOTHESIS:
            ancestors.add(current_id)
        stack.extend(current.parent_node_ids)

    if not ancestors:
        return ()

    roots = tuple(
        sorted(
            candidate
            for candidate in ancestors
            if not any(
                parent_id in ancestors for parent_id in node_by_id[candidate].parent_node_ids
            )
        )
    )
    return roots


def _node_depth(node_id: str, node_by_id: dict[str, CampaignNode]) -> int:
    depth_by_id: dict[str, int] = {}
    stack: list[tuple[str, bool]] = [(node_id, False)]
    while stack:
        current_id, expanded = stack.pop()
        if current_id in depth_by_id:
            continue
        node = node_by_id[current_id]
        if expanded:
            depth_by_id[current_id] = (
                0
                if not node.parent_node_ids
                else 1 + max(depth_by_id[parent] for parent in node.parent_node_ids)
            )
            continue
        stack.append((current_id, True))
        for parent_id in node.parent_node_ids:
            if parent_id not in depth_by_id:
                stack.append((parent_id, False))
    return depth_by_id[node_id]


def _enforce_policy(
    entries: tuple[CampaignPortfolioFrontierEntry, ...],
    campaign: ResearchCampaign,
    policy: CampaignPortfolioPolicy,
) -> None:
    if len(entries) > policy.max_frontier_size:
        raise CampaignPortfolioPolicyError("current frontier exceeds max_frontier_size")
    if len(campaign.retained_alternative_node_ids) > policy.max_retained_alternatives:
        raise CampaignPortfolioPolicyError("retained alternatives exceed max_retained_alternatives")
    if len(campaign.replications) > policy.max_replication_relations:
        raise CampaignPortfolioPolicyError("replication relations exceed max_replication_relations")

    roots = tuple(sorted({root for entry in entries for root in entry.hypothesis_root_node_ids}))
    if entries and len(roots) < policy.min_distinct_hypothesis_roots:
        raise CampaignPortfolioPolicyError(
            "current frontier does not satisfy minimum hypothesis-root diversity"
        )
    for root in roots:
        count = sum(root in entry.hypothesis_root_node_ids for entry in entries)
        if count > policy.max_frontier_per_hypothesis_root:
            raise CampaignPortfolioPolicyError(
                "current frontier exceeds per-hypothesis-root concentration limit"
            )


def _validated_campaign(campaign: ResearchCampaign) -> ResearchCampaign:
    if type(campaign) is not ResearchCampaign:
        raise CampaignPortfolioPolicyError("campaign must be an exact ResearchCampaign")
    try:
        return campaign._validated_snapshot()
    except ResearchCampaignError as exc:
        raise CampaignPortfolioPolicyError(
            "campaign failed canonical portfolio revalidation"
        ) from exc


def _validate_policy(policy: CampaignPortfolioPolicy) -> None:
    for label, value, minimum in (
        ("max_frontier_size", policy.max_frontier_size, 1),
        (
            "min_distinct_hypothesis_roots",
            policy.min_distinct_hypothesis_roots,
            0,
        ),
        (
            "max_frontier_per_hypothesis_root",
            policy.max_frontier_per_hypothesis_root,
            1,
        ),
        ("max_retained_alternatives", policy.max_retained_alternatives, 0),
        ("max_replication_relations", policy.max_replication_relations, 0),
    ):
        if type(value) is not int or not minimum <= value <= _MAX_LIMIT:
            raise CampaignPortfolioPolicyError(
                f"{label} must be an exact bounded integer >= {minimum}"
            )
    if policy.min_distinct_hypothesis_roots > policy.max_frontier_size:
        raise CampaignPortfolioPolicyError(
            "min_distinct_hypothesis_roots cannot exceed max_frontier_size"
        )
    if policy.max_frontier_per_hypothesis_root > policy.max_frontier_size:
        raise CampaignPortfolioPolicyError(
            "max_frontier_per_hypothesis_root cannot exceed max_frontier_size"
        )


def _validate_entry(entry: CampaignPortfolioFrontierEntry) -> None:
    if type(entry.node_id) is not str or not entry.node_id:
        raise CampaignPortfolioPolicyError("entry node_id must be non-empty text")
    if type(entry.node_kind) is not CampaignNodeKind:
        raise CampaignPortfolioPolicyError("entry node_kind has an invalid type")
    if type(entry.artifact_sha256) is not str or len(entry.artifact_sha256) != 64:
        raise CampaignPortfolioPolicyError("entry artifact_sha256 must be 64 lowercase hex")
    if any(character not in "0123456789abcdef" for character in entry.artifact_sha256):
        raise CampaignPortfolioPolicyError("entry artifact_sha256 must be 64 lowercase hex")
    if type(entry.hypothesis_root_node_ids) is not tuple:
        raise CampaignPortfolioPolicyError("hypothesis_root_node_ids must be an exact tuple")
    if entry.hypothesis_root_node_ids != tuple(sorted(set(entry.hypothesis_root_node_ids))):
        raise CampaignPortfolioPolicyError("hypothesis_root_node_ids must be unique and sorted")
    if (
        entry.terminal_outcome is not None
        and type(entry.terminal_outcome) is not CampaignBranchOutcomeKind
    ):
        raise CampaignPortfolioPolicyError("terminal_outcome has an invalid type")
    if type(entry.expandable) is not bool:
        raise CampaignPortfolioPolicyError("expandable must be an exact bool")
    if entry.expandable != (entry.terminal_outcome is None):
        raise CampaignPortfolioPolicyError(
            "expandable must be false exactly when a terminal outcome exists"
        )
    if type(entry.depth) is not int or entry.depth < 0:
        raise CampaignPortfolioPolicyError("depth must be an exact nonnegative integer")
