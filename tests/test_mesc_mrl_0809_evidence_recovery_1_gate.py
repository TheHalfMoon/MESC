from __future__ import annotations

import subprocess
from pathlib import Path

from medscale.mesc._mrl_0809_evidence_recovery_1_gate_v1 import (
    validate_evidence_recovery_1_authority,
)

ROOT = Path(__file__).resolve().parents[1]


def _head() -> str:
    return subprocess.check_output(
        ("git", "rev-parse", "HEAD"),
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def test_current_revision_has_exact_evidence_recovery_authority() -> None:
    identity = validate_evidence_recovery_1_authority(ROOT, _head())
    assert identity.authorization_sha256 == (
        "2d785a51faeec8fd4fb66890196ed7becd16b44190121228653802e2ae6d9327"
    )
    assert identity.decision_sha256 == (
        "d4a8c8deef9a014e6d39a56800f55337e130ae0d517eed1d2316300db7979e43"
    )
    assert identity.static_manifest_sha256 == (
        "8942b3f73cc52452b128ee724ea0c1b1df537cbb17ab54f35f81f9b8a62aa2ba"
    )
    assert identity.predecessor_result_sha256 == (
        "2346c595176a5cbeaff40897a4be64e0ebdad0e40c58438bb6f6a4d98304fda3"
    )
    assert identity.predecessor_merge_sha == "1a634525e95ae1bb6a9fa01745ecd63c2d82684a"
    assert identity.predecessor_merge_tree == "8c60c1ea30757fd743de8bee462e5f81c292ecb1"
