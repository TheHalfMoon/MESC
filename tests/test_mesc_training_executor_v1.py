"""Qualification tests for the fail-closed MESC training executor boundary."""

from __future__ import annotations

from dataclasses import replace

import pytest

import medscale.mesc._training_executor_v1 as executor_module
from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._training_authorization_receipt_v1 import (
    build_training_authorization_receipt,
)
from medscale.mesc._training_corpus_binding_v1 import TrainingCorpusBindingReport
from medscale.mesc._training_executor_v1 import (
    TrainingBackend,
    TrainingBackendResult,
    TrainingExecutionEnvironment,
    TrainingExecutionError,
    TrainingExecutionManifest,
    TrainingExecutionReceipt,
    TrainingResultArtifact,
    execute_training,
)
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


def _runtime_receipt() -> TrainingRuntimeQualificationReceipt:
    smoke = TrainingRuntimeSmokeEvidence(
        canonical_json_bytes(
            {
                "dependency_lock_sha256": _LOCK_SHA,
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
        dependency_lock_sha256=_LOCK_SHA,
        repository_sha=_REPOSITORY_SHA,
        repository_tree=_REPOSITORY_TREE,
        probe_id="fixture-probe",
        probe_version="v1",
        smoke_evidence=smoke,
    )


def _binding() -> TrainingCorpusBindingReport:
    return TrainingCorpusBindingReport(
        disposition="PASS",
        qualification_sha256="1" * 64,
        training_dataset_sha256=_DATASET_SHA,
        qualified_training_record_ids_sha256="2" * 64,
        corpus_sha256="3" * 64,
        corpus_training_record_ids_sha256="2" * 64,
        canonical_jsonl_sha256=_CORPUS_RAW_SHA,
        canonical_jsonl_byte_count=128,
        example_count=2,
        blockers=(),
    )


def _readiness_manifest(
    *,
    corpus_binding_sha256: str | None = None,
) -> TrainingReadinessManifest:
    compact = _candidate(role="compact")
    reasoner = _candidate(role="reasoner")
    runtime = _runtime_receipt()
    corpus_sha = corpus_binding_sha256 or _binding().binding_sha256
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
        corpus_binding_sha256=corpus_sha,
        runtime_qualification_sha256=runtime.receipt_sha256,
        runtime_qualification_receipt=runtime,
    )
    authorization = build_training_authorization_receipt(
        authorizer_id="fixture-founder",
        authorization_subject_sha256=pre.authorization_subject_sha256,
        runtime_qualification_sha256=runtime.receipt_sha256,
        corpus_binding_sha256=corpus_sha,
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
        python_version=_PYTHON,
        os_name=_OS,
        gpu_model=_GPU,
        dependency_lock_sha256=_LOCK_SHA,
        repository_sha=_REPOSITORY_SHA,
        repository_tree=_REPOSITORY_TREE,
        result_paths=(
            f"experiments/{experiment_id}/outputs",
            f"experiments/{experiment_id}/results",
        ),
        reproduction_command=(f"uv run medscale mesc-train --plan {experiment_id}.json"),
    )


def _launch(
    manifest: TrainingReadinessManifest,
    readiness: TrainingReadinessReport,
) -> TrainingLaunchPlan:
    return build_training_launch_plan(
        manifest=manifest,
        readiness=readiness,
        compact=_run(manifest, role="compact"),
        reasoner=_run(manifest, role="reasoner"),
    )


def _local_assets(
    launch: TrainingLaunchPlan,
    binding: TrainingCorpusBindingReport,
    *,
    role: TrainingRole,
) -> TrainingLocalAssetAttestationReport:
    run = launch.compact if role == "compact" else launch.reasoner
    return TrainingLocalAssetAttestationReport(
        disposition="PASS",
        role=role,
        launch_plan_sha256=launch.plan_sha256,
        run_plan_sha256=run.run_plan_sha256,
        corpus_binding_sha256=binding.binding_sha256,
        training_dataset_sha256=run.training_dataset_sha256,
        model_id=run.model_id,
        revision=run.revision,
        expected_weights_sha256=run.weights_sha256,
        observed_weights_sha256=run.weights_sha256,
        model_verifier_id="fixture-local-verifier",
        model_verifier_version="v1",
        model_verifier_receipt_sha256=_VERIFIER_SHA,
        model_network_accessed=False,
        model_remote_code_allowed=False,
        model_gated_terms_accepted=False,
        expected_corpus_sha256=binding.canonical_jsonl_sha256,
        observed_corpus_sha256=binding.canonical_jsonl_sha256,
        expected_corpus_byte_count=binding.canonical_jsonl_byte_count,
        observed_corpus_byte_count=binding.canonical_jsonl_byte_count,
        blockers=(),
    )


def _environment(run: TrainingRunPlan) -> TrainingExecutionEnvironment:
    return TrainingExecutionEnvironment(
        repository_sha=run.repository_sha,
        repository_tree=run.repository_tree,
        dependency_lock_sha256=run.dependency_lock_sha256,
        runner_class=run.runner_class,
        python_version=run.python_version,
        os_name=run.os_name,
        gpu_model=run.gpu_model,
    )


def _bundle(
    role: TrainingRole = "compact",
) -> tuple[
    TrainingReadinessManifest,
    TrainingReadinessReport,
    TrainingLaunchPlan,
    TrainingCorpusBindingReport,
    TrainingLocalAssetAttestationReport,
    TrainingExecutionEnvironment,
]:
    manifest = _readiness_manifest()
    readiness = assess_training_readiness(manifest)
    launch = _launch(manifest, readiness)
    binding = _binding()
    run = launch.compact if role == "compact" else launch.reasoner
    return (
        manifest,
        readiness,
        launch,
        binding,
        _local_assets(launch, binding, role=role),
        _environment(run),
    )


class _SuccessBackend:
    def __init__(self, *, reverse: bool = False) -> None:
        self.calls = 0
        self.manifest: TrainingExecutionManifest | None = None
        self.reverse = reverse

    def execute(
        self,
        *,
        manifest: TrainingExecutionManifest,
    ) -> TrainingBackendResult:
        self.calls += 1
        self.manifest = manifest
        artifacts = [
            TrainingResultArtifact(
                path=f"{namespace}/artifact-{index}.json",
                sha256=f"{index + 1:x}" * 64,
                byte_count=100 + index,
            )
            for index, namespace in enumerate(manifest.result_namespaces)
        ]
        if self.reverse:
            artifacts.reverse()
        return TrainingBackendResult(
            disposition="SUCCEEDED",
            backend_id="fixture-backend",
            backend_version="v1",
            started_at="2026-08-25T05:00:00Z",
            finished_at="2026-08-25T05:01:00Z",
            artifacts=tuple(artifacts),
        )


def _execute(
    backend: TrainingBackend,
    *,
    role: TrainingRole = "compact",
) -> TrainingExecutionReceipt:
    manifest, readiness, launch, binding, assets, environment = _bundle(role)
    return execute_training(
        manifest=manifest,
        readiness=readiness,
        launch_plan=launch,
        corpus_binding=binding,
        local_assets=assets,
        environment=environment,
        role=role,
        backend=backend,
    )


def test_success_receipt_binds_all_authority_and_results() -> None:
    manifest, readiness, launch, binding, assets, environment = _bundle()
    backend = _SuccessBackend(reverse=True)

    receipt = execute_training(
        manifest=manifest,
        readiness=readiness,
        launch_plan=launch,
        corpus_binding=binding,
        local_assets=assets,
        environment=environment,
        role="compact",
        backend=backend,
    )

    assert receipt.disposition == "SUCCEEDED"
    assert backend.calls == 1
    assert backend.manifest is not None
    assert receipt.launch_plan_sha256 == launch.plan_sha256
    assert receipt.run_plan_sha256 == launch.compact.run_plan_sha256
    assert receipt.readiness_manifest_sha256 == manifest.manifest_sha256
    assert receipt.corpus_binding_sha256 == binding.binding_sha256
    assert receipt.local_asset_attestation_sha256 == assets.attestation_sha256
    assert receipt.environment_sha256 == environment.environment_sha256
    assert receipt.runtime_qualification_sha256 == manifest.runtime_qualification_sha256
    assert (
        receipt.training_authorization_receipt_sha256
        == manifest.training_authorization_receipt_sha256
    )
    assert receipt.result_manifest_sha256 is not None
    assert tuple(item.path for item in receipt.result_artifacts) == tuple(
        sorted(item.path for item in receipt.result_artifacts)
    )
    assert len(receipt.receipt_sha256) == 64


def test_forged_readiness_fails_before_backend() -> None:
    manifest, readiness, launch, binding, assets, environment = _bundle()
    forged = replace(readiness, manifest_sha256="f" * 64)
    backend = _SuccessBackend()

    with pytest.raises(TrainingExecutionError, match="recomputed readiness"):
        execute_training(
            manifest=manifest,
            readiness=forged,
            launch_plan=launch,
            corpus_binding=binding,
            local_assets=assets,
            environment=environment,
            role="compact",
            backend=backend,
        )
    assert backend.calls == 0


def test_forged_launch_plan_fails_before_backend() -> None:
    manifest, readiness, launch, binding, assets, environment = _bundle()
    forged = replace(launch, runtime_qualification_sha256="f" * 64)
    backend = _SuccessBackend()

    with pytest.raises(TrainingExecutionError, match="recomputed launch plan"):
        execute_training(
            manifest=manifest,
            readiness=readiness,
            launch_plan=forged,
            corpus_binding=binding,
            local_assets=assets,
            environment=environment,
            role="compact",
            backend=backend,
        )
    assert backend.calls == 0


def test_corpus_binding_must_match_selected_dataset() -> None:
    manifest, readiness, launch, binding, assets, environment = _bundle()
    mismatched = replace(binding, training_dataset_sha256="f" * 64)
    backend = _SuccessBackend()

    with pytest.raises(
        TrainingExecutionError,
        match="corpus binding identity does not match launch plan",
    ):
        execute_training(
            manifest=manifest,
            readiness=readiness,
            launch_plan=launch,
            corpus_binding=mismatched,
            local_assets=assets,
            environment=environment,
            role="compact",
            backend=backend,
        )
    assert backend.calls == 0


def test_local_attestation_must_bind_exact_role() -> None:
    manifest, readiness, launch, binding, assets, environment = _bundle()
    mismatched = replace(assets, role="reasoner")
    backend = _SuccessBackend()

    with pytest.raises(TrainingExecutionError, match="attestation role"):
        execute_training(
            manifest=manifest,
            readiness=readiness,
            launch_plan=launch,
            corpus_binding=binding,
            local_assets=mismatched,
            environment=environment,
            role="compact",
            backend=backend,
        )
    assert backend.calls == 0


def test_environment_must_match_selected_run() -> None:
    manifest, readiness, launch, binding, assets, environment = _bundle()
    stale = replace(environment, repository_tree="9" * 40)
    backend = _SuccessBackend()

    with pytest.raises(TrainingExecutionError, match="repository_tree"):
        execute_training(
            manifest=manifest,
            readiness=readiness,
            launch_plan=launch,
            corpus_binding=binding,
            local_assets=assets,
            environment=stale,
            role="compact",
            backend=backend,
        )
    assert backend.calls == 0


def test_backend_is_mandatory() -> None:
    manifest, readiness, launch, binding, assets, environment = _bundle()
    with pytest.raises(TrainingExecutionError, match="explicit training backend"):
        execute_training(
            manifest=manifest,
            readiness=readiness,
            launch_plan=launch,
            corpus_binding=binding,
            local_assets=assets,
            environment=environment,
            role="compact",
            backend=None,
        )


def test_backend_receives_only_core_owned_manifest() -> None:
    backend = _SuccessBackend()
    _execute(backend)
    assert backend.manifest is not None
    assert type(backend.manifest) is TrainingExecutionManifest
    assert backend.manifest.model_id == "fixture/compact"
    assert backend.manifest.canonical_corpus_sha256 == _CORPUS_RAW_SHA
    assert backend.manifest.model_verifier_receipt_sha256 == _VERIFIER_SHA


def test_backend_mutation_of_core_manifest_is_detected() -> None:
    class MutatingBackend(_SuccessBackend):
        def execute(
            self,
            *,
            manifest: TrainingExecutionManifest,
        ) -> TrainingBackendResult:
            result = super().execute(manifest=manifest)
            object.__setattr__(manifest, "model_id", "tampered/model")
            return result

    with pytest.raises(TrainingExecutionError, match="mutated"):
        _execute(MutatingBackend())


def test_backend_exception_never_fabricates_receipt() -> None:
    class BrokenBackend:
        def execute(
            self,
            *,
            manifest: TrainingExecutionManifest,
        ) -> TrainingBackendResult:
            del manifest
            raise RuntimeError("backend crashed")

    with pytest.raises(TrainingExecutionError, match="without a canonical result"):
        _execute(BrokenBackend())


def test_success_artifacts_must_stay_in_all_namespaces() -> None:
    class EscapingBackend:
        def execute(
            self,
            *,
            manifest: TrainingExecutionManifest,
        ) -> TrainingBackendResult:
            del manifest
            return TrainingBackendResult(
                disposition="SUCCEEDED",
                backend_id="fixture-backend",
                backend_version="v1",
                started_at="2026-08-25T05:00:00Z",
                finished_at="2026-08-25T05:01:00Z",
                artifacts=(
                    TrainingResultArtifact(
                        path="outside/result.json",
                        sha256="1" * 64,
                        byte_count=10,
                    ),
                ),
            )

    with pytest.raises(TrainingExecutionError, match="escapes planned"):
        _execute(EscapingBackend())

    class MissingNamespaceBackend:
        def execute(
            self,
            *,
            manifest: TrainingExecutionManifest,
        ) -> TrainingBackendResult:
            return TrainingBackendResult(
                disposition="SUCCEEDED",
                backend_id="fixture-backend",
                backend_version="v1",
                started_at="2026-08-25T05:00:00Z",
                finished_at="2026-08-25T05:01:00Z",
                artifacts=(
                    TrainingResultArtifact(
                        path=(f"{manifest.result_namespaces[0]}/result.json"),
                        sha256="1" * 64,
                        byte_count=10,
                    ),
                ),
            )

    with pytest.raises(TrainingExecutionError, match="every planned"):
        _execute(MissingNamespaceBackend())


def test_failed_receipt_has_no_partial_canonical_artifacts() -> None:
    class FailedBackend:
        def execute(
            self,
            *,
            manifest: TrainingExecutionManifest,
        ) -> TrainingBackendResult:
            del manifest
            return TrainingBackendResult(
                disposition="FAILED",
                backend_id="fixture-backend",
                backend_version="v1",
                started_at="2026-08-25T05:00:00Z",
                finished_at="2026-08-25T05:00:30Z",
                artifacts=(),
                failure_reason="fixture failure",
            )

    receipt = _execute(FailedBackend())
    assert receipt.disposition == "FAILED"
    assert receipt.result_artifacts == ()
    assert receipt.result_manifest_sha256 is None
    assert receipt.failure_reason == "fixture failure"


def test_backend_result_requires_real_ordered_utc_timestamps() -> None:
    with pytest.raises(TrainingExecutionError, match="canonical UTC"):
        TrainingBackendResult(
            disposition="FAILED",
            backend_id="fixture-backend",
            backend_version="v1",
            started_at="now",
            finished_at="2026-08-25T05:01:00Z",
            artifacts=(),
            failure_reason="failure",
        )

    with pytest.raises(TrainingExecutionError, match="must not precede"):
        TrainingBackendResult(
            disposition="FAILED",
            backend_id="fixture-backend",
            backend_version="v1",
            started_at="2026-08-25T05:02:00Z",
            finished_at="2026-08-25T05:01:00Z",
            artifacts=(),
            failure_reason="failure",
        )


def test_failed_or_aborted_result_cannot_claim_artifacts() -> None:
    artifact = TrainingResultArtifact(
        path="experiments/x/result.json",
        sha256="1" * 64,
        byte_count=10,
    )
    with pytest.raises(TrainingExecutionError, match="cannot claim"):
        TrainingBackendResult(
            disposition="ABORTED",
            backend_id="fixture-backend",
            backend_version="v1",
            started_at="2026-08-25T05:00:00Z",
            finished_at="2026-08-25T05:01:00Z",
            artifacts=(artifact,),
            failure_reason="aborted",
        )


def test_noncanonical_backend_result_subclass_is_rejected() -> None:
    class ForgedResult(TrainingBackendResult):
        pass

    class ForgingBackend:
        def execute(
            self,
            *,
            manifest: TrainingExecutionManifest,
        ) -> TrainingBackendResult:
            artifacts = tuple(
                TrainingResultArtifact(
                    path=f"{namespace}/result.json",
                    sha256=f"{index + 1:x}" * 64,
                    byte_count=10,
                )
                for index, namespace in enumerate(manifest.result_namespaces)
            )
            return ForgedResult(
                disposition="SUCCEEDED",
                backend_id="fixture-backend",
                backend_version="v1",
                started_at="2026-08-25T05:00:00Z",
                finished_at="2026-08-25T05:01:00Z",
                artifacts=artifacts,
            )

    with pytest.raises(TrainingExecutionError, match="non-canonical"):
        _execute(ForgingBackend())


def test_subclassed_environment_is_rejected_before_execution() -> None:
    manifest, readiness, launch, binding, assets, environment = _bundle()

    class ForgedEnvironment(TrainingExecutionEnvironment):
        pass

    forged = ForgedEnvironment(
        repository_sha=environment.repository_sha,
        repository_tree=environment.repository_tree,
        dependency_lock_sha256=environment.dependency_lock_sha256,
        runner_class=environment.runner_class,
        python_version=environment.python_version,
        os_name=environment.os_name,
        gpu_model=environment.gpu_model,
    )
    backend = _SuccessBackend()
    with pytest.raises(TrainingExecutionError, match="exact canonical type"):
        execute_training(
            manifest=manifest,
            readiness=readiness,
            launch_plan=launch,
            corpus_binding=binding,
            local_assets=assets,
            environment=forged,
            role="compact",
            backend=backend,
        )
    assert backend.calls == 0


def test_reasoner_role_executes_end_to_end() -> None:
    backend = _SuccessBackend()
    receipt = _execute(backend, role="reasoner")

    assert receipt.disposition == "SUCCEEDED"
    assert receipt.role == "reasoner"
    assert receipt.model_id == "fixture/reasoner"
    assert backend.manifest is not None
    assert backend.manifest.role == "reasoner"
    assert backend.manifest.model_id == "fixture/reasoner"


def test_aborted_backend_returns_canonical_terminal_receipt() -> None:
    class AbortedBackend:
        def execute(
            self,
            *,
            manifest: TrainingExecutionManifest,
        ) -> TrainingBackendResult:
            del manifest
            return TrainingBackendResult(
                disposition="ABORTED",
                backend_id="fixture-backend",
                backend_version="v1",
                started_at="2026-08-25T05:00:00Z",
                finished_at="2026-08-25T05:00:15Z",
                artifacts=(),
                failure_reason="fixture operator abort",
            )

    receipt = _execute(AbortedBackend())
    assert receipt.disposition == "ABORTED"
    assert receipt.result_artifacts == ()
    assert receipt.result_manifest_sha256 is None
    assert receipt.failure_reason == "fixture operator abort"


def test_caller_owned_launch_mutation_after_validation_is_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, readiness, launch, binding, assets, environment = _bundle()
    backend = _SuccessBackend()
    original_require_environment = executor_module._require_environment

    def mutate_caller_after_validation(
        observed_environment: TrainingExecutionEnvironment,
        *,
        run_plan: TrainingRunPlan,
    ) -> None:
        original_require_environment(
            observed_environment,
            run_plan=run_plan,
        )
        object.__setattr__(launch.compact, "model_id", "tampered/model")

    monkeypatch.setattr(
        executor_module,
        "_require_environment",
        mutate_caller_after_validation,
    )

    receipt = execute_training(
        manifest=manifest,
        readiness=readiness,
        launch_plan=launch,
        corpus_binding=binding,
        local_assets=assets,
        environment=environment,
        role="compact",
        backend=backend,
    )

    assert receipt.model_id == "fixture/compact"
    assert backend.manifest is not None
    assert backend.manifest.model_id == "fixture/compact"


def test_forged_nested_run_plan_is_rejected_before_backend() -> None:
    manifest, readiness, launch, binding, assets, environment = _bundle()
    backend = _SuccessBackend()

    class ForgedRunPlan(TrainingRunPlan):
        pass

    forged = object.__new__(ForgedRunPlan)
    for field_name in TrainingRunPlan.__dataclass_fields__:
        object.__setattr__(forged, field_name, getattr(launch.compact, field_name))
    forged_launch = replace(launch, compact=forged)

    with pytest.raises(TrainingExecutionError, match=r"launch_plan[.]compact"):
        execute_training(
            manifest=manifest,
            readiness=readiness,
            launch_plan=forged_launch,
            corpus_binding=binding,
            local_assets=assets,
            environment=environment,
            role="compact",
            backend=backend,
        )
    assert backend.manifest is None


def test_mutated_exact_run_plan_is_revalidated_before_backend() -> None:
    manifest, readiness, launch, binding, assets, environment = _bundle()
    backend = _SuccessBackend()
    object.__setattr__(launch.compact, "result_paths", ("../escape",))

    with pytest.raises(
        TrainingExecutionError,
        match="canonical execution inputs could not be reconstructed",
    ):
        execute_training(
            manifest=manifest,
            readiness=readiness,
            launch_plan=launch,
            corpus_binding=binding,
            local_assets=assets,
            environment=environment,
            role="compact",
            backend=backend,
        )
    assert backend.manifest is None


def test_result_artifact_path_rejects_nul() -> None:
    with pytest.raises(TrainingExecutionError, match="POSIX repository path"):
        TrainingResultArtifact(
            path="experiments/compact/result\x00.json",
            sha256="1" * 64,
            byte_count=1,
        )
