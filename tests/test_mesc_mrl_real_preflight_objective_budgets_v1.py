"""Adversarial MRL-0806 objective-budget evidence contract tests."""

from __future__ import annotations

import copy

import pytest

from medscale.mesc import _mrl_real_preflight_evidence_v1 as evidence
from medscale.mesc._canonical_json_v1 import canonical_json_bytes

_SHA_A = "a" * 64
_SHA_F = "f" * 64
_KIND = "mesc.mrl.real_preflight.objective_budgets.v1"


def _payload() -> dict[str, object]:
    return {
        "adaptive_query_budget": {
            "tier_1_queries": 3,
            "tier_2_queries": 1,
        },
        "budget_exhaustion_disposition": "BLOCKED",
        "evaluation_tier_policy": {"allowed_tiers": [1, 2, 3]},
        "frozen_externally": True,
        "research_objective_sha256": _SHA_A,
        "resource_budget": {
            "compute_seconds": 60,
            "evaluator_invocations": 4,
            "generated_tokens": 4096,
            "input_tokens": 4096,
            "known_failure_retries": 0,
            "max_experiments": 4,
            "monetary_cost_microunits": 0,
            "retries": 1,
            "storage_bytes": 1024,
            "wall_clock_seconds": 60,
        },
        "tier_result_exposure_policy": [
            {
                "allowed_result_fields": ["content_quality", "structural_validity"],
                "max_exposures": 3,
                "tier": 1,
            },
            {
                "allowed_result_fields": ["content_quality", "structural_validity"],
                "max_exposures": 1,
                "tier": 2,
            },
            {
                "allowed_result_fields": [],
                "max_exposures": 0,
                "tier": 3,
            },
        ],
    }


def _raw(payload: dict[str, object]) -> bytes:
    return canonical_json_bytes(
        {
            "disposition": "PASS",
            "kind": _KIND,
            "payload": payload,
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
            "subject_sha256": _SHA_F,
            "task_id": "MRL-0806",
        }
    )


def _nested(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload[key]
    assert isinstance(value, dict)
    return value


def _exposures(payload: dict[str, object]) -> list[dict[str, object]]:
    value = payload["tier_result_exposure_policy"]
    assert isinstance(value, list)
    assert all(isinstance(item, dict) for item in value)
    return value  # type: ignore[return-value]


def test_lossless_objective_budget_payload_parses_but_is_untrusted_by_default() -> None:
    raw = _raw(_payload())
    parsed = evidence.parse_mrl_real_preflight_evidence(raw)
    assert parsed.task_id == "MRL-0806"
    assert parsed.kind == _KIND

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="not trusted"):
        evidence.admit_mrl_real_preflight_evidence(raw, expected_task_id="MRL-0806")


def test_resource_not_applicable_null_semantics_are_preserved() -> None:
    payload = _payload()
    resource = _nested(payload, "resource_budget")
    resource["compute_seconds"] = None
    resource["input_tokens"] = None
    resource["generated_tokens"] = None
    resource["monetary_cost_microunits"] = None
    resource["evaluator_invocations"] = None

    parsed = evidence.parse_mrl_real_preflight_evidence(_raw(payload))
    assert parsed.task_id == "MRL-0806"


def test_legacy_aggregate_budget_schema_is_rejected() -> None:
    legacy = {
        "adaptive_query_budget": 3,
        "compute_units": 1,
        "frozen_externally": True,
        "monetary_budget_microunits": 0,
        "research_objective_sha256": _SHA_A,
        "result_exposure_budget": 2,
        "storage_bytes": 1024,
        "token_budget": 4096,
        "wall_clock_seconds": 60,
    }

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="exact canonical key set"):
        evidence.parse_mrl_real_preflight_evidence(_raw(legacy))


def test_resource_budget_rejects_known_failure_retries_above_retries() -> None:
    payload = _payload()
    resource = _nested(payload, "resource_budget")
    resource["retries"] = 1
    resource["known_failure_retries"] = 2

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="resource_budget"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_resource_budget_rejects_boolean_numeric_alias() -> None:
    payload = _payload()
    resource = _nested(payload, "resource_budget")
    resource["max_experiments"] = True

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="resource_budget"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_evaluation_tiers_must_be_unique_and_strictly_ascending() -> None:
    payload = _payload()
    policy = _nested(payload, "evaluation_tier_policy")
    policy["allowed_tiers"] = [2, 1, 3]

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="evaluation_tier_policy"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_evaluation_tier_rejects_boolean_alias() -> None:
    payload = _payload()
    policy = _nested(payload, "evaluation_tier_policy")
    policy["allowed_tiers"] = [True, 2, 3]

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="integer evaluation tier"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_tier_result_exposure_policy_must_cover_exact_allowed_tiers() -> None:
    payload = _payload()
    payload["tier_result_exposure_policy"] = copy.deepcopy(_exposures(payload)[:-1])

    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="define exactly every allowed evaluation tier",
    ):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_tier_result_exposure_policy_rejects_unsorted_or_duplicate_tiers() -> None:
    payload = _payload()
    exposures = copy.deepcopy(_exposures(payload))
    exposures[0], exposures[1] = exposures[1], exposures[0]
    payload["tier_result_exposure_policy"] = exposures

    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="unique and strictly ascending by tier",
    ):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_sealed_tier_cannot_expose_iterative_results() -> None:
    payload = _payload()
    exposures = _exposures(payload)
    exposures[2]["max_exposures"] = 1
    exposures[2]["allowed_result_fields"] = ["structural_validity"]

    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="tier_result_exposure_policy",
    ):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_result_fields_must_be_sorted_unique() -> None:
    payload = _payload()
    exposures = _exposures(payload)
    exposures[0]["allowed_result_fields"] = ["structural_validity", "content_quality"]

    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="tier_result_exposure_policy",
    ):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_tier_1_queries_require_search_tier() -> None:
    payload = _payload()
    policy = _nested(payload, "evaluation_tier_policy")
    policy["allowed_tiers"] = [2, 3]
    payload["tier_result_exposure_policy"] = copy.deepcopy(_exposures(payload)[1:])

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="tier_1_queries"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_tier_2_queries_require_replication_tier() -> None:
    payload = _payload()
    policy = _nested(payload, "evaluation_tier_policy")
    policy["allowed_tiers"] = [1, 3]
    exposures = _exposures(payload)
    payload["tier_result_exposure_policy"] = [
        copy.deepcopy(exposures[0]),
        copy.deepcopy(exposures[2]),
    ]

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="tier_2_queries"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_budget_exhaustion_disposition_must_be_blocked() -> None:
    payload = _payload()
    payload["budget_exhaustion_disposition"] = "CONTINUE"

    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="budget_exhaustion_disposition",
    ):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))
