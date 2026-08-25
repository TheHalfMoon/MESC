"""Fail-closed repository-side MESC training executor boundary.

The core independently revalidates canonical training authority, snapshots one exact
execution manifest, and invokes only an explicitly injected backend. It performs no
model loading, provider access, network access, GPU work, or training by itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import PurePosixPath
from typing import Final, Literal, Protocol

from medscale.mesc._training_corpus_binding_v1 import TrainingCorpusBindingReport
from medscale.mesc._training_launch_plan_v1 import (
    TrainingLaunchPlan,
    TrainingRole,
    TrainingRunPlan,
    build_training_launch_plan,
)
from medscale.mesc._training_local_asset_attestation_v1 import (
    TrainingLocalAssetAttestationReport,
)
from medscale.mesc._training_readiness_v1 import (
    TrainingCandidate,
    TrainingReadinessManifest,
    TrainingReadinessReport,
    assess_training_readiness,
)
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.manifests import RunnerClass
from medscale.modelkit.recipes import AdapterMethod, DatasetRef, TrainingRecipe
from medscale.reproducibility import content_hash

TrainingExecutionDisposition = Literal["SUCCEEDED", "FAILED", "ABORTED"]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_TIMESTAMP: Final = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$",
    flags=re.ASCII,
)
_EXECUTOR_VERSION: Final = "MESC-TRAINING-EXECUTOR-V1"
_RESULT_MANIFEST_KIND: Final = "mesc.training_execution.results.v1"


class TrainingExecutionError(ValueError):
    """Raised when execution cannot cross the canonical training boundary."""


@dataclass(frozen=True, slots=True)
class TrainingExecutionEnvironment:
    """Observed environment identity required to equal one selected run plan."""

    repository_sha: str
    repository_tree: str
    dependency_lock_sha256: str
    runner_class: RunnerClass
    python_version: str
    os_name: str
    gpu_model: str

    def __post_init__(self) -> None:
        _require_git_sha(self.repository_sha, field="repository_sha")
        _require_git_sha(self.repository_tree, field="repository_tree")
        _require_sha256(
            self.dependency_lock_sha256,
            field="dependency_lock_sha256",
        )
        if not isinstance(self.runner_class, RunnerClass):
            raise TrainingExecutionError("runner_class must be a RunnerClass")
        _require_text(self.python_version, field="python_version")
        _require_text(self.os_name, field="os_name")
        _require_text(self.gpu_model, field="gpu_model")

    @property
    def environment_sha256(self) -> str:
        """Return the content identity of the observed environment."""
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """Return the canonical environment payload."""
        return {
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "gpu_model": self.gpu_model,
            "os_name": self.os_name,
            "python_version": self.python_version,
            "repository_sha": self.repository_sha,
            "repository_tree": self.repository_tree,
            "runner_class": self.runner_class.value,
        }


@dataclass(frozen=True, slots=True)
class TrainingResultArtifact:
    """One content-addressed final artifact emitted by a training backend."""

    path: str
    sha256: str
    byte_count: int

    def __post_init__(self) -> None:
        _require_repository_relative_path(self.path, field="artifact path")
        _require_sha256(self.sha256, field="artifact sha256")
        if type(self.byte_count) is not int or self.byte_count <= 0:
            raise TrainingExecutionError("artifact byte_count must be a positive int")

    def to_dict(self) -> dict[str, object]:
        """Return the canonical artifact payload."""
        return {
            "byte_count": self.byte_count,
            "path": self.path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class TrainingBackendResult:
    """Backend-owned terminal observation returned to the core executor."""

    disposition: TrainingExecutionDisposition
    backend_id: str
    backend_version: str
    started_at: str
    finished_at: str
    artifacts: tuple[TrainingResultArtifact, ...]
    failure_reason: str | None = None

    def __post_init__(self) -> None:
        if self.disposition not in ("SUCCEEDED", "FAILED", "ABORTED"):
            raise TrainingExecutionError("backend disposition is invalid")
        _require_text(self.backend_id, field="backend_id")
        _require_text(self.backend_version, field="backend_version")
        _require_ordered_timestamps(self.started_at, self.finished_at)
        _require_artifact_tuple(self.artifacts, field="artifacts")
        _require_unique_artifact_paths(self.artifacts, field="artifacts")

        if self.disposition == "SUCCEEDED":
            if not self.artifacts:
                raise TrainingExecutionError("SUCCEEDED backend result requires result artifacts")
            if self.failure_reason is not None:
                raise TrainingExecutionError("SUCCEEDED backend result cannot have failure_reason")
            return

        if self.artifacts:
            raise TrainingExecutionError(
                "FAILED or ABORTED backend result cannot claim canonical artifacts"
            )
        _require_text(self.failure_reason, field="failure_reason")


@dataclass(frozen=True, slots=True)
class TrainingExecutionManifest:
    """Core-owned immutable input for exactly one backend invocation."""

    role: TrainingRole
    launch_plan_sha256: str
    run_plan_sha256: str
    readiness_manifest_sha256: str
    corpus_binding_sha256: str
    local_asset_attestation_sha256: str
    environment_sha256: str
    experiment_id: str
    model_id: str
    revision: str
    weights_sha256: str
    training_dataset_sha256: str
    recipe_id: str
    seeds: tuple[int, ...]
    runner_class: str
    python_version: str
    os_name: str
    gpu_model: str
    repository_sha: str
    repository_tree: str
    dependency_lock_sha256: str
    runtime_qualification_sha256: str
    training_authorization_receipt_sha256: str
    canonical_corpus_sha256: str
    canonical_corpus_byte_count: int
    model_verifier_receipt_sha256: str
    result_namespaces: tuple[str, ...]
    executor_version: str = _EXECUTOR_VERSION

    def __post_init__(self) -> None:
        if self.executor_version != _EXECUTOR_VERSION:
            raise TrainingExecutionError(f"executor_version must be exactly {_EXECUTOR_VERSION}")
        if self.role not in ("compact", "reasoner"):
            raise TrainingExecutionError("role must be compact or reasoner")

        for field, value in (
            ("launch_plan_sha256", self.launch_plan_sha256),
            ("run_plan_sha256", self.run_plan_sha256),
            ("readiness_manifest_sha256", self.readiness_manifest_sha256),
            ("corpus_binding_sha256", self.corpus_binding_sha256),
            (
                "local_asset_attestation_sha256",
                self.local_asset_attestation_sha256,
            ),
            ("environment_sha256", self.environment_sha256),
            ("weights_sha256", self.weights_sha256),
            ("training_dataset_sha256", self.training_dataset_sha256),
            ("recipe_id", self.recipe_id),
            ("dependency_lock_sha256", self.dependency_lock_sha256),
            (
                "runtime_qualification_sha256",
                self.runtime_qualification_sha256,
            ),
            (
                "training_authorization_receipt_sha256",
                self.training_authorization_receipt_sha256,
            ),
            ("canonical_corpus_sha256", self.canonical_corpus_sha256),
            (
                "model_verifier_receipt_sha256",
                self.model_verifier_receipt_sha256,
            ),
        ):
            _require_sha256(value, field=field)

        _require_git_sha(self.revision, field="revision")
        _require_git_sha(self.repository_sha, field="repository_sha")
        _require_git_sha(self.repository_tree, field="repository_tree")
        _require_text(self.experiment_id, field="experiment_id")
        _require_text(self.model_id, field="model_id")
        _require_text(self.runner_class, field="runner_class")
        _require_text(self.python_version, field="python_version")
        _require_text(self.os_name, field="os_name")
        _require_text(self.gpu_model, field="gpu_model")

        if not self.seeds:
            raise TrainingExecutionError("seeds must be non-empty")
        if any(type(seed) is not int or seed < 0 for seed in self.seeds):
            raise TrainingExecutionError("seeds must contain non-negative integers only")
        if len(set(self.seeds)) != len(self.seeds):
            raise TrainingExecutionError("seeds must not contain duplicates")
        if (
            type(self.canonical_corpus_byte_count) is not int
            or self.canonical_corpus_byte_count <= 0
        ):
            raise TrainingExecutionError("canonical_corpus_byte_count must be a positive int")
        _require_namespaces(self.result_namespaces)

    @property
    def execution_manifest_sha256(self) -> str:
        """Return the deterministic identity of this backend invocation."""
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """Return the canonical execution-manifest payload."""
        return {
            "canonical_corpus_byte_count": self.canonical_corpus_byte_count,
            "canonical_corpus_sha256": self.canonical_corpus_sha256,
            "corpus_binding_sha256": self.corpus_binding_sha256,
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "environment_sha256": self.environment_sha256,
            "executor_version": self.executor_version,
            "experiment_id": self.experiment_id,
            "gpu_model": self.gpu_model,
            "launch_plan_sha256": self.launch_plan_sha256,
            ("local_asset_attestation_sha256"): self.local_asset_attestation_sha256,
            "model_id": self.model_id,
            "model_verifier_receipt_sha256": (self.model_verifier_receipt_sha256),
            "os_name": self.os_name,
            "python_version": self.python_version,
            "readiness_manifest_sha256": self.readiness_manifest_sha256,
            "recipe_id": self.recipe_id,
            "repository_sha": self.repository_sha,
            "repository_tree": self.repository_tree,
            "result_namespaces": list(self.result_namespaces),
            "revision": self.revision,
            "role": self.role,
            "run_plan_sha256": self.run_plan_sha256,
            "runner_class": self.runner_class,
            "runtime_qualification_sha256": self.runtime_qualification_sha256,
            "seeds": list(self.seeds),
            "training_authorization_receipt_sha256": (self.training_authorization_receipt_sha256),
            "training_dataset_sha256": self.training_dataset_sha256,
            "weights_sha256": self.weights_sha256,
        }


class TrainingBackend(Protocol):
    """Injected backend boundary; default CI supplies fake implementations only."""

    def execute(
        self,
        *,
        manifest: TrainingExecutionManifest,
    ) -> TrainingBackendResult: ...


@dataclass(frozen=True, slots=True)
class TrainingExecutionReceipt:
    """Canonical terminal receipt for one backend invocation."""

    disposition: TrainingExecutionDisposition
    launch_plan_sha256: str
    run_plan_sha256: str
    readiness_manifest_sha256: str
    corpus_binding_sha256: str
    local_asset_attestation_sha256: str
    execution_manifest_sha256: str
    environment_sha256: str
    role: TrainingRole
    experiment_id: str
    model_id: str
    revision: str
    weights_sha256: str
    training_dataset_sha256: str
    repository_sha: str
    repository_tree: str
    dependency_lock_sha256: str
    runtime_qualification_sha256: str
    training_authorization_receipt_sha256: str
    backend_id: str
    backend_version: str
    started_at: str
    finished_at: str
    result_artifacts: tuple[TrainingResultArtifact, ...]
    result_manifest_sha256: str | None
    failure_reason: str | None
    executor_version: str = _EXECUTOR_VERSION

    def __post_init__(self) -> None:
        if self.executor_version != _EXECUTOR_VERSION:
            raise TrainingExecutionError(f"executor_version must be exactly {_EXECUTOR_VERSION}")
        if self.disposition not in ("SUCCEEDED", "FAILED", "ABORTED"):
            raise TrainingExecutionError("receipt disposition is invalid")
        if self.role not in ("compact", "reasoner"):
            raise TrainingExecutionError("role must be compact or reasoner")

        for field, value in (
            ("launch_plan_sha256", self.launch_plan_sha256),
            ("run_plan_sha256", self.run_plan_sha256),
            ("readiness_manifest_sha256", self.readiness_manifest_sha256),
            ("corpus_binding_sha256", self.corpus_binding_sha256),
            (
                "local_asset_attestation_sha256",
                self.local_asset_attestation_sha256,
            ),
            ("execution_manifest_sha256", self.execution_manifest_sha256),
            ("environment_sha256", self.environment_sha256),
            ("weights_sha256", self.weights_sha256),
            ("training_dataset_sha256", self.training_dataset_sha256),
            ("dependency_lock_sha256", self.dependency_lock_sha256),
            (
                "runtime_qualification_sha256",
                self.runtime_qualification_sha256,
            ),
            (
                "training_authorization_receipt_sha256",
                self.training_authorization_receipt_sha256,
            ),
        ):
            _require_sha256(value, field=field)

        if self.result_manifest_sha256 is not None:
            _require_sha256(
                self.result_manifest_sha256,
                field="result_manifest_sha256",
            )
        _require_git_sha(self.revision, field="revision")
        _require_git_sha(self.repository_sha, field="repository_sha")
        _require_git_sha(self.repository_tree, field="repository_tree")
        _require_text(self.experiment_id, field="experiment_id")
        _require_text(self.model_id, field="model_id")
        _require_text(self.backend_id, field="backend_id")
        _require_text(self.backend_version, field="backend_version")
        _require_ordered_timestamps(self.started_at, self.finished_at)
        _require_artifact_tuple(
            self.result_artifacts,
            field="result_artifacts",
        )
        _require_unique_artifact_paths(
            self.result_artifacts,
            field="result_artifacts",
        )

        paths = tuple(item.path for item in self.result_artifacts)
        if paths != tuple(sorted(paths)):
            raise TrainingExecutionError("result_artifacts must use canonical path ordering")

        if self.disposition == "SUCCEEDED":
            if not self.result_artifacts or self.result_manifest_sha256 is None:
                raise TrainingExecutionError(
                    "SUCCEEDED receipt requires artifacts and result manifest"
                )
            if self.failure_reason is not None:
                raise TrainingExecutionError("SUCCEEDED receipt cannot have failure_reason")
            expected = _result_manifest_sha256(self.result_artifacts)
            if self.result_manifest_sha256 != expected:
                raise TrainingExecutionError("result manifest does not match canonical artifacts")
            return

        if self.result_artifacts or self.result_manifest_sha256 is not None:
            raise TrainingExecutionError(
                "FAILED or ABORTED receipt cannot claim canonical artifacts"
            )
        _require_text(self.failure_reason, field="failure_reason")

    @property
    def receipt_sha256(self) -> str:
        """Return the deterministic identity of this receipt."""
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """Return the canonical receipt payload."""
        return {
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "corpus_binding_sha256": self.corpus_binding_sha256,
            "dependency_lock_sha256": self.dependency_lock_sha256,
            "disposition": self.disposition,
            "environment_sha256": self.environment_sha256,
            "execution_manifest_sha256": self.execution_manifest_sha256,
            "executor_version": self.executor_version,
            "experiment_id": self.experiment_id,
            "failure_reason": self.failure_reason,
            "finished_at": self.finished_at,
            "launch_plan_sha256": self.launch_plan_sha256,
            "local_asset_attestation_sha256": (self.local_asset_attestation_sha256),
            "model_id": self.model_id,
            "readiness_manifest_sha256": self.readiness_manifest_sha256,
            "repository_sha": self.repository_sha,
            "repository_tree": self.repository_tree,
            "result_artifacts": [item.to_dict() for item in self.result_artifacts],
            "result_manifest_sha256": self.result_manifest_sha256,
            "revision": self.revision,
            "role": self.role,
            "run_plan_sha256": self.run_plan_sha256,
            "runtime_qualification_sha256": self.runtime_qualification_sha256,
            "started_at": self.started_at,
            "training_authorization_receipt_sha256": (self.training_authorization_receipt_sha256),
            "training_dataset_sha256": self.training_dataset_sha256,
            "weights_sha256": self.weights_sha256,
        }


def execute_training(
    *,
    manifest: TrainingReadinessManifest,
    readiness: TrainingReadinessReport,
    launch_plan: TrainingLaunchPlan,
    corpus_binding: TrainingCorpusBindingReport,
    local_assets: TrainingLocalAssetAttestationReport,
    environment: TrainingExecutionEnvironment,
    role: TrainingRole,
    backend: TrainingBackend | None,
) -> TrainingExecutionReceipt:
    """Revalidate canonical authority and invoke one explicit training backend."""
    _require_exact_input(
        manifest,
        TrainingReadinessManifest,
        field="manifest",
    )
    _require_exact_input(
        readiness,
        TrainingReadinessReport,
        field="readiness",
    )
    _require_exact_input(
        launch_plan,
        TrainingLaunchPlan,
        field="launch_plan",
    )
    _require_exact_input(
        corpus_binding,
        TrainingCorpusBindingReport,
        field="corpus_binding",
    )
    _require_exact_input(
        local_assets,
        TrainingLocalAssetAttestationReport,
        field="local_assets",
    )
    _require_exact_input(
        environment,
        TrainingExecutionEnvironment,
        field="environment",
    )
    if role not in ("compact", "reasoner"):
        raise TrainingExecutionError("role must be compact or reasoner")
    if backend is None:
        raise TrainingExecutionError("an explicit training backend is required")

    (
        manifest,
        readiness,
        launch_plan,
        corpus_binding,
        local_assets,
        environment,
    ) = _snapshot_execution_inputs(
        manifest=manifest,
        readiness=readiness,
        launch_plan=launch_plan,
        corpus_binding=corpus_binding,
        local_assets=local_assets,
        environment=environment,
    )

    rebuilt_launch = _recompute_launch(
        manifest=manifest,
        readiness=readiness,
        launch_plan=launch_plan,
    )
    if launch_plan != rebuilt_launch:
        raise TrainingExecutionError("supplied launch plan does not match recomputed launch plan")

    run_plan = launch_plan.compact if role == "compact" else launch_plan.reasoner
    _require_corpus_binding(corpus_binding, run_plan=run_plan)
    _require_local_attestation(
        local_assets,
        launch_plan=launch_plan,
        run_plan=run_plan,
        corpus_binding=corpus_binding,
        role=role,
    )
    _require_environment(environment, run_plan=run_plan)

    execution_manifest = _build_execution_manifest(
        manifest=manifest,
        launch_plan=launch_plan,
        run_plan=run_plan,
        corpus_binding=corpus_binding,
        local_assets=local_assets,
        environment=environment,
        role=role,
    )
    execution_manifest_sha256 = execution_manifest.execution_manifest_sha256

    try:
        backend_result = backend.execute(manifest=execution_manifest)
    except Exception as exc:
        raise TrainingExecutionError("training backend failed without a canonical result") from exc

    if execution_manifest.execution_manifest_sha256 != execution_manifest_sha256:
        raise TrainingExecutionError("backend mutated the core-owned execution manifest")
    if type(backend_result) is not TrainingBackendResult:
        raise TrainingExecutionError("backend returned a non-canonical TrainingBackendResult")

    result = _snapshot_backend_result(backend_result)
    artifacts = tuple(sorted(result.artifacts, key=lambda item: item.path))
    result_manifest_sha256: str | None = None
    if result.disposition == "SUCCEEDED":
        _require_result_namespaces(
            artifacts,
            namespaces=execution_manifest.result_namespaces,
        )
        result_manifest_sha256 = _result_manifest_sha256(artifacts)

    return TrainingExecutionReceipt(
        disposition=result.disposition,
        launch_plan_sha256=execution_manifest.launch_plan_sha256,
        run_plan_sha256=execution_manifest.run_plan_sha256,
        readiness_manifest_sha256=(execution_manifest.readiness_manifest_sha256),
        corpus_binding_sha256=execution_manifest.corpus_binding_sha256,
        local_asset_attestation_sha256=(execution_manifest.local_asset_attestation_sha256),
        execution_manifest_sha256=execution_manifest_sha256,
        environment_sha256=execution_manifest.environment_sha256,
        role=execution_manifest.role,
        experiment_id=execution_manifest.experiment_id,
        model_id=execution_manifest.model_id,
        revision=execution_manifest.revision,
        weights_sha256=execution_manifest.weights_sha256,
        training_dataset_sha256=(execution_manifest.training_dataset_sha256),
        repository_sha=execution_manifest.repository_sha,
        repository_tree=execution_manifest.repository_tree,
        dependency_lock_sha256=(execution_manifest.dependency_lock_sha256),
        runtime_qualification_sha256=(execution_manifest.runtime_qualification_sha256),
        training_authorization_receipt_sha256=(
            execution_manifest.training_authorization_receipt_sha256
        ),
        backend_id=result.backend_id,
        backend_version=result.backend_version,
        started_at=result.started_at,
        finished_at=result.finished_at,
        result_artifacts=artifacts,
        result_manifest_sha256=result_manifest_sha256,
        failure_reason=result.failure_reason,
    )


def _snapshot_execution_inputs(
    *,
    manifest: TrainingReadinessManifest,
    readiness: TrainingReadinessReport,
    launch_plan: TrainingLaunchPlan,
    corpus_binding: TrainingCorpusBindingReport,
    local_assets: TrainingLocalAssetAttestationReport,
    environment: TrainingExecutionEnvironment,
) -> tuple[
    TrainingReadinessManifest,
    TrainingReadinessReport,
    TrainingLaunchPlan,
    TrainingCorpusBindingReport,
    TrainingLocalAssetAttestationReport,
    TrainingExecutionEnvironment,
]:
    _require_nested_canonical_types(manifest=manifest, launch_plan=launch_plan)
    try:
        compact_recipe = replace(
            manifest.compact_recipe,
            base=replace(manifest.compact_recipe.base),
            dataset=replace(manifest.compact_recipe.dataset),
        )
        reasoner_recipe = replace(
            manifest.reasoner_recipe,
            base=replace(manifest.reasoner_recipe.base),
            dataset=replace(manifest.reasoner_recipe.dataset),
        )
        manifest_snapshot = replace(
            manifest,
            compact_candidate=replace(manifest.compact_candidate),
            reasoner_candidate=replace(manifest.reasoner_candidate),
            compact_recipe=compact_recipe,
            reasoner_recipe=reasoner_recipe,
        )
        launch_snapshot = replace(
            launch_plan,
            compact=replace(launch_plan.compact),
            reasoner=replace(launch_plan.reasoner),
        )
        return (
            manifest_snapshot,
            replace(readiness),
            launch_snapshot,
            replace(corpus_binding),
            replace(local_assets),
            replace(environment),
        )
    except Exception as exc:
        raise TrainingExecutionError(
            "canonical execution inputs could not be reconstructed"
        ) from exc


def _require_nested_canonical_types(
    *,
    manifest: TrainingReadinessManifest,
    launch_plan: TrainingLaunchPlan,
) -> None:
    checks: tuple[tuple[str, object, type[object]], ...] = (
        ("manifest.compact_candidate", manifest.compact_candidate, TrainingCandidate),
        ("manifest.reasoner_candidate", manifest.reasoner_candidate, TrainingCandidate),
        ("manifest.compact_recipe", manifest.compact_recipe, TrainingRecipe),
        ("manifest.reasoner_recipe", manifest.reasoner_recipe, TrainingRecipe),
        ("launch_plan.compact", launch_plan.compact, TrainingRunPlan),
        ("launch_plan.reasoner", launch_plan.reasoner, TrainingRunPlan),
    )
    for field, value, expected_type in checks:
        _require_exact_input(value, expected_type, field=field)

    for field, recipe in (
        ("manifest.compact_recipe", manifest.compact_recipe),
        ("manifest.reasoner_recipe", manifest.reasoner_recipe),
    ):
        _require_exact_input(recipe.base, ModelRef, field=f"{field}.base")
        _require_exact_input(recipe.dataset, DatasetRef, field=f"{field}.dataset")
        _require_exact_input(recipe.method, AdapterMethod, field=f"{field}.method")


def _recompute_launch(
    *,
    manifest: TrainingReadinessManifest,
    readiness: TrainingReadinessReport,
    launch_plan: TrainingLaunchPlan,
) -> TrainingLaunchPlan:
    try:
        recomputed = assess_training_readiness(manifest)
        if readiness != recomputed:
            raise TrainingExecutionError(
                "supplied readiness report does not match recomputed readiness"
            )
        if not recomputed.can_launch_training:
            raise TrainingExecutionError("recomputed readiness is not READY_TO_LAUNCH")
        return build_training_launch_plan(
            manifest=manifest,
            readiness=recomputed,
            compact=launch_plan.compact,
            reasoner=launch_plan.reasoner,
        )
    except TrainingExecutionError:
        raise
    except (TypeError, ValueError) as exc:
        raise TrainingExecutionError("upstream readiness or launch recomputation failed") from exc


def _require_corpus_binding(
    binding: TrainingCorpusBindingReport,
    *,
    run_plan: TrainingRunPlan,
) -> None:
    if binding.disposition != "PASS" or not binding.can_attest_local_artifact:
        raise TrainingExecutionError("corpus binding is not canonical PASS")
    if binding.training_dataset_sha256 != run_plan.training_dataset_sha256:
        raise TrainingExecutionError("corpus binding training dataset does not match selected run")
    if binding.canonical_jsonl_byte_count <= 0:
        raise TrainingExecutionError("canonical corpus must be non-empty")


def _require_local_attestation(
    attestation: TrainingLocalAssetAttestationReport,
    *,
    launch_plan: TrainingLaunchPlan,
    run_plan: TrainingRunPlan,
    corpus_binding: TrainingCorpusBindingReport,
    role: TrainingRole,
) -> None:
    if attestation.disposition != "PASS" or not attestation.can_execute_training:
        raise TrainingExecutionError("local asset attestation is not canonical PASS")

    expected: tuple[tuple[str, object, object], ...] = (
        ("role", attestation.role, role),
        (
            "launch_plan_sha256",
            attestation.launch_plan_sha256,
            launch_plan.plan_sha256,
        ),
        (
            "run_plan_sha256",
            attestation.run_plan_sha256,
            run_plan.run_plan_sha256,
        ),
        (
            "corpus_binding_sha256",
            attestation.corpus_binding_sha256,
            corpus_binding.binding_sha256,
        ),
        (
            "training_dataset_sha256",
            attestation.training_dataset_sha256,
            run_plan.training_dataset_sha256,
        ),
        ("model_id", attestation.model_id, run_plan.model_id),
        ("revision", attestation.revision, run_plan.revision),
        (
            "expected_weights_sha256",
            attestation.expected_weights_sha256,
            run_plan.weights_sha256,
        ),
        (
            "observed_weights_sha256",
            attestation.observed_weights_sha256,
            run_plan.weights_sha256,
        ),
        (
            "expected_corpus_sha256",
            attestation.expected_corpus_sha256,
            corpus_binding.canonical_jsonl_sha256,
        ),
        (
            "observed_corpus_sha256",
            attestation.observed_corpus_sha256,
            corpus_binding.canonical_jsonl_sha256,
        ),
        (
            "expected_corpus_byte_count",
            attestation.expected_corpus_byte_count,
            corpus_binding.canonical_jsonl_byte_count,
        ),
        (
            "observed_corpus_byte_count",
            attestation.observed_corpus_byte_count,
            corpus_binding.canonical_jsonl_byte_count,
        ),
    )
    for field, actual, wanted in expected:
        if actual != wanted:
            raise TrainingExecutionError(f"local asset attestation {field} does not match")

    if (
        attestation.model_network_accessed
        or attestation.model_remote_code_allowed
        or attestation.model_gated_terms_accepted
    ):
        raise TrainingExecutionError(
            "local asset attestation contains forbidden security observations"
        )
    if attestation.model_verifier_receipt_sha256 is None:
        raise TrainingExecutionError("local asset attestation lacks model verifier receipt")


def _require_environment(
    environment: TrainingExecutionEnvironment,
    *,
    run_plan: TrainingRunPlan,
) -> None:
    expected: tuple[tuple[str, object, object], ...] = (
        ("repository_sha", environment.repository_sha, run_plan.repository_sha),
        (
            "repository_tree",
            environment.repository_tree,
            run_plan.repository_tree,
        ),
        (
            "dependency_lock_sha256",
            environment.dependency_lock_sha256,
            run_plan.dependency_lock_sha256,
        ),
        ("runner_class", environment.runner_class, run_plan.runner_class),
        (
            "python_version",
            environment.python_version,
            run_plan.python_version,
        ),
        ("os_name", environment.os_name, run_plan.os_name),
        ("gpu_model", environment.gpu_model, run_plan.gpu_model),
    )
    for field, actual, wanted in expected:
        if actual != wanted:
            raise TrainingExecutionError(
                f"execution environment {field} does not match selected run"
            )


def _build_execution_manifest(
    *,
    manifest: TrainingReadinessManifest,
    launch_plan: TrainingLaunchPlan,
    run_plan: TrainingRunPlan,
    corpus_binding: TrainingCorpusBindingReport,
    local_assets: TrainingLocalAssetAttestationReport,
    environment: TrainingExecutionEnvironment,
    role: TrainingRole,
) -> TrainingExecutionManifest:
    verifier_receipt = local_assets.model_verifier_receipt_sha256
    if verifier_receipt is None:
        raise TrainingExecutionError("local asset attestation lacks model verifier receipt")
    return TrainingExecutionManifest(
        role=role,
        launch_plan_sha256=launch_plan.plan_sha256,
        run_plan_sha256=run_plan.run_plan_sha256,
        readiness_manifest_sha256=manifest.manifest_sha256,
        corpus_binding_sha256=corpus_binding.binding_sha256,
        local_asset_attestation_sha256=local_assets.attestation_sha256,
        environment_sha256=environment.environment_sha256,
        experiment_id=run_plan.experiment_id,
        model_id=run_plan.model_id,
        revision=run_plan.revision,
        weights_sha256=run_plan.weights_sha256,
        training_dataset_sha256=run_plan.training_dataset_sha256,
        recipe_id=run_plan.recipe_id,
        seeds=tuple(run_plan.seeds),
        runner_class=run_plan.runner_class.value,
        python_version=run_plan.python_version,
        os_name=run_plan.os_name,
        gpu_model=run_plan.gpu_model,
        repository_sha=run_plan.repository_sha,
        repository_tree=run_plan.repository_tree,
        dependency_lock_sha256=run_plan.dependency_lock_sha256,
        runtime_qualification_sha256=(launch_plan.runtime_qualification_sha256),
        training_authorization_receipt_sha256=(launch_plan.training_authorization_receipt_sha256),
        canonical_corpus_sha256=corpus_binding.canonical_jsonl_sha256,
        canonical_corpus_byte_count=corpus_binding.canonical_jsonl_byte_count,
        model_verifier_receipt_sha256=verifier_receipt,
        result_namespaces=tuple(run_plan.result_paths),
    )


def _snapshot_backend_result(
    result: TrainingBackendResult,
) -> TrainingBackendResult:
    try:
        artifacts = tuple(
            TrainingResultArtifact(
                path=item.path,
                sha256=item.sha256,
                byte_count=item.byte_count,
            )
            for item in result.artifacts
        )
        return TrainingBackendResult(
            disposition=result.disposition,
            backend_id=result.backend_id,
            backend_version=result.backend_version,
            started_at=result.started_at,
            finished_at=result.finished_at,
            artifacts=artifacts,
            failure_reason=result.failure_reason,
        )
    except (AttributeError, TypeError, TrainingExecutionError) as exc:
        raise TrainingExecutionError("backend result could not be snapshotted canonically") from exc


def _require_namespaces(namespaces: tuple[str, ...]) -> None:
    if not isinstance(namespaces, tuple) or not namespaces:
        raise TrainingExecutionError("result_namespaces must be a non-empty immutable tuple")
    if len(set(namespaces)) != len(namespaces):
        raise TrainingExecutionError("result_namespaces must be unique")

    paths = tuple(PurePosixPath(path) for path in namespaces)
    for path in namespaces:
        _require_repository_relative_path(path, field="result namespace")
    for index, left in enumerate(paths):
        for right in paths[index + 1 :]:
            if left in right.parents or right in left.parents:
                raise TrainingExecutionError("result_namespaces must be disjoint")


def _require_result_namespaces(
    artifacts: tuple[TrainingResultArtifact, ...],
    *,
    namespaces: tuple[str, ...],
) -> None:
    namespace_paths = tuple(PurePosixPath(path) for path in namespaces)
    artifact_paths = tuple(PurePosixPath(item.path) for item in artifacts)

    for path in artifact_paths:
        if not any(path == namespace or namespace in path.parents for namespace in namespace_paths):
            raise TrainingExecutionError(
                "backend result artifact escapes planned result namespaces"
            )
    for namespace in namespace_paths:
        if not any(path == namespace or namespace in path.parents for path in artifact_paths):
            raise TrainingExecutionError(
                "backend result does not represent every planned result namespace"
            )


def _result_manifest_sha256(
    artifacts: tuple[TrainingResultArtifact, ...],
) -> str:
    return content_hash(
        {
            "artifacts": [item.to_dict() for item in artifacts],
            "kind": _RESULT_MANIFEST_KIND,
        }
    )


def _require_artifact_tuple(
    artifacts: object,
    *,
    field: str,
) -> None:
    if not isinstance(artifacts, tuple):
        raise TrainingExecutionError(f"{field} must be an immutable tuple")
    if any(type(item) is not TrainingResultArtifact for item in artifacts):
        raise TrainingExecutionError(f"{field} must contain exact TrainingResultArtifact values")


def _require_unique_artifact_paths(
    artifacts: tuple[TrainingResultArtifact, ...],
    *,
    field: str,
) -> None:
    paths = tuple(item.path for item in artifacts)
    if len(set(paths)) != len(paths):
        raise TrainingExecutionError(f"{field} paths must be unique")


def _require_ordered_timestamps(started_at: str, finished_at: str) -> None:
    started = _parse_timestamp(started_at, field="started_at")
    finished = _parse_timestamp(finished_at, field="finished_at")
    if finished < started:
        raise TrainingExecutionError("finished_at must not precede started_at")


def _require_exact_input(
    value: object,
    expected_type: type[object],
    *,
    field: str,
) -> None:
    if type(value) is not expected_type:
        raise TrainingExecutionError(f"{field} must use its exact canonical type")


def _require_repository_relative_path(
    value: object,
    *,
    field: str,
) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise TrainingExecutionError(f"{field} must be a non-empty POSIX repository path")
    path = PurePosixPath(value)
    canonical = str(path)
    if path.is_absolute() or canonical == "." or ".." in path.parts:
        raise TrainingExecutionError(f"{field} must remain inside the repository")
    if canonical != value:
        raise TrainingExecutionError(f"{field} must use canonical POSIX spelling")
    return value


def _parse_timestamp(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or _TIMESTAMP.fullmatch(value) is None:
        raise TrainingExecutionError(f"{field} must be canonical UTC RFC3339 seconds")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise TrainingExecutionError(f"{field} must be a valid UTC timestamp") from exc


def _require_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise TrainingExecutionError(f"{field} must be exactly 64 lowercase hex characters")
    return value


def _require_git_sha(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _GIT_SHA.fullmatch(value) is None:
        raise TrainingExecutionError(f"{field} must be exactly 40 lowercase hex characters")
    return value


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise TrainingExecutionError(f"{field} must be non-empty NUL-free text")
    return value
