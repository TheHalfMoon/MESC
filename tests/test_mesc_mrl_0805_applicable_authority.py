"""Regression tests for MRL-0805 applicable execution authority semantics."""

from __future__ import annotations

import hashlib

import pytest

from medscale.mesc import _mrl_real_preflight_evidence_v1 as evidence
from medscale.mesc import _training_authorization_trust_v1 as authorization_trust
from medscale.mesc._canonical_json_v1 import canonical_json_bytes

_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_NO_TRAINING_KIND = "mesc.mrl.real_preflight.no_training_evaluation_authority.v1"


def _no_training_authority() -> dict[str, object]:
    return {
        "authorization_artifact_sha256": _SHA_A,
        "authorization_disposition": "AUTHORIZED",
        "authorization_scope": "NO_TRAINING_EVALUATION",
        "authorization_subject_sha256": _SHA_B,
        "evaluation_execution_authorized": True,
        "execution_authority_receipt_sha256": _SHA_C,
        "real_training_authorized": False,
        "training_prohibited": True,
    }


def _raw(payload: dict[str, object]) -> bytes:
    return canonical_json_bytes(
        {
            "disposition": "PASS",
            "kind": _NO_TRAINING_KIND,
            "payload": payload,
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
            "subject_sha256": _SHA_C,
            "task_id": "MRL-0805",
        }
    )


def test_no_training_evaluation_authority_parses_without_claiming_training() -> None:
    raw = _raw(_no_training_authority())
    parsed = evidence.parse_mrl_real_preflight_evidence(raw)

    assert parsed.task_id == "MRL-0805"
    assert parsed.kind == _NO_TRAINING_KIND
    assert parsed.evidence_sha256 == hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize(
    ("field_name", "bad_value", "message"),
    (
        ("authorization_disposition", "BLOCKED", "authorization_disposition"),
        ("authorization_scope", "TRAINING", "authorization_scope"),
        ("evaluation_execution_authorized", False, "evaluation_execution_authorized"),
        ("real_training_authorized", True, "real_training_authorized"),
        ("training_prohibited", False, "training_prohibited"),
    ),
)
def test_no_training_evaluation_authority_fails_closed_on_boundary_drift(
    field_name: str,
    bad_value: object,
    message: str,
) -> None:
    payload = _no_training_authority()
    payload[field_name] = bad_value

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match=message):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_no_training_evaluation_authority_rejects_training_trust_fields() -> None:
    payload = _no_training_authority()
    payload["authorization_trust_registry_sha256"] = _SHA_A

    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="exact canonical key set",
    ):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_no_training_evaluation_authority_is_not_admitted_by_schema_alone() -> None:
    raw = _raw(_no_training_authority())

    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="not trusted",
    ):
        evidence.admit_mrl_real_preflight_evidence(raw, expected_task_id="MRL-0805")


def test_no_training_admission_does_not_invoke_training_authorization_trust(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _raw(_no_training_authority())
    digest = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(
        evidence,
        "TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256",
        frozenset({digest}),
    )

    def unexpected_training_trust(
        *,
        expected_registry_sha256: str,
        artifact_sha256: str,
    ) -> None:
        del expected_registry_sha256, artifact_sha256
        raise AssertionError("training authorization trust is not applicable")

    monkeypatch.setattr(
        authorization_trust,
        "validate_training_authorization_trust",
        unexpected_training_trust,
    )

    admitted = evidence.admit_mrl_real_preflight_evidence(
        raw,
        expected_task_id="MRL-0805",
    )
    assert admitted.kind == _NO_TRAINING_KIND


def test_no_training_kind_cannot_be_used_for_another_mrl_role() -> None:
    document = {
        "disposition": "PASS",
        "kind": _NO_TRAINING_KIND,
        "payload": _no_training_authority(),
        "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
        "subject_sha256": _SHA_C,
        "task_id": "MRL-0804",
    }

    with pytest.raises(
        evidence.MRLRealPreflightEvidenceError,
        match="kind does not match task_id",
    ):
        evidence.parse_mrl_real_preflight_evidence(canonical_json_bytes(document))
