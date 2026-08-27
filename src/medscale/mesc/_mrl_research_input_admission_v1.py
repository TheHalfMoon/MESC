"""Fail-closed, content-addressed MRL V1 research-input admission contract.

The contract classifies candidate inputs before they may enter MRL learning surfaces.
It keeps external evaluation evidence read-only, rejects clinical/product/PHI and other
protected runtime inputs, and prevents declared transformed lineage from laundering a
restricted parent into a more permissive research-learning class.

This module is declarative only. It grants no filesystem, network, model, data, GPU,
inference, training, promotion, deployment, release, or clinical authority.
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
    "ResearchInputAdmissionContract",
    "ResearchInputAdmissionError",
    "ResearchInputClassification",
    "ResearchInputDisposition",
    "ResearchInputParentRef",
    "ResearchLearningSurface",
]

_TOKEN_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")


class ResearchInputAdmissionError(ValueError):
    """Fail-closed validation error for MRL research-input admission semantics."""


class ResearchInputClassification(enum.Enum):
    """Canonical MRL V1 candidate-input classifications."""

    RESEARCH_ARTIFACT = "RESEARCH_ARTIFACT"
    DETERMINISTIC_FIXTURE_OUTPUT = "DETERMINISTIC_FIXTURE_OUTPUT"
    NEGATIVE_OR_INVALID_RESEARCH_RESULT = "NEGATIVE_OR_INVALID_RESEARCH_RESULT"
    EXTERNAL_EVALUATION_EVIDENCE = "EXTERNAL_EVALUATION_EVIDENCE"
    CLINICAL_RUNTIME_STATE = "CLINICAL_RUNTIME_STATE"
    PRODUCT_TELEMETRY = "PRODUCT_TELEMETRY"
    PHI_OR_PATIENT_DATA = "PHI_OR_PATIENT_DATA"
    CREDENTIAL_OR_PROVIDER_CONTROL_STATE = "CREDENTIAL_OR_PROVIDER_CONTROL_STATE"
    SEALED_TIER3_ITEM_CONTENT = "SEALED_TIER3_ITEM_CONTENT"
    UNKNOWN = "UNKNOWN"


class ResearchInputDisposition(enum.Enum):
    """The only admission dispositions derived from input classification."""

    LEARNING_ADMITTED = "LEARNING_ADMITTED"
    EXTERNAL_EVALUATION_ONLY = "EXTERNAL_EVALUATION_ONLY"
    REJECTED = "REJECTED"


class ResearchLearningSurface(enum.Enum):
    """MRL learning surfaces protected by the admission boundary."""

    CAMPAIGN_HISTORY = "CAMPAIGN_HISTORY"
    OBSERVATION = "OBSERVATION"
    PROCEDURE_EXTRACTION = "PROCEDURE_EXTRACTION"
    RESEARCH_SEARCH_INDEX = "RESEARCH_SEARCH_INDEX"


_LEARNING_CLASSIFICATIONS: Final[frozenset[ResearchInputClassification]] = frozenset(
    {
        ResearchInputClassification.RESEARCH_ARTIFACT,
        ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
        ResearchInputClassification.NEGATIVE_OR_INVALID_RESEARCH_RESULT,
    }
)
_REJECTED_CLASSIFICATIONS: Final[frozenset[ResearchInputClassification]] = frozenset(
    {
        ResearchInputClassification.CLINICAL_RUNTIME_STATE,
        ResearchInputClassification.PRODUCT_TELEMETRY,
        ResearchInputClassification.PHI_OR_PATIENT_DATA,
        ResearchInputClassification.CREDENTIAL_OR_PROVIDER_CONTROL_STATE,
        ResearchInputClassification.SEALED_TIER3_ITEM_CONTENT,
        ResearchInputClassification.UNKNOWN,
    }
)


@dataclass(frozen=True, slots=True)
class ResearchInputParentRef:
    """Content-addressed admission identity and classification of one declared parent."""

    admission_sha256: str
    classification: ResearchInputClassification
    disposition: ResearchInputDisposition

    def __post_init__(self) -> None:
        _require_sha256(self.admission_sha256, "admission_sha256")
        _require_exact_enum(self.classification, ResearchInputClassification, "classification")
        _require_exact_enum(self.disposition, ResearchInputDisposition, "disposition")
        expected = _disposition_for_classification(self.classification)
        if self.disposition is not expected:
            raise ResearchInputAdmissionError(
                "parent disposition must exactly match its canonical classification"
            )

    def _validated_snapshot(self) -> ResearchInputParentRef:
        _require_exact_parent_ref(self)
        return ResearchInputParentRef(
            admission_sha256=self.admission_sha256,
            classification=self.classification,
            disposition=self.disposition,
        )

    def to_dict(self) -> dict[str, str]:
        """Return one freshly validated parent-reference semantic mapping."""
        _require_exact_parent_ref(self)
        snapshot = self._validated_snapshot()
        return {
            "admission_sha256": snapshot.admission_sha256,
            "classification": snapshot.classification.value,
            "disposition": snapshot.disposition.value,
        }


@dataclass(frozen=True, slots=True)
class ResearchInputAdmissionContract:
    """Immutable classification and admission envelope for one candidate MRL input."""

    input_id: str
    classification_policy_sha256: str
    classification: ResearchInputClassification
    source_artifact_sha256: str | None
    source_contract_sha256: str | None
    allowed_learning_surfaces: tuple[ResearchLearningSurface, ...]
    transformation_kind: str | None = None
    parent_inputs: tuple[ResearchInputParentRef, ...] = ()

    def __post_init__(self) -> None:
        _require_token(self.input_id, "input_id")
        _require_sha256(self.classification_policy_sha256, "classification_policy_sha256")
        _require_exact_enum(self.classification, ResearchInputClassification, "classification")
        _require_optional_sha256(self.source_artifact_sha256, "source_artifact_sha256")
        _require_optional_sha256(self.source_contract_sha256, "source_contract_sha256")
        _require_learning_surfaces(self.allowed_learning_surfaces)
        _require_parent_refs(self.parent_inputs)
        _require_transformation_lineage(self.transformation_kind, self.parent_inputs)

        disposition = _disposition_for_classification(self.classification)
        if disposition is ResearchInputDisposition.LEARNING_ADMITTED:
            if self.source_artifact_sha256 is None or self.source_contract_sha256 is None:
                raise ResearchInputAdmissionError(
                    "learning-admitted input requires exact source artifact and contract identities"
                )
            if not self.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "learning-admitted input requires at least one explicit learning surface"
                )
        elif disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY:
            if self.source_artifact_sha256 is None or self.source_contract_sha256 is None:
                raise ResearchInputAdmissionError(
                    "external evaluation evidence requires exact artifact and "
                    "governing contract identities"
                )
            if self.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "external evaluation evidence cannot enter an MRL learning surface"
                )
        else:
            if self.source_artifact_sha256 is not None or self.source_contract_sha256 is not None:
                raise ResearchInputAdmissionError(
                    "rejected input cannot carry source artifact or contract identities into MRL"
                )
            if self.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "rejected input cannot enter an MRL learning surface"
                )

        _require_no_lineage_laundering(disposition, self.parent_inputs)

    @property
    def disposition(self) -> ResearchInputDisposition:
        """Return the canonical disposition after fresh exact-type validation."""
        _require_exact_admission(self)
        snapshot = self._validated_snapshot()
        return _disposition_for_classification(snapshot.classification)

    def require_learning_admission(self, surface: ResearchLearningSurface) -> None:
        """Fail closed unless this exact input may enter the requested MRL learning surface."""
        _require_exact_admission(self)
        _require_exact_enum(surface, ResearchLearningSurface, "surface")
        snapshot = self._validated_snapshot()
        if (
            _disposition_for_classification(snapshot.classification)
            is not ResearchInputDisposition.LEARNING_ADMITTED
        ):
            raise ResearchInputAdmissionError("input is not admitted as an MRL learning signal")
        if surface not in snapshot.allowed_learning_surfaces:
            raise ResearchInputAdmissionError(
                f"input is not admitted to learning surface {surface.value!r}"
            )

    def require_external_evaluation_use(self) -> None:
        """Fail closed unless this input is separately classified as external evidence only."""
        _require_exact_admission(self)
        snapshot = self._validated_snapshot()
        if (
            _disposition_for_classification(snapshot.classification)
            is not ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY
        ):
            raise ResearchInputAdmissionError(
                "input is not admitted as separately governed external evaluation evidence"
            )

    def _validated_snapshot(self) -> ResearchInputAdmissionContract:
        _require_exact_admission(self)
        parents = tuple(parent._validated_snapshot() for parent in self.parent_inputs)
        return ResearchInputAdmissionContract(
            input_id=self.input_id,
            classification_policy_sha256=self.classification_policy_sha256,
            classification=self.classification,
            source_artifact_sha256=self.source_artifact_sha256,
            source_contract_sha256=self.source_contract_sha256,
            allowed_learning_surfaces=self.allowed_learning_surfaces,
            transformation_kind=self.transformation_kind,
            parent_inputs=parents,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        disposition = _disposition_for_classification(self.classification)
        return {
            "format": "MRL-RESEARCH-INPUT-ADMISSION-V1",
            "input_id": self.input_id,
            "classification_policy_sha256": self.classification_policy_sha256,
            "classification": self.classification.value,
            "disposition": disposition.value,
            "source_artifact_sha256": self.source_artifact_sha256,
            "source_contract_sha256": self.source_contract_sha256,
            "allowed_learning_surfaces": [
                surface.value for surface in self.allowed_learning_surfaces
            ],
            "transformation_kind": self.transformation_kind,
            "parent_inputs": [parent.to_dict() for parent in self.parent_inputs],
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return complete semantics from one freshly validated local snapshot."""
        _require_exact_admission(self)
        snapshot = self._validated_snapshot()
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical UTF-8 semantic bytes from a fresh snapshot."""
        _require_exact_admission(self)
        snapshot = self._validated_snapshot()
        return canonical_semantic_bytes(snapshot._semantic_dict_validated())

    @property
    def content_sha256(self) -> str:
        """Derive content identity outside the semantic preimage."""
        _require_exact_admission(self)
        snapshot = self._validated_snapshot()
        return derive_content_sha256(snapshot._semantic_dict_validated())

    def to_dict(self) -> dict[str, object]:
        """Return semantic envelope plus derived content identity."""
        _require_exact_admission(self)
        snapshot = self._validated_snapshot()
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def _disposition_for_classification(
    classification: ResearchInputClassification,
) -> ResearchInputDisposition:
    _require_exact_enum(classification, ResearchInputClassification, "classification")
    if classification in _LEARNING_CLASSIFICATIONS:
        return ResearchInputDisposition.LEARNING_ADMITTED
    if classification is ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE:
        return ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY
    if classification in _REJECTED_CLASSIFICATIONS:
        return ResearchInputDisposition.REJECTED
    raise ResearchInputAdmissionError("unsupported research-input classification")


def _require_no_lineage_laundering(
    child_disposition: ResearchInputDisposition,
    parents: tuple[ResearchInputParentRef, ...],
) -> None:
    for parent in parents:
        if (
            parent.disposition is ResearchInputDisposition.REJECTED
            and child_disposition is not ResearchInputDisposition.REJECTED
        ):
            raise ResearchInputAdmissionError(
                "a rejected parent cannot be transformed into an admissible MRL input"
            )
        if (
            parent.disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY
            and child_disposition is ResearchInputDisposition.LEARNING_ADMITTED
        ):
            raise ResearchInputAdmissionError(
                "external evaluation evidence cannot be transformed into an MRL learning signal"
            )


def _require_transformation_lineage(
    transformation_kind: str | None,
    parents: tuple[ResearchInputParentRef, ...],
) -> None:
    if transformation_kind is None:
        if parents:
            raise ResearchInputAdmissionError(
                "parent inputs require an explicit transformation_kind"
            )
        return
    _require_token(transformation_kind, "transformation_kind")
    if not parents:
        raise ResearchInputAdmissionError(
            "transformed input requires at least one parent admission identity"
        )


def _require_parent_refs(parents: tuple[ResearchInputParentRef, ...]) -> None:
    if type(parents) is not tuple:
        raise ResearchInputAdmissionError("parent_inputs must be an exact tuple")
    digests: list[str] = []
    for parent in parents:
        _require_exact_parent_ref(parent)
        snapshot = parent._validated_snapshot()
        digests.append(snapshot.admission_sha256)
    if tuple(digests) != tuple(sorted(set(digests))):
        raise ResearchInputAdmissionError(
            "parent_inputs must be unique and strictly sorted by admission_sha256"
        )


def _require_learning_surfaces(
    surfaces: tuple[ResearchLearningSurface, ...],
) -> None:
    if type(surfaces) is not tuple:
        raise ResearchInputAdmissionError("allowed_learning_surfaces must be an exact tuple")
    values: list[str] = []
    for surface in surfaces:
        _require_exact_enum(surface, ResearchLearningSurface, "learning surface")
        values.append(surface.value)
    if tuple(values) != tuple(sorted(set(values))):
        raise ResearchInputAdmissionError(
            "allowed_learning_surfaces must be unique and strictly sorted"
        )


def _require_exact_admission(value: ResearchInputAdmissionContract) -> None:
    if type(value) is not ResearchInputAdmissionContract:
        raise ResearchInputAdmissionError(
            "research input admission requires an exact ResearchInputAdmissionContract instance"
        )


def _require_exact_parent_ref(value: ResearchInputParentRef) -> None:
    if type(value) is not ResearchInputParentRef:
        raise ResearchInputAdmissionError(
            "parent input reference must be an exact ResearchInputParentRef instance"
        )


def _require_exact_enum(value: object, expected: type[enum.Enum], label: str) -> None:
    if type(value) is not expected:
        raise ResearchInputAdmissionError(f"{label} must be an exact {expected.__name__}")


def _require_token(value: object, label: str) -> None:
    if type(value) is not str or not _TOKEN_ID.fullmatch(value):
        raise ResearchInputAdmissionError(f"{label} must be a canonical token identifier")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or not _SHA256.fullmatch(value):
        raise ResearchInputAdmissionError(f"{label} must be exactly 64 lowercase hex characters")


def _require_optional_sha256(value: object, label: str) -> None:
    if value is None:
        return
    _require_sha256(value, label)
