"""Training-example lineage contract for MESC Research Loop V1.

MRL-0601 binds one exact canonical ``TrainingExampleV1`` to its immutable source and
provenance identities without reading source bytes, datasets, models, providers, runtimes,
or training systems. Later contamination and transformation tasks may bind additional
evidence to this lineage identity; they must not rewrite it.

This contract is evidence metadata only. It grants no data access, training execution,
model promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
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


def _make_lineage_identity_registry() -> tuple[
    Callable[[TrainingExampleLineageContract, str], None],
    Callable[[TrainingExampleLineageContract], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: TrainingExampleLineageContract, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise TrainingExampleLineageError(
                "training lineage construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: TrainingExampleLineageContract) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise TrainingExampleLineageError(
                "training lineage construction identity is missing"
            )
        return identity

    return store, load


_store_lineage_identity, _load_lineage_identity = _make_lineage_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class TrainingExampleLineageContract:
    """Immutable lineage identity derived from one exact canonical training example."""

    example: TrainingExampleV1

    def __post_init__(self) -> None:
        if type(self) is not TrainingExampleLineageContract:
            return
        example = _rebuild_training_example(self.example)
        _store_lineage_identity(
            self,
            derive_content_sha256(_lineage_semantic_dict(example)),
        )

    def _validated_example(self) -> tuple[TrainingExampleV1, str]:
        if type(self) is not TrainingExampleLineageContract:
            raise TrainingExampleLineageError(
                "lineage must be an exact TrainingExampleLineageContract"
            )
        bound_content_sha256 = _load_lineage_identity(self)
        _require_sha256(bound_content_sha256, "bound lineage content_sha256")
        example = _rebuild_training_example(self.example)
        current_content_sha256 = derive_content_sha256(_lineage_semantic_dict(example))
        if current_content_sha256 != bound_content_sha256:
            raise TrainingExampleLineageError(
                "training lineage identity changed after construction"
            )
        return example, bound_content_sha256

    @property
    def training_example_sha256(self) -> str:
        """Return the deterministic identity of the construction-bound training example."""
        example, _ = self._validated_example()
        return example.example_sha256

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
        """Return the immutable lineage-contract construction identity."""
        data = self.semantic_dict()
        return derive_content_sha256(data)

    def semantic_dict(self) -> dict[str, object]:
        """Return complete immutable lineage semantics after exact revalidation."""
        example, _ = self._validated_example()
        return _lineage_semantic_dict(example)

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


def _lineage_semantic_dict(example: TrainingExampleV1) -> dict[str, object]:
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


def _require_sha256(value: object, label: str) -> None:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise TrainingExampleLineageError(f"{label} must be 64 lowercase hex")
