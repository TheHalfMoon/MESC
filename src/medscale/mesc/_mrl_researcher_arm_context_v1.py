"""Context-bound fixture researcher benchmark arms for MRL-0506..0509.

The MRL-0505 harness owns measurement and derives metrics from canonical campaign state.
This module separately records the context surface visible to each required researcher
arm so benchmark labels cannot silently smuggle in stronger memory:

- stateless: no research-memory context;
- history-only: exact MRL-0401 campaign-history projection;
- admitted-procedure-memory: exact non-empty MRL-0408 admitted-procedure search index;
- portfolio/tree-search: exact MRL-0501 frontier plus MRL-0502..0504 branch semantics.

These artifacts are deterministic fixture benchmark attestations only. They do not execute
an agent and grant no model/data/network/GPU/training/promotion/deployment/release or
clinical authority.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from dataclasses import dataclass

from medscale.mesc._mrl_campaign_branch_semantics_v1 import (
    CampaignBranchSemantics,
    CampaignBranchSemanticsError,
)
from medscale.mesc._mrl_campaign_history_projection_v1 import (
    CampaignHistoryProjection,
    CampaignHistoryProjectionError,
)
from medscale.mesc._mrl_campaign_portfolio_policy_v1 import (
    CampaignPortfolioFrontier,
    CampaignPortfolioPolicyError,
)
from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_procedure_search_index_v1 import (
    ProcedureSearchIndex,
    ProcedureSearchIndexError,
)
from medscale.mesc._mrl_researcher_benchmark_v1 import (
    ResearcherBenchmarkArm,
    ResearcherBenchmarkHarnessError,
    ResearcherBenchmarkRun,
)

__all__ = [
    "ResearcherArmContext",
    "ResearcherArmContextError",
    "build_history_only_researcher_context",
    "build_portfolio_tree_search_researcher_context",
    "build_procedure_memory_researcher_context",
    "build_stateless_researcher_context",
]


class ResearcherArmContextError(ValueError):
    """Fail-closed validation error for MRL-0506..0509 context attestations."""


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
            raise ResearcherArmContextError("researcher arm context identity already exists")
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: object, label: str) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise ResearcherArmContextError(f"{label} construction identity is missing")
        return identity

    return store, load


_store_identity, _load_identity = _make_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ResearcherArmContext:
    """One exact benchmark run plus only the memory context allowed for its arm."""

    benchmark_run: ResearcherBenchmarkRun
    history_projection: CampaignHistoryProjection | None = None
    procedure_search_index: ProcedureSearchIndex | None = None
    portfolio_frontier: CampaignPortfolioFrontier | None = None
    branch_semantics: CampaignBranchSemantics | None = None
    fixture_only: bool = True
    non_evidence: bool = True

    def __post_init__(self) -> None:
        _validate_context(self)
        _store_identity(self, derive_content_sha256(self._semantic_dict_validated()))

    def _validated_snapshot(self) -> ResearcherArmContext:
        if type(self) is not ResearcherArmContext:
            raise ResearcherArmContextError("context must be an exact ResearcherArmContext")
        bound = _load_identity(self, "researcher arm context")
        _validate_context(self)
        current = derive_content_sha256(self._semantic_dict_validated())
        if current != bound:
            raise ResearcherArmContextError("researcher arm context changed after construction")
        return self

    def _semantic_dict_validated(self) -> dict[str, object]:
        run = _validated_run(self.benchmark_run)
        history = _validated_history_optional(self.history_projection)
        procedure_index = _validated_index_optional(self.procedure_search_index)
        frontier = _validated_frontier_optional(self.portfolio_frontier)
        semantics = _validated_semantics_optional(self.branch_semantics)
        return {
            "format": "MRL-RESEARCHER-ARM-CONTEXT-V1",
            "arm": run.arm.value,
            "benchmark_run_sha256": run.content_sha256,
            "researcher_visible_context": _visible_context_labels(run.arm),
            "history_projection_sha256": (None if history is None else history.content_sha256),
            "procedure_search_index_sha256": (
                None if procedure_index is None else procedure_index.content_sha256
            ),
            "portfolio_frontier_sha256": (None if frontier is None else frontier.content_sha256),
            "branch_semantics_sha256": (None if semantics is None else semantics.content_sha256),
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


def build_stateless_researcher_context(
    benchmark_run: ResearcherBenchmarkRun,
) -> ResearcherArmContext:
    """Build MRL-0506 with no researcher-visible research-memory artifacts."""
    _require_run_arm(benchmark_run, ResearcherBenchmarkArm.STATELESS)
    return ResearcherArmContext(benchmark_run=benchmark_run)


def build_history_only_researcher_context(
    benchmark_run: ResearcherBenchmarkRun,
    history_projection: CampaignHistoryProjection,
) -> ResearcherArmContext:
    """Build MRL-0507 with only exact campaign-history memory visible."""
    run = _require_run_arm(benchmark_run, ResearcherBenchmarkArm.HISTORY_ONLY)
    history = _validated_history(history_projection)
    if history.latest_campaign_sha256 != run.campaign.content_sha256:
        raise ResearcherArmContextError(
            "history projection does not terminate at the exact benchmark campaign"
        )
    return ResearcherArmContext(
        benchmark_run=benchmark_run,
        history_projection=history_projection,
    )


def build_procedure_memory_researcher_context(
    benchmark_run: ResearcherBenchmarkRun,
    procedure_search_index: ProcedureSearchIndex,
) -> ResearcherArmContext:
    """Build MRL-0508 with only an exact admitted-procedure search index visible."""
    _require_run_arm(
        benchmark_run,
        ResearcherBenchmarkArm.ADMITTED_PROCEDURE_MEMORY,
    )
    index = _validated_index(procedure_search_index)
    if not index.entries:
        raise ResearcherArmContextError(
            "admitted-procedure-memory benchmark requires a non-empty admitted index"
        )
    return ResearcherArmContext(
        benchmark_run=benchmark_run,
        procedure_search_index=procedure_search_index,
    )


def build_portfolio_tree_search_researcher_context(
    benchmark_run: ResearcherBenchmarkRun,
    portfolio_frontier: CampaignPortfolioFrontier,
    branch_semantics: CampaignBranchSemantics,
) -> ResearcherArmContext:
    """Build MRL-0509 with only exact portfolio/tree-search state visible."""
    run = _require_run_arm(
        benchmark_run,
        ResearcherBenchmarkArm.PORTFOLIO_TREE_SEARCH,
    )
    frontier = _validated_frontier(portfolio_frontier)
    semantics = _validated_semantics(branch_semantics)
    if frontier.content_sha256 != run.portfolio_frontier.content_sha256:
        raise ResearcherArmContextError(
            "portfolio context does not bind the benchmark run frontier"
        )
    if semantics.content_sha256 != run.branch_semantics.content_sha256:
        raise ResearcherArmContextError(
            "portfolio context does not bind the benchmark run branch semantics"
        )
    return ResearcherArmContext(
        benchmark_run=benchmark_run,
        portfolio_frontier=portfolio_frontier,
        branch_semantics=branch_semantics,
    )


def _validate_context(context: ResearcherArmContext) -> None:
    run = _validated_run(context.benchmark_run)
    if type(context.fixture_only) is not bool or context.fixture_only is not True:
        raise ResearcherArmContextError("fixture_only must be exact True")
    if type(context.non_evidence) is not bool or context.non_evidence is not True:
        raise ResearcherArmContextError("non_evidence must be exact True")

    history = _validated_history_optional(context.history_projection)
    procedure_index = _validated_index_optional(context.procedure_search_index)
    frontier = _validated_frontier_optional(context.portfolio_frontier)
    semantics = _validated_semantics_optional(context.branch_semantics)

    if run.arm is ResearcherBenchmarkArm.STATELESS:
        if any(value is not None for value in (history, procedure_index, frontier, semantics)):
            raise ResearcherArmContextError(
                "stateless researcher cannot receive research-memory context"
            )
        return

    if run.arm is ResearcherBenchmarkArm.HISTORY_ONLY:
        if history is None or any(
            value is not None for value in (procedure_index, frontier, semantics)
        ):
            raise ResearcherArmContextError(
                "history-only researcher requires exactly campaign-history context"
            )
        if history.latest_campaign_sha256 != run.campaign.content_sha256:
            raise ResearcherArmContextError(
                "history projection does not terminate at the exact benchmark campaign"
            )
        return

    if run.arm is ResearcherBenchmarkArm.ADMITTED_PROCEDURE_MEMORY:
        if procedure_index is None or any(
            value is not None for value in (history, frontier, semantics)
        ):
            raise ResearcherArmContextError(
                "procedure-memory researcher requires exactly admitted procedure index context"
            )
        if not procedure_index.entries:
            raise ResearcherArmContextError(
                "admitted-procedure-memory benchmark requires a non-empty admitted index"
            )
        return

    if run.arm is ResearcherBenchmarkArm.PORTFOLIO_TREE_SEARCH:
        if (
            frontier is None
            or semantics is None
            or history is not None
            or procedure_index is not None
        ):
            raise ResearcherArmContextError(
                "portfolio researcher requires exactly frontier and branch-semantics context"
            )
        if frontier.content_sha256 != run.portfolio_frontier.content_sha256:
            raise ResearcherArmContextError(
                "portfolio context does not bind the benchmark run frontier"
            )
        if semantics.content_sha256 != run.branch_semantics.content_sha256:
            raise ResearcherArmContextError(
                "portfolio context does not bind the benchmark run branch semantics"
            )
        return

    raise ResearcherArmContextError("unsupported researcher benchmark arm")


def _visible_context_labels(arm: ResearcherBenchmarkArm) -> list[str]:
    if arm is ResearcherBenchmarkArm.STATELESS:
        return []
    if arm is ResearcherBenchmarkArm.HISTORY_ONLY:
        return ["CAMPAIGN_HISTORY"]
    if arm is ResearcherBenchmarkArm.ADMITTED_PROCEDURE_MEMORY:
        return ["ADMITTED_PROCEDURE_INDEX"]
    if arm is ResearcherBenchmarkArm.PORTFOLIO_TREE_SEARCH:
        return ["PORTFOLIO_FRONTIER", "BRANCH_SEMANTICS"]
    raise ResearcherArmContextError("unsupported researcher benchmark arm")


def _require_run_arm(
    run: ResearcherBenchmarkRun,
    expected: ResearcherBenchmarkArm,
) -> ResearcherBenchmarkRun:
    snapshot = _validated_run(run)
    if snapshot.arm is not expected:
        raise ResearcherArmContextError(f"benchmark run arm must be {expected.value}")
    return snapshot


def _validated_run(run: ResearcherBenchmarkRun) -> ResearcherBenchmarkRun:
    if type(run) is not ResearcherBenchmarkRun:
        raise ResearcherArmContextError("benchmark_run has an invalid type")
    try:
        return run._validated_snapshot()
    except ResearcherBenchmarkHarnessError as exc:
        raise ResearcherArmContextError("benchmark run failed canonical revalidation") from exc


def _validated_history(value: CampaignHistoryProjection) -> CampaignHistoryProjection:
    if type(value) is not CampaignHistoryProjection:
        raise ResearcherArmContextError("history_projection has an invalid type")
    try:
        return value._validated_snapshot()
    except CampaignHistoryProjectionError as exc:
        raise ResearcherArmContextError("history projection failed canonical revalidation") from exc


def _validated_history_optional(
    value: CampaignHistoryProjection | None,
) -> CampaignHistoryProjection | None:
    return None if value is None else _validated_history(value)


def _validated_index(value: ProcedureSearchIndex) -> ProcedureSearchIndex:
    if type(value) is not ProcedureSearchIndex:
        raise ResearcherArmContextError("procedure_search_index has an invalid type")
    try:
        return value._validated_snapshot()
    except ProcedureSearchIndexError as exc:
        raise ResearcherArmContextError(
            "procedure search index failed canonical revalidation"
        ) from exc


def _validated_index_optional(
    value: ProcedureSearchIndex | None,
) -> ProcedureSearchIndex | None:
    return None if value is None else _validated_index(value)


def _validated_frontier(
    value: CampaignPortfolioFrontier,
) -> CampaignPortfolioFrontier:
    if type(value) is not CampaignPortfolioFrontier:
        raise ResearcherArmContextError("portfolio_frontier has an invalid type")
    try:
        return value._validated_snapshot()
    except CampaignPortfolioPolicyError as exc:
        raise ResearcherArmContextError("portfolio frontier failed canonical revalidation") from exc


def _validated_frontier_optional(
    value: CampaignPortfolioFrontier | None,
) -> CampaignPortfolioFrontier | None:
    return None if value is None else _validated_frontier(value)


def _validated_semantics(value: CampaignBranchSemantics) -> CampaignBranchSemantics:
    if type(value) is not CampaignBranchSemantics:
        raise ResearcherArmContextError("branch_semantics has an invalid type")
    try:
        return value._validated_snapshot()
    except CampaignBranchSemanticsError as exc:
        raise ResearcherArmContextError("branch semantics failed canonical revalidation") from exc


def _validated_semantics_optional(
    value: CampaignBranchSemantics | None,
) -> CampaignBranchSemantics | None:
    return None if value is None else _validated_semantics(value)
