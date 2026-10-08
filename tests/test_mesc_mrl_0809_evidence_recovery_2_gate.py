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
        "d3c1edc0bb212db0717fe14694b80923cd09dea1ba4e4e2dbe5583d74b59d722"
    )
    assert identity.decision_sha256 == (
        "878c98f53600e299b34510d4ca1d4a355dd5ca7ee4104a6eba60aaad56380d5e"
    )
    assert identity.static_manifest_sha256 == (
        "1c05e6261ff08de2e3d71c06bcc389b40bbd9f6487e4da8881792f64c6953969"
    )
    assert identity.predecessor_failure_sha256 == (
        "4bb9e9c5bfd85e7315bc788cad3f92d0ab1e7736ee57d8d620093acfca13a23b"
    )
    assert identity.predecessor_merge_sha == "f9b7579189b77b06379d1a71d104d4b0267cf500"
    assert identity.predecessor_merge_tree == "7bf4cbace9bce891da652a12ec3d7b6b4d9a8b03"
