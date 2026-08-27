"""MRL-0104 tests for fail-closed binding to the canonical ExperimentManifest."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from medscale.mesc._mrl_experiment_manifest_binding_v1 import (
    ExperimentManifestBinding,
    ExperimentManifestBindingError,
    bind_experiment_manifest,
)
from medscale.mesc._mrl_research_experiment_plan_v1 import (
    ExpectedDatasetBinding,
    ExpectedExperimentManifestBinding,
    ExpectedModelBinding,
    PlanFailureCondition,
    PlanStopCondition,
    PlanTierAllowance,
    ResearchExperimentPlan,
)
from medscale.mesc._mrl_research_hypothesis_v1 import ResearchHypothesis
from medscale.mesc._mrl_research_objective_v1 import (
    AdaptiveEvaluationControls,
    AdaptiveInvalidationRule,
    AdaptiveQueryBudget,
    AdaptiveStoppingRule,
    BudgetExhaustionDisposition,
    EvaluationTier,
    EvaluationTierPolicy,
    EvaluatorIdentity,
    EvidenceFloor,
    FloorComparator,
    MetricContract,
    MetricDirection,
    RepeatedEvaluationPolicy,
    ResearchObjectiveContract,
    ResourceBudget,
    TierResultExposure,
)
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.manifests import DatasetSnapshot, ExperimentManifest, RunnerClass, RunnerEnv
from medscale.reproducibility import canonical_json, content_hash

_CONFIGURATION = canonical_json({"fixture": True, "shots": 0})
_DATASET = DatasetSnapshot("fixture-dataset", "1.0.0", "e" * 64)
_MODEL = ModelRef(
    model_id="fixture/model",
    revision="revision-001",
    quantization="none",
    backend="fixture",
)
_RUNNER = RunnerEnv(runner=RunnerClass.LOCAL, python="3.11", os_name="linux")
_RESULTS = ("experiments/results/fixture-experiment-001.json",)


def _objective() -> ResearchObjectiveContract:
    return ResearchObjectiveContract(
        objective_id="fixture-research-objective",
        research_program_refs=("RQ1",),
        target_capabilities=("evidence-fidelity",),
        hard_guardrails=(
            EvidenceFloor(
                floor_id="global-safety",
                metric_id="safety",
                comparator=FloorComparator.GTE,
                threshold_decimal="0.95",
            ),
        ),
        search_metrics=(
            MetricContract(
                metric_id="search-score",
                evaluator_id="eval.search",
                tier=EvaluationTier.SEARCH,
                direction=MetricDirection.MAXIMIZE,
            ),
        ),
        evaluation_metrics=(
            MetricContract(
                metric_id="safety",
                evaluator_id="eval.sealed",
                tier=EvaluationTier.SEALED,
                direction=MetricDirection.MAXIMIZE,
            ),
        ),
        subgroup_floors=(
            EvidenceFloor(
                floor_id="subgroup-safety",
                metric_id="safety",
                comparator=FloorComparator.GTE,
                threshold_decimal="0.9",
                subgroup="critical-cohort",
            ),
        ),
        resource_budget=ResourceBudget(
            wall_clock_seconds=600,
            compute_seconds=300,
            input_tokens=10_000,
            generated_tokens=2_000,
            storage_bytes=1_000_000,
            monetary_cost_microunits=500_000,
            max_experiments=12,
            retries=3,
            known_failure_retries=1,
            evaluator_invocations=20,
        ),
        allowed_mutation_surfaces=("experiments/fixture.py",),
        forbidden_mutation_surfaces=("governance", "sealed-evaluation"),
        evaluation_tier_policy=EvaluationTierPolicy(
            allowed_tiers=(EvaluationTier.SEARCH, EvaluationTier.SEALED)
        ),
        adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=5, tier_2_queries=0),
        adaptive_evaluation_controls=AdaptiveEvaluationControls(
            repeated_candidate_evaluation=RepeatedEvaluationPolicy.PERMITTED_WITHIN_FROZEN_BUDGET,
            stopping_rules=(
                AdaptiveStoppingRule.ADAPTIVE_QUERY_BUDGET_EXHAUSTED,
                AdaptiveStoppingRule.EXTERNAL_GOVERNANCE_STOP,
                AdaptiveStoppingRule.OBJECTIVE_INVALIDATED,
            ),
            invalidation_rules=(
                AdaptiveInvalidationRule.EVALUATOR_IDENTITY_CHANGED,
                AdaptiveInvalidationRule.OBJECTIVE_SEMANTICS_CHANGED,
                AdaptiveInvalidationRule.PROTECTED_SURFACE_MUTATION_ATTEMPT,
                AdaptiveInvalidationRule.SEALED_BOUNDARY_BREACH,
            ),
        ),
        tier_result_exposure_policy=(
            TierResultExposure(
                tier=EvaluationTier.SEARCH,
                max_exposures=5,
                allowed_result_fields=("aggregate_score",),
            ),
            TierResultExposure(
                tier=EvaluationTier.SEALED,
                max_exposures=0,
                allowed_result_fields=(),
            ),
        ),
        budget_exhaustion_disposition=BudgetExhaustionDisposition.BLOCKED,
        evaluator_identities=(
            EvaluatorIdentity(
                evaluator_id="eval.sealed",
                artifact_sha256="b" * 64,
                tiers=(EvaluationTier.SEALED,),
            ),
            EvaluatorIdentity(
                evaluator_id="eval.search",
                artifact_sha256="a" * 64,
                tiers=(EvaluationTier.SEARCH,),
            ),
        ),
    )


def _manifest(**overrides: object) -> ExperimentManifest:
    values: dict[str, object] = {
        "experiment_id": "fixture-experiment-001",
        "rq_refs": ("RQ1",),
        "configuration": _CONFIGURATION,
        "datasets": (_DATASET,),
        "model": _MODEL,
        "model_tier": 1,
        "code_sha": "1" * 40,
        "seeds": (7, 11),
        "runner": _RUNNER,
        "started_at": "2026-08-27T00:00:00+00:00",
        "results_paths": _RESULTS,
        "reproduction": "uv run fixture-experiment",
    }
    values.update(overrides)
    return ExperimentManifest(**values)  # type: ignore[arg-type]


def _plan() -> ResearchExperimentPlan:
    objective = _objective()
    hypothesis = ResearchHypothesis(
        hypothesis_id="fixture-hypothesis",
        objective_sha256=objective.content_sha256,
        mechanism="A bounded fixture mutation may improve the search metric.",
        predicted_effects=("Search score increases without violating safety floors.",),
        predicted_failure_modes=("The mutation may have no measurable effect.",),
        falsification_criteria=("Search score does not improve under the frozen evaluator.",),
        evidence_refs=("fixture:evidence-001",),
        parent_hypothesis_ids=(),
        created_from_campaign_state_sha256="c" * 64,
    )
    expected_manifest = ExpectedExperimentManifestBinding(
        experiment_id="fixture-experiment-001",
        rq_refs=("RQ1",),
        configuration_sha256=content_hash(json.loads(_CONFIGURATION)),
        datasets=(
            ExpectedDatasetBinding(
                name=_DATASET.name,
                version=_DATASET.version,
                content_sha256=_DATASET.content_sha256,
            ),
        ),
        model=ExpectedModelBinding(
            model_id=_MODEL.model_id,
            revision=_MODEL.revision or "",
            quantization=_MODEL.quantization,
            backend=_MODEL.backend,
        ),
        model_tier=1,
        code_sha="1" * 40,
        seeds=(7, 11),
        results_paths=_RESULTS,
    )
    return ResearchExperimentPlan(
        experiment_plan_id="fixture-plan-001",
        objective=objective,
        hypothesis=hypothesis,
        mutation_surfaces=("experiments/fixture.py",),
        expected_manifest=expected_manifest,
        resource_ceiling=ResourceBudget(
            wall_clock_seconds=300,
            compute_seconds=120,
            input_tokens=2_000,
            generated_tokens=500,
            storage_bytes=100_000,
            monetary_cost_microunits=100_000,
            max_experiments=1,
            retries=1,
            known_failure_retries=0,
            evaluator_invocations=4,
        ),
        evaluator_identities=objective.evaluator_identities,
        evaluation_tiers=(EvaluationTier.SEARCH, EvaluationTier.SEALED),
        tier_allowances=(
            PlanTierAllowance(
                tier=EvaluationTier.SEARCH,
                max_queries=3,
                max_result_exposures=3,
                allowed_result_fields=("aggregate_score",),
            ),
            PlanTierAllowance(
                tier=EvaluationTier.SEALED,
                max_queries=0,
                max_result_exposures=0,
                allowed_result_fields=(),
            ),
        ),
        stop_conditions=(
            PlanStopCondition.ADAPTIVE_QUERY_ALLOWANCE_EXHAUSTED,
            PlanStopCondition.EXTERNAL_GOVERNANCE_STOP,
            PlanStopCondition.FAILURE_CONDITION_TRIGGERED,
            PlanStopCondition.OBJECTIVE_INVALIDATED,
        ),
        failure_conditions=(
            PlanFailureCondition.EVALUATOR_IDENTITY_MISMATCH,
            PlanFailureCondition.MANIFEST_BINDING_MISMATCH,
            PlanFailureCondition.MUTATION_SCOPE_VIOLATION,
            PlanFailureCondition.OBJECTIVE_SEMANTICS_CHANGED,
            PlanFailureCondition.SEALED_BOUNDARY_BREACH,
        ),
    )


def test_binding_uses_existing_runtime_manifest_identity() -> None:
    plan = _plan()
    manifest = _manifest()

    binding = bind_experiment_manifest(plan, manifest)
    payload = binding.semantic_dict()

    assert payload == {
        "format": "MRL-EXPERIMENT-MANIFEST-BINDING-V1",
        "experiment_plan_sha256": plan.content_sha256,
        "experiment_manifest_sha256": manifest.manifest_id,
    }
    assert "content_sha256" not in payload
    assert binding.to_dict()["content_sha256"] == binding.content_sha256
    assert binding.semantic_bytes == bind_experiment_manifest(plan, manifest).semantic_bytes


@pytest.mark.parametrize(
    "manifest",
    [
        _manifest(experiment_id="other-experiment"),
        _manifest(rq_refs=("RQ2",)),
        _manifest(configuration=canonical_json({"fixture": False, "shots": 0})),
        _manifest(datasets=(DatasetSnapshot("fixture-dataset", "2.0.0", "e" * 64),)),
        _manifest(model=replace(_MODEL, backend="other-backend")),
        _manifest(model_tier=2),
        _manifest(code_sha="2" * 40),
        _manifest(seeds=(7, 13)),
        _manifest(results_paths=("experiments/results/other.json",)),
    ],
)
def test_every_plan_bound_manifest_field_must_match(manifest: ExperimentManifest) -> None:
    with pytest.raises(ExperimentManifestBindingError, match="does not match the frozen plan"):
        bind_experiment_manifest(_plan(), manifest)


def test_runtime_only_fields_change_manifest_identity_without_breaking_plan_match() -> None:
    plan = _plan()
    first = bind_experiment_manifest(plan, _manifest())
    second = bind_experiment_manifest(
        plan,
        _manifest(
            runner=RunnerEnv(
                runner=RunnerClass.LOCAL,
                python="3.12",
                os_name="linux",
                gpu="fixture-gpu",
            ),
            started_at="2026-08-27T00:01:00+00:00",
            reproduction="uv run fixture-experiment --repeat",
        ),
    )

    assert first.manifest.manifest_id != second.manifest.manifest_id
    assert first.content_sha256 != second.content_sha256


@pytest.mark.parametrize("peak_vram_gb", [float("nan"), float("inf")])
def test_non_finite_runtime_vram_is_rejected_before_manifest_identity(
    peak_vram_gb: float,
) -> None:
    manifest = _manifest(
        runner=RunnerEnv(
            runner=RunnerClass.LOCAL,
            python="3.11",
            os_name="linux",
            peak_vram_gb=peak_vram_gb,
        )
    )

    with pytest.raises(ExperimentManifestBindingError, match="finite numeric"):
        bind_experiment_manifest(_plan(), manifest)


def test_binding_snapshots_inputs_and_isolated_from_later_external_tampering() -> None:
    plan = _plan()
    manifest = _manifest(model=replace(_MODEL))
    binding = bind_experiment_manifest(plan, manifest)
    before = binding.to_dict()

    object.__setattr__(manifest.model, "backend", "tampered")
    object.__setattr__(plan.expected_manifest, "code_sha", "2" * 40)

    assert binding.to_dict() == before


def test_replacing_bound_manifest_after_construction_fails_closed() -> None:
    binding = bind_experiment_manifest(_plan(), _manifest())
    replacement = _manifest(
        runner=RunnerEnv(
            runner=RunnerClass.LOCAL,
            python="3.12",
            os_name="linux",
            gpu="replacement-gpu",
        ),
        started_at="2026-08-27T00:02:00+00:00",
        reproduction="uv run fixture-experiment --replacement",
    )
    object.__setattr__(binding, "manifest", replacement)

    with pytest.raises(ExperimentManifestBindingError, match="manifest identity changed"):
        binding.semantic_dict()
    with pytest.raises(ExperimentManifestBindingError, match="manifest identity changed"):
        _ = binding.semantic_bytes
    with pytest.raises(ExperimentManifestBindingError, match="manifest identity changed"):
        _ = binding.content_sha256
    with pytest.raises(ExperimentManifestBindingError, match="manifest identity changed"):
        binding.to_dict()


def test_replacing_bound_plan_and_manifest_pair_after_construction_fails_closed() -> None:
    binding = bind_experiment_manifest(_plan(), _manifest())
    replacement_plan = replace(_plan(), experiment_plan_id="fixture-plan-002")
    replacement_manifest = _manifest(
        runner=RunnerEnv(
            runner=RunnerClass.LOCAL,
            python="3.12",
            os_name="linux",
        ),
        started_at="2026-08-27T00:03:00+00:00",
        reproduction="uv run fixture-experiment --new-pair",
    )
    object.__setattr__(binding, "plan", replacement_plan)
    object.__setattr__(binding, "manifest", replacement_manifest)

    with pytest.raises(ExperimentManifestBindingError, match="plan identity changed"):
        binding.semantic_dict()


def test_binding_public_views_fail_closed_on_reachable_internal_tampering() -> None:
    binding = bind_experiment_manifest(_plan(), _manifest())
    object.__setattr__(binding.manifest.model, "backend", "tampered")

    with pytest.raises(ExperimentManifestBindingError, match="does not match the frozen plan"):
        binding.semantic_dict()


def test_malformed_reachable_plan_is_normalized_to_binding_domain_error() -> None:
    binding = bind_experiment_manifest(_plan(), _manifest())
    object.__setattr__(binding.plan, "evaluator_identities", None)

    with pytest.raises(ExperimentManifestBindingError, match="plan failed canonical revalidation"):
        binding.semantic_dict()
    with pytest.raises(ExperimentManifestBindingError, match="plan failed canonical revalidation"):
        _ = binding.semantic_bytes
    with pytest.raises(ExperimentManifestBindingError, match="plan failed canonical revalidation"):
        _ = binding.content_sha256
    with pytest.raises(ExperimentManifestBindingError, match="plan failed canonical revalidation"):
        binding.to_dict()


def test_binding_subclass_private_overrides_cannot_forge_public_views() -> None:
    class BindingSubclass(ExperimentManifestBinding):
        def __post_init__(self) -> None:
            pass

        def _validated_snapshot(self) -> ExperimentManifestBinding:
            raise AssertionError("overridden snapshot must never be dispatched")

        def _semantic_dict_validated(self) -> dict[str, str]:
            return {
                "format": "ATTACKER",
                "experiment_plan_sha256": "a" * 64,
                "experiment_manifest_sha256": "b" * 64,
            }

    substituted = BindingSubclass(plan=_plan(), manifest=_manifest())

    with pytest.raises(ExperimentManifestBindingError, match="exact ExperimentManifestBinding"):
        substituted.semantic_dict()
    with pytest.raises(ExperimentManifestBindingError, match="exact ExperimentManifestBinding"):
        _ = substituted.semantic_bytes
    with pytest.raises(ExperimentManifestBindingError, match="exact ExperimentManifestBinding"):
        _ = substituted.content_sha256
    with pytest.raises(ExperimentManifestBindingError, match="exact ExperimentManifestBinding"):
        substituted.to_dict()


def test_manifest_subclass_type_substitution_is_rejected() -> None:
    class ManifestSubclass(ExperimentManifest):
        pass

    manifest = _manifest()
    substituted = ManifestSubclass(**manifest.__dict__)

    with pytest.raises(ExperimentManifestBindingError, match="exact ExperimentManifest"):
        ExperimentManifestBinding(plan=_plan(), manifest=substituted)
