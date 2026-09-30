"""MRL-0809 successor (v2) contract, v1-preservation and receipt-validator coverage."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any, cast

import pytest

from medscale.mesc import _mrl_0809_runtime_feasibility_v2 as v2
from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._training_hf_safetensors_identity_v1 import (
    HfArtifactFileIdentity,
    HfSafeTensorsArtifactIdentity,
)

_ROOT = Path(__file__).resolve().parents[1]
_EXP = _ROOT / "specs" / "mesc-experiment-0"
_HARNESS = _ROOT / "scripts" / "mesc_mrl_0809_runtime_feasibility_v2.py"
_V1_ROSTER = "Qwen/Qwen3.8-27B", "google/gemma-4-31B-it"
_GIB = 1024**3


def _json(name: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((_EXP / name).read_bytes()))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _harness() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mrl_0809_harness_v2_contract", _HARNESS)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- frozen identities agree everywhere ---------------------------------------------------


def test_frozen_digests_bind_the_committed_successor_artifacts() -> None:
    assert _sha(_EXP / "candidate-roster-v2.json") == v2.CANDIDATE_ROSTER_SHA256
    assert _sha(_EXP / "mrl-0809-successor-v2-authorization.json") == (
        v2.SUCCESSOR_AUTHORIZATION_SHA256
    )
    assert _sha(_EXP / "mrl-0809-v1-infeasibility-record.json") == (
        v2.V1_INFEASIBILITY_RECORD_SHA256
    )
    harness = _harness()
    assert harness.CANDIDATE_ROSTER_SHA256 == v2.CANDIDATE_ROSTER_SHA256
    assert harness.SUCCESSOR_AUTHORIZATION_SHA256 == v2.SUCCESSOR_AUTHORIZATION_SHA256
    assert harness.V1_INFEASIBILITY_RECORD_SHA256 == v2.V1_INFEASIBILITY_RECORD_SHA256
    assert harness.RUNTIME_REPRESENTATION == v2.RUNTIME_REPRESENTATION
    assert harness.MAX_PEAK_GPU_MEMORY_BYTES == v2.MAX_PEAK_GPU_MEMORY_BYTES
    assert harness.EXPECTED_PACKAGES == v2.EXPECTED_PACKAGES
    assert harness.MAX_NEW_TOKENS == v2.MAX_NEW_TOKENS
    assert hashlib.sha256(harness.SYNTHETIC_PROMPT.encode("utf-8")).hexdigest() == (
        v2.SYNTHETIC_PROMPT_SHA256
    )


def test_harness_validator_and_roster_freeze_identical_candidates() -> None:
    harness = _harness()
    roster = _json("candidate-roster-v2.json")
    rows = {row["candidate_id"]: row for row in roster["active_candidates"]}
    assert set(rows) == set(v2.EXPECTED_CANDIDATES) == set(harness.EXPECTED_CANDIDATES)
    for model_id, expected in v2.EXPECTED_CANDIDATES.items():
        row = rows[model_id]
        script = harness.EXPECTED_CANDIDATES[model_id]
        for key, value in expected.items():
            assert script[key] == value, (model_id, key)
        assert row["candidate_revision"] == expected["revision"]
        for key in (
            "architecture",
            "artifact_identity_sha256",
            "config_sha256",
            "processor_config_sha256",
            "processor_policy",
            "prompt_token_ids_sha256",
            "text_vocab_size",
            "tokenizer_config_sha256",
            "weights_sha256",
        ):
            assert row[key] == expected[key], (model_id, key)
        assert row["selected_payload_bytes"] == harness.EXPECTED_SELECTED_PAYLOAD_BYTES[model_id]
        assert row["allowed_weight_files"] == [item["path"] for item in row["weight_files"]]
        assert (row["processor_metadata_filename"] is None) == (
            row["processor_policy"] == v2.TOKENIZER_ONLY
        )


def test_roster_weight_manifests_rederive_the_frozen_weight_identities() -> None:
    for row in _json("candidate-roster-v2.json")["active_candidates"]:
        files = tuple(
            HfArtifactFileIdentity(
                path=item["path"],
                kind=item["kind"],
                sha256=item["sha256"],
                byte_count=item["byte_count"],
            )
            for item in row["weight_files"]
        )
        identity = HfSafeTensorsArtifactIdentity(
            model_id=row["candidate_id"],
            revision=row["candidate_revision"],
            layout=row["layout"],
            files=files,
        )
        assert identity.weights_sha256 == row["weights_sha256"]
        assert identity.verifier_receipt_sha256 == row["artifact_identity_sha256"]


# --- Founder candidate policy ------------------------------------------------------------


def test_roster_satisfies_the_founder_candidate_policy() -> None:
    roster = _json("candidate-roster-v2.json")
    policy = _json("mrl-0809-successor-v2-authorization.json")["candidate_policy"]
    assert roster["candidate_count"] == policy["candidate_count"] == 2
    assert roster["status"] == "FROZEN_METADATA_ONLY"
    assert roster["real_model_execution_authorized"] is False
    assert roster["training_authorized"] is False
    assert roster["result_exposure_started"] is False
    for row in roster["active_candidates"]:
        estimate = row["footprint_estimate"]
        total = (
            estimate["fp16_retained_parameter_count"] + estimate["nf4_quantized_parameter_count"]
        )
        assert total <= policy["preferred_max_total_parameters"], row["candidate_id"]
        assert (
            estimate["estimated_nf4_weight_bytes"] <= policy["preferred_max_estimated_weight_bytes"]
        ), row["candidate_id"]
        assert row["gated"] is False
        assert row["trust_remote_code"] is False
        assert row["remote_code_required"] is False
        assert row["license_identity"] == "Apache-2.0"
        assert row["role"] == "RQ1_SUCCESSOR_EVALUATION_CANDIDATE"
        assert row["candidate_id"] not in _V1_ROSTER


def test_footprint_model_is_calibrated_against_the_v1_out_of_memory_result() -> None:
    calibration = _json("candidate-roster-v2.json")["footprint_model"]["calibration"]
    observed = {row["model_id"]: row for row in calibration}
    for model_id in _V1_ROSTER:
        assert observed[model_id]["estimated_nf4_weight_bytes"] > int(14.56 * _GIB)


def test_roster_keeps_the_flagship_strategy_and_disclaims_selection() -> None:
    roster = _json("candidate-roster-v2.json")
    assert roster["flagship_strategy"] == {
        "adr": "docs/adr/0036-performance-first-health-model-strategy.md",
        "preferred_foundation_candidate": "Qwen/Qwen3.8-27B",
        "state": "UNCHANGED",
    }
    assert {"FLAGSHIP_SELECTION", "MODEL_PROMOTION", "TRAINING_SELECTION"} <= set(roster["not_for"])
    selected = [row for row in roster["shortlist"] if row["disposition"] == "SELECTED"]
    assert sorted(row["candidate_id"] for row in selected) == sorted(v2.EXPECTED_CANDIDATES)
    assert all(len(row["revision"]) == 40 for row in roster["shortlist"])


def test_successor_authorization_grants_nothing_beyond_the_founder_decision() -> None:
    authorization = _json("mrl-0809-successor-v2-authorization.json")
    assert authorization["selected_option"] == "ISSUE_450_OPTION_3"
    assert set(authorization["non_grants"].values()) == {False}
    assert authorization["stage4"]["attempts_authorized"] == 1
    assert authorization["stage4"]["state"] == "NOT_STARTED"
    assert authorization["stage4"]["input"] == "SYNTHETIC_ONLY"
    assert authorization["runtime"]["monetary_cost_microunits"] == 0
    assert authorization["runtime"]["credentials"] == "NONE"
    assert authorization["v1"]["retry_authorized"] is False
    record = _ROOT / authorization["authority_source"]["decision_record_path"]
    assert _sha(record) == authorization["authority_source"]["decision_record_sha256"]


# --- v1 preservation -----------------------------------------------------------------------


def test_v1_contract_bytes_are_preserved_and_record_the_negative_result() -> None:
    record = _json("mrl-0809-v1-infeasibility-record.json")
    assert record["v1_disposition"] == "INFEASIBLE_ON_FROZEN_STANDARD_T4_CONTRACT"
    assert record["pass_claimed"] is False
    assert record["gemma_tested"] is False
    assert record["retry_authorized"] is False
    outcomes = {row["model_id"]: row for row in record["attempt"]["candidates"]}
    assert outcomes["Qwen/Qwen3.8-27B"]["probe"] == "FAIL"
    assert outcomes["Qwen/Qwen3.8-27B"]["failure"] == "CUDA_OOM_DURING_WEIGHT_LOAD"
    assert outcomes["google/gemma-4-31B-it"]["stage"] == "NOT_RUN"
    assert outcomes["google/gemma-4-31B-it"]["probe"] == "NOT_RUN"
    for binding in record["v1_contract_preserved_at_successor_base"].values():
        assert _sha(_ROOT / binding["path"]) == binding["sha256"], binding["path"]
    assert _json("mrl-0809-runtime-feasibility-slot-v1.json")["state"] == "ABSENT"
    assert _json("mrl-0809-runtime-feasibility-trust-v1.json")["trusted_receipt_sha256"] == []


# --- MRL-0806 carry-forward ------------------------------------------------------------------


def test_mrl0806_successor_changes_only_the_declared_candidate_binding() -> None:
    v1_auth = _json("mrl-0806-objective-budgets-authorization-v1.json")
    v2_auth = _json("mrl-0806-objective-budgets-authorization-v2.json")
    for key in ("candidate_id", "experiment_id", "policy", "research_question"):
        assert v2_auth[key] == v1_auth[key], key
    changed = {"candidate_roster_sha256", "rq1_protocol_sha256"}
    for key, value in v1_auth["frozen_artifacts"].items():
        if key not in changed:
            assert v2_auth["frozen_artifacts"][key] == value, key
    assert v2_auth["frozen_artifacts"]["candidate_roster_sha256"] == v2.CANDIDATE_ROSTER_SHA256
    assert v2_auth["predecessor_authorization"]["sha256"] == _sha(
        _EXP / "mrl-0806-objective-budgets-authorization-v1.json"
    )
    for key, value in v1_auth["predecessor_evidence"].items():
        expected = None if key in {"MRL-0801", "MRL-0805"} else value
        assert v2_auth["predecessor_evidence"][key] == expected, key
    assert v2_auth["pending_successor_evidence_before_mrl_0899"] == ["MRL-0801", "MRL-0805"]
    p1 = _json("mrl-0806-rq1-protocol-v1.json")
    p2 = _json("mrl-0806-rq1-protocol-v2.json")
    assert set(p1) == set(p2)
    for key, value in p1.items():
        if key not in {"candidate_roster_sha256", "candidates", "preflight_evidence_sha256"}:
            assert p2[key] == value, key
    assert v2_auth["frozen_artifacts"]["rq1_protocol_sha256"] == _sha(
        _EXP / "mrl-0806-rq1-protocol-v2.json"
    )
    assert [row["model_id"] for row in p2["candidates"]] == sorted(v2.EXPECTED_CANDIDATES)


# --- receipt validator -----------------------------------------------------------------------

_PROMPT_IDS = {
    "Qwen/Qwen3-8B": [
        151644, 872, 198, 7985, 825, 2805, 11652, 911, 264, 6303, 21495, 13, 151645, 198,
        151644, 77091, 198,
    ],
    "google/gemma-4-12B-it": [
        2, 105, 2364, 107, 6974, 886, 2822, 13315, 1003, 496, 3730, 17852, 236761, 106, 107,
        105, 4368, 107, 100, 45518, 107, 101,
    ],
}  # fmt: skip


def test_frozen_prompt_token_digests_match_the_recorded_chat_template_ids() -> None:
    for model_id, ids in _PROMPT_IDS.items():
        digest = hashlib.sha256(canonical_json_bytes(ids)).hexdigest()
        assert digest == v2.EXPECTED_CANDIDATES[model_id]["prompt_token_ids_sha256"]


def _generation(model_id: str) -> dict[str, object]:
    return {
        "all_generated_logits_finite": True,
        "decoded_text_sha256": "d" * 64,
        "generated_token_ids": [11, 12, 13],
        "prompt_construction": v2.PROMPT_CONSTRUCTION,
        "prompt_token_ids_sha256": v2.EXPECTED_CANDIDATES[model_id]["prompt_token_ids_sha256"],
        "synthetic_prompt_sha256": v2.SYNTHETIC_PROMPT_SHA256,
    }


def _candidate(model_id: str) -> dict[str, object]:
    expected = v2.EXPECTED_CANDIDATES[model_id]
    generation = _generation(model_id)
    return {
        "all_modules_on_cuda_device_0": True,
        "architecture": expected["architecture"],
        "artifact_identity_sha256": expected["artifact_identity_sha256"],
        "config_sha256": expected["config_sha256"],
        "generation_evidence": generation,
        "load_completed": True,
        "model_id": model_id,
        "peak_cpu_memory_bytes": 4 * _GIB,
        "peak_gpu_memory_bytes": 8 * _GIB,
        "processor_config_sha256": expected["processor_config_sha256"],
        "processor_loaded": expected["processor_policy"] == v2.AUTO_PROCESSOR,
        "processor_policy": expected["processor_policy"],
        "revision": expected["revision"],
        "runtime_representation": v2.RUNTIME_REPRESENTATION,
        "stage_receipt_sha256": "1" * 64,
        "synthetic_generation_completed": True,
        "synthetic_generation_sha256": hashlib.sha256(canonical_json_bytes(generation)).hexdigest(),
        "text_only_generation": True,
        "text_vocab_size": expected["text_vocab_size"],
        "tokenizer_config_sha256": expected["tokenizer_config_sha256"],
        "tokenizer_loaded": True,
        "unloaded_after_probe": True,
        "weights_sha256": expected["weights_sha256"],
    }


def _runtime_identity() -> dict[str, object]:
    return {
        "bubblewrap_sha256": "e" * 64,
        "bubblewrap_version": "bubblewrap 0.11.0",
        "colab_release_tag": "release-fixture",
        "compute_dtype": "float16",
        "gpu_model": "Tesla T4",
        "gpu_uuid": "GPU-fixture",
        "gpu_vram_bytes": 15_360 * 1024 * 1024,
        "harness_sha256": "f" * 64,
        "kernel_release": "kernel-fixture",
        "package_versions": dict(v2.EXPECTED_PACKAGES),
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": "assignment:test-only",
        "provider_owner": "GOOGLE",
        "python_version": "3.11.15",
        "runtime_representation": v2.RUNTIME_REPRESENTATION,
    }


def _receipt() -> dict[str, Any]:
    identity = _runtime_identity()
    return {
        "candidate_roster_sha256": v2.CANDIDATE_ROSTER_SHA256,
        "candidate_substitution_performed": False,
        "candidates": [_candidate(model_id) for model_id in sorted(v2.EXPECTED_CANDIDATES)],
        "capacity_fallback_performed": False,
        "cleanup_completed": True,
        "compute_dtype": "float16",
        "dependency_lock_sha256": "a" * 64,
        "disposition": "PASS",
        "gpu_model": "Tesla T4",
        "gpu_vram_bytes": identity["gpu_vram_bytes"],
        "local_files_only_during_isolated_execution": True,
        "monetary_cost_microunits": 0,
        "mrl_0804_evidence_sha256": (
            "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0"
        ),
        "mrl_0804_runtime_identity_sha256": (
            "05b19593f7c9c1f03df39a100189da653695bad1b13d24c921dd1fecd7fe0b45"
        ),
        "mrl_0808_evidence_sha256": (
            "d65558e910cfaf63d41c1c52db1524039943eef00fd6692c576bf8ed1c8ebf77"
        ),
        "network_access_during_isolated_generation": False,
        "network_access_during_isolated_load": False,
        "offload_performed": False,
        "optimizer_present": False,
        "persistent_weight_writeback": False,
        "provider": "GOOGLE_COLAB",
        "provider_execution_id": "assignment:test-only",
        "provider_owner": "GOOGLE",
        "repository_sha": "1" * 40,
        "repository_tree": "2" * 40,
        "runtime_identity": identity,
        "runtime_identity_sha256": hashlib.sha256(canonical_json_bytes(identity)).hexdigest(),
        "sandbox_policy_sha256": (
            "169255451b232a530875e221f39096fd103f3429b5d5125f54229f1b347c8316"
        ),
        "schema_version": v2.SCHEMA,
        "static_prerequisite_manifest_sha256": "b" * 64,
        "successor_authorization_sha256": v2.SUCCESSOR_AUTHORIZATION_SHA256,
        "training_performed": False,
        "trust_remote_code": False,
        "v1_infeasibility_record_sha256": v2.V1_INFEASIBILITY_RECORD_SHA256,
        "weight_mutation_performed": False,
    }


def _validate(receipt: dict[str, Any]) -> v2.SuccessorRuntimeFeasibilityReceipt:
    return v2.validate_successor_runtime_feasibility_receipt(
        canonical_json_bytes(receipt),
        expected_static_prerequisite_manifest_sha256="b" * 64,
        expected_dependency_lock_sha256="a" * 64,
    )


def _refresh_generation(candidate: dict[str, Any]) -> None:
    candidate["synthetic_generation_sha256"] = hashlib.sha256(
        canonical_json_bytes(candidate["generation_evidence"])
    ).hexdigest()


def test_validator_accepts_the_exact_dual_candidate_successor_pass() -> None:
    validated = _validate(_receipt())
    assert validated.runtime_representation == v2.RUNTIME_REPRESENTATION
    assert validated.provider_execution_id == "assignment:test-only"


def _set(path: tuple[object, ...], value: object) -> Any:
    def mutate(receipt: dict[str, Any]) -> None:
        target: Any = receipt
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value

    return mutate


_TOP_LEVEL_FORGERIES = {
    "hidden_offload": _set(("offload_performed",), True),
    "hidden_fallback": _set(("capacity_fallback_performed",), True),
    "candidate_substitution_flag": _set(("candidate_substitution_performed",), True),
    "remote_code": _set(("trust_remote_code",), True),
    "paid_compute": _set(("monetary_cost_microunits",), 1),
    "training": _set(("training_performed",), True),
    "optimizer": _set(("optimizer_present",), True),
    "weight_mutation": _set(("weight_mutation_performed",), True),
    "writeback": _set(("persistent_weight_writeback",), True),
    "isolated_load_network": _set(("network_access_during_isolated_load",), True),
    "isolated_generation_network": _set(("network_access_during_isolated_generation",), True),
    "not_local_only": _set(("local_files_only_during_isolated_execution",), False),
    "no_cleanup": _set(("cleanup_completed",), False),
    "failed_disposition": _set(("disposition",), "FAIL"),
    "v1_schema": _set(("schema_version",), "MESC-MRL-0809-RUNTIME-MODEL-FEASIBILITY-V1"),
    "roster_hash_mismatch": _set(("candidate_roster_sha256",), "0" * 64),
    "authorization_hash_mismatch": _set(("successor_authorization_sha256",), "0" * 64),
    "v1_record_rewritten": _set(("v1_infeasibility_record_sha256",), "0" * 64),
    "sandbox_policy_drift": _set(("sandbox_policy_sha256",), "0" * 64),
    "provider_substitution": _set(("provider",), "KAGGLE"),
    "gpu_substitution": _set(("gpu_model",), "Tesla P100-PCIE-16GB"),
    "compute_dtype_drift": _set(("compute_dtype",), "bfloat16"),
    "manifest_drift": _set(("static_prerequisite_manifest_sha256",), "c" * 64),
}


@pytest.mark.parametrize("forgery", sorted(_TOP_LEVEL_FORGERIES))
def test_validator_rejects_top_level_forgeries(forgery: str) -> None:
    receipt = _receipt()
    _TOP_LEVEL_FORGERIES[forgery](receipt)
    with pytest.raises(v2.MRL0809SuccessorRuntimeFeasibilityError):
        _validate(receipt)


_CANDIDATE_FORGERIES = {
    "revision_drift": ("revision", "0" * 40),
    "weights_drift": ("weights_sha256", "0" * 64),
    "config_drift": ("config_sha256", "0" * 64),
    "tokenizer_drift": ("tokenizer_config_sha256", "0" * 64),
    "representation_drift": ("runtime_representation", "bitsandbytes-int8-v1"),
    "not_all_on_device_0": ("all_modules_on_cuda_device_0", False),
    "load_not_completed": ("load_completed", False),
    "tokenizer_not_loaded": ("tokenizer_loaded", False),
    "not_unloaded": ("unloaded_after_probe", False),
    "headroom_exceeded": ("peak_gpu_memory_bytes", 12 * _GIB + 1),
    "architecture_drift": ("architecture", "Qwen3_5ForConditionalGeneration"),
}


@pytest.mark.parametrize("forgery", sorted(_CANDIDATE_FORGERIES))
@pytest.mark.parametrize("index", [0, 1])
def test_validator_rejects_candidate_forgeries(forgery: str, index: int) -> None:
    receipt = _receipt()
    key, value = _CANDIDATE_FORGERIES[forgery]
    receipt["candidates"][index][key] = value
    with pytest.raises(v2.MRL0809SuccessorRuntimeFeasibilityError):
        _validate(receipt)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("all_generated_logits_finite", False),
        ("prompt_token_ids_sha256", "0" * 64),
        ("prompt_construction", "RAW_TOKENIZER_CALL"),
        ("synthetic_prompt_sha256", "0" * 64),
        ("generated_token_ids", list(range(13))),
        ("generated_token_ids", []),
    ],
)
def test_validator_rejects_generation_evidence_forgeries(key: str, value: object) -> None:
    receipt = _receipt()
    candidate = receipt["candidates"][0]
    candidate["generation_evidence"][key] = value
    _refresh_generation(candidate)
    with pytest.raises(v2.MRL0809SuccessorRuntimeFeasibilityError):
        _validate(receipt)


def test_validator_rejects_processor_claims_that_contradict_the_frozen_policy() -> None:
    receipt = _receipt()
    by_id = {row["model_id"]: row for row in receipt["candidates"]}
    by_id["Qwen/Qwen3-8B"]["processor_loaded"] = True
    with pytest.raises(v2.MRL0809SuccessorRuntimeFeasibilityError):
        _validate(receipt)
    receipt = _receipt()
    by_id = {row["model_id"]: row for row in receipt["candidates"]}
    by_id["google/gemma-4-12B-it"]["processor_loaded"] = False
    with pytest.raises(v2.MRL0809SuccessorRuntimeFeasibilityError):
        _validate(receipt)


def test_validator_rejects_v1_candidate_substitution_and_roster_shape_drift() -> None:
    receipt = _receipt()
    substituted = copy.deepcopy(receipt["candidates"][0])
    substituted["model_id"] = "Qwen/Qwen3.8-27B"
    receipt["candidates"][0] = substituted
    with pytest.raises(v2.MRL0809SuccessorRuntimeFeasibilityError):
        _validate(receipt)
    receipt = _receipt()
    receipt["candidates"] = receipt["candidates"][:1]
    with pytest.raises(v2.MRL0809SuccessorRuntimeFeasibilityError):
        _validate(receipt)
    receipt = _receipt()
    receipt["candidates"] = list(reversed(receipt["candidates"]))
    with pytest.raises(v2.MRL0809SuccessorRuntimeFeasibilityError):
        _validate(receipt)


def test_validator_rejects_runtime_identity_drift() -> None:
    for key, value in (
        ("python_version", "3.12.1"),
        ("gpu_model", "NVIDIA A100-SXM4-40GB"),
        ("package_versions", {**v2.EXPECTED_PACKAGES, "transformers": "5.17.0"}),
    ):
        receipt = _receipt()
        receipt["runtime_identity"][key] = value
        receipt["runtime_identity_sha256"] = hashlib.sha256(
            canonical_json_bytes(receipt["runtime_identity"])
        ).hexdigest()
        with pytest.raises(v2.MRL0809SuccessorRuntimeFeasibilityError):
            _validate(receipt)


def test_validator_rejects_noncanonical_bytes() -> None:
    raw = canonical_json_bytes(_receipt())
    with pytest.raises(v2.MRL0809SuccessorRuntimeFeasibilityError):
        v2.validate_successor_runtime_feasibility_receipt(
            raw.rstrip(b"\n") + b" \n",
            expected_static_prerequisite_manifest_sha256="b" * 64,
            expected_dependency_lock_sha256="a" * 64,
        )
