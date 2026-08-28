"""Fixture-only replication and retained-lead behavior for MRL-0205.

This module layers deterministic replication decisions and append-only campaign updates
on top of the canonically closed MRL-0204 fixture loop. It does not weaken or modify the
MRL-0204 result contract: ``FixtureLoopResult`` remains unable to emit ``REPLICATE`` or
``RETAIN_LEAD`` directly.

All behavior is pure and in-memory. It grants no filesystem, network, model, dataset,
GPU, inference, training, promotion, deployment, release, clinical, or budget-expansion
authority.
"""

from __future__ import annotations

from dataclasses import dataclass

from medscale.mesc._mrl_fixture_loop_v1 import FixtureLoopResult
from medscale.mesc._mrl_research_campaign_v1 import (
    CampaignBranchOutcome,
    CampaignBranchOutcomeKind,
    CampaignNode,
    CampaignNodeKind,
    CampaignReplicationRelation,
    CampaignResourceTotals,
    CampaignTierTotals,
    ResearchCampaign,
)
from medscale.mesc._mrl_research_decision_v1 import (
    ResearchDecision,
    ResearchDecisionState,
)
from medscale.mesc._mrl_research_experiment_receipt_v1 import (
    ObservedResourceUse,
    ResearchExperimentReceipt,
    TierAccounting,
)
from medscale.mesc._mrl_research_objective_v1 import (
    EvaluationTier,
    ResearchObjectiveContract,
    ResourceBudget,
)

__all__ = [
    "FixtureReplicationCycle",
    "FixtureReplicationError",
    "apply_fixture_replication",
    "assess_fixture_replication",
    "complete_fixture_replication_cycle",
    "request_fixture_replication",
    "start_fixture_campaign",
]


class FixtureReplicationError(ValueError):
    """Fail-closed validation error for MRL-0205 fixture replication behavior."""


@dataclass(frozen=True, slots=True)
class FixtureReplicationCycle:
    """Exact binding of one request, replica assessment, and campaign transition."""

    primary: FixtureLoopResult
    replication_decision: ResearchDecision
    replica: FixtureLoopResult
    retained_decision: ResearchDecision
    campaign: ResearchCampaign
    fixture_only: bool = True
    non_evidence: bool = True

    def __post_init__(self) -> None:
        _validate_cycle(self)

    def to_dict(self) -> dict[str, object]:
        """Return deterministic identity references and permanent non-authority flags."""
        primary = _snapshot_loop_result(self.primary, "primary")
        request = _snapshot_decision(self.replication_decision, "replication_decision")
        replica = _snapshot_loop_result(self.replica, "replica")
        outcome = _snapshot_decision(self.retained_decision, "retained_decision")
        campaign = _snapshot_campaign(self.campaign)
        _validate_replication_chain(primary, request, replica, outcome)
        _validate_campaign_contains_cycle(campaign, primary, request, replica, outcome)
        return {
            "format": "MRL-FIXTURE-REPLICATION-CYCLE-V1",
            "primary_result_sha256": primary.content_sha256,
            "replication_decision_sha256": request.content_sha256,
            "replica_result_sha256": replica.content_sha256,
            "retained_decision_sha256": outcome.content_sha256,
            "campaign_sha256": campaign.content_sha256,
            "retained": outcome.state is ResearchDecisionState.RETAIN_LEAD,
            "fixture_only": True,
            "non_evidence": True,
            "can_expand_budget": False,
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_model_promotion": False,
        }


def request_fixture_replication(primary: FixtureLoopResult) -> ResearchDecision:
    """Request one fixture replication only for an exact MRL-0204 evidence candidate."""
    source = _snapshot_loop_result(primary, "primary")
    if source.decision.state is not ResearchDecisionState.EVIDENCE_CANDIDATE:
        raise FixtureReplicationError(
            "fixture replication requires an MRL-0204 EVIDENCE_CANDIDATE source"
        )
    return ResearchDecision(
        receipt_sha256=source.receipt.content_sha256,
        evidence_sha256s=(source.observation.content_sha256,),
        state=ResearchDecisionState.REPLICATE,
        reason="Fixture evidence candidate requires an independent bounded replication.",
    )


def assess_fixture_replication(
    primary: FixtureLoopResult,
    replication_decision: ResearchDecision,
    replica: FixtureLoopResult,
) -> ResearchDecision:
    """Assess one distinct fixture replica without creating promotion authority."""
    source = _snapshot_loop_result(primary, "primary")
    request = _snapshot_decision(replication_decision, "replication_decision")
    repeated = _snapshot_loop_result(replica, "replica")
    _validate_replication_pair(source, request, repeated)

    state = repeated.decision.state
    if state is ResearchDecisionState.EVIDENCE_CANDIDATE:
        state = ResearchDecisionState.RETAIN_LEAD
        reason = "Independent fixture replication confirmed the retained lead."
    elif state is ResearchDecisionState.REJECT:
        reason = "Independent fixture replication did not confirm the retained lead."
    elif state is ResearchDecisionState.BLOCKED:
        reason = "Independent fixture replication was blocked by a frozen boundary."
    elif state is ResearchDecisionState.INVALID:
        reason = "Independent fixture replication was invalid under the frozen plan."
    else:
        raise FixtureReplicationError("replica contains an unsupported MRL-0204 decision state")

    evidence = tuple(
        sorted(
            {
                source.observation.content_sha256,
                repeated.observation.content_sha256,
            }
        )
    )
    if len(evidence) != 2:
        raise FixtureReplicationError("fixture replication requires two distinct observations")
    return ResearchDecision(
        receipt_sha256=repeated.receipt.content_sha256,
        evidence_sha256s=evidence,
        state=state,
        reason=reason,
    )


def start_fixture_campaign(
    campaign_id: str,
    primary: FixtureLoopResult,
) -> ResearchCampaign:
    """Create the first append-only fixture campaign snapshot from one MRL-0204 result."""
    source = _snapshot_loop_result(primary, "primary")
    plan = source.receipt.binding.plan
    objective = plan.objective
    nodes = _result_nodes(source)
    outcomes = _negative_outcomes_for_decision(
        source.decision,
        _decision_node_id(source.decision),
    )
    resources = _resource_totals_from_receipt(source.receipt)
    tiers = _tier_totals_from_receipt(source.receipt)
    _require_campaign_budget(objective, nodes, resources, tiers)
    return ResearchCampaign(
        campaign_id=campaign_id,
        objective_sha256=objective.content_sha256,
        parent=None,
        nodes=nodes,
        replications=(),
        retained_alternative_node_ids=(),
        branch_outcomes=outcomes,
        current_frontier_node_ids=(_decision_node_id(source.decision),),
        procedure_candidate_node_ids=(),
        cumulative_resource_usage=resources,
        cumulative_tier_usage=tiers,
    )


def apply_fixture_replication(
    campaign: ResearchCampaign,
    primary: FixtureLoopResult,
    replication_decision: ResearchDecision,
    replica: FixtureLoopResult,
    retained_decision: ResearchDecision,
) -> ResearchCampaign:
    """Append one exact replication branch and its assessment to a fixture campaign."""
    parent = _snapshot_campaign(campaign)
    source = _snapshot_loop_result(primary, "primary")
    request = _snapshot_decision(replication_decision, "replication_decision")
    repeated = _snapshot_loop_result(replica, "replica")
    outcome = _snapshot_decision(retained_decision, "retained_decision")
    _validate_replication_chain(source, request, repeated, outcome)
    _require_source_in_campaign(parent, source)

    objective = repeated.receipt.binding.plan.objective
    if parent.objective_sha256 != objective.content_sha256:
        raise FixtureReplicationError("replica objective does not match the campaign objective")

    nodes = list(parent.nodes)
    _append_node(
        nodes,
        CampaignNode(
            node_id=_decision_node_id(request),
            kind=CampaignNodeKind.DECISION,
            artifact_sha256=request.content_sha256,
            parent_node_ids=(_decision_node_id(source.decision),),
        ),
    )
    for node in _result_nodes(repeated):
        _append_node(nodes, node)
    _append_node(
        nodes,
        CampaignNode(
            node_id=_decision_node_id(outcome),
            kind=CampaignNodeKind.DECISION,
            artifact_sha256=outcome.content_sha256,
            parent_node_ids=(_decision_node_id(repeated.decision),),
        ),
    )
    next_nodes = tuple(sorted(nodes, key=lambda item: item.node_id))

    relation = CampaignReplicationRelation(
        source_node_id=_decision_node_id(source.decision),
        replica_node_id=_decision_node_id(repeated.decision),
        evidence_sha256s=outcome.evidence_sha256s,
    )
    replications = tuple(
        sorted(
            (*parent.replications, relation),
            key=lambda item: (item.source_node_id, item.replica_node_id),
        )
    )

    branch_outcomes = list(parent.branch_outcomes)
    branch_outcomes.extend(
        _negative_outcomes_for_decision(outcome, _decision_node_id(outcome))
    )
    next_outcomes = tuple(sorted(branch_outcomes, key=lambda item: item.terminal_node_id))

    retained = parent.retained_alternative_node_ids
    if outcome.state is ResearchDecisionState.RETAIN_LEAD:
        retained = tuple(
            sorted(
                set(
                    (
                        *retained,
                        _decision_node_id(source.decision),
                        _decision_node_id(repeated.decision),
                    )
                )
            )
        )

    resources = _add_resource_usage(
        parent.cumulative_resource_usage,
        repeated.receipt.observed_resource_use,
    )
    tiers = _add_tier_usage(parent.cumulative_tier_usage, repeated.receipt.tier_accounting)
    _require_campaign_budget(objective, next_nodes, resources, tiers)

    return ResearchCampaign(
        campaign_id=parent.campaign_id,
        objective_sha256=parent.objective_sha256,
        parent=parent,
        nodes=next_nodes,
        replications=replications,
        retained_alternative_node_ids=retained,
        branch_outcomes=next_outcomes,
        current_frontier_node_ids=(_decision_node_id(outcome),),
        procedure_candidate_node_ids=parent.procedure_candidate_node_ids,
        cumulative_resource_usage=resources,
        cumulative_tier_usage=tiers,
    )


def complete_fixture_replication_cycle(
    campaign: ResearchCampaign,
    primary: FixtureLoopResult,
    replica: FixtureLoopResult,
) -> FixtureReplicationCycle:
    """Request, assess, and append one bounded fixture replication cycle."""
    request = request_fixture_replication(primary)
    outcome = assess_fixture_replication(primary, request, replica)
    updated = apply_fixture_replication(campaign, primary, request, replica, outcome)
    return FixtureReplicationCycle(
        primary=primary,
        replication_decision=request,
        replica=replica,
        retained_decision=outcome,
        campaign=updated,
    )


def _validate_cycle(value: FixtureReplicationCycle) -> None:
    if type(value.fixture_only) is not bool or not value.fixture_only:
        raise FixtureReplicationError("fixture_only must remain true")
    if type(value.non_evidence) is not bool or not value.non_evidence:
        raise FixtureReplicationError("non_evidence must remain true")
    primary = _snapshot_loop_result(value.primary, "primary")
    request = _snapshot_decision(value.replication_decision, "replication_decision")
    replica = _snapshot_loop_result(value.replica, "replica")
    outcome = _snapshot_decision(value.retained_decision, "retained_decision")
    campaign = _snapshot_campaign(value.campaign)
    _validate_replication_chain(primary, request, replica, outcome)
    _validate_campaign_contains_cycle(campaign, primary, request, replica, outcome)


def _validate_replication_pair(
    primary: FixtureLoopResult,
    request: ResearchDecision,
    replica: FixtureLoopResult,
) -> None:
    if primary.decision.state is not ResearchDecisionState.EVIDENCE_CANDIDATE:
        raise FixtureReplicationError("replication source is not an EVIDENCE_CANDIDATE")
    if request.state is not ResearchDecisionState.REPLICATE:
        raise FixtureReplicationError("replication request must use REPLICATE")
    if request.receipt_sha256 != primary.receipt.content_sha256:
        raise FixtureReplicationError("replication request does not bind the source receipt")
    if request.evidence_sha256s != (primary.observation.content_sha256,):
        raise FixtureReplicationError("replication request does not bind the source observation")
    if replica.proposal.proposal_id == primary.proposal.proposal_id:
        raise FixtureReplicationError("replica proposal must have a distinct proposal_id")
    if replica.proposal.candidate.content_sha256 != primary.proposal.candidate.content_sha256:
        raise FixtureReplicationError("replica must evaluate the exact retained candidate")
    if replica.proposal.research_surface_sha256 != primary.proposal.research_surface_sha256:
        raise FixtureReplicationError("replica must use the same frozen fixture surface")

    source_plan = primary.receipt.binding.plan
    replica_plan = replica.receipt.binding.plan
    if replica_plan.objective.content_sha256 != source_plan.objective.content_sha256:
        raise FixtureReplicationError("replica must remain inside the same frozen objective")
    if replica_plan.hypothesis.content_sha256 != source_plan.hypothesis.content_sha256:
        raise FixtureReplicationError("replica must bind the same research hypothesis")
    if replica_plan.evaluator_identities != source_plan.evaluator_identities:
        raise FixtureReplicationError("replica must bind the same frozen evaluator identities")
    if replica.observation.content_sha256 == primary.observation.content_sha256:
        raise FixtureReplicationError("replica observation must be independently identified")


def _validate_replication_chain(
    primary: FixtureLoopResult,
    request: ResearchDecision,
    replica: FixtureLoopResult,
    outcome: ResearchDecision,
) -> None:
    _validate_replication_pair(primary, request, replica)
    expected = assess_fixture_replication(primary, request, replica)
    if outcome.content_sha256 != expected.content_sha256:
        raise FixtureReplicationError(
            "retained decision does not match the exact replica assessment"
        )


def _validate_campaign_contains_cycle(
    campaign: ResearchCampaign,
    primary: FixtureLoopResult,
    request: ResearchDecision,
    replica: FixtureLoopResult,
    outcome: ResearchDecision,
) -> None:
    by_id = {node.node_id: node for node in campaign.nodes}
    expected = (
        (_decision_node_id(primary.decision), primary.decision.content_sha256),
        (_decision_node_id(request), request.content_sha256),
        (_decision_node_id(replica.decision), replica.decision.content_sha256),
        (_decision_node_id(outcome), outcome.content_sha256),
    )
    for node_id, artifact_sha256 in expected:
        node = by_id.get(node_id)
        if node is None or node.artifact_sha256 != artifact_sha256:
            raise FixtureReplicationError("campaign does not contain the exact replication cycle")
    relation_key = (
        _decision_node_id(primary.decision),
        _decision_node_id(replica.decision),
    )
    if relation_key not in {
        (item.source_node_id, item.replica_node_id) for item in campaign.replications
    }:
        raise FixtureReplicationError("campaign is missing the exact replication relationship")


def _require_source_in_campaign(campaign: ResearchCampaign, primary: FixtureLoopResult) -> None:
    by_id = {node.node_id: node for node in campaign.nodes}
    for node in _result_nodes(primary):
        existing = by_id.get(node.node_id)
        if existing is None or existing != node:
            raise FixtureReplicationError(
                "campaign does not contain the exact primary result chain"
            )


def _result_nodes(result: FixtureLoopResult) -> tuple[CampaignNode, ...]:
    plan = result.receipt.binding.plan
    hypothesis_id = _artifact_node_id("hypothesis", plan.hypothesis.content_sha256)
    plan_id = _artifact_node_id("plan", plan.content_sha256)
    receipt_id = _artifact_node_id("receipt", result.receipt.content_sha256)
    decision_id = _decision_node_id(result.decision)
    nodes = (
        CampaignNode(
            node_id=hypothesis_id,
            kind=CampaignNodeKind.HYPOTHESIS,
            artifact_sha256=plan.hypothesis.content_sha256,
            parent_node_ids=(),
        ),
        CampaignNode(
            node_id=plan_id,
            kind=CampaignNodeKind.EXPERIMENT_PLAN,
            artifact_sha256=plan.content_sha256,
            parent_node_ids=(hypothesis_id,),
        ),
        CampaignNode(
            node_id=receipt_id,
            kind=CampaignNodeKind.RECEIPT,
            artifact_sha256=result.receipt.content_sha256,
            parent_node_ids=(plan_id,),
        ),
        CampaignNode(
            node_id=decision_id,
            kind=CampaignNodeKind.DECISION,
            artifact_sha256=result.decision.content_sha256,
            parent_node_ids=(receipt_id,),
        ),
    )
    return tuple(sorted(nodes, key=lambda item: item.node_id))


def _append_node(nodes: list[CampaignNode], candidate: CampaignNode) -> None:
    by_id = {node.node_id: node for node in nodes}
    existing = by_id.get(candidate.node_id)
    if existing is None:
        nodes.append(candidate)
        return
    if existing != candidate:
        raise FixtureReplicationError("campaign node id collides with different semantics")


def _negative_outcomes_for_decision(
    decision: ResearchDecision,
    node_id: str,
) -> tuple[CampaignBranchOutcome, ...]:
    if decision.state in (
        ResearchDecisionState.EVIDENCE_CANDIDATE,
        ResearchDecisionState.REPLICATE,
        ResearchDecisionState.RETAIN_LEAD,
    ):
        return ()
    if decision.state is ResearchDecisionState.REJECT:
        kind = CampaignBranchOutcomeKind.REJECTED
    elif decision.state is ResearchDecisionState.INVALID:
        kind = CampaignBranchOutcomeKind.INVALID
    elif decision.state is ResearchDecisionState.BLOCKED:
        kind = CampaignBranchOutcomeKind.FAILED
    else:
        raise FixtureReplicationError("unsupported decision state for campaign outcome")
    return (
        CampaignBranchOutcome(
            terminal_node_id=node_id,
            outcome=kind,
            evidence_sha256s=decision.evidence_sha256s,
            reason=decision.reason,
        ),
    )


def _resource_totals_from_receipt(receipt: ResearchExperimentReceipt) -> CampaignResourceTotals:
    usage = receipt.observed_resource_use
    return CampaignResourceTotals(
        wall_clock_seconds=usage.wall_clock_seconds,
        compute_seconds=_optional_zero(usage.compute_seconds),
        input_tokens=_optional_zero(usage.input_tokens),
        generated_tokens=_optional_zero(usage.generated_tokens),
        storage_bytes=usage.storage_bytes,
        monetary_cost_microunits=_optional_zero(usage.monetary_cost_microunits),
        retries=usage.retries,
        known_failure_retries=usage.known_failure_retries,
        evaluator_invocations=_optional_zero(usage.evaluator_invocations),
    )


def _add_resource_usage(
    current: CampaignResourceTotals,
    usage: ObservedResourceUse,
) -> CampaignResourceTotals:
    return CampaignResourceTotals(
        wall_clock_seconds=current.wall_clock_seconds + usage.wall_clock_seconds,
        compute_seconds=current.compute_seconds + _optional_zero(usage.compute_seconds),
        input_tokens=current.input_tokens + _optional_zero(usage.input_tokens),
        generated_tokens=current.generated_tokens + _optional_zero(usage.generated_tokens),
        storage_bytes=current.storage_bytes + usage.storage_bytes,
        monetary_cost_microunits=(
            current.monetary_cost_microunits + _optional_zero(usage.monetary_cost_microunits)
        ),
        retries=current.retries + usage.retries,
        known_failure_retries=current.known_failure_retries + usage.known_failure_retries,
        evaluator_invocations=(
            current.evaluator_invocations + _optional_zero(usage.evaluator_invocations)
        ),
    )


def _tier_totals_from_receipt(
    receipt: ResearchExperimentReceipt,
) -> tuple[CampaignTierTotals, ...]:
    return tuple(
        CampaignTierTotals(
            tier=item.tier,
            queries_used=item.queries_used,
            result_exposures_used=item.result_exposures_used,
        )
        for item in receipt.tier_accounting
    )


def _add_tier_usage(
    current: tuple[CampaignTierTotals, ...],
    added: tuple[TierAccounting, ...],
) -> tuple[CampaignTierTotals, ...]:
    totals = {
        item.tier: (item.queries_used, item.result_exposures_used)
        for item in current
    }
    for item in added:
        queries, exposures = totals.get(item.tier, (0, 0))
        totals[item.tier] = (
            queries + item.queries_used,
            exposures + item.result_exposures_used,
        )
    return tuple(
        CampaignTierTotals(
            tier=tier,
            queries_used=values[0],
            result_exposures_used=values[1],
        )
        for tier, values in sorted(totals.items(), key=lambda item: int(item[0]))
    )


def _require_campaign_budget(
    objective: ResearchObjectiveContract,
    nodes: tuple[CampaignNode, ...],
    resources: CampaignResourceTotals,
    tiers: tuple[CampaignTierTotals, ...],
) -> None:
    budget = objective.resource_budget
    _require_resource_budget(resources, budget)
    receipt_count = sum(node.kind is CampaignNodeKind.RECEIPT for node in nodes)
    if receipt_count > budget.max_experiments:
        raise FixtureReplicationError("fixture campaign exceeds max_experiments")

    tier_by_id = {item.tier: item for item in tiers}
    exposure_by_tier = {
        item.tier: item.max_exposures for item in objective.tier_result_exposure_policy
    }
    for tier, totals in tier_by_id.items():
        max_exposures = exposure_by_tier.get(tier)
        if max_exposures is None and totals.result_exposures_used:
            raise FixtureReplicationError(
                "fixture campaign exposes results on an unconfigured tier"
            )
        if max_exposures is not None and totals.result_exposures_used > max_exposures:
            raise FixtureReplicationError("fixture campaign exceeds frozen result-exposure budget")
        if tier is EvaluationTier.SEARCH:
            max_queries = objective.adaptive_query_budget.tier_1_queries
        elif tier is EvaluationTier.REPLICATION:
            max_queries = objective.adaptive_query_budget.tier_2_queries
        else:
            max_queries = 0
        if totals.queries_used > max_queries:
            raise FixtureReplicationError("fixture campaign exceeds frozen adaptive-query budget")


def _require_resource_budget(
    totals: CampaignResourceTotals,
    budget: ResourceBudget,
) -> None:
    _require_ceiling(totals.wall_clock_seconds, budget.wall_clock_seconds, "wall_clock_seconds")
    _require_optional_ceiling(totals.compute_seconds, budget.compute_seconds, "compute_seconds")
    _require_optional_ceiling(totals.input_tokens, budget.input_tokens, "input_tokens")
    _require_optional_ceiling(totals.generated_tokens, budget.generated_tokens, "generated_tokens")
    _require_ceiling(totals.storage_bytes, budget.storage_bytes, "storage_bytes")
    _require_optional_ceiling(
        totals.monetary_cost_microunits,
        budget.monetary_cost_microunits,
        "monetary_cost_microunits",
    )
    _require_ceiling(totals.retries, budget.retries, "retries")
    _require_ceiling(
        totals.known_failure_retries,
        budget.known_failure_retries,
        "known_failure_retries",
    )
    _require_optional_ceiling(
        totals.evaluator_invocations,
        budget.evaluator_invocations,
        "evaluator_invocations",
    )


def _require_optional_ceiling(value: int, ceiling: int | None, label: str) -> None:
    if ceiling is None:
        if value != 0:
            raise FixtureReplicationError(f"{label} is not applicable to the frozen objective")
        return
    _require_ceiling(value, ceiling, label)


def _require_ceiling(value: int, ceiling: int, label: str) -> None:
    if value > ceiling:
        raise FixtureReplicationError(f"fixture campaign exceeds frozen {label} budget")


def _optional_zero(value: int | None) -> int:
    return 0 if value is None else value


def _artifact_node_id(prefix: str, sha256: str) -> str:
    return f"{prefix}-{sha256[:16]}"


def _decision_node_id(decision: ResearchDecision) -> str:
    return _artifact_node_id("decision", decision.content_sha256)


def _snapshot_loop_result(value: FixtureLoopResult, label: str) -> FixtureLoopResult:
    if type(value) is not FixtureLoopResult:
        raise FixtureReplicationError(f"{label} must be an exact FixtureLoopResult")
    try:
        return FixtureLoopResult._validated_snapshot(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FixtureReplicationError(f"{label} failed canonical revalidation") from exc


def _snapshot_decision(value: ResearchDecision, label: str) -> ResearchDecision:
    if type(value) is not ResearchDecision:
        raise FixtureReplicationError(f"{label} must be an exact ResearchDecision")
    try:
        return ResearchDecision._validated_snapshot(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FixtureReplicationError(f"{label} failed canonical revalidation") from exc


def _snapshot_campaign(value: ResearchCampaign) -> ResearchCampaign:
    if type(value) is not ResearchCampaign:
        raise FixtureReplicationError("campaign must be an exact ResearchCampaign")
    try:
        return ResearchCampaign._validated_snapshot(value)
    except (AttributeError, TypeError, ValueError) as exc:
        raise FixtureReplicationError("campaign failed canonical revalidation") from exc
