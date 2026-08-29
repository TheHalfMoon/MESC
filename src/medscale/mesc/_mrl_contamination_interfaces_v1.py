"""Exact, near, and semantic contamination evidence interfaces for MRL V1.

MRL-0602 records detector evidence against one exact MRL-0601 training-example lineage.
It does not read corpora, execute detectors, access models, or decide training authority.
Detector execution and real corpus access remain separately governed future operations.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

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
    "ContaminationCheckEvidence",
    "ContaminationCheckKind",
    "ContaminationDisposition",
    "ContaminationEvidenceReport",
    "ContaminationInterfaceError",
    "build_contamination_evidence_report",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DECIMAL = re.compile(r"^(?:0|1|0\.[0-9]*[1-9])$")


class ContaminationInterfaceError(ValueError):
    """Fail-closed validation error for contamination evidence interfaces."""


class ContaminationCheckKind(enum.Enum):
    EXACT = "EXACT"
    NEAR = "NEAR"
    SEMANTIC = "SEMANTIC"


class ContaminationDisposition(enum.Enum):
    CLEAR = "CLEAR"
    BLOCKED = "BLOCKED"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True, slots=True)
class ContaminationCheckEvidence:
    """One immutable detector result; similarity thresholds use higher-is-more-similar."""

    kind: ContaminationCheckKind
    detector_id: str
    detector_artifact_sha256: str
    evidence_artifact_sha256: str
    disposition: ContaminationDisposition
    similarity_decimal: str | None = None
    threshold_decimal: str | None = None

    def __post_init__(self) -> None:
        if type(self.kind) is not ContaminationCheckKind:
            raise ContaminationInterfaceError("kind must be an exact ContaminationCheckKind")
        _require_text(self.detector_id, "detector_id")
        _require_sha256(self.detector_artifact_sha256, "detector_artifact_sha256")
        _require_sha256(self.evidence_artifact_sha256, "evidence_artifact_sha256")
        if type(self.disposition) is not ContaminationDisposition:
            raise ContaminationInterfaceError(
                "disposition must be an exact ContaminationDisposition"
            )
        if self.kind is ContaminationCheckKind.EXACT:
            if self.similarity_decimal is not None or self.threshold_decimal is not None:
                raise ContaminationInterfaceError(
                    "exact contamination evidence cannot carry similarity fields"
                )
            return
        if self.disposition is ContaminationDisposition.INDETERMINATE:
            if self.similarity_decimal is not None:
                _require_unit_decimal(self.similarity_decimal, "similarity_decimal")
            if self.threshold_decimal is not None:
                _require_unit_decimal(self.threshold_decimal, "threshold_decimal")
            return
        if self.similarity_decimal is None or self.threshold_decimal is None:
            raise ContaminationInterfaceError(
                "near/semantic clear or blocked evidence requires similarity and threshold"
            )
        similarity = _unit_decimal(self.similarity_decimal, "similarity_decimal")
        threshold = _unit_decimal(self.threshold_decimal, "threshold_decimal")
        expected = (
            ContaminationDisposition.BLOCKED
            if similarity >= threshold
            else ContaminationDisposition.CLEAR
        )
        if self.disposition is not expected:
            raise ContaminationInterfaceError(
                "near/semantic disposition does not match frozen similarity threshold"
            )

    def _validated_snapshot(self) -> ContaminationCheckEvidence:
        if type(self) is not ContaminationCheckEvidence:
            raise ContaminationInterfaceError(
                "check must be an exact ContaminationCheckEvidence"
            )
        return ContaminationCheckEvidence(
            kind=self.kind,
            detector_id=self.detector_id,
            detector_artifact_sha256=self.detector_artifact_sha256,
            evidence_artifact_sha256=self.evidence_artifact_sha256,
            disposition=self.disposition,
            similarity_decimal=self.similarity_decimal,
            threshold_decimal=self.threshold_decimal,
        )

    def _to_dict_validated(self) -> dict[str, object]:
        return {
            "detector_artifact_sha256": self.detector_artifact_sha256,
            "detector_id": self.detector_id,
            "disposition": self.disposition.value,
            "evidence_artifact_sha256": self.evidence_artifact_sha256,
            "kind": self.kind.value,
            "similarity_decimal": self.similarity_decimal,
            "threshold_decimal": self.threshold_decimal,
        }

    def to_dict(self) -> dict[str, object]:
        snapshot = ContaminationCheckEvidence._validated_snapshot(self)
        return snapshot._to_dict_validated()


@dataclass(frozen=True, slots=True)
class ContaminationEvidenceReport:
    """Complete three-interface evidence report for one exact training lineage."""

    training_lineage_sha256: str
    checks: tuple[ContaminationCheckEvidence, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.training_lineage_sha256, "training_lineage_sha256")
        if type(self.checks) is not tuple or len(self.checks) != 3:
            raise ContaminationInterfaceError("checks must contain exactly three interfaces")
        if any(type(item) is not ContaminationCheckEvidence for item in self.checks):
            raise ContaminationInterfaceError("checks contains an invalid item type")
        check_snapshots = tuple(
            ContaminationCheckEvidence._validated_snapshot(item)
            for item in self.checks
        )
        kinds = tuple(item.kind.value for item in check_snapshots)
        expected = tuple(kind.value for kind in ContaminationCheckKind)
        if kinds != expected:
            raise ContaminationInterfaceError("checks must be ordered EXACT, NEAR, SEMANTIC")

    def _validated_snapshot(self) -> ContaminationEvidenceReport:
        if type(self) is not ContaminationEvidenceReport:
            raise ContaminationInterfaceError(
                "report must be an exact ContaminationEvidenceReport"
            )
        if type(self.checks) is not tuple:
            raise ContaminationInterfaceError("checks must be an exact tuple")
        return ContaminationEvidenceReport(
            training_lineage_sha256=self.training_lineage_sha256,
            checks=tuple(
                ContaminationCheckEvidence._validated_snapshot(item) for item in self.checks
            ),
        )

    def _disposition_validated(self) -> ContaminationDisposition:
        if any(item.disposition is ContaminationDisposition.BLOCKED for item in self.checks):
            return ContaminationDisposition.BLOCKED
        if any(
            item.disposition is ContaminationDisposition.INDETERMINATE for item in self.checks
        ):
            return ContaminationDisposition.INDETERMINATE
        return ContaminationDisposition.CLEAR

    @property
    def disposition(self) -> ContaminationDisposition:
        snapshot = ContaminationEvidenceReport._validated_snapshot(self)
        return snapshot._disposition_validated()

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
            "can_authorize_model_promotion": False,
            "can_authorize_training": False,
            "checks": [item._to_dict_validated() for item in self.checks],
            "disposition": self._disposition_validated().value,
            "format": "MRL-CONTAMINATION-EVIDENCE-REPORT-V1",
            "training_lineage_sha256": self.training_lineage_sha256,
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = ContaminationEvidenceReport._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def build_contamination_evidence_report(
    lineage: TrainingExampleLineageContract,
    checks: tuple[ContaminationCheckEvidence, ...],
) -> ContaminationEvidenceReport:
    """Bind supplied detector evidence to one freshly revalidated lineage identity."""
    if type(lineage) is not TrainingExampleLineageContract:
        raise ContaminationInterfaceError("lineage must be an exact TrainingExampleLineageContract")
    try:
        rebuilt = build_training_example_lineage(lineage.example)
    except TrainingExampleLineageError as exc:
        raise ContaminationInterfaceError("training lineage failed canonical revalidation") from exc
    if rebuilt.content_sha256 != lineage.content_sha256:
        raise ContaminationInterfaceError("training lineage identity changed after construction")
    return ContaminationEvidenceReport(
        training_lineage_sha256=rebuilt.content_sha256,
        checks=checks,
    )


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise ContaminationInterfaceError(f"{label} must be canonical non-empty text")
    if any(character.isspace() for character in value):
        raise ContaminationInterfaceError(f"{label} cannot contain whitespace")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ContaminationInterfaceError(f"{label} must be 64 lowercase hex")


def _require_unit_decimal(value: object, label: str) -> None:
    _unit_decimal(value, label)


def _unit_decimal(value: object, label: str) -> Decimal:
    if type(value) is not str or _DECIMAL.fullmatch(value) is None:
        raise ContaminationInterfaceError(f"{label} must be canonical decimal in [0,1]")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise ContaminationInterfaceError(f"{label} must be finite decimal text") from exc
    if not parsed.is_finite() or parsed < 0 or parsed > 1:
        raise ContaminationInterfaceError(f"{label} must be within [0,1]")
    return parsed
