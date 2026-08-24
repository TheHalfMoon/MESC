"""Qualification tests for deterministic MESC training launch planning."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._training_launch_plan_v1 import (
    TrainingLaunchPlanError,
    TrainingRole,
    TrainingRunPlan,
    build_training_launch_plan,
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

_DATASET_SHA = "d" * 64
_REPOSITORY_SHA = "a" * 40
_REPOSITORY_TREE = "b" * 40
_LOCK_SHA = "c" * 64


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
        weights_sha256="5" * 64,
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


def _manifest(
    *,
    runtime_receipt: str | None = "7" * 64,
    authorization_receipt: str | None = "8" * 64,
) -> TrainingReadinessManifest:
    compact = _candidate(role="compact")
    reasoner = _candidate(role="reasoner")
    return TrainingReadinessManifest(
        compact_candidate=compact,
        reasoner_candidate=reasoner,
        compact_recipe=_recipe(compact),
        reasoner_recipe=_recipe(reasoner),
        pilot_closeout_sha256="1" * 64,
        tournament_report_sha256="2" * 64,
        training_dataset_sha256=_DATASET_SHA,
        provenance_ledger_sha256="3" * 64,
        decontamination_report_sha256="6" * 64,
        evaluation_contract_sha256="9" * 64,
        license_review_sha256="e" * 64,
        pilot_closeout_disposition="PASS",
        tournament_disposition="PASS",
        decontamination_disposition="PASS",
        license_disposition="PASS",
        r2_training_data_only=True,
        heldout_eval_excluded_from_training=True,
        phi_present=False,
        runtime_qualification_sha256=runtime_receipt,
        training_authorization_receipt_sha256=authorization_receipt,
    )


def _run(manifest: TrainingReadinessManifest, *, role: TrainingRole) -> TrainingRunPlan:
    if role == "compact":
        candidate = manifest.compact_candidate
        recipe = manifest.compact_recipe
        experiment_id = "mesc-t6-compact-sft"
        result_paths = (
            "experiments/mesc-t6-compact-sft/outputs",
            "experiments/mesc-t6-compact-sft/results",
        )
    else:
        candidate = manifest.reasoner_candidate
        recipe = manifest.reasoner_recipe
        experiment_id = "mesc-t6-reasoner-sft"
        result_paths = (
            "experiments/mesc-t6-reasoner-sft/outputs",
            "experiments/mesc-t6-reasoner-sft/results",
        )
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
        runner_class=RunnerClass.COLAB,
        python_version="3.12.14",
        os_name="linux",
        gpu_model="NVIDIA-H100-80GB-HBM3",
        dependency_lock_sha256=_LOCK_SHA,
        repository_sha=_REPOSITORY_SHA,
        repository_tree=_REPOSITORY_TREE,
        result_paths=result_paths,
        reproduction_command=f"uv run medscale mesc-train --plan {experiment_id}.json",
    )


def _build() -> tuple[
    TrainingReadinessManifest,
    TrainingReadinessReport,
    TrainingRunPlan,
    TrainingRunPlan,
]:
    manifest = _manifest()
    readiness = assess_training_readiness(manifest)
    compact = _run(manifest, role="compact")
    reasoner = _run(manifest, role="reasoner")
    return manifest, readiness, compact, reasoner


def test_launch_plan_is_content_addressed_and_preserves_all_bindings() -> None:
    manifest, readiness, compact, reasoner = _build()

    plan = build_training_launch_plan(
        manifest=manifest,
        readiness=readiness,
        compact=compact,
        reasoner=reasoner,
    )
    rebuilt = build_training_launch_plan(
        manifest=manifest,
        readiness=readiness,
        compact=compact,
        reasoner=reasoner,
    )
    expected_runtime = manifest.runtime_qualification_sha256
    expected_authorization = manifest.training_authorization_receipt_sha256

    assert plan.readiness_manifest_sha256 == manifest.manifest_sha256
    assert plan.runtime_qualification_sha256 == expected_runtime
    assert plan.training_authorization_receipt_sha256 == expected_authorization
    assert plan.compact.run_plan_sha256 == compact.run_plan_sha256
    assert plan.reasoner.run_plan_sha256 == reasoner.run_plan_sha256
    assert len(plan.plan_sha256) == 64
    assert plan.plan_sha256 == rebuilt.plan_sha256


def test_ready_for_authorization_cannot_build_launch_plan() -> None:
    manifest = _manifest(runtime_receipt=None, authorization_receipt=None)
    readiness = assess_training_readiness(manifest)

    with pytest.raises(TrainingLaunchPlanError, match="not READY_TO_LAUNCH"):
        build_training_launch_plan(
            manifest=manifest,
            readiness=readiness,
            compact=_run(manifest, role="compact"),
            reasoner=_run(manifest, role="reasoner"),
        )


def test_forged_or_stale_readiness_report_is_rejected() -> None:
    manifest, readiness, compact, reasoner = _build()
    forged = TrainingReadinessReport(
        disposition="READY_TO_LAUNCH",
        manifest_sha256="f" * 64,
        blockers=(),
        launch_requirements=(),
    )
    assert forged != readiness

    with pytest.raises(TrainingLaunchPlanError, match="does not match recomputed"):
        build_training_launch_plan(
            manifest=manifest,
            readiness=forged,
            compact=compact,
            reasoner=reasoner,
        )


def test_run_must_bind_exact_selected_candidate_recipe_and_dataset() -> None:
    manifest, readiness, compact, reasoner = _build()
    wrong = replace(compact, recipe_id="f" * 64)

    with pytest.raises(TrainingLaunchPlanError, match="compact run recipe_id"):
        build_training_launch_plan(
            manifest=manifest,
            readiness=readiness,
            compact=wrong,
            reasoner=reasoner,
        )


def test_runs_must_bind_same_repository_and_dependency_lock() -> None:
    manifest, readiness, compact, reasoner = _build()

    with pytest.raises(TrainingLaunchPlanError, match="same repository_sha"):
        build_training_launch_plan(
            manifest=manifest,
            readiness=readiness,
            compact=compact,
            reasoner=replace(reasoner, repository_sha="9" * 40),
        )

    with pytest.raises(TrainingLaunchPlanError, match="same dependency lock"):
        build_training_launch_plan(
            manifest=manifest,
            readiness=readiness,
            compact=compact,
            reasoner=replace(reasoner, dependency_lock_sha256="9" * 64),
        )


def test_result_paths_must_be_repository_relative_and_disjoint() -> None:
    manifest, readiness, compact, reasoner = _build()

    with pytest.raises(TrainingLaunchPlanError, match="inside the repository"):
        replace(compact, result_paths=("../escape",))

    with pytest.raises(TrainingLaunchPlanError, match="result_paths must be disjoint"):
        build_training_launch_plan(
            manifest=manifest,
            readiness=readiness,
            compact=compact,
            reasoner=replace(reasoner, result_paths=compact.result_paths),
        )


def test_seeds_are_explicit_unique_and_non_negative() -> None:
    _, _, compact, _ = _build()

    with pytest.raises(TrainingLaunchPlanError, match="non-empty non-negative"):
        replace(compact, seeds=())
    with pytest.raises(TrainingLaunchPlanError, match="duplicates"):
        replace(compact, seeds=(42, 42))
    with pytest.raises(TrainingLaunchPlanError, match="non-empty non-negative"):
        replace(compact, seeds=(42, -1))


def test_reproduction_command_is_single_line() -> None:
    _, _, compact, _ = _build()

    with pytest.raises(TrainingLaunchPlanError, match="single-line"):
        replace(compact, reproduction_command="uv run first\nuv run second")


def test_run_plan_identity_changes_with_environment_or_code_identity() -> None:
    _, _, compact, _ = _build()

    changed_lock = replace(compact, dependency_lock_sha256="9" * 64)
    changed_tree = replace(compact, repository_tree="9" * 40)

    assert changed_lock.run_plan_sha256 != compact.run_plan_sha256
    assert changed_tree.run_plan_sha256 != compact.run_plan_sha256
