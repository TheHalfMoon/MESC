"""MRL-0103 tests for the immutable ResearchExperimentPlan."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace

import pytest

from medscale.mesc._mrl_research_experiment_plan_v1 import (
    ExpectedDatasetBinding,
    ExpectedExperimentManifestBinding,
    ExpectedModelBinding,
    PlanFailureCondition,
    PlanStopCondition,
    PlanTierAllowance,
    ResearchExperimentPlan,
    ResearchExperimentPlanError,
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
        allowed_mutation_surfaces=(
            "experiments/fixture.py",
            "tests/fixtures/mrl/candidates",
        ),
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
                allowed_result_fields=("aggregate_score", "cost_microunits"),
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


def _hypothesis(objective: ResearchObjectiveContract) -> ResearchHypothesis:
    return ResearchHypothesis(
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


def _expected_manifest() -> ExpectedExperimentManifestBinding:
    return ExpectedExperimentManifestBinding(
        experiment_id="fixture-experiment-001",
        rq_refs=("RQ1",),
        configuration_sha256="d" * 64,
        datasets=(
            ExpectedDatasetBinding(
                name="fixture-dataset",
                version="1.0.0",
                content_sha256="e" * 64,
            ),
        ),
        model=ExpectedModelBinding(
            model_id="fixture/model",
            revision="revision-001",
            quantization="none",
            backend="fixture",
        ),
        model_tier=1,
        code_sha="1" * 40,
        seeds=(7, 11),
        results_paths=("experiments/results/fixture-experiment-001.json",),
    )


def _resource_ceiling() -> ResourceBudget:
    return ResourceBudget(
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
    )


def _plan() -> ResearchExperimentPlan:
    objective = _objective()
    return ResearchExperimentPlan(
        experiment_plan_id="fixture-plan-001",
        objective=objective,
        hypothesis=_hypothesis(objective),
        mutation_surfaces=(
            "experiments/fixture.py",
            "tests/fixtures/mrl/candidates/candidate.json",
        ),
        expected_manifest=_expected_manifest(),
        resource_ceiling=_resource_ceiling(),
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
            PlanStopCondition.RESOURCE_CEILING_REACHED,
        ),
        failure_conditions=(
            PlanFailureCondition.EVALUATOR_IDENTITY_MISMATCH,
            PlanFailureCondition.MANIFEST_BINDING_MISMATCH,
            PlanFailureCondition.MUTATION_SCOPE_VIOLATION,
            PlanFailureCondition.OBJECTIVE_SEMANTICS_CHANGED,
            PlanFailureCondition.RESOURCE_BUDGET_OVERRUN,
            PlanFailureCondition.SEALED_BOUNDARY_BREACH,
        ),
    )


def test_plan_identity_is_outside_semantic_preimage() -> None:
    plan = _plan()

    assert "content_sha256" not in plan.semantic_dict()
    assert plan.to_dict()["content_sha256"] == plan.content_sha256
    assert len(plan.content_sha256) == 64


def test_equivalent_plans_have_byte_stable_identity() -> None:
    first = _plan()
    second = _plan()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256


def test_semantic_envelope_binds_objective_and_hypothesis_by_identity_only() -> None:
    plan = _plan()
    payload = plan.semantic_dict()

    assert payload["format"] == "MRL-RESEARCH-EXPERIMENT-PLAN-V1"
    assert payload["objective_sha256"] == plan.objective.content_sha256
    assert payload["hypothesis_sha256"] == plan.hypothesis.content_sha256
    assert "objective" not in payload
    assert "hypothesis" not in payload


def test_expected_manifest_binding_is_plan_time_subset_not_runtime_manifest() -> None:
    binding = _plan().semantic_dict()["expected_manifest"]
    assert isinstance(binding, dict)
    assert "configuration_sha256" in binding
    assert "datasets" in binding
    assert "model" in binding
    assert "seeds" in binding
    assert "results_paths" in binding
    for runtime_only in ("runner", "started_at", "reproduction", "manifest_id"):
        assert runtime_only not in binding


def test_plan_and_nested_contracts_are_frozen() -> None:
    plan = _plan()

    with pytest.raises(FrozenInstanceError):
        plan.experiment_plan_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        plan.expected_manifest.code_sha = "2" * 40  # type: ignore[misc]


def test_hypothesis_must_bind_exact_supplied_objective() -> None:
    plan = _plan()
    other_objective = replace(plan.objective, objective_id="other-objective")

    with pytest.raises(ResearchExperimentPlanError, match="hypothesis objective_sha256"):
        replace(plan, objective=other_objective)


def test_plan_mutation_scope_must_be_within_objective_allow_list() -> None:
    with pytest.raises(ResearchExperimentPlanError, match="outside the frozen objective"):
        replace(_plan(), mutation_surfaces=("experiments/unlisted.py",))


def test_objective_directory_allowance_may_be_narrowed_by_plan() -> None:
    plan = replace(
        _plan(),
        mutation_surfaces=("tests/fixtures/mrl/candidates/deeper/candidate.json",),
    )
    assert plan.mutation_surfaces == ("tests/fixtures/mrl/candidates/deeper/candidate.json",)


@pytest.mark.parametrize(
    "surface",
    [
        ".github/workflows/ci.yml",
        "docs/adr/0033-modelkit-public-surface-and-runtime-governance.md",
        "specs/mesc-research-loop-v1/spec.md",
        "data/sealed.jsonl",
    ],
)
def test_plan_cannot_broaden_mutation_authority(surface: str) -> None:
    with pytest.raises(ResearchExperimentPlanError):
        replace(_plan(), mutation_surfaces=(surface,))


def test_noncanonical_mutation_path_fails_closed() -> None:
    with pytest.raises(ResearchExperimentPlanError, match="non-canonical relative path"):
        replace(_plan(), mutation_surfaces=("tests/fixtures/mrl/../sealed.json",))


def test_plan_resource_ceiling_must_fit_objective() -> None:
    plan = _plan()
    with pytest.raises(ResearchExperimentPlanError, match="wall_clock_seconds exceeds"):
        replace(
            plan,
            resource_ceiling=replace(plan.resource_ceiling, wall_clock_seconds=601),
        )


def test_one_plan_cannot_claim_multiple_experiments() -> None:
    plan = _plan()
    with pytest.raises(ResearchExperimentPlanError, match="exactly one experiment"):
        replace(
            plan,
            resource_ceiling=replace(plan.resource_ceiling, max_experiments=2),
        )


def test_not_applicable_objective_resource_cannot_be_minted_by_plan() -> None:
    plan = _plan()
    objective = replace(
        plan.objective,
        resource_budget=replace(plan.objective.resource_budget, compute_seconds=None),
    )
    hypothesis = _hypothesis(objective)
    with pytest.raises(ResearchExperimentPlanError, match="compute_seconds is not applicable"):
        replace(plan, objective=objective, hypothesis=hypothesis)


@pytest.mark.parametrize(
    "resource_name",
    [
        "compute_seconds",
        "input_tokens",
        "generated_tokens",
        "monetary_cost_microunits",
        "evaluator_invocations",
    ],
)
def test_applicable_objective_resource_cannot_be_dropped_from_plan(
    resource_name: str,
) -> None:
    plan = _plan()
    if resource_name == "compute_seconds":
        ceiling = replace(plan.resource_ceiling, compute_seconds=None)
    elif resource_name == "input_tokens":
        ceiling = replace(plan.resource_ceiling, input_tokens=None)
    elif resource_name == "generated_tokens":
        ceiling = replace(plan.resource_ceiling, generated_tokens=None)
    elif resource_name == "monetary_cost_microunits":
        ceiling = replace(plan.resource_ceiling, monetary_cost_microunits=None)
    elif resource_name == "evaluator_invocations":
        ceiling = replace(plan.resource_ceiling, evaluator_invocations=None)
    else:
        raise AssertionError(f"unhandled resource field: {resource_name}")

    with pytest.raises(
        ResearchExperimentPlanError,
        match=rf"resource_ceiling {resource_name} cannot be not applicable",
    ):
        replace(plan, resource_ceiling=ceiling)


def test_expected_manifest_rq_refs_must_fit_objective() -> None:
    plan = _plan()
    with pytest.raises(ResearchExperimentPlanError, match="research-question refs"):
        replace(
            plan,
            expected_manifest=replace(plan.expected_manifest, rq_refs=("RQ2",)),
        )


def test_expected_manifest_requires_full_git_identity() -> None:
    with pytest.raises(ResearchExperimentPlanError, match="40-character git SHA"):
        replace(_expected_manifest(), code_sha="1" * 39)


def test_expected_manifest_requires_exact_model_revision() -> None:
    with pytest.raises(ResearchExperimentPlanError, match="model revision"):
        replace(
            _expected_manifest(),
            model=replace(_expected_manifest().model, revision=""),
        )


def test_expected_manifest_seed_plan_is_sorted_unique_and_nonnegative() -> None:
    with pytest.raises(ResearchExperimentPlanError, match="strictly ascending"):
        replace(_expected_manifest(), seeds=(11, 7))
    with pytest.raises(ResearchExperimentPlanError, match="non-negative"):
        replace(_expected_manifest(), seeds=(-1,))


def test_expected_result_destinations_stay_in_governed_roots() -> None:
    with pytest.raises(ResearchExperimentPlanError, match="outside governed experiment roots"):
        replace(_expected_manifest(), results_paths=("results/unscoped.json",))


def test_evaluator_identity_must_exactly_match_objective() -> None:
    plan = _plan()
    altered = replace(plan.evaluator_identities[0], artifact_sha256="f" * 64)
    with pytest.raises(ResearchExperimentPlanError, match="does not exactly match"):
        replace(plan, evaluator_identities=(altered, plan.evaluator_identities[1]))


def test_plan_tiers_must_fit_objective_policy() -> None:
    plan = _plan()
    with pytest.raises(ResearchExperimentPlanError, match="subset"):
        replace(
            plan,
            evaluation_tiers=(
                EvaluationTier.SEARCH,
                EvaluationTier.REPLICATION,
                EvaluationTier.SEALED,
            ),
        )


def test_every_plan_tier_requires_a_frozen_evaluator() -> None:
    plan = _plan()
    with pytest.raises(ResearchExperimentPlanError, match="has no exact frozen evaluator"):
        replace(
            plan,
            evaluator_identities=(plan.evaluator_identities[1],),
        )


def test_plan_can_narrow_tier_without_rewriting_exact_evaluator_identity() -> None:
    plan = _plan()
    multi_tier_search = replace(
        plan.objective.evaluator_identities[1],
        tiers=(EvaluationTier.SEARCH, EvaluationTier.SEALED),
    )
    objective = replace(
        plan.objective,
        evaluator_identities=(plan.objective.evaluator_identities[0], multi_tier_search),
    )

    narrowed = replace(
        plan,
        objective=objective,
        hypothesis=_hypothesis(objective),
        evaluation_tiers=(EvaluationTier.SEARCH,),
        evaluator_identities=(multi_tier_search,),
        tier_allowances=(plan.tier_allowances[0],),
    )

    assert narrowed.evaluation_tiers == (EvaluationTier.SEARCH,)
    assert narrowed.evaluator_identities == (multi_tier_search,)


def test_query_allowance_cannot_exceed_objective() -> None:
    plan = _plan()
    with pytest.raises(ResearchExperimentPlanError, match="query allowance exceeds"):
        replace(
            plan,
            tier_allowances=(
                replace(plan.tier_allowances[0], max_queries=6),
                plan.tier_allowances[1],
            ),
        )


def test_result_exposure_cannot_exceed_objective() -> None:
    plan = _plan()
    with pytest.raises(ResearchExperimentPlanError, match="result exposure exceeds"):
        replace(
            plan,
            tier_allowances=(
                replace(plan.tier_allowances[0], max_result_exposures=6),
                plan.tier_allowances[1],
            ),
        )


def test_result_fields_must_be_subset_of_objective_exposure() -> None:
    plan = _plan()
    with pytest.raises(ResearchExperimentPlanError, match="outside the frozen objective"):
        replace(
            plan,
            tier_allowances=(
                replace(
                    plan.tier_allowances[0],
                    allowed_result_fields=("aggregate_score", "raw_item_content"),
                ),
                plan.tier_allowances[1],
            ),
        )


def test_sealed_tier_cannot_expose_iterative_results() -> None:
    with pytest.raises(ResearchExperimentPlanError, match="Tier 3/4"):
        PlanTierAllowance(
            tier=EvaluationTier.SEALED,
            max_queries=0,
            max_result_exposures=1,
            allowed_result_fields=(),
        )


def test_tier_allowances_must_cover_exact_plan_tiers() -> None:
    plan = _plan()
    with pytest.raises(ResearchExperimentPlanError, match="exactly every plan evaluation tier"):
        replace(plan, tier_allowances=(plan.tier_allowances[0],))


def test_stop_and_failure_conditions_are_required_and_canonical() -> None:
    plan = _plan()
    with pytest.raises(ResearchExperimentPlanError, match="stop_conditions cannot be empty"):
        replace(plan, stop_conditions=())
    with pytest.raises(ResearchExperimentPlanError, match="failure_conditions cannot be empty"):
        replace(plan, failure_conditions=())
    with pytest.raises(ResearchExperimentPlanError, match="strictly sorted"):
        replace(plan, stop_conditions=tuple(reversed(plan.stop_conditions)))


@pytest.mark.parametrize(
    ("objective_rule", "required_condition"),
    [
        (
            AdaptiveStoppingRule.ADAPTIVE_QUERY_BUDGET_EXHAUSTED,
            PlanStopCondition.ADAPTIVE_QUERY_ALLOWANCE_EXHAUSTED,
        ),
        (
            AdaptiveStoppingRule.EXTERNAL_GOVERNANCE_STOP,
            PlanStopCondition.EXTERNAL_GOVERNANCE_STOP,
        ),
        (
            AdaptiveStoppingRule.OBJECTIVE_INVALIDATED,
            PlanStopCondition.OBJECTIVE_INVALIDATED,
        ),
        (
            AdaptiveStoppingRule.RESOURCE_BUDGET_EXHAUSTED,
            PlanStopCondition.RESOURCE_CEILING_REACHED,
        ),
        (
            AdaptiveStoppingRule.RESULT_EXPOSURE_BUDGET_EXHAUSTED,
            PlanStopCondition.RESULT_EXPOSURE_ALLOWANCE_EXHAUSTED,
        ),
    ],
)
def test_plan_stop_conditions_cover_every_frozen_objective_rule(
    objective_rule: AdaptiveStoppingRule,
    required_condition: PlanStopCondition,
) -> None:
    plan = _plan()
    controls = replace(
        plan.objective.adaptive_evaluation_controls,
        stopping_rules=tuple(sorted(AdaptiveStoppingRule, key=lambda rule: rule.value)),
    )
    objective = replace(plan.objective, adaptive_evaluation_controls=controls)
    complete = replace(
        plan,
        objective=objective,
        hypothesis=_hypothesis(objective),
        stop_conditions=tuple(sorted(PlanStopCondition, key=lambda condition: condition.value)),
    )
    assert objective_rule in controls.stopping_rules
    reduced = tuple(
        condition for condition in complete.stop_conditions if condition is not required_condition
    )

    with pytest.raises(ResearchExperimentPlanError, match="omit frozen objective requirements"):
        replace(complete, stop_conditions=reduced)


@pytest.mark.parametrize(
    ("objective_rule", "required_condition"),
    [
        (
            AdaptiveInvalidationRule.EVALUATOR_IDENTITY_CHANGED,
            PlanFailureCondition.EVALUATOR_IDENTITY_MISMATCH,
        ),
        (
            AdaptiveInvalidationRule.LINEAGE_OR_CONTAMINATION_FAILURE,
            PlanFailureCondition.CONTAMINATION_OR_LINEAGE_FAILURE,
        ),
        (
            AdaptiveInvalidationRule.OBJECTIVE_SEMANTICS_CHANGED,
            PlanFailureCondition.OBJECTIVE_SEMANTICS_CHANGED,
        ),
        (
            AdaptiveInvalidationRule.PROTECTED_SURFACE_MUTATION_ATTEMPT,
            PlanFailureCondition.MUTATION_SCOPE_VIOLATION,
        ),
        (
            AdaptiveInvalidationRule.SEALED_BOUNDARY_BREACH,
            PlanFailureCondition.SEALED_BOUNDARY_BREACH,
        ),
    ],
)
def test_plan_failure_conditions_cover_every_frozen_objective_rule(
    objective_rule: AdaptiveInvalidationRule,
    required_condition: PlanFailureCondition,
) -> None:
    plan = _plan()
    controls = replace(
        plan.objective.adaptive_evaluation_controls,
        invalidation_rules=tuple(sorted(AdaptiveInvalidationRule, key=lambda rule: rule.value)),
    )
    objective = replace(plan.objective, adaptive_evaluation_controls=controls)
    complete = replace(
        plan,
        objective=objective,
        hypothesis=_hypothesis(objective),
        failure_conditions=tuple(
            sorted(PlanFailureCondition, key=lambda condition: condition.value)
        ),
    )
    assert objective_rule in controls.invalidation_rules
    reduced = tuple(
        condition
        for condition in complete.failure_conditions
        if condition is not required_condition
    )

    with pytest.raises(ResearchExperimentPlanError, match="omit frozen objective requirements"):
        replace(complete, failure_conditions=reduced)


def test_objective_invalidation_rules_require_failure_triggered_stop() -> None:
    plan = _plan()
    assert plan.objective.adaptive_evaluation_controls.invalidation_rules
    reduced = tuple(
        condition
        for condition in plan.stop_conditions
        if condition is not PlanStopCondition.FAILURE_CONDITION_TRIGGERED
    )

    with pytest.raises(ResearchExperimentPlanError, match="FAILURE_CONDITION_TRIGGERED"):
        replace(plan, stop_conditions=reduced)


def test_material_semantic_changes_change_plan_identity() -> None:
    plan = _plan()
    changed = replace(
        plan,
        tier_allowances=(
            replace(plan.tier_allowances[0], max_queries=2),
            plan.tier_allowances[1],
        ),
    )
    assert changed.content_sha256 != plan.content_sha256


def test_post_construction_nested_manifest_mutation_fails_public_views() -> None:
    plan = _plan()
    object.__setattr__(plan.expected_manifest.datasets[0], "content_sha256", "INVALID")

    with pytest.raises(ResearchExperimentPlanError, match="64 lowercase hex"):
        plan.semantic_dict()


def test_post_construction_objective_mutation_fails_public_views() -> None:
    plan = _plan()
    object.__setattr__(plan.objective, "allowed_mutation_surfaces", ("governance",))

    with pytest.raises(
        ResearchExperimentPlanError,
        match="objective failed canonical revalidation",
    ):
        _ = plan.content_sha256


def test_runtime_type_confusion_fails_closed() -> None:
    plan = _plan()
    with pytest.raises(ResearchExperimentPlanError, match="exact EvaluationTier"):
        PlanTierAllowance(
            tier=1,  # type: ignore[arg-type]
            max_queries=0,
            max_result_exposures=0,
            allowed_result_fields=(),
        )
    with pytest.raises(ResearchExperimentPlanError, match="exact tuple"):
        replace(plan, mutation_surfaces=["experiments/fixture.py"])  # type: ignore[arg-type]


def test_unknown_constructor_field_is_rejected_by_closed_contract() -> None:
    plan = _plan()
    kwargs = {field.name: getattr(plan, field.name) for field in fields(ResearchExperimentPlan)}
    kwargs["unknown_field"] = "rejected"

    with pytest.raises(TypeError, match="unexpected keyword"):
        ResearchExperimentPlan(**kwargs)


def test_plan_subclass_cannot_use_canonical_semantic_views() -> None:
    class PlanSubclass(ResearchExperimentPlan):
        pass

    plan = _plan()
    subclass = PlanSubclass(
        experiment_plan_id=plan.experiment_plan_id,
        objective=plan.objective,
        hypothesis=plan.hypothesis,
        mutation_surfaces=plan.mutation_surfaces,
        expected_manifest=plan.expected_manifest,
        resource_ceiling=plan.resource_ceiling,
        evaluator_identities=plan.evaluator_identities,
        evaluation_tiers=plan.evaluation_tiers,
        tier_allowances=plan.tier_allowances,
        stop_conditions=plan.stop_conditions,
        failure_conditions=plan.failure_conditions,
    )

    with pytest.raises(ResearchExperimentPlanError, match="exact ResearchExperimentPlan"):
        subclass.semantic_dict()


@pytest.mark.parametrize(
    "forbidden_surface",
    [
        "tests/fixtures/mrl/../mrl/candidates",
        "tests/fixtures/mrl//candidates",
        "/tests/fixtures/mrl/candidates",
        r"tests\fixtures\mrl\candidates",
    ],
)
def test_plan_revalidates_malformed_forbidden_mutation_surface_before_scope_checks(
    forbidden_surface: str,
) -> None:
    plan = _plan()
    object.__setattr__(
        plan.objective,
        "forbidden_mutation_surfaces",
        (forbidden_surface,),
    )

    with pytest.raises(ResearchExperimentPlanError):
        plan.semantic_dict()


@pytest.mark.parametrize(
    "forbidden_surface",
    [
        "experiments/../experiments/results",
        "experiments//results",
        "/experiments/results",
        r"experiments\results",
    ],
)
def test_plan_revalidates_malformed_forbidden_surface_before_result_destination_checks(
    forbidden_surface: str,
) -> None:
    plan = _plan()
    object.__setattr__(
        plan.objective,
        "forbidden_mutation_surfaces",
        (forbidden_surface,),
    )

    with pytest.raises(ResearchExperimentPlanError):
        plan.to_dict()


def test_mrl_0208_compute_ceiling_cannot_be_self_expanded_after_freeze() -> None:
    plan = _plan()
    object.__setattr__(
        plan,
        "resource_ceiling",
        replace(plan.resource_ceiling, compute_seconds=301),
    )

    with pytest.raises(ResearchExperimentPlanError, match="compute_seconds exceeds"):
        _ = plan.content_sha256


def test_mrl_0208_query_ceiling_cannot_be_self_expanded_after_freeze() -> None:
    plan = _plan()
    object.__setattr__(
        plan,
        "tier_allowances",
        (
            replace(plan.tier_allowances[0], max_queries=6),
            plan.tier_allowances[1],
        ),
    )

    with pytest.raises(ResearchExperimentPlanError, match="query allowance exceeds"):
        _ = plan.content_sha256


def test_mrl_0208_result_exposure_ceiling_cannot_be_self_expanded_after_freeze() -> None:
    plan = _plan()
    object.__setattr__(
        plan,
        "tier_allowances",
        (
            replace(plan.tier_allowances[0], max_result_exposures=6),
            plan.tier_allowances[1],
        ),
    )

    with pytest.raises(ResearchExperimentPlanError, match="result exposure exceeds"):
        _ = plan.content_sha256
