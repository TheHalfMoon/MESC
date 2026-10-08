"""Versioned Recovery-3 authority and unarmed-launch guard."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from medscale.mesc import _mrl_0809_evidence_recovery_3_gate_v1 as gate
from medscale.mesc._canonical_json_v1 import canonical_json_bytes

ROOT = Path(__file__).resolve().parents[1]


def _head() -> str:
    return subprocess.check_output(
        ("git", "-C", str(ROOT), "rev-parse", "HEAD"),
        text=True,
        encoding="utf-8",
    ).strip()


def test_accepted_implementation_is_tied_to_canonical_recovery2_failure() -> None:
    identity = gate.validate_evidence_recovery_3_authority(ROOT, _head())
    assert identity.predecessor_merge_sha == "60ec9973694a8b64cc2ae58cd5e5a2e410d91b91"
    assert identity.predecessor_merge_tree == "0add794a81ba68aaa61fd2f23da7280baefbf9e7"
    assert identity.predecessor_failure_sha256 == (
        "af1c2ddb2c5b7b046ce441a6cbe717071fd3962114f280c4deea01fdb62aafba"
    )
    assert identity.authorization_sha256 == (
        "2ce48b1c824881dac0500a8b1051c758ab17ff0119e9db2487da3a758184d1f9"
    )
    assert identity.static_manifest_sha256 == (
        "521d4281bc2dec5ebbb393729cb7203715efd2eca757b5a63bae5bf752a548ba"
    )


def test_unarmed_recovery3_cannot_allocate_without_final_sha_approval() -> None:
    with pytest.raises(gate.MRL0809EvidenceRecovery3GateError, match="NOT_EFFECTIVE"):
        gate.require_recovery_3_launch_effectiveness(ROOT, _head())


def test_unsupported_nominal_rate_zero_requirement_is_rejected() -> None:
    raw = (ROOT / gate.AUTHORIZATION).read_bytes()
    data = json.loads(raw)
    data["preflight"]["active_nominal_rate_must_be_zero"] = True
    with pytest.raises(
        gate.MRL0809EvidenceRecovery3GateError, match="paid-unit preflight weakened"
    ):
        gate._check_authorization(canonical_json_bytes(data))


def test_recovery2_unconsumed_claim_is_rejected() -> None:
    raw = (ROOT / gate.PREDECESSOR_FAILURE).read_bytes()
    data = json.loads(raw)
    data["authority"]["launch_authorization_consumed"] = False
    with pytest.raises(gate.MRL0809EvidenceRecovery3GateError, match="not consumed"):
        gate._check_failure(gate._historical_json_bytes(data))


def test_paid_unit_purchase_is_not_reclassified_as_free() -> None:
    raw = (ROOT / gate.PREDECESSOR_FAILURE).read_bytes()
    data = json.loads(raw)
    data["billing_observations"]["paid_unit_purchase_commands"] = 1
    with pytest.raises(gate.MRL0809EvidenceRecovery3GateError, match="paid-unit purchase"):
        gate._check_failure(gate._historical_json_bytes(data))
