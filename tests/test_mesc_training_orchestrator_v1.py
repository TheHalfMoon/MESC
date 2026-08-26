"""Qualification tests for the fail-closed MESC training orchestrator."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

import medscale.mesc._training_orchestrator_v1 as orchestrator_module
from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._training_authorization_receipt_v1 import (
    build_training_authorization_receipt,
)
from medscale.mesc._training_corpus_binding_v1 import TrainingCorpusBindingReport
from medscale.mesc._training_executor_v1 import (
    TrainingBackendResult,
    TrainingExecutionEnvironment,
    TrainingExecutionManifest,
    TrainingResultArtifact,
)
from medscale.mesc._training_launch_plan_v1 import (
    TrainingLaunchPlan,
    TrainingRole,
    TrainingRunPlan,
    build_training_launch_plan,
)
from medscale.mesc._training_local_asset_attestation_v1 import LocalModelAssetObservation
from medscale.mesc._training_orchestrator_v1 import (
    TrainingOrchestratorError,
    hash_dependency_lock,
    observe_gpu_model,
    observe_repository_identity,
    observe_training_execution_environment,
    run_training_orchestrator,
)
from medscale.mesc._training_readiness_v1 import (
    TrainingCandidate,
    TrainingReadinessManifest,
    assess_training_readiness,
)
from medscale.mesc._training_runtime_qualification_v1 import (
    TrainingRuntimeQualificationReceipt,
    TrainingRuntimeSmokeEvidence,
    build_training_runtime_qualification_receipt,
)
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.manifests import RunnerClass
from medscale.modelkit.recipes import AdapterMethod, DatasetRef, TrainingRecipe

_DATASET_SHA = "d" * 64
_REPOSITORY_SHA = "a" * 40
_REPOSITORY_TREE = "b" * 40
_LOCK_SHA = "c" * 64
_CORPUS_SHA = "f" * 64
_CORPUS_RAW_SHA = "6" * 64
_VERIFIER_SHA = "5" * 64
_PYTHON = "3.12.14"
_OS = "linux"
_GPU = "fixture-gpu"


def _candidate(*, role: TrainingRole) -> TrainingCandidate:
    if role == "compact":
        return TrainingCandidate(
            model_id="fixture/compact",
            revision="1" * 40,
            weights_sha256="4" * 64,
            license_id="apache-2.0",
        )
    return TrainingCandidate(
        model_id="fixture/reasoner",
        revision="2" * 40,
        weights_sha256="9" * 64,
        license_id="apache-2.0",
    )


def _recipe(candidate: TrainingCandidate) -> TrainingRecipe:
    return TrainingRecipe(
        base=ModelRef(
            model_id=candidate.model_id,
            revision=candidate.revision,
            quantization="nf4",
            backend="transformers",
        ),
        method=AdapterMethod.QLORA,
        dataset=DatasetRef(
            name="mesc-evidence-sft-v1",
            version="1.0.0",
            content_sha256=_DATASET_SHA,
        ),
        seed=42,
        max_steps=100,
    )


def _runtime_receipt(
    *, dependency_lock_sha256: str = _LOCK_SHA
) -> TrainingRuntimeQualificationReceipt:
    smoke = TrainingRuntimeSmokeEvidence(
        canonical_json_bytes(
            {
                "dependency_lock_sha256": dependency_lock_sha256,
                "disposition": "PASS",
                "gpu_model": _GPU,
                "kind": "mesc.training_runtime_smoke.v1",
                "network_accessed": False,
                "os_name": _OS,
                "probe_id": "fixture-probe",
                "probe_version": "v1",
                "python_version": _PYTHON,
                "remote_code_allowed": False,
                "repository_sha": _REPOSITORY_SHA,
                "repository_tree": _REPOSITORY_TREE,
                "runner_class": RunnerClass.LOCAL.value,
            }
        )
    )
    return build_training_runtime_qualification_receipt(
        runner_class=RunnerClass.LOCAL,
        python_version=_PYTHON,
        os_name=_OS,
        gpu_model=_GPU,
        dependency_lock_sha256=dependency_lock_sha256,
        repository_sha=_REPOSITORY_SHA,
        repository_tree=_REPOSITORY_TREE,
        probe_id="fixture-probe",
        probe_version="v1",
        smoke_evidence=smoke,
    )


def _readiness_manifest(
    *,
    dependency_lock_sha256: str = _LOCK_SHA,
    corpus_binding_sha256: str = _CORPUS_SHA,
) -> TrainingReadinessManifest:
    compact = _candidate(role="compact")
    reasoner = _candidate(role="reasoner")
    runtime = _runtime_receipt(dependency_lock_sha256=dependency_lock_sha256)
    pre = TrainingReadinessManifest(
        compact_candidate=compact,
        reasoner_candidate=reasoner,
        compact_recipe=_recipe(compact),
        reasoner_recipe=_recipe(reasoner),
        pilot_closeout_sha256="1" * 64,
        tournament_report_sha256="2" * 64,
        training_dataset_sha256=_DATASET_SHA,
        provenance_ledger_sha256="3" * 64,
        decontamination_report_sha256="4" * 64,
        evaluation_contract_sha256="a" * 64,
        license_review_sha256="e" * 64,
        pilot_closeout_disposition="PASS",
        tournament_disposition="PASS",
        decontamination_disposition="PASS",
        license_disposition="PASS",
        r2_training_data_only=True,
        heldout_eval_excluded_from_training=True,
        phi_present=False,
        corpus_binding_sha256=corpus_binding_sha256,
        runtime_qualification_sha256=runtime.receipt_sha256,
        runtime_qualification_receipt=runtime,
    )
    authorization = build_training_authorization_receipt(
        authorizer_id="fixture-founder",
        authorization_subject_sha256=pre.authorization_subject_sha256,
        runtime_qualification_sha256=runtime.receipt_sha256,
        corpus_binding_sha256=corpus_binding_sha256,
        authorization_statement="Fixture authorization for the exact launch subject.",
        authorize=True,
    )
    return replace(
        pre,
        training_authorization_receipt_sha256=authorization.receipt_sha256,
        training_authorization_receipt=authorization,
    )


def _run(
    manifest: TrainingReadinessManifest,
    *,
    role: TrainingRole,
    repository_sha: str = _REPOSITORY_SHA,
    repository_tree: str = _REPOSITORY_TREE,
    dependency_lock_sha256: str = _LOCK_SHA,
    python_version: str = _PYTHON,
    os_name: str = _OS,
    gpu_model: str = _GPU,
) -> TrainingRunPlan:
    if role == "compact":
        candidate = manifest.compact_candidate
        recipe = manifest.compact_recipe
        experiment_id = "mesc-t6-compact-sft"
    else:
        candidate = manifest.reasoner_candidate
        recipe = manifest.reasoner_recipe
        experiment_id = "mesc-t6-reasoner-sft"

    return TrainingRunPlan(
        role=role,
        experiment_id=experiment_id,
        rq_refs=("RQ1",),
        recipe_id=recipe.recipe_id,
        model_id=candidate.model_id,
        revision=candidate.revision,
        weights_sha256=candidate.weights_sha256,
        training_dataset_sha256=manifest.training_dataset_sha256,
        seeds=(17, 42, 91),
        runner_class=RunnerClass.LOCAL,
        python_version=python_version,
        os_name=os_name,
        gpu_model=gpu_model,
        dependency_lock_sha256=dependency_lock_sha256,
        repository_sha=repository_sha,
        repository_tree=repository_tree,
        result_paths=(
            f"experiments/{experiment_id}/outputs",
            f"experiments/{experiment_id}/results",
        ),
        reproduction_command=(
            'python -c "from medscale.mesc._training_orchestrator_v1 import '
            f"run_training_orchestrator; run_training_orchestrator(role='{role}')\""
        ),
    )


def _launch(
    manifest: TrainingReadinessManifest,
    *,
    repository_sha: str = _REPOSITORY_SHA,
    repository_tree: str = _REPOSITORY_TREE,
    dependency_lock_sha256: str = _LOCK_SHA,
) -> TrainingLaunchPlan:
    readiness = assess_training_readiness(manifest)
    return build_training_launch_plan(
        manifest=manifest,
        readiness=readiness,
        compact=_run(
            manifest,
            role="compact",
            repository_sha=repository_sha,
            repository_tree=repository_tree,
            dependency_lock_sha256=dependency_lock_sha256,
        ),
        reasoner=_run(
            manifest,
            role="reasoner",
            repository_sha=repository_sha,
            repository_tree=repository_tree,
            dependency_lock_sha256=dependency_lock_sha256,
        ),
    )


def _binding(raw: bytes) -> TrainingCorpusBindingReport:
    return TrainingCorpusBindingReport(
        disposition="PASS",
        qualification_sha256="1" * 64,
        training_dataset_sha256=_DATASET_SHA,
        qualified_training_record_ids_sha256="2" * 64,
        corpus_sha256="3" * 64,
        corpus_training_record_ids_sha256="2" * 64,
        canonical_jsonl_sha256=hashlib.sha256(raw).hexdigest(),
        canonical_jsonl_byte_count=len(raw),
        example_count=2,
        blockers=(),
    )


class _Verifier:
    def __init__(self) -> None:
        self.calls = 0

    def verify(
        self,
        *,
        role: TrainingRole,
        model_root: Path,
        run_plan: TrainingRunPlan,
    ) -> LocalModelAssetObservation:
        self.calls += 1
        assert model_root.is_dir()
        return LocalModelAssetObservation(
            role=role,
            model_id=run_plan.model_id,
            revision=run_plan.revision,
            weights_sha256=run_plan.weights_sha256,
            verifier_id="fixture-local-verifier",
            verifier_version="v1",
            verifier_receipt_sha256=_VERIFIER_SHA,
            network_accessed=False,
            remote_code_allowed=False,
            gated_terms_accepted=False,
        )


class _SuccessBackend:
    def __init__(self) -> None:
        self.calls = 0
        self.manifest: TrainingExecutionManifest | None = None

    def execute(
        self,
        *,
        manifest: TrainingExecutionManifest,
    ) -> TrainingBackendResult:
        self.calls += 1
        self.manifest = manifest
        artifacts = tuple(
            TrainingResultArtifact(
                path=f"{namespace}/artifact-{index}.json",
                sha256=f"{index + 1:x}" * 64,
                byte_count=100 + index,
            )
            for index, namespace in enumerate(manifest.result_namespaces)
        )
        return TrainingBackendResult(
            disposition="SUCCEEDED",
            backend_id="fixture-backend",
            backend_version="v1",
            started_at="2026-08-26T05:00:00Z",
            finished_at="2026-08-26T05:01:00Z",
            artifacts=artifacts,
        )


def _init_git_repo(path: Path) -> tuple[str, str]:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "fixture@example.invalid"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Fixture"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    (path / "README").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "add", "README"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "fixture"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    commit = (
        subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .lower()
    )
    tree = (
        subprocess.run(
            ["git", "rev-parse", "HEAD^{tree}"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        )
        .stdout.strip()
        .lower()
    )
    return commit, tree


def test_hash_dependency_lock_matches_sha256(tmp_path: Path) -> None:
    lock = tmp_path / "uv.lock"
    payload = b"fixture-lock-bytes\n"
    lock.write_bytes(payload)
    assert hash_dependency_lock(lock) == hashlib.sha256(payload).hexdigest()


def test_hash_dependency_lock_refuses_non_regular_file(tmp_path: Path) -> None:
    directory = tmp_path / "not-a-file"
    directory.mkdir()
    with pytest.raises(TrainingOrchestratorError, match="regular file"):
        hash_dependency_lock(directory)


def test_hash_dependency_lock_refuses_symlink(tmp_path: Path) -> None:
    target = tmp_path / "uv.lock"
    target.write_bytes(b"x")
    link = tmp_path / "link.lock"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(TrainingOrchestratorError, match="symlink"):
        hash_dependency_lock(link)


def test_observe_repository_identity(tmp_path: Path) -> None:
    commit, tree = _init_git_repo(tmp_path)
    observed_commit, observed_tree = observe_repository_identity(tmp_path)
    assert observed_commit == commit
    assert observed_tree == tree


def test_observe_gpu_model_requires_probe() -> None:
    with pytest.raises(TrainingOrchestratorError, match="gpu_probe"):
        observe_gpu_model()
    assert observe_gpu_model(gpu_probe=lambda: "fixture-gpu") == "fixture-gpu"


def test_observe_training_execution_environment(tmp_path: Path) -> None:
    commit, tree = _init_git_repo(tmp_path)
    lock = tmp_path / "uv.lock"
    lock.write_bytes(b"lock-v1\n")
    environment = observe_training_execution_environment(
        repository_root=tmp_path,
        runner_class=RunnerClass.LOCAL,
        gpu_probe=lambda: "fixture-gpu",
        python_version="3.12.14",
        os_name="linux",
    )
    assert environment.repository_sha == commit
    assert environment.repository_tree == tree
    assert environment.dependency_lock_sha256 == hash_dependency_lock(lock)
    assert environment.gpu_model == "fixture-gpu"
    assert environment.runner_class is RunnerClass.LOCAL


def test_orchestrator_invokes_executor_when_authority_matches(tmp_path: Path) -> None:
    raw = b'{"id":"ex-1","text":"fixture"}\n{"id":"ex-2","text":"fixture-2"}\n'
    model_root = tmp_path / "model"
    model_root.mkdir()
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_bytes(raw)
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    lock = repository_root / "uv.lock"
    lock.write_bytes(b"orchestrator-lock\n")
    lock_sha = hash_dependency_lock(lock)
    binding = _binding(raw)

    manifest = _readiness_manifest(
        dependency_lock_sha256=lock_sha,
        corpus_binding_sha256=binding.binding_sha256,
    )
    launch = _launch(manifest, dependency_lock_sha256=lock_sha)
    run = launch.compact
    environment = TrainingExecutionEnvironment(
        repository_sha=run.repository_sha,
        repository_tree=run.repository_tree,
        dependency_lock_sha256=run.dependency_lock_sha256,
        runner_class=run.runner_class,
        python_version=run.python_version,
        os_name=run.os_name,
        gpu_model=run.gpu_model,
    )
    backend = _SuccessBackend()
    verifier = _Verifier()

    receipt = run_training_orchestrator(
        manifest=manifest,
        launch_plan=launch,
        corpus_binding=binding,
        role="compact",
        model_root=model_root,
        corpus_path=corpus_path,
        repository_root=repository_root,
        environment=environment,
        verifier=verifier,
        backend_factory=lambda *_args: backend,
    )

    assert receipt.disposition == "SUCCEEDED"
    assert backend.calls == 1
    assert verifier.calls == 1
    assert backend.manifest is not None
    assert backend.manifest.role == "compact"


def test_orchestrator_refuses_environment_mismatch(tmp_path: Path) -> None:
    raw = b'{"id":"ex-1","text":"fixture"}\n'
    model_root = tmp_path / "model"
    model_root.mkdir()
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_bytes(raw)
    repository_root = tmp_path / "repo"
    repository_root.mkdir()

    binding = _binding(raw)
    manifest = _readiness_manifest(corpus_binding_sha256=binding.binding_sha256)
    launch = _launch(manifest)
    run = launch.compact
    environment = TrainingExecutionEnvironment(
        repository_sha=run.repository_sha,
        repository_tree=run.repository_tree,
        dependency_lock_sha256=run.dependency_lock_sha256,
        runner_class=run.runner_class,
        python_version=run.python_version,
        os_name=run.os_name,
        gpu_model="wrong-gpu",
    )

    with pytest.raises(TrainingOrchestratorError, match="gpu_model"):
        run_training_orchestrator(
            manifest=manifest,
            launch_plan=launch,
            corpus_binding=binding,
            role="compact",
            model_root=model_root,
            corpus_path=corpus_path,
            repository_root=repository_root,
            environment=environment,
            verifier=_Verifier(),
            backend_factory=lambda *_args: _SuccessBackend(),
        )


def test_orchestrator_refuses_blocked_readiness(tmp_path: Path) -> None:
    raw = b'{"id":"ex-1","text":"fixture"}\n'
    model_root = tmp_path / "model"
    model_root.mkdir()
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_bytes(raw)
    repository_root = tmp_path / "repo"
    repository_root.mkdir()

    binding = _binding(raw)
    good = _readiness_manifest(corpus_binding_sha256=binding.binding_sha256)
    manifest = replace(good, pilot_closeout_disposition="FAIL")
    readiness = assess_training_readiness(manifest)
    assert readiness.disposition == "BLOCKED"

    # Launch construction itself refuses BLOCKED readiness; supply a forged path by
    # attempting orchestration after assessing readiness separately.
    with pytest.raises(TrainingOrchestratorError, match="READY_TO_LAUNCH"):
        run_training_orchestrator(
            manifest=manifest,
            readiness=readiness,
            launch_plan=_launch(good),
            corpus_binding=binding,
            role="compact",
            model_root=model_root,
            corpus_path=corpus_path,
            repository_root=repository_root,
            environment=TrainingExecutionEnvironment(
                repository_sha=_REPOSITORY_SHA,
                repository_tree=_REPOSITORY_TREE,
                dependency_lock_sha256=_LOCK_SHA,
                runner_class=RunnerClass.LOCAL,
                python_version="3.12.14",
                os_name="linux",
                gpu_model="fixture-gpu",
            ),
            verifier=_Verifier(),
            backend_factory=lambda *_args: _SuccessBackend(),
        )


def test_orchestrator_refuses_launch_plan_drift(tmp_path: Path) -> None:
    raw = b'{"id":"ex-1","text":"fixture"}\n'
    model_root = tmp_path / "model"
    model_root.mkdir()
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_bytes(raw)
    repository_root = tmp_path / "repo"
    repository_root.mkdir()

    binding = _binding(raw)
    manifest = _readiness_manifest(corpus_binding_sha256=binding.binding_sha256)
    launch = _launch(manifest)
    drifted = replace(launch, readiness_manifest_sha256="0" * 64)

    with pytest.raises(TrainingOrchestratorError, match="launch plan"):
        run_training_orchestrator(
            manifest=manifest,
            launch_plan=drifted,
            corpus_binding=binding,
            role="compact",
            model_root=model_root,
            corpus_path=corpus_path,
            repository_root=repository_root,
            environment=TrainingExecutionEnvironment(
                repository_sha=_REPOSITORY_SHA,
                repository_tree=_REPOSITORY_TREE,
                dependency_lock_sha256=_LOCK_SHA,
                runner_class=RunnerClass.LOCAL,
                python_version="3.12.14",
                os_name="linux",
                gpu_model="fixture-gpu",
            ),
            verifier=_Verifier(),
            backend_factory=lambda *_args: _SuccessBackend(),
        )


def test_module_does_not_import_training_stack_at_import_time() -> None:
    source = Path(orchestrator_module.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "import torch",
        "import transformers",
        "import trl",
        "import peft",
        "import accelerate",
        "import bitsandbytes",
        "import datasets",
    ):
        assert forbidden not in source
