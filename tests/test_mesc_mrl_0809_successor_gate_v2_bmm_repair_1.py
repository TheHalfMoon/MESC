from __future__ import annotations

import subprocess
from pathlib import Path

from medscale.mesc._mrl_0809_successor_gate_v2_bmm_repair_1 import (
    validate_bmm_repair_static_prerequisites,
)


def test_current_revision_bmm_repair_static_prerequisites() -> None:
    root = Path(__file__).resolve().parents[1]
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=root, text=True, encoding="utf-8"
    ).strip()

    identity = validate_bmm_repair_static_prerequisites(root, head)

    assert len(identity.manifest_sha256) == 64
    assert len(identity.consumed_failure_record_sha256) == 64
