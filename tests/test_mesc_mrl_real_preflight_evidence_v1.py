"""Adversarial tests for MRL-8 real-preflight evidence envelopes."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

import pytest

from medscale.mesc import _mrl_real_preflight_evidence_v1 as evidence
from medscale.mesc._canonical_json_v1 import canonical_json_bytes

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_SHA_D = "d" * 64
_SHA_E = "e" * 64
_SHA_F = "f" * 64
_GIT_A = "1" * 40


def _model_weights() -> dict[str, object]:
    return {
        "access_authorization_sha256": _SHA_A,
        "artifact_identity_sha256": _SHA_B,
        "asset_custody_sha256": _SHA_C,
        "asset_present": True,
        "model_id": "example/model",
        "revision": _GIT_A,
        "weights_sha256": _SHA_D,
    }


def _corpus_rights() -> dict[str, object]:
    return {
        "access_authorization_sha256": _SHA_A,
        "byte_count": 123,
        "corpus_id": "example/corpus",
        "corpus_present": True,
        "corpus_sha256": _SHA_B,
        "provenance_sha256": _SHA_C,
        "rights_disposition": "PASS",
        "rights_evidence_sha256": _SHA_D,
    }


def _isolation() -> dict[str, object]:
    return {
        "contamination_disposition": "PASS",
        "corpus_sha256": _SHA_A,
        "decontamination_report_sha256": _SHA_B,
        "heldout_evaluation_sha256": _SHA_C,
        "lineage_report_sha256": _SHA_D,
        "sealed_evaluation_excluded_from_training": True,
    }


def _runtime() -> dict[str, object]:
    return {
        "network_accessed": False,
        "platform_qualified": True,
        "remote_code_allowed": False,
        "runtime_identity_sha256": _SHA_A,
        "runtime_qualification_receipt_sha256": _SHA_B,
        "smoke_receipt_sha256": _SHA_C,
    }


def _training_authorization() -> dict[str, object]:
    return {
        "authorization_artifact_sha256": _SHA_A,
        "authorization_disposition": "AUTHORIZED",
        "authorization_subject_sha256": _SHA_B,
        "authorization_trust_registry_sha256": _SHA_C,
        "real_training_authorized": True,
        "training_authorization_receipt_sha256": _SHA_D,
    }


def _objective_budgets() -> dict[str, object]:
    return {
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


def _evaluators() -> dict[str, object]:
    return {
        "evaluation_contract_sha256": _SHA_A,
        "evaluator_identity_sha256": _SHA_B,
        "non_promotional": True,
        "promotion_authority_present": False,
        "sealed_tier3_identity_sha256": _SHA_C,
    }


def _sandbox() -> dict[str, object]:
    return {
        "allowed_mutation_paths_sha256": _SHA_A,
        "mutation_paths_frozen": True,
        "network_policy_enforced": True,
        "network_policy_sha256": _SHA_B,
        "output_destinations_frozen": True,
        "output_destinations_sha256": _SHA_C,
        "runtime_sandbox_evidence_sha256": _SHA_D,
        "sandbox_policy_sha256": _SHA_E,
        "sandbox_qualified": True,
        "stop_conditions_frozen": True,
        "stop_conditions_sha256": _SHA_F,
    }


_PAYLOADS: tuple[
    tuple[evidence.MRLRealPreflightTask, str, Callable[[], dict[str, object]]],
    ...,
] = (
    ("MRL-0801", "mesc.mrl.real_preflight.model_weights.v1", _model_weights),
    ("MRL-0802", "mesc.mrl.real_preflight.corpus_rights.v1", _corpus_rights),
    ("MRL-0803", "mesc.mrl.real_preflight.isolation.v1", _isolation),
    ("MRL-0804", "mesc.mrl.real_preflight.runtime.v1", _runtime),
    (
        "MRL-0805",
        "mesc.mrl.real_preflight.training_authorization.v1",
        _training_authorization,
    ),
    ("MRL-0806", "mesc.mrl.real_preflight.objective_budgets.v1", _objective_budgets),
    ("MRL-0807", "mesc.mrl.real_preflight.evaluators.v1", _evaluators),
    ("MRL-0808", "mesc.mrl.real_preflight.sandbox.v1", _sandbox),
)


def _document(
    task_id: evidence.MRLRealPreflightTask,
    kind: str,
    payload: dict[str, object],
) -> dict[str, object]:
    return {
        "disposition": "PASS",
        "kind": kind,
        "payload": payload,
        "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
        "subject_sha256": _SHA_F,
        "task_id": task_id,
    }


def _raw(
    task_id: evidence.MRLRealPreflightTask,
    kind: str,
    payload: dict[str, object],
) -> bytes:
    return canonical_json_bytes(_document(task_id, kind, payload))


@pytest.mark.parametrize(("task_id", "kind", "factory"), _PAYLOADS)
def test_all_real_preflight_roles_parse_but_are_not_trusted_by_default(
    task_id: evidence.MRLRealPreflightTask,
    kind: str,
    factory: Callable[[], dict[str, object]],
) -> None:
    raw = _raw(task_id, kind, factory())
    parsed = evidence.parse_mrl_real_preflight_evidence(raw)

    assert parsed.task_id == task_id
    assert parsed.kind == kind
    assert parsed.subject_sha256 == _SHA_F
    assert parsed.evidence_sha256 == hashlib.sha256(raw).hexdigest()

    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="not trusted",
    ):
        evidence.admit_mrl_real_preflight_evidence(raw, expected_task_id=task_id)


def test_exact_trust_digest_admits_only_the_matching_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _raw("MRL-0801", _PAYLOADS[0][1], _model_weights())
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(
        evidence,
        "TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256",
        frozenset({digest}),
    )

    admitted = evidence.admit_mrl_real_preflight_evidence(
        raw,
        expected_task_id="MRL-0801",
    )
    assert admitted.evidence_sha256 == digest

    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="does not match the expected task",
    ):
        evidence.admit_mrl_real_preflight_evidence(
            raw,
            expected_task_id="MRL-0802",
        )


def test_noncanonical_json_is_rejected() -> None:
    document = _document("MRL-0801", _PAYLOADS[0][1], _model_weights())
    raw = json.dumps(document, indent=2, sort_keys=True).encode("utf-8")

    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="not canonical JSON",
    ):
        evidence.parse_mrl_real_preflight_evidence(raw)


def test_duplicate_json_member_is_rejected() -> None:
    raw = (
        b'{"disposition":"PASS","disposition":"PASS","kind":'
        b'"mesc.mrl.real_preflight.model_weights.v1","payload":{},'
        b'"schema_version":"MRL-REAL-PREFLIGHT-EVIDENCE-V1",'
        b'"subject_sha256":"' + _SHA_F.encode("ascii") + b'","task_id":"MRL-0801"}\n'
    )
    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="duplicate",
    ):
        evidence.parse_mrl_real_preflight_evidence(raw)


def test_task_kind_mismatch_is_rejected() -> None:
    raw = _raw("MRL-0801", _PAYLOADS[1][1], _model_weights())
    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="kind does not match",
    ):
        evidence.parse_mrl_real_preflight_evidence(raw)


@pytest.mark.parametrize(
    ("task_id", "kind", "factory", "field_name", "bad_value", "message"),
    (
        (
            "MRL-0801",
            "mesc.mrl.real_preflight.model_weights.v1",
            _model_weights,
            "asset_present",
            False,
            "asset_present",
        ),
        (
            "MRL-0802",
            "mesc.mrl.real_preflight.corpus_rights.v1",
            _corpus_rights,
            "rights_disposition",
            "BLOCKED",
            "rights_disposition",
        ),
        (
            "MRL-0803",
            "mesc.mrl.real_preflight.isolation.v1",
            _isolation,
            "sealed_evaluation_excluded_from_training",
            False,
            "sealed_evaluation_excluded_from_training",
        ),
        (
            "MRL-0804",
            "mesc.mrl.real_preflight.runtime.v1",
            _runtime,
            "platform_qualified",
            False,
            "platform_qualified",
        ),
        (
            "MRL-0805",
            "mesc.mrl.real_preflight.training_authorization.v1",
            _training_authorization,
            "real_training_authorized",
            False,
            "real_training_authorized",
        ),
        (
            "MRL-0806",
            "mesc.mrl.real_preflight.objective_budgets.v1",
            _objective_budgets,
            "frozen_externally",
            False,
            "frozen_externally",
        ),
        (
            "MRL-0807",
            "mesc.mrl.real_preflight.evaluators.v1",
            _evaluators,
            "promotion_authority_present",
            True,
            "promotion_authority_present",
        ),
        (
            "MRL-0808",
            "mesc.mrl.real_preflight.sandbox.v1",
            _sandbox,
            "sandbox_qualified",
            False,
            "sandbox_qualified",
        ),
    ),
)
def test_role_specific_fail_closed_semantics(
    task_id: evidence.MRLRealPreflightTask,
    kind: str,
    factory: Callable[[], dict[str, object]],
    field_name: str,
    bad_value: object,
    message: str,
) -> None:
    payload = factory()
    payload[field_name] = bad_value
    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match=message):
        evidence.parse_mrl_real_preflight_evidence(_raw(task_id, kind, payload))


def test_extra_payload_field_is_rejected() -> None:
    payload = _model_weights()
    payload["unexpected"] = _SHA_A
    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="exact canonical key set",
    ):
        evidence.parse_mrl_real_preflight_evidence(
            _raw("MRL-0801", _PAYLOADS[0][1], payload)
        )


def test_malformed_trust_registry_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        evidence,
        "TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256",
        frozenset({"malformed"}),
    )
    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="trusted evidence digest",
    ):
        evidence.mrl_real_preflight_trust_snapshot()


def test_trust_registry_identity_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    first = "1" * 64
    second = "2" * 64
    monkeypatch.setattr(
        evidence,
        "TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256",
        frozenset({second, first}),
    )
    snapshot = evidence.mrl_real_preflight_trust_snapshot()
    expected = canonical_json_bytes(
        {
            "registry_version": "MRL-REAL-PREFLIGHT-EVIDENCE-TRUST-V1",
            "trusted_evidence_sha256": [first, second],
        }
    )
    assert snapshot.registry_sha256 == hashlib.sha256(expected).hexdigest()
