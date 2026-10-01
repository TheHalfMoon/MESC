from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATHS = (
    "docs/execution/mrl_0809_runtime_feasibility_runbook_v2_repair_1.md",
    "scripts/mesc_mrl_0809_runtime_feasibility_v2_repair.py",
    "scripts/mesc_mrl_0809_runtime_worker_v2_repair.py",
    "scripts/mesc_mrl_0809_stage4_v2_repair_driver.py",
    "specs/mesc-experiment-0/mrl-0809-static-prerequisites-v2.json",
    "specs/mesc-experiment-0/mrl-0809-successor-v2/founder-decision-stage4-repair.md",
    "src/medscale/mesc/_mrl_0809_device_placement_audit_v1.py",
    "src/medscale/mesc/_mrl_0809_successor_gate_v2_repair_1.py",
)


def test_emit_repair_source_hashes_for_manifest_finalization() -> None:
    hashes = {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in PATHS}
    raise AssertionError("REPAIR_SHA256=" + json.dumps(hashes, sort_keys=True))
