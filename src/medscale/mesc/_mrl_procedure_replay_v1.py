"""Deterministic fixture-only procedure replay harness for MRL V1.

MRL-0403 replays one exact research procedure against the canonical in-memory fixture
research surface and records the result as immutable evidence. Replay evidence does not
advance the independent procedure-admission lifecycle by itself and grants no model,
data, network, GPU, inference, training, promotion, deployment, release, or clinical
authority.
"""

from __future__ import annotations

import enum
import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_fixture_research_surface_v1 import (
    FixtureCandidate,
    FixtureEvaluation,
    FixtureEvaluator,
    FixtureParameterValue,
    FixtureResearchSurface,
    FixtureResearchSurfaceError,
    build_fixture_candidate,
    evaluate_fixture_candidate,
)
from medscale.mesc._mrl_research_procedure_v1 import ResearchProcedure, ResearchProcedureError

__all__ = [
    "ProcedureReplayDisposition",
    "ProcedureReplayError",
    "ProcedureReplayReceipt",
    "replay_procedure_fixture",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProcedureReplayError(ValueError):
    """Fail-closed validation error for deterministic procedure replay."""


class ProcedureReplayDisposition(enum.Enum):
    """Replay evidence dispositions that do not imply procedure admission."""

    REPRODUCED = "REPRODUCED"
    MISMATCH = "MISMATCH"


def _make_receipt_identity_registry() -> tuple[
    Callable[[ProcedureReplayReceipt, str], None],
    Callable[[ProcedureReplayReceipt], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: ProcedureReplayReceipt, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ProcedureReplayError("replay receipt construction identity already exists")
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: ProcedureReplayReceipt) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ProcedureReplayError("replay receipt construction identity is missing")
        return identity

    return store, load


_store_receipt_identity, _load_receipt_identity = _make_receipt_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ProcedureReplayReceipt:
    """Immutable fixture replay evidence for one exact procedure candidate identity."""

    procedure_admission_subject_sha256: str
    procedure_content_sha256: str
    surface_sha256: str
    evaluator_sha256: str
    candidate_sha256: str
    evaluation_sha256: str
    metric_id: str
    expected_score: int
    expected_max_score: int
    observed_score: int
    observed_max_score: int
    disposition: ProcedureReplayDisposition

    def __post_init__(self) -> None:
        _require_sha256(
            self.procedure_admission_subject_sha256,
            "procedure_admission_subject_sha256",
        )
        _require_sha256(self.procedure_content_sha256, "procedure_content_sha256")
        _require_sha256(self.surface_sha256, "surface_sha256")
        _require_sha256(self.evaluator_sha256, "evaluator_sha256")
        _require_sha256(self.candidate_sha256, "candidate_sha256")
        _require_sha256(self.evaluation_sha256, "evaluation_sha256")
        _require_text(self.metric_id, "metric_id")
        _require_score_pair(self.expected_score, self.expected_max_score, "expected")
        _require_score_pair(self.observed_score, self.observed_max_score, "observed")
        if type(self.disposition) is not ProcedureReplayDisposition:
            raise ProcedureReplayError("disposition must be an exact ProcedureReplayDisposition")
        expected_disposition = (
            ProcedureReplayDisposition.REPRODUCED
            if (
                self.expected_score == self.observed_score
                and self.expected_max_score == self.observed_max_score
            )
            else ProcedureReplayDisposition.MISMATCH
        )
        if self.disposition is not expected_disposition:
            raise ProcedureReplayError("replay disposition does not match observed evidence")
        _store_receipt_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> ProcedureReplayReceipt:
        if type(self) is not ProcedureReplayReceipt:
            raise ProcedureReplayError("receipt must be an exact ProcedureReplayReceipt")
        bound_content_sha256 = _load_receipt_identity(self)
        _require_sha256(bound_content_sha256, "bound receipt content_sha256")
        snapshot = ProcedureReplayReceipt(
            procedure_admission_subject_sha256=self.procedure_admission_subject_sha256,
            procedure_content_sha256=self.procedure_content_sha256,
            surface_sha256=self.surface_sha256,
            evaluator_sha256=self.evaluator_sha256,
            candidate_sha256=self.candidate_sha256,
            evaluation_sha256=self.evaluation_sha256,
            metric_id=self.metric_id,
            expected_score=self.expected_score,
            expected_max_score=self.expected_max_score,
            observed_score=self.observed_score,
            observed_max_score=self.observed_max_score,
            disposition=self.disposition,
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise ProcedureReplayError("replay receipt identity changed after construction")
        return snapshot

    @property
    def fixture_only(self) -> bool:
        return True

    @property
    def non_evidence_for_real_execution(self) -> bool:
        return True

    @property
    def can_advance_admission(self) -> bool:
        return False

    @property
    def can_authorize(self) -> bool:
        return False

    @property
    def can_authorize_training(self) -> bool:
        return False

    @property
    def can_authorize_model_promotion(self) -> bool:
        return False

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "can_advance_admission": False,
            "can_authorize": False,
            "can_authorize_model_promotion": False,
            "can_authorize_training": False,
            "candidate_sha256": self.candidate_sha256,
            "disposition": self.disposition.value,
            "evaluation_sha256": self.evaluation_sha256,
            "evaluator_sha256": self.evaluator_sha256,
            "expected_max_score": self.expected_max_score,
            "expected_score": self.expected_score,
            "fixture_only": True,
            "format": "MRL-PROCEDURE-REPLAY-RECEIPT-V1",
            "metric_id": self.metric_id,
            "non_evidence_for_real_execution": True,
            "observed_max_score": self.observed_max_score,
            "observed_score": self.observed_score,
            "procedure_admission_subject_sha256": self.procedure_admission_subject_sha256,
            "procedure_content_sha256": self.procedure_content_sha256,
            "surface_sha256": self.surface_sha256,
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return freshly revalidated deterministic non-authoritative replay semantics."""
        snapshot = ProcedureReplayReceipt._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def replay_procedure_fixture(
    procedure: ResearchProcedure,
    surface: FixtureResearchSurface,
    evaluator: FixtureEvaluator,
    parameter_values: tuple[FixtureParameterValue, ...],
    *,
    expected_score: int,
    expected_max_score: int,
) -> ProcedureReplayReceipt:
    """Replay one coherent set of exact fixture snapshots in pure in-memory evaluation."""
    if type(procedure) is not ResearchProcedure:
        raise ProcedureReplayError("procedure must be an exact ResearchProcedure")
    if type(surface) is not FixtureResearchSurface:
        raise ProcedureReplayError("surface must be an exact FixtureResearchSurface")
    if type(evaluator) is not FixtureEvaluator:
        raise ProcedureReplayError("evaluator must be an exact FixtureEvaluator")
    if type(parameter_values) is not tuple:
        raise ProcedureReplayError("parameter_values must be an exact tuple")
    if any(type(value) is not FixtureParameterValue for value in parameter_values):
        raise ProcedureReplayError("parameter_values contains an invalid item type")
    _require_score_pair(expected_score, expected_max_score, "expected")

    try:
        procedure_snapshot = procedure._validated_snapshot()
        surface_snapshot = FixtureResearchSurface._validated_snapshot(surface)
        evaluator_snapshot = FixtureEvaluator._validated_snapshot(evaluator)
        parameter_snapshots = tuple(
            FixtureParameterValue(
                parameter_id=value.parameter_id,
                value=value.value,
            )
            for value in parameter_values
        )
        procedure_subject_sha256 = procedure_snapshot.admission_subject_sha256
        procedure_content_sha256 = procedure_snapshot.content_sha256
        candidate: FixtureCandidate = build_fixture_candidate(
            surface_snapshot,
            parameter_snapshots,
        )
        evaluation: FixtureEvaluation = evaluate_fixture_candidate(
            surface_snapshot,
            evaluator_snapshot,
            candidate,
        )
    except (ResearchProcedureError, FixtureResearchSurfaceError) as exc:
        raise ProcedureReplayError("procedure replay failed canonical fixture validation") from exc

    disposition = (
        ProcedureReplayDisposition.REPRODUCED
        if (expected_score == evaluation.score and expected_max_score == evaluation.max_score)
        else ProcedureReplayDisposition.MISMATCH
    )
    return ProcedureReplayReceipt(
        procedure_admission_subject_sha256=procedure_subject_sha256,
        procedure_content_sha256=procedure_content_sha256,
        surface_sha256=surface_snapshot.content_sha256,
        evaluator_sha256=evaluator_snapshot.content_sha256,
        candidate_sha256=candidate.content_sha256,
        evaluation_sha256=evaluation.content_sha256,
        metric_id=evaluation.metric_id,
        expected_score=expected_score,
        expected_max_score=expected_max_score,
        observed_score=evaluation.score,
        observed_max_score=evaluation.max_score,
        disposition=disposition,
    )


def _require_score_pair(score: object, max_score: object, label: str) -> None:
    if type(score) is not int or type(max_score) is not int:
        raise ProcedureReplayError(f"{label} scores must be exact integers")
    if max_score <= 0 or score < 0 or score > max_score:
        raise ProcedureReplayError(f"{label} scores must satisfy 0 <= score <= max_score")


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise ProcedureReplayError(f"{label} must be canonical non-empty text")
    if any(character.isspace() for character in value):
        raise ProcedureReplayError(f"{label} cannot contain whitespace")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise ProcedureReplayError(f"{label} must be 64 lowercase hex")
