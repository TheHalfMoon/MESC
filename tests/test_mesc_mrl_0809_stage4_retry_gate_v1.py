from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from medscale.mesc import _mrl_0809_stage4_retry_gate_v1 as GATE

ROOT = Path(__file__).resolve().parents[1]


def _head() -> str:
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        text=True,
        encoding="utf-8",
    ).strip()


def test_current_revision_has_exact_retry_authority() -> None:
    identity = GATE.validate_stage4_retry_authority(ROOT, _head())

    assert identity.authorization_sha256 == GATE._AUTHORIZATION_SHA256
    assert identity.decision_sha256 == GATE._DECISION_SHA256
    assert identity.repair_merge_sha == GATE._REPAIR_MERGE_SHA
    assert identity.repair_merge_tree == GATE._REPAIR_MERGE_TREE


def test_authorization_byte_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    original = GATE._git_bytes

    def drifted(root: Path, revision: str, path: str) -> bytes:
        raw = original(root, revision, path)
        if path == GATE.AUTHORIZATION:
            return raw + b" "
        return raw

    monkeypatch.setattr(GATE, "_git_bytes", drifted)
    with pytest.raises(GATE.MRL0809Stage4RetryGateError, match="authorization bytes drifted"):
        GATE.validate_stage4_retry_authority(ROOT, _head())


def test_decision_byte_drift_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    original = GATE._git_bytes

    def drifted(root: Path, revision: str, path: str) -> bytes:
        raw = original(root, revision, path)
        if path == GATE.DECISION:
            return raw + b" "
        return raw

    monkeypatch.setattr(GATE, "_git_bytes", drifted)
    with pytest.raises(GATE.MRL0809Stage4RetryGateError, match="decision bytes drifted"):
        GATE.validate_stage4_retry_authority(ROOT, _head())
