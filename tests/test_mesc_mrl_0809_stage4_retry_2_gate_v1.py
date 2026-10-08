from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from medscale.mesc import _mrl_0809_stage4_retry_2_gate_v1 as gate

ROOT = Path(__file__).resolve().parents[1]


def _head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def test_current_revision_has_exact_retry_2_authority() -> None:
    identity = gate.validate_stage4_retry_2_authority(ROOT, _head())

    assert identity.authorization_sha256 == gate._AUTHORIZATION_SHA256
    assert identity.decision_sha256 == gate._DECISION_SHA256
    assert identity.bmm_repair_merge_sha == gate._BMM_REPAIR_MERGE_SHA
    assert identity.bmm_repair_merge_tree == gate._BMM_REPAIR_MERGE_TREE
    assert len(identity.static_manifest_sha256) == 64


def test_retry_2_authorization_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = gate._git_bytes

    def drift(root: Path, revision: str, path: str) -> bytes:
        raw = original(root, revision, path)
        if path == gate.AUTHORIZATION:
            return raw + b" "
        return raw

    monkeypatch.setattr(gate, "_git_bytes", drift)

    with pytest.raises(gate.MRL0809Stage4Retry2GateError, match="authorization bytes drifted"):
        gate.validate_stage4_retry_2_authority(ROOT, _head())


def test_retry_2_decision_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = gate._git_bytes

    def drift(root: Path, revision: str, path: str) -> bytes:
        raw = original(root, revision, path)
        if path == gate.DECISION:
            return raw + b"\n"
        return raw

    monkeypatch.setattr(gate, "_git_bytes", drift)

    with pytest.raises(
        gate.MRL0809Stage4Retry2GateError,
        match="accepted Founder retry-2 decision bytes drifted",
    ):
        gate.validate_stage4_retry_2_authority(ROOT, _head())
