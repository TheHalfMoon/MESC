"""Evidence data models: enums, state-transition logic, and the frozen EvidenceObject.

Stability: **public-frozen data model** — ``EvidenceObject`` and its identity
derivation are contract (ADR-0017); constructors and field semantics do not change
without an ADR + migration.

An :class:`EvidenceObject` is a validated unit of evidence: one atomic claim, bound to a
source through R1-grade provenance, carrying an explicit verification state and a
declared, mechanical evidence grading. A claim is not evidence; evidence is a claim plus
provenance plus verification state.

Invariants encoded here rather than in prose:

- identity is content-derived (equal content, identical ``evidence_id``);
- identity meaning is versioned explicitly and is independent of container schema version;
- verification-state transitions follow the ADR-0009 state machine;
- a model-extracted claim can never reach ``EXTRACTION_VERIFIED`` without an
  independent human or deterministic-rule check;
- grading is a declared scheme, never an opaque confidence score.
"""

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass
from typing import Final

from medscale.provenance import Provenance, validate_timestamp
from medscale.reproducibility import content_hash

__all__ = [
    "SCHEMA_VERSION",
    "STUDY_DESIGN_LEVEL_SCHEME",
    "EvidenceObject",
    "ExtractionMethod",
    "StudyType",
    "VerificationState",
    "level_from_study_type",
]

SCHEMA_VERSION: Final = "1"

#: The one grading scheme shipped in v1: a deterministic map from study *design* to
#: level. It grades design, not quality of execution (ADR-0009 §4).
STUDY_DESIGN_LEVEL_SCHEME: Final = "medscale-study-design-v1"


class StudyType(enum.Enum):
    SYSTEMATIC_REVIEW = "systematic_review"
    META_ANALYSIS = "meta_analysis"
    RANDOMIZED_CONTROLLED_TRIAL = "randomized_controlled_trial"
    COHORT = "cohort"
    CASE_CONTROL = "case_control"
    CROSS_SECTIONAL = "cross_sectional"
    CASE_REPORT = "case_report"
    PRECLINICAL = "preclinical"
    IN_SILICO = "in_silico"
    OTHER = "other"


class ExtractionMethod(enum.Enum):
    """How the structured fields were produced from the source."""

    HUMAN = "human"
    RULE = "rule"
    MODEL = "model"


class VerificationState(enum.Enum):
    UNVERIFIED = "unverified"
    SOURCE_VERIFIED = "source_verified"
    EXTRACTION_VERIFIED = "extraction_verified"
    DISPUTED = "disputed"
    RETRACTED = "retracted"


_TRANSITIONS: Final[dict[VerificationState, frozenset[VerificationState]]] = {
    VerificationState.UNVERIFIED: frozenset({VerificationState.SOURCE_VERIFIED}),
    VerificationState.SOURCE_VERIFIED: frozenset(
        {
            VerificationState.EXTRACTION_VERIFIED,
            VerificationState.DISPUTED,
            VerificationState.RETRACTED,
        }
    ),
    VerificationState.EXTRACTION_VERIFIED: frozenset(
        {VerificationState.DISPUTED, VerificationState.RETRACTED}
    ),
    VerificationState.DISPUTED: frozenset(
        {VerificationState.EXTRACTION_VERIFIED, VerificationState.RETRACTED}
    ),
    VerificationState.RETRACTED: frozenset(),
}


def level_from_study_type(study_type: StudyType) -> str:
    """Deterministically derive the ``medscale-study-design-v1`` level."""
    from medscale.evidence.grading import _LEVEL_BY_STUDY_TYPE

    return _LEVEL_BY_STUDY_TYPE[study_type]


@dataclass(frozen=True)
class EvidenceObject:
    """One atomic claim with source, provenance, grading, and verification state."""

    claim: str
    study_type: StudyType
    provenance: Provenance
    created_at: str
    source_record_id: str | None = None
    population: str | None = None
    intervention: str | None = None
    comparator: str | None = None
    outcome: str | None = None
    effect_measure: str | None = None
    effect_value: str | None = None
    grading_scheme: str = STUDY_DESIGN_LEVEL_SCHEME
    evidence_level: str = ""
    extraction_method: ExtractionMethod = ExtractionMethod.HUMAN
    verification: VerificationState = VerificationState.UNVERIFIED
    schema_version: str = SCHEMA_VERSION
    identity_version: int = 1

    def __post_init__(self) -> None:
        if not self.claim.strip():
            raise ValueError("claim must be a non-empty atomic assertion")
        if type(self.identity_version) is not int or self.identity_version < 1:
            raise ValueError("identity_version must be a positive int")
        validate_timestamp(self.created_at, "created_at")
        if not self.evidence_level:
            if self.grading_scheme != STUDY_DESIGN_LEVEL_SCHEME:
                raise ValueError(
                    f"evidence_level is required for non-default scheme {self.grading_scheme!r}"
                )
            object.__setattr__(self, "evidence_level", level_from_study_type(self.study_type))

    @property
    def evidence_id(self) -> str:
        """Content-derived identity, stable across schema and verification changes."""
        return content_hash(
            {
                "claim": self.claim,
                "study_type": self.study_type.value,
                "population": self.population,
                "intervention": self.intervention,
                "comparator": self.comparator,
                "outcome": self.outcome,
                "effect_measure": self.effect_measure,
                "effect_value": self.effect_value,
                "source_api": self.provenance.source_api.value,
                "source_identifier": self.provenance.identifier,
                "identity_version": self.identity_version,
            }
        )

    def with_verification(
        self,
        target: VerificationState,
        *,
        checked_by: ExtractionMethod | None = None,
    ) -> EvidenceObject:
        """Return a new object advanced to ``target``, enforcing the state machine.

        Entering ``EXTRACTION_VERIFIED`` requires an explicit ``checked_by`` of HUMAN or
        RULE — a model can never verify its own extraction (ADR-0009 §2).
        """
        if target not in _TRANSITIONS[self.verification]:
            raise ValueError(
                f"illegal verification transition: {self.verification.value} -> {target.value}"
            )
        if target is VerificationState.EXTRACTION_VERIFIED and checked_by not in (
            ExtractionMethod.HUMAN,
            ExtractionMethod.RULE,
        ):
            raise ValueError(
                "EXTRACTION_VERIFIED requires checked_by=HUMAN or RULE; "
                "a model cannot verify its own extraction"
            )
        return dataclasses.replace(self, verification=target)
