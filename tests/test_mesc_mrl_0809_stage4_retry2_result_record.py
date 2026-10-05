from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPECS = ROOT / "specs/mesc-experiment-0"
RESULT = SPECS / "mrl-0809-successor-v2-stage4-retry-2-result.json"
EVIDENCE = SPECS / "mrl-0809-successor-v2-stage4-retry-2-evidence"
AUTHORIZATION = SPECS / "mrl-0809-successor-v2-stage4-retry-2-authorization.json"
DECISION = SPECS / "mrl-0809-successor-v2/founder-decision-stage4-retry-2.md"
SLOT = SPECS / "mrl-0809-runtime-feasibility-slot-v2-repair-1.json"
TRUST = SPECS / "mrl-0809-runtime-feasibility-trust-v2-repair-1.json"
SCRIPT = ROOT / "scripts/mesc_mrl_0809_stage4_v2_retry_2_driver.py"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_driver() -> ModuleType:
    sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_stage4_v2_retry_2_driver_result_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_retry2_result_record_is_canonical_and_fail_closed() -> None:
    raw = RESULT.read_bytes()
    result = json.loads(raw)
    expected_raw = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )
    assert raw == expected_raw

    assert result["schema_version"] == "MESC-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-2-RESULT-V1"
    assert result["canonical"] == {
        "sha": "ac29a73e688da39485f7a5a4ab707944e18542c9",
        "tree": "e991b506d8a4eeb432cecd3b4bc27e351c779cab",
    }
    assert result["disposition"] == "PASS_RUNTIME_SEQUENCE_UNADMITTED"
    assert result["driver_execution"]["return_code"] == 0
    assert result["driver_execution"]["fail_stop_sequence_completed"] is True
    assert result["authority"]["launch_authorization_consumed"] is True
    assert result["authority"]["automatic_retry_authorized"] is False
    assert result["authority"]["automatic_relaunch_authorized"] is False

    assert result["fresh_main_qualification"]["all_success"] is True
    assert result["fresh_main_qualification"]["ci_run"] == 37231311055
    assert result["fresh_main_qualification"]["codeql_run"] == 37231311071
    assert result["fresh_main_qualification"]["optional_extras_run"] == 37231311107
    assert result["fresh_main_qualification"]["hf_publication_run"] == 37231311091

    assert result["authority"]["authorization_sha256"] == _sha256(AUTHORIZATION)
    assert result["authority"]["decision_sha256"] == _sha256(DECISION)
    assert result["historical"]["retry_1_failure_record_sha256"] == _sha256(
        SPECS / "mrl-0809-successor-v2-stage4-retry-1-failure-record.json"
    )

    assert result["runtime"]["provider_class"] == "GOOGLE_COLAB_FREE"
    assert result["runtime"]["gpu_class"] == "STANDARD_T4"
    assert result["runtime"]["gpu_model"] == "Tesla T4"
    assert result["runtime"]["monetary_cost_microunits"] == 0
    assert result["runtime"]["runtime_representation"] == "bitsandbytes-nf4-v1"
    assert result["runtime"]["input"] == "SYNTHETIC_ONLY"

    candidates = {entry["model_id"]: entry for entry in result["candidates"]}
    assert candidates["Qwen/Qwen3-8B"]["stage"] == "PASS"
    assert candidates["Qwen/Qwen3-8B"]["probe"] == "PASS"
    assert candidates["Qwen/Qwen3-8B"]["observation_bytes_preserved"] is True
    assert candidates["google/gemma-4-12B-it"]["stage"] == "PASS"
    assert candidates["google/gemma-4-12B-it"]["probe"] == "PASS_FAIL_STOP_DRIVER_RC_0"
    assert candidates["google/gemma-4-12B-it"]["observation_bytes_preserved"] is False

    assert result["independent_verification"] == {
        "reason": "FULL_GEMMA_OBSERVATION_AND_ASSEMBLED_RECEIPT_BYTES_UNAVAILABLE",
        "state": "BLOCKED",
    }
    assert result["trust_admission"] == {"eligible": False, "state": "NOT_ADMITTED"}
    assert all(value is False for value in result["non_grants"].values())


def test_preserved_evidence_hashes_and_missing_bytes_are_exact() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    for item in result["evidence_retention"]["full_bytes_preserved"]:
        path = ROOT / item["path"]
        assert path.is_file(), item["path"]
        assert path.stat().st_size == item["byte_count"]
        assert _sha256(path) == item["sha256"]

    missing = {item["path"]: item for item in result["evidence_retention"]["missing_full_bytes"]}
    assert set(missing) == {
        "gemma-observation.json",
        "runtime-feasibility-v2-bmm-repair-1.json",
    }
    assert missing["gemma-observation.json"]["sha256"] == (
        "d3c603d8e7e69ae86f33c53870ca316db52480b383dc0c09155a8289ea12ce78"
    )
    assert missing["runtime-feasibility-v2-bmm-repair-1.json"]["sha256"] == (
        "7666699551322b8a75d1720cf94f73111766c316ad6a080654073a2ddc81d1de"
    )
    assert not (EVIDENCE / "gemma-observation.json").exists()
    assert not (EVIDENCE / "runtime-feasibility-v2-bmm-repair-1.json").exists()


def test_colab_history_event_proves_driver_zero_and_generated_digests() -> None:
    result = json.loads(RESULT.read_text(encoding="utf-8"))
    event_path = ROOT / result["driver_execution"]["final_execution_event_path"]
    event = json.loads(event_path.read_text(encoding="utf-8"))
    assert event["timestamp"] == result["driver_execution"]["event_utc"]
    stdout = "".join(
        output.get("text", "")
        for output in event["outputs"]
        if output.get("output_type") == "stream" and output.get("name") == "stdout"
    )
    assert "DRIVER_RC=0\n" in stdout
    for item in result["generated_artifact_digests"]:
        expected = f"EVIDENCE {item['path']} bytes={item['byte_count']} sha256={item['sha256']}\n"
        assert expected in stdout


def test_result_record_mechanically_blocks_any_retry2_relaunch() -> None:
    driver = _load_driver()
    assert driver._CONSUMED_RECORDS[1] == Path(
        "specs/mesc-experiment-0/mrl-0809-successor-v2-stage4-retry-2-result.json"
    )
    with pytest.raises(driver.Stage4Retry2LaunchError, match="already consumed"):
        driver._require_unconsumed(ROOT)


def test_runtime_trust_and_slot_remain_unmodified() -> None:
    slot = json.loads(SLOT.read_text(encoding="utf-8"))
    trust = json.loads(TRUST.read_text(encoding="utf-8"))
    assert slot["state"] == "ABSENT"
    assert trust["trusted_receipt_sha256"] == []
