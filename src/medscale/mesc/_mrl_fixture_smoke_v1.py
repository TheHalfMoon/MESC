"""Deterministic fixture-only golden-path smoke scenario for public alignment Phase 6.

This module composes the existing MRL fixture contracts in memory. It performs no
filesystem writes, network access, model/data access, inference, training, GPU work,
promotion, release, deployment, or clinical action. Its output is fixture-only and
non-evidence by construction.
"""

from __future__ import annotations

import json
from typing import Final

from medscale.mesc._mrl_fixture_loop_v1 import (
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
    FixtureObservationResourceUse,
)
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.manifests import DatasetSnapshot, ExperimentManifest, RunnerClass, RunnerEnv
from medscale.reproducibility import canonical_json, content_hash

__all__ = ["build_fixture_smoke_payload", "run_fixture_smoke"]

_CONFIGURATION: Final[str] = canonical_json({"fixture": True, "mrl": "align-20-smoke"})
_DATASET: Final[DatasetSnapshot] = DatasetSnapshot("fixture-dataset", "1.0.0", "e" * 64)
_MODEL: Final[ModelRef] = ModelRef(
    model_id="fixture/model",
    revision="revision-001",
    quantization="none",
    backend="fixture",
)
_RUNNER: Final[RunnerEnv] = RunnerEnv(runner=RunnerClass.LOCAL, python="3.11", os_name="linux")
_RESULTS: Final[tuple[str, ...]] = ("tests/fixtures/mrl/results/fixture-experiment-001.json",)
_MUTATION_PATH: Final[str] = "tests/fixtures/mrl/candidates/candidate.json"


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


def _hypothesis(objective: ResearchObjectiveContract) -> ResearchHypothesis:
    return ResearchHypothesis(
        hypothesis_id="fixture-hypothesis",
        objective_sha256=objective.content_sha256,
        mechanism="A bounded fixture parameter assignment may satisfy the toy objective.",
        predicted_effects=("The fixture score increases under the frozen evaluator.",),
        predicted_failure_modes=("The bounded candidate may not satisfy the fixture target.",),
        falsification_criteria=("The frozen fixture evaluator reports a non-perfect score.",),
        evidence_refs=("fixture:align-20",),
        parent_hypothesis_ids=(),
        created_from_campaign_state_sha256="c" * 64,
    )


def _plan() -> ResearchExperimentPlan:
    objective = _objective()
    evaluator = _evaluator()
    return ResearchExperimentPlan(
        experiment_plan_id="fixture-plan-align-20",
        objective=objective,
        hypothesis=_hypothesis(objective),
        mutation_surfaces=(_MUTATION_PATH,),
        expected_manifest=ExpectedExperimentManifestBinding(
            experiment_id="fixture-experiment-align-20",
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
    return ExperimentManifest(
        experiment_id="fixture-experiment-align-20",
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
        reproduction="medscale mesc-fixture-smoke",
    )


def _admission_for_proposal(
    proposal_sha256: str,
    candidate_evaluation_sha256: str,
) -> ResearchInputAdmissionContract:
    permission = ResearchInputSourcePermission(
        permission_id="fixture-output-permission",
        source_artifact_sha256=candidate_evaluation_sha256,
        source_contract_sha256=proposal_sha256,
        classification=ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    return ResearchInputAdmissionContract(
        input_id="fixture-smoke-observation-input",
        classification_policy_sha256="b" * 64,
        classification=ResearchInputClassification.DETERMINISTIC_FIXTURE_OUTPUT,
        source_artifact_sha256=candidate_evaluation_sha256,
        source_contract_sha256=proposal_sha256,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        source_permission=permission,
    )


def run_fixture_smoke() -> FixtureLoopResult:
    """Run one fixed non-perfect fixture scenario entirely in memory."""

    plan = _plan()
    policy = build_fixture_mutation_policy(plan)
    surface = _surface()
    evaluator = _evaluator()
    proposal = propose_fixture_experiment(
        plan,
        policy,
        surface,
        proposal_id="fixture-proposal-align-20",
        mutation_path=_MUTATION_PATH,
        parameter_values=(
            FixtureParameterValue(parameter_id="alpha", value=1),
            FixtureParameterValue(parameter_id="beta", value=0),
        ),
    )
    evaluation = evaluate_fixture_candidate(surface, evaluator, proposal.candidate)
    result = complete_fixture_loop(
        plan,
        policy,
        surface,
        evaluator,
        proposal,
        _admission_for_proposal(proposal.content_sha256, evaluation.content_sha256),
        _manifest(),
        CodePatchIdentity(
            code_sha="1" * 40,
            tree_sha="2" * 40,
            patch_sha256="3" * 64,
        ),
        resource_use=FixtureObservationResourceUse(
            operation_count=1,
            evaluator_invocations=1,
            storage_bytes=0,
        ),
        diagnostics=(
            FixtureObservationDiagnostic(
                code="fixture-smoke",
                detail="Deterministic fixture-only plumbing qualification completed.",
            ),
        ),
    )
    if result.decision.state is not ResearchDecisionState.REJECT:
        raise RuntimeError("fixture smoke must deterministically end in REJECT")
    return result


def build_fixture_smoke_payload() -> dict[str, object]:
    """Return the canonical user-facing non-evidence smoke summary."""

    result = run_fixture_smoke()
    return {
        "format": "MESC-FIXTURE-SMOKE-V1",
        "proposal_sha256": result.proposal.content_sha256,
        "observation_sha256": result.observation.content_sha256,
        "receipt_sha256": result.receipt.content_sha256,
        "decision_sha256": result.decision.content_sha256,
        "result_sha256": result.content_sha256,
        "decision_state": result.decision.state.value,
        "fixture_only": True,
        "non_evidence": True,
        "filesystem_writes": False,
        "network_access": False,
        "model_execution": False,
        "training_authorized": False,
        "promotion_authorized": False,
        "release_authorized": False,
        "deployment_authorized": False,
        "clinical_authority": False,
    }
