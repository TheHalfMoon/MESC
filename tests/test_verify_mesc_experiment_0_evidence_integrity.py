from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

ROOT = "mesc-experiment-0-evidence"


def _load_module(path: Path, name: str) -> Any:
    """Load one repository test module without making tests a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURES: Any = _load_module(
    Path(__file__).with_name("test_verify_mesc_experiment_0_evidence.py"),
    "mesc_exp0_fixture_module",
)
VERIFIER: Any = FIXTURES.VERIFIER


def test_load_json_rejects_duplicate_object_keys() -> None:
    """Ambiguous JSON objects cannot enter content-addressed evidence."""
    payload = b'{"schema_version":"x","schema_version":"y"}'
    with pytest.raises(VERIFIER.EvidenceError, match="duplicate JSON key"):
        VERIFIER.load_json(payload, "duplicate.json")


def test_load_json_rejects_non_finite_constants() -> None:
    """Non-standard NaN/Infinity JSON values fail closed."""
    with pytest.raises(VERIFIER.EvidenceError, match="non-finite JSON constant"):
        VERIFIER.load_json(b'{"metric":NaN}', "non-finite.json")


def test_require_number_handles_arbitrarily_large_nonnegative_int() -> None:
    """Integer budgets do not overflow finite-number validation."""
    VERIFIER.require_number(10**10_000, "resource_budget.synthetic")


def test_verify_rejects_pass_runtime_with_unlisted_gpu(tmp_path: Path) -> None:
    """A PASS runtime receipt must satisfy the frozen GPU allowlist."""
    docs = FIXTURES._base_docs()
    runtime_path = f"{ROOT}/runtime-receipt.json"
    runtime = json.loads(docs[runtime_path])
    runtime["gpu_models"] = ["UNLISTED_GPU"]
    docs[runtime_path] = FIXTURES._json_bytes(runtime)

    bundle = tmp_path / "unlisted-gpu.zip"
    FIXTURES._write_bundle(bundle, docs)
    with pytest.raises(VERIFIER.EvidenceError, match="GPU model violates frozen runtime policy"):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_pass_runtime_without_cuda(tmp_path: Path) -> None:
    """A PASS runtime receipt cannot contradict its required CUDA state."""
    docs = FIXTURES._base_docs()
    runtime_path = f"{ROOT}/runtime-receipt.json"
    runtime = json.loads(docs[runtime_path])
    runtime["cuda_available"] = False
    docs[runtime_path] = FIXTURES._json_bytes(runtime)

    bundle = tmp_path / "cuda-unavailable.zip"
    FIXTURES._write_bundle(bundle, docs)
    with pytest.raises(VERIFIER.EvidenceError, match="requires CUDA availability"):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_result_evidence_key_path_mismatch(tmp_path: Path) -> None:
    """Result evidence_key must bind the same candidate encoded by its archive path."""
    docs = FIXTURES._base_docs()
    config = json.loads(docs[f"{ROOT}/experiment-config.json"])
    candidate = config["candidate_roster"][0]
    runtime_bytes = docs[f"{ROOT}/runtime-receipt.json"]
    snapshot_path = f"{ROOT}/candidate-snapshots/{candidate['evidence_key']}.json"
    snapshot_bytes = docs[snapshot_path]

    result = {
        "schema_version": "MESC-EXPERIMENT-0-CANDIDATE-RESULT-V1",
        "experiment_config_sha256": hashlib.sha256(
            docs[f"{ROOT}/experiment-config.json"]
        ).hexdigest(),
        "runtime_receipt_sha256": hashlib.sha256(runtime_bytes).hexdigest(),
        "candidate_snapshot_receipt_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        "candidate_id": candidate["candidate_id"],
        "candidate_revision": candidate["candidate_revision"],
        "evidence_key": "different-candidate-key",
        "lane": "smoke",
        "metric_vector": {},
        "hard_floor_vector": {},
        "item_count": 0,
        "invalid_item_count": 0,
        "abstention_count": 0,
        "resource_usage": {},
        "query_budget_used": {},
        "result_exposure_used": {},
        "result_manifest_sha256": "4" * 64,
        "candidate_disposition": "BLOCKED_RUNTIME",
        "limitations": ["Synthetic mismatch fixture."],
    }
    result_path = f"{ROOT}/lane-results/{candidate['evidence_key']}/smoke.json"
    docs[result_path] = FIXTURES._json_bytes(result)

    bundle = tmp_path / "evidence-key-mismatch.zip"
    FIXTURES._write_bundle(bundle, docs)
    with pytest.raises(VERIFIER.EvidenceError, match="evidence_key/path mismatch"):
        VERIFIER.verify(str(bundle))