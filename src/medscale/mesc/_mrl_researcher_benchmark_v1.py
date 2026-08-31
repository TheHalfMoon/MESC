"""Deterministic fixture-only researcher benchmark harness for MRL-0505.

The harness evaluates one exact canonical ``ResearchCampaign`` together with the exact
MRL-0501 portfolio frontier and MRL-0502..0504 branch-semantics view derived from that
campaign. It derives bounded researcher meta-metrics from canonical campaign state; it
does not execute an agent, model, tool, network call, training job, or real experiment.

The benchmark is intentionally non-authoritative. It can support later MRL-0506..0510
comparisons but cannot authorize real execution, training, promotion, deployment,
release, or clinical action.
"""

from __future__ import annotations

import enum
import weakref
from collections.abc import Callable
from dataclasses import dataclass

from medscale.mesc._mrl_campaign_branch_semantics_v1 import (
    CampaignBranchSemantics,
    CampaignBranchSemanticsError,
)
from medscale.mesc._mrl_campaign_portfolio_policy_v1 import (
    CampaignPortfolioFrontier,
    CampaignPortfolioPolicyError,
)
from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_procedure_transfer_test_v1 import (
    ProcedureTransferTestError,
    ProcedureTransferTestReport,
)
from medscale.mesc._mrl_research_campaign_v1 import (
    CampaignBranchOutcomeKind,
    CampaignNodeKind,
    CampaignReplicationRelation,
    ResearchCampaign,
    ResearchCampaignError,
)

__all__ = [
    "ResearcherBenchmarkArm",
    "ResearcherBenchmarkHarnessError",
    "ResearcherBenchmarkMetrics",
    "ResearcherBenchmarkRun",
    "build_researcher_benchmark_run",
]


class ResearcherBenchmarkHarnessError(ValueError):
    """Fail-closed validation error for the MRL-0505 benchmark harness."""


class ResearcherBenchmarkArm(enum.Enum):
    """Canonical researcher variants required by the MRL V1 benchmark."""

    STATELESS = "STATELESS"
    HISTORY_ONLY = "HISTORY_ONLY"
    ADMITTED_PROCEDURE_MEMORY = "ADMITTED_PROCEDURE_MEMORY"
    PORTFOLIO_TREE_SEARCH = "PORTFOLIO_TREE_SEARCH"


def _make_identity_registry() -> tuple[
    Callable[[object, str], None],
    Callable[[object, str], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: object, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise ResearcherBenchmarkHarnessError("benchmark construction identity already exists")
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: object, label: str) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ResearcherBenchmarkHarnessError(f"{label} construction identity is missing")
        return identity

    return store, load


_store_identity, _load_identity = _make_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ResearcherBenchmarkMetrics:
    """Derived researcher meta-metrics for one exact fixture campaign."""

    experiment_count: int
    hypothesis_count: int
    frontier_hypothesis_root_count: int
    replication_count: int
    validated_replicated_gain_count: int
    experiments_to_first_replicated_gain: int | None
    invalid_outcome_count: int
    terminal_failure_outcome_count: int
    repeated_known_failure_count: int
    known_failure_retry_count: int
    compute_unit_count: int
    evaluator_invocation_count: int
    storage_bytes: int
    procedure_transfer_attempt_count: int
    procedure_transfer_success_count: int

    def __post_init__(self) -> None:
        _validate_metrics(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> ResearcherBenchmarkMetrics:
        if type(self) is not ResearcherBenchmarkMetrics:
            raise ResearcherBenchmarkHarnessError(
                "metrics must be an exact ResearcherBenchmarkMetrics"
            )
        bound = _load_identity(self, "researcher benchmark metrics")
        _validate_metrics(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise ResearcherBenchmarkHarnessError(
                "researcher benchmark metrics changed after construction"
            )
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        rate = None
        if self.compute_unit_count:
            rate = {
                "numerator": self.validated_replicated_gain_count,
                "denominator": self.compute_unit_count,
            }
        return {
            "format": "MRL-RESEARCHER-BENCHMARK-METRICS-V1",
            "experiment_count": self.experiment_count,
            "hypothesis_count": self.hypothesis_count,
            "frontier_hypothesis_root_count": self.frontier_hypothesis_root_count,
            "replication_count": self.replication_count,
            "validated_replicated_gain_count": self.validated_replicated_gain_count,
            "experiments_to_first_replicated_gain": self.experiments_to_first_replicated_gain,
            "invalid_outcome_count": self.invalid_outcome_count,
            "terminal_failure_outcome_count": self.terminal_failure_outcome_count,
            "repeated_known_failure_count": self.repeated_known_failure_count,
            "known_failure_retry_count": self.known_failure_retry_count,
            "compute_unit_count": self.compute_unit_count,
            "validated_gain_per_compute_unit": rate,
            "evaluator_invocation_count": self.evaluator_invocation_count,
            "storage_bytes": self.storage_bytes,
            "procedure_transfer_attempt_count": self.procedure_transfer_attempt_count,
            "procedure_transfer_success_count": self.procedure_transfer_success_count,
            "fixture_only": True,
            "non_evidence": True,
        }

    def semantic_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ResearcherBenchmarkRun:
    """One construction-bound fixture benchmark run over exact canonical campaign state."""

    arm: ResearcherBenchmarkArm
    campaign: ResearchCampaign
    portfolio_frontier: CampaignPortfolioFrontier
    branch_semantics: CampaignBranchSemantics
    procedure_transfer_reports: tuple[ProcedureTransferTestReport, ...]
    metrics: ResearcherBenchmarkMetrics
    fixture_only: bool = True
    non_evidence: bool = True

    def __post_init__(self) -> None:
        _validate_run(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> ResearcherBenchmarkRun:
        if type(self) is not ResearcherBenchmarkRun:
            raise ResearcherBenchmarkHarnessError("run must be an exact ResearcherBenchmarkRun")
        bound = _load_identity(self, "researcher benchmark run")
        _validate_run(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise ResearcherBenchmarkHarnessError(
                "researcher benchmark run changed after construction"
            )
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        campaign = _validated_campaign(self.campaign)
        frontier = _validated_frontier(self.portfolio_frontier)
        semantics = _validated_branch_semantics(self.branch_semantics)
        reports = _validated_transfer_reports(self.procedure_transfer_reports)
        metrics = self.metrics._validated_snapshot()
        return {
            "format": "MRL-RESEARCHER-BENCHMARK-RUN-V1",
            "arm": self.arm.value,
            "campaign_sha256": campaign.content_sha256,
            "portfolio_frontier_sha256": frontier.content_sha256,
            "branch_semantics_sha256": semantics.content_sha256,
            "procedure_transfer_report_sha256s": [report.content_sha256 for report in reports],
            "metrics": metrics._semantic_dict_validated(),
            "fixture_only": self.fixture_only,
            "non_evidence": self.non_evidence,
            "can_execute_agent": False,
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data

    @property
    def can_execute_agent(self) -> bool:
        return False

    @property
    def can_authorize_real_execution(self) -> bool:
        return False

    @property
    def can_authorize_training(self) -> bool:
        return False

    @property
    def can_authorize_promotion(self) -> bool:
        return False


def build_researcher_benchmark_run(
    arm: ResearcherBenchmarkArm,
    campaign: ResearchCampaign,
    portfolio_frontier: CampaignPortfolioFrontier,
    branch_semantics: CampaignBranchSemantics,
    *,
    procedure_transfer_reports: tuple[ProcedureTransferTestReport, ...] = (),
) -> ResearcherBenchmarkRun:
    """Derive one fixture benchmark run without executing or trusting a research agent."""
    _require_exact_enum(arm, ResearcherBenchmarkArm, "arm")
    campaign_snapshot = _validated_campaign(campaign)
    frontier_snapshot = _validated_frontier(portfolio_frontier)
    semantics_snapshot = _validated_branch_semantics(branch_semantics)
    reports = _validated_transfer_reports(procedure_transfer_reports)

    if frontier_snapshot.campaign.content_sha256 != campaign_snapshot.content_sha256:
        raise ResearcherBenchmarkHarnessError(
            "portfolio frontier does not bind the exact benchmark campaign"
        )
    if semantics_snapshot.campaign.content_sha256 != campaign_snapshot.content_sha256:
        raise ResearcherBenchmarkHarnessError(
            "branch semantics do not bind the exact benchmark campaign"
        )
    if semantics_snapshot.portfolio_frontier.content_sha256 != frontier_snapshot.content_sha256:
        raise ResearcherBenchmarkHarnessError(
            "branch semantics do not bind the exact benchmark portfolio frontier"
        )

    metrics = _derive_metrics(
        campaign_snapshot,
        frontier_snapshot,
        semantics_snapshot,
        reports,
    )
    return ResearcherBenchmarkRun(
        arm=arm,
        campaign=campaign,
        portfolio_frontier=portfolio_frontier,
        branch_semantics=branch_semantics,
        procedure_transfer_reports=procedure_transfer_reports,
        metrics=metrics,
    )


def _derive_metrics(
    campaign: ResearchCampaign,
    frontier: CampaignPortfolioFrontier,
    semantics: CampaignBranchSemantics,
    reports: tuple[ProcedureTransferTestReport, ...],
) -> ResearcherBenchmarkMetrics:
    nodes = campaign.nodes
    resources = campaign.cumulative_resource_usage
    outcomes = campaign.branch_outcomes
    retained = set(campaign.retained_alternative_node_ids)
    negative_nodes = {item.terminal_node_id for item in outcomes}

    validated_relations = tuple(
        relation
        for relation in campaign.replications
        if relation.source_node_id in retained
        and relation.replica_node_id in retained
        and relation.source_node_id not in negative_nodes
        and relation.replica_node_id not in negative_nodes
    )

    return ResearcherBenchmarkMetrics(
        experiment_count=sum(node.kind is CampaignNodeKind.RECEIPT for node in nodes),
        hypothesis_count=sum(node.kind is CampaignNodeKind.HYPOTHESIS for node in nodes),
        frontier_hypothesis_root_count=_frontier_root_count(frontier),
        replication_count=len(campaign.replications),
        validated_replicated_gain_count=len(validated_relations),
        experiments_to_first_replicated_gain=_experiments_to_first_replicated_gain(
            campaign,
            validated_relations,
        ),
        invalid_outcome_count=sum(
            item.outcome is CampaignBranchOutcomeKind.INVALID for item in outcomes
        ),
        terminal_failure_outcome_count=sum(
            item.outcome
            in (
                CampaignBranchOutcomeKind.FAILED,
                CampaignBranchOutcomeKind.INVALID,
                CampaignBranchOutcomeKind.REJECTED,
            )
            for item in outcomes
        ),
        repeated_known_failure_count=semantics.repeated_known_failure_count,
        known_failure_retry_count=resources.known_failure_retries,
        compute_unit_count=resources.compute_seconds,
        evaluator_invocation_count=resources.evaluator_invocations,
        storage_bytes=resources.storage_bytes,
        procedure_transfer_attempt_count=len(reports),
        procedure_transfer_success_count=sum(report.all_cases_reproduced for report in reports),
    )


def _experiments_to_first_replicated_gain(
    campaign: ResearchCampaign,
    validated_relations: tuple[CampaignReplicationRelation, ...],
) -> int | None:
    if not validated_relations:
        return None
    relation_keys = {
        (relation.source_node_id, relation.replica_node_id) for relation in validated_relations
    }
    chain = _oldest_first_campaign_chain(campaign)
    for snapshot in chain:
        keys = {
            (relation.source_node_id, relation.replica_node_id)
            for relation in snapshot.replications
        }
        if relation_keys.intersection(keys):
            return sum(node.kind is CampaignNodeKind.RECEIPT for node in snapshot.nodes)
    raise ResearcherBenchmarkHarnessError(
        "validated replication relation is absent from canonical campaign history"
    )


def _oldest_first_campaign_chain(
    campaign: ResearchCampaign,
) -> tuple[ResearchCampaign, ...]:
    newest_to_oldest: list[ResearchCampaign] = []
    current: ResearchCampaign | None = campaign
    while current is not None:
        snapshot = _validated_campaign(current)
        newest_to_oldest.append(snapshot)
        current = snapshot.parent
    return tuple(reversed(newest_to_oldest))


def _frontier_root_count(frontier: CampaignPortfolioFrontier) -> int:
    roots = {root for entry in frontier.entries for root in entry.hypothesis_root_node_ids}
    return len(roots)


def _validate_run(run: ResearcherBenchmarkRun) -> None:
    _require_exact_enum(run.arm, ResearcherBenchmarkArm, "arm")
    if type(run.fixture_only) is not bool or run.fixture_only is not True:
        raise ResearcherBenchmarkHarnessError("fixture_only must be exact True")
    if type(run.non_evidence) is not bool or run.non_evidence is not True:
        raise ResearcherBenchmarkHarnessError("non_evidence must be exact True")
    campaign = _validated_campaign(run.campaign)
    frontier = _validated_frontier(run.portfolio_frontier)
    semantics = _validated_branch_semantics(run.branch_semantics)
    reports = _validated_transfer_reports(run.procedure_transfer_reports)
    if frontier.campaign.content_sha256 != campaign.content_sha256:
        raise ResearcherBenchmarkHarnessError(
            "portfolio frontier does not bind the exact benchmark campaign"
        )
    if semantics.campaign.content_sha256 != campaign.content_sha256:
        raise ResearcherBenchmarkHarnessError(
            "branch semantics do not bind the exact benchmark campaign"
        )
    if semantics.portfolio_frontier.content_sha256 != frontier.content_sha256:
        raise ResearcherBenchmarkHarnessError(
            "branch semantics do not bind the exact benchmark portfolio frontier"
        )
    expected = _derive_metrics(campaign, frontier, semantics, reports)
    if run.metrics.semantic_dict() != expected.semantic_dict():
        raise ResearcherBenchmarkHarnessError(
            "benchmark metrics do not match the exact canonical benchmark inputs"
        )


def _validate_metrics(metrics: ResearcherBenchmarkMetrics) -> None:
    for label, value in (
        ("experiment_count", metrics.experiment_count),
        ("hypothesis_count", metrics.hypothesis_count),
        ("frontier_hypothesis_root_count", metrics.frontier_hypothesis_root_count),
        ("replication_count", metrics.replication_count),
        ("validated_replicated_gain_count", metrics.validated_replicated_gain_count),
        ("invalid_outcome_count", metrics.invalid_outcome_count),
        ("terminal_failure_outcome_count", metrics.terminal_failure_outcome_count),
        ("repeated_known_failure_count", metrics.repeated_known_failure_count),
        ("known_failure_retry_count", metrics.known_failure_retry_count),
        ("compute_unit_count", metrics.compute_unit_count),
        ("evaluator_invocation_count", metrics.evaluator_invocation_count),
        ("storage_bytes", metrics.storage_bytes),
        ("procedure_transfer_attempt_count", metrics.procedure_transfer_attempt_count),
        ("procedure_transfer_success_count", metrics.procedure_transfer_success_count),
    ):
        _require_nonnegative_int(value, label)

    first_gain = metrics.experiments_to_first_replicated_gain
    if first_gain is not None:
        if type(first_gain) is not int or first_gain < 1:
            raise ResearcherBenchmarkHarnessError(
                "experiments_to_first_replicated_gain must be positive when present"
            )
        if first_gain > metrics.experiment_count:
            raise ResearcherBenchmarkHarnessError(
                "experiments_to_first_replicated_gain cannot exceed experiment_count"
            )
    if metrics.validated_replicated_gain_count > metrics.replication_count:
        raise ResearcherBenchmarkHarnessError(
            "validated replicated gains cannot exceed replication count"
        )
    if metrics.procedure_transfer_success_count > metrics.procedure_transfer_attempt_count:
        raise ResearcherBenchmarkHarnessError("procedure transfer successes cannot exceed attempts")


def _validated_campaign(campaign: ResearchCampaign) -> ResearchCampaign:
    if type(campaign) is not ResearchCampaign:
        raise ResearcherBenchmarkHarnessError("campaign must be an exact ResearchCampaign")
    try:
        return campaign._validated_snapshot()
    except ResearchCampaignError as exc:
        raise ResearcherBenchmarkHarnessError("campaign failed canonical revalidation") from exc


def _validated_frontier(
    frontier: CampaignPortfolioFrontier,
) -> CampaignPortfolioFrontier:
    if type(frontier) is not CampaignPortfolioFrontier:
        raise ResearcherBenchmarkHarnessError(
            "portfolio_frontier must be an exact CampaignPortfolioFrontier"
        )
    try:
        return frontier._validated_snapshot()
    except CampaignPortfolioPolicyError as exc:
        raise ResearcherBenchmarkHarnessError(
            "portfolio frontier failed canonical revalidation"
        ) from exc


def _validated_branch_semantics(
    semantics: CampaignBranchSemantics,
) -> CampaignBranchSemantics:
    if type(semantics) is not CampaignBranchSemantics:
        raise ResearcherBenchmarkHarnessError(
            "branch_semantics must be an exact CampaignBranchSemantics"
        )
    try:
        return semantics._validated_snapshot()
    except CampaignBranchSemanticsError as exc:
        raise ResearcherBenchmarkHarnessError(
            "branch semantics failed canonical revalidation"
        ) from exc


def _validated_transfer_reports(
    reports: tuple[ProcedureTransferTestReport, ...],
) -> tuple[ProcedureTransferTestReport, ...]:
    if type(reports) is not tuple:
        raise ResearcherBenchmarkHarnessError("procedure_transfer_reports must be an exact tuple")
    snapshots: list[ProcedureTransferTestReport] = []
    for report in reports:
        if type(report) is not ProcedureTransferTestReport:
            raise ResearcherBenchmarkHarnessError(
                "procedure_transfer_reports contains an invalid item type"
            )
        try:
            snapshots.append(report._validated_snapshot())
        except ProcedureTransferTestError as exc:
            raise ResearcherBenchmarkHarnessError(
                "procedure transfer report failed canonical revalidation"
            ) from exc
    hashes = tuple(report.content_sha256 for report in snapshots)
    if hashes != tuple(sorted(set(hashes))):
        raise ResearcherBenchmarkHarnessError(
            "procedure_transfer_reports must be unique and sorted by content identity"
        )
    return tuple(snapshots)


def _require_nonnegative_int(value: object, label: str) -> None:
    if type(value) is not int or value < 0:
        raise ResearcherBenchmarkHarnessError(f"{label} must be a non-negative exact int")


def _require_exact_enum(value: object, enum_type: type[enum.Enum], label: str) -> None:
    if type(value) is not enum_type:
        raise ResearcherBenchmarkHarnessError(f"{label} must be an exact {enum_type.__name__}")
