"""Teacher, prompt, and source transformation bindings for MRL V1.

MRL-0603 binds one exact MRL-0601 training-example lineage to immutable transformation
artifact identities. It records provenance only; it does not execute prompts, call teacher
models, read sources, or authorize training.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_training_example_lineage_v1 import (
    TrainingExampleLineageContract,
    TrainingExampleLineageError,
    build_training_example_lineage,
)

__all__ = [
    "TrainingTransformationBinding",
    "TrainingTransformationBindingError",
    "build_training_transformation_binding",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class TrainingTransformationBindingError(ValueError):
    """Fail-closed validation error for MRL training transformation provenance."""


@dataclass(frozen=True, slots=True)
class TrainingTransformationBinding:
    """Immutable source/prompt/teacher provenance for one exact training lineage."""

    training_lineage_sha256: str
    source_sha256: str
    transformation_kind: str
    transformation_artifact_sha256: str
    prompt_template_sha256: str | None
    teacher_model_sha256: str | None
    teacher_output_sha256: str | None

    def __post_init__(self) -> None:
        _require_sha256(self.training_lineage_sha256, "training_lineage_sha256")
        _require_sha256(self.source_sha256, "source_sha256")
        _require_text(self.transformation_kind, "transformation_kind")
        _require_sha256(
            self.transformation_artifact_sha256,
            "transformation_artifact_sha256",
        )
        _require_optional_sha256(self.prompt_template_sha256, "prompt_template_sha256")
        _require_optional_sha256(self.teacher_model_sha256, "teacher_model_sha256")
        _require_optional_sha256(self.teacher_output_sha256, "teacher_output_sha256")
        if (self.teacher_model_sha256 is None) != (self.teacher_output_sha256 is None):
            raise TrainingTransformationBindingError(
                "teacher model and teacher output identities must be supplied together"
            )

    def _validated_snapshot(self) -> TrainingTransformationBinding:
        if type(self) is not TrainingTransformationBinding:
            raise TrainingTransformationBindingError(
                "binding must be an exact TrainingTransformationBinding"
            )
        return TrainingTransformationBinding(
            training_lineage_sha256=self.training_lineage_sha256,
            source_sha256=self.source_sha256,
            transformation_kind=self.transformation_kind,
            transformation_artifact_sha256=self.transformation_artifact_sha256,
            prompt_template_sha256=self.prompt_template_sha256,
            teacher_model_sha256=self.teacher_model_sha256,
            teacher_output_sha256=self.teacher_output_sha256,
        )

    @property
    def can_access_source(self) -> bool:
        return False

    @property
    def can_invoke_teacher(self) -> bool:
        return False

    @property
    def can_authorize_training(self) -> bool:
        return False

    @property
    def can_authorize_model_promotion(self) -> bool:
        return False

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "can_access_source": False,
            "can_authorize_model_promotion": False,
            "can_authorize_training": False,
            "can_invoke_teacher": False,
            "format": "MRL-TRAINING-TRANSFORMATION-BINDING-V1",
            "prompt_template_sha256": self.prompt_template_sha256,
            "source_sha256": self.source_sha256,
            "teacher_model_sha256": self.teacher_model_sha256,
            "teacher_output_sha256": self.teacher_output_sha256,
            "training_lineage_sha256": self.training_lineage_sha256,
            "transformation_artifact_sha256": self.transformation_artifact_sha256,
            "transformation_kind": self.transformation_kind,
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = TrainingTransformationBinding._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def build_training_transformation_binding(
    lineage: TrainingExampleLineageContract,
    *,
    transformation_kind: str,
    transformation_artifact_sha256: str,
    prompt_template_sha256: str | None = None,
    teacher_model_sha256: str | None = None,
    teacher_output_sha256: str | None = None,
) -> TrainingTransformationBinding:
    """Bind caller-supplied transformation identities to one revalidated lineage."""
    if type(lineage) is not TrainingExampleLineageContract:
        raise TrainingTransformationBindingError(
            "lineage must be an exact TrainingExampleLineageContract"
        )
    try:
        rebuilt = build_training_example_lineage(lineage.example)
    except TrainingExampleLineageError as exc:
        raise TrainingTransformationBindingError(
            "training lineage failed canonical revalidation"
        ) from exc
    if rebuilt.content_sha256 != lineage.content_sha256:
        raise TrainingTransformationBindingError(
            "training lineage identity changed after construction"
        )
    return TrainingTransformationBinding(
        training_lineage_sha256=rebuilt.content_sha256,
        source_sha256=rebuilt.example.source_sha256,
        transformation_kind=transformation_kind,
        transformation_artifact_sha256=transformation_artifact_sha256,
        prompt_template_sha256=prompt_template_sha256,
        teacher_model_sha256=teacher_model_sha256,
        teacher_output_sha256=teacher_output_sha256,
    )


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise TrainingTransformationBindingError(f"{label} must be canonical non-empty text")
    if any(character.isspace() for character in value):
        raise TrainingTransformationBindingError(f"{label} cannot contain whitespace")


def _require_optional_sha256(value: object, label: str) -> None:
    if value is not None:
        _require_sha256(value, label)


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise TrainingTransformationBindingError(f"{label} must be 64 lowercase hex")
