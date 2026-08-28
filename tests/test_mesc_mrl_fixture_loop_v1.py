"""MRL-0204 tests for the deterministic fixture propose/run/receipt/decision loop."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from medscale.mesc._mrl_fixture_loop_v1 import (
    FixtureExperimentProposal,
    FixtureLoopError,
    FixtureLoopResult,
    build_fixture_experiment_receipt,
    complete_fixture_loop,
    decide_fixture_experiment,
    execute_fixture_proposal,
    propose_fixture_experiment,
)
from medscale.mesc._mrl_fixture_mutation_policy_v1 import (
    FixtureMutationPolicy,
    build_fixture_mutation_policy,
)
from medscale.mesc._mrl_fixture_research_surface_v1 import (
    FixtureEvaluator,
    FixtureParameterDomain,
    FixtureParameterValue,
    FixtureResearchSurface,
    evaluate_fixture_candidate,
)
from medscale.mesc._mrl_research_decision_v1 import ResearchDecisionState
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
    FixtureObservationFailureClass,
    FixtureObservationResourceUse,
    FixtureObservationRunStatus,
    FixtureRawOutputArtifact,
    FixtureRawOutputStream,
    StructuredFixtureObservation,
)
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.manifests import (
    DatasetSnapshot,
    ExperimentManifest,
    RunnerClass,
    RunnerEnv,
)
from medscale.reproducibility import canonical_json, content_hash

_CONFIGURATION = canonical_json({"fixture": True, "mrl": "0204"})
_DATASET = DatasetSnapshot("fixture-dataset", "1.0.0", "e" * 64)
_MODEL = ModelRef(
    model_id="fixture/model",
    revision="revision-001",
    quantization="none",
    backend="fixture",
)
_RUNNER = RunnerEnv(runner=RunnerClass.LOCAL, python="3.11", os_name="linux")
_RESULTS = ("tests/fixtures/mrl/results/fixture-experiment-001.json",)
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


def _objective() -> ResearchObjectiveContract:
    evaluator = _evaluator()
    return ResearchObjectiveContract(
        objective_id="fixture-research-objective",
        research_program_refs=("RQ1",),
        target_capabilities=("fixture-loop-validity",),
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
            max_experiments=4,
            retries=1,
            known_failure_retries=0,
            evaluator_invocations=10,
        ),
        allowed_mutation_surfaces=("tests/fixtures/mrl/candidates",),
        forbidden_mutation_surfaces=("governance", "sealed-evaluation"),
        evaluation_tier_policy=EvaluationTierPolicy(
            allowed_tiers=(EvaluationTier.DEVELOPMENT, EvaluationTier.SEARCH)
        ),
        adaptive_query_budget=AdaptiveQueryBudget(
            tier_1_queries=0,
            tier_2_queries=0,
        ),
        adaptive_evaluation_controls=AdaptiveEvaluationControls(
            repeated_candidate_evaluation=RepeatedEvaluationPolicy.FORBIDDEN,
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
                max_exposures=1,
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
        hypothesis_id="fixture-hypothesis",
        objective_sha256=objective.content_sha256,
        mechanism="A bounded fixture parameter assignment may satisfy the toy objective.",
        predicted_effects=("The fixture score increases under the frozen evaluator.",),
        predicted_failure_modes=("The bounded candidate may not satisfy the fixture target.",),
        falsification_criteria=("The frozen fixture evaluator reports a non-perfect score.",),
        evidence_refs=("fixture:evidence-0204",),
        parent_hypothesis_ids=(),
        created_from_campaign_state_sha256="c" * 64,
    )


def _plan() -> ResearchExperimentPlan:
    objective = _objective()
    evaluator = _evaluator()
    return ResearchExperimentPlan(
        experiment_plan_id="fixture-plan-0204",
        objective=objective,
        hypothesis=_hypothesis(objective),
        mutation_surfaces=(_MUTATION_PATH,),
        expected_manifest=ExpectedExperimentManifestBinding(
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
            seeds=(7,),
            results_paths=_RESULTS,
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


def _manifest(*, code_sha: str = "1" * 40) -> ExperimentManifest:
    return ExperimentManifest(
        experiment_id="fixture-experiment-001",
        rq_refs=("RQ1",),
        configuration=_CONFIGURATION,
        datasets=(_DATASET,),
        model=_MODEL,
        model_tier=1,
        code_sha=code_sha,
        seeds=(7,),
        runner=_RUNNER,
        started_at="2026-08-28T00:00:00+00:00",
        results_paths=_RESULTS,
        reproduction="uv run fixture-mrl-0204",
    )


def _proposal(
    *,
    alpha: int = 1,
    beta: int = 2,
) -> FixtureExperimentProposal:
    plan = _plan()
    return propose_fixture_experiment(
        plan,
        build_fixture_mutation_policy(plan),
        _surface(),
        proposal_id="fixture-proposal-0204",
        mutation_path=_MUTATION_PATH,
        parameter_values=(
            FixtureParameterValue(parameter_id="alpha", value=alpha),
            FixtureParameterValue(parameter_id="beta", value=beta),
        ),
    )


def _admission_for_proposal(
    proposal: FixtureExperimentProposal,
) -> ResearchInputAdmissionContract:
    evaluation = evaluate_fixture_candidate(
        _surface(),
        _evaluator(),
        proposal.candidate,
    )
    permission = ResearchInputSourcePermission(
        permission_id="fixture-output-permission",
        source_artifact_sha256=evaluation.content_sha256,
        source_contract_sha256="d" * 64,
        classification=ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    return ResearchInputAdmissionContract(
        input_id="fixture-loop-observation-input",
        classification_policy_sha256="b" * 64,
        classification=ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
        source_artifact_sha256=evaluation.content_sha256,
        source_contract_sha256="d" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        source_permission=permission,
    )


def _negative_admission(raw_sha256: str) -> ResearchInputAdmissionContract:
    permission = ResearchInputSourcePermission(
        permission_id="fixture-failure-permission",
        source_artifact_sha256=raw_sha256,
        source_contract_sha256="d" * 64,
        classification=ResearchInputClassification.NEGATIVE_OR_INVALID_RESEARCH_RESULT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    return ResearchInputAdmissionContract(
        input_id="fixture-loop-failure-input",
        classification_policy_sha256="b" * 64,
        classification=ResearchInputClassification.NEGATIVE_OR_INVALID_RESEARCH_RESULT,
        source_artifact_sha256=raw_sha256,
        source_contract_sha256="d" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        source_permission=permission,
    )


def _resource_use(
    *,
    operation_count: int = 1,
    evaluator_invocations: int = 1,
    storage_bytes: int = 64,
) -> FixtureObservationResourceUse:
    return FixtureObservationResourceUse(
        operation_count=operation_count,
        evaluator_invocations=evaluator_invocations,
        storage_bytes=storage_bytes,
    )


def _code_identity() -> CodePatchIdentity:
    return CodePatchIdentity(
        code_sha="1" * 40,
        tree_sha="2" * 40,
        patch_sha256="3" * 64,
    )


def _complete(
    *,
    alpha: int = 1,
    beta: int = 2,
) -> FixtureLoopResult:
    plan = _plan()
    policy = build_fixture_mutation_policy(plan)
    proposal = propose_fixture_experiment(
        plan,
        policy,
        _surface(),
        proposal_id="fixture-proposal-0204",
        mutation_path=_MUTATION_PATH,
        parameter_values=(
            FixtureParameterValue(parameter_id="alpha", value=alpha),
            FixtureParameterValue(parameter_id="beta", value=beta),
        ),
    )
    return complete_fixture_loop(
        plan,
        policy,
        _surface(),
        _evaluator(),
        proposal,
        _admission_for_proposal(proposal),
        _manifest(),
        _code_identity(),
        resource_use=_resource_use(),
        raw_output_artifacts=(
            FixtureRawOutputArtifact(
                stream=FixtureRawOutputStream.STDOUT,
                artifact_sha256="f" * 64,
            ),
        ),
        diagnostics=(
            FixtureObservationDiagnostic(
                code="fixture-summary",
                detail="Bounded fixture evaluation completed.",
            ),
        ),
    )


def test_proposal_is_deterministic_and_binds_exact_plan_policy_surface() -> None:
    first = _proposal()
    second = _proposal()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256
    assert first.experiment_plan_sha256 == _plan().content_sha256
    assert first.mutation_policy_sha256 == build_fixture_mutation_policy(_plan()).content_sha256
    assert first.research_surface_sha256 == _surface().content_sha256
    assert first.candidate.surface_sha256 == _surface().content_sha256
    assert "content_sha256" not in first.semantic_dict()


def test_proposal_rejects_path_outside_frozen_mutation_policy() -> None:
    plan = _plan()

    with pytest.raises(ValueError, match="REJECT_OUTSIDE_ALLOW_LIST"):
        propose_fixture_experiment(
            plan,
            build_fixture_mutation_policy(plan),
            _surface(),
            proposal_id="fixture-proposal-0204",
            mutation_path="tests/fixtures/mrl/other.json",
            parameter_values=(
                FixtureParameterValue(parameter_id="alpha", value=1),
                FixtureParameterValue(parameter_id="beta", value=2),
            ),
        )


def test_execute_fixture_proposal_returns_exact_structured_observation() -> None:
    plan = _plan()
    policy = build_fixture_mutation_policy(plan)
    proposal = _proposal()
    observation = execute_fixture_proposal(
        plan,
        policy,
        _surface(),
        _evaluator(),
        proposal,
        _admission_for_proposal(proposal),
        resource_use=_resource_use(),
        raw_output_artifacts=(
            FixtureRawOutputArtifact(
                stream=FixtureRawOutputStream.STDOUT,
                artifact_sha256="f" * 64,
            ),
        ),
    )

    assert observation.run_status is FixtureObservationRunStatus.SUCCEEDED
    assert observation.evaluation is not None
    assert observation.evaluation.candidate_sha256 == proposal.candidate.content_sha256
    payload = observation.semantic_dict()
    assert payload["trusted_control_input"] is False
    assert payload["raw_output_trusted_control"] is False


def test_complete_fixture_loop_builds_canonical_receipt_and_evidence_candidate() -> None:
    result = _complete()
    payload = result.semantic_dict()

    assert result.decision.state is ResearchDecisionState.EVIDENCE_CANDIDATE
    assert result.receipt.binding.plan.content_sha256 == result.proposal.experiment_plan_sha256
    assert result.observation.evaluation is not None
    assert result.receipt.metric_artifacts[0].artifact_sha256 == (
        result.observation.evaluation.content_sha256
    )
    assert result.receipt.raw_output_artifact_sha256s == ("f" * 64,)
    assert result.decision.receipt_sha256 == result.receipt.content_sha256
    assert result.decision.evidence_sha256s == (result.observation.content_sha256,)
    assert payload["fixture_only"] is True
    assert payload["non_evidence"] is True
    assert payload["can_update_campaign"] is False
    assert payload["can_authorize_real_execution"] is False
    assert payload["can_authorize_training"] is False
    assert payload["can_authorize_model_promotion"] is False


def test_nonperfect_fixture_result_is_rejected_without_replication_behavior() -> None:
    result = _complete(alpha=1, beta=0)

    assert result.observation.evaluation is not None
    assert result.observation.evaluation.score == 1
    assert result.receipt.guardrail_results[0].passed is True
    assert result.decision.state is ResearchDecisionState.REJECT
    assert result.decision.state not in (
        ResearchDecisionState.REPLICATE,
        ResearchDecisionState.RETAIN_LEAD,
    )


def test_hard_guardrail_failure_rejects_fixture_result() -> None:
    result = _complete(alpha=0, beta=0)

    assert result.observation.evaluation is not None
    assert result.observation.evaluation.score == 0
    assert result.receipt.guardrail_results[0].passed is False
    assert result.decision.state is ResearchDecisionState.REJECT


def test_failed_fixture_observation_builds_invalid_canonical_receipt() -> None:
    plan = _plan()
    proposal = _proposal()
    raw_sha256 = "7" * 64
    observation = StructuredFixtureObservation(
        observation_id="fixture-proposal-0204-observation",
        input_admission=_negative_admission(raw_sha256),
        run_status=FixtureObservationRunStatus.FAILED,
        evaluation=None,
        resource_use=_resource_use(evaluator_invocations=0),
        failure_class=FixtureObservationFailureClass.EXECUTION_FAILED,
        raw_output_artifacts=(
            FixtureRawOutputArtifact(
                stream=FixtureRawOutputStream.STDERR,
                artifact_sha256=raw_sha256,
            ),
        ),
    )
    receipt = build_fixture_experiment_receipt(
        plan,
        _evaluator(),
        observation,
        _manifest(),
        _code_identity(),
    )
    decision = decide_fixture_experiment(proposal, observation, receipt)

    assert receipt.failure_classification is PlanFailureCondition.EXECUTION_ERROR
    assert receipt.metric_artifacts == ()
    assert receipt.guardrail_results == ()
    assert decision.state is ResearchDecisionState.INVALID


def test_resource_blocked_observation_maps_to_blocked_decision() -> None:
    plan = _plan()
    proposal = _proposal()
    raw_sha256 = "8" * 64
    observation = StructuredFixtureObservation(
        observation_id="fixture-proposal-0204-observation",
        input_admission=_negative_admission(raw_sha256),
        run_status=FixtureObservationRunStatus.FAILED,
        evaluation=None,
        resource_use=_resource_use(evaluator_invocations=0, storage_bytes=1_001),
        failure_class=FixtureObservationFailureClass.RESOURCE_BLOCKED,
        raw_output_artifacts=(
            FixtureRawOutputArtifact(
                stream=FixtureRawOutputStream.STDERR,
                artifact_sha256=raw_sha256,
            ),
        ),
    )
    receipt = build_fixture_experiment_receipt(
        plan,
        _evaluator(),
        observation,
        _manifest(),
        _code_identity(),
    )
    decision = decide_fixture_experiment(proposal, observation, receipt)

    assert receipt.failure_classification is PlanFailureCondition.RESOURCE_BUDGET_OVERRUN
    assert decision.state is ResearchDecisionState.BLOCKED


def test_manifest_identity_mismatch_fails_closed_before_receipt() -> None:
    result = _complete()
    observation = result.observation

    with pytest.raises(ValueError, match="code_sha"):
        build_fixture_experiment_receipt(
            _plan(),
            _evaluator(),
            observation,
            _manifest(code_sha="9" * 40),
            _code_identity(),
        )


def test_proposal_plan_identity_mismatch_fails_closed_at_execution() -> None:
    plan = _plan()
    policy = build_fixture_mutation_policy(plan)
    proposal = _proposal()
    object.__setattr__(proposal, "experiment_plan_sha256", "9" * 64)

    with pytest.raises(FixtureLoopError, match="proposal"):
        execute_fixture_proposal(
            plan,
            policy,
            _surface(),
            _evaluator(),
            proposal,
            _admission_for_proposal(_proposal()),
            resource_use=_resource_use(),
        )


def test_post_construction_loop_result_tamper_fails_closed() -> None:
    result = _complete()
    object.__setattr__(result, "fixture_only", False)

    with pytest.raises(FixtureLoopError, match="fixture_only"):
        result.semantic_dict()


def test_derived_proposal_cannot_override_snapshot_dispatch() -> None:
    trusted = _proposal()

    class DerivedProposal(FixtureExperimentProposal):
        def _validated_snapshot(self) -> FixtureExperimentProposal:
            return trusted

    derived = DerivedProposal(
        proposal_id=trusted.proposal_id,
        experiment_plan_sha256=trusted.experiment_plan_sha256,
        mutation_policy_sha256=trusted.mutation_policy_sha256,
        research_surface_sha256=trusted.research_surface_sha256,
        mutation_path=trusted.mutation_path,
        candidate=trusted.candidate,
    )

    with pytest.raises(FixtureLoopError, match="must be exact FixtureExperimentProposal"):
        derived.semantic_dict()


def test_derived_policy_is_rejected_before_trust_bearing_dispatch() -> None:
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

    with pytest.raises(FixtureLoopError, match="must be exact FixtureMutationPolicy"):
        propose_fixture_experiment(
            plan,
            derived,
            _surface(),
            proposal_id="fixture-proposal-0204",
            mutation_path=_MUTATION_PATH,
            parameter_values=(
                FixtureParameterValue(parameter_id="alpha", value=1),
                FixtureParameterValue(parameter_id="beta", value=2),
            ),
        )


def test_non_fixture_plan_shape_is_rejected() -> None:
    plan = _plan()
    search_identity = _objective().evaluator_identities[1]
    invalid = replace(
        plan,
        evaluator_identities=(search_identity,),
        evaluation_tiers=(EvaluationTier.SEARCH,),
        tier_allowances=(
            PlanTierAllowance(
                tier=EvaluationTier.SEARCH,
                max_queries=0,
                max_result_exposures=0,
                allowed_result_fields=(),
            ),
        ),
    )

    with pytest.raises(FixtureLoopError, match="Tier 0 DEVELOPMENT"):
        propose_fixture_experiment(
            invalid,
            build_fixture_mutation_policy(invalid),
            _surface(),
            proposal_id="fixture-proposal-0204",
            mutation_path=_MUTATION_PATH,
            parameter_values=(
                FixtureParameterValue(parameter_id="alpha", value=1),
                FixtureParameterValue(parameter_id="beta", value=2),
            ),
        )


def test_loop_exposes_no_campaign_update_or_promotion_authority() -> None:
    result = _complete()
    payload = result.to_dict()

    assert result.decision.state is not ResearchDecisionState.REPLICATE
    assert result.decision.state is not ResearchDecisionState.RETAIN_LEAD
    assert result.decision.can_authorize_promotion is False
    assert payload["can_update_campaign"] is False
    assert payload["can_authorize_model_promotion"] is False


def test_mrl_0206_metric_fabrication_cannot_reuse_canonical_receipt() -> None:
    result = _complete()
    evaluation = result.observation.evaluation
    assert evaluation is not None
    object.__setattr__(evaluation, "score", 0)

    with pytest.raises(FixtureLoopError, match="canonical revalidation"):
        decide_fixture_experiment(
            result.proposal,
            result.observation,
            result.receipt,
        )


def test_mrl_0206_modified_evaluator_cannot_build_valid_receipt() -> None:
    result = _complete()
    trusted = _evaluator()
    modified = FixtureEvaluator(
        evaluator_id=trusted.evaluator_id,
        metric_id=trusted.metric_id,
        target_values=(
            FixtureParameterValue(parameter_id="alpha", value=0),
            FixtureParameterValue(parameter_id="beta", value=0),
        ),
    )

    with pytest.raises(FixtureLoopError, match="evaluator artifact"):
        build_fixture_experiment_receipt(
            _plan(),
            modified,
            result.observation,
            _manifest(),
            _code_identity(),
        )


def test_mrl_0206_fixture_metrics_never_claim_sealed_or_promotion_authority() -> None:
    result = _complete()
    payload = result.to_dict()

    assert result.receipt.metric_artifacts[0].tier is EvaluationTier.DEVELOPMENT
    assert result.decision.can_authorize_promotion is False
    assert payload["non_evidence"] is True
    assert payload["can_update_campaign"] is False
    assert payload["can_authorize_real_execution"] is False
    assert payload["can_authorize_training"] is False
    assert payload["can_authorize_model_promotion"] is False
