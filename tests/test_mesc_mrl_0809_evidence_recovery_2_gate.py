from __future__ import annotations

import subprocess
from pathlib import Path

from medscale.mesc._mrl_0809_evidence_recovery_2_gate_v1 import (
    validate_evidence_recovery_2_authority,
)

ROOT = Path(__file__).resolve().parents[1]


def _head() -> str:
    return subprocess.check_output(
        ("git", "rev-parse", "HEAD"),
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def test_current_revision_has_exact_evidence_recovery_2_authority() -> None:
    identity = validate_evidence_recovery_2_authority(ROOT, _head())
    assert identity.authorization_sha256 == (
        "2c2b22cf88bc49dda4e2e89309e6ea0c580ef3f54aa36dd5c1fab7fd663677a8"
    )
    assert identity.decision_sha256 == (
        "878c98f53600e299b34510d4ca1d4a355dd5ca7ee4104a6eba60aaad56380d5e"
    )
    assert identity.static_manifest_sha256 == (
        "2aeb7b17bf9496a8dd65fba7b03d9b951e635ec4c7392717abbebf1756fb631a"
    )
    assert identity.predecessor_failure_sha256 == (
        "4bb9e9c5bfd85e7315bc788cad3f92d0ab1e7736ee57d8d620093acfca13a23b"
    )
    assert identity.predecessor_merge_sha == "f9b7579189b77b06379d1a71d104d4b0267cf500"
    assert identity.predecessor_merge_tree == "7bf4cbace9bce891da652a12ec3d7b6b4d9a8b03"
