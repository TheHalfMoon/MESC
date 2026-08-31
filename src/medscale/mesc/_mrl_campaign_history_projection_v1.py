"""Append-only campaign-history projection for MESC Research Loop V1.

MRL-0401 exposes a deterministic derived view over the canonical ``ResearchCampaign``
parent chain. Every historical campaign snapshot remains present in oldest-to-newest
order; later snapshots append entries and cannot rewrite or delete earlier history.

The projection is a query/navigation view only. Canonical campaign artifacts remain the
source of truth, and this module grants no execution, training, promotion, deployment,
release, or clinical authority.
"""

from __future__ import annotations

import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, cast

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_campaign_v1 import ResearchCampaign

__all__ = [
    "CampaignHistoryEntry",
    "CampaignHistoryProjection",
    "CampaignHistoryProjectionError",
    "build_campaign_history_projection",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


class CampaignHistoryProjectionError(ValueError):
    """Fail-closed validation error for the derived MRL campaign-history view."""


def _make_entry_identity_registry() -> tuple[
    Callable[[CampaignHistoryEntry, str], None],
    Callable[[CampaignHistoryEntry], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: CampaignHistoryEntry, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise CampaignHistoryProjectionError(
                "campaign history entry construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: CampaignHistoryEntry) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise CampaignHistoryProjectionError(
                "campaign history entry construction identity is missing"
            )
        return identity

    return store, load


def _make_projection_identity_registry() -> tuple[
    Callable[[CampaignHistoryProjection, str], None],
    Callable[[CampaignHistoryProjection], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: CampaignHistoryProjection, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise CampaignHistoryProjectionError(
                "campaign history projection construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: CampaignHistoryProjection) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise CampaignHistoryProjectionError(
                "campaign history projection construction identity is missing"
            )
        return identity

    return store, load


_store_entry_identity, _load_entry_identity = _make_entry_identity_registry()
_store_projection_identity, _load_projection_identity = _make_projection_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class CampaignHistoryEntry:
    """One immutable canonical campaign snapshot represented in the history view."""

    sequence_index: int
    campaign_sha256: str
    parent_campaign_sha256: str | None
    node_ids: tuple[str, ...]
    branch_outcome_node_ids: tuple[str, ...]
    current_frontier_node_ids: tuple[str, ...]
    procedure_candidate_node_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.sequence_index) is not int or self.sequence_index < 0:
            raise CampaignHistoryProjectionError("sequence_index must be a non-negative exact int")
        _require_sha256(self.campaign_sha256, "campaign_sha256")
        if self.parent_campaign_sha256 is not None:
            _require_sha256(self.parent_campaign_sha256, "parent_campaign_sha256")
        _require_sorted_unique_text(self.node_ids, "node_ids")
        _require_sorted_unique_text(
            self.branch_outcome_node_ids,
            "branch_outcome_node_ids",
            allow_empty=True,
        )
        _require_sorted_unique_text(
            self.current_frontier_node_ids,
            "current_frontier_node_ids",
            allow_empty=True,
        )
        _require_sorted_unique_text(
            self.procedure_candidate_node_ids,
            "procedure_candidate_node_ids",
            allow_empty=True,
        )
        _store_entry_identity(
            self,
            derive_content_sha256(self._to_dict_validated()),
        )

    def _validated_snapshot(self) -> CampaignHistoryEntry:
        if type(self) is not CampaignHistoryEntry:
            raise CampaignHistoryProjectionError(
                "entry must be an exact CampaignHistoryEntry"
            )
        bound_content_sha256 = _load_entry_identity(self)
        _require_sha256(bound_content_sha256, "bound entry content_sha256")
        snapshot = CampaignHistoryEntry(
            sequence_index=self.sequence_index,
            campaign_sha256=self.campaign_sha256,
            parent_campaign_sha256=self.parent_campaign_sha256,
            node_ids=self.node_ids,
            branch_outcome_node_ids=self.branch_outcome_node_ids,
            current_frontier_node_ids=self.current_frontier_node_ids,
            procedure_candidate_node_ids=self.procedure_candidate_node_ids,
        )
        current_content_sha256 = derive_content_sha256(snapshot._to_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise CampaignHistoryProjectionError(
                "campaign history entry identity changed after construction"
            )
        return snapshot

    def _to_dict_validated(self) -> dict[str, object]:
        return {
            "branch_outcome_node_ids": list(self.branch_outcome_node_ids),
            "campaign_sha256": self.campaign_sha256,
            "current_frontier_node_ids": list(self.current_frontier_node_ids),
            "node_ids": list(self.node_ids),
            "parent_campaign_sha256": self.parent_campaign_sha256,
            "procedure_candidate_node_ids": list(self.procedure_candidate_node_ids),
            "sequence_index": self.sequence_index,
        }

    def to_dict(self) -> dict[str, object]:
        """Return freshly revalidated deterministic entry semantics."""
        snapshot = CampaignHistoryEntry._validated_snapshot(self)
        return snapshot._to_dict_validated()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class CampaignHistoryProjection:
    """Deterministic non-authoritative oldest-to-newest campaign history."""

    campaign_id: str
    objective_sha256: str
    entries: tuple[CampaignHistoryEntry, ...]

    def __post_init__(self) -> None:
        _require_text(self.campaign_id, "campaign_id")
        _require_sha256(self.objective_sha256, "objective_sha256")
        if type(self.entries) is not tuple or not self.entries:
            raise CampaignHistoryProjectionError("entries must be a non-empty exact tuple")
        if any(type(entry) is not CampaignHistoryEntry for entry in self.entries):
            raise CampaignHistoryProjectionError("entries contains an invalid item type")

        entry_snapshots = tuple(
            CampaignHistoryEntry._validated_snapshot(entry) for entry in self.entries
        )
        expected_indexes = tuple(range(len(entry_snapshots)))
        observed_indexes = tuple(entry.sequence_index for entry in entry_snapshots)
        if observed_indexes != expected_indexes:
            raise CampaignHistoryProjectionError("entries must use contiguous oldest-first indexes")

        seen_hashes: set[str] = set()
        previous_sha256: str | None = None
        for entry in entry_snapshots:
            if entry.campaign_sha256 in seen_hashes:
                raise CampaignHistoryProjectionError(
                    "campaign history cannot repeat a snapshot hash"
                )
            if entry.parent_campaign_sha256 != previous_sha256:
                raise CampaignHistoryProjectionError(
                    "campaign history parent linkage must match the previous snapshot"
                )
            seen_hashes.add(entry.campaign_sha256)
            previous_sha256 = entry.campaign_sha256
        _store_projection_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> CampaignHistoryProjection:
        if type(self) is not CampaignHistoryProjection:
            raise CampaignHistoryProjectionError(
                "projection must be an exact CampaignHistoryProjection"
            )
        if type(self.entries) is not tuple:
            raise CampaignHistoryProjectionError("entries must be an exact tuple")
        bound_content_sha256 = _load_projection_identity(self)
        _require_sha256(bound_content_sha256, "bound projection content_sha256")
        snapshot = CampaignHistoryProjection(
            campaign_id=self.campaign_id,
            objective_sha256=self.objective_sha256,
            entries=tuple(
                CampaignHistoryEntry._validated_snapshot(entry) for entry in self.entries
            ),
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise CampaignHistoryProjectionError(
                "campaign history projection identity changed after construction"
            )
        return snapshot

    def _latest_campaign_sha256_validated(self) -> str:
        return self.entries[-1].campaign_sha256

    @property
    def latest_campaign_sha256(self) -> str:
        """Return the canonical identity of the newest represented campaign snapshot."""
        snapshot = CampaignHistoryProjection._validated_snapshot(self)
        return snapshot._latest_campaign_sha256_validated()

    @property
    def can_authorize(self) -> bool:
        """Derived history projections can never authorize research execution."""
        return False

    @property
    def content_sha256(self) -> str:
        """Return deterministic identity over the complete derived history view."""
        return derive_content_sha256(self.semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical bytes for the non-authoritative projection."""
        return canonical_semantic_bytes(self.semantic_dict())

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "campaign_id": self.campaign_id,
            "can_authorize": False,
            "entries": [entry._to_dict_validated() for entry in self.entries],
            "format": "MRL-CAMPAIGN-HISTORY-PROJECTION-V1",
            "latest_campaign_sha256": self._latest_campaign_sha256_validated(),
            "objective_sha256": self.objective_sha256,
            "projection_kind": "DERIVED_NON_AUTHORITATIVE",
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return complete derived-view semantics after exact revalidation."""
        snapshot = CampaignHistoryProjection._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    def to_dict(self) -> dict[str, object]:
        """Return projection semantics plus its derived identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def build_campaign_history_projection(campaign: ResearchCampaign) -> CampaignHistoryProjection:
    """Build one append-only history view from one coherent canonical campaign snapshot."""
    if type(campaign) is not ResearchCampaign:
        raise CampaignHistoryProjectionError("campaign must be an exact ResearchCampaign")

    try:
        campaign_snapshot = campaign._validated_snapshot()
        chain = _oldest_first_chain(campaign_snapshot)
        previous_sha256: str | None = None
        entries: list[CampaignHistoryEntry] = []
        for sequence_index, snapshot in enumerate(chain):
            snapshot_sha256 = snapshot.content_sha256
            parent_sha256 = cast(str | None, snapshot.semantic_dict()["parent_campaign_sha256"])
            if parent_sha256 != previous_sha256:
                raise CampaignHistoryProjectionError(
                    "campaign snapshot parent identity does not match canonical history"
                )
            entry = CampaignHistoryEntry(
                sequence_index=sequence_index,
                campaign_sha256=snapshot_sha256,
                parent_campaign_sha256=parent_sha256,
                node_ids=tuple(node.node_id for node in snapshot.nodes),
                branch_outcome_node_ids=tuple(
                    item.terminal_node_id for item in snapshot.branch_outcomes
                ),
                current_frontier_node_ids=snapshot.current_frontier_node_ids,
                procedure_candidate_node_ids=snapshot.procedure_candidate_node_ids,
            )
            entries.append(entry)
            previous_sha256 = snapshot_sha256
    except CampaignHistoryProjectionError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise CampaignHistoryProjectionError(
            "campaign history failed canonical revalidation"
        ) from exc

    return CampaignHistoryProjection(
        campaign_id=campaign_snapshot.campaign_id,
        objective_sha256=campaign_snapshot.objective_sha256,
        entries=tuple(entries),
    )


def _oldest_first_chain(campaign: ResearchCampaign) -> tuple[ResearchCampaign, ...]:
    reverse_chain: list[ResearchCampaign] = []
    seen: set[int] = set()
    current: ResearchCampaign | None = campaign
    while current is not None:
        if type(current) is not ResearchCampaign:
            raise CampaignHistoryProjectionError("campaign parent chain contains an invalid type")
        identity = id(current)
        if identity in seen:
            raise CampaignHistoryProjectionError("campaign parent chain cannot contain a cycle")
        seen.add(identity)
        reverse_chain.append(current)
        current = current.parent
    if not reverse_chain:
        raise CampaignHistoryProjectionError("campaign history cannot be empty")
    return tuple(reversed(reverse_chain))


def _require_sorted_unique_text(
    values: tuple[str, ...],
    label: str,
    *,
    allow_empty: bool = False,
) -> None:
    if type(values) is not tuple:
        raise CampaignHistoryProjectionError(f"{label} must be an exact tuple")
    if not values and not allow_empty:
        raise CampaignHistoryProjectionError(f"{label} cannot be empty")
    for value in values:
        _require_text(value, f"{label} member")
    if values != tuple(sorted(set(values))):
        raise CampaignHistoryProjectionError(f"{label} must be sorted and unique")


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise CampaignHistoryProjectionError(f"{label} must be canonical non-empty text")
    if "\n" in value or "\r" in value:
        raise CampaignHistoryProjectionError(f"{label} must be one line")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CampaignHistoryProjectionError(f"{label} must be 64 lowercase hex")
