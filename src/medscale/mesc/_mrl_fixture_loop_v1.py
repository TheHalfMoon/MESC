"""Deterministic fixture-only propose/run/receipt/decision loop for MRL-0204.

The loop composes existing canonical MRL contracts. It proposes one bounded in-memory
fixture candidate, evaluates it with the frozen fixture evaluator, records a structured
observation, builds the existing ResearchExperimentReceipt, and emits the existing
ResearchDecision. It does not update campaign state; replication and retained-lead
behavior remain owned by MRL-0205.

This module performs no filesystem writes, subprocess execution, network access, real
model/data access, GPU work, inference, training, promotion, deployment, release, or
clinical action and grants no such authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_experiment_manifest_binding_v1 import bind_experiment_manifest
from medscale.mesc._mrl_fixture_mutation_policy_v1 import (
    FixtureMutationPolicy,
    require_fixture_mutation_allowed,
)
from medscale.mesc._mrl_fixture_research_surface_v1 import (
    FixtureCandidate,
    FixtureEvaluation,
    FixtureEvaluator,
    FixtureParameterValue,
    FixtureResearchSurface,
    build_fixture_candidate,
    evaluate_fixture_candidate,
)
from medscale.mesc._mrl_research_decision_v1 import (
    ResearchDecision,
    ResearchDecisionState,
)
from medscale.mesc._mrl_research_experiment_plan_v1 import (
    PlanFailureCondition,
    ResearchExperimentPlan,
)
from medscale.mesc._mrl_research_experiment_receipt_v1 import (
    CodePatchIdentity,
    ContaminationLineageAudit,
    ContaminationLineageStatus,
    EvidenceFloorResult,
    MetricArtifactResult,
    ObservedResourceUse,
    ReproductionResult,
    ReproductionStatus,
    ResearchExperimentReceipt,
    TierAccounting,
)
from medscale.mesc._mrl_research_input_admission_v1 import (
    ResearchInputAdmissionContract,
)
from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    FloorComparator,
)
from medscale.mesc._mrl_structured_fixture_observation_v1 import (
    FixtureObservationDiagnostic,
    FixtureObservationFailureClass,
    FixtureObservationResourceUse,
    FixtureObservationRunStatus,
    FixtureRawOutputArtifact,
    StructuredFixtureObservation,
)
from medscale.modelkit.manifests import ExperimentManifest

__all__ = [
    "FixtureExperimentProposal",
    "FixtureLoopError",
    "FixtureLoopResult",
    "build_fixture_experiment_receipt",
    "complete_fixture_loop",
    "decide_fixture_experiment",
    "execute_fixture_proposal",
    "propose_fixture_experiment",
]

_DEVELOPMENT_EXPOSED_FIELDS: Final[tuple[str, ...]] = ("max_score", "score")


class FixtureLoopError(ValueError):
    """Fail-closed validation error for the MRL-0204 fixture loop."""


@dataclass(frozen=True, slots=True)
class FixtureExperimentProposal:
    """Content-addressed proposal for one allow-listed fixture candidate."""

    proposal_id: str
    experiment_plan_sha256: str
    mutation_policy_sha256: str
    research_surface_sha256: str
    mutation_path: str
    candidate: FixtureCandidate
    fixture_only: bool = True
    non_evidence: bool = True

    def __post_init__(self) -> None:
        _validate_proposal_local(self)

    def _validated_snapshot(self) -> FixtureExperimentProposal:
        _require_exact_type(self, FixtureExperimentProposal, "fixture_experiment_proposal")
        return FixtureExperimentProposal(
            proposal_id=self.proposal_id,
            experiment_plan_sha256=self.experiment_plan_sha256,
            mutation_policy_sha256=self.mutation_policy_sha256,
            research_surface_sha256=self.research_surface_sha256,
            mutation_path=self.mutation_path,
            candidate=_snapshot_candidate(self.candidate),
            fixture_only=self.fixture_only,
            non_evidence=self.non_evidence,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-FIXTURE-EXPERIMENT-PROPOSAL-V1",
            "proposal_id": self.proposal_id,
            "experiment_plan_sha256": self.experiment_plan_sha256,
            "mutation_policy_sha256": self.mutation_policy_sha256,
            "research_surface_sha256": self.research_surface_sha256,
            "mutation_path": self.mutation_path,
            "candidate_sha256": self.candidate.content_sha256,
            "fixture_only": self.fixture_only,
            "non_evidence": self.non_evidence,
            "can_apply_repository_mutation": False,
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = FixtureExperimentProposal._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        snapshot = FixtureExperimentProposal._validated_snapshot(self)
        return canonical_semantic_bytes(snapshot._semantic_dict_validated())

    @property
    def content_sha256(self) -> str:
        snapshot = FixtureExperimentProposal._validated_snapshot(self)
        return derive_content_sha256(snapshot._semantic_dict_validated())

    def to_dict(self) -> dict[str, object]:
        snapshot = FixtureExperimentProposal._validated_snapshot(self)
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data


@dataclass(frozen=True, slots=True)
class FixtureLoopResult:
    """Content-addressed binding of one completed fixture proposal and its records."""

    proposal: FixtureExperimentProposal
    observation: StructuredFixtureObservation
    receipt: ResearchExperimentReceipt
    decision: ResearchDecision
    fixture_only: bool = True
    non_evidence: bool = True

    def __post_init__(self) -> None:
        _validate_result(self)

    def _validated_snapshot(self) -> FixtureLoopResult:
        _require_exact_type(self, FixtureLoopResult, "fixture_loop_result")
        return FixtureLoopResult(
            proposal=_snapshot_proposal(self.proposal),
            observation=_snapshot_observation(self.observation),
            receipt=_snapshot_receipt(self.receipt),
            decision=_snapshot_decision(self.decision),
            fixture_only=self.fixture_only,
            non_evidence=self.non_evidence,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-FIXTURE-LOOP-RESULT-V1",
            "proposal_sha256": self.proposal.content_sha256,
            "observation_sha256": self.observation.content_sha256,
            "receipt_sha256": self.receipt.content_sha256,
            "decision_sha256": self.decision.content_sha256,
            "decision_state": self.decision.state.value,
            "fixture_only": self.fixture_only,
            "non_evidence": self.non_evidence,
            "can_update_campaign": False,
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = FixtureLoopResult._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        snapshot = FixtureLoopResult._validated_snapshot(self)
        return canonical_semantic_bytes(snapshot._semantic_dict_validated())

    @property
    def content_sha256(self) -> str:
        snapshot = FixtureLoopResult._validated_snapshot(self)
        return derive_content_sha256(snapshot._semantic_dict_validated())

    def to_dict(self) -> dict[str, object]:
        snapshot = FixtureLoopResult._validated_snapshot(self)
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def propose_fixture_experiment(
    plan: ResearchExperimentPlan,
    policy: FixtureMutationPolicy,
    surface: FixtureResearchSurface,
    *,
    proposal_id: str,
    mutation_path: str,
    parameter_values: tuple[FixtureParameterValue, ...],
) -> FixtureExperimentProposal:
    """Build one deterministic proposal after revalidating the frozen mutation envelope."""

    plan_snapshot = _snapshot_plan(plan)
    policy_snapshot = _snapshot_policy(policy)
    surface_snapshot = _snapshot_surface(surface)
    _require_fixture_plan_shape(plan_snapshot, surface_snapshot)
    require_fixture_mutation_allowed(plan_snapshot, policy_snapshot, mutation_path)
    candidate = build_fixture_candidate(surface_snapshot, parameter_values)
    return FixtureExperimentProposal(
        proposal_id=proposal_id,
        experiment_plan_sha256=plan_snapshot.content_sha256,
        mutation_policy_sha256=policy_snapshot.content_sha256,
        research_surface_sha256=surface_snapshot.content_sha256,
        mutation_path=mutation_path,
        candidate=candidate,
    )


def execute_fixture_proposal(
    plan: ResearchExperimentPlan,
    policy: FixtureMutationPolicy,
    surface: FixtureResearchSurface,
    evaluator: FixtureEvaluator,
    proposal: FixtureExperimentProposal,
    input_admission: ResearchInputAdmissionContract,
    *,
    resource_use: FixtureObservationResourceUse,
    raw_output_artifacts: tuple[FixtureRawOutputArtifact, ...] = (),
    diagnostics: tuple[FixtureObservationDiagnostic, ...] = (),
) -> StructuredFixtureObservation:
    """Evaluate one valid proposal entirely in memory and return a structured observation."""

    plan_snapshot = _snapshot_plan(plan)
    policy_snapshot = _snapshot_policy(policy)
    surface_snapshot = _snapshot_surface(surface)
    evaluator_snapshot = _snapshot_evaluator(evaluator)
    proposal_snapshot = _snapshot_proposal(proposal)
    _require_fixture_plan_shape(plan_snapshot, surface_snapshot)
    _require_proposal_bindings(
        proposal_snapshot,
        plan_snapshot,
        policy_snapshot,
        surface_snapshot,
    )
    require_fixture_mutation_allowed(
        plan_snapshot,
        policy_snapshot,
        proposal_snapshot.mutation_path,
    )
    if surface_snapshot.evaluator_sha256 != evaluator_snapshot.content_sha256:
        raise FixtureLoopError("fixture surface does not bind the supplied evaluator")

    evaluation = evaluate_fixture_candidate(
        surface_snapshot,
        evaluator_snapshot,
        proposal_snapshot.candidate,
    )
    return StructuredFixtureObservation(
        observation_id=f"{proposal_snapshot.proposal_id}-observation",
        input_admission=input_admission,
        run_status=FixtureObservationRunStatus.SUCCEEDED,
        evaluation=evaluation,
        resource_use=resource_use,
        failure_class=None,
        raw_output_artifacts=raw_output_artifacts,
        diagnostics=diagnostics,
    )


def build_fixture_experiment_receipt(
    plan: ResearchExperimentPlan,
    evaluator: FixtureEvaluator,
    observation: StructuredFixtureObservation,
    manifest: ExperimentManifest,
    code_identity: CodePatchIdentity,
) -> ResearchExperimentReceipt:
    """Translate one structured fixture observation into the canonical receipt contract."""

    plan_snapshot = _snapshot_plan(plan)
    evaluator_snapshot = _snapshot_evaluator(evaluator)
    observation_snapshot = _snapshot_observation(observation)
    _require_exact_type(manifest, ExperimentManifest, "experiment_manifest")
    _require_exact_type(code_identity, CodePatchIdentity, "code_identity")
    _require_fixture_plan_shape(plan_snapshot, None)

    binding = bind_experiment_manifest(plan_snapshot, manifest)
    metric_artifacts: tuple[MetricArtifactResult, ...] = ()
    guardrail_results: tuple[EvidenceFloorResult, ...] = ()
    failure_classification: PlanFailureCondition | None = None
    exposure_count = 0
    exposed_fields: tuple[str, ...] = ()

    if observation_snapshot.run_status is FixtureObservationRunStatus.SUCCEEDED:
        evaluation = observation_snapshot.evaluation
        if evaluation is None:
            raise FixtureLoopError("successful fixture observation is missing its evaluation")
        _require_evaluation_matches_plan(plan_snapshot, evaluator_snapshot, evaluation)
        metric_artifact = MetricArtifactResult(
            metric_id=evaluation.metric_id,
            evaluator_id=evaluator_snapshot.evaluator_id,
            evaluator_artifact_sha256=evaluator_snapshot.content_sha256,
            tier=EvaluationTier.DEVELOPMENT,
            artifact_sha256=evaluation.content_sha256,
        )
        metric_artifacts = (metric_artifact,)
        guardrail_results = tuple(
            EvidenceFloorResult(
                floor_id=floor.floor_id,
                metric_artifact_sha256=metric_artifact.artifact_sha256,
                passed=_fixture_floor_passed(
                    score=evaluation.score,
                    max_score=evaluation.max_score,
                    comparator=floor.comparator,
                    threshold_decimal=floor.threshold_decimal,
                ),
            )
            for floor in plan_snapshot.objective.hard_guardrails
        )
        exposure_count = 1
        exposed_fields = _DEVELOPMENT_EXPOSED_FIELDS
    else:
        failure_classification = _failure_condition_for_observation(observation_snapshot)
        if failure_classification not in plan_snapshot.failure_conditions:
            raise FixtureLoopError(
                "fixture observation failure is not frozen in the experiment plan"
            )

    raw_output_sha256s = tuple(
        sorted({item.artifact_sha256 for item in observation_snapshot.raw_output_artifacts})
    )
    observed_resources = ObservedResourceUse(
        wall_clock_seconds=0,
        compute_seconds=None,
        input_tokens=None,
        generated_tokens=None,
        storage_bytes=observation_snapshot.resource_use.storage_bytes,
        monetary_cost_microunits=None,
        retries=0,
        known_failure_retries=0,
        evaluator_invocations=observation_snapshot.resource_use.evaluator_invocations,
    )
    return ResearchExperimentReceipt(
        binding=binding,
        code_identity=code_identity,
        observed_resource_use=observed_resources,
        metric_artifacts=metric_artifacts,
        guardrail_results=guardrail_results,
        subgroup_results=(),
        failure_classification=failure_classification,
        contamination_lineage_audit=ContaminationLineageAudit(
            status=ContaminationLineageStatus.NOT_EVALUATED,
            artifact_sha256=None,
        ),
        reproduction=ReproductionResult(
            status=ReproductionStatus.NOT_ATTEMPTED,
            artifact_sha256=None,
        ),
        raw_output_artifact_sha256s=raw_output_sha256s,
        tier_accounting=(
            TierAccounting(
                tier=EvaluationTier.DEVELOPMENT,
                queries_used=0,
                result_exposures_used=exposure_count,
                exposed_result_fields=exposed_fields,
            ),
        ),
    )


def decide_fixture_experiment(
    proposal: FixtureExperimentProposal,
    observation: StructuredFixtureObservation,
    receipt: ResearchExperimentReceipt,
) -> ResearchDecision:
    """Emit a bounded MRL V1 decision without replication, retention, or promotion authority."""

    proposal_snapshot = _snapshot_proposal(proposal)
    observation_snapshot = _snapshot_observation(observation)
    receipt_snapshot = _snapshot_receipt(receipt)
    _require_receipt_chain(proposal_snapshot, observation_snapshot, receipt_snapshot)

    if observation_snapshot.run_status is FixtureObservationRunStatus.FAILED:
        if observation_snapshot.failure_class is FixtureObservationFailureClass.RESOURCE_BLOCKED:
            state = ResearchDecisionState.BLOCKED
            reason = "Fixture execution was blocked by the frozen resource boundary."
        else:
            state = ResearchDecisionState.INVALID
            reason = "Fixture execution failed or was invalid under the frozen plan."
    else:
        evaluation = observation_snapshot.evaluation
        if evaluation is None:
            raise FixtureLoopError("successful fixture observation is missing its evaluation")
        floors_passed = all(item.passed for item in receipt_snapshot.guardrail_results)
        if not floors_passed:
            state = ResearchDecisionState.REJECT
            reason = "Fixture result failed one or more frozen hard guardrails."
        elif evaluation.score == evaluation.max_score:
            state = ResearchDecisionState.EVIDENCE_CANDIDATE
            reason = "Fixture result satisfied the bounded objective and hard guardrails."
        else:
            state = ResearchDecisionState.REJECT
            reason = "Fixture result did not satisfy the bounded fixture objective."

    return ResearchDecision(
        receipt_sha256=receipt_snapshot.content_sha256,
        evidence_sha256s=(observation_snapshot.content_sha256,),
        state=state,
        reason=reason,
    )


def complete_fixture_loop(
    plan: ResearchExperimentPlan,
    policy: FixtureMutationPolicy,
    surface: FixtureResearchSurface,
    evaluator: FixtureEvaluator,
    proposal: FixtureExperimentProposal,
    input_admission: ResearchInputAdmissionContract,
    manifest: ExperimentManifest,
    code_identity: CodePatchIdentity,
    *,
    resource_use: FixtureObservationResourceUse,
    raw_output_artifacts: tuple[FixtureRawOutputArtifact, ...] = (),
    diagnostics: tuple[FixtureObservationDiagnostic, ...] = (),
) -> FixtureLoopResult:
    """Complete the MRL-0204 fixture path without campaign mutation."""

    observation = execute_fixture_proposal(
        plan,
        policy,
        surface,
        evaluator,
        proposal,
        input_admission,
        resource_use=resource_use,
        raw_output_artifacts=raw_output_artifacts,
        diagnostics=diagnostics,
    )
    receipt = build_fixture_experiment_receipt(
        plan,
        evaluator,
        observation,
        manifest,
        code_identity,
    )
    decision = decide_fixture_experiment(proposal, observation, receipt)
    return FixtureLoopResult(
        proposal=proposal,
        observation=observation,
        receipt=receipt,
        decision=decision,
    )


def _validate_proposal_local(proposal: FixtureExperimentProposal) -> None:
    _require_token(proposal.proposal_id, "proposal_id")
    _require_sha256(proposal.experiment_plan_sha256, "experiment_plan_sha256")
    _require_sha256(proposal.mutation_policy_sha256, "mutation_policy_sha256")
    _require_sha256(proposal.research_surface_sha256, "research_surface_sha256")
    if type(proposal.mutation_path) is not str or not proposal.mutation_path:
        raise FixtureLoopError("mutation_path must be a non-empty exact str")
    candidate = _snapshot_candidate(proposal.candidate)
    if candidate.surface_sha256 != proposal.research_surface_sha256:
        raise FixtureLoopError("fixture proposal candidate does not bind the research surface")
    _require_true(proposal.fixture_only, "fixture_only")
    _require_true(proposal.non_evidence, "non_evidence")


def _validate_result(result: FixtureLoopResult) -> None:
    _require_true(result.fixture_only, "fixture_only")
    _require_true(result.non_evidence, "non_evidence")
    proposal = _snapshot_proposal(result.proposal)
    observation = _snapshot_observation(result.observation)
    receipt = _snapshot_receipt(result.receipt)
    decision = _snapshot_decision(result.decision)
    _require_receipt_chain(proposal, observation, receipt)
    if decision.state in (
        ResearchDecisionState.REPLICATE,
        ResearchDecisionState.RETAIN_LEAD,
    ):
        raise FixtureLoopError("MRL-0204 fixture loop cannot emit MRL-0205 decision states")
    if decision.receipt_sha256 != receipt.content_sha256:
        raise FixtureLoopError("fixture decision does not bind the exact receipt")
    if decision.evidence_sha256s != (observation.content_sha256,):
        raise FixtureLoopError("fixture decision must bind only the structured observation")


def _require_proposal_bindings(
    proposal: FixtureExperimentProposal,
    plan: ResearchExperimentPlan,
    policy: FixtureMutationPolicy,
    surface: FixtureResearchSurface,
) -> None:
    if proposal.experiment_plan_sha256 != plan.content_sha256:
        raise FixtureLoopError("fixture proposal does not bind the supplied experiment plan")
    if proposal.mutation_policy_sha256 != policy.content_sha256:
        raise FixtureLoopError("fixture proposal does not bind the supplied mutation policy")
    if proposal.research_surface_sha256 != surface.content_sha256:
        raise FixtureLoopError("fixture proposal does not bind the supplied research surface")
    if proposal.candidate.surface_sha256 != surface.content_sha256:
        raise FixtureLoopError("fixture proposal candidate does not bind the research surface")


def _require_receipt_chain(
    proposal: FixtureExperimentProposal,
    observation: StructuredFixtureObservation,
    receipt: ResearchExperimentReceipt,
) -> None:
    if receipt.binding.plan.content_sha256 != proposal.experiment_plan_sha256:
        raise FixtureLoopError("fixture receipt does not bind the proposal experiment plan")
    if observation.run_status is FixtureObservationRunStatus.SUCCEEDED:
        evaluation = observation.evaluation
        if evaluation is None:
            raise FixtureLoopError("successful fixture observation is missing its evaluation")
        if evaluation.surface_sha256 != proposal.research_surface_sha256:
            raise FixtureLoopError(
                "fixture observation does not bind the proposal research surface"
            )
        if evaluation.candidate_sha256 != proposal.candidate.content_sha256:
            raise FixtureLoopError("fixture observation does not bind the proposal candidate")
        if len(receipt.metric_artifacts) != 1:
            raise FixtureLoopError(
                "successful fixture receipt must bind one fixture metric artifact"
            )
        metric_artifact = receipt.metric_artifacts[0]
        if metric_artifact.artifact_sha256 != evaluation.content_sha256:
            raise FixtureLoopError("fixture receipt does not bind the observation metric artifact")
        if metric_artifact.metric_id != evaluation.metric_id:
            raise FixtureLoopError("fixture receipt metric id does not match the observation")
        if metric_artifact.evaluator_artifact_sha256 != evaluation.evaluator_sha256:
            raise FixtureLoopError("fixture receipt evaluator does not match the observation")
    elif receipt.failure_classification is None:
        raise FixtureLoopError("failed fixture observation requires a failed canonical receipt")


def _require_fixture_plan_shape(
    plan: ResearchExperimentPlan,
    surface: FixtureResearchSurface | None,
) -> None:
    if plan.evaluation_tiers != (EvaluationTier.DEVELOPMENT,):
        raise FixtureLoopError("MRL-0204 fixture plan must use only Tier 0 DEVELOPMENT")
    if len(plan.tier_allowances) != 1:
        raise FixtureLoopError("MRL-0204 fixture plan requires one Tier 0 allowance")
    allowance = plan.tier_allowances[0]
    if allowance.tier is not EvaluationTier.DEVELOPMENT:
        raise FixtureLoopError("MRL-0204 fixture allowance must be Tier 0 DEVELOPMENT")
    if allowance.max_queries != 0:
        raise FixtureLoopError("MRL-0204 fixture loop cannot consume adaptive queries")
    if allowance.max_result_exposures != 1:
        raise FixtureLoopError("MRL-0204 fixture loop requires exactly one result exposure")
    if allowance.allowed_result_fields != _DEVELOPMENT_EXPOSED_FIELDS:
        raise FixtureLoopError("MRL-0204 fixture result fields must be max_score and score")
    if plan.objective.subgroup_floors:
        raise FixtureLoopError("MRL-0204 fixture loop does not implement subgroup evidence")

    metrics = tuple(
        metric
        for metric in plan.objective.evaluation_metrics
        if metric.tier is EvaluationTier.DEVELOPMENT
    )
    if len(metrics) != 1:
        raise FixtureLoopError("MRL-0204 fixture plan requires exactly one Tier 0 metric")
    metric = metrics[0]
    if not plan.objective.hard_guardrails:
        raise FixtureLoopError("MRL-0204 fixture plan requires at least one hard guardrail")
    if any(floor.metric_id != metric.metric_id for floor in plan.objective.hard_guardrails):
        raise FixtureLoopError("fixture hard guardrails must bind the Tier 0 fixture metric")
    if any(floor.comparator is not FloorComparator.GTE for floor in plan.objective.hard_guardrails):
        raise FixtureLoopError("MRL-0204 fixture hard guardrails must use GTE")
    if len(plan.evaluator_identities) != 1:
        raise FixtureLoopError("MRL-0204 fixture plan requires one exact evaluator identity")
    identity = plan.evaluator_identities[0]
    if identity.evaluator_id != metric.evaluator_id:
        raise FixtureLoopError("fixture metric does not bind the plan evaluator identity")
    if identity.tiers != (EvaluationTier.DEVELOPMENT,):
        raise FixtureLoopError("fixture evaluator identity must be Tier 0 DEVELOPMENT only")
    if surface is not None and surface.evaluator_sha256 != identity.artifact_sha256:
        raise FixtureLoopError("fixture surface evaluator identity does not match the plan")


def _require_evaluation_matches_plan(
    plan: ResearchExperimentPlan,
    evaluator: FixtureEvaluator,
    evaluation: FixtureEvaluation,
) -> None:
    _require_exact_type(evaluation, FixtureEvaluation, "fixture_evaluation")
    metric = next(
        metric
        for metric in plan.objective.evaluation_metrics
        if metric.tier is EvaluationTier.DEVELOPMENT
    )
    identity = plan.evaluator_identities[0]
    if evaluation.metric_id != metric.metric_id:
        raise FixtureLoopError("fixture evaluation metric does not match the frozen plan")
    if evaluator.evaluator_id != identity.evaluator_id:
        raise FixtureLoopError("fixture evaluator id does not match the frozen plan")
    if evaluator.content_sha256 != identity.artifact_sha256:
        raise FixtureLoopError("fixture evaluator artifact does not match the frozen plan")
    if evaluation.evaluator_sha256 != evaluator.content_sha256:
        raise FixtureLoopError("fixture evaluation does not bind the exact evaluator")


def _fixture_floor_passed(
    *,
    score: int,
    max_score: int,
    comparator: FloorComparator,
    threshold_decimal: str,
) -> bool:
    if comparator is not FloorComparator.GTE:
        raise FixtureLoopError("MRL-0204 fixture floors must use GTE")
    ratio = Decimal(score) / Decimal(max_score)
    return ratio >= Decimal(threshold_decimal)


def _failure_condition_for_observation(
    observation: StructuredFixtureObservation,
) -> PlanFailureCondition:
    failure = observation.failure_class
    if failure is FixtureObservationFailureClass.POLICY_REJECTED:
        return PlanFailureCondition.MUTATION_SCOPE_VIOLATION
    if failure is FixtureObservationFailureClass.RESOURCE_BLOCKED:
        return PlanFailureCondition.RESOURCE_BUDGET_OVERRUN
    if failure in (
        FixtureObservationFailureClass.EXECUTION_FAILED,
        FixtureObservationFailureClass.INVALID_RESULT,
    ):
        return PlanFailureCondition.EXECUTION_ERROR
    raise FixtureLoopError("failed fixture observation has no supported failure classification")


def _snapshot_plan(value: ResearchExperimentPlan) -> ResearchExperimentPlan:
    _require_exact_type(value, ResearchExperimentPlan, "research_experiment_plan")
    try:
        return ResearchExperimentPlan._validated_snapshot(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FixtureLoopError("research_experiment_plan failed canonical revalidation") from exc


def _snapshot_policy(value: FixtureMutationPolicy) -> FixtureMutationPolicy:
    _require_exact_type(value, FixtureMutationPolicy, "fixture_mutation_policy")
    try:
        return FixtureMutationPolicy._validated_snapshot(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FixtureLoopError("fixture_mutation_policy failed canonical revalidation") from exc


def _snapshot_surface(value: FixtureResearchSurface) -> FixtureResearchSurface:
    _require_exact_type(value, FixtureResearchSurface, "fixture_research_surface")
    try:
        return FixtureResearchSurface._validated_snapshot(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FixtureLoopError("fixture_research_surface failed canonical revalidation") from exc


def _snapshot_evaluator(value: FixtureEvaluator) -> FixtureEvaluator:
    _require_exact_type(value, FixtureEvaluator, "fixture_evaluator")
    try:
        return FixtureEvaluator._validated_snapshot(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FixtureLoopError("fixture_evaluator failed canonical revalidation") from exc


def _snapshot_candidate(value: FixtureCandidate) -> FixtureCandidate:
    _require_exact_type(value, FixtureCandidate, "fixture_candidate")
    try:
        return FixtureCandidate._validated_snapshot(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FixtureLoopError("fixture_candidate failed canonical revalidation") from exc


def _snapshot_proposal(value: FixtureExperimentProposal) -> FixtureExperimentProposal:
    _require_exact_type(value, FixtureExperimentProposal, "fixture_experiment_proposal")
    return FixtureExperimentProposal._validated_snapshot(value)


def _snapshot_observation(value: StructuredFixtureObservation) -> StructuredFixtureObservation:
    _require_exact_type(value, StructuredFixtureObservation, "structured_fixture_observation")
    try:
        return StructuredFixtureObservation._validated_snapshot(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FixtureLoopError(
            "structured_fixture_observation failed canonical revalidation"
        ) from exc


def _snapshot_receipt(value: ResearchExperimentReceipt) -> ResearchExperimentReceipt:
    _require_exact_type(value, ResearchExperimentReceipt, "research_experiment_receipt")
    try:
        return ResearchExperimentReceipt._validated_snapshot(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FixtureLoopError("research_experiment_receipt failed canonical revalidation") from exc


def _snapshot_decision(value: ResearchDecision) -> ResearchDecision:
    _require_exact_type(value, ResearchDecision, "research_decision")
    try:
        return ResearchDecision._validated_snapshot(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FixtureLoopError("research_decision failed canonical revalidation") from exc


def _require_token(value: str, label: str) -> None:
    if type(value) is not str or not value:
        raise FixtureLoopError(f"{label} must be a non-empty exact str")
    if value != value.strip() or any(char in value for char in "\x00\r\n\t"):
        raise FixtureLoopError(f"{label} must be canonical text")


def _require_sha256(value: str, label: str) -> None:
    _require_token(value, label)
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise FixtureLoopError(f"{label} must be 64 lowercase hex")


def _require_true(value: bool, label: str) -> None:
    if value is not True:
        raise FixtureLoopError(f"{label} must be exactly true")


def _require_exact_type(value: object, expected: type[object], label: str) -> None:
    if type(value) is not expected:
        raise FixtureLoopError(f"{label} must be exact {expected.__name__}")