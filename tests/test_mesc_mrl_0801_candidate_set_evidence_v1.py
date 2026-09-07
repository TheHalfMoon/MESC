"""Adversarial coverage for MRL-0801 active-candidate set evidence."""

from __future__ import annotations

import hashlib

import pytest

from medscale.mesc import _mrl_real_preflight_evidence_v1 as evidence
from medscale.mesc._canonical_json_v1 import canonical_json_bytes

_KIND = "mesc.mrl.real_preflight.model_weights_set.v1"
_SHA_A = "a" * 64
_SHA_B = "b" * 64
_SHA_C = "c" * 64
_SHA_D = "d" * 64
_SHA_E = "e" * 64
_SHA_F = "f" * 64
_GIT_A = "1" * 40
_GIT_B = "2" * 40


def _candidate(model_id: str, revision: str, *, suffix: str) -> dict[str, object]:
    digest = suffix * 64
    return {
        "access_authorization_sha256": _SHA_A,
        "artifact_identity_sha256": _SHA_B,
        "asset_custody_sha256": _SHA_C,
        "asset_present": True,
        "model_id": model_id,
        "revision": revision,
        "weights_sha256": digest,
    }


def _payload() -> dict[str, object]:
    return {
        "candidate_roster_sha256": _SHA_E,
        "candidates": [
            _candidate("Qwen/Qwen3.8-27B", _GIT_A, suffix="d"),
            _candidate("google/gemma-4-31B-it", _GIT_B, suffix="e"),
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
            "task_id": "MRL-0801",
        }
    )


def test_candidate_set_parses_but_is_not_trusted_by_default() -> None:
    raw = _raw(_payload())
    parsed = evidence.parse_mrl_real_preflight_evidence(raw)

    assert parsed.task_id == "MRL-0801"
    assert parsed.kind == _KIND
    assert parsed.evidence_sha256 == hashlib.sha256(raw).hexdigest()
    assert evidence.TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256 == frozenset()

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="not trusted"):
        evidence.admit_mrl_real_preflight_evidence(raw, expected_task_id="MRL-0801")


def test_candidate_set_can_use_existing_outer_trust_admission(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _raw(_payload())
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


def test_candidate_set_rejects_empty_candidates() -> None:
    payload = _payload()
    payload["candidates"] = []

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="at least one candidate"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_candidate_set_rejects_duplicate_model_id() -> None:
    payload = _payload()
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    candidates[1] = _candidate("Qwen/Qwen3.8-27B", _GIT_B, suffix="e")

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="model_id values"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_candidate_set_rejects_duplicate_model_revision_identity() -> None:
    payload = _payload()
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    candidates.append(dict(candidates[0]))

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="model_id values"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_candidate_set_rejects_noncanonical_candidate_order() -> None:
    payload = _payload()
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    payload["candidates"] = list(reversed(candidates))

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="strictly ordered"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_candidate_set_rejects_absent_asset() -> None:
    payload = _payload()
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    first = candidates[0]
    assert isinstance(first, dict)
    first["asset_present"] = False

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="asset_present"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_candidate_set_rejects_floating_revision() -> None:
    payload = _payload()
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    first = candidates[0]
    assert isinstance(first, dict)
    first["revision"] = "main"

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="40 lowercase hex"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_candidate_set_rejects_open_ended_candidate_fields() -> None:
    payload = _payload()
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    first = candidates[0]
    assert isinstance(first, dict)
    first["unexpected"] = _SHA_A

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="exact canonical key set"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_candidate_set_rejects_invalid_roster_identity() -> None:
    payload = _payload()
    payload["candidate_roster_sha256"] = "not-a-sha"

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="candidate_roster_sha256"):
        evidence.parse_mrl_real_preflight_evidence(_raw(payload))


def test_candidate_set_kind_is_only_valid_for_mrl_0801() -> None:
    raw = canonical_json_bytes(
        {
            "disposition": "PASS",
            "kind": _KIND,
            "payload": _payload(),
            "schema_version": "MRL-REAL-PREFLIGHT-EVIDENCE-V1",
            "subject_sha256": _SHA_F,
            "task_id": "MRL-0802",
        }
    )

    with pytest.raises(evidence.MRLRealPreflightEvidenceError, match="kind does not match"):
        evidence.parse_mrl_real_preflight_evidence(raw)
