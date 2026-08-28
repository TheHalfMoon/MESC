"""Deterministic fixture-only research surface for MRL-0201.

This module provides a bounded, in-memory toy research surface and a separately frozen
fixture evaluator. It performs no filesystem, network, model, dataset, provider, GPU,
inference, training, promotion, deployment, release, or clinical action.

The surface is intentionally smaller than the later MRL-2 loop. It defines deterministic
candidate parameters and deterministic fixture scoring only. Mutation-policy enforcement,
observation envelopes, experiment orchestration, receipts, and campaign updates remain
owned by later canonical tasks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)

__all__ = [
    "FixtureCandidate",
    "FixtureEvaluation",
    "FixtureEvaluator",
    "FixtureParameterDomain",
    "FixtureParameterValue",
    "FixtureResearchSurface",
    "FixtureResearchSurfaceError",
    "build_fixture_candidate",
    "evaluate_fixture_candidate",
]

_ID: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_MIN_PARAMETER_VALUE: Final = -1000
_MAX_PARAMETER_VALUE: Final = 1000


class FixtureResearchSurfaceError(ValueError):
    """Fail-closed validation error for the MRL fixture research surface."""


@dataclass(frozen=True, slots=True)
class FixtureParameterValue:
    """One exact toy parameter assignment."""

    parameter_id: str
    value: int

    def __post_init__(self) -> None:
        _require_id(self.parameter_id, "parameter_id")
        _require_parameter_int(self.value, "value")

    def to_dict(self) -> dict[str, object]:
        return {"parameter_id": self.parameter_id, "value": self.value}


@dataclass(frozen=True, slots=True)
class FixtureParameterDomain:
    """Finite allowed values for one toy experiment parameter."""

    parameter_id: str
    allowed_values: tuple[int, ...]

    def __post_init__(self) -> None:
        _require_id(self.parameter_id, "parameter_id")
        if type(self.allowed_values) is not tuple or not self.allowed_values:
            raise FixtureResearchSurfaceError(
                "allowed_values must be a non-empty exact tuple"
            )
        for value in self.allowed_values:
            _require_parameter_int(value, "allowed_values")
        if self.allowed_values != tuple(sorted(set(self.allowed_values))):
            raise FixtureResearchSurfaceError(
                "allowed_values must be unique and strictly sorted"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "parameter_id": self.parameter_id,
            "allowed_values": list(self.allowed_values),
        }


@dataclass(frozen=True, slots=True)
class FixtureEvaluator:
    """Separately frozen deterministic evaluator for one toy fixture surface."""

    evaluator_id: str
    metric_id: str
    target_values: tuple[FixtureParameterValue, ...]
    fixture_only: bool = True
    non_evidence: bool = True

    def __post_init__(self) -> None:
        _validate_evaluator(self)

    def _validated_snapshot(self) -> FixtureEvaluator:
        _require_exact_type(self, FixtureEvaluator, "fixture_evaluator")
        return FixtureEvaluator(
            evaluator_id=self.evaluator_id,
            metric_id=self.metric_id,
            target_values=tuple(
                FixtureParameterValue(
                    parameter_id=value.parameter_id,
                    value=value.value,
                )
                for value in self.target_values
            ),
            fixture_only=self.fixture_only,
            non_evidence=self.non_evidence,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-FIXTURE-EVALUATOR-V1",
            "evaluator_id": self.evaluator_id,
            "metric_id": self.metric_id,
            "target_values": [value.to_dict() for value in self.target_values],
            "fixture_only": self.fixture_only,
            "non_evidence": self.non_evidence,
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        _require_exact_type(self, FixtureEvaluator, "fixture_evaluator")
        snapshot = FixtureEvaluator._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        _require_exact_type(self, FixtureEvaluator, "fixture_evaluator")
        return canonical_semantic_bytes(FixtureEvaluator.semantic_dict(self))

    @property
    def content_sha256(self) -> str:
        _require_exact_type(self, FixtureEvaluator, "fixture_evaluator")
        return derive_content_sha256(FixtureEvaluator.semantic_dict(self))

    def to_dict(self) -> dict[str, object]:
        _require_exact_type(self, FixtureEvaluator, "fixture_evaluator")
        data = FixtureEvaluator.semantic_dict(self)
        data["content_sha256"] = derive_content_sha256(data)
        return data


@dataclass(frozen=True, slots=True)
class FixtureResearchSurface:
    """Content-addressed finite toy parameter surface bound to one frozen evaluator."""

    surface_id: str
    parameter_domains: tuple[FixtureParameterDomain, ...]
    evaluator_sha256: str
    fixture_only: bool = True
    non_evidence: bool = True

    def __post_init__(self) -> None:
        _validate_surface(self)

    def _validated_snapshot(self) -> FixtureResearchSurface:
        _require_exact_type(self, FixtureResearchSurface, "fixture_research_surface")
        return FixtureResearchSurface(
            surface_id=self.surface_id,
            parameter_domains=tuple(
                FixtureParameterDomain(
                    parameter_id=domain.parameter_id,
                    allowed_values=domain.allowed_values,
                )
                for domain in self.parameter_domains
            ),
            evaluator_sha256=self.evaluator_sha256,
            fixture_only=self.fixture_only,
            non_evidence=self.non_evidence,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-FIXTURE-RESEARCH-SURFACE-V1",
            "surface_id": self.surface_id,
            "parameter_domains": [
                domain.to_dict() for domain in self.parameter_domains
            ],
            "evaluator_sha256": self.evaluator_sha256,
            "fixture_only": self.fixture_only,
            "non_evidence": self.non_evidence,
            "execution_mode": "PURE_IN_MEMORY",
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        _require_exact_type(self, FixtureResearchSurface, "fixture_research_surface")
        snapshot = FixtureResearchSurface._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        _require_exact_type(self, FixtureResearchSurface, "fixture_research_surface")
        return canonical_semantic_bytes(FixtureResearchSurface.semantic_dict(self))

    @property
    def content_sha256(self) -> str:
        _require_exact_type(self, FixtureResearchSurface, "fixture_research_surface")
        return derive_content_sha256(FixtureResearchSurface.semantic_dict(self))

    def to_dict(self) -> dict[str, object]:
        _require_exact_type(self, FixtureResearchSurface, "fixture_research_surface")
        data = FixtureResearchSurface.semantic_dict(self)
        data["content_sha256"] = derive_content_sha256(data)
        return data


@dataclass(frozen=True, slots=True)
class FixtureCandidate:
    """Content-addressed assignment for every parameter on one fixture surface."""

    surface_sha256: str
    parameter_values: tuple[FixtureParameterValue, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.surface_sha256, "surface_sha256")
        _require_parameter_values(self.parameter_values, "parameter_values")

    def _validated_snapshot(self) -> FixtureCandidate:
        _require_exact_type(self, FixtureCandidate, "fixture_candidate")
        return FixtureCandidate(
            surface_sha256=self.surface_sha256,
            parameter_values=tuple(
                FixtureParameterValue(
                    parameter_id=value.parameter_id,
                    value=value.value,
                )
                for value in self.parameter_values
            ),
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-FIXTURE-CANDIDATE-V1",
            "surface_sha256": self.surface_sha256,
            "parameter_values": [
                value.to_dict() for value in self.parameter_values
            ],
            "fixture_only": True,
            "non_evidence": True,
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        _require_exact_type(self, FixtureCandidate, "fixture_candidate")
        snapshot = FixtureCandidate._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        _require_exact_type(self, FixtureCandidate, "fixture_candidate")
        return canonical_semantic_bytes(FixtureCandidate.semantic_dict(self))

    @property
    def content_sha256(self) -> str:
        _require_exact_type(self, FixtureCandidate, "fixture_candidate")
        return derive_content_sha256(FixtureCandidate.semantic_dict(self))

    def to_dict(self) -> dict[str, object]:
        _require_exact_type(self, FixtureCandidate, "fixture_candidate")
        data = FixtureCandidate.semantic_dict(self)
        data["content_sha256"] = derive_content_sha256(data)
        return data


@dataclass(frozen=True, slots=True)
class FixtureEvaluation:
    """Deterministic non-evidence score for one fixture candidate."""

    surface_sha256: str
    evaluator_sha256: str
    candidate_sha256: str
    metric_id: str
    score: int
    max_score: int

    def __post_init__(self) -> None:
        _require_sha256(self.surface_sha256, "surface_sha256")
        _require_sha256(self.evaluator_sha256, "evaluator_sha256")
        _require_sha256(self.candidate_sha256, "candidate_sha256")
        _require_id(self.metric_id, "metric_id")
        _require_nonnegative_int(self.score, "score")
        _require_nonnegative_int(self.max_score, "max_score")
        if self.max_score == 0:
            raise FixtureResearchSurfaceError("max_score must be positive")
        if self.score > self.max_score:
            raise FixtureResearchSurfaceError("score cannot exceed max_score")

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-FIXTURE-EVALUATION-V1",
            "surface_sha256": self.surface_sha256,
            "evaluator_sha256": self.evaluator_sha256,
            "candidate_sha256": self.candidate_sha256,
            "metric_id": self.metric_id,
            "score": self.score,
            "max_score": self.max_score,
            "fixture_only": True,
            "non_evidence": True,
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        _require_exact_type(self, FixtureEvaluation, "fixture_evaluation")
        snapshot = FixtureEvaluation(
            surface_sha256=self.surface_sha256,
            evaluator_sha256=self.evaluator_sha256,
            candidate_sha256=self.candidate_sha256,
            metric_id=self.metric_id,
            score=self.score,
            max_score=self.max_score,
        )
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        _require_exact_type(self, FixtureEvaluation, "fixture_evaluation")
        return canonical_semantic_bytes(FixtureEvaluation.semantic_dict(self))

    @property
    def content_sha256(self) -> str:
        _require_exact_type(self, FixtureEvaluation, "fixture_evaluation")
        return derive_content_sha256(FixtureEvaluation.semantic_dict(self))

    def to_dict(self) -> dict[str, object]:
        _require_exact_type(self, FixtureEvaluation, "fixture_evaluation")
        data = FixtureEvaluation.semantic_dict(self)
        data["content_sha256"] = derive_content_sha256(data)
        return data


def build_fixture_candidate(
    surface: FixtureResearchSurface,
    parameter_values: tuple[FixtureParameterValue, ...],
) -> FixtureCandidate:
    """Build one bounded candidate after validating exact surface-domain membership."""

    _require_exact_type(surface, FixtureResearchSurface, "fixture_research_surface")
    surface_snapshot = FixtureResearchSurface._validated_snapshot(surface)
    _require_parameter_values(parameter_values, "parameter_values")
    _require_candidate_matches_surface(surface_snapshot, parameter_values)
    return FixtureCandidate(
        surface_sha256=surface_snapshot.content_sha256,
        parameter_values=parameter_values,
    )


def evaluate_fixture_candidate(
    surface: FixtureResearchSurface,
    evaluator: FixtureEvaluator,
    candidate: FixtureCandidate,
) -> FixtureEvaluation:
    """Score one candidate deterministically against the separately frozen evaluator."""

    _require_exact_type(surface, FixtureResearchSurface, "fixture_research_surface")
    _require_exact_type(evaluator, FixtureEvaluator, "fixture_evaluator")
    _require_exact_type(candidate, FixtureCandidate, "fixture_candidate")
    surface_snapshot = FixtureResearchSurface._validated_snapshot(surface)
    evaluator_snapshot = FixtureEvaluator._validated_snapshot(evaluator)
    candidate_snapshot = FixtureCandidate._validated_snapshot(candidate)
    _require_fixture_binding(surface_snapshot, evaluator_snapshot)
    if candidate_snapshot.surface_sha256 != surface_snapshot.content_sha256:
        raise FixtureResearchSurfaceError(
            "candidate does not bind the supplied fixture surface"
        )
    _require_candidate_matches_surface(
        surface_snapshot,
        candidate_snapshot.parameter_values,
    )
    targets = {
        value.parameter_id: value.value for value in evaluator_snapshot.target_values
    }
    score = sum(
        targets[value.parameter_id] == value.value
        for value in candidate_snapshot.parameter_values
    )
    return FixtureEvaluation(
        surface_sha256=surface_snapshot.content_sha256,
        evaluator_sha256=evaluator_snapshot.content_sha256,
        candidate_sha256=candidate_snapshot.content_sha256,
        metric_id=evaluator_snapshot.metric_id,
        score=score,
        max_score=len(candidate_snapshot.parameter_values),
    )


def _validate_surface(surface: FixtureResearchSurface) -> None:
    _require_id(surface.surface_id, "surface_id")
    _require_sha256(surface.evaluator_sha256, "evaluator_sha256")
    _require_true(surface.fixture_only, "fixture_only")
    _require_true(surface.non_evidence, "non_evidence")
    if type(surface.parameter_domains) is not tuple or not surface.parameter_domains:
        raise FixtureResearchSurfaceError(
            "parameter_domains must be a non-empty exact tuple"
        )
    for domain in surface.parameter_domains:
        _require_exact_type(domain, FixtureParameterDomain, "parameter_domain")
        FixtureParameterDomain(
            parameter_id=domain.parameter_id,
            allowed_values=domain.allowed_values,
        )
    domain_ids = tuple(domain.parameter_id for domain in surface.parameter_domains)
    if domain_ids != tuple(sorted(set(domain_ids))):
        raise FixtureResearchSurfaceError(
            "parameter_domains must be unique and strictly sorted by parameter_id"
        )


def _validate_evaluator(evaluator: FixtureEvaluator) -> None:
    _require_id(evaluator.evaluator_id, "evaluator_id")
    _require_id(evaluator.metric_id, "metric_id")
    _require_true(evaluator.fixture_only, "fixture_only")
    _require_true(evaluator.non_evidence, "non_evidence")
    _require_parameter_values(evaluator.target_values, "target_values")


def _require_fixture_binding(
    surface: FixtureResearchSurface,
    evaluator: FixtureEvaluator,
) -> None:
    if surface.evaluator_sha256 != evaluator.content_sha256:
        raise FixtureResearchSurfaceError(
            "fixture surface does not bind the supplied evaluator"
        )
    domain_by_id = {
        domain.parameter_id: domain for domain in surface.parameter_domains
    }
    target_ids = tuple(value.parameter_id for value in evaluator.target_values)
    if target_ids != tuple(domain_by_id):
        raise FixtureResearchSurfaceError(
            "evaluator target values must cover exactly every surface parameter"
        )
    for target in evaluator.target_values:
        if target.value not in domain_by_id[target.parameter_id].allowed_values:
            raise FixtureResearchSurfaceError(
                "evaluator target value falls outside the bound surface domain"
            )


def _require_candidate_matches_surface(
    surface: FixtureResearchSurface,
    parameter_values: tuple[FixtureParameterValue, ...],
) -> None:
    domain_by_id = {
        domain.parameter_id: domain for domain in surface.parameter_domains
    }
    value_ids = tuple(value.parameter_id for value in parameter_values)
    if value_ids != tuple(domain_by_id):
        raise FixtureResearchSurfaceError(
            "candidate values must cover exactly every surface parameter"
        )
    for value in parameter_values:
        if value.value not in domain_by_id[value.parameter_id].allowed_values:
            raise FixtureResearchSurfaceError(
                "candidate value falls outside the bound surface domain"
            )


def _require_parameter_values(
    values: tuple[FixtureParameterValue, ...],
    label: str,
) -> None:
    if type(values) is not tuple or not values:
        raise FixtureResearchSurfaceError(f"{label} must be a non-empty exact tuple")
    for value in values:
        _require_exact_type(value, FixtureParameterValue, label)
        FixtureParameterValue(
            parameter_id=value.parameter_id,
            value=value.value,
        )
    ids = tuple(value.parameter_id for value in values)
    if ids != tuple(sorted(set(ids))):
        raise FixtureResearchSurfaceError(
            f"{label} must be unique and strictly sorted by parameter_id"
        )


def _require_parameter_int(value: object, label: str) -> None:
    if type(value) is not int:
        raise FixtureResearchSurfaceError(f"{label} must contain exact integers")
    if value < _MIN_PARAMETER_VALUE or value > _MAX_PARAMETER_VALUE:
        raise FixtureResearchSurfaceError(
            f"{label} values must stay within the bounded fixture range"
        )


def _require_nonnegative_int(value: object, label: str) -> None:
    if type(value) is not int or value < 0:
        raise FixtureResearchSurfaceError(
            f"{label} must be an exact non-negative integer"
        )


def _require_true(value: object, label: str) -> None:
    if type(value) is not bool or not value:
        raise FixtureResearchSurfaceError(f"{label} must be exactly True")


def _require_id(value: object, label: str) -> None:
    if type(value) is not str or not _ID.fullmatch(value):
        raise FixtureResearchSurfaceError(
            f"{label} must use non-empty lowercase kebab-case semantics"
        )


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or not _SHA256.fullmatch(value):
        raise FixtureResearchSurfaceError(
            f"{label} must be exactly 64 lowercase hex characters"
        )


def _require_exact_type(value: object, expected: type[object], label: str) -> None:
    if type(value) is not expected:
        raise FixtureResearchSurfaceError(f"{label} has an invalid exact type")
