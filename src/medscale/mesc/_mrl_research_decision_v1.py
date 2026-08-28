"""Immutable, content-addressed MRL V1 research decision artifact.

A research decision binds one exact experiment-receipt identity to the exact evidence
artifacts used to judge it, one closed MRL V1 decision state, and the canonical reason
for that judgment. Decisions are scientific records only. They grant no filesystem,
network, model, dataset, GPU, inference, training, promotion, deployment, release, or
clinical authority.
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

__all__ = [
    "ResearchDecision",
    "ResearchDecisionError",
    "ResearchDecisionState",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


class ResearchDecisionError(ValueError):
    """Fail-closed validation error for one MRL research decision."""


class ResearchDecisionState(enum.Enum):
    """Closed non-promotional state set allowed by MRL V1."""

    INVALID = "INVALID"
    REJECT = "REJECT"
    REPLICATE = "REPLICATE"
    RETAIN_LEAD = "RETAIN_LEAD"
    EVIDENCE_CANDIDATE = "EVIDENCE_CANDIDATE"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class ResearchDecision:
    """Content-addressed scientific judgment over one exact receipt and evidence set."""

    receipt_sha256: str
    evidence_sha256s: tuple[str, ...]
    state: ResearchDecisionState
    reason: str

    def __post_init__(self) -> None:
        _validate_decision(self)

    def _validated_snapshot(self) -> ResearchDecision:
        """Rebuild and validate local semantic state before every trust-bearing view."""
        _require_exact_decision(self)
        return ResearchDecision(
            receipt_sha256=self.receipt_sha256,
            evidence_sha256s=self.evidence_sha256s,
            state=self.state,
            reason=self.reason,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        """Serialize one snapshot that has already passed complete validation."""
        return {
            "format": "MRL-RESEARCH-DECISION-V1",
            "receipt_sha256": self.receipt_sha256,
            "evidence_sha256s": list(self.evidence_sha256s),
            "state": self.state.value,
            "reason": self.reason,
            "can_authorize_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return complete semantics from one freshly revalidated snapshot."""
        snapshot = self._validated_snapshot()
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical UTF-8 semantic bytes without self-referential identity."""
        snapshot = self._validated_snapshot()
        return canonical_semantic_bytes(snapshot._semantic_dict_validated())

    @property
    def content_sha256(self) -> str:
        """Derive decision identity outside its own semantic preimage."""
        snapshot = self._validated_snapshot()
        return derive_content_sha256(snapshot._semantic_dict_validated())

    @property
    def can_authorize_promotion(self) -> bool:
        """Return the permanent MRL V1 non-authority invariant."""
        _ = self._validated_snapshot()
        return False

    def to_dict(self) -> dict[str, object]:
        """Return semantic envelope plus the derived decision identity."""
        snapshot = self._validated_snapshot()
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def _validate_decision(decision: ResearchDecision) -> None:
    _require_sha256(decision.receipt_sha256, "receipt_sha256")
    _require_evidence_sha256s(decision.evidence_sha256s)
    _require_exact_state(decision.state)
    _require_text(decision.reason, "reason")


def _require_exact_decision(value: ResearchDecision) -> None:
    if type(value) is not ResearchDecision:
        raise ResearchDecisionError(
            "research decision semantic views require an exact ResearchDecision instance"
        )


def _require_exact_state(value: ResearchDecisionState) -> None:
    if type(value) is not ResearchDecisionState:
        raise ResearchDecisionError(
            "state must be an exact ResearchDecisionState; promotion-authority states are not allowed"
        )


def _require_evidence_sha256s(values: tuple[str, ...]) -> None:
    if type(values) is not tuple:
        raise ResearchDecisionError("evidence_sha256s must be an exact tuple")
    if not values:
        raise ResearchDecisionError("evidence_sha256s cannot be empty")
    for value in values:
        _require_sha256(value, "evidence_sha256s")
    if values != tuple(sorted(set(values))):
        raise ResearchDecisionError("evidence_sha256s must be unique and strictly sorted")


def _require_sha256(value: str, label: str) -> None:
    _require_text(value, label)
    if not _SHA256.fullmatch(value):
        raise ResearchDecisionError(f"{label} must be 64 lowercase hex")


def _require_text(value: str, label: str) -> None:
    if type(value) is not str:
        raise ResearchDecisionError(f"{label} must be an exact string")
    if not value or value != value.strip() or any(char in value for char in "\x00\r\n\t"):
        raise ResearchDecisionError(f"{label} must be non-empty canonical text")
