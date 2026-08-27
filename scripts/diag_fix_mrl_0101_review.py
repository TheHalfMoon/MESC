from __future__ import annotations

from pathlib import Path

IMPL = Path("src/medscale/mesc/_mrl_research_objective_v1.py")
TEST = Path("tests/test_mesc_mrl_research_objective_v1.py")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return text.replace(old, new, 1)


impl = IMPL.read_text(encoding="utf-8")

impl = replace_once(
    impl,
    '''__all__ = [
    "AdaptiveQueryBudget",
    "BudgetExhaustionDisposition",
    "EvaluationTier",
    "EvaluationTierPolicy",
    "EvaluatorIdentity",
    "EvidenceFloor",
    "FloorComparator",
    "MetricContract",
    "MetricDirection",
    "ResearchObjectiveContract",
    "ResearchObjectiveContractError",
    "ResourceBudget",
    "TierResultExposure",
]
''',
    '''__all__ = [
    "AdaptiveEvaluationControls",
    "AdaptiveInvalidationRule",
    "AdaptiveQueryBudget",
    "AdaptiveStoppingRule",
    "BudgetExhaustionDisposition",
    "EvaluationTier",
    "EvaluationTierPolicy",
    "EvaluatorIdentity",
    "EvidenceFloor",
    "FloorComparator",
    "MetricContract",
    "MetricDirection",
    "RepeatedEvaluationPolicy",
    "ResearchObjectiveContract",
    "ResearchObjectiveContractError",
    "ResourceBudget",
    "TierResultExposure",
]
''',
    "__all__",
)

impl = replace_once(
    impl,
    '''_RESEARCH_PROGRAM_REF: Final = re.compile(
    r"^(?:RQ[1-7]|(?:MESC|MCRL|ARABIC|AMGE|OMNI|MRL)-RQ-[0-9]{4})$"
)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
''',
    '''_ACCEPTED_RESEARCH_PROGRAM_REFS: Final[frozenset[str]] = frozenset(
    {"RQ1", "RQ2", "RQ3", "RQ4", "RQ5", "RQ6", "RQ7"}
)
_SAFE_MUTATION_ROOTS: Final[tuple[str, ...]] = (
    "experiments/",
    "research/experiments/",
    "tests/fixtures/mrl/",
)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
''',
    "research ref constants",
)

impl = replace_once(
    impl,
    '''class BudgetExhaustionDisposition(enum.Enum):
    BLOCKED = "BLOCKED"


class EvaluationTier(enum.IntEnum):
''',
    '''class BudgetExhaustionDisposition(enum.Enum):
    BLOCKED = "BLOCKED"


class RepeatedEvaluationPolicy(enum.Enum):
    FORBIDDEN = "FORBIDDEN"
    PERMITTED_WITHIN_FROZEN_BUDGET = "PERMITTED_WITHIN_FROZEN_BUDGET"


class AdaptiveStoppingRule(enum.Enum):
    ADAPTIVE_QUERY_BUDGET_EXHAUSTED = "ADAPTIVE_QUERY_BUDGET_EXHAUSTED"
    EXTERNAL_GOVERNANCE_STOP = "EXTERNAL_GOVERNANCE_STOP"
    OBJECTIVE_INVALIDATED = "OBJECTIVE_INVALIDATED"
    RESOURCE_BUDGET_EXHAUSTED = "RESOURCE_BUDGET_EXHAUSTED"
    RESULT_EXPOSURE_BUDGET_EXHAUSTED = "RESULT_EXPOSURE_BUDGET_EXHAUSTED"


class AdaptiveInvalidationRule(enum.Enum):
    EVALUATOR_IDENTITY_CHANGED = "EVALUATOR_IDENTITY_CHANGED"
    LINEAGE_OR_CONTAMINATION_FAILURE = "LINEAGE_OR_CONTAMINATION_FAILURE"
    OBJECTIVE_SEMANTICS_CHANGED = "OBJECTIVE_SEMANTICS_CHANGED"
    PROTECTED_SURFACE_MUTATION_ATTEMPT = "PROTECTED_SURFACE_MUTATION_ATTEMPT"
    SEALED_BOUNDARY_BREACH = "SEALED_BOUNDARY_BREACH"


class EvaluationTier(enum.IntEnum):
''',
    "adaptive enums",
)

impl = replace_once(
    impl,
    '''    def to_dict(self) -> dict[str, int]:
        return {
            "tier_1_queries": self.tier_1_queries,
            "tier_2_queries": self.tier_2_queries,
        }


@dataclass(frozen=True, slots=True)
class EvaluationTierPolicy:
''',
    '''    def to_dict(self) -> dict[str, int]:
        return {
            "tier_1_queries": self.tier_1_queries,
            "tier_2_queries": self.tier_2_queries,
        }


@dataclass(frozen=True, slots=True)
class AdaptiveEvaluationControls:
    """Frozen repeated-evaluation, stopping, and invalidation semantics."""

    repeated_candidate_evaluation: RepeatedEvaluationPolicy
    stopping_rules: tuple[AdaptiveStoppingRule, ...]
    invalidation_rules: tuple[AdaptiveInvalidationRule, ...]

    def __post_init__(self) -> None:
        _require_exact_enum(
            self.repeated_candidate_evaluation,
            RepeatedEvaluationPolicy,
            "repeated_candidate_evaluation",
        )
        _require_sorted_unique_enum_members(
            self.stopping_rules,
            AdaptiveStoppingRule,
            "stopping_rules",
        )
        _require_sorted_unique_enum_members(
            self.invalidation_rules,
            AdaptiveInvalidationRule,
            "invalidation_rules",
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "repeated_candidate_evaluation": self.repeated_candidate_evaluation.value,
            "stopping_rules": [rule.value for rule in self.stopping_rules],
            "invalidation_rules": [rule.value for rule in self.invalidation_rules],
        }


@dataclass(frozen=True, slots=True)
class EvaluationTierPolicy:
''',
    "adaptive controls",
)

impl = replace_once(
    impl,
    '''@dataclass(frozen=True, slots=True)
class MetricContract:
    """Metric identity bound to a frozen evaluator and optimization direction."""

    metric_id: str
    evaluator_id: str
    direction: MetricDirection

    def __post_init__(self) -> None:
        _require_token(self.metric_id, "metric_id")
        _require_token(self.evaluator_id, "evaluator_id")
        _require_exact_enum(self.direction, MetricDirection, "direction")

    def to_dict(self) -> dict[str, str]:
        return {
            "metric_id": self.metric_id,
            "evaluator_id": self.evaluator_id,
            "direction": self.direction.value,
        }
''',
    '''@dataclass(frozen=True, slots=True)
class MetricContract:
    """Metric identity bound to one frozen evaluator and evaluation tier."""

    metric_id: str
    evaluator_id: str
    tier: EvaluationTier
    direction: MetricDirection

    def __post_init__(self) -> None:
        _require_token(self.metric_id, "metric_id")
        _require_token(self.evaluator_id, "evaluator_id")
        _require_exact_enum(self.tier, EvaluationTier, "tier")
        _require_exact_enum(self.direction, MetricDirection, "direction")

    def to_dict(self) -> dict[str, object]:
        return {
            "metric_id": self.metric_id,
            "evaluator_id": self.evaluator_id,
            "tier": int(self.tier),
            "direction": self.direction.value,
        }
''',
    "metric tier binding",
)

impl = replace_once(
    impl,
    '''    evaluation_tier_policy: EvaluationTierPolicy
    adaptive_query_budget: AdaptiveQueryBudget
    tier_result_exposure_policy: tuple[TierResultExposure, ...]
''',
    '''    evaluation_tier_policy: EvaluationTierPolicy
    adaptive_query_budget: AdaptiveQueryBudget
    adaptive_evaluation_controls: AdaptiveEvaluationControls
    tier_result_exposure_policy: tuple[TierResultExposure, ...]
''',
    "objective adaptive field",
)

impl = replace_once(
    impl,
    '''        _require_sorted_unique_text(
            self.allowed_mutation_surfaces, "allowed_mutation_surfaces", allow_empty=True
        )
        _require_sorted_unique_text(self.forbidden_mutation_surfaces, "forbidden_mutation_surfaces")
''',
    '''        _require_allowed_mutation_surfaces(self.allowed_mutation_surfaces)
        _require_sorted_unique_text(self.forbidden_mutation_surfaces, "forbidden_mutation_surfaces")
''',
    "mutation validation",
)

impl = replace_once(
    impl,
    '''        _require_exact_instance(
            self.adaptive_query_budget, AdaptiveQueryBudget, "adaptive_query_budget"
        )
        _require_exact_enum(
''',
    '''        _require_exact_instance(
            self.adaptive_query_budget, AdaptiveQueryBudget, "adaptive_query_budget"
        )
        _require_exact_instance(
            self.adaptive_evaluation_controls,
            AdaptiveEvaluationControls,
            "adaptive_evaluation_controls",
        )
        _require_exact_enum(
''',
    "adaptive controls exact type",
)

impl = replace_once(
    impl,
    '''        known_evaluators = set(evaluator_ids)
        for metric in self.search_metrics + self.evaluation_metrics:
            if metric.evaluator_id not in known_evaluators:
                raise ResearchObjectiveContractError(
                    f"metric {metric.metric_id!r} references unknown evaluator "
                    f"{metric.evaluator_id!r}"
                )

        if not self.hard_guardrails:
''',
    '''        evaluator_by_id = {
            identity.evaluator_id: identity for identity in self.evaluator_identities
        }
        for metric in self.search_metrics:
            if metric.tier is not EvaluationTier.SEARCH:
                raise ResearchObjectiveContractError(
                    f"search metric {metric.metric_id!r} must use Tier 1 SEARCH"
                )
            _require_metric_evaluator_binding(metric, evaluator_by_id, allowed_tiers)
        for metric in self.evaluation_metrics:
            if metric.tier is EvaluationTier.SEARCH:
                raise ResearchObjectiveContractError(
                    f"evaluation metric {metric.metric_id!r} cannot use Tier 1 SEARCH"
                )
            _require_metric_evaluator_binding(metric, evaluator_by_id, allowed_tiers)

        if not self.hard_guardrails:
''',
    "metric evaluator validation",
)

impl = replace_once(
    impl,
    '''            "adaptive_query_budget": self.adaptive_query_budget.to_dict(),
            "tier_result_exposure_policy": [
''',
    '''            "adaptive_query_budget": self.adaptive_query_budget.to_dict(),
            "adaptive_evaluation_controls": self.adaptive_evaluation_controls.to_dict(),
            "tier_result_exposure_policy": [
''',
    "semantic adaptive controls",
)

impl = replace_once(
    impl,
    '''def _require_sorted_unique_program_refs(values: tuple[str, ...]) -> None:
    _require_sorted_unique_text(values, "research_program_refs")
    for value in values:
        if not _RESEARCH_PROGRAM_REF.fullmatch(value):
            raise ResearchObjectiveContractError(
                f"research_program_refs contains unsupported reference {value!r}"
            )


def _require_sorted_unique_text(
''',
    '''def _require_sorted_unique_program_refs(values: tuple[str, ...]) -> None:
    _require_sorted_unique_text(values, "research_program_refs")
    for value in values:
        if value not in _ACCEPTED_RESEARCH_PROGRAM_REFS:
            raise ResearchObjectiveContractError(
                "research_program_refs contains an unregistered canonical question "
                f"reference {value!r}"
            )


def _require_allowed_mutation_surfaces(values: tuple[str, ...]) -> None:
    _require_sorted_unique_text(values, "allowed_mutation_surfaces", allow_empty=True)
    for value in values:
        parts = value.split("/")
        if (
            value.startswith("/")
            or value.endswith("/")
            or "\\\\" in value
            or any(part in ("", ".", "..") for part in parts)
        ):
            raise ResearchObjectiveContractError(
                f"allowed_mutation_surfaces contains non-canonical relative path {value!r}"
            )
        if not any(value.startswith(root) for root in _SAFE_MUTATION_ROOTS):
            raise ResearchObjectiveContractError(
                "allowed_mutation_surfaces may target only governed campaign-mutable roots; "
                f"rejected {value!r}"
            )


def _require_sorted_unique_text(
''',
    "program refs and mutation safe roots",
)

impl = replace_once(
    impl,
    '''def _require_exact_enum(value: object, expected_type: type[enum.Enum], label: str) -> None:
    if type(value) is not expected_type:
        raise ResearchObjectiveContractError(
            f"{label} must be exact {expected_type.__name__} member"
        )
''',
    '''def _require_exact_enum(value: object, expected_type: type[enum.Enum], label: str) -> None:
    if type(value) is not expected_type:
        raise ResearchObjectiveContractError(
            f"{label} must be exact {expected_type.__name__} member"
        )


def _require_sorted_unique_enum_members(
    values: tuple[enum.Enum, ...], expected_type: type[enum.Enum], label: str
) -> None:
    if type(values) is not tuple or not values:
        raise ResearchObjectiveContractError(f"{label} must be a non-empty exact tuple")
    for value in values:
        _require_exact_enum(value, expected_type, label)
    encoded = tuple(str(value.value) for value in values)
    if encoded != tuple(sorted(set(encoded))):
        raise ResearchObjectiveContractError(
            f"{label} must be unique and canonically sorted"
        )


def _require_metric_evaluator_binding(
    metric: MetricContract,
    evaluator_by_id: dict[str, EvaluatorIdentity],
    allowed_tiers: set[EvaluationTier],
) -> None:
    evaluator = evaluator_by_id.get(metric.evaluator_id)
    if evaluator is None:
        raise ResearchObjectiveContractError(
            f"metric {metric.metric_id!r} references unknown evaluator {metric.evaluator_id!r}"
        )
    if metric.tier not in allowed_tiers:
        raise ResearchObjectiveContractError(
            f"metric {metric.metric_id!r} references a tier outside the objective policy"
        )
    if metric.tier not in evaluator.tiers:
        raise ResearchObjectiveContractError(
            f"evaluator {metric.evaluator_id!r} does not admit metric tier {int(metric.tier)}"
        )
''',
    "enum and metric helpers",
)

IMPL.write_text(impl, encoding="utf-8")


test = TEST.read_text(encoding="utf-8")

test = replace_once(
    test,
    "from dataclasses import FrozenInstanceError, replace\n",
    "from dataclasses import FrozenInstanceError, fields, replace\n",
    "test dataclasses import",
)

test = replace_once(
    test,
    '''from medscale.mesc._mrl_research_objective_v1 import (
    AdaptiveQueryBudget,
    BudgetExhaustionDisposition,
''',
    '''from medscale.mesc._mrl_research_objective_v1 import (
    AdaptiveEvaluationControls,
    AdaptiveInvalidationRule,
    AdaptiveQueryBudget,
    AdaptiveStoppingRule,
    BudgetExhaustionDisposition,
''',
    "test adaptive imports",
)

test = replace_once(
    test,
    '''    MetricDirection,
    ResearchObjectiveContract,
''',
    '''    MetricDirection,
    RepeatedEvaluationPolicy,
    ResearchObjectiveContract,
''',
    "test repeat import",
)

test = replace_once(
    test,
    '''                metric_id="search-score",
                evaluator_id="eval.search",
                direction=MetricDirection.MAXIMIZE,
''',
    '''                metric_id="search-score",
                evaluator_id="eval.search",
                tier=EvaluationTier.SEARCH,
                direction=MetricDirection.MAXIMIZE,
''',
    "fixture search metric tier",
)

test = replace_once(
    test,
    '''                metric_id="safety",
                evaluator_id="eval.sealed",
                direction=MetricDirection.MAXIMIZE,
''',
    '''                metric_id="safety",
                evaluator_id="eval.sealed",
                tier=EvaluationTier.SEALED,
                direction=MetricDirection.MAXIMIZE,
''',
    "fixture evaluation metric tier",
)

test = replace_once(
    test,
    '''        allowed_mutation_surfaces=("src/medscale/mesc/fixture.py",),
''',
    '''        allowed_mutation_surfaces=("tests/fixtures/mrl/fixture.py",),
''',
    "fixture safe mutation root",
)

test = replace_once(
    test,
    '''        adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=5, tier_2_queries=0),
        tier_result_exposure_policy=(
''',
    '''        adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=5, tier_2_queries=0),
        adaptive_evaluation_controls=AdaptiveEvaluationControls(
            repeated_candidate_evaluation=(
                RepeatedEvaluationPolicy.PERMITTED_WITHIN_FROZEN_BUDGET
            ),
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
''',
    "fixture adaptive controls",
)

test = replace_once(
    test,
    '''        lambda value: replace(
            value,
            allowed_mutation_surfaces=("src/medscale/mesc/other_fixture.py",),
        ),
''',
    '''        lambda value: replace(
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
''',
    "material identity controls",
)

test = replace_once(
    test,
    '''def test_allowed_and_forbidden_mutation_surfaces_cannot_overlap() -> None:
    with pytest.raises(ResearchObjectiveContractError, match="both allowed and forbidden"):
        replace(
            _objective(),
            allowed_mutation_surfaces=("governance",),
        )
''',
    '''def test_allowed_and_forbidden_mutation_surfaces_cannot_overlap() -> None:
    with pytest.raises(ResearchObjectiveContractError, match="both allowed and forbidden"):
        replace(
            _objective(),
            forbidden_mutation_surfaces=("governance", "tests/fixtures/mrl/fixture.py"),
        )
''',
    "mutation overlap test",
)

test = replace_once(
    test,
    '''def test_research_program_reference_format_fails_closed() -> None:
    with pytest.raises(ResearchObjectiveContractError, match="unsupported reference"):
        replace(_objective(), research_program_refs=("UNREGISTERED-RQ-0001",))
''',
    '''@pytest.mark.parametrize("reference", ["UNREGISTERED-RQ-0001", "MRL-RQ-0001"])
def test_unregistered_research_program_reference_fails_closed(reference: str) -> None:
    with pytest.raises(ResearchObjectiveContractError, match="unregistered canonical question"):
        replace(_objective(), research_program_refs=(reference,))
''',
    "unregistered research refs",
)

test = replace_once(
    test,
    '''                MetricContract(
                    metric_id="search-score",
                    evaluator_id="eval.search",
                    direction="MAXIMIZE",  # type: ignore[arg-type]
                ),
''',
    '''                MetricContract(
                    metric_id="search-score",
                    evaluator_id="eval.search",
                    tier=EvaluationTier.SEARCH,
                    direction="MAXIMIZE",  # type: ignore[arg-type]
                ),
''',
    "runtime type metric tier",
)

test = replace_once(
    test,
    '''def test_unknown_constructor_field_is_rejected_by_closed_typed_contract() -> None:
    kwargs = _objective().semantic_dict()
    kwargs["unknown_field"] = "rejected"

    with pytest.raises(TypeError):
        ResearchObjectiveContract(**kwargs)  # type: ignore[arg-type]
''',
    '''def test_unknown_constructor_field_is_rejected_by_closed_typed_contract() -> None:
    objective = _objective()
    kwargs = {
        field.name: getattr(objective, field.name)
        for field in fields(ResearchObjectiveContract)
    }
    kwargs["unknown_field"] = "rejected"

    with pytest.raises(TypeError, match="unexpected keyword"):
        ResearchObjectiveContract(**kwargs)  # type: ignore[arg-type]
''',
    "closed constructor test",
)

extra_tests = r'''

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
            search_metrics=(
                replace(objective.search_metrics[0], tier=EvaluationTier.SEALED),
            ),
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
            evaluation_tier_policy=EvaluationTierPolicy(
                allowed_tiers=(EvaluationTier.SEARCH,)
            ),
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
'''

test += extra_tests
TEST.write_text(test, encoding="utf-8")
