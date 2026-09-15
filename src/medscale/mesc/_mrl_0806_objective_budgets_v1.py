"""Deterministic MRL-0806 RQ1 objective/budget freeze.

This module freezes one exact RQ1 objective, protocol, scientific-inference boundary,
and bounded resource/exposure budget. It produces untrusted preflight evidence only. It
does not load models, execute inference, activate GPUs, train, mutate weights, admit trust,
promote, release, deploy, or create clinical authority.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Context, Decimal, localcontext
from fractions import Fraction
from typing import Final, cast

from medscale.mesc._canonical_json_v1 import (
    CanonicalContractError,
    canonical_json_bytes,
)
from medscale.mesc._mrl_real_preflight_evidence_v1 import (
    parse_mrl_real_preflight_evidence,
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

_AUTHORIZATION_SHA256: Final = "81f976547a7591d7b9624e15666d92c7a4ba4d2965859364828b0bc14d7f25bb"
_AUTH_SCHEMA: Final = "MESC-MRL-0806-OBJECTIVE-BUDGETS-AUTHORIZATION-V1"
_TASK: Final = "MRL-0806"
_KIND: Final = "mesc.mrl.real_preflight.objective_budgets.v1"
_RECEIPT_SCHEMA: Final = "MESC-MRL-0806-OBJECTIVE-BUDGETS-RECEIPT-V1"
_SCOPE: Final = "MRL-0806_RQ1_OBJECTIVE_BUDGET_FREEZE_ONLY"
_CANDIDATE: Final = "mrl-rq1-fhir-grammar-decoupling-v1"
_EXPERIMENT: Final = "mesc-experiment-0-foundation-tournament"
_RESEARCH_QUESTION: Final = "RQ1"
_OBJECTIVE_SHA256: Final = "53149a0966e88eaa0c584f3f115e624444a8e479fc4bb45adf5ce727d18ed621"
_PROTOCOL_SHA256: Final = "8a2601a76077413d65c42ff68a65f118f7479350952b4b3e45785593ae11e494"
_CANDIDATE_ROSTER_SHA256: Final = "2968f2c71fd0de4a9ef9b5f6e5d4d58d75ce0f2cf5af8a56840031d85f694489"
_CORPUS_SHA256: Final = "977f5faa543f479276ad3742af797435e2ee732d8b9e8e594fabbf99e916b16e"
_EVALUATION_CONTRACT_SHA256: Final = (
    "300d310113a7e9d29521808238ef38d33c3c0927311c1d41d4d4dc591936b998"
)
_EVALUATOR_IDENTITY_SHA256: Final = (
    "af5cf78bfe7a932ed14c90d7decc9a060d1fde52de47e74cede9bfcb2da310ba"
)
_SEALED_TIER3_IDENTITY_SHA256: Final = (
    "2703548e3a09b7e8a12b1c62ae060d32322b488815ad3edd8a40bf8c948003c0"
)
_SEALED_BYTES_SHA256: Final = "a74ca84315459622b38a437fd31b9b82058701c5a28798ced3c8deac5a5f9247"
_PREDECESSOR_EVIDENCE: Final = {
    "MRL-0801": "c03792530e497857c700b64b1ee9950ede595006d35b577b7b8c573624c6c8b9",
    "MRL-0802": "1d6d14590a19c20bcd794e4c0ddbd2fa5e1c767b70e9d199fc169aeaaa86b762",
    "MRL-0803": "629d8d39a6ea44e753b6d83e07116b12213a74c14f395bea700224fc6781c8e2",
    "MRL-0804": "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0",
    "MRL-0805": "48e528b2c73d689805634f733628cc3f3e93d10b93afee7d765900c45fe42116",
    "MRL-0807": "1316c1ef2236203d4ad703cb269f8e30afc6d3dfe6d7a2df68128ec2a2edabab",
}
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_EXPECTED_BASE_SHA: Final = "1653fe9e26aeb2f52f48afdfdc8d9c3f133fec91"
_EXPECTED_BASE_TREE: Final = "ea274f48a74378da59226727af0ff1bce329eb11"
_HL7: Final = "hl7-fhir-r4-structural-validator-6.10.4"
_F1: Final = "medscale-patient-projection-set-f1-v1"
_TIERS: Final = (
    EvaluationTier.SEARCH,
    EvaluationTier.REPLICATION,
    EvaluationTier.SEALED,
)
_CONSTRAINTS: Final = ("constrained", "unconstrained")
_PROMPTS: Final = ("few-shot", "zero-shot")
_T_CRITICAL: Final = Decimal("4.302652729696142")
_DECIMAL_PLACES: Final = Decimal("0.000000000001")
_DECIMAL_PRECISION: Final = 80


class MRL0806ObjectiveBudgetsError(ValueError):
    """Raised when MRL-0806 frozen objective/budget material fails closed."""


@dataclass(frozen=True, slots=True)
class PairedSeedSummary:
    """Deterministic three-seed paired summary using exact rational source values."""

    mean: str
    ci95_lower: str
    ci95_upper: str
    disposition: str

    def to_dict(self) -> dict[str, str]:
        return {
            "ci95_lower": self.ci95_lower,
            "ci95_upper": self.ci95_upper,
            "disposition": self.disposition,
            "mean": self.mean,
        }


@dataclass(frozen=True, slots=True)
class MRL0806Qualification:
    """Deterministic untrusted MRL-0806 receipt and evidence candidate."""

    freeze_receipt_bytes: bytes = field(repr=False)
    evidence_bytes: bytes = field(repr=False)
    research_objective_sha256: str
    rq1_protocol_sha256: str
    freeze_receipt_sha256: str
    evidence_sha256: str


def _metric_id(metric: str, constraint: str, prompt: str, tier: str) -> str:
    return f"{metric}-{constraint}-{prompt}-{tier}-v1"


def _tier_metrics(tier: EvaluationTier, tier_name: str) -> tuple[MetricContract, ...]:
    items: list[MetricContract] = []
    for constraint in _CONSTRAINTS:
        for prompt in _PROMPTS:
            items.extend(
                (
                    MetricContract(
                        metric_id=_metric_id(
                            "fhir-structural-validity", constraint, prompt, tier_name
                        ),
                        evaluator_id=_HL7,
                        tier=tier,
                        direction=MetricDirection.MAXIMIZE,
                    ),
                    MetricContract(
                        metric_id=_metric_id(
                            "patient-projection-set-f1", constraint, prompt, tier_name
                        ),
                        evaluator_id=_F1,
                        tier=tier,
                        direction=MetricDirection.MAXIMIZE,
                    ),
                )
            )
    return tuple(sorted(items, key=lambda item: item.metric_id))


def build_mrl_0806_rq1_objective() -> ResearchObjectiveContract:
    """Rebuild the exact externally frozen RQ1 objective from typed canonical contracts."""
    evaluators = (
        EvaluatorIdentity(
            evaluator_id=_HL7,
            artifact_sha256=_EVALUATOR_IDENTITY_SHA256,
            tiers=_TIERS,
        ),
        EvaluatorIdentity(
            evaluator_id=_F1,
            artifact_sha256=_EVALUATOR_IDENTITY_SHA256,
            tiers=_TIERS,
        ),
    )
    search_metrics = _tier_metrics(EvaluationTier.SEARCH, "search")
    evaluation_metrics = tuple(
        sorted(
            _tier_metrics(EvaluationTier.REPLICATION, "replication")
            + _tier_metrics(EvaluationTier.SEALED, "sealed"),
            key=lambda item: item.metric_id,
        )
    )
    hard_guardrails = tuple(
        sorted(
            (
                EvidenceFloor(
                    floor_id=f"sealed-{prompt}-constrained-structural-validity-perfect",
                    metric_id=_metric_id(
                        "fhir-structural-validity", "constrained", prompt, "sealed"
                    ),
                    comparator=FloorComparator.GTE,
                    threshold_decimal="1",
                )
                for prompt in _PROMPTS
            ),
            key=lambda item: item.floor_id,
        )
    )
    return ResearchObjectiveContract(
        objective_id=_CANDIDATE,
        research_program_refs=(_RESEARCH_QUESTION,),
        target_capabilities=("fhir-content-retention", "fhir-structural-validity"),
        hard_guardrails=hard_guardrails,
        search_metrics=search_metrics,
        evaluation_metrics=evaluation_metrics,
        subgroup_floors=(),
        resource_budget=ResourceBudget(
            wall_clock_seconds=86_400,
            compute_seconds=86_400,
            input_tokens=786_432,
            generated_tokens=196_608,
            storage_bytes=214_748_364_800,
            monetary_cost_microunits=0,
            max_experiments=72,
            retries=0,
            known_failure_retries=0,
            evaluator_invocations=768,
        ),
        allowed_mutation_surfaces=(),
        forbidden_mutation_surfaces=("data", "docs", "specs", "src", "tests"),
        evaluation_tier_policy=EvaluationTierPolicy(allowed_tiers=_TIERS),
        adaptive_query_budget=AdaptiveQueryBudget(tier_1_queries=24, tier_2_queries=24),
        adaptive_evaluation_controls=AdaptiveEvaluationControls(
            repeated_candidate_evaluation=RepeatedEvaluationPolicy.PERMITTED_WITHIN_FROZEN_BUDGET,
            stopping_rules=tuple(sorted(AdaptiveStoppingRule, key=lambda item: item.value)),
            invalidation_rules=tuple(sorted(AdaptiveInvalidationRule, key=lambda item: item.value)),
        ),
        tier_result_exposure_policy=(
            TierResultExposure(
                tier=EvaluationTier.SEARCH,
                max_exposures=1,
                allowed_result_fields=("content_quality", "structural_validity"),
            ),
            TierResultExposure(
                tier=EvaluationTier.REPLICATION,
                max_exposures=1,
                allowed_result_fields=("content_quality", "structural_validity"),
            ),
            TierResultExposure(
                tier=EvaluationTier.SEALED,
                max_exposures=0,
                allowed_result_fields=(),
            ),
        ),
        budget_exhaustion_disposition=BudgetExhaustionDisposition.BLOCKED,
        evaluator_identities=evaluators,
    )


def paired_seed_summary(
    values: tuple[Fraction, Fraction, Fraction],
) -> PairedSeedSummary:
    """Summarize exactly three paired seed deltas under the frozen df=2 policy."""
    if (
        type(values) is not tuple
        or len(values) != 3
        or any(type(v) is not Fraction for v in values)
    ):
        raise MRL0806ObjectiveBudgetsError("exactly three built-in Fraction values are required")
    mean = sum(values, Fraction()) / Fraction(3, 1)
    variance = sum((value - mean) ** 2 for value in values) / Fraction(2, 1)
    context = Context(prec=_DECIMAL_PRECISION, rounding=ROUND_HALF_EVEN)
    with localcontext(context) as active:
        mean_decimal = active.divide(Decimal(mean.numerator), Decimal(mean.denominator))
        if variance == 0:
            half_width = Decimal(0)
        else:
            variance_of_mean = variance / Fraction(3, 1)
            variance_decimal = active.divide(
                Decimal(variance_of_mean.numerator),
                Decimal(variance_of_mean.denominator),
            )
            half_width = active.multiply(_T_CRITICAL, active.sqrt(variance_decimal))
        lower = active.subtract(mean_decimal, half_width)
        upper = active.add(mean_decimal, half_width)
        disposition = (
            "POSITIVE"
            if lower > 0
            else "NEGATIVE"
            if upper < 0
            else "NO_DIFFERENCE_WITHIN_SEED_VARIANCE"
        )
        return PairedSeedSummary(
            mean=_serialize_decimal(mean_decimal, active),
            ci95_lower=_serialize_decimal(lower, active),
            ci95_upper=_serialize_decimal(upper, active),
            disposition=disposition,
        )


def qualify_mrl_0806_objective_budgets(
    authorization_raw: bytes,
    research_objective_raw: bytes,
    rq1_protocol_raw: bytes,
    *,
    repository_sha: str,
    repository_tree: str,
) -> MRL0806Qualification:
    """Produce deterministic untrusted objective/budget evidence from exact frozen artifacts."""
    authorization = _validate_authorization(authorization_raw)
    repository_sha = _require_git_sha(repository_sha, "repository_sha")
    repository_tree = _require_git_sha(repository_tree, "repository_tree")
    objective = build_mrl_0806_rq1_objective()
    if (
        objective.content_sha256 != _OBJECTIVE_SHA256
        or objective.semantic_bytes != research_objective_raw
    ):
        raise MRL0806ObjectiveBudgetsError(
            "research objective bytes do not match the frozen typed objective"
        )
    if hashlib.sha256(research_objective_raw).hexdigest() != _OBJECTIVE_SHA256:
        raise MRL0806ObjectiveBudgetsError(
            "research objective digest does not match frozen authority"
        )
    protocol = _parse_canonical_json_object(rq1_protocol_raw, label="RQ1 protocol")
    if hashlib.sha256(rq1_protocol_raw).hexdigest() != _PROTOCOL_SHA256:
        raise MRL0806ObjectiveBudgetsError("RQ1 protocol digest does not match frozen authority")
    _validate_protocol(protocol)
    frozen_artifacts = _require_object(authorization["frozen_artifacts"], label="frozen_artifacts")
    if frozen_artifacts["research_objective_sha256"] != _OBJECTIVE_SHA256:
        raise MRL0806ObjectiveBudgetsError("authorization objective identity drifted")
    if frozen_artifacts["rq1_protocol_sha256"] != _PROTOCOL_SHA256:
        raise MRL0806ObjectiveBudgetsError("authorization protocol identity drifted")

    receipt_bytes = canonical_json_bytes(
        {
            "authorization_sha256": hashlib.sha256(authorization_raw).hexdigest(),
            "candidate_id": _CANDIDATE,
            "experiment_id": _EXPERIMENT,
            "non_promotional": True,
            "promotion_authority_present": False,
            "repository_sha": repository_sha,
            "repository_tree": repository_tree,
            "research_objective_sha256": _OBJECTIVE_SHA256,
            "rq1_protocol_sha256": _PROTOCOL_SHA256,
            "schema_version": _RECEIPT_SCHEMA,
            "task_id": _TASK,
            "training_authorized": False,
            "weight_mutation_authorized": False,
        }
    )
    receipt_sha256 = hashlib.sha256(receipt_bytes).hexdigest()
    evidence_bytes = canonical_json_bytes(
        {
            "disposition": "PASS",
            "kind": _KIND,
            "payload": {
                "adaptive_query_budget": objective.adaptive_query_budget.to_dict(),
                "budget_exhaustion_disposition": objective.budget_exhaustion_disposition.value,
                "evaluation_tier_policy": objective.evaluation_tier_policy.to_dict(),
                "frozen_externally": True,
                "research_objective_sha256": _OBJECTIVE_SHA256,
                "resource_budget": objective.resource_budget.to_dict(),
                "tier_result_exposure_policy": [
                    item.to_dict() for item in objective.tier_result_exposure_policy
                ],
            },
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
            "subject_sha256": receipt_sha256,
            "task_id": _TASK,
        }
    )
    parsed = parse_mrl_real_preflight_evidence(evidence_bytes)
    if parsed.task_id != _TASK or parsed.subject_sha256 != receipt_sha256:
        raise MRL0806ObjectiveBudgetsError("produced MRL-0806 evidence failed semantic self-check")
    return MRL0806Qualification(
        freeze_receipt_bytes=receipt_bytes,
        evidence_bytes=evidence_bytes,
        research_objective_sha256=_OBJECTIVE_SHA256,
        rq1_protocol_sha256=_PROTOCOL_SHA256,
        freeze_receipt_sha256=receipt_sha256,
        evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest(),
    )


def verify_mrl_0806_bundle(
    authorization_raw: bytes,
    research_objective_raw: bytes,
    rq1_protocol_raw: bytes,
    *,
    repository_sha: str,
    repository_tree: str,
    freeze_receipt_bytes: bytes,
    evidence_bytes: bytes,
) -> MRL0806Qualification:
    """Recompute the bundle and require byte-identical supplied external evidence."""
    expected = qualify_mrl_0806_objective_budgets(
        authorization_raw,
        research_objective_raw,
        rq1_protocol_raw,
        repository_sha=repository_sha,
        repository_tree=repository_tree,
    )
    if freeze_receipt_bytes != expected.freeze_receipt_bytes:
        raise MRL0806ObjectiveBudgetsError("supplied MRL-0806 freeze receipt is not deterministic")
    if evidence_bytes != expected.evidence_bytes:
        raise MRL0806ObjectiveBudgetsError("supplied MRL-0806 evidence is not deterministic")
    return expected


def _validate_authorization(raw: bytes) -> dict[str, object]:
    document = _parse_canonical_json_object(raw, label="MRL-0806 authorization")
    if hashlib.sha256(raw).hexdigest() != _AUTHORIZATION_SHA256:
        raise MRL0806ObjectiveBudgetsError("authorization bytes do not match external authority")
    if document.get("schema_version") != _AUTH_SCHEMA or document.get("task_id") != _TASK:
        raise MRL0806ObjectiveBudgetsError("authorization schema/task identity is invalid")
    if document.get("authorization_state") != "AUTHORIZED" or document.get("scope") != _SCOPE:
        raise MRL0806ObjectiveBudgetsError("authorization state/scope is invalid")
    if document.get("candidate_id") != _CANDIDATE or document.get("experiment_id") != _EXPERIMENT:
        raise MRL0806ObjectiveBudgetsError("authorization campaign identity is invalid")
    if document.get("research_question") != _RESEARCH_QUESTION:
        raise MRL0806ObjectiveBudgetsError("authorization research question is invalid")
    expected_keys = {
        "authority_source",
        "authorization_id",
        "authorization_state",
        "authorized_base",
        "candidate_id",
        "experiment_id",
        "frozen_artifacts",
        "policy",
        "predecessor_evidence",
        "research_question",
        "schema_version",
        "scope",
        "task_id",
    }
    if set(document) != expected_keys:
        raise MRL0806ObjectiveBudgetsError("authorization has non-canonical key set")
    _validate_authority_source(
        _require_object(document["authority_source"], label="authority_source")
    )
    _validate_authorized_base(_require_object(document["authorized_base"], label="authorized_base"))
    predecessor = _require_object(
        document.get("predecessor_evidence"), label="predecessor_evidence"
    )
    if predecessor != _PREDECESSOR_EVIDENCE:
        raise MRL0806ObjectiveBudgetsError("authorization predecessor evidence drifted")
    frozen = _require_object(document.get("frozen_artifacts"), label="frozen_artifacts")
    expected_frozen = {
        "candidate_roster_sha256": _CANDIDATE_ROSTER_SHA256,
        "evaluation_contract_sha256": _EVALUATION_CONTRACT_SHA256,
        "evaluator_identity_sha256": _EVALUATOR_IDENTITY_SHA256,
        "research_objective_sha256": _OBJECTIVE_SHA256,
        "rq1_protocol_sha256": _PROTOCOL_SHA256,
        "sealed_tier3_identity_sha256": _SEALED_TIER3_IDENTITY_SHA256,
    }
    if frozen != expected_frozen:
        raise MRL0806ObjectiveBudgetsError("authorization frozen artifact identities drifted")
    policy = _require_object(document.get("policy"), label="policy")
    required_true = {
        "evidence_production_authorized",
        "objective_budget_freeze_authorized",
    }
    required_false = {
        "clinical_authority_present",
        "gpu_execution_authorized",
        "model_loading_authorized",
        "paid_compute_spend_authorized",
        "production_trust_registry_mutation_authorized",
        "promotion_authority_present",
        "release_authority_present",
        "scientific_model_execution_authorized",
        "tokenizer_loading_authorized",
        "training_authorized",
        "training_ready",
        "weight_mutation_authorized",
    }
    if set(policy) != required_true | required_false:
        raise MRL0806ObjectiveBudgetsError("authorization policy has non-canonical key set")
    if any(policy[key] is not True for key in required_true):
        raise MRL0806ObjectiveBudgetsError("required objective/evidence authority is absent")
    if any(policy[key] is not False for key in required_false):
        raise MRL0806ObjectiveBudgetsError("authorization grants prohibited execution authority")
    return document


def _validate_authority_source(source: dict[str, object]) -> None:
    expected = {
        "author_association",
        "author_login",
        "body_sha256",
        "created_at",
        "issue_node_id",
        "issue_number",
    }
    if set(source) != expected:
        raise MRL0806ObjectiveBudgetsError("authority_source has non-canonical key set")
    if source["author_association"] != "OWNER" or source["author_login"] != "TheHalfMoon":
        raise MRL0806ObjectiveBudgetsError("authorization is not owner authority")
    body_sha = source["body_sha256"]
    if type(body_sha) is not str or _SHA256.fullmatch(body_sha) is None:
        raise MRL0806ObjectiveBudgetsError("authority body SHA-256 is invalid")
    issue_number = source["issue_number"]
    if type(issue_number) is not int or issue_number <= 0:
        raise MRL0806ObjectiveBudgetsError("authority issue number is invalid")
    for field_name in ("created_at", "issue_node_id"):
        value = source[field_name]
        if type(value) is not str or not value or value.strip() != value:
            raise MRL0806ObjectiveBudgetsError(f"authority {field_name} is invalid")


def _validate_authorized_base(base: dict[str, object]) -> None:
    expected = {
        "main_sha",
        "main_tree",
        "post_merge_ci_run",
        "post_merge_ci_success",
        "post_merge_codeql_run",
        "post_merge_codeql_success",
        "post_merge_optional_extras_run",
        "post_merge_optional_extras_success",
    }
    if set(base) != expected:
        raise MRL0806ObjectiveBudgetsError("authorized_base has non-canonical key set")
    if base["main_sha"] != _EXPECTED_BASE_SHA or base["main_tree"] != _EXPECTED_BASE_TREE:
        raise MRL0806ObjectiveBudgetsError("authorization predecessor Git identity drifted")
    for run_field in (
        "post_merge_ci_run",
        "post_merge_codeql_run",
        "post_merge_optional_extras_run",
    ):
        value = base[run_field]
        if type(value) is not int or value <= 0:
            raise MRL0806ObjectiveBudgetsError(f"{run_field} must be a positive integer")
    for success_field in (
        "post_merge_ci_success",
        "post_merge_codeql_success",
        "post_merge_optional_extras_success",
    ):
        if base[success_field] is not True:
            raise MRL0806ObjectiveBudgetsError(f"{success_field} must be true")


def _validate_protocol(document: dict[str, object]) -> None:
    if document.get("research_question") != _RESEARCH_QUESTION:
        raise MRL0806ObjectiveBudgetsError("protocol research question drifted")
    if document.get("experiment_id") != _EXPERIMENT:
        raise MRL0806ObjectiveBudgetsError("protocol experiment identity drifted")
    if document.get("candidate_roster_sha256") != _CANDIDATE_ROSTER_SHA256:
        raise MRL0806ObjectiveBudgetsError("protocol candidate roster identity drifted")
    if document.get("corpus_sha256") != _CORPUS_SHA256:
        raise MRL0806ObjectiveBudgetsError("protocol corpus identity drifted")
    if document.get("evaluation_contract_sha256") != _EVALUATION_CONTRACT_SHA256:
        raise MRL0806ObjectiveBudgetsError("protocol evaluation contract identity drifted")
    if document.get("evaluator_identity_sha256") != _EVALUATOR_IDENTITY_SHA256:
        raise MRL0806ObjectiveBudgetsError("protocol evaluator identity drifted")
    if document.get("sealed_tier3_bytes_sha256") != _SEALED_BYTES_SHA256:
        raise MRL0806ObjectiveBudgetsError("protocol sealed bytes identity drifted")
    if document.get("preflight_evidence_sha256") != _PREDECESSOR_EVIDENCE:
        raise MRL0806ObjectiveBudgetsError("protocol predecessor evidence drifted")
    if document.get("seeds") != [17, 29, 43]:
        raise MRL0806ObjectiveBudgetsError("protocol seed set drifted")
    if document.get("generation_call_count") != 384:
        raise MRL0806ObjectiveBudgetsError("protocol generation-call ceiling drifted")
    if (
        document.get("training_authorized") is not False
        or document.get("weight_mutation_authorized") is not False
    ):
        raise MRL0806ObjectiveBudgetsError("protocol must not grant training or weight mutation")
    configuration_counts = _require_object(
        document.get("configuration_count_by_tier"),
        label="configuration_count_by_tier",
    )
    if configuration_counts != {"REPLICATION": 24, "SEALED": 24, "SEARCH": 24}:
        raise MRL0806ObjectiveBudgetsError("protocol configuration schedule drifted")
    item_counts = _require_object(document.get("item_count_by_tier"), label="item_count_by_tier")
    if item_counts != {"REPLICATION": 4, "SEALED": 4, "SEARCH": 8}:
        raise MRL0806ObjectiveBudgetsError("protocol item schedule drifted")
    confirmation = _require_object(
        document.get("sealed_confirmation_policy"),
        label="sealed_confirmation_policy",
    )
    if confirmation != {
        "missing_candidate_disposition": "INCONCLUSIVE_INCOMPLETE_CONFIRMATORY_SET",
        "post_result_candidate_substitution": False,
        "required_candidate_count": 2,
        "required_candidate_roles": [
            "PREFERRED_FOUNDATION_CANDIDATE",
            "PRIMARY_CHALLENGER",
        ],
        "score_ranked_selection": False,
        "tier2_completion_required_for_all_candidates": True,
        "tier2_result_dependent_sealed_exclusion_allowed": False,
        "type": "ALL_CANDIDATES_PREDECLARED_CONFIRMATORY_V1",
    }:
        raise MRL0806ObjectiveBudgetsError("sealed confirmatory candidate policy drifted")
    authority = _require_object(
        document.get("scientific_inference_authority"),
        label="scientific_inference_authority",
    )
    if authority != {
        "cross_model_pooling_for_terminal_claim": False,
        "replication_role": "INDEPENDENT_REPLICATION_WITHOUT_TERMINAL_CLAIM_AUTHORITY",
        "replication_tier_terminal_claim_authority": False,
        "sealed_tier_terminal_claim_authority": True,
        "search_tier_terminal_claim_authority": False,
        "terminal_claim_requires_all_predeclared_candidates": True,
        "terminal_scientific_decision_tier": "SEALED",
    }:
        raise MRL0806ObjectiveBudgetsError("scientific inference tier authority drifted")
    statistics = _require_object(document.get("statistical_analysis"), label="statistical_analysis")
    if statistics.get("cross_model_pooling") != "FORBIDDEN_FOR_TERMINAL_RQ1_CLAIM":
        raise MRL0806ObjectiveBudgetsError("protocol cross-model pooling rule drifted")
    if (
        statistics.get("constraint_delta_role")
        != "SECONDARY_EFFECT_ESTIMATE_NOT_REQUIRED_FOR_SUPPORT"
    ):
        raise MRL0806ObjectiveBudgetsError("protocol constraint-delta role drifted")


def _parse_canonical_json_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MRL0806ObjectiveBudgetsError(f"{label} is not valid JSON") from exc
    if type(value) is not dict:
        raise MRL0806ObjectiveBudgetsError(f"{label} must be one exact object")
    document = cast(dict[str, object], value)
    try:
        canonical = canonical_json_bytes(document)
    except (CanonicalContractError, TypeError, ValueError) as exc:
        raise MRL0806ObjectiveBudgetsError(f"{label} is outside canonical JSON domain") from exc
    if canonical != raw:
        raise MRL0806ObjectiveBudgetsError(f"{label} bytes are not canonical")
    return document


def _require_object(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        raise MRL0806ObjectiveBudgetsError(f"{label} must be one exact object")
    return cast(dict[str, object], value)


def _require_git_sha(value: object, label: str) -> str:
    if type(value) is not str or _GIT_SHA.fullmatch(value) is None:
        raise MRL0806ObjectiveBudgetsError(f"{label} must be 40 lowercase hex")
    return value


def _serialize_decimal(value: Decimal, context: Context) -> str:
    quantized = value.quantize(_DECIMAL_PLACES, rounding=ROUND_HALF_EVEN, context=context)
    if quantized == 0:
        quantized = abs(quantized)
    return format(quantized, "f")
