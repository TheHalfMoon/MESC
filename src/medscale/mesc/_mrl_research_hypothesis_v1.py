"""Immutable, content-addressed MRL V1 research hypothesis artifact.

A research hypothesis binds one falsifiable mechanism to the exact objective and
campaign-state identities from which it was created. It is a declarative scientific
artifact only and grants no filesystem, network, model, data, GPU, inference, training,
promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)

__all__ = ["ResearchHypothesis", "ResearchHypothesisError"]

_HYPOTHESIS_ID: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


class ResearchHypothesisError(ValueError):
    """Fail-closed validation error for MRL hypothesis semantics."""


@dataclass(frozen=True, slots=True)
class ResearchHypothesis:
    """Frozen, falsifiable hypothesis bound to exact scientific ancestry."""

    hypothesis_id: str
    objective_sha256: str
    mechanism: str
    predicted_effects: tuple[str, ...]
    predicted_failure_modes: tuple[str, ...]
    falsification_criteria: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    parent_hypothesis_ids: tuple[str, ...]
    created_from_campaign_state_sha256: str

    def __post_init__(self) -> None:
        _require_hypothesis_id(self.hypothesis_id, "hypothesis_id")
        _require_sha256(self.objective_sha256, "objective_sha256")
        _require_text(self.mechanism, "mechanism")
        _require_semantic_statements(self.predicted_effects, "predicted_effects")
        _require_semantic_statements(
            self.predicted_failure_modes,
            "predicted_failure_modes",
        )
        _require_semantic_statements(self.falsification_criteria, "falsification_criteria")
        _require_sorted_unique_refs(self.evidence_refs, "evidence_refs", allow_empty=True)
        _require_parent_hypothesis_ids(
            self.parent_hypothesis_ids,
            hypothesis_id=self.hypothesis_id,
        )
        _require_sha256(
            self.created_from_campaign_state_sha256,
            "created_from_campaign_state_sha256",
        )

    def _validated_snapshot(self) -> ResearchHypothesis:
        """Rebuild and validate one local semantic snapshot before every public view."""
        return ResearchHypothesis(
            hypothesis_id=self.hypothesis_id,
            objective_sha256=self.objective_sha256,
            mechanism=self.mechanism,
            predicted_effects=self.predicted_effects,
            predicted_failure_modes=self.predicted_failure_modes,
            falsification_criteria=self.falsification_criteria,
            evidence_refs=self.evidence_refs,
            parent_hypothesis_ids=self.parent_hypothesis_ids,
            created_from_campaign_state_sha256=self.created_from_campaign_state_sha256,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        """Serialize one snapshot that has just passed complete validation."""
        return {
            "format": "MRL-RESEARCH-HYPOTHESIS-V1",
            "hypothesis_id": self.hypothesis_id,
            "objective_sha256": self.objective_sha256,
            "mechanism": self.mechanism,
            "predicted_effects": list(self.predicted_effects),
            "predicted_failure_modes": list(self.predicted_failure_modes),
            "falsification_criteria": list(self.falsification_criteria),
            "evidence_refs": list(self.evidence_refs),
            "parent_hypothesis_ids": list(self.parent_hypothesis_ids),
            "created_from_campaign_state_sha256": self.created_from_campaign_state_sha256,
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return complete semantics from one freshly revalidated local snapshot."""
        snapshot = self._validated_snapshot()
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical UTF-8 bytes from one freshly revalidated snapshot."""
        snapshot = self._validated_snapshot()
        return canonical_semantic_bytes(snapshot._semantic_dict_validated())

    @property
    def content_sha256(self) -> str:
        """Derive identity from canonical semantics outside the semantic preimage."""
        snapshot = self._validated_snapshot()
        return derive_content_sha256(snapshot._semantic_dict_validated())

    def to_dict(self) -> dict[str, object]:
        """Return semantic envelope plus derived content identity."""
        snapshot = self._validated_snapshot()
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def _require_text(value: str, label: str) -> None:
    if type(value) is not str:
        raise ResearchHypothesisError(f"{label} must be an exact string")
    if not value or value != value.strip() or any(char in value for char in "\x00\r\n\t"):
        raise ResearchHypothesisError(f"{label} must be non-empty canonical text")


def _require_hypothesis_id(value: str, label: str) -> None:
    _require_text(value, label)
    if not _HYPOTHESIS_ID.fullmatch(value):
        raise ResearchHypothesisError(f"{label} must use lowercase kebab-case identifier semantics")


def _require_sha256(value: str, label: str) -> None:
    _require_text(value, label)
    if not _SHA256.fullmatch(value):
        raise ResearchHypothesisError(f"{label} must be 64 lowercase hex")


def _require_semantic_statements(values: tuple[str, ...], label: str) -> None:
    if type(values) is not tuple:
        raise ResearchHypothesisError(f"{label} must be an exact tuple")
    if not values:
        raise ResearchHypothesisError(f"{label} cannot be empty")
    for value in values:
        _require_text(value, label)
    if len(values) != len(set(values)):
        raise ResearchHypothesisError(f"{label} cannot contain duplicate statements")


def _require_sorted_unique_refs(
    values: tuple[str, ...],
    label: str,
    *,
    allow_empty: bool,
) -> None:
    if type(values) is not tuple:
        raise ResearchHypothesisError(f"{label} must be an exact tuple")
    if not values and not allow_empty:
        raise ResearchHypothesisError(f"{label} cannot be empty")
    for value in values:
        _require_text(value, label)
    if values != tuple(sorted(set(values))):
        raise ResearchHypothesisError(f"{label} must be unique and strictly sorted")


def _require_parent_hypothesis_ids(
    values: tuple[str, ...],
    *,
    hypothesis_id: str,
) -> None:
    _require_sorted_unique_refs(values, "parent_hypothesis_ids", allow_empty=True)
    for value in values:
        _require_hypothesis_id(value, "parent_hypothesis_ids")
        if value == hypothesis_id:
            raise ResearchHypothesisError("hypothesis cannot reference itself as a parent")
