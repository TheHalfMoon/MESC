"""Deterministic pre-execution MESC training launch-plan construction.

A launch plan is an immutable, content-addressed bridge between a fully qualified
``READY_TO_LAUNCH`` readiness manifest and a later training executor. This module
never accesses providers, model weights, datasets, credentials, GPUs, or trainers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Final, Literal

from medscale.mesc._training_readiness_v1 import (
    TrainingReadinessManifest,
    TrainingReadinessReport,
    assess_training_readiness,
)
from medscale.modelkit.manifests import RunnerClass
from medscale.reproducibility import content_hash

TrainingRole = Literal["compact", "reasoner"]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_EXPERIMENT_ID: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", flags=re.ASCII)
_RQ_REF: Final = re.compile(r"^(?:RQ[1-9][0-9]?|background)$", flags=re.ASCII)
_PLAN_VERSION: Final = "MESC-TRAINING-LAUNCH-PLAN-V1"


class TrainingLaunchPlanError(ValueError):
    """Fail-closed launch-plan construction error."""


@dataclass(frozen=True, slots=True)
class TrainingRunPlan:
    """One exact, non-executing training-run specification."""

    role: TrainingRole
    experiment_id: str
    rq_refs: tuple[str, ...]
    recipe_id: str
    model_id: str
    revision: str
    weights_sha256: str
    training_dataset_sha256: str
    seeds: tuple[int, ...]
    runner_class: RunnerClass
    python_version: str
    os_name: str
    gpu_model: str
    dependency_lock_sha256: str
    repository_sha: str
    repository_tree: str
    result_paths: tuple[str, ...]
    reproduction_command: str

    def __post_init__(self) -> None:
        if self.role not in ("compact", "reasoner"):
            raise TrainingLaunchPlanError("role must be exactly 'compact' or 'reasoner'")
        if _EXPERIMENT_ID.fullmatch(self.experiment_id) is None:
            raise TrainingLaunchPlanError("experiment_id must be non-empty kebab-case")
        if not self.rq_refs:
            raise TrainingLaunchPlanError("rq_refs must be non-empty")
        if any(_RQ_REF.fullmatch(ref) is None for ref in self.rq_refs):
            raise TrainingLaunchPlanError("every rq_ref must be RQn or 'background'")
        _require_sha256(self.recipe_id, field="recipe_id")
        if not self.model_id.strip():
            raise TrainingLaunchPlanError("model_id must be non-empty")
        if _GIT_SHA.fullmatch(self.revision) is None:
            raise TrainingLaunchPlanError("revision must be exactly 40 lowercase hex characters")
        _require_sha256(self.weights_sha256, field="weights_sha256")
        _require_sha256(self.training_dataset_sha256, field="training_dataset_sha256")
        if not self.seeds or any(isinstance(seed, bool) or seed < 0 for seed in self.seeds):
            raise TrainingLaunchPlanError("seeds must be non-empty non-negative integers")
        if len(set(self.seeds)) != len(self.seeds):
            raise TrainingLaunchPlanError("seeds must not contain duplicates")
        if not isinstance(self.runner_class, RunnerClass):
            raise TrainingLaunchPlanError("runner_class must be a RunnerClass")
        if (
            not self.python_version.strip()
            or not self.os_name.strip()
            or not self.gpu_model.strip()
        ):
            raise TrainingLaunchPlanError(
                "python_version, os_name, and gpu_model must be non-empty"
            )
        _require_sha256(self.dependency_lock_sha256, field="dependency_lock_sha256")
        if _GIT_SHA.fullmatch(self.repository_sha) is None:
            raise TrainingLaunchPlanError(
                "repository_sha must be exactly 40 lowercase hex characters"
            )
        if _GIT_SHA.fullmatch(self.repository_tree) is None:
            raise TrainingLaunchPlanError(
                "repository_tree must be exactly 40 lowercase hex characters"
            )
        if not self.result_paths:
            raise TrainingLaunchPlanError("result_paths must be non-empty")
        for path in self.result_paths:
            _require_repository_relative_path(path)
        if len(set(self.result_paths)) != len(self.result_paths):
            raise TrainingLaunchPlanError("result_paths must not contain duplicates")
        if not self.reproduction_command.strip() or "\n" in self.reproduction_command:
            raise TrainingLaunchPlanError(
                "reproduction_command must be one non-empty single-line command"
            )

    @property
    def run_plan_sha256(self) -> str:
        """Return the deterministic identity of this exact run plan."""
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "experiment_id": self.experiment_id,
            "gpu_model": self.gpu_model,
            "model_id": self.model_id,
            "os_name": self.os_name,
            "python_version": self.python_version,
            "recipe_id": self.recipe_id,
            "repository_sha": self.repository_sha,
            "repository_tree": self.repository_tree,
            "reproduction_command": self.reproduction_command,
            "result_paths": list(self.result_paths),
            "revision": self.revision,
            "role": self.role,
            "rq_refs": list(self.rq_refs),
            "runner_class": self.runner_class.value,
            "seeds": list(self.seeds),
            "training_dataset_sha256": self.training_dataset_sha256,
            "weights_sha256": self.weights_sha256,
        }


@dataclass(frozen=True, slots=True)
class TrainingLaunchPlan:
    """Content-addressed pair of exact Compact and Reasoner run plans."""

    readiness_manifest_sha256: str
    runtime_qualification_sha256: str
    training_authorization_receipt_sha256: str
    compact: TrainingRunPlan
    reasoner: TrainingRunPlan
    plan_version: str = _PLAN_VERSION

    def __post_init__(self) -> None:
        if self.plan_version != _PLAN_VERSION:
            raise TrainingLaunchPlanError(f"plan_version must be exactly {_PLAN_VERSION}")
        _require_sha256(self.readiness_manifest_sha256, field="readiness_manifest_sha256")
        _require_sha256(
            self.runtime_qualification_sha256,
            field="runtime_qualification_sha256",
        )
        _require_sha256(
            self.training_authorization_receipt_sha256,
            field="training_authorization_receipt_sha256",
        )
        if self.compact.role != "compact" or self.reasoner.role != "reasoner":
            raise TrainingLaunchPlanError(
                "run plans must occupy their exact Compact/Reasoner roles"
            )
        if self.compact.experiment_id == self.reasoner.experiment_id:
            raise TrainingLaunchPlanError("Compact and Reasoner experiment_id values must differ")
        if self.compact.repository_sha != self.reasoner.repository_sha:
            raise TrainingLaunchPlanError("both runs must bind the same repository_sha")
        if self.compact.repository_tree != self.reasoner.repository_tree:
            raise TrainingLaunchPlanError("both runs must bind the same repository_tree")
        if self.compact.dependency_lock_sha256 != self.reasoner.dependency_lock_sha256:
            raise TrainingLaunchPlanError("both runs must bind the same dependency lock")
        if set(self.compact.result_paths) & set(self.reasoner.result_paths):
            raise TrainingLaunchPlanError("Compact and Reasoner result_paths must be disjoint")

    @property
    def plan_sha256(self) -> str:
        """Return the deterministic identity of the complete launch plan."""
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "compact": self.compact.to_dict(),
            "plan_version": self.plan_version,
            "readiness_manifest_sha256": self.readiness_manifest_sha256,
            "reasoner": self.reasoner.to_dict(),
            "runtime_qualification_sha256": self.runtime_qualification_sha256,
            "training_authorization_receipt_sha256": self.training_authorization_receipt_sha256,
        }


def build_training_launch_plan(
    *,
    manifest: TrainingReadinessManifest,
    readiness: TrainingReadinessReport,
    compact: TrainingRunPlan,
    reasoner: TrainingRunPlan,
) -> TrainingLaunchPlan:
    """Build a plan only from an exact, independently recomputable launch-ready manifest."""
    recomputed = assess_training_readiness(manifest)
    if readiness != recomputed:
        raise TrainingLaunchPlanError(
            "supplied readiness report does not match recomputed readiness"
        )
    if readiness.disposition != "READY_TO_LAUNCH" or not readiness.can_launch_training:
        raise TrainingLaunchPlanError("training readiness disposition is not READY_TO_LAUNCH")
    if readiness.blockers or readiness.launch_requirements:
        raise TrainingLaunchPlanError("launch-ready report must have no blockers or requirements")
    if readiness.manifest_sha256 != manifest.manifest_sha256:
        raise TrainingLaunchPlanError("readiness report is not bound to the supplied manifest")
    if manifest.runtime_qualification_sha256 is None:
        raise TrainingLaunchPlanError("runtime qualification receipt is absent")
    if manifest.training_authorization_receipt_sha256 is None:
        raise TrainingLaunchPlanError("training authorization receipt is absent")

    _require_run_binding(
        role="compact",
        run=compact,
        model_id=manifest.compact_candidate.model_id,
        revision=manifest.compact_candidate.revision,
        weights_sha256=manifest.compact_candidate.weights_sha256,
        recipe_id=manifest.compact_recipe.recipe_id,
        training_dataset_sha256=manifest.training_dataset_sha256,
    )
    _require_run_binding(
        role="reasoner",
        run=reasoner,
        model_id=manifest.reasoner_candidate.model_id,
        revision=manifest.reasoner_candidate.revision,
        weights_sha256=manifest.reasoner_candidate.weights_sha256,
        recipe_id=manifest.reasoner_recipe.recipe_id,
        training_dataset_sha256=manifest.training_dataset_sha256,
    )

    return TrainingLaunchPlan(
        readiness_manifest_sha256=manifest.manifest_sha256,
        runtime_qualification_sha256=manifest.runtime_qualification_sha256,
        training_authorization_receipt_sha256=manifest.training_authorization_receipt_sha256,
        compact=compact,
        reasoner=reasoner,
    )


def _require_run_binding(
    *,
    role: TrainingRole,
    run: TrainingRunPlan,
    model_id: str,
    revision: str,
    weights_sha256: str,
    recipe_id: str,
    training_dataset_sha256: str,
) -> None:
    expected = (
        ("role", run.role, role),
        ("model_id", run.model_id, model_id),
        ("revision", run.revision, revision),
        ("weights_sha256", run.weights_sha256, weights_sha256),
        ("recipe_id", run.recipe_id, recipe_id),
        ("training_dataset_sha256", run.training_dataset_sha256, training_dataset_sha256),
    )
    for field, actual, wanted in expected:
        if actual != wanted:
            raise TrainingLaunchPlanError(f"{role} run {field} does not match readiness manifest")


def _require_sha256(value: str, *, field: str) -> None:
    if _SHA256.fullmatch(value) is None:
        raise TrainingLaunchPlanError(f"{field} must be exactly 64 lowercase hex characters")


def _require_repository_relative_path(value: str) -> None:
    if not value or "\\" in value:
        raise TrainingLaunchPlanError("result path must be a non-empty POSIX repository path")
    path = PurePosixPath(value)
    if path.is_absolute() or path == PurePosixPath(".") or ".." in path.parts:
        raise TrainingLaunchPlanError("result path must remain inside the repository")
