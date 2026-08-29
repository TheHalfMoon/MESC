"""Sealed Tier 3 evaluation interface for MESC Research Loop V1.

MRL-0304 defines only the boundary between adaptive research and independent sealed
evaluation. The research side can submit exact artifact identities and later receive an
opaque evidence reference. It never receives sealed item-level content or an iterative
agent-consumable result stream.

MRL-0305 owns the independent sealed-evaluation evidence report. This module grants no
execution, training, promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_objective_v1 import EvaluationTier
from medscale.mesc._mrl_tier_evaluation_contract_v1 import TierEvaluationContract

__all__ = [
    "SealedEvaluationHandoff",
    "SealedEvaluationInterfaceError",
    "SealedEvaluationRequest",
    "build_sealed_evaluation_request",
    "record_sealed_evidence_handoff",
]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


class SealedEvaluationInterfaceError(ValueError):
    """Fail-closed error for the MRL-0304 sealed boundary."""


@dataclass(frozen=True, slots=True)
class SealedEvaluationRequest:
    """Content-addressed request containing identities only, never sealed item content."""

    tier_contract_sha256: str
    candidate_sha256: str
    source_receipt_sha256: str
    evaluator_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.tier_contract_sha256, "tier_contract_sha256")
        _require_sha256(self.candidate_sha256, "candidate_sha256")
        _require_sha256(self.source_receipt_sha256, "source_receipt_sha256")
        _require_sorted_unique_text(self.evaluator_ids, "evaluator_ids")

    @property
    def content_sha256(self) -> str:
        """Return identity derived from canonical request semantics."""
        return derive_content_sha256(self.semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        """Return deterministic bytes for the sealed-evaluation request."""
        return canonical_semantic_bytes(self.semantic_dict())

    def semantic_dict(self) -> dict[str, object]:
        """Return identity-only request semantics."""
        return {
            "candidate_sha256": self.candidate_sha256,
            "evaluator_ids": list(self.evaluator_ids),
            "format": "MRL-SEALED-EVALUATION-REQUEST-V1",
            "source_receipt_sha256": self.source_receipt_sha256,
            "tier": int(EvaluationTier.SEALED),
            "tier_contract_sha256": self.tier_contract_sha256,
        }

    def to_dict(self) -> dict[str, object]:
        """Return request semantics plus derived identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


@dataclass(frozen=True, slots=True)
class SealedEvaluationHandoff:
    """Opaque sealed-evidence reference delivered outside the adaptive result stream."""

    request_sha256: str
    sealed_evidence_ref_sha256: str

    def __post_init__(self) -> None:
        _require_sha256(self.request_sha256, "request_sha256")
        _require_sha256(self.sealed_evidence_ref_sha256, "sealed_evidence_ref_sha256")

    @property
    def content_sha256(self) -> str:
        """Return content identity for the opaque handoff."""
        return derive_content_sha256(self.semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        """Return deterministic bytes without sealed item-level content."""
        return canonical_semantic_bytes(self.semantic_dict())

    def semantic_dict(self) -> dict[str, object]:
        """Return permanent non-iterative and non-authoritative handoff semantics."""
        return {
            "agent_visible_result_fields": [],
            "can_authorize": False,
            "can_authorize_model_promotion": False,
            "format": "MRL-SEALED-EVALUATION-HANDOFF-V1",
            "iterative_agent_result_stream": False,
            "request_sha256": self.request_sha256,
            "sealed_evidence_ref_sha256": self.sealed_evidence_ref_sha256,
            "sealed_item_level_search_context": False,
            "tier": int(EvaluationTier.SEALED),
        }

    def to_dict(self) -> dict[str, object]:
        """Return handoff semantics plus derived identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def build_sealed_evaluation_request(
    tier_contract: TierEvaluationContract,
    candidate_sha256: str,
    source_receipt_sha256: str,
) -> SealedEvaluationRequest:
    """Create an identity-only Tier 3 request from a frozen sealed contract."""
    if type(tier_contract) is not TierEvaluationContract:
        raise SealedEvaluationInterfaceError(
            "tier_contract must be an exact TierEvaluationContract"
        )
    if tier_contract.tier is not EvaluationTier.SEALED:
        raise SealedEvaluationInterfaceError("sealed evaluation requires Tier 3 SEALED")
    tier_contract.semantic_dict()
    evaluator_ids = tuple(
        identity.evaluator_id
        for identity in tier_contract.objective.evaluator_identities
        if EvaluationTier.SEALED in identity.tiers
    )
    if not evaluator_ids:
        raise SealedEvaluationInterfaceError("sealed evaluation requires a bound evaluator")
    return SealedEvaluationRequest(
        tier_contract_sha256=tier_contract.content_sha256,
        candidate_sha256=candidate_sha256,
        source_receipt_sha256=source_receipt_sha256,
        evaluator_ids=evaluator_ids,
    )


def record_sealed_evidence_handoff(
    request: SealedEvaluationRequest,
    sealed_evidence_ref_sha256: str,
) -> SealedEvaluationHandoff:
    """Record only an opaque independent evidence reference for later MRL-0305 use."""
    if type(request) is not SealedEvaluationRequest:
        raise SealedEvaluationInterfaceError("request must be an exact SealedEvaluationRequest")
    return SealedEvaluationHandoff(
        request_sha256=request.content_sha256,
        sealed_evidence_ref_sha256=sealed_evidence_ref_sha256,
    )


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise SealedEvaluationInterfaceError(f"{label} must be 64 lowercase hex")


def _require_sorted_unique_text(values: tuple[str, ...], label: str) -> None:
    if type(values) is not tuple or not values:
        raise SealedEvaluationInterfaceError(f"{label} must be a non-empty exact tuple")
    if any(type(value) is not str or not value or value.strip() != value for value in values):
        raise SealedEvaluationInterfaceError(f"{label} must contain canonical exact strings")
    if values != tuple(sorted(set(values))):
        raise SealedEvaluationInterfaceError(f"{label} must be sorted and unique")
