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

old_views = '''    @property
    def content_sha256(self) -> str:
        """Derived artifact identity, excluded from its semantic preimage."""
        return derive_content_sha256(self.semantic_dict())

    @property
    def semantic_bytes(self) -> bytes:
        """Canonical UTF-8 semantic bytes used to derive ``content_sha256``."""
        return canonical_semantic_bytes(self.semantic_dict())

    def semantic_dict(self) -> dict[str, object]:
        """Return complete material semantics, deliberately excluding own identity."""
        return {
            "format": "MRL-RESEARCH-OBJECTIVE-V1",
            "objective_id": self.objective_id,
            "research_program_refs": list(self.research_program_refs),
            "target_capabilities": list(self.target_capabilities),
            "hard_guardrails": [floor.to_dict() for floor in self.hard_guardrails],
            "search_metrics": [metric.to_dict() for metric in self.search_metrics],
            "evaluation_metrics": [metric.to_dict() for metric in self.evaluation_metrics],
            "subgroup_floors": [floor.to_dict() for floor in self.subgroup_floors],
            "resource_budget": self.resource_budget.to_dict(),
            "allowed_mutation_surfaces": list(self.allowed_mutation_surfaces),
            "forbidden_mutation_surfaces": list(self.forbidden_mutation_surfaces),
            "evaluation_tier_policy": self.evaluation_tier_policy.to_dict(),
            "adaptive_query_budget": self.adaptive_query_budget.to_dict(),
            "adaptive_evaluation_controls": self.adaptive_evaluation_controls.to_dict(),
            "tier_result_exposure_policy": [
                policy.to_dict() for policy in self.tier_result_exposure_policy
            ],
            "budget_exhaustion_disposition": self.budget_exhaustion_disposition.value,
            "evaluator_identities": [identity.to_dict() for identity in self.evaluator_identities],
        }

    def to_dict(self) -> dict[str, object]:
        """Return the artifact envelope with identity outside the semantic preimage."""
        data = self.semantic_dict()
        data["content_sha256"] = self.content_sha256
        return data
'''

new_views = '''    def _validated_snapshot(self) -> ResearchObjectiveContract:
        """Rebuild one locally validated semantic snapshot before any public view."""
        _require_exact_instance(self, ResearchObjectiveContract, "research_objective")
        _require_exact_instances(self.hard_guardrails, EvidenceFloor, "hard_guardrails")
        _require_exact_instances(self.search_metrics, MetricContract, "search_metrics")
        _require_exact_instances(self.evaluation_metrics, MetricContract, "evaluation_metrics")
        _require_exact_instances(self.subgroup_floors, EvidenceFloor, "subgroup_floors")
        _require_exact_instances(
            self.tier_result_exposure_policy,
            TierResultExposure,
            "tier_result_exposure_policy",
        )
        _require_exact_instances(
            self.evaluator_identities,
            EvaluatorIdentity,
            "evaluator_identities",
        )

        return ResearchObjectiveContract(
            objective_id=self.objective_id,
            research_program_refs=self.research_program_refs,
            target_capabilities=self.target_capabilities,
            hard_guardrails=tuple(
                _snapshot_evidence_floor(floor) for floor in self.hard_guardrails
            ),
            search_metrics=tuple(
                _snapshot_metric_contract(metric) for metric in self.search_metrics
            ),
            evaluation_metrics=tuple(
                _snapshot_metric_contract(metric) for metric in self.evaluation_metrics
            ),
            subgroup_floors=tuple(
                _snapshot_evidence_floor(floor) for floor in self.subgroup_floors
            ),
            resource_budget=_snapshot_resource_budget(self.resource_budget),
            allowed_mutation_surfaces=self.allowed_mutation_surfaces,
            forbidden_mutation_surfaces=self.forbidden_mutation_surfaces,
            evaluation_tier_policy=_snapshot_evaluation_tier_policy(
                self.evaluation_tier_policy
            ),
            adaptive_query_budget=_snapshot_adaptive_query_budget(
                self.adaptive_query_budget
            ),
            adaptive_evaluation_controls=_snapshot_adaptive_evaluation_controls(
                self.adaptive_evaluation_controls
            ),
            tier_result_exposure_policy=tuple(
                _snapshot_tier_result_exposure(policy)
                for policy in self.tier_result_exposure_policy
            ),
            budget_exhaustion_disposition=self.budget_exhaustion_disposition,
            evaluator_identities=tuple(
                _snapshot_evaluator_identity(identity)
                for identity in self.evaluator_identities
            ),
        )

    @property
    def content_sha256(self) -> str:
        """Derive identity from one freshly revalidated semantic snapshot."""
        snapshot = self._validated_snapshot()
        return derive_content_sha256(snapshot._semantic_dict_validated())

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical bytes from one freshly revalidated semantic snapshot."""
        snapshot = self._validated_snapshot()
        return canonical_semantic_bytes(snapshot._semantic_dict_validated())

    def semantic_dict(self) -> dict[str, object]:
        """Return complete semantics from one freshly revalidated local snapshot."""
        snapshot = self._validated_snapshot()
        return snapshot._semantic_dict_validated()

    def _semantic_dict_validated(self) -> dict[str, object]:
        """Serialize a private snapshot that has just passed full validation."""
        return {
            "format": "MRL-RESEARCH-OBJECTIVE-V1",
            "objective_id": self.objective_id,
            "research_program_refs": list(self.research_program_refs),
            "target_capabilities": list(self.target_capabilities),
            "hard_guardrails": [floor.to_dict() for floor in self.hard_guardrails],
            "search_metrics": [metric.to_dict() for metric in self.search_metrics],
            "evaluation_metrics": [metric.to_dict() for metric in self.evaluation_metrics],
            "subgroup_floors": [floor.to_dict() for floor in self.subgroup_floors],
            "resource_budget": self.resource_budget.to_dict(),
            "allowed_mutation_surfaces": list(self.allowed_mutation_surfaces),
            "forbidden_mutation_surfaces": list(self.forbidden_mutation_surfaces),
            "evaluation_tier_policy": self.evaluation_tier_policy.to_dict(),
            "adaptive_query_budget": self.adaptive_query_budget.to_dict(),
            "adaptive_evaluation_controls": self.adaptive_evaluation_controls.to_dict(),
            "tier_result_exposure_policy": [
                policy.to_dict() for policy in self.tier_result_exposure_policy
            ],
            "budget_exhaustion_disposition": self.budget_exhaustion_disposition.value,
            "evaluator_identities": [identity.to_dict() for identity in self.evaluator_identities],
        }

    def to_dict(self) -> dict[str, object]:
        """Return an envelope from one freshly revalidated local snapshot."""
        snapshot = self._validated_snapshot()
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data
'''

impl = replace_once(impl, old_views, new_views, "public semantic views")

snapshot_helpers = '''

def _snapshot_resource_budget(value: ResourceBudget) -> ResourceBudget:
    _require_exact_instance(value, ResourceBudget, "resource_budget")
    return ResourceBudget(
        wall_clock_seconds=value.wall_clock_seconds,
        compute_seconds=value.compute_seconds,
        input_tokens=value.input_tokens,
        generated_tokens=value.generated_tokens,
        storage_bytes=value.storage_bytes,
        monetary_cost_microunits=value.monetary_cost_microunits,
        retries=value.retries,
        known_failure_retries=value.known_failure_retries,
        evaluator_invocations=value.evaluator_invocations,
    )


def _snapshot_adaptive_query_budget(value: AdaptiveQueryBudget) -> AdaptiveQueryBudget:
    _require_exact_instance(value, AdaptiveQueryBudget, "adaptive_query_budget")
    return AdaptiveQueryBudget(
        tier_1_queries=value.tier_1_queries,
        tier_2_queries=value.tier_2_queries,
    )


def _snapshot_adaptive_evaluation_controls(
    value: AdaptiveEvaluationControls,
) -> AdaptiveEvaluationControls:
    _require_exact_instance(
        value,
        AdaptiveEvaluationControls,
        "adaptive_evaluation_controls",
    )
    return AdaptiveEvaluationControls(
        repeated_candidate_evaluation=value.repeated_candidate_evaluation,
        stopping_rules=value.stopping_rules,
        invalidation_rules=value.invalidation_rules,
    )


def _snapshot_evaluation_tier_policy(value: EvaluationTierPolicy) -> EvaluationTierPolicy:
    _require_exact_instance(value, EvaluationTierPolicy, "evaluation_tier_policy")
    return EvaluationTierPolicy(allowed_tiers=value.allowed_tiers)


def _snapshot_evaluator_identity(value: EvaluatorIdentity) -> EvaluatorIdentity:
    _require_exact_instance(value, EvaluatorIdentity, "evaluator_identity")
    return EvaluatorIdentity(
        evaluator_id=value.evaluator_id,
        artifact_sha256=value.artifact_sha256,
        tiers=value.tiers,
    )


def _snapshot_metric_contract(value: MetricContract) -> MetricContract:
    _require_exact_instance(value, MetricContract, "metric_contract")
    return MetricContract(
        metric_id=value.metric_id,
        evaluator_id=value.evaluator_id,
        tier=value.tier,
        direction=value.direction,
    )


def _snapshot_evidence_floor(value: EvidenceFloor) -> EvidenceFloor:
    _require_exact_instance(value, EvidenceFloor, "evidence_floor")
    return EvidenceFloor(
        floor_id=value.floor_id,
        metric_id=value.metric_id,
        comparator=value.comparator,
        threshold_decimal=value.threshold_decimal,
        subgroup=value.subgroup,
    )


def _snapshot_tier_result_exposure(value: TierResultExposure) -> TierResultExposure:
    _require_exact_instance(value, TierResultExposure, "tier_result_exposure")
    return TierResultExposure(
        tier=value.tier,
        max_exposures=value.max_exposures,
        allowed_result_fields=value.allowed_result_fields,
    )
'''

impl = replace_once(
    impl,
    "\n\ndef _require_text(value: str, label: str) -> None:\n",
    snapshot_helpers + "\n\ndef _require_text(value: str, label: str) -> None:\n",
    "snapshot helpers",
)

impl = replace_once(
    impl,
    '    if not value or value != value.strip() or any(char in value for char in "\\r\\n\\t"):\n',
    '    if not value or value != value.strip() or any(char in value for char in "\\x00\\r\\n\\t"):\n',
    "canonical text NUL rejection",
)

impl = replace_once(
    impl,
    '''            value.startswith("/")
            or value.endswith("/")
            or "\\\\" in value
            or any(part in ("", ".", "..") for part in parts)
''',
    '''            value.startswith("/")
            or value.endswith("/")
            or "\\x00" in value
            or "\\\\" in value
            or any(part in ("", ".", "..") for part in parts)
''',
    "mutation path NUL rejection",
)

IMPL.write_text(impl, encoding="utf-8")


test = TEST.read_text(encoding="utf-8")
extra = r'''


def test_mutation_surface_with_nul_fails_closed() -> None:
    with pytest.raises(ResearchObjectiveContractError, match="canonical text|canonical relative"):
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
        objective.evaluator_identities[0],
        "tiers",
        (EvaluationTier.SEALED,),
    )

    with pytest.raises(ResearchObjectiveContractError, match="does not admit metric tier"):
        objective.semantic_dict()
    with pytest.raises(ResearchObjectiveContractError, match="does not admit metric tier"):
        _ = objective.content_sha256
'''

test += extra
TEST.write_text(test, encoding="utf-8")
