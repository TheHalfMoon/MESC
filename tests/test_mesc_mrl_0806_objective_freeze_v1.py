"""Adversarial MRL-0806 RQ1 objective/budget freeze tests."""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_0806_objective_budgets_v1 import (
    MRL0806ObjectiveBudgetsError,
    MRL0806Qualification,
    build_mrl_0806_rq1_objective,
    paired_seed_summary,
    qualify_mrl_0806_objective_budgets,
    verify_mrl_0806_bundle,
)
from medscale.mesc._mrl_hard_medical_non_regression_v1 import (
    evaluate_hard_medical_non_regression,
)
from medscale.mesc._mrl_real_preflight_evidence_v1 import (
    TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256,
    admit_mrl_real_preflight_evidence,
    parse_mrl_real_preflight_evidence,
)
from medscale.mesc._mrl_research_objective_v1 import EvaluationTier
from medscale.mesc._mrl_sealed_evaluation_evidence_v1 import (
    SealedMetricEvidence,
    build_sealed_evaluation_evidence_report,
)
from medscale.mesc._mrl_sealed_evaluation_interface_v1 import (
    build_sealed_evaluation_request,
    record_sealed_evidence_handoff,
)
from medscale.mesc._mrl_tier_evaluation_contract_v1 import TierEvaluationContract

_ROOT = Path(__file__).resolve().parents[1]
_AUTH = _ROOT / "specs/mesc-experiment-0/mrl-0806-objective-budgets-authorization-v1.json"
_OBJECTIVE = _ROOT / "specs/mesc-experiment-0/mrl-0806-rq1-objective-v1.json"
_PROTOCOL = _ROOT / "specs/mesc-experiment-0/mrl-0806-rq1-protocol-v1.json"
_SLOT = _ROOT / "specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0806.json"
_INDEX = _ROOT / "specs/mesc-research-loop-v1/real-preflight-evidence-index-v1.json"
_TASKS = _ROOT / "specs/mesc-research-loop-v1/tasks.md"
_OBJECTIVE_SHA256 = "53149a0966e88eaa0c584f3f115e624444a8e479fc4bb45adf5ce727d18ed621"
_PROTOCOL_SHA256 = "8a2601a76077413d65c42ff68a65f118f7479350952b4b3e45785593ae11e494"


def _inputs() -> tuple[bytes, bytes, bytes]:
    return _AUTH.read_bytes(), _OBJECTIVE.read_bytes(), _PROTOCOL.read_bytes()


def _candidate() -> MRL0806Qualification:
    return qualify_mrl_0806_objective_budgets(
        *_inputs(),
        repository_sha="a" * 40,
        repository_tree="b" * 40,
    )


def test_authorization_explicitly_denies_clinical_authority() -> None:
    authorization = json.loads(_AUTH.read_bytes())
    assert authorization["policy"]["clinical_authority_present"] is False


def test_frozen_objective_and_protocol_match_exact_authorized_identities() -> None:
    objective = build_mrl_0806_rq1_objective()
    assert objective.semantic_bytes == _OBJECTIVE.read_bytes()
    assert objective.content_sha256 == _OBJECTIVE_SHA256
    assert hashlib.sha256(_PROTOCOL.read_bytes()).hexdigest() == _PROTOCOL_SHA256
    protocol = json.loads(_PROTOCOL.read_bytes())
    assert protocol["seeds"] == [17, 29, 43]
    assert protocol["generation_call_count"] == 384
    assert protocol["sealed_confirmation_policy"] == {
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
    }
    assert protocol["scientific_inference_authority"] == {
        "cross_model_pooling_for_terminal_claim": False,
        "replication_role": "INDEPENDENT_REPLICATION_WITHOUT_TERMINAL_CLAIM_AUTHORITY",
        "replication_tier_terminal_claim_authority": False,
        "sealed_tier_terminal_claim_authority": True,
        "search_tier_terminal_claim_authority": False,
        "terminal_claim_requires_all_predeclared_candidates": True,
        "terminal_scientific_decision_tier": "SEALED",
    }
    assert protocol["configuration_count_by_tier"] == {
        "REPLICATION": 24,
        "SEALED": 24,
        "SEARCH": 24,
    }
    assert "positive structural delta is not required" in protocol["outcome_policy"]["SUPPORTS_RQ1"]
    assert "predicted_count=1" in protocol["outcome_policy"]["FALSIFIED_CONTENT_DEGRADATION"]
    assert canonical_json_bytes(protocol) == _PROTOCOL.read_bytes()


def test_resource_query_and_exposure_budgets_are_exact() -> None:
    objective = build_mrl_0806_rq1_objective()
    assert objective.resource_budget.to_dict() == {
        "compute_seconds": 86_400,
        "evaluator_invocations": 768,
        "generated_tokens": 196_608,
        "input_tokens": 786_432,
        "known_failure_retries": 0,
        "max_experiments": 72,
        "monetary_cost_microunits": 0,
        "retries": 0,
        "storage_bytes": 214_748_364_800,
        "wall_clock_seconds": 86_400,
    }
    assert objective.adaptive_query_budget.to_dict() == {
        "tier_1_queries": 24,
        "tier_2_queries": 24,
    }
    assert [item.to_dict() for item in objective.tier_result_exposure_policy] == [
        {
            "allowed_result_fields": ["content_quality", "structural_validity"],
            "max_exposures": 1,
            "tier": 1,
        },
        {
            "allowed_result_fields": ["content_quality", "structural_validity"],
            "max_exposures": 1,
            "tier": 2,
        },
        {"allowed_result_fields": [], "max_exposures": 0, "tier": 3},
    ]


def test_hard_guardrails_bind_only_sealed_metrics() -> None:
    objective = build_mrl_0806_rq1_objective()
    tiers = {metric.metric_id: metric.tier for metric in objective.evaluation_metrics}
    assert len(objective.hard_guardrails) == 2
    assert all(
        tiers[floor.metric_id] is EvaluationTier.SEALED for floor in objective.hard_guardrails
    )
    assert all("replication" not in floor.metric_id for floor in objective.hard_guardrails)


def test_frozen_objective_is_compatible_with_canonical_hard_medical_gate() -> None:
    objective = build_mrl_0806_rq1_objective()
    contract = TierEvaluationContract(objective=objective, tier=EvaluationTier.SEALED)
    request = build_sealed_evaluation_request(
        contract,
        candidate_sha256="c" * 64,
        source_receipt_sha256="d" * 64,
    )
    handoff = record_sealed_evidence_handoff(request, "e" * 64)
    evidence = tuple(
        SealedMetricEvidence(
            metric_id=metric.metric_id,
            evaluator_id=metric.evaluator_id,
            value_decimal="1",
            evidence_artifact_sha256=hashlib.sha256(metric.metric_id.encode()).hexdigest(),
        )
        for metric in objective.evaluation_metrics
        if metric.tier is EvaluationTier.SEALED
    )
    report = build_sealed_evaluation_evidence_report(contract, request, handoff, evidence)
    gates = evaluate_hard_medical_non_regression(objective, report)
    assert gates.all_hard_gates_satisfied is True
    assert gates.violated_floor_ids == ()


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (
            (Fraction(1, 4), Fraction(1, 4), Fraction(1, 4)),
            {
                "ci95_lower": "0.250000000000",
                "ci95_upper": "0.250000000000",
                "disposition": "POSITIVE",
                "mean": "0.250000000000",
            },
        ),
        (
            (Fraction(-1, 8), Fraction(0), Fraction(1, 8)),
            {
                "ci95_lower": "-0.310517213965",
                "ci95_upper": "0.310517213965",
                "disposition": "NO_DIFFERENCE_WITHIN_SEED_VARIANCE",
                "mean": "0.000000000000",
            },
        ),
        (
            (Fraction(-1, 2), Fraction(-3, 8), Fraction(-1, 4)),
            {
                "ci95_lower": "-0.685517213965",
                "ci95_upper": "-0.064482786035",
                "disposition": "NEGATIVE",
                "mean": "-0.375000000000",
            },
        ),
    ],
)
def test_paired_seed_summary_is_frozen_exact_decimal(
    values: tuple[Fraction, Fraction, Fraction], expected: dict[str, str]
) -> None:
    assert paired_seed_summary(values).to_dict() == expected


def test_paired_seed_summary_rejects_wrong_arity_or_non_fraction() -> None:
    with pytest.raises(MRL0806ObjectiveBudgetsError, match="exactly three"):
        paired_seed_summary((Fraction(1), Fraction(2)))  # type: ignore[arg-type]
    with pytest.raises(MRL0806ObjectiveBudgetsError, match="exactly three"):
        paired_seed_summary((Fraction(1), Fraction(2), 3))  # type: ignore[arg-type]


def test_producer_is_deterministic_and_evidence_is_untrusted_by_default() -> None:
    first = _candidate()
    second = _candidate()
    assert first.freeze_receipt_bytes == second.freeze_receipt_bytes
    assert first.evidence_bytes == second.evidence_bytes
    assert first.evidence_sha256 == second.evidence_sha256
    parsed = parse_mrl_real_preflight_evidence(first.evidence_bytes)
    assert parsed.task_id == "MRL-0806"
    assert first.evidence_sha256 not in TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256
    with pytest.raises(Exception, match="not trusted"):
        admit_mrl_real_preflight_evidence(
            first.evidence_bytes,
            expected_task_id="MRL-0806",
        )


def test_bundle_verification_recomputes_byte_identical_outputs() -> None:
    result = _candidate()
    verified = verify_mrl_0806_bundle(
        *_inputs(),
        repository_sha="a" * 40,
        repository_tree="b" * 40,
        freeze_receipt_bytes=result.freeze_receipt_bytes,
        evidence_bytes=result.evidence_bytes,
    )
    assert verified.evidence_sha256 == result.evidence_sha256


def test_changed_objective_protocol_or_authorization_fail_closed() -> None:
    authorization, objective, protocol = _inputs()
    changed_objective = objective.replace(b'"objective_id"', b'"objective_ix"', 1)
    with pytest.raises(MRL0806ObjectiveBudgetsError):
        qualify_mrl_0806_objective_budgets(
            authorization,
            changed_objective,
            protocol,
            repository_sha="a" * 40,
            repository_tree="b" * 40,
        )
    protocol_doc = json.loads(protocol)
    protocol_doc["seeds"] = [17, 29, 47]
    with pytest.raises(MRL0806ObjectiveBudgetsError, match="protocol digest"):
        qualify_mrl_0806_objective_budgets(
            authorization,
            objective,
            canonical_json_bytes(protocol_doc),
            repository_sha="a" * 40,
            repository_tree="b" * 40,
        )
    auth_doc = json.loads(authorization)
    auth_doc["authorization_state"] = "REVOKED"
    with pytest.raises(MRL0806ObjectiveBudgetsError, match="authorization bytes"):
        qualify_mrl_0806_objective_budgets(
            canonical_json_bytes(auth_doc),
            objective,
            protocol,
            repository_sha="a" * 40,
            repository_tree="b" * 40,
        )


def test_producer_stage_does_not_require_permanent_absence_of_later_admission() -> None:
    candidate = _candidate()
    candidate_digest = candidate.evidence_sha256
    tasks = _TASKS.read_text(encoding="utf-8")
    unchecked = "- [ ] **MRL-0806 — Freeze real research objective and all budgets**"
    checked = "- [x] **MRL-0806 — Freeze real research objective and all budgets**"
    index = json.loads(_INDEX.read_bytes())
    rows = [row for row in index["records"] if row["task_id"] == "MRL-0806"]
    slot_bytes = _SLOT.read_bytes()
    slot_document = json.loads(slot_bytes)
    if slot_document.get("state") == "ABSENT":
        assert slot_document == {
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-SLOT-V1",
            "state": "ABSENT",
            "task_id": "MRL-0806",
        }
        assert tasks.count(unchecked) == 1
        assert tasks.count(checked) == 0
        assert rows == []
        assert candidate_digest not in TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256
        return
    admitted = parse_mrl_real_preflight_evidence(slot_bytes)
    admitted_digest = hashlib.sha256(slot_bytes).hexdigest()
    assert admitted.task_id == "MRL-0806"
    assert admitted.kind == "mesc.mrl.real_preflight.objective_budgets.v1"
    assert admitted_digest in TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256
    assert admitted_digest != candidate_digest
    assert tasks.count(unchecked) == 0
    assert tasks.count(checked) == 1
    assert rows == [
        {
            "evidence_path": "specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0806.json",
            "evidence_sha256": admitted_digest,
            "task_id": "MRL-0806",
        }
    ]
