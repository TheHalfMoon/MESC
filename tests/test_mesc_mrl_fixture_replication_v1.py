"""MRL-0205 tests for fixture replication and retained-lead campaign behavior."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from medscale.mesc._mrl_fixture_loop_v1 import (
    FixtureExperimentProposal,
    FixtureLoopResult,
    complete_fixture_loop,
    propose_fixture_experiment,
)
from medscale.mesc._mrl_fixture_mutation_policy_v1 import build_fixture_mutation_policy
from medscale.mesc._mrl_fixture_replication_v1 import (
    FixtureReplicationError,
    apply_fixture_replication,
    assess_fixture_replication,
    complete_fixture_replication_cycle,
    request_fixture_replication,
    start_fixture_campaign,
)
from medscale.mesc._mrl_fixture_research_surface_v1 import (
    FixtureEvaluator,
    FixtureParameterDomain,
    FixtureParameterValue,
    FixtureResearchSurface,
    evaluate_fixture_candidate,
)
from medscale.mesc._mrl_research_campaign_v1 import CampaignNodeKind
from medscale.mesc._mrl_research_decision_v1 import (
    ResearchDecision,
    ResearchDecisionState,
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
from medscale.mesc._mrl_research_experiment_receipt_v1 import CodePatchIdentity
from medscale.mesc._mrl_research_hypothesis_v1 import ResearchHypothesis
from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
    ResearchInputClassification,
    ResearchInputSourcePermission,
    ResearchLearningSurface,
)
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
from medscale.mesc._mrl_structured_fixture_observation_v1 import (
    FixtureObservationDiagnostic,
    FixtureObservationResourceUse,
)
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.manifests import (
    DatasetSnapshot,
    ExperimentManifest,
    RunnerClass,
    RunnerEnv,
)
from medscale.reproducibility import canonical_json, content_hash

_CONFIGURATION = canonical_json({"fixture": True, "mrl": "0205"})
_DATASET = DatasetSnapshot("fixture-dataset", "1.0.0", "e" * 64)
_MODEL = ModelRef(
    model_id="fixture/model",
    revision="revision-001",
    quantization="none",
    backend="fixture",
)
_RUNNER = RunnerEnv(runner=RunnerClass.LOCAL, python="3.11", os_name="linux")
_MUTATION_PATH = "tests/fixtures/mrl/candidates/candidate.json"


def _evaluator() -> FixtureEvaluator:
    return FixtureEvaluator(
        evaluator_id="fixture-eval",
        metric_id="fixture-score",
        target_values=(
            FixtureParameterValue(parameter_id="alpha", value=1),
            FixtureParameterValue(parameter_id="beta", value=2),
        ),
    )


def _surface() -> FixtureResearchSurface:
    evaluator = _evaluator()
    return FixtureResearchSurface(
        surface_id="fixture-surface",
        parameter_domains=(
            FixtureParameterDomain(parameter_id="alpha", allowed_values=(0, 1)),
            FixtureParameterDomain(parameter_id="beta", allowed_values=(0, 2)),
        ),
        evaluator_sha256=evaluator.content_sha256,
    )


def _objective(
    *,
    max_exposures: int = 2,
    repeated_evaluation: RepeatedEvaluationPolicy = (
        RepeatedEvaluationPolicy.PERMITTED_WITHIN_FROZEN_BUDGET
    ),
) -> ResearchObjectiveContract:
    evaluator = _evaluator()
    return ResearchObjectiveContract(
        objective_id="fixture-replication-objective",
        research_program_refs=("RQ1",),
        target_capabilities=("fixture-replication-validity",),
        hard_guardrails=(
            EvidenceFloor(
                floor_id="fixture-floor",
                metric_id="fixture-score",
                comparator=FloorComparator.GTE,
                threshold_decimal="0.5",
            ),
        ),
        search_metrics=(
            MetricContract(
                metric_id="search-score",
                evaluator_id="search-eval",
                tier=EvaluationTier.SEARCH,
                direction=MetricDirection.MAXIMIZE,
            ),
        ),
        evaluation_metrics=(
            MetricContract(
                metric_id="fixture-score",
                evaluator_id=evaluator.evaluator_id,
                tier=EvaluationTier.DEVELOPMENT,
                direction=MetricDirection.MAXIMIZE,
            ),
        ),
        subgroup_floors=(),
        resource_budget=ResourceBudget(
            wall_clock_seconds=100,
            compute_seconds=None,
            input_tokens=None,
            generated_tokens=None,
            storage_bytes=10_000,
            monetary_cost_microunits=None,
            max_experiments=2,
            retries=0,
            known_failure_retries=0,
            evaluator_invocations=4,
        ),
        allowed_mutation_surfaces=("tests/fixtures/mrl/candidates",),
        forbidden_mutation_surfaces=("governance", "sealed-evaluation"),
        evaluation_tier_policy=EvaluationTierPolicy(
            allowed_tiers=(EvaluationTier.DEVELOPMENT, EvaluationTier.SEARCH)
        ),
        adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=0, tier_2_queries=0),
        adaptive_evaluation_controls=AdaptiveEvaluationControls(
            repeated_candidate_evaluation=repeated_evaluation,
            stopping_rules=(
                AdaptiveStoppingRule.EXTERNAL_GOVERNANCE_STOP,
                AdaptiveStoppingRule.OBJECTIVE_INVALIDATED,
                AdaptiveStoppingRule.RESOURCE_BUDGET_EXHAUSTED,
                AdaptiveStoppingRule.RESULT_EXPOSURE_BUDGET_EXHAUSTED,
            ),
            invalidation_rules=(
                AdaptiveInvalidationRule.EVALUATOR_IDENTITY_CHANGED,
                AdaptiveInvalidationRule.LINEAGE_OR_CONTAMINATION_FAILURE,
                AdaptiveInvalidationRule.OBJECTIVE_SEMANTICS_CHANGED,
                AdaptiveInvalidationRule.PROTECTED_SURFACE_MUTATION_ATTEMPT,
                AdaptiveInvalidationRule.SEALED_BOUNDARY_BREACH,
            ),
        ),
        tier_result_exposure_policy=(
            TierResultExposure(
                tier=EvaluationTier.DEVELOPMENT,
                max_exposures=max_exposures,
                allowed_result_fields=("max_score", "score"),
            ),
            TierResultExposure(
                tier=EvaluationTier.SEARCH,
                max_exposures=0,
                allowed_result_fields=(),
            ),
        ),
        budget_exhaustion_disposition=BudgetExhaustionDisposition.BLOCKED,
        evaluator_identities=(
            EvaluatorIdentity(
                evaluator_id=evaluator.evaluator_id,
                artifact_sha256=evaluator.content_sha256,
                tiers=(EvaluationTier.DEVELOPMENT,),
            ),
            EvaluatorIdentity(
                evaluator_id="search-eval",
                artifact_sha256="a" * 64,
                tiers=(EvaluationTier.SEARCH,),
            ),
        ),
    )


def _hypothesis(objective: ResearchObjectiveContract) -> ResearchHypothesis:
    return ResearchHypothesis(
        hypothesis_id="fixture-replication-hypothesis",
        objective_sha256=objective.content_sha256,
        mechanism="A bounded candidate may survive independent fixture replication.",
        predicted_effects=("The replica preserves the frozen fixture score.",),
        predicted_failure_modes=("The replica may fail a frozen guardrail.",),
        falsification_criteria=("The independent replica is not an evidence candidate.",),
        evidence_refs=("fixture:evidence-0205",),
        parent_hypothesis_ids=(),
        created_from_campaign_state_sha256="c" * 64,
    )


def _plan(
    label: str,
    *,
    max_exposures: int = 2,
    repeated_evaluation: RepeatedEvaluationPolicy = (
        RepeatedEvaluationPolicy.PERMITTED_WITHIN_FROZEN_BUDGET
    ),
) -> ResearchExperimentPlan:
    objective = _objective(
        max_exposures=max_exposures,
        repeated_evaluation=repeated_evaluation,
    )
    evaluator = _evaluator()
    return ResearchExperimentPlan(
        experiment_plan_id=f"fixture-plan-{label}",
        objective=objective,
        hypothesis=_hypothesis(objective),
        mutation_surfaces=(_MUTATION_PATH,),
        expected_manifest=ExpectedExperimentManifestBinding(
            experiment_id=f"fixture-experiment-{label}",
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
            seeds=(7,),
            results_paths=(f"tests/fixtures/mrl/results/{label}.json",),
        ),
        resource_ceiling=ResourceBudget(
            wall_clock_seconds=10,
            compute_seconds=None,
            input_tokens=None,
            generated_tokens=None,
            storage_bytes=1_000,
            monetary_cost_microunits=None,
            max_experiments=1,
            retries=0,
            known_failure_retries=0,
            evaluator_invocations=2,
        ),
        evaluator_identities=(
            EvaluatorIdentity(
                evaluator_id=evaluator.evaluator_id,
                artifact_sha256=evaluator.content_sha256,
                tiers=(EvaluationTier.DEVELOPMENT,),
            ),
        ),
        evaluation_tiers=(EvaluationTier.DEVELOPMENT,),
        tier_allowances=(
            PlanTierAllowance(
                tier=EvaluationTier.DEVELOPMENT,
                max_queries=0,
                max_result_exposures=1,
                allowed_result_fields=("max_score", "score"),
            ),
        ),
        stop_conditions=tuple(sorted(PlanStopCondition, key=lambda item: item.value)),
        failure_conditions=tuple(sorted(PlanFailureCondition, key=lambda item: item.value)),
    )


def _manifest(label: str) -> ExperimentManifest:
    return ExperimentManifest(
        experiment_id=f"fixture-experiment-{label}",
        rq_refs=("RQ1",),
        configuration=_CONFIGURATION,
        datasets=(_DATASET,),
        model=_MODEL,
        model_tier=1,
        code_sha="1" * 40,
        seeds=(7,),
        runner=_RUNNER,
        started_at="2026-08-28T00:00:00+00:00",
        results_paths=(f"tests/fixtures/mrl/results/{label}.json",),
        reproduction=f"uv run fixture-mrl-0205 {label}",
    )


def _admission(label: str, proposal: FixtureExperimentProposal) -> ResearchInputAdmissionContract:
    evaluation = evaluate_fixture_candidate(_surface(), _evaluator(), proposal.candidate)
    permission = ResearchInputSourcePermission(
        permission_id=f"fixture-output-{label}",
        source_artifact_sha256=evaluation.content_sha256,
        source_contract_sha256="d" * 64,
        classification=ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    return ResearchInputAdmissionContract(
        input_id=f"fixture-observation-{label}",
        classification_policy_sha256="b" * 64,
        classification=ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
        source_artifact_sha256=evaluation.content_sha256,
        source_contract_sha256="d" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        source_permission=permission,
    )


def _complete(
    label: str,
    *,
    max_exposures: int = 2,
    repeated_evaluation: RepeatedEvaluationPolicy = (
        RepeatedEvaluationPolicy.PERMITTED_WITHIN_FROZEN_BUDGET
    ),
) -> FixtureLoopResult:
    plan = _plan(
        label,
        max_exposures=max_exposures,
        repeated_evaluation=repeated_evaluation,
    )
    policy = build_fixture_mutation_policy(plan)
    proposal = propose_fixture_experiment(
        plan,
        policy,
        _surface(),
        proposal_id=f"fixture-proposal-{label}",
        mutation_path=_MUTATION_PATH,
        parameter_values=(
            FixtureParameterValue(parameter_id="alpha", value=1),
            FixtureParameterValue(parameter_id="beta", value=2),
        ),
    )
    return complete_fixture_loop(
        plan,
        policy,
        _surface(),
        _evaluator(),
        proposal,
        _admission(label, proposal),
        _manifest(label),
        CodePatchIdentity(
            code_sha="1" * 40,
            tree_sha="2" * 40,
            patch_sha256="3" * 64,
        ),
        resource_use=FixtureObservationResourceUse(
            operation_count=1,
            evaluator_invocations=1,
            storage_bytes=64,
        ),
        diagnostics=(
            FixtureObservationDiagnostic(
                code="fixture-summary",
                detail=f"Bounded fixture replication {label} completed.",
            ),
        ),
    )


def test_replication_request_is_exact_non_authoritative_decision() -> None:
    primary = _complete("primary")
    decision = request_fixture_replication(primary)

    assert decision.state is ResearchDecisionState.REPLICATE
    assert decision.receipt_sha256 == primary.receipt.content_sha256
    assert decision.evidence_sha256s == (primary.observation.content_sha256,)
    assert decision.can_authorize_promotion is False


def test_confirmed_replica_emits_retained_lead_with_two_evidence_identities() -> None:
    primary = _complete("primary")
    replica = _complete("replica")
    request = request_fixture_replication(primary)
    outcome = assess_fixture_replication(primary, request, replica)

    assert outcome.state is ResearchDecisionState.RETAIN_LEAD
    assert outcome.receipt_sha256 == replica.receipt.content_sha256
    assert outcome.evidence_sha256s == tuple(
        sorted((primary.observation.content_sha256, replica.observation.content_sha256))
    )
    assert outcome.can_authorize_promotion is False


def test_replica_must_be_independently_identified_and_exact_candidate_bound() -> None:
    primary = _complete("primary")
    request = request_fixture_replication(primary)

    with pytest.raises(FixtureReplicationError, match="distinct proposal_id"):
        assess_fixture_replication(primary, request, primary)

    different = _complete("replica")
    different_proposal = replace(
        different.proposal,
        candidate=replace(
            different.proposal.candidate,
            parameter_values=(
                FixtureParameterValue(parameter_id="alpha", value=0),
                FixtureParameterValue(parameter_id="beta", value=2),
            ),
        ),
    )
    object.__setattr__(different, "proposal", different_proposal)
    with pytest.raises((FixtureReplicationError, ValueError)):
        assess_fixture_replication(primary, request, different)


def test_campaign_update_is_append_only_and_records_replication_relation() -> None:
    primary = _complete("primary")
    replica = _complete("replica")
    campaign = start_fixture_campaign("fixture-campaign", primary)
    request = request_fixture_replication(primary)
    outcome = assess_fixture_replication(primary, request, replica)
    updated = apply_fixture_replication(campaign, primary, request, replica, outcome)

    assert updated.parent is not None
    assert updated.parent.content_sha256 == campaign.content_sha256
    assert len(updated.replications) == 1
    assert len(updated.nodes) > len(campaign.nodes)
    assert sum(node.kind is CampaignNodeKind.RECEIPT for node in updated.nodes) == 2
    assert updated.cumulative_resource_usage.storage_bytes == 128
    assert updated.cumulative_resource_usage.evaluator_invocations == 2
    assert updated.cumulative_tier_usage[0].tier is EvaluationTier.DEVELOPMENT
    assert updated.cumulative_tier_usage[0].result_exposures_used == 2
    assert len(updated.retained_alternative_node_ids) == 2
    assert set(campaign.nodes).issubset(set(updated.nodes))


def test_complete_cycle_exposes_only_fixture_non_authority_semantics() -> None:
    primary = _complete("primary")
    replica = _complete("replica")
    campaign = start_fixture_campaign("fixture-campaign", primary)
    cycle = complete_fixture_replication_cycle(campaign, primary, replica)
    payload = cycle.to_dict()

    assert cycle.retained_decision.state is ResearchDecisionState.RETAIN_LEAD
    assert payload["retained"] is True
    assert payload["fixture_only"] is True
    assert payload["non_evidence"] is True
    assert payload["can_expand_budget"] is False
    assert payload["can_authorize_real_execution"] is False
    assert payload["can_authorize_training"] is False
    assert payload["can_authorize_model_promotion"] is False


def test_forged_replication_request_fails_closed() -> None:
    primary = _complete("primary")
    replica = _complete("replica")
    forged = ResearchDecision(
        receipt_sha256=primary.receipt.content_sha256,
        evidence_sha256s=(primary.observation.content_sha256,),
        state=ResearchDecisionState.RETAIN_LEAD,
        reason="Caller-controlled state must not be accepted as a replication request.",
    )

    with pytest.raises(FixtureReplicationError, match="must use REPLICATE"):
        assess_fixture_replication(primary, forged, replica)


def test_campaign_result_exposure_budget_cannot_self_expand() -> None:
    primary = _complete("primary", max_exposures=1)
    replica = _complete("replica", max_exposures=1)
    campaign = start_fixture_campaign("fixture-campaign", primary)
    request = request_fixture_replication(primary)
    outcome = assess_fixture_replication(primary, request, replica)

    with pytest.raises(FixtureReplicationError, match="result-exposure budget"):
        apply_fixture_replication(campaign, primary, request, replica, outcome)


def test_non_evidence_candidate_cannot_request_replication() -> None:
    primary = _complete("primary")
    forged_decision = ResearchDecision(
        receipt_sha256=primary.receipt.content_sha256,
        evidence_sha256s=(primary.observation.content_sha256,),
        state=ResearchDecisionState.REJECT,
        reason="Synthetic rejection for fail-closed request coverage.",
    )
    forged = FixtureLoopResult(
        proposal=primary.proposal,
        observation=primary.observation,
        receipt=primary.receipt,
        decision=forged_decision,
    )

    with pytest.raises(FixtureReplicationError, match="EVIDENCE_CANDIDATE"):
        request_fixture_replication(forged)


def test_replication_requires_frozen_repeated_evaluation_permission() -> None:
    primary = _complete(
        "primary",
        repeated_evaluation=RepeatedEvaluationPolicy.FORBIDDEN,
    )
    replica = _complete(
        "replica",
        repeated_evaluation=RepeatedEvaluationPolicy.FORBIDDEN,
    )
    request = request_fixture_replication(primary)

    with pytest.raises(FixtureReplicationError, match="repeated candidate evaluation"):
        assess_fixture_replication(primary, request, replica)
