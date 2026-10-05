from __future__ import annotations

import hashlib
import importlib
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
RECORD = (
    ROOT / "specs/mesc-experiment-0/mrl-0809-successor-v2-evidence-recovery-1-failure-record.json"
)
EVIDENCE = ROOT / "specs/mesc-experiment-0/mrl-0809-successor-v2-evidence-recovery-1-evidence"

sys.path.insert(0, str(ROOT / "scripts"))
_driver: Any = importlib.import_module("mesc_mrl_0809_evidence_recovery_1_driver")
EvidenceRecovery1LaunchError: type[RuntimeError] = _driver.EvidenceRecovery1LaunchError
_require_recovery_unconsumed: Callable[[Path], None] = _driver._require_recovery_unconsumed


def _load(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_failure_record_is_fail_closed_and_preserves_non_grants() -> None:
    record = _load(RECORD)
    assert record["disposition"] == "FAIL_EVIDENCE_RETENTION_AFTER_RUNTIME_PASS"
    assert record["failure_class"] == "POST_RUNTIME_COPYOUT_NOT_COMPLETED_BEFORE_SESSION_PRUNE"
    authority = record["authority"]
    assert authority["launch_authorization_consumed"] is True
    assert authority["automatic_retry_authorized"] is False
    assert authority["automatic_relaunch_authorized"] is False
    assert record["independent_verification"] == {
        "reason": "FULL_GEMMA_OBSERVATION_ASSEMBLED_RECEIPT_AND_RECOVERY_BUNDLE_BYTES_UNAVAILABLE",
        "state": "BLOCKED",
    }
    assert record["trust_admission"] == {"eligible": False, "state": "NOT_ADMITTED"}
    non_grants = record["non_grants"]
    assert all(value is False for value in non_grants.values())


def test_preserved_evidence_hashes_match_exact_bytes() -> None:
    record = _load(RECORD)
    preserved = record["evidence_retention"]["preserved_evidence"]
    for item in preserved:
        path = ROOT / item["path"]
        assert path.is_file(), item["path"]
        assert path.stat().st_size == item["byte_count"]
        assert _sha256(path) == item["sha256"]


def test_execution_events_bind_prelaunch_driver_success_and_prune() -> None:
    prelaunch = _load(EVIDENCE / "prelaunch-execution-event.json")
    final = _load(EVIDENCE / "final-driver-execution-event.json")
    termination = _load(EVIDENCE / "session-termination-event.json")
    prelaunch_stdout = "".join(
        str(item.get("text", ""))
        for item in prelaunch["outputs"]
        if item.get("output_type") == "stream"
    )
    final_stdout = "".join(
        str(item.get("text", ""))
        for item in final["outputs"]
        if item.get("output_type") == "stream"
    )
    assert "PRELAUNCH_PASS\n" in prelaunch_stdout
    assert "DRIVER_RC=0\n" in final_stdout
    assert termination == {
        "event_type": "session_terminated",
        "reason": "pruned",
        "timestamp": "2026-10-05T19:52:17.687836+00:00",
    }


def test_launch_consumption_receipt_blocks_relaunch() -> None:
    receipt = _load(EVIDENCE / "evidence-recovery-1-launch-consumption.json")
    assert receipt["canonical_revision"] == "fd1c72f216886e6bb6b708ffd6bb3a335606e6ce"
    assert receipt["launch_authorization_consumed"] is True
    assert receipt["automatic_retry_authorized"] is False
    assert receipt["automatic_relaunch_authorized"] is False
    with pytest.raises(EvidenceRecovery1LaunchError, match="already consumed"):
        _require_recovery_unconsumed(ROOT)


def test_recovery_target_bytes_remain_explicitly_unavailable() -> None:
    record = _load(RECORD)
    missing = {item["path"] for item in record["evidence_retention"]["missing_full_bytes"]}
    assert missing == {
        "gemma-observation.json",
        "runtime-feasibility-v2-bmm-repair-1.json",
        "evidence-recovery-1-bundle.json",
    }
    assert record["execution"]["driver_return_code"] == 0
    assert record["execution"]["runtime_sequence_completed"] is True
    assert record["evidence_retention"]["objective_state"] == "FAILED"
