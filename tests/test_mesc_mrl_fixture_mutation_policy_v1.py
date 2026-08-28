"""MRL-0202 tests for the deterministic fixture mutation policy."""

from __future__ import annotations

from dataclasses import replace

import pytest

from medscale.mesc._mrl_fixture_mutation_policy_v1 import (
    FixtureMutationDisposition,
    FixtureMutationPolicy,
    FixtureMutationPolicyError,
    assess_fixture_mutation_path,
    build_fixture_mutation_policy,
    require_fixture_mutation_allowed,
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
        adaptive_query_budget=AdaptiveQueryBudget(
            tier_1_queries=5,
            tier_2_queries=0,
        ),
        adaptive_evaluation_controls=AdaptiveEvaluationControls(
            repeated_candidate_evaluation=(RepeatedEvaluationPolicy.PERMITTED_WITHIN_FROZEN_BUDGET),
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
    return ResearchExperimentPlan(
        experiment_plan_id="fixture-plan-001",
        objective=objective,
        hypothesis=hypothesis,
        mutation_surfaces=(
            "experiments/fixture.py",
            "tests/fixtures/mrl/candidates/candidate.json",
        ),
        expected_manifest=ExpectedExperimentManifestBinding(
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
        ),
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


def test_policy_is_deterministic_and_binds_exact_plan() -> None:
    plan = _plan()
    first = build_fixture_mutation_policy(plan)
    second = build_fixture_mutation_policy(_plan())

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.experiment_plan_sha256 == plan.content_sha256
    assert first.allowed_surfaces == plan.mutation_surfaces
    assert first.forbidden_surfaces == plan.objective.forbidden_mutation_surfaces
    assert "content_sha256" not in first.semantic_dict()
    assert first.to_dict()["content_sha256"] == first.content_sha256


def test_policy_is_fixture_only_non_evidence_and_cannot_apply_mutations() -> None:
    payload = build_fixture_mutation_policy(_plan()).semantic_dict()

    assert payload["fixture_only"] is True
    assert payload["non_evidence"] is True
    assert payload["can_apply_mutation"] is False
    assert payload["can_authorize_real_execution"] is False
    assert payload["can_authorize_training"] is False
    assert payload["can_authorize_model_promotion"] is False


@pytest.mark.parametrize(
    "path",
    [
        "experiments/fixture.py",
        "tests/fixtures/mrl/candidates/candidate.json",
    ],
)
def test_exact_plan_allow_list_paths_are_allowed(path: str) -> None:
    plan = _plan()
    policy = build_fixture_mutation_policy(plan)

    assert assess_fixture_mutation_path(plan, policy, path) is FixtureMutationDisposition.ALLOW
    require_fixture_mutation_allowed(plan, policy, path)


@pytest.mark.parametrize(
    "path",
    [
        "experiments/unlisted.py",
        "research/experiments/unlisted.json",
        "tests/fixtures/mrl/other.json",
    ],
)
def test_paths_outside_plan_allow_list_are_rejected(path: str) -> None:
    plan = _plan()
    policy = build_fixture_mutation_policy(plan)

    assert (
        assess_fixture_mutation_path(plan, policy, path)
        is FixtureMutationDisposition.REJECT_OUTSIDE_ALLOW_LIST
    )
    with pytest.raises(FixtureMutationPolicyError, match="REJECT_OUTSIDE_ALLOW_LIST"):
        require_fixture_mutation_allowed(plan, policy, path)


@pytest.mark.parametrize(
    ("authority", "path"),
    [
        (
            "evaluator",
            "src/medscale/mesc/_mrl_fixture_research_surface_v1.py",
        ),
        (
            "governance",
            "docs/adr/0035-mrl-governance-constitution.md",
        ),
        (
            "sealed-data",
            "data/sealed/tier-3-items.jsonl",
        ),
        (
            "authorization",
            "specs/mesc-research-loop-v1/tasks.md",
        ),
        (
            "trust",
            "collaboration/reviewers/alice.json",
        ),
        (
            "machine-state",
            "PROJECT_STATE.json",
        ),
        (
            "ci-security",
            ".github/workflows/ci.yml",
        ),
    ],
)
def test_authority_bearing_paths_are_rejected(authority: str, path: str) -> None:
    del authority
    plan = _plan()
    policy = build_fixture_mutation_policy(plan)

    assert (
        assess_fixture_mutation_path(plan, policy, path)
        is FixtureMutationDisposition.REJECT_PROTECTED_AUTHORITY
    )
    with pytest.raises(FixtureMutationPolicyError, match="REJECT_PROTECTED_AUTHORITY"):
        require_fixture_mutation_allowed(plan, policy, path)


def test_policy_cannot_delete_a_canonical_protected_surface() -> None:
    policy = build_fixture_mutation_policy(_plan())

    with pytest.raises(
        FixtureMutationPolicyError,
        match="must exactly match the canonical policy",
    ):
        replace(
            policy,
            protected_authority_surfaces=policy.protected_authority_surfaces[:-1],
        )


def test_policy_cannot_add_a_protected_path_to_its_allow_list() -> None:
    policy = build_fixture_mutation_policy(_plan())

    with pytest.raises(
        FixtureMutationPolicyError,
        match="overlaps protected authority",
    ):
        replace(policy, allowed_surfaces=("src/medscale/mesc/evaluator.py",))


def test_policy_must_stay_bound_to_the_exact_plan_allow_list() -> None:
    plan = _plan()
    policy = build_fixture_mutation_policy(plan)
    narrowed = replace(policy, allowed_surfaces=("experiments/fixture.py",))

    with pytest.raises(
        FixtureMutationPolicyError,
        match="allow-list does not exactly match the plan",
    ):
        assess_fixture_mutation_path(plan, narrowed, "experiments/fixture.py")


def test_policy_must_stay_bound_to_exact_plan_identity() -> None:
    plan = _plan()
    policy = build_fixture_mutation_policy(plan)
    altered_objective = replace(
        plan.objective,
        target_capabilities=("different-capability",),
    )
    altered_hypothesis = replace(
        plan.hypothesis,
        objective_sha256=altered_objective.content_sha256,
    )
    other_plan = replace(
        plan,
        objective=altered_objective,
        hypothesis=altered_hypothesis,
    )

    with pytest.raises(
        FixtureMutationPolicyError,
        match="does not bind the supplied experiment plan",
    ):
        assess_fixture_mutation_path(
            other_plan,
            policy,
            "experiments/fixture.py",
        )


@pytest.mark.parametrize(
    "path",
    [
        "/experiments/fixture.py",
        "experiments/fixture.py/",
        "experiments/../specs/tasks.md",
        r"experiments\fixture.py",
        "experiments//fixture.py",
        "",
    ],
)
def test_noncanonical_paths_fail_closed(path: str) -> None:
    plan = _plan()
    policy = build_fixture_mutation_policy(plan)

    with pytest.raises(FixtureMutationPolicyError, match=r"non-canonical|non-empty"):
        assess_fixture_mutation_path(plan, policy, path)


def test_post_construction_policy_tamper_fails_closed() -> None:
    plan = _plan()
    policy = build_fixture_mutation_policy(plan)
    object.__setattr__(
        policy,
        "allowed_surfaces",
        ("src/medscale/mesc/_mrl_fixture_research_surface_v1.py",),
    )

    with pytest.raises(FixtureMutationPolicyError):
        policy.semantic_dict()
    with pytest.raises(FixtureMutationPolicyError):
        assess_fixture_mutation_path(
            plan,
            policy,
            "src/medscale/mesc/_mrl_fixture_research_surface_v1.py",
        )


def test_derived_plan_cannot_override_snapshot_dispatch() -> None:
    trusted = _plan()

    class DerivedPlan(ResearchExperimentPlan):
        def _validated_snapshot(self) -> ResearchExperimentPlan:
            return trusted

    derived = DerivedPlan(
        experiment_plan_id=trusted.experiment_plan_id,
        objective=trusted.objective,
        hypothesis=trusted.hypothesis,
        mutation_surfaces=trusted.mutation_surfaces,
        expected_manifest=trusted.expected_manifest,
        resource_ceiling=trusted.resource_ceiling,
        evaluator_identities=trusted.evaluator_identities,
        evaluation_tiers=trusted.evaluation_tiers,
        tier_allowances=trusted.tier_allowances,
        stop_conditions=trusted.stop_conditions,
        failure_conditions=trusted.failure_conditions,
    )

    with pytest.raises(
        FixtureMutationPolicyError,
        match="must be exact ResearchExperimentPlan",
    ):
        build_fixture_mutation_policy(derived)


def test_derived_policy_cannot_override_snapshot_dispatch() -> None:
    plan = _plan()
    trusted = build_fixture_mutation_policy(plan)

    class DerivedPolicy(FixtureMutationPolicy):
        def _validated_snapshot(self) -> FixtureMutationPolicy:
            return trusted

    derived = DerivedPolicy(
        policy_id=trusted.policy_id,
        experiment_plan_sha256=trusted.experiment_plan_sha256,
        allowed_surfaces=trusted.allowed_surfaces,
        forbidden_surfaces=trusted.forbidden_surfaces,
        protected_authority_surfaces=trusted.protected_authority_surfaces,
    )

    with pytest.raises(
        FixtureMutationPolicyError,
        match="must be exact FixtureMutationPolicy",
    ):
        assess_fixture_mutation_path(
            plan,
            derived,
            "experiments/fixture.py",
        )
