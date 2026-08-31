"""Derived retained-alternative, replication, and failure-dedup semantics for MRL-0502..0504.

These artifacts are deterministic views over one exact canonical ``ResearchCampaign`` and
its MRL-0501 portfolio frontier. They preserve every historical branch occurrence while
providing explicit retained-alternative semantics, replication relationships, and
deduplicated failure signatures.

This module is non-authoritative. It grants no filesystem, network, model, data, GPU,
training, promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_campaign_portfolio_policy_v1 import (
    CampaignPortfolioFrontier,
    CampaignPortfolioPolicyError,
)
from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_campaign_v1 import (
    CampaignBranchOutcome,
    CampaignBranchOutcomeKind,
    CampaignNode,
    CampaignNodeKind,
    CampaignReplicationRelation,
    ResearchCampaign,
    ResearchCampaignError,
)

__all__ = [
    "CampaignBranchSemantics",
    "CampaignBranchSemanticsError",
    "FailureSignatureGroup",
    "ReplicationBranch",
    "RetainedAlternativeBranch",
    "build_campaign_branch_semantics",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)


class CampaignBranchSemanticsError(ValueError):
    """Fail-closed validation error for MRL-0502..0504 branch semantics."""


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
            raise CampaignBranchSemanticsError(
                "branch-semantics construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: object, label: str) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise CampaignBranchSemanticsError(f"{label} construction identity is missing")
        return identity

    return store, load


_store_identity, _load_identity = _make_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class RetainedAlternativeBranch:
    """One retained campaign node, preserved as a non-authoritative alternative branch."""

    node_id: str
    node_kind: CampaignNodeKind
    artifact_sha256: str
    hypothesis_root_node_ids: tuple[str, ...]
    terminal_outcome: CampaignBranchOutcomeKind | None
    on_current_frontier: bool
    expandable: bool

    def __post_init__(self) -> None:
        _validate_retained(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> RetainedAlternativeBranch:
        if type(self) is not RetainedAlternativeBranch:
            raise CampaignBranchSemanticsError(
                "retained branch must be an exact RetainedAlternativeBranch"
            )
        bound = _load_identity(self, "retained alternative branch")
        _validate_retained(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise CampaignBranchSemanticsError(
                "retained alternative branch changed after construction"
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
            "on_current_frontier": self.on_current_frontier,
            "expandable": self.expandable,
        }

    def to_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.to_dict())


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ReplicationBranch:
    """One exact canonical campaign replication relationship."""

    source_node_id: str
    replica_node_id: str
    evidence_sha256s: tuple[str, ...]
    source_node_kind: CampaignNodeKind
    replica_node_kind: CampaignNodeKind
    source_hypothesis_root_node_ids: tuple[str, ...]
    replica_hypothesis_root_node_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_replication(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> ReplicationBranch:
        if type(self) is not ReplicationBranch:
            raise CampaignBranchSemanticsError("replication must be an exact ReplicationBranch")
        bound = _load_identity(self, "replication branch")
        _validate_replication(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise CampaignBranchSemanticsError("replication branch changed after construction")
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "source_node_id": self.source_node_id,
            "replica_node_id": self.replica_node_id,
            "evidence_sha256s": list(self.evidence_sha256s),
            "source_node_kind": self.source_node_kind.value,
            "replica_node_kind": self.replica_node_kind.value,
            "source_hypothesis_root_node_ids": list(self.source_hypothesis_root_node_ids),
            "replica_hypothesis_root_node_ids": list(self.replica_hypothesis_root_node_ids),
        }

    def to_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.to_dict())


@dataclass(frozen=True, slots=True, weakref_slot=True)
class FailureSignatureGroup:
    """One deduplicated failure signature while preserving all exact occurrences."""

    signature_sha256: str
    outcome: CampaignBranchOutcomeKind
    terminal_node_kind: CampaignNodeKind
    normalized_reason: str
    occurrence_node_ids: tuple[str, ...]
    evidence_sha256s: tuple[str, ...]

    def __post_init__(self) -> None:
        _validate_failure_group(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> FailureSignatureGroup:
        if type(self) is not FailureSignatureGroup:
            raise CampaignBranchSemanticsError(
                "failure group must be an exact FailureSignatureGroup"
            )
        bound = _load_identity(self, "failure signature group")
        _validate_failure_group(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise CampaignBranchSemanticsError("failure signature group changed after construction")
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "signature_sha256": self.signature_sha256,
            "outcome": self.outcome.value,
            "terminal_node_kind": self.terminal_node_kind.value,
            "normalized_reason": self.normalized_reason,
            "occurrence_node_ids": list(self.occurrence_node_ids),
            "evidence_sha256s": list(self.evidence_sha256s),
            "occurrence_count": len(self.occurrence_node_ids),
            "duplicate_count": max(0, len(self.occurrence_node_ids) - 1),
        }

    def to_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.to_dict())


@dataclass(frozen=True, slots=True, weakref_slot=True)
class CampaignBranchSemantics:
    """Construction-bound MRL-0502..0504 derived branch view."""

    campaign: ResearchCampaign
    portfolio_frontier: CampaignPortfolioFrontier
    retained_alternatives: tuple[RetainedAlternativeBranch, ...]
    replications: tuple[ReplicationBranch, ...]
    failure_signatures: tuple[FailureSignatureGroup, ...]

    def __post_init__(self) -> None:
        _validate_semantics(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> CampaignBranchSemantics:
        if type(self) is not CampaignBranchSemantics:
            raise CampaignBranchSemanticsError(
                "branch semantics must be an exact CampaignBranchSemantics"
            )
        bound = _load_identity(self, "campaign branch semantics")
        _validate_semantics(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise CampaignBranchSemanticsError(
                "campaign branch semantics changed after construction"
            )
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        campaign = _validated_campaign(self.campaign)
        frontier = _validated_frontier(self.portfolio_frontier)
        retained = tuple(item._validated_snapshot() for item in self.retained_alternatives)
        replications = tuple(item._validated_snapshot() for item in self.replications)
        failures = tuple(item._validated_snapshot() for item in self.failure_signatures)
        return {
            "format": "MRL-CAMPAIGN-BRANCH-SEMANTICS-V1",
            "campaign_sha256": campaign.content_sha256,
            "portfolio_frontier_sha256": frontier.content_sha256,
            "retained_alternatives": [item.to_dict() for item in retained],
            "replications": [item.to_dict() for item in replications],
            "failure_signatures": [item.to_dict() for item in failures],
            "failure_occurrence_count": sum(len(item.occurrence_node_ids) for item in failures),
            "unique_failure_signature_count": len(failures),
            "repeated_known_failure_count": sum(
                max(0, len(item.occurrence_node_ids) - 1) for item in failures
            ),
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
    def repeated_known_failure_count(self) -> int:
        semantics = self._validated_snapshot()
        return sum(
            max(0, len(item.occurrence_node_ids) - 1) for item in semantics.failure_signatures
        )

    @property
    def can_authorize_execution(self) -> bool:
        return False

    @property
    def can_authorize_training(self) -> bool:
        return False

    @property
    def can_authorize_promotion(self) -> bool:
        return False


def build_campaign_branch_semantics(
    campaign: ResearchCampaign,
    portfolio_frontier: CampaignPortfolioFrontier,
) -> CampaignBranchSemantics:
    """Derive exact retained, replication, and failure-dedup views from one campaign."""
    snapshot = _validated_campaign(campaign)
    frontier = _validated_frontier(portfolio_frontier)
    if frontier.campaign.content_sha256 != snapshot.content_sha256:
        raise CampaignBranchSemanticsError(
            "portfolio frontier does not bind the exact supplied campaign"
        )

    node_by_id = {node.node_id: node for node in snapshot.nodes}
    outcome_by_node = {item.terminal_node_id: item for item in snapshot.branch_outcomes}
    retained = tuple(
        RetainedAlternativeBranch(
            node_id=node_id,
            node_kind=node_by_id[node_id].kind,
            artifact_sha256=node_by_id[node_id].artifact_sha256,
            hypothesis_root_node_ids=_hypothesis_roots(node_id, node_by_id),
            terminal_outcome=(
                None if node_id not in outcome_by_node else outcome_by_node[node_id].outcome
            ),
            on_current_frontier=node_id in snapshot.current_frontier_node_ids,
            expandable=node_id not in outcome_by_node,
        )
        for node_id in snapshot.retained_alternative_node_ids
    )
    replications = tuple(_replication_view(item, node_by_id) for item in snapshot.replications)
    failures = _failure_groups(snapshot.branch_outcomes, node_by_id)
    return CampaignBranchSemantics(
        campaign=campaign,
        portfolio_frontier=portfolio_frontier,
        retained_alternatives=retained,
        replications=replications,
        failure_signatures=failures,
    )


def _validate_semantics(value: CampaignBranchSemantics) -> None:
    campaign = _validated_campaign(value.campaign)
    frontier = _validated_frontier(value.portfolio_frontier)
    if frontier.campaign.content_sha256 != campaign.content_sha256:
        raise CampaignBranchSemanticsError(
            "portfolio frontier does not bind the exact supplied campaign"
        )
    if type(value.retained_alternatives) is not tuple:
        raise CampaignBranchSemanticsError("retained_alternatives must be an exact tuple")
    if type(value.replications) is not tuple:
        raise CampaignBranchSemanticsError("replications must be an exact tuple")
    if type(value.failure_signatures) is not tuple:
        raise CampaignBranchSemanticsError("failure_signatures must be an exact tuple")

    retained = tuple(item._validated_snapshot() for item in value.retained_alternatives)
    replications = tuple(item._validated_snapshot() for item in value.replications)
    failures = tuple(item._validated_snapshot() for item in value.failure_signatures)

    node_by_id = {node.node_id: node for node in campaign.nodes}
    outcome_by_node = {item.terminal_node_id: item for item in campaign.branch_outcomes}
    expected_retained = tuple(
        RetainedAlternativeBranch(
            node_id=node_id,
            node_kind=node_by_id[node_id].kind,
            artifact_sha256=node_by_id[node_id].artifact_sha256,
            hypothesis_root_node_ids=_hypothesis_roots(node_id, node_by_id),
            terminal_outcome=(
                None if node_id not in outcome_by_node else outcome_by_node[node_id].outcome
            ),
            on_current_frontier=node_id in campaign.current_frontier_node_ids,
            expandable=node_id not in outcome_by_node,
        )
        for node_id in campaign.retained_alternative_node_ids
    )
    expected_replications = tuple(
        _replication_view(item, node_by_id) for item in campaign.replications
    )
    expected_failures = _failure_groups(campaign.branch_outcomes, node_by_id)

    if tuple(item.to_dict() for item in retained) != tuple(
        item.to_dict() for item in expected_retained
    ):
        raise CampaignBranchSemanticsError(
            "retained alternatives do not match the exact canonical campaign"
        )
    if tuple(item.to_dict() for item in replications) != tuple(
        item.to_dict() for item in expected_replications
    ):
        raise CampaignBranchSemanticsError(
            "replication branches do not match the exact canonical campaign"
        )
    if tuple(item.to_dict() for item in failures) != tuple(
        item.to_dict() for item in expected_failures
    ):
        raise CampaignBranchSemanticsError(
            "failure signatures do not match the exact canonical campaign"
        )


def _replication_view(
    relation: CampaignReplicationRelation,
    node_by_id: dict[str, CampaignNode],
) -> ReplicationBranch:
    return ReplicationBranch(
        source_node_id=relation.source_node_id,
        replica_node_id=relation.replica_node_id,
        evidence_sha256s=relation.evidence_sha256s,
        source_node_kind=node_by_id[relation.source_node_id].kind,
        replica_node_kind=node_by_id[relation.replica_node_id].kind,
        source_hypothesis_root_node_ids=_hypothesis_roots(relation.source_node_id, node_by_id),
        replica_hypothesis_root_node_ids=_hypothesis_roots(relation.replica_node_id, node_by_id),
    )


def _failure_groups(
    outcomes: tuple[CampaignBranchOutcome, ...],
    node_by_id: dict[str, CampaignNode],
) -> tuple[FailureSignatureGroup, ...]:
    grouped: dict[
        str,
        tuple[CampaignBranchOutcomeKind, CampaignNodeKind, str, list[str], set[str]],
    ] = {}
    for outcome in outcomes:
        node = node_by_id[outcome.terminal_node_id]
        normalized_reason = _normalize_reason(outcome.reason)
        signature = _failure_signature(
            outcome.outcome,
            node.kind,
            normalized_reason,
        )
        existing = grouped.get(signature)
        if existing is None:
            grouped[signature] = (
                outcome.outcome,
                node.kind,
                normalized_reason,
                [outcome.terminal_node_id],
                set(outcome.evidence_sha256s),
            )
            continue
        existing[3].append(outcome.terminal_node_id)
        existing[4].update(outcome.evidence_sha256s)

    return tuple(
        FailureSignatureGroup(
            signature_sha256=signature,
            outcome=values[0],
            terminal_node_kind=values[1],
            normalized_reason=values[2],
            occurrence_node_ids=tuple(sorted(values[3])),
            evidence_sha256s=tuple(sorted(values[4])),
        )
        for signature, values in sorted(grouped.items())
    )


def _failure_signature(
    outcome: CampaignBranchOutcomeKind,
    node_kind: CampaignNodeKind,
    normalized_reason: str,
) -> str:
    return derive_content_sha256(
        {
            "format": "MRL-FAILURE-SIGNATURE-V1",
            "outcome": outcome.value,
            "terminal_node_kind": node_kind.value,
            "normalized_reason": normalized_reason,
        }
    )


def _normalize_reason(reason: str) -> str:
    if type(reason) is not str:
        raise CampaignBranchSemanticsError("failure reason must be text")
    normalized = " ".join(reason.split()).casefold()
    if not normalized:
        raise CampaignBranchSemanticsError("failure reason cannot be empty")
    return normalized


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
    return tuple(
        sorted(
            candidate
            for candidate in ancestors
            if not any(
                parent_id in ancestors for parent_id in node_by_id[candidate].parent_node_ids
            )
        )
    )


def _validated_campaign(campaign: ResearchCampaign) -> ResearchCampaign:
    if type(campaign) is not ResearchCampaign:
        raise CampaignBranchSemanticsError("campaign must be an exact ResearchCampaign")
    try:
        return campaign._validated_snapshot()
    except ResearchCampaignError as exc:
        raise CampaignBranchSemanticsError(
            "campaign failed canonical branch-semantics revalidation"
        ) from exc


def _validated_frontier(frontier: CampaignPortfolioFrontier) -> CampaignPortfolioFrontier:
    if type(frontier) is not CampaignPortfolioFrontier:
        raise CampaignBranchSemanticsError(
            "portfolio_frontier must be an exact CampaignPortfolioFrontier"
        )
    try:
        return frontier._validated_snapshot()
    except CampaignPortfolioPolicyError as exc:
        raise CampaignBranchSemanticsError(
            "portfolio frontier failed branch-semantics revalidation"
        ) from exc


def _validate_retained(value: RetainedAlternativeBranch) -> None:
    _require_text(value.node_id, "retained node_id")
    if type(value.node_kind) is not CampaignNodeKind:
        raise CampaignBranchSemanticsError("retained node_kind has an invalid type")
    _require_sha256(value.artifact_sha256, "retained artifact_sha256")
    _require_sorted_unique_texts(
        value.hypothesis_root_node_ids,
        "retained hypothesis_root_node_ids",
    )
    if (
        value.terminal_outcome is not None
        and type(value.terminal_outcome) is not CampaignBranchOutcomeKind
    ):
        raise CampaignBranchSemanticsError("retained terminal_outcome has an invalid type")
    if type(value.on_current_frontier) is not bool:
        raise CampaignBranchSemanticsError("on_current_frontier must be an exact bool")
    if type(value.expandable) is not bool:
        raise CampaignBranchSemanticsError("expandable must be an exact bool")
    if value.terminal_outcome is not None and value.expandable:
        raise CampaignBranchSemanticsError("terminal retained alternative cannot be expandable")


def _validate_replication(value: ReplicationBranch) -> None:
    _require_text(value.source_node_id, "replication source_node_id")
    _require_text(value.replica_node_id, "replication replica_node_id")
    if value.source_node_id == value.replica_node_id:
        raise CampaignBranchSemanticsError("replication source and replica must differ")
    _require_sorted_unique_sha256s(value.evidence_sha256s, "replication evidence_sha256s")
    if type(value.source_node_kind) is not CampaignNodeKind:
        raise CampaignBranchSemanticsError("source_node_kind has an invalid type")
    if type(value.replica_node_kind) is not CampaignNodeKind:
        raise CampaignBranchSemanticsError("replica_node_kind has an invalid type")
    _require_sorted_unique_texts(
        value.source_hypothesis_root_node_ids,
        "source_hypothesis_root_node_ids",
    )
    _require_sorted_unique_texts(
        value.replica_hypothesis_root_node_ids,
        "replica_hypothesis_root_node_ids",
    )


def _validate_failure_group(value: FailureSignatureGroup) -> None:
    _require_sha256(value.signature_sha256, "failure signature_sha256")
    if type(value.outcome) is not CampaignBranchOutcomeKind:
        raise CampaignBranchSemanticsError("failure outcome has an invalid type")
    if type(value.terminal_node_kind) is not CampaignNodeKind:
        raise CampaignBranchSemanticsError("failure terminal_node_kind has an invalid type")
    if _normalize_reason(value.normalized_reason) != value.normalized_reason:
        raise CampaignBranchSemanticsError("failure normalized_reason is not canonical")
    _require_sorted_unique_texts(value.occurrence_node_ids, "failure occurrence_node_ids")
    if not value.occurrence_node_ids:
        raise CampaignBranchSemanticsError("failure group must preserve at least one occurrence")
    _require_sorted_unique_sha256s(value.evidence_sha256s, "failure evidence_sha256s")
    expected = _failure_signature(
        value.outcome,
        value.terminal_node_kind,
        value.normalized_reason,
    )
    if value.signature_sha256 != expected:
        raise CampaignBranchSemanticsError("failure signature identity is inconsistent")


def _require_text(value: str, label: str) -> None:
    if type(value) is not str or not value:
        raise CampaignBranchSemanticsError(f"{label} must be non-empty text")


def _require_sha256(value: str, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CampaignBranchSemanticsError(f"{label} must be 64 lowercase hex")


def _require_sorted_unique_texts(values: tuple[str, ...], label: str) -> None:
    if type(values) is not tuple or any(type(item) is not str or not item for item in values):
        raise CampaignBranchSemanticsError(f"{label} must be an exact tuple of non-empty text")
    if values != tuple(sorted(set(values))):
        raise CampaignBranchSemanticsError(f"{label} must be unique and sorted")


def _require_sorted_unique_sha256s(values: tuple[str, ...], label: str) -> None:
    if type(values) is not tuple:
        raise CampaignBranchSemanticsError(f"{label} must be an exact tuple")
    for value in values:
        _require_sha256(value, label)
    if values != tuple(sorted(set(values))):
        raise CampaignBranchSemanticsError(f"{label} must be unique and sorted")
