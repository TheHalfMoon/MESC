"""Procedure-candidate extraction interface for MESC Research Loop V1.

MRL-0402 binds procedure-candidate references to exact canonical campaign history and the
MRL-0109 research-input admission boundary. Candidate references are derived only after
``PROCEDURE_EXTRACTION`` learning admission succeeds. The repository-controlled permission
trust registry remains authoritative; this module cannot mint or widen trust.

Extraction metadata is non-authoritative. It cannot review or admit a procedure and grants
no filesystem, network, model, dataset, GPU, inference, training, promotion, deployment,
release, or clinical authority.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass

from medscale.mesc._mrl_campaign_history_projection_v1 import (
    CampaignHistoryProjection,
    build_campaign_history_projection,
)
from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_campaign_v1 import (
    CampaignNodeKind,
    ResearchCampaign,
)
from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
    ResearchInputAdmissionError,
    ResearchLearningSurface,
)

__all__ = [
    "ProcedureCandidateExtraction",
    "ProcedureCandidateExtractionError",
    "ProcedureCandidateReference",
    "extract_procedure_candidates",
]


class ProcedureCandidateExtractionError(ValueError):
    """Fail-closed validation error for MRL-0402 candidate extraction."""


def _make_reference_identity_registry() -> tuple[
    Callable[[ProcedureCandidateReference, str], None],
    Callable[[ProcedureCandidateReference], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: ProcedureCandidateReference, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ProcedureCandidateExtractionError(
                "candidate reference construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: ProcedureCandidateReference) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ProcedureCandidateExtractionError(
                "candidate reference construction identity is missing"
            )
        return identity

    return store, load


def _make_extraction_identity_registry() -> tuple[
    Callable[[ProcedureCandidateExtraction, str], None],
    Callable[[ProcedureCandidateExtraction], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: ProcedureCandidateExtraction, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ProcedureCandidateExtractionError(
                "candidate extraction construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: ProcedureCandidateExtraction) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ProcedureCandidateExtractionError(
                "candidate extraction construction identity is missing"
            )
        return identity

    return store, load


_store_reference_identity, _load_reference_identity = _make_reference_identity_registry()
_store_extraction_identity, _load_extraction_identity = _make_extraction_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureCandidateReference:
    """One exact procedure-candidate node bound to one canonical campaign snapshot."""

    sequence_index: int
    campaign_sha256: str
    node_id: str
    artifact_sha256: str

    def __post_init__(self) -> None:
        if type(self.sequence_index) is not int or self.sequence_index < 0:
            raise ProcedureCandidateExtractionError(
                "sequence_index must be a non-negative exact int"
            )
        _require_sha256(self.campaign_sha256, "campaign_sha256")
        _require_text(self.node_id, "node_id")
        _require_sha256(self.artifact_sha256, "artifact_sha256")
        _store_reference_identity(
            self,
            derive_content_sha256(self._to_dict_validated()),
        )

    def _validated_snapshot(self) -> ProcedureCandidateReference:
        if type(self) is not ProcedureCandidateReference:
            raise ProcedureCandidateExtractionError(
                "candidate reference must be an exact ProcedureCandidateReference"
            )
        bound_content_sha256 = _load_reference_identity(self)
        _require_sha256(bound_content_sha256, "bound candidate reference content_sha256")
        snapshot = ProcedureCandidateReference(
            sequence_index=self.sequence_index,
            campaign_sha256=self.campaign_sha256,
            node_id=self.node_id,
            artifact_sha256=self.artifact_sha256,
        )
        current_content_sha256 = derive_content_sha256(snapshot._to_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise ProcedureCandidateExtractionError(
                "candidate reference identity changed after construction"
            )
        return snapshot

    def _to_dict_validated(self) -> dict[str, object]:
        return {
            "artifact_sha256": self.artifact_sha256,
            "campaign_sha256": self.campaign_sha256,
            "node_id": self.node_id,
            "sequence_index": self.sequence_index,
        }

    def to_dict(self) -> dict[str, object]:
        """Return freshly revalidated deterministic candidate-reference semantics."""
        snapshot = ProcedureCandidateReference._validated_snapshot(self)
        return snapshot._to_dict_validated()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureCandidateExtraction:
    """Non-authoritative extraction result after the canonical input gate succeeds."""

    history_projection_sha256: str
    input_admission_sha256: str
    candidates: tuple[ProcedureCandidateReference, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.history_projection_sha256, "history_projection_sha256")
        _require_sha256(self.input_admission_sha256, "input_admission_sha256")
        if type(self.candidates) is not tuple:
            raise ProcedureCandidateExtractionError("candidates must be an exact tuple")
        if any(type(item) is not ProcedureCandidateReference for item in self.candidates):
            raise ProcedureCandidateExtractionError("candidates contains an invalid item type")
        candidate_snapshots = tuple(
            ProcedureCandidateReference._validated_snapshot(item) for item in self.candidates
        )
        keys = tuple((item.sequence_index, item.node_id) for item in candidate_snapshots)
        if keys != tuple(sorted(set(keys))):
            raise ProcedureCandidateExtractionError(
                "candidates must be unique and sorted by sequence index and node id"
            )
        _store_extraction_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> ProcedureCandidateExtraction:
        if type(self) is not ProcedureCandidateExtraction:
            raise ProcedureCandidateExtractionError(
                "extraction must be an exact ProcedureCandidateExtraction"
            )
        if type(self.candidates) is not tuple:
            raise ProcedureCandidateExtractionError("candidates must be an exact tuple")
        bound_content_sha256 = _load_extraction_identity(self)
        _require_sha256(bound_content_sha256, "bound extraction content_sha256")
        snapshot = ProcedureCandidateExtraction(
            history_projection_sha256=self.history_projection_sha256,
            input_admission_sha256=self.input_admission_sha256,
            candidates=tuple(
                ProcedureCandidateReference._validated_snapshot(item) for item in self.candidates
            ),
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise ProcedureCandidateExtractionError(
                "candidate extraction identity changed after construction"
            )
        return snapshot

    @property
    def can_review_procedure(self) -> bool:
        """Extraction cannot create independent review status."""
        return False

    @property
    def can_admit_procedure(self) -> bool:
        """Extraction cannot admit a procedure."""
        return False

    @property
    def can_authorize(self) -> bool:
        """Extraction metadata grants no execution or governance authority."""
        return False

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical extraction bytes."""
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        """Return deterministic extraction identity."""
        return derive_content_sha256(self.semantic_dict())

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "can_admit_procedure": False,
            "can_authorize": False,
            "can_review_procedure": False,
            "candidates": [item._to_dict_validated() for item in self.candidates],
            "format": "MRL-PROCEDURE-CANDIDATE-EXTRACTION-V1",
            "history_projection_sha256": self.history_projection_sha256,
            "input_admission_sha256": self.input_admission_sha256,
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return complete non-authoritative extraction semantics after revalidation."""
        snapshot = ProcedureCandidateExtraction._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    def to_dict(self) -> dict[str, object]:
        """Return extraction semantics plus derived identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def extract_procedure_candidates(
    campaign: ResearchCampaign,
    admission: ResearchInputAdmissionContract,
) -> ProcedureCandidateExtraction:
    """Extract exact refs from one campaign snapshot after stable learning admission."""
    if type(campaign) is not ResearchCampaign:
        raise ProcedureCandidateExtractionError("campaign must be an exact ResearchCampaign")
    if type(admission) is not ResearchInputAdmissionContract:
        raise ProcedureCandidateExtractionError(
            "admission must be an exact ResearchInputAdmissionContract"
        )

    try:
        campaign_snapshot = campaign._validated_snapshot()
        history = build_campaign_history_projection(campaign_snapshot)
        admission_sha256 = _stable_learning_admission_sha256(admission)
        candidates = _derive_candidate_references(campaign_snapshot, history)
    except ResearchInputAdmissionError as exc:
        raise ProcedureCandidateExtractionError(
            "research input is not canonically admitted for procedure extraction"
        ) from exc
    except ProcedureCandidateExtractionError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise ProcedureCandidateExtractionError(
            "procedure-candidate extraction failed canonical revalidation"
        ) from exc

    return ProcedureCandidateExtraction(
        history_projection_sha256=history.content_sha256,
        input_admission_sha256=admission_sha256,
        candidates=candidates,
    )


def _stable_learning_admission_sha256(
    admission: ResearchInputAdmissionContract,
) -> str:
    """Require the same exact admitted identity across two complete trust-gate passes."""
    admission.require_learning_admission(ResearchLearningSurface.PROCEDURE_EXTRACTION)
    first_sha256 = admission.content_sha256
    admission.require_learning_admission(ResearchLearningSurface.PROCEDURE_EXTRACTION)
    second_sha256 = admission.content_sha256
    if first_sha256 != second_sha256:
        raise ProcedureCandidateExtractionError(
            "research input admission identity changed during procedure extraction"
        )
    return second_sha256


def _derive_candidate_references(
    campaign: ResearchCampaign,
    history: CampaignHistoryProjection,
) -> tuple[ProcedureCandidateReference, ...]:
    chain = _oldest_first_chain(campaign)
    if len(chain) != len(history.entries):
        raise ProcedureCandidateExtractionError(
            "campaign chain length does not match its canonical history projection"
        )

    references: list[ProcedureCandidateReference] = []
    for sequence_index, (snapshot, entry) in enumerate(zip(chain, history.entries, strict=True)):
        if snapshot.content_sha256 != entry.campaign_sha256:
            raise ProcedureCandidateExtractionError(
                "campaign snapshot identity does not match its history entry"
            )
        candidate_ids = snapshot.procedure_candidate_node_ids
        if candidate_ids != entry.procedure_candidate_node_ids:
            raise ProcedureCandidateExtractionError(
                "procedure-candidate ids do not match canonical history"
            )
        nodes = {node.node_id: node for node in snapshot.nodes}
        for node_id in candidate_ids:
            node = nodes.get(node_id)
            if node is None or node.kind is not CampaignNodeKind.PROCEDURE_CANDIDATE:
                raise ProcedureCandidateExtractionError(
                    "procedure-candidate history references an invalid campaign node"
                )
            references.append(
                ProcedureCandidateReference(
                    sequence_index=sequence_index,
                    campaign_sha256=entry.campaign_sha256,
                    node_id=node_id,
                    artifact_sha256=node.artifact_sha256,
                )
            )
    return tuple(references)


def _oldest_first_chain(campaign: ResearchCampaign) -> tuple[ResearchCampaign, ...]:
    reverse_chain: list[ResearchCampaign] = []
    seen: set[int] = set()
    current: ResearchCampaign | None = campaign
    while current is not None:
        if type(current) is not ResearchCampaign:
            raise ProcedureCandidateExtractionError(
                "campaign parent chain contains an invalid type"
            )
        identity = id(current)
        if identity in seen:
            raise ProcedureCandidateExtractionError("campaign parent chain cannot contain a cycle")
        seen.add(identity)
        reverse_chain.append(current)
        current = current.parent
    if not reverse_chain:
        raise ProcedureCandidateExtractionError("campaign chain cannot be empty")
    return tuple(reversed(reverse_chain))


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise ProcedureCandidateExtractionError(f"{label} must be canonical non-empty text")
    if "\n" in value or "\r" in value:
        raise ProcedureCandidateExtractionError(f"{label} must be one line")


def _require_sha256(value: object, label: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ProcedureCandidateExtractionError(f"{label} must be 64 lowercase hex")
