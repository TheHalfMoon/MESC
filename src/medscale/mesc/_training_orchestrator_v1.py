"""Fail-closed MESC training CLI/orchestrator boundary.

Observes the local repository, lock, Python, OS, and GPU identities; consumes already
canonical readiness, launch, corpus-binding, and local-asset evidence; constructs the
explicit Hugging Face local SFT backend; and invokes ``execute_training`` only when every
required authority already matches.

This module does not invent runtime-qualification or training-authorization receipts, does
not download models, does not accept gated terms, and does not claim that implementation
equals authorized real training.
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Final

from medscale.mesc._training_corpus_binding_v1 import TrainingCorpusBindingReport
from medscale.mesc._training_executor_v1 import (
    TrainingBackend,
    TrainingExecutionEnvironment,
    TrainingExecutionReceipt,
    execute_training,
)
from medscale.mesc._training_hf_local_sft_backend_v1 import (
    HfLocalSftBackend,
    HfLocalSftRuntime,
    build_hf_local_sft_runtime,
)
from medscale.mesc._training_hf_safetensors_identity_v1 import (
    HfSafeTensorsLocalModelVerifier,
)
from medscale.mesc._training_launch_plan_v1 import (
    TrainingLaunchPlan,
    TrainingRole,
    TrainingRunPlan,
    build_training_launch_plan,
)
from medscale.mesc._training_local_asset_attestation_v1 import (
    LocalModelAssetVerifier,
    attest_local_training_assets,
)
from medscale.mesc._training_readiness_v1 import (
    TrainingReadinessManifest,
    TrainingReadinessReport,
    assess_training_readiness,
)
from medscale.modelkit.manifests import RunnerClass
from medscale.modelkit.recipes import TrainingRecipe

_ORCHESTRATOR_VERSION: Final = "MESC-TRAINING-ORCHESTRATOR-V1"
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_SHA256_CHUNK: Final = 1024 * 1024
_O_BINARY: Final = getattr(os, "O_BINARY", 0)
_O_NOFOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)

GpuProbe = Callable[[], str]
BackendFactory = Callable[
    [TrainingRecipe, Path, Path, Path, HfLocalSftRuntime],
    TrainingBackend,
]


class TrainingOrchestratorError(ValueError):
    """Raised when the orchestrator cannot fail-closed into ``execute_training``."""


def hash_dependency_lock(lock_path: Path) -> str:
    """Return the SHA-256 of the exact ``uv.lock`` bytes (no-follow)."""
    if not isinstance(lock_path, Path):
        raise TrainingOrchestratorError("lock_path must be an exact pathlib.Path")
    if lock_path.is_symlink():
        raise TrainingOrchestratorError("dependency lock path must not be a symlink")
    try:
        flags = os.O_RDONLY | _O_BINARY | _O_NOFOLLOW
        fd = os.open(os.fspath(lock_path), flags)
    except OSError as exc:
        raise TrainingOrchestratorError("dependency lock cannot be opened") from exc
    try:
        digest = hashlib.sha256()
        total = 0
        while True:
            chunk = os.read(fd, _SHA256_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
        if total <= 0:
            raise TrainingOrchestratorError("dependency lock must be non-empty")
        return digest.hexdigest()
    finally:
        os.close(fd)


def observe_repository_identity(repository_root: Path) -> tuple[str, str]:
    """Observe exact ``HEAD`` commit SHA and tree SHA from the local git repository."""
    if not isinstance(repository_root, Path):
        raise TrainingOrchestratorError("repository_root must be an exact pathlib.Path")
    if not repository_root.is_dir():
        raise TrainingOrchestratorError("repository_root must be an existing directory")
    commit = _git_rev_parse(repository_root, "HEAD")
    tree = _git_rev_parse(repository_root, "HEAD^{tree}")
    return commit, tree


def observe_python_version() -> str:
    """Observe the exact running Python version string."""
    return platform.python_version()


def observe_os_name() -> str:
    """Observe the canonical lowercase OS name for environment binding."""
    return platform.system().lower()


def observe_gpu_model(*, gpu_probe: GpuProbe | None = None) -> str:
    """Observe the GPU identity required by the launch plan.

    Callers must supply an explicit ``gpu_probe`` when automatic probing is unavailable.
    The default probe refuses to invent a GPU identity.
    """
    probe = _default_gpu_probe if gpu_probe is None else gpu_probe
    try:
        value = probe()
    except TrainingOrchestratorError:
        raise
    except Exception as exc:
        raise TrainingOrchestratorError("gpu probe failed") from exc
    if not isinstance(value, str) or not value.strip():
        raise TrainingOrchestratorError("gpu_model must be a non-empty string")
    return value.strip()


def observe_training_execution_environment(
    *,
    repository_root: Path,
    runner_class: RunnerClass,
    lock_path: Path | None = None,
    gpu_probe: GpuProbe | None = None,
    python_version: str | None = None,
    os_name: str | None = None,
) -> TrainingExecutionEnvironment:
    """Observe the local execution environment that must equal one selected run plan."""
    if not isinstance(runner_class, RunnerClass):
        raise TrainingOrchestratorError("runner_class must be a RunnerClass")
    resolved_lock = repository_root / "uv.lock" if lock_path is None else lock_path
    repository_sha, repository_tree = observe_repository_identity(repository_root)
    return TrainingExecutionEnvironment(
        repository_sha=repository_sha,
        repository_tree=repository_tree,
        dependency_lock_sha256=hash_dependency_lock(resolved_lock),
        runner_class=runner_class,
        python_version=observe_python_version() if python_version is None else python_version,
        os_name=observe_os_name() if os_name is None else os_name,
        gpu_model=observe_gpu_model(gpu_probe=gpu_probe),
    )


def run_training_orchestrator(
    *,
    manifest: TrainingReadinessManifest,
    launch_plan: TrainingLaunchPlan,
    corpus_binding: TrainingCorpusBindingReport,
    role: TrainingRole,
    model_root: Path,
    corpus_path: Path,
    repository_root: Path,
    readiness: TrainingReadinessReport | None = None,
    recipe: TrainingRecipe | None = None,
    environment: TrainingExecutionEnvironment | None = None,
    verifier: LocalModelAssetVerifier | None = None,
    runtime: HfLocalSftRuntime | None = None,
    backend_factory: BackendFactory | None = None,
    lock_path: Path | None = None,
    gpu_probe: GpuProbe | None = None,
) -> TrainingExecutionReceipt:
    """Fail-closed orchestration into the canonical training executor."""
    if type(manifest) is not TrainingReadinessManifest:
        raise TrainingOrchestratorError("manifest must be an exact TrainingReadinessManifest")
    if type(launch_plan) is not TrainingLaunchPlan:
        raise TrainingOrchestratorError("launch_plan must be an exact TrainingLaunchPlan")
    if type(corpus_binding) is not TrainingCorpusBindingReport:
        raise TrainingOrchestratorError(
            "corpus_binding must be an exact TrainingCorpusBindingReport"
        )
    if role not in ("compact", "reasoner"):
        raise TrainingOrchestratorError("role must be compact or reasoner")
    for field, value in (
        ("model_root", model_root),
        ("corpus_path", corpus_path),
        ("repository_root", repository_root),
    ):
        if not isinstance(value, Path):
            raise TrainingOrchestratorError(f"{field} must be an exact pathlib.Path")

    assessed = assess_training_readiness(manifest) if readiness is None else readiness
    if type(assessed) is not TrainingReadinessReport:
        raise TrainingOrchestratorError("readiness must be an exact TrainingReadinessReport")
    if assessed.manifest_sha256 != manifest.manifest_sha256:
        raise TrainingOrchestratorError("readiness report is not bound to the supplied manifest")
    if not assessed.can_launch_training:
        raise TrainingOrchestratorError(
            f"training readiness disposition is {assessed.disposition}, not READY_TO_LAUNCH"
        )

    rebuilt = build_training_launch_plan(
        manifest=manifest,
        readiness=assessed,
        compact=launch_plan.compact,
        reasoner=launch_plan.reasoner,
    )
    if rebuilt != launch_plan:
        raise TrainingOrchestratorError(
            "supplied launch plan does not match recomputed launch plan"
        )

    run_plan = launch_plan.compact if role == "compact" else launch_plan.reasoner
    selected_recipe = (
        manifest.compact_recipe
        if recipe is None and role == "compact"
        else manifest.reasoner_recipe
        if recipe is None
        else recipe
    )
    if type(selected_recipe) is not TrainingRecipe:
        raise TrainingOrchestratorError("recipe must be an exact TrainingRecipe")
    if selected_recipe.recipe_id != run_plan.recipe_id:
        raise TrainingOrchestratorError("recipe identity does not match the selected run plan")

    observed_environment = (
        observe_training_execution_environment(
            repository_root=repository_root,
            runner_class=run_plan.runner_class,
            lock_path=lock_path,
            gpu_probe=gpu_probe,
        )
        if environment is None
        else environment
    )
    if type(observed_environment) is not TrainingExecutionEnvironment:
        raise TrainingOrchestratorError("environment must be an exact TrainingExecutionEnvironment")
    _require_environment_match(observed_environment, run_plan=run_plan)

    selected_verifier: LocalModelAssetVerifier = (
        HfSafeTensorsLocalModelVerifier() if verifier is None else verifier
    )
    local_assets = attest_local_training_assets(
        launch_plan=launch_plan,
        corpus_binding=corpus_binding,
        role=role,
        model_root=model_root,
        corpus_path=corpus_path,
        verifier=selected_verifier,
    )
    if not local_assets.can_execute_training:
        blockers = ", ".join(local_assets.blockers) if local_assets.blockers else "unknown"
        raise TrainingOrchestratorError(f"local asset attestation blocked: {blockers}")

    selected_runtime = build_hf_local_sft_runtime() if runtime is None else runtime
    factory = _default_backend_factory if backend_factory is None else backend_factory
    try:
        backend = factory(
            selected_recipe,
            model_root,
            corpus_path,
            repository_root,
            selected_runtime,
        )
    except TrainingOrchestratorError:
        raise
    except Exception as exc:
        raise TrainingOrchestratorError("backend factory failed") from exc
    if backend is None:
        raise TrainingOrchestratorError("an explicit training backend is required")

    return execute_training(
        manifest=manifest,
        readiness=assessed,
        launch_plan=launch_plan,
        corpus_binding=corpus_binding,
        local_assets=local_assets,
        environment=observed_environment,
        role=role,
        backend=backend,
    )


def _default_backend_factory(
    recipe: TrainingRecipe,
    model_root: Path,
    corpus_path: Path,
    repository_root: Path,
    runtime: HfLocalSftRuntime,
) -> TrainingBackend:
    return HfLocalSftBackend(
        recipe=recipe,
        model_root=model_root,
        corpus_path=corpus_path,
        repository_root=repository_root,
        runtime=runtime,
    )


def _default_gpu_probe() -> str:
    raise TrainingOrchestratorError(
        "gpu_model cannot be invented; supply gpu_probe with the observed GPU identity"
    )


def _git_rev_parse(repository_root: Path, rev: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", rev],
            cwd=os.fspath(repository_root),
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        raise TrainingOrchestratorError("git rev-parse could not be executed") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown git error"
        raise TrainingOrchestratorError(f"git rev-parse failed: {detail}")
    value = completed.stdout.strip().lower()
    if _GIT_SHA.fullmatch(value) is None:
        raise TrainingOrchestratorError(f"git rev-parse returned a non-canonical SHA for {rev}")
    return value


def _require_environment_match(
    environment: TrainingExecutionEnvironment,
    *,
    run_plan: TrainingRunPlan,
) -> None:
    if type(run_plan) is not TrainingRunPlan:
        raise TrainingOrchestratorError("run_plan must be an exact TrainingRunPlan")
    comparisons = (
        ("repository_sha", environment.repository_sha, run_plan.repository_sha),
        ("repository_tree", environment.repository_tree, run_plan.repository_tree),
        (
            "dependency_lock_sha256",
            environment.dependency_lock_sha256,
            run_plan.dependency_lock_sha256,
        ),
        ("runner_class", environment.runner_class, run_plan.runner_class),
        ("python_version", environment.python_version, run_plan.python_version),
        ("os_name", environment.os_name, run_plan.os_name),
        ("gpu_model", environment.gpu_model, run_plan.gpu_model),
    )
    for field, observed, expected in comparisons:
        if observed != expected:
            raise TrainingOrchestratorError(
                f"observed {field} does not match the selected run plan"
            )


__all__ = [
    "BackendFactory",
    "GpuProbe",
    "TrainingOrchestratorError",
    "hash_dependency_lock",
    "observe_gpu_model",
    "observe_os_name",
    "observe_python_version",
    "observe_repository_identity",
    "observe_training_execution_environment",
    "run_training_orchestrator",
]
