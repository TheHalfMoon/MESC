"""Regression tests for MRL-0103 fail-closed plan boundaries."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

import medscale.mesc._mrl_research_experiment_plan_v1 as plan_module


@dataclass(frozen=True, slots=True)
class _DatasetShape:
    name: str
    version: str
    content_sha256: str


@dataclass(frozen=True, slots=True)
class _ModelShape:
    model_id: str
    revision: str
    quantization: str
    backend: str


def _binding() -> plan_module.ExpectedExperimentManifestBinding:
    return plan_module.ExpectedExperimentManifestBinding(
        experiment_id="fixture-experiment-001",
        rq_refs=("RQ1",),
        configuration_sha256="d" * 64,
        datasets=(
            plan_module.ExpectedDatasetBinding(
                name="fixture-dataset",
                version="1.0.0",
                content_sha256="e" * 64,
            ),
        ),
        model=plan_module.ExpectedModelBinding(
            model_id="fixture/model",
            revision="revision-001",
            quantization="none",
            backend="fixture",
        ),
        model_tier=1,
        code_sha="1" * 40,
        seeds=(7,),
        results_paths=("experiments/results/fixture-experiment-001.json",),
    )


def test_expected_manifest_snapshot_rejects_dataset_shape_substitution() -> None:
    binding = _binding()
    object.__setattr__(
        binding,
        "datasets",
        (_DatasetShape("fixture-dataset", "1.0.0", "e" * 64),),
    )

    with pytest.raises(plan_module.ResearchExperimentPlanError, match="ExpectedDatasetBinding"):
        plan_module._snapshot_expected_manifest(binding)


def test_expected_manifest_snapshot_rejects_model_shape_substitution() -> None:
    binding = _binding()
    object.__setattr__(
        binding,
        "model",
        _ModelShape("fixture/model", "revision-001", "none", "fixture"),
    )

    with pytest.raises(plan_module.ResearchExperimentPlanError, match="ExpectedModelBinding"):
        plan_module._snapshot_expected_manifest(binding)


def test_plan_mutation_surface_rejects_nested_forbidden_path() -> None:
    with pytest.raises(plan_module.ResearchExperimentPlanError, match="forbidden"):
        plan_module._require_plan_mutation_surface(
            "tests/fixtures/mrl/sealed/candidate.json",
            ("tests/fixtures/mrl/",),
            ("tests/fixtures/mrl/sealed/",),
        )


def test_result_destination_rejects_nested_forbidden_path() -> None:
    destination = "experiments/results/sealed/result.json"
    plan_module._require_result_paths((destination,))

    with pytest.raises(plan_module.ResearchExperimentPlanError, match="forbidden"):
        plan_module._require_result_destinations_outside_forbidden_surfaces(
            (destination,),
            ("experiments/results/sealed/",),
        )
