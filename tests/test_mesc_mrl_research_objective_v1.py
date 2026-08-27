"""MRL-0101 tests for the immutable ResearchObjectiveContract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, fields, replace

import pytest

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
    ResearchObjectiveContractError,
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
            retries=3,
            known_failure_retries=1,
            evaluator_invocations=20,
        ),
        allowed_mutation_surfaces=("tests/fixtures/mrl/fixture.py",),
        forbidden_mutation_surfaces=("governance", "sealed-evaluation"),
        evaluation_tier_policy=EvaluationTierPolicy(
            allowed_tiers=(EvaluationTier.SEARCH, EvaluationTier.SEALED)
        ),
        adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=5, tier_2_queries=0),
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


def test_objective_identity_is_outside_semantic_preimage() -> None:
    objective = _objective()

    assert b"content_sha256" not in objective.semantic_bytes
    assert "content_sha256" not in objective.semantic_dict()
    assert objective.to_dict()["content_sha256"] == objective.content_sha256
    assert len(objective.content_sha256) == 64


def test_equivalent_objectives_have_byte_stable_identity() -> None:
    first = _objective()
    second = _objective()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: replace(
            value,
            resource_budget=replace(value.resource_budget, wall_clock_seconds=601),
        ),
        lambda value: replace(
            value,
            adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=4, tier_2_queries=0),
        ),
        lambda value: replace(
            value,
            tier_result_exposure_policy=(
                TierResultExposure(
                    tier=EvaluationTier.SEARCH,
                    max_exposures=4,
                    allowed_result_fields=("aggregate_score", "cost_microunits"),
                ),
                TierResultExposure(
                    tier=EvaluationTier.SEALED,
                    max_exposures=0,
                    allowed_result_fields=(),
                ),
            ),
        ),
        lambda value: replace(
            value,
            evaluator_identities=(
                EvaluatorIdentity(
                    evaluator_id="eval.sealed",
                    artifact_sha256="c" * 64,
                    tiers=(EvaluationTier.SEALED,),
                ),
                value.evaluator_identities[1],
            ),
        ),
        lambda value: replace(
            value,
            hard_guardrails=(replace(value.hard_guardrails[0], threshold_decimal="0.96"),),
        ),
        lambda value: replace(
            value,
            allowed_mutation_surfaces=("experiments/other-fixture.py",),
        ),
        lambda value: replace(
            value,
            adaptive_evaluation_controls=replace(
                value.adaptive_evaluation_controls,
                repeated_candidate_evaluation=RepeatedEvaluationPolicy.FORBIDDEN,
            ),
        ),
    ],
)
def test_material_semantic_changes_change_content_identity(mutate: object) -> None:
    original = _objective()
    changed = mutate(original)  # type: ignore[operator]

    assert changed.content_sha256 != original.content_sha256


def test_objective_and_nested_contracts_are_frozen() -> None:
    objective = _objective()

    with pytest.raises(FrozenInstanceError):
        objective.objective_id = "changed"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        objective.resource_budget.retries = 99  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("wall_clock_seconds", 0),
        ("wall_clock_seconds", True),
        ("compute_seconds", -1),
        ("storage_bytes", -1),
        ("retries", -1),
        ("evaluator_invocations", -1),
    ],
)
def test_invalid_resource_ceilings_fail_closed(field: str, value: object) -> None:
    kwargs: dict[str, object] = {
        "wall_clock_seconds": 600,
        "compute_seconds": 300,
        "input_tokens": 10_000,
        "generated_tokens": 2_000,
        "storage_bytes": 1_000_000,
        "monetary_cost_microunits": 500_000,
        "retries": 3,
        "known_failure_retries": 1,
        "evaluator_invocations": 20,
    }
    kwargs[field] = value

    with pytest.raises(ResearchObjectiveContractError):
        ResourceBudget(**kwargs)  # type: ignore[arg-type]


def test_known_failure_retry_ceiling_cannot_exceed_total_retries() -> None:
    with pytest.raises(ResearchObjectiveContractError, match="cannot exceed retries"):
        replace(_objective().resource_budget, retries=1, known_failure_retries=2)


@pytest.mark.parametrize(
    "threshold",
    ["0.90", "1e-1", ".9", "-0", "01", "nan", "inf"],
)
def test_noncanonical_floor_decimals_fail_closed(threshold: str) -> None:
    with pytest.raises(ResearchObjectiveContractError):
        replace(_objective().hard_guardrails[0], threshold_decimal=threshold)


def test_allowed_and_forbidden_mutation_surfaces_cannot_overlap() -> None:
    with pytest.raises(ResearchObjectiveContractError, match="both allowed and forbidden"):
        replace(
            _objective(),
            forbidden_mutation_surfaces=("governance", "tests/fixtures/mrl/fixture.py"),
        )


def test_set_like_semantics_must_be_strictly_sorted_and_unique() -> None:
    objective = _objective()

    with pytest.raises(ResearchObjectiveContractError, match="strictly sorted"):
        replace(objective, target_capabilities=("zeta", "alpha"))
    with pytest.raises(ResearchObjectiveContractError, match="strictly sorted"):
        replace(
            objective,
            evaluator_identities=tuple(reversed(objective.evaluator_identities)),
        )
    with pytest.raises(ResearchObjectiveContractError, match="strictly sorted"):
        replace(
            objective,
            research_program_refs=("RQ1", "RQ1"),
        )


@pytest.mark.parametrize("reference", ["UNREGISTERED-RQ-0001", "MRL-RQ-0001"])
def test_unregistered_research_program_reference_fails_closed(reference: str) -> None:
    with pytest.raises(ResearchObjectiveContractError, match="unregistered canonical question"):
        replace(_objective(), research_program_refs=(reference,))


def test_metric_must_reference_a_frozen_evaluator_identity() -> None:
    objective = _objective()
    with pytest.raises(ResearchObjectiveContractError, match="unknown evaluator"):
        replace(
            objective,
            search_metrics=(replace(objective.search_metrics[0], evaluator_id="eval.unknown"),),
        )


def test_metric_identity_cannot_be_reused_across_search_and_evaluation() -> None:
    objective = _objective()
    with pytest.raises(ResearchObjectiveContractError, match="cannot be reused"):
        replace(
            objective,
            evaluation_metrics=(
                replace(objective.evaluation_metrics[0], metric_id="search-score"),
            ),
            hard_guardrails=(replace(objective.hard_guardrails[0], metric_id="search-score"),),
            subgroup_floors=(replace(objective.subgroup_floors[0], metric_id="search-score"),),
        )


def test_evaluator_cannot_reference_tier_outside_objective_policy() -> None:
    objective = _objective()
    with pytest.raises(ResearchObjectiveContractError, match="outside the objective policy"):
        replace(
            objective,
            evaluator_identities=(
                objective.evaluator_identities[0],
                replace(
                    objective.evaluator_identities[1],
                    tiers=(EvaluationTier.SEARCH, EvaluationTier.REPLICATION),
                ),
            ),
        )


def test_floor_roles_and_metric_bindings_fail_closed() -> None:
    objective = _objective()

    with pytest.raises(ResearchObjectiveContractError, match="hard_guardrails must be global"):
        replace(
            objective,
            hard_guardrails=(replace(objective.hard_guardrails[0], subgroup="cohort"),),
        )
    with pytest.raises(ResearchObjectiveContractError, match="require a subgroup"):
        replace(
            objective,
            subgroup_floors=(replace(objective.subgroup_floors[0], subgroup=None),),
        )
    with pytest.raises(ResearchObjectiveContractError, match="evaluation metric"):
        replace(
            objective,
            hard_guardrails=(replace(objective.hard_guardrails[0], metric_id="search-score"),),
        )


def test_tier_3_and_4_cannot_expose_iterative_agent_feedback() -> None:
    with pytest.raises(ResearchObjectiveContractError, match="cannot expose"):
        TierResultExposure(
            tier=EvaluationTier.SEALED,
            max_exposures=1,
            allowed_result_fields=(),
        )
    with pytest.raises(ResearchObjectiveContractError, match="cannot expose"):
        TierResultExposure(
            tier=EvaluationTier.EXTERNAL_ASSURANCE,
            max_exposures=0,
            allowed_result_fields=("aggregate_score",),
        )


def test_exposure_policy_must_match_allowed_tiers_exactly() -> None:
    objective = _objective()
    with pytest.raises(ResearchObjectiveContractError, match="exactly every allowed"):
        replace(
            objective,
            tier_result_exposure_policy=(objective.tier_result_exposure_policy[0],),
        )


def test_adaptive_query_budget_cannot_target_disallowed_tier() -> None:
    objective = _objective()
    with pytest.raises(ResearchObjectiveContractError, match="tier_2_queries must be zero"):
        replace(
            objective,
            adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=5, tier_2_queries=1),
        )


def test_runtime_type_confusion_fails_closed() -> None:
    objective = _objective()

    with pytest.raises(ResearchObjectiveContractError, match="exact MetricDirection"):
        replace(
            objective,
            search_metrics=(
                MetricContract(
                    metric_id="search-score",
                    evaluator_id="eval.search",
                    tier=EvaluationTier.SEARCH,
                    direction="MAXIMIZE",  # type: ignore[arg-type]
                ),
            ),
        )
    with pytest.raises(ResearchObjectiveContractError, match="exact EvaluationTier"):
        TierResultExposure(
            tier=3,  # type: ignore[arg-type]
            max_exposures=0,
            allowed_result_fields=(),
        )


def test_unknown_constructor_field_is_rejected_by_closed_typed_contract() -> None:
    objective = _objective()
    kwargs = {
        field.name: getattr(objective, field.name) for field in fields(ResearchObjectiveContract)
    }
    kwargs["unknown_field"] = "rejected"

    with pytest.raises(TypeError, match="unexpected keyword"):
        ResearchObjectiveContract(**kwargs)


@pytest.mark.parametrize(
    "surface",
    [
        ".github/workflows/ci.yml",
        "data/sealed-evaluation.jsonl",
        "docs/adr/0035-mrl-governance-constitution.md",
        "specs/mesc-research-loop-v1/spec.md",
        "src/medscale/mesc/evaluator.py",
    ],
)
def test_protected_mutation_surfaces_cannot_be_allow_listed(surface: str) -> None:
    with pytest.raises(ResearchObjectiveContractError, match="campaign-mutable roots"):
        replace(_objective(), allowed_mutation_surfaces=(surface,))


def test_noncanonical_allowed_mutation_path_fails_closed() -> None:
    with pytest.raises(ResearchObjectiveContractError, match="non-canonical relative path"):
        replace(
            _objective(),
            allowed_mutation_surfaces=("tests/fixtures/mrl/../sealed.json",),
        )


def test_governed_campaign_mutation_root_is_accepted() -> None:
    objective = replace(
        _objective(),
        allowed_mutation_surfaces=("experiments/fixture.py",),
    )
    assert objective.allowed_mutation_surfaces == ("experiments/fixture.py",)


def test_search_metric_cannot_use_sealed_only_evaluator() -> None:
    objective = _objective()
    with pytest.raises(ResearchObjectiveContractError, match="does not admit metric tier"):
        replace(
            objective,
            search_metrics=(
                replace(
                    objective.search_metrics[0],
                    evaluator_id="eval.sealed",
                ),
            ),
        )


def test_search_and_evaluation_metric_tiers_cannot_collapse() -> None:
    objective = _objective()
    with pytest.raises(ResearchObjectiveContractError, match="must use Tier 1 SEARCH"):
        replace(
            objective,
            search_metrics=(replace(objective.search_metrics[0], tier=EvaluationTier.SEALED),),
        )
    with pytest.raises(ResearchObjectiveContractError, match="cannot use Tier 1 SEARCH"):
        replace(
            objective,
            evaluation_metrics=(
                replace(objective.evaluation_metrics[0], tier=EvaluationTier.SEARCH),
            ),
        )


def test_metric_tier_must_be_allowed_by_objective() -> None:
    objective = _objective()
    with pytest.raises(ResearchObjectiveContractError, match="outside the objective policy"):
        replace(
            objective,
            evaluation_tier_policy=EvaluationTierPolicy(allowed_tiers=(EvaluationTier.SEARCH,)),
            tier_result_exposure_policy=(objective.tier_result_exposure_policy[0],),
        )


def test_adaptive_controls_are_required_and_canonical() -> None:
    controls = _objective().adaptive_evaluation_controls
    with pytest.raises(ResearchObjectiveContractError, match="non-empty exact tuple"):
        replace(controls, stopping_rules=())
    with pytest.raises(ResearchObjectiveContractError, match="non-empty exact tuple"):
        replace(controls, invalidation_rules=())
    with pytest.raises(ResearchObjectiveContractError, match="canonically sorted"):
        replace(controls, stopping_rules=tuple(reversed(controls.stopping_rules)))
    with pytest.raises(ResearchObjectiveContractError, match="exact RepeatedEvaluationPolicy"):
        AdaptiveEvaluationControls(
            repeated_candidate_evaluation="FORBIDDEN",  # type: ignore[arg-type]
            stopping_rules=controls.stopping_rules,
            invalidation_rules=controls.invalidation_rules,
        )


def test_adaptive_control_semantics_are_content_addressed() -> None:
    objective = _objective()
    changed_stopping = replace(
        objective,
        adaptive_evaluation_controls=replace(
            objective.adaptive_evaluation_controls,
            stopping_rules=(AdaptiveStoppingRule.OBJECTIVE_INVALIDATED,),
        ),
    )
    changed_invalidation = replace(
        objective,
        adaptive_evaluation_controls=replace(
            objective.adaptive_evaluation_controls,
            invalidation_rules=(AdaptiveInvalidationRule.OBJECTIVE_SEMANTICS_CHANGED,),
        ),
    )

    assert changed_stopping.content_sha256 != objective.content_sha256
    assert changed_invalidation.content_sha256 != objective.content_sha256


def test_mutation_surface_with_nul_fails_closed() -> None:
    with pytest.raises(ResearchObjectiveContractError, match=r"canonical text|canonical relative"):
        replace(
            _objective(),
            allowed_mutation_surfaces=("experiments/result\x00.json",),
        )


def test_post_construction_top_level_mutation_fails_closed_at_public_views() -> None:
    objective = _objective()
    object.__setattr__(
        objective,
        "allowed_mutation_surfaces",
        ("src/medscale/mesc/forged.py",),
    )

    with pytest.raises(ResearchObjectiveContractError, match="campaign-mutable roots"):
        objective.semantic_dict()
    with pytest.raises(ResearchObjectiveContractError, match="campaign-mutable roots"):
        _ = objective.semantic_bytes
    with pytest.raises(ResearchObjectiveContractError, match="campaign-mutable roots"):
        _ = objective.content_sha256
    with pytest.raises(ResearchObjectiveContractError, match="campaign-mutable roots"):
        objective.to_dict()


def test_post_construction_nested_budget_mutation_fails_closed_at_public_views() -> None:
    objective = _objective()
    object.__setattr__(objective.resource_budget, "retries", -1)

    with pytest.raises(ResearchObjectiveContractError, match="retries must be a non-negative"):
        objective.semantic_dict()
    with pytest.raises(ResearchObjectiveContractError, match="retries must be a non-negative"):
        _ = objective.content_sha256
    with pytest.raises(ResearchObjectiveContractError, match="retries must be a non-negative"):
        objective.to_dict()


def test_post_construction_nested_metric_mutation_rechecks_cross_field_invariants() -> None:
    objective = _objective()
    object.__setattr__(objective.search_metrics[0], "tier", EvaluationTier.SEALED)

    with pytest.raises(ResearchObjectiveContractError, match="must use Tier 1 SEARCH"):
        objective.semantic_dict()
    with pytest.raises(ResearchObjectiveContractError, match="must use Tier 1 SEARCH"):
        _ = objective.content_sha256


def test_post_construction_nested_evaluator_mutation_rechecks_tier_binding() -> None:
    objective = _objective()
    object.__setattr__(
        objective.evaluator_identities[1],
        "tiers",
        (EvaluationTier.SEALED,),
    )

    with pytest.raises(ResearchObjectiveContractError, match="does not admit metric tier"):
        objective.semantic_dict()
    with pytest.raises(ResearchObjectiveContractError, match="does not admit metric tier"):
        _ = objective.content_sha256
