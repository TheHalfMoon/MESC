"""Exact, near, and semantic contamination evidence interfaces for MRL V1.

MRL-0602 records detector evidence against one exact MRL-0601 training-example lineage.
It does not read corpora, execute detectors, access models, or decide training authority.
Detector execution and real corpus access remain separately governed future operations.
"""

from __future__ import annotations

import enum
import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_training_example_lineage_v1 import (
    TrainingExampleLineageContract,
    TrainingExampleLineageError,
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


def _make_check_identity_registry() -> tuple[
    Callable[[ContaminationCheckEvidence, str], None],
    Callable[[ContaminationCheckEvidence], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: ContaminationCheckEvidence, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ContaminationInterfaceError(
                "contamination check construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: ContaminationCheckEvidence) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ContaminationInterfaceError(
                "contamination check construction identity is missing"
            )
        return identity

    return store, load


def _make_report_identity_registry() -> tuple[
    Callable[[ContaminationEvidenceReport, str], None],
    Callable[[ContaminationEvidenceReport], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: ContaminationEvidenceReport, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ContaminationInterfaceError(
                "contamination report construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: ContaminationEvidenceReport) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ContaminationInterfaceError(
                "contamination report construction identity is missing"
            )
        return identity

    return store, load


_store_check_identity, _load_check_identity = _make_check_identity_registry()
_store_report_identity, _load_report_identity = _make_report_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
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
        _validate_check(self)
        _store_check_identity(
            self,
            derive_content_sha256(self._to_dict_validated()),
        )

    def _validated_snapshot(self) -> ContaminationCheckEvidence:
        if type(self) is not ContaminationCheckEvidence:
            raise ContaminationInterfaceError("check must be an exact ContaminationCheckEvidence")
        bound_content_sha256 = _load_check_identity(self)
        _require_sha256(bound_content_sha256, "bound check content_sha256")
        snapshot = ContaminationCheckEvidence(
            kind=self.kind,
            detector_id=self.detector_id,
            detector_artifact_sha256=self.detector_artifact_sha256,
            evidence_artifact_sha256=self.evidence_artifact_sha256,
            disposition=self.disposition,
            similarity_decimal=self.similarity_decimal,
            threshold_decimal=self.threshold_decimal,
        )
        current_content_sha256 = derive_content_sha256(snapshot._to_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise ContaminationInterfaceError(
                "contamination check identity changed after construction"
            )
        return snapshot

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


@dataclass(frozen=True, slots=True, weakref_slot=True)
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
            ContaminationCheckEvidence._validated_snapshot(item) for item in self.checks
        )
        kinds = tuple(item.kind.value for item in check_snapshots)
        expected = tuple(kind.value for kind in ContaminationCheckKind)
        if kinds != expected:
            raise ContaminationInterfaceError("checks must be ordered EXACT, NEAR, SEMANTIC")
        _store_report_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> ContaminationEvidenceReport:
        if type(self) is not ContaminationEvidenceReport:
            raise ContaminationInterfaceError("report must be an exact ContaminationEvidenceReport")
        if type(self.checks) is not tuple:
            raise ContaminationInterfaceError("checks must be an exact tuple")
        bound_content_sha256 = _load_report_identity(self)
        _require_sha256(bound_content_sha256, "bound report content_sha256")
        snapshot = ContaminationEvidenceReport(
            training_lineage_sha256=self.training_lineage_sha256,
            checks=tuple(
                ContaminationCheckEvidence._validated_snapshot(item) for item in self.checks
            ),
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise ContaminationInterfaceError(
                "contamination report identity changed after construction"
            )
        return snapshot

    def _disposition_validated(self) -> ContaminationDisposition:
        if any(item.disposition is ContaminationDisposition.BLOCKED for item in self.checks):
            return ContaminationDisposition.BLOCKED
        if any(item.disposition is ContaminationDisposition.INDETERMINATE for item in self.checks):
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
    """Bind supplied detector evidence to the construction-bound lineage identity."""
    if type(lineage) is not TrainingExampleLineageContract:
        raise ContaminationInterfaceError("lineage must be an exact TrainingExampleLineageContract")
    try:
        _, lineage_sha256 = lineage._validated_example()
    except TrainingExampleLineageError as exc:
        raise ContaminationInterfaceError("training lineage failed canonical revalidation") from exc
    return ContaminationEvidenceReport(
        training_lineage_sha256=lineage_sha256,
        checks=checks,
    )


def _validate_check(value: ContaminationCheckEvidence) -> None:
    if type(value.kind) is not ContaminationCheckKind:
        raise ContaminationInterfaceError("kind must be an exact ContaminationCheckKind")
    _require_text(value.detector_id, "detector_id")
    _require_sha256(value.detector_artifact_sha256, "detector_artifact_sha256")
    _require_sha256(value.evidence_artifact_sha256, "evidence_artifact_sha256")
    if type(value.disposition) is not ContaminationDisposition:
        raise ContaminationInterfaceError("disposition must be an exact ContaminationDisposition")
    if value.kind is ContaminationCheckKind.EXACT:
        if value.similarity_decimal is not None or value.threshold_decimal is not None:
            raise ContaminationInterfaceError(
                "exact contamination evidence cannot carry similarity fields"
            )
        return
    if value.disposition is ContaminationDisposition.INDETERMINATE:
        if value.similarity_decimal is not None:
            _require_unit_decimal(value.similarity_decimal, "similarity_decimal")
        if value.threshold_decimal is not None:
            _require_unit_decimal(value.threshold_decimal, "threshold_decimal")
        return
    if value.similarity_decimal is None or value.threshold_decimal is None:
        raise ContaminationInterfaceError(
            "near/semantic clear or blocked evidence requires similarity and threshold"
        )
    similarity = _unit_decimal(value.similarity_decimal, "similarity_decimal")
    threshold = _unit_decimal(value.threshold_decimal, "threshold_decimal")
    expected = (
        ContaminationDisposition.BLOCKED
        if similarity >= threshold
        else ContaminationDisposition.CLEAR
    )
    if value.disposition is not expected:
        raise ContaminationInterfaceError(
            "near/semantic disposition does not match frozen similarity threshold"
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
