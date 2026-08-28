"""MRL-0105 tests for the immutable ResearchExperimentReceipt."""

from __future__ import annotations

import json
from dataclasses import fields, replace

import pytest

from medscale.mesc._mrl_experiment_manifest_binding_v1 import bind_experiment_manifest
from medscale.mesc._mrl_research_experiment_plan_v1 import (
    ExpectedDatasetBinding,
    ExpectedExperimentManifestBinding,
    ExpectedModelBinding,
    PlanFailureCondition,
    PlanStopCondition,
    PlanTierAllowance,
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
    ResearchExperimentReceiptError,
    TierAccounting,
)
from medscale.mesc._mrl_research_hypothesis_v1 import ResearchHypothesis
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
from medscale.modelkit.interfaces import ModelRef
from medscale.modelkit.manifests import DatasetSnapshot, ExperimentManifest, RunnerClass, RunnerEnv
from medscale.reproducibility import canonical_json, content_hash

_CONFIGURATION = canonical_json({"fixture": True, "shots": 0})
_DATASET = DatasetSnapshot("fixture-dataset", "1.0.0", "e" * 64)
_MODEL = ModelRef(
    model_id="fixture/model",
    revision="revision-001",
    quantization="none",
    backend="fixture",
)
_RUNNER = RunnerEnv(runner=RunnerClass.LOCAL, python="3.11", os_name="linux")
_RESULTS = ("experiments/results/fixture-experiment-001.json",)


def _objective() -> ResearchObjectiveContract:
    return ResearchObjectiveContract(
        objective_id="fixture-research-objective",
        research_program_refs=("RQ1",),
        target_capabilities=("evidence-fidelity",),
        hard_guardrails=(
            EvidenceFloor(
                floor_id="global-safety",
                metric_id="safety",
                comparator=FloorComparator.GTE,
                threshold_decimal="0.95",
            ),
        ),
        search_metrics=(
            MetricContract(
                metric_id="search-score",
                evaluator_id="eval.search",
                tier=EvaluationTier.SEARCH,
                direction=MetricDirection.MAXIMIZE,
            ),
        ),
        evaluation_metrics=(
            MetricContract(
                metric_id="safety",
                evaluator_id="eval.sealed",
                tier=EvaluationTier.SEALED,
                direction=MetricDirection.MAXIMIZE,
            ),
        ),
        subgroup_floors=(
            EvidenceFloor(
                floor_id="subgroup-safety",
                metric_id="safety",
                comparator=FloorComparator.GTE,
                threshold_decimal="0.9",
                subgroup="critical-cohort",
            ),
        ),
        resource_budget=ResourceBudget(
            wall_clock_seconds=600,
            compute_seconds=300,
            input_tokens=10_000,
            generated_tokens=2_000,
            storage_bytes=1_000_000,
            monetary_cost_microunits=500_000,
            max_experiments=12,
            retries=3,
            known_failure_retries=1,
            evaluator_invocations=20,
        ),
        allowed_mutation_surfaces=("experiments/fixture.py",),
        forbidden_mutation_surfaces=("governance", "sealed-evaluation"),
        evaluation_tier_policy=EvaluationTierPolicy(
            allowed_tiers=(EvaluationTier.SEARCH, EvaluationTier.SEALED)
        ),
        adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=5, tier_2_queries=0),
        adaptive_evaluation_controls=AdaptiveEvaluationControls(
            repeated_candidate_evaluation=RepeatedEvaluationPolicy.PERMITTED_WITHIN_FROZEN_BUDGET,
            stopping_rules=(
                AdaptiveStoppingRule.ADAPTIVE_QUERY_BUDGET_EXHAUSTED,
                AdaptiveStoppingRule.EXTERNAL_GOVERNANCE_STOP,
                AdaptiveStoppingRule.OBJECTIVE_INVALIDATED,
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
                tier=EvaluationTier.SEARCH,
                max_exposures=5,
                allowed_result_fields=("aggregate_score",),
            ),
            TierResultExposure(
                tier=EvaluationTier.SEALED,
                max_exposures=0,
                allowed_result_fields=(),
            ),
        ),
        budget_exhaustion_disposition=BudgetExhaustionDisposition.BLOCKED,
        evaluator_identities=(
            EvaluatorIdentity(
                evaluator_id="eval.sealed",
                artifact_sha256="b" * 64,
                tiers=(EvaluationTier.SEALED,),
            ),
            EvaluatorIdentity(
                evaluator_id="eval.search",
                artifact_sha256="a" * 64,
                tiers=(EvaluationTier.SEARCH,),
            ),
        ),
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
        seeds=(7, 11),
        runner=_RUNNER,
        started_at="2026-08-28T00:00:00+00:00",
        results_paths=_RESULTS,
        reproduction="uv run fixture-experiment",
    )


def _plan(*, code_sha: str = "1" * 40) -> ResearchExperimentPlan:
    objective = _objective()
    hypothesis = ResearchHypothesis(
        hypothesis_id="fixture-hypothesis",
        objective_sha256=objective.content_sha256,
        mechanism="A bounded fixture mutation may improve the search metric.",
        predicted_effects=("Search score increases without violating safety floors.",),
        predicted_failure_modes=("The mutation may have no measurable effect.",),
        falsification_criteria=("Search score does not improve under the frozen evaluator.",),
        evidence_refs=("fixture:evidence-001",),
        parent_hypothesis_ids=(),
        created_from_campaign_state_sha256="c" * 64,
    )
    expected_manifest = ExpectedExperimentManifestBinding(
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
        code_sha=code_sha,
        seeds=(7, 11),
        results_paths=_RESULTS,
    )
    return ResearchExperimentPlan(
        experiment_plan_id="fixture-plan-001",
        objective=objective,
        hypothesis=hypothesis,
        mutation_surfaces=("experiments/fixture.py",),
        expected_manifest=expected_manifest,
        resource_ceiling=ResourceBudget(
            wall_clock_seconds=300,
            compute_seconds=120,
            input_tokens=2_000,
            generated_tokens=500,
            storage_bytes=100_000,
            monetary_cost_microunits=100_000,
            max_experiments=1,
            retries=1,
            known_failure_retries=0,
            evaluator_invocations=4,
        ),
        evaluator_identities=objective.evaluator_identities,
        evaluation_tiers=(EvaluationTier.SEARCH, EvaluationTier.SEALED),
        tier_allowances=(
            PlanTierAllowance(
                tier=EvaluationTier.SEARCH,
                max_queries=3,
                max_result_exposures=3,
                allowed_result_fields=("aggregate_score",),
            ),
            PlanTierAllowance(
                tier=EvaluationTier.SEALED,
                max_queries=0,
                max_result_exposures=0,
                allowed_result_fields=(),
            ),
        ),
        stop_conditions=tuple(sorted(PlanStopCondition, key=lambda item: item.value)),
        failure_conditions=tuple(sorted(PlanFailureCondition, key=lambda item: item.value)),
    )


def _metrics() -> tuple[MetricArtifactResult, ...]:
    return (
        MetricArtifactResult(
            metric_id="safety",
            evaluator_id="eval.sealed",
            evaluator_artifact_sha256="b" * 64,
            tier=EvaluationTier.SEALED,
            artifact_sha256="6" * 64,
        ),
        MetricArtifactResult(
            metric_id="search-score",
            evaluator_id="eval.search",
            evaluator_artifact_sha256="a" * 64,
            tier=EvaluationTier.SEARCH,
            artifact_sha256="5" * 64,
        ),
    )


def _resource_use(**overrides: object) -> ObservedResourceUse:
    values: dict[str, object] = {
        "wall_clock_seconds": 120,
        "compute_seconds": 60,
        "input_tokens": 1_000,
        "generated_tokens": 250,
        "storage_bytes": 50_000,
        "monetary_cost_microunits": 50_000,
        "retries": 0,
        "known_failure_retries": 0,
        "evaluator_invocations": 2,
    }
    values.update(overrides)
    return ObservedResourceUse(**values)  # type: ignore[arg-type]


def _receipt(**overrides: object) -> ResearchExperimentReceipt:
    plan = _plan()
    binding = bind_experiment_manifest(plan, _manifest())
    values: dict[str, object] = {
        "binding": binding,
        "code_identity": CodePatchIdentity(
            code_sha="1" * 40,
            tree_sha="2" * 40,
            patch_sha256="3" * 64,
        ),
        "observed_resource_use": _resource_use(),
        "metric_artifacts": _metrics(),
        "guardrail_results": (
            EvidenceFloorResult(
                floor_id="global-safety",
                metric_artifact_sha256="6" * 64,
                passed=True,
            ),
        ),
        "subgroup_results": (
            EvidenceFloorResult(
                floor_id="subgroup-safety",
                metric_artifact_sha256="6" * 64,
                passed=True,
            ),
        ),
        "failure_classification": None,
        "contamination_lineage_audit": ContaminationLineageAudit(
            status=ContaminationLineageStatus.NOT_EVALUATED,
            artifact_sha256=None,
        ),
        "reproduction": ReproductionResult(
            status=ReproductionStatus.NOT_ATTEMPTED,
            artifact_sha256=None,
        ),
        "raw_output_artifact_sha256s": ("7" * 64,),
        "tier_accounting": (
            TierAccounting(
                tier=EvaluationTier.SEARCH,
                queries_used=2,
                result_exposures_used=1,
                exposed_result_fields=("aggregate_score",),
            ),
            TierAccounting(
                tier=EvaluationTier.SEALED,
                queries_used=0,
                result_exposures_used=0,
                exposed_result_fields=(),
            ),
        ),
    }
    values.update(overrides)
    return ResearchExperimentReceipt(**values)  # type: ignore[arg-type]


def test_receipt_identity_is_outside_semantic_preimage_and_byte_stable() -> None:
    first = _receipt()
    second = _receipt()

    assert "content_sha256" not in first.semantic_dict()
    assert first.to_dict()["content_sha256"] == first.content_sha256
    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256


def test_receipt_binds_exact_plan_manifest_code_metric_and_tier_identities() -> None:
    receipt = _receipt()
    payload = receipt.semantic_dict()
    binding = receipt.binding.semantic_dict()

    assert payload["experiment_plan_sha256"] == binding["experiment_plan_sha256"]
    assert payload["experiment_manifest_sha256"] == binding["experiment_manifest_sha256"]
    assert payload["code_identity"] == {
        "code_sha": "1" * 40,
        "tree_sha": "2" * 40,
        "patch_sha256": "3" * 64,
    }
    assert [item["metric_id"] for item in payload["metric_artifacts"]] == [
        "safety",
        "search-score",
    ]
    assert [item["tier"] for item in payload["tier_accounting"]] == [1, 3]


def test_material_semantic_change_changes_receipt_identity() -> None:
    receipt = _receipt()
    changed = replace(
        receipt,
        reproduction=ReproductionResult(
            status=ReproductionStatus.REPRODUCED,
            artifact_sha256="8" * 64,
        ),
    )

    assert changed.content_sha256 != receipt.content_sha256


def test_code_sha_must_match_both_plan_and_bound_manifest() -> None:
    with pytest.raises(ResearchExperimentReceiptError, match="code_sha"):
        _receipt(
            code_identity=CodePatchIdentity(
                code_sha="9" * 40,
                tree_sha="2" * 40,
                patch_sha256="3" * 64,
            )
        )


def test_successful_receipt_requires_every_applicable_metric() -> None:
    with pytest.raises(ResearchExperimentReceiptError, match="exactly every metric"):
        _receipt(metric_artifacts=(_metrics()[0],))


def test_failed_receipt_may_preserve_partial_metric_evidence() -> None:
    receipt = _receipt(
        metric_artifacts=(),
        guardrail_results=(),
        subgroup_results=(),
        failure_classification=PlanFailureCondition.EXECUTION_ERROR,
    )

    assert receipt.failure_classification is PlanFailureCondition.EXECUTION_ERROR
    assert receipt.metric_artifacts == ()


@pytest.mark.parametrize(
    ("field", "value", "pattern"),
    (
        ("evaluator_id", "eval.search", "evaluator_id"),
        ("evaluator_artifact_sha256", "0" * 64, "evaluator artifact identity"),
        ("tier", EvaluationTier.SEARCH, "tier"),
    ),
)
def test_metric_identity_substitution_fails_closed(
    field: str,
    value: object,
    pattern: str,
) -> None:
    metrics = list(_metrics())
    metrics[0] = replace(metrics[0], **{field: value})
    with pytest.raises(ResearchExperimentReceiptError, match=pattern):
        _receipt(metric_artifacts=tuple(metrics))


def test_metric_artifacts_must_be_unique_and_strictly_sorted() -> None:
    with pytest.raises(ResearchExperimentReceiptError, match="strictly sorted"):
        _receipt(metric_artifacts=tuple(reversed(_metrics())))


def test_guardrail_and_subgroup_results_bind_the_exact_metric_artifact() -> None:
    bad = EvidenceFloorResult(
        floor_id="global-safety",
        metric_artifact_sha256="0" * 64,
        passed=True,
    )
    with pytest.raises(ResearchExperimentReceiptError, match="does not bind"):
        _receipt(guardrail_results=(bad,))


def test_successful_receipt_requires_every_applicable_floor_result() -> None:
    with pytest.raises(ResearchExperimentReceiptError, match="guardrail_results"):
        _receipt(guardrail_results=())
    with pytest.raises(ResearchExperimentReceiptError, match="subgroup_results"):
        _receipt(subgroup_results=())


def test_resource_overrun_requires_exact_matching_failure_classification() -> None:
    overrun = _resource_use(wall_clock_seconds=301)

    with pytest.raises(ResearchExperimentReceiptError, match="matching failure"):
        _receipt(observed_resource_use=overrun)

    receipt = _receipt(
        observed_resource_use=overrun,
        failure_classification=PlanFailureCondition.RESOURCE_BUDGET_OVERRUN,
    )
    assert receipt.failure_classification is PlanFailureCondition.RESOURCE_BUDGET_OVERRUN


def test_false_resource_overrun_classification_fails_closed() -> None:
    with pytest.raises(ResearchExperimentReceiptError, match="requires matching observed"):
        _receipt(failure_classification=PlanFailureCondition.RESOURCE_BUDGET_OVERRUN)


def test_resource_not_applicable_semantics_cannot_be_changed() -> None:
    with pytest.raises(ResearchExperimentReceiptError, match="cannot be None"):
        _receipt(observed_resource_use=_resource_use(compute_seconds=None))


def test_query_overrun_requires_matching_frozen_failure_classification() -> None:
    accounting = (
        TierAccounting(
            tier=EvaluationTier.SEARCH,
            queries_used=4,
            result_exposures_used=1,
            exposed_result_fields=("aggregate_score",),
        ),
        TierAccounting(
            tier=EvaluationTier.SEALED,
            queries_used=0,
            result_exposures_used=0,
            exposed_result_fields=(),
        ),
    )
    with pytest.raises(ResearchExperimentReceiptError, match="matching failure"):
        _receipt(tier_accounting=accounting)

    receipt = _receipt(
        tier_accounting=accounting,
        failure_classification=PlanFailureCondition.ADAPTIVE_QUERY_BUDGET_OVERRUN,
    )
    assert receipt.failure_classification is PlanFailureCondition.ADAPTIVE_QUERY_BUDGET_OVERRUN


def test_result_exposure_overrun_requires_matching_failure_classification() -> None:
    accounting = (
        TierAccounting(
            tier=EvaluationTier.SEARCH,
            queries_used=1,
            result_exposures_used=4,
            exposed_result_fields=("aggregate_score",),
        ),
        TierAccounting(
            tier=EvaluationTier.SEALED,
            queries_used=0,
            result_exposures_used=0,
            exposed_result_fields=(),
        ),
    )
    receipt = _receipt(
        tier_accounting=accounting,
        failure_classification=PlanFailureCondition.RESULT_EXPOSURE_BUDGET_OVERRUN,
    )
    assert receipt.failure_classification is PlanFailureCondition.RESULT_EXPOSURE_BUDGET_OVERRUN


def test_tier_accounting_must_match_plan_tiers_exactly() -> None:
    with pytest.raises(ResearchExperimentReceiptError, match="exactly every plan tier"):
        _receipt(tier_accounting=(_receipt().tier_accounting[0],))


def test_exposed_fields_cannot_escape_frozen_tier_allowance() -> None:
    accounting = (
        TierAccounting(
            tier=EvaluationTier.SEARCH,
            queries_used=1,
            result_exposures_used=1,
            exposed_result_fields=("raw_item",),
        ),
        _receipt().tier_accounting[1],
    )
    with pytest.raises(ResearchExperimentReceiptError, match="outside the frozen allowance"):
        _receipt(tier_accounting=accounting)


def test_failure_classification_must_have_been_frozen_in_plan() -> None:
    plan = _plan()
    narrowed = replace(
        plan,
        failure_conditions=(
            PlanFailureCondition.CONTAMINATION_OR_LINEAGE_FAILURE,
            PlanFailureCondition.EVALUATOR_IDENTITY_MISMATCH,
            PlanFailureCondition.MUTATION_SCOPE_VIOLATION,
            PlanFailureCondition.OBJECTIVE_SEMANTICS_CHANGED,
            PlanFailureCondition.SEALED_BOUNDARY_BREACH,
        ),
    )
    binding = bind_experiment_manifest(narrowed, _manifest())
    with pytest.raises(ResearchExperimentReceiptError, match="not frozen"):
        _receipt(
            binding=binding,
            failure_classification=PlanFailureCondition.EXECUTION_ERROR,
        )


def test_contamination_failure_classification_and_audit_must_agree() -> None:
    with pytest.raises(ResearchExperimentReceiptError, match="must agree"):
        _receipt(failure_classification=PlanFailureCondition.CONTAMINATION_OR_LINEAGE_FAILURE)

    receipt = _receipt(
        failure_classification=PlanFailureCondition.CONTAMINATION_OR_LINEAGE_FAILURE,
        contamination_lineage_audit=ContaminationLineageAudit(
            status=ContaminationLineageStatus.FAILED,
            artifact_sha256="8" * 64,
        ),
    )
    assert receipt.contamination_lineage_audit.status is ContaminationLineageStatus.FAILED


def test_audit_and_reproduction_cannot_claim_artifacts_when_not_performed() -> None:
    with pytest.raises(ResearchExperimentReceiptError, match="cannot claim"):
        ContaminationLineageAudit(
            status=ContaminationLineageStatus.NOT_EVALUATED,
            artifact_sha256="8" * 64,
        )
    with pytest.raises(ResearchExperimentReceiptError, match="cannot claim"):
        ReproductionResult(
            status=ReproductionStatus.NOT_ATTEMPTED,
            artifact_sha256="8" * 64,
        )


def test_raw_output_identities_are_hashes_only_sorted_and_unique() -> None:
    receipt = _receipt()
    field_names = {item.name for item in fields(receipt)}

    assert "raw_output_artifact_sha256s" in field_names
    assert "raw_stdout" not in field_names
    assert "raw_stderr" not in field_names

    with pytest.raises(ResearchExperimentReceiptError, match="strictly sorted"):
        _receipt(raw_output_artifact_sha256s=("8" * 64, "7" * 64))


def test_numeric_subclasses_are_rejected_from_resource_accounting() -> None:
    with pytest.raises(ResearchExperimentReceiptError, match="exact non-negative integer"):
        _resource_use(wall_clock_seconds=True)


def test_nested_type_substitution_is_rejected() -> None:
    class MetricArtifactSubclass(MetricArtifactResult):
        pass

    original = _metrics()[0]
    substituted = MetricArtifactSubclass(
        metric_id=original.metric_id,
        evaluator_id=original.evaluator_id,
        evaluator_artifact_sha256=original.evaluator_artifact_sha256,
        tier=original.tier,
        artifact_sha256=original.artifact_sha256,
    )
    with pytest.raises(ResearchExperimentReceiptError, match="invalid item types"):
        _receipt(metric_artifacts=(substituted, _metrics()[1]))


def test_post_construction_rebinding_fails_on_next_trust_bearing_view() -> None:
    receipt = _receipt()
    object.__setattr__(
        receipt,
        "code_identity",
        CodePatchIdentity(
            code_sha="9" * 40,
            tree_sha="2" * 40,
            patch_sha256="3" * 64,
        ),
    )

    with pytest.raises(ResearchExperimentReceiptError, match="code_sha"):
        _ = receipt.content_sha256


def test_receipt_itself_rejects_subclass_trust_views() -> None:
    class ReceiptSubclass(ResearchExperimentReceipt):
        pass

    base = _receipt()
    subclassed = ReceiptSubclass(
        binding=base.binding,
        code_identity=base.code_identity,
        observed_resource_use=base.observed_resource_use,
        metric_artifacts=base.metric_artifacts,
        guardrail_results=base.guardrail_results,
        subgroup_results=base.subgroup_results,
        failure_classification=base.failure_classification,
        contamination_lineage_audit=base.contamination_lineage_audit,
        reproduction=base.reproduction,
        raw_output_artifact_sha256s=base.raw_output_artifact_sha256s,
        tier_accounting=base.tier_accounting,
    )
    with pytest.raises(ResearchExperimentReceiptError, match="subclasses/type substitution"):
        _ = subclassed.content_sha256
