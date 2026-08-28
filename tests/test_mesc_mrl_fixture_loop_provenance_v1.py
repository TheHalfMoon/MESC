"""Regression tests for MRL-0204 fixture-loop provenance boundaries."""

from __future__ import annotations

import json

import pytest

from medscale.mesc._mrl_fixture_loop_v1 import (
    FixtureExperimentProposal,
    FixtureLoopError,
    FixtureLoopResult,
    complete_fixture_loop,
    propose_fixture_experiment,
)
from medscale.mesc._mrl_fixture_mutation_policy_v1 import build_fixture_mutation_policy
from medscale.mesc._mrl_fixture_research_surface_v1 import (
    FixtureEvaluator,
    FixtureParameterDomain,
    FixtureParameterValue,
    FixtureResearchSurface,
    evaluate_fixture_candidate,
)
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
from medscale.mesc._mrl_structured_fixture_observation_v1 import FixtureObservationResourceUse
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.manifests import (
    DatasetSnapshot,
    ExperimentManifest,
    RunnerClass,
    RunnerEnv,
)
from medscale.reproducibility import canonical_json, content_hash

_CONFIGURATION = canonical_json({"fixture": True, "mrl": "0204-provenance"})
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
    """Return the exact deterministic evaluator used by the regression fixture."""
    return FixtureEvaluator(
        evaluator_id="fixture-eval",
        metric_id="fixture-score",
        target_values=(
            FixtureParameterValue(parameter_id="alpha", value=1),
            FixtureParameterValue(parameter_id="beta", value=2),
        ),
    )


def _surface(surface_id: str = "fixture-surface") -> FixtureResearchSurface:
    """Return one surface identity over the same frozen evaluator semantics."""
    return FixtureResearchSurface(
        surface_id=surface_id,
        parameter_domains=(
            FixtureParameterDomain(parameter_id="alpha", allowed_values=(0, 1)),
            FixtureParameterDomain(parameter_id="beta", allowed_values=(0, 2)),
        ),
        evaluator_sha256=_evaluator().content_sha256,
    )


def _objective() -> ResearchObjectiveContract:
    """Build the frozen objective envelope for the regression fixture."""
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
        adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=0, tier_2_queries=0),
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


def _plan() -> ResearchExperimentPlan:
    """Build the exact Tier 0 plan used by the regression fixture."""
    objective = _objective()
    evaluator = _evaluator()
    hypothesis = ResearchHypothesis(
        hypothesis_id="fixture-hypothesis",
        objective_sha256=objective.content_sha256,
        mechanism="A bounded fixture assignment may satisfy the toy objective.",
        predicted_effects=("The frozen fixture score increases.",),
        predicted_failure_modes=("The candidate may miss the fixture target.",),
        falsification_criteria=("The frozen evaluator reports a non-perfect score.",),
        evidence_refs=("fixture:evidence-0204",),
        parent_hypothesis_ids=(),
        created_from_campaign_state_sha256="c" * 64,
    )
    return ResearchExperimentPlan(
        experiment_plan_id="fixture-plan-0204",
        objective=objective,
        hypothesis=hypothesis,
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


def _manifest() -> ExperimentManifest:
    """Return a runtime manifest that exactly matches the frozen plan binding."""
    return ExperimentManifest(
        experiment_id="fixture-experiment-001",
        rq_refs=("RQ1",),
        configuration=_CONFIGURATION,
        datasets=(_DATASET,),
        model=_MODEL,
        model_tier=1,
        code_sha="1" * 40,
        seeds=(7,),
        runner=_RUNNER,
        started_at="2026-08-28T00:00:00+00:00",
        results_paths=_RESULTS,
        reproduction="uv run fixture-mrl-0204-provenance",
    )


def _proposal(
    plan: ResearchExperimentPlan,
    surface: FixtureResearchSurface,
) -> FixtureExperimentProposal:
    """Propose one perfect candidate on the supplied exact surface."""
    return propose_fixture_experiment(
        plan,
        build_fixture_mutation_policy(plan),
        surface,
        proposal_id="fixture-proposal-0204",
        mutation_path=_MUTATION_PATH,
        parameter_values=(
            FixtureParameterValue(parameter_id="alpha", value=1),
            FixtureParameterValue(parameter_id="beta", value=2),
        ),
    )


def _admission(
    proposal: FixtureExperimentProposal,
    surface: FixtureResearchSurface,
) -> ResearchInputAdmissionContract:
    """Admit only the exact deterministic evaluation produced by the proposal surface."""
    evaluation = evaluate_fixture_candidate(surface, _evaluator(), proposal.candidate)
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


def _complete() -> FixtureLoopResult:
    """Complete one valid MRL-0204 fixture loop for negative regression tests."""
    plan = _plan()
    surface = _surface()
    proposal = _proposal(plan, surface)
    return complete_fixture_loop(
        plan,
        build_fixture_mutation_policy(plan),
        surface,
        _evaluator(),
        proposal,
        _admission(proposal, surface),
        _manifest(),
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
    )


def test_proposal_constructor_rejects_candidate_surface_relabeling() -> None:
    """A candidate cannot be relabelled onto a different surface identity."""
    plan = _plan()
    proposal = _proposal(plan, _surface())

    with pytest.raises(FixtureLoopError, match="candidate does not bind the research surface"):
        FixtureExperimentProposal(
            proposal_id=proposal.proposal_id,
            experiment_plan_sha256=proposal.experiment_plan_sha256,
            mutation_policy_sha256=proposal.mutation_policy_sha256,
            research_surface_sha256="9" * 64,
            mutation_path=proposal.mutation_path,
            candidate=proposal.candidate,
        )


def test_loop_result_rejects_observation_from_different_valid_surface() -> None:
    """Hash-valid records from another surface cannot be spliced into the receipt chain."""
    result = _complete()
    plan = _plan()
    alternate_surface = _surface("fixture-surface-alt")
    alternate_proposal = _proposal(plan, alternate_surface)

    with pytest.raises(FixtureLoopError, match="observation does not bind.*research surface"):
        FixtureLoopResult(
            proposal=alternate_proposal,
            observation=result.observation,
            receipt=result.receipt,
            decision=result.decision,
        )


@pytest.mark.parametrize(
    "state",
    (ResearchDecisionState.REPLICATE, ResearchDecisionState.RETAIN_LEAD),
)
def test_loop_result_rejects_mrl_0205_decision_states(
    state: ResearchDecisionState,
) -> None:
    """Direct construction cannot publish replication policy owned by MRL-0205."""
    result = _complete()
    decision = ResearchDecision(
        receipt_sha256=result.receipt.content_sha256,
        evidence_sha256s=(result.observation.content_sha256,),
        state=state,
        reason="This state belongs to MRL-0205 and must fail closed here.",
    )

    with pytest.raises(FixtureLoopError, match="cannot emit MRL-0205 decision states"):
        FixtureLoopResult(
            proposal=result.proposal,
            observation=result.observation,
            receipt=result.receipt,
            decision=decision,
        )
