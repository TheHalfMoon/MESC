"""R2-compatible sealed temporal-canary fixture workflow for MRL V1.

MRL-0606 binds one exact MRL-0605 temporal-canary manifest to the canonical pure in-memory
fixture evaluator and records only content identities plus aggregate fixture metrics. The
executed fixture candidate must exactly match the sealed canary artifact identity; receipts
never expose item-level canary content and cannot place a canary into training or search.
"""

from __future__ import annotations

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
from medscale.mesc._mrl_temporal_canary_manifest_v1 import (
    TemporalCanaryManifest,
    TemporalCanaryManifestError,
    TemporalCanarySourceKind,
)

__all__ = [
    "TemporalCanaryFixtureReceipt",
    "TemporalCanaryFixtureWorkflowError",
    "run_temporal_canary_fixture_workflow",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class TemporalCanaryFixtureWorkflowError(ValueError):
    """Fail-closed validation error for the R2 temporal-canary fixture workflow."""


def _make_receipt_identity_registry() -> tuple[
    Callable[[TemporalCanaryFixtureReceipt, str], None],
    Callable[[TemporalCanaryFixtureReceipt], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: TemporalCanaryFixtureReceipt, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise TemporalCanaryFixtureWorkflowError(
                "temporal-canary receipt construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: TemporalCanaryFixtureReceipt) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise TemporalCanaryFixtureWorkflowError(
                "temporal-canary receipt construction identity is missing"
            )
        return identity

    return store, load


_store_receipt_identity, _load_receipt_identity = _make_receipt_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class TemporalCanaryFixtureReceipt:
    """Immutable aggregate-only receipt for one sealed fixture canary evaluation."""

    manifest_sha256: str
    canary_artifact_sha256: str
    source_kind: TemporalCanarySourceKind
    surface_sha256: str
    evaluator_sha256: str
    candidate_sha256: str
    evaluation_sha256: str
    metric_id: str
    observed_score: int
    observed_max_score: int

    def __post_init__(self) -> None:
        _require_sha256(self.manifest_sha256, "manifest_sha256")
        _require_sha256(self.canary_artifact_sha256, "canary_artifact_sha256")
        if type(self.source_kind) is not TemporalCanarySourceKind:
            raise TemporalCanaryFixtureWorkflowError(
                "source_kind must be an exact TemporalCanarySourceKind"
            )
        _require_sha256(self.surface_sha256, "surface_sha256")
        _require_sha256(self.evaluator_sha256, "evaluator_sha256")
        _require_sha256(self.candidate_sha256, "candidate_sha256")
        if self.canary_artifact_sha256 != self.candidate_sha256:
            raise TemporalCanaryFixtureWorkflowError(
                "candidate identity must equal the sealed canary artifact identity"
            )
        _require_sha256(self.evaluation_sha256, "evaluation_sha256")
        _require_text(self.metric_id, "metric_id")
        if type(self.observed_score) is not int or type(self.observed_max_score) is not int:
            raise TemporalCanaryFixtureWorkflowError("observed scores must be exact integers")
        if (
            self.observed_max_score <= 0
            or self.observed_score < 0
            or self.observed_score > self.observed_max_score
        ):
            raise TemporalCanaryFixtureWorkflowError(
                "observed scores must satisfy 0 <= score <= max_score"
            )
        _store_receipt_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> TemporalCanaryFixtureReceipt:
        if type(self) is not TemporalCanaryFixtureReceipt:
            raise TemporalCanaryFixtureWorkflowError(
                "receipt must be an exact TemporalCanaryFixtureReceipt"
            )
        bound_content_sha256 = _load_receipt_identity(self)
        _require_sha256(bound_content_sha256, "bound receipt content_sha256")
        snapshot = TemporalCanaryFixtureReceipt(
            manifest_sha256=self.manifest_sha256,
            canary_artifact_sha256=self.canary_artifact_sha256,
            source_kind=self.source_kind,
            surface_sha256=self.surface_sha256,
            evaluator_sha256=self.evaluator_sha256,
            candidate_sha256=self.candidate_sha256,
            evaluation_sha256=self.evaluation_sha256,
            metric_id=self.metric_id,
            observed_score=self.observed_score,
            observed_max_score=self.observed_max_score,
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise TemporalCanaryFixtureWorkflowError(
                "temporal-canary receipt identity changed after construction"
            )
        return snapshot

    @property
    def sealed(self) -> bool:
        return True

    @property
    def fixture_only(self) -> bool:
        return True

    @property
    def exposes_canary_content(self) -> bool:
        return False

    @property
    def can_enter_training(self) -> bool:
        return False

    @property
    def can_enter_search(self) -> bool:
        return False

    @property
    def can_authorize(self) -> bool:
        return False

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "can_authorize": False,
            "can_enter_search": False,
            "can_enter_training": False,
            "canary_artifact_sha256": self.canary_artifact_sha256,
            "candidate_sha256": self.candidate_sha256,
            "evaluation_sha256": self.evaluation_sha256,
            "evaluator_sha256": self.evaluator_sha256,
            "exposes_canary_content": False,
            "fixture_only": True,
            "format": "MRL-TEMPORAL-CANARY-FIXTURE-RECEIPT-V1",
            "manifest_sha256": self.manifest_sha256,
            "metric_id": self.metric_id,
            "observed_max_score": self.observed_max_score,
            "observed_score": self.observed_score,
            "sealed": True,
            "source_kind": self.source_kind.value,
            "surface_sha256": self.surface_sha256,
            "workflow_mode": "R2_FIXTURE_ONLY",
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = TemporalCanaryFixtureReceipt._validated_snapshot(self)
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


def run_temporal_canary_fixture_workflow(
    manifest: TemporalCanaryManifest,
    surface: FixtureResearchSurface,
    evaluator: FixtureEvaluator,
    parameter_values: tuple[FixtureParameterValue, ...],
) -> TemporalCanaryFixtureReceipt:
    """Evaluate one exact sealed-canary fixture candidate from coherent fixture snapshots."""
    if type(manifest) is not TemporalCanaryManifest:
        raise TemporalCanaryFixtureWorkflowError(
            "manifest must be an exact TemporalCanaryManifest"
        )
    if type(surface) is not FixtureResearchSurface:
        raise TemporalCanaryFixtureWorkflowError(
            "surface must be an exact FixtureResearchSurface"
        )
    if type(evaluator) is not FixtureEvaluator:
        raise TemporalCanaryFixtureWorkflowError(
            "evaluator must be an exact FixtureEvaluator"
        )
    if type(parameter_values) is not tuple:
        raise TemporalCanaryFixtureWorkflowError("parameter_values must be an exact tuple")
    if any(type(value) is not FixtureParameterValue for value in parameter_values):
        raise TemporalCanaryFixtureWorkflowError(
            "parameter_values contains an invalid item type"
        )

    try:
        # Pre-reconciliation MRL-0605 compatibility: once PR #299 becomes canonical,
        # this must call the original manifest construction-bound validation path.
        manifest_snapshot = TemporalCanaryManifest(
            canary_id=manifest.canary_id,
            source_kind=manifest.source_kind,
            canary_artifact_sha256=manifest.canary_artifact_sha256,
            temporal_boundary_at=manifest.temporal_boundary_at,
            created_at=manifest.created_at,
            evaluator_artifact_sha256=manifest.evaluator_artifact_sha256,
            topic_tags=manifest.topic_tags,
        )
        surface_snapshot = FixtureResearchSurface._validated_snapshot(surface)
        evaluator_snapshot = FixtureEvaluator._validated_snapshot(evaluator)
        parameter_snapshots = tuple(
            FixtureParameterValue(parameter_id=value.parameter_id, value=value.value)
            for value in parameter_values
        )
        evaluator_sha256 = evaluator_snapshot.content_sha256
        if manifest_snapshot.evaluator_artifact_sha256 != evaluator_sha256:
            raise TemporalCanaryFixtureWorkflowError(
                "temporal-canary manifest evaluator identity does not match "
                "supplied fixture evaluator"
            )
        candidate: FixtureCandidate = build_fixture_candidate(
            surface_snapshot,
            parameter_snapshots,
        )
        candidate_sha256 = candidate.content_sha256
        if manifest_snapshot.canary_artifact_sha256 != candidate_sha256:
            raise TemporalCanaryFixtureWorkflowError(
                "temporal-canary manifest artifact identity does not match "
                "supplied fixture candidate"
            )
        evaluation: FixtureEvaluation = evaluate_fixture_candidate(
            surface_snapshot,
            evaluator_snapshot,
            candidate,
        )
    except (TemporalCanaryManifestError, FixtureResearchSurfaceError) as exc:
        raise TemporalCanaryFixtureWorkflowError(
            "temporal-canary fixture workflow failed canonical validation"
        ) from exc

    return TemporalCanaryFixtureReceipt(
        manifest_sha256=manifest_snapshot.content_sha256,
        canary_artifact_sha256=manifest_snapshot.canary_artifact_sha256,
        source_kind=manifest_snapshot.source_kind,
        surface_sha256=surface_snapshot.content_sha256,
        evaluator_sha256=evaluator_sha256,
        candidate_sha256=candidate_sha256,
        evaluation_sha256=evaluation.content_sha256,
        metric_id=evaluation.metric_id,
        observed_score=evaluation.score,
        observed_max_score=evaluation.max_score,
    )


def _require_text(value: object, label: str) -> None:
    if type(value) is not str or not value or value.strip() != value:
        raise TemporalCanaryFixtureWorkflowError(f"{label} must be canonical non-empty text")
    if any(character.isspace() for character in value):
        raise TemporalCanaryFixtureWorkflowError(f"{label} cannot contain whitespace")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise TemporalCanaryFixtureWorkflowError(f"{label} must be 64 lowercase hex")
