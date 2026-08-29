"""Training-example lineage contract for MESC Research Loop V1.

MRL-0601 binds one exact canonical ``TrainingExampleV1`` to its immutable source and
provenance identities without reading source bytes, datasets, models, providers, runtimes,
or training systems. Later contamination and transformation tasks may bind additional
evidence to this lineage identity; they must not rewrite it.

This contract is evidence metadata only. It grants no data access, training execution,
model promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._training_example_contract_v1 import (
    TrainingExampleContractError,
    TrainingExampleV1,
    TrainingMessage,
)

__all__ = [
    "TrainingExampleLineageContract",
    "TrainingExampleLineageError",
    "build_training_example_lineage",
]


class TrainingExampleLineageError(ValueError):
    """Fail-closed validation error for one MRL training-example lineage contract."""


@dataclass(frozen=True, slots=True)
class TrainingExampleLineageContract:
    """Immutable lineage identity derived from one exact canonical training example."""

    example: TrainingExampleV1

    def __post_init__(self) -> None:
        _rebuild_training_example(self.example)

    @property
    def training_example_sha256(self) -> str:
        """Return the deterministic identity of the revalidated training example."""
        return _rebuild_training_example(self.example).example_sha256

    @property
    def can_access_source(self) -> bool:
        """Lineage metadata cannot grant source or dataset access."""
        return False

    @property
    def can_authorize_training(self) -> bool:
        """Lineage metadata cannot authorize training execution."""
        return False

    @property
    def can_authorize_model_promotion(self) -> bool:
        """MRL-0601 cannot make a model-promotion decision."""
        return False

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical evidence-only bytes."""
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        """Return the deterministic lineage-contract identity."""
        return derive_content_sha256(self.semantic_dict())

    def semantic_dict(self) -> dict[str, object]:
        """Return complete immutable lineage semantics after exact revalidation."""
        example = _rebuild_training_example(self.example)
        return {
            "can_access_source": False,
            "can_authorize_model_promotion": False,
            "can_authorize_training": False,
            "evidence_refs": list(example.evidence_refs),
            "example_id": example.example_id,
            "format": "MRL-TRAINING-EXAMPLE-LINEAGE-V1",
            "origin": example.origin,
            "source_id": example.source_id,
            "source_license": example.source_license,
            "source_revision": example.source_revision,
            "source_sha256": example.source_sha256,
            "source_timestamp": example.source_timestamp,
            "synthetic_provenance_sha256": example.synthetic_provenance_sha256,
            "training_example_sha256": example.example_sha256,
            "training_record_id": example.training_record_id,
        }

    def to_dict(self) -> dict[str, object]:
        """Return lineage semantics plus the derived content identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def build_training_example_lineage(
    example: TrainingExampleV1,
) -> TrainingExampleLineageContract:
    """Build one exact, non-authoritative lineage contract."""
    if type(example) is not TrainingExampleV1:
        raise TrainingExampleLineageError("example must be an exact TrainingExampleV1")
    try:
        rebuilt = _rebuild_training_example(example)
    except (AttributeError, TypeError, ValueError, TrainingExampleContractError) as exc:
        raise TrainingExampleLineageError("training example failed canonical revalidation") from exc
    return TrainingExampleLineageContract(example=rebuilt)


def _rebuild_training_example(example: TrainingExampleV1) -> TrainingExampleV1:
    if type(example) is not TrainingExampleV1:
        raise TrainingExampleLineageError("example must be an exact TrainingExampleV1")
    try:
        prompt = tuple(
            TrainingMessage(role=message.role, content=message.content)
            for message in example.prompt
        )
        completion = TrainingMessage(
            role=example.completion.role,
            content=example.completion.content,
        )
        return TrainingExampleV1(
            example_id=example.example_id,
            training_record_id=example.training_record_id,
            source_id=example.source_id,
            source_revision=example.source_revision,
            source_license=example.source_license,
            source_sha256=example.source_sha256,
            source_timestamp=example.source_timestamp,
            origin=example.origin,
            synthetic_provenance_sha256=example.synthetic_provenance_sha256,
            evidence_refs=tuple(example.evidence_refs),
            task_type=example.task_type,
            specialty=example.specialty,
            patient_population=example.patient_population,
            language=example.language,
            training_stage=example.training_stage,
            prompt=prompt,
            completion=completion,
            uncertainty_class=example.uncertainty_class,
            abstention_target=example.abstention_target,
            contradiction_state=example.contradiction_state,
            verification_state=example.verification_state,
            clinician_review_state=example.clinician_review_state,
            contamination_state=example.contamination_state,
            contract_version=example.contract_version,
        )
    except (AttributeError, TypeError, ValueError, TrainingExampleContractError) as exc:
        raise TrainingExampleLineageError("training example failed canonical revalidation") from exc
