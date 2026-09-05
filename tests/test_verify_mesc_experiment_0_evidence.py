from __future__ import annotations

import hashlib
import importlib.util
import json
import zipfile
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = "mesc-experiment-0-evidence"


def _load_verifier() -> ModuleType:
    """Load the verifier module from the repository tree."""
    path = Path(__file__).resolve().parents[1] / "tools" / "verify_mesc_experiment_0_evidence.py"
    spec = importlib.util.spec_from_file_location("mesc_exp0_verifier", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFIER = _load_verifier()


def _json_bytes(value: Any) -> bytes:
    """Serialize exact canonical JSON bytes used by Experiment-0 evidence."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _authority_bindings() -> dict[str, str]:
    """Create a complete synthetic MRL binding set for verifier tests."""
    return {key: f"test-{key}" for key in VERIFIER.REQUIRED_AUTHORITY_KEYS}


def _base_candidate() -> dict[str, Any]:
    """Return one selectable synthetic candidate with immutable identity."""
    return {
        "candidate_id": "example/model",
        "candidate_revision": "c" * 40,
        "candidate_class": "SELECTABLE_FOUNDATION",
        "evidence_key": "example-model",
        "supported_input_modalities": ["text", "vision"],
    }


def _base_config() -> dict[str, Any]:
    """Return a contract-complete frozen synthetic Experiment-0 configuration."""
    return {
        "schema_version": "MESC-EXPERIMENT-0-CONFIG-V1",
        "experiment_id": "exp0-test",
        "status": "FROZEN_EXECUTION_CONFIG",
        "objective_id": "objective-test",
        "repository_sha": "a" * 40,
        "repository_tree": "b" * 40,
        "strategy_decision_id": "ADR-0036",
        "candidate_roster": [_base_candidate()],
        "dataset_identities": [
            {
                "dataset_id": "dataset-test",
                "split_id": "split-test",
                "held_out_tier": "tier-test",
            }
        ],
        "evaluator_identities": [{"evaluator_id": "evaluator-test"}],
        "scoring_policy_identities": [{"scoring_policy_id": "scoring-test"}],
        "prompt_template_identities": [{"prompt_template_id": "prompt-test"}],
        "generation_configs": [{"generation_config_id": "generation-test"}],
        "runtime_policy": {
            "provider": "GOOGLE_COLAB",
            "require_hosted_gpu": True,
            "allowed_gpu_count": 1,
            "allowed_gpu_models": ["TEST_GPU"],
            "allow_unlisted_gpu_model": False,
        },
        "network_policy": {"allow_repository_clone": True},
        "filesystem_policy": {"allowed_write_roots": ["/content/mesc-experiment-0"]},
        "credential_policy": {"forbid_secret_printing": True},
        "resource_budget": {
            "max_gpu_hours": 1,
            "max_wall_hours": 2,
            "max_storage_bytes": 1_000_000,
            "max_retries": 0,
        },
        "query_budget": {"max_adaptive_queries": 0},
        "result_exposure_budget": {
            "tier1_max_exposures": 10,
            "tier2_max_exposures": 5,
            "tier3_allowed_fields": ["score"],
        },
        "hard_floor_policy": {
            "policy_id": "hard-floor-test",
            "rules": [{"id": "floor-1"}],
        },
        "decision_rule": {
            "rule_id": "decision-test",
            "type": "PREDECLARED",
            "definition": "Apply hard floors before ranking.",
        },
        "sealed_evaluation_policy": {
            "policy_id": "sealed-test",
            "tier3_item_access_by_research_process": False,
            "allowed_aggregate_fields": ["score"],
        },
        "authority_bindings": _authority_bindings(),
    }


def _base_snapshot(config_sha: str, candidate: dict[str, Any]) -> dict[str, Any]:
    """Return an explicit blocked snapshot receipt for the synthetic candidate."""
    return {
        "schema_version": "MESC-EXPERIMENT-0-CANDIDATE-SNAPSHOT-V1",
        "experiment_config_sha256": config_sha,
        "candidate_id": candidate["candidate_id"],
        "candidate_revision": candidate["candidate_revision"],
        "candidate_class": candidate["candidate_class"],
        "evidence_key": candidate["evidence_key"],
        "resolved_revision": candidate["candidate_revision"],
        "processor_or_tokenizer_identity": "processor-test",
        "model_config_sha256": "1" * 64,
        "snapshot_manifest_sha256": "2" * 64,
        "snapshot_file_count": 1,
        "snapshot_total_bytes": 100,
        "license_identity": "license-test",
        "notice_identity": "notice-test",
        "usage_policy_identity": "usage-policy-test",
        "trust_remote_code": False,
        "remote_code_exception_identity": None,
        "load_disposition": "BLOCKED_RUNTIME",
        "failure_stage": "load",
        "failure_class": "SyntheticBlock",
        "failure_message_sha256": "3" * 64,
        "allocated_memory_after_load_bytes": 0,
        "reserved_memory_after_load_bytes": 0,
        "peak_allocated_memory_bytes": 0,
        "peak_reserved_memory_bytes": 0,
    }


def _base_docs() -> dict[str, bytes]:
    """Build one internally bound metadata-only inconclusive evidence set."""
    config = _base_config()
    config_bytes = _json_bytes(config)
    config_sha = hashlib.sha256(config_bytes).hexdigest()
    candidate = config["candidate_roster"][0]

    environment = {
        "schema_version": "MESC-EXPERIMENT-0-ENVIRONMENT-V1",
        "python_version": "3.12.0",
        "platform": "test-platform",
        "packages": [{"name": "torch", "version": "test"}],
    }
    environment_bytes = _json_bytes(environment)
    environment_sha = hashlib.sha256(environment_bytes).hexdigest()

    runtime = {
        "schema_version": "MESC-EXPERIMENT-0-RUNTIME-V1",
        "experiment_config_sha256": config_sha,
        "repository_sha": config["repository_sha"],
        "repository_tree": config["repository_tree"],
        "execution_started_at_utc": "2026-09-05T00:00:00+00:00",
        "execution_completed_at_utc": "2026-09-05T00:01:00+00:00",
        "runtime_provider": "GOOGLE_COLAB",
        "runtime_class": "GOOGLE_COLAB_HOSTED_GPU_RUNTIME",
        "python_version": "3.12.0",
        "platform_string": "test-platform",
        "torch_version": "test",
        "transformers_version": None,
        "cuda_available": True,
        "cuda_version": "test",
        "gpu_count": 1,
        "gpu_models": ["TEST_GPU"],
        "gpu_total_memory_bytes": [1_000_000],
        "colab_release_tag_or_image_identity_if_observable": None,
        "installed_environment_manifest_sha256": environment_sha,
        "network_policy_observation": "FROZEN_POLICY_OBSERVED",
        "credential_surface_observation": "NO_SECRET_PERSISTENCE_OBSERVED",
        "final_runtime_disposition": "PASS_RUNTIME_PREFLIGHT",
        "stop_reason": None,
    }
    decision = {
        "schema_version": "MESC-EXPERIMENT-0-DECISION-V1",
        "experiment_config_sha256": config_sha,
        "candidate_result_sha256s": [],
        "hard_floor_summary": {
            "all_mandatory_passed": False,
            "failed_floor_ids": [],
        },
        "metric_vector_summary": {},
        "resource_summary": {},
        "rights_summary": {},
        "contamination_summary": {},
        "sealed_evaluation_receipt_identity": None,
        "selected_candidate_id": None,
        "selected_candidate_revision": None,
        "rationale": "Synthetic test bundle is intentionally inconclusive.",
        "limitations": ["No candidate execution in this test."],
        "decision_disposition": "INCONCLUSIVE_OR_BLOCKED",
    }
    snapshot = _base_snapshot(config_sha, candidate)
    return {
        f"{ROOT}/experiment-config.json": config_bytes,
        f"{ROOT}/runtime-receipt.json": _json_bytes(runtime),
        f"{ROOT}/environment-manifest.json": environment_bytes,
        f"{ROOT}/candidate-snapshots/{candidate['evidence_key']}.json": (_json_bytes(snapshot)),
        f"{ROOT}/decision/foundation-decision.json": _json_bytes(decision),
    }


def _replace_config(docs: dict[str, bytes], config: dict[str, Any]) -> None:
    """Replace config bytes and rebind dependent synthetic records."""
    config_bytes = _json_bytes(config)
    config_sha = hashlib.sha256(config_bytes).hexdigest()
    docs[f"{ROOT}/experiment-config.json"] = config_bytes

    runtime = json.loads(docs[f"{ROOT}/runtime-receipt.json"])
    runtime["experiment_config_sha256"] = config_sha
    runtime["repository_sha"] = config["repository_sha"]
    runtime["repository_tree"] = config["repository_tree"]
    docs[f"{ROOT}/runtime-receipt.json"] = _json_bytes(runtime)

    decision = json.loads(docs[f"{ROOT}/decision/foundation-decision.json"])
    decision["experiment_config_sha256"] = config_sha
    docs[f"{ROOT}/decision/foundation-decision.json"] = _json_bytes(decision)

    candidate = config["candidate_roster"][0]
    old_snapshot = next(path for path in docs if "/candidate-snapshots/" in path)
    docs.pop(old_snapshot)
    path = f"{ROOT}/candidate-snapshots/{candidate['evidence_key']}.json"
    docs[path] = _json_bytes(_base_snapshot(config_sha, candidate))


def _write_bundle(
    path: Path,
    docs: dict[str, bytes],
    *,
    manifest_self_entry: bool = False,
    extra_members: dict[str, bytes] | None = None,
) -> None:
    """Write a synthetic bundle with exact member manifest."""
    members = dict(docs)
    if extra_members:
        members.update(extra_members)
    entries = [
        {
            "path": name,
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
            "media_type": "application/json",
        }
        for name, data in sorted(members.items())
    ]
    if manifest_self_entry:
        entries.append(
            {
                "path": f"{ROOT}/manifests/bundle-manifest.json",
                "size_bytes": 0,
                "sha256": "0" * 64,
                "media_type": "application/json",
            }
        )
    manifest = _json_bytes(
        {
            "schema_version": "MESC-EXPERIMENT-0-BUNDLE-V1",
            "entries": entries,
        }
    )
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(members.items()):
            archive.writestr(name, data)
        archive.writestr(f"{ROOT}/manifests/bundle-manifest.json", manifest)


def test_verify_accepts_valid_metadata_bundle(tmp_path: Path) -> None:
    """A complete internally bound inconclusive metadata bundle is accepted."""
    bundle = tmp_path / "valid.zip"
    _write_bundle(bundle, _base_docs())
    result = VERIFIER.verify(str(bundle))
    assert result["status"] == "VERIFIED_STRUCTURE_AND_IDENTITY"
    assert result["repository_sha"] == "a" * 40
    assert result["decision_disposition"] == "INCONCLUSIVE_OR_BLOCKED"


def test_verify_rejects_manifest_self_reference(tmp_path: Path) -> None:
    """The bundle manifest cannot recursively hash itself."""
    bundle = tmp_path / "self-ref.zip"
    _write_bundle(bundle, _base_docs(), manifest_self_entry=True)
    with pytest.raises(VERIFIER.EvidenceError, match="must not list/hash itself"):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_secret_bearing_field(tmp_path: Path) -> None:
    """Credential-like JSON field names are rejected."""
    docs = _base_docs()
    docs[f"{ROOT}/environment-manifest.json"] = _json_bytes({"api_key": "do-not-store"})
    bundle = tmp_path / "secret.zip"
    _write_bundle(bundle, docs)
    with pytest.raises(VERIFIER.EvidenceError, match="forbidden secret-bearing field"):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_secret_like_value(tmp_path: Path) -> None:
    """Credential-like serialized values are rejected."""
    docs = _base_docs()
    docs[f"{ROOT}/environment-manifest.json"] = _json_bytes(
        {
            "schema_version": "MESC-EXPERIMENT-0-ENVIRONMENT-V1",
            "package_source": "https://user:password@example.invalid/x",
        }
    )
    bundle = tmp_path / "secret-value.zip"
    _write_bundle(bundle, docs)
    with pytest.raises(VERIFIER.EvidenceError, match="possible secret-bearing value"):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_missing_mrl_binding(tmp_path: Path) -> None:
    """A frozen config cannot omit any MRL authority/evidence binding."""
    docs = _base_docs()
    config = json.loads(docs[f"{ROOT}/experiment-config.json"])
    config["authority_bindings"]["mrl_0807_evaluator_freeze_id"] = None
    _replace_config(docs, config)
    bundle = tmp_path / "missing-binding.zip"
    _write_bundle(bundle, docs)
    with pytest.raises(
        VERIFIER.EvidenceError,
        match="incomplete MRL authority/evidence bindings",
    ):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_unfrozen_budget(tmp_path: Path) -> None:
    """A named frozen config with a null execution budget fails closed."""
    docs = _base_docs()
    config = json.loads(docs[f"{ROOT}/experiment-config.json"])
    config["resource_budget"]["max_gpu_hours"] = None
    _replace_config(docs, config)
    bundle = tmp_path / "unfrozen-budget.zip"
    _write_bundle(bundle, docs)
    with pytest.raises(VERIFIER.EvidenceError, match="resource_budget.max_gpu_hours"):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_environment_hash_mismatch(tmp_path: Path) -> None:
    """Runtime receipts must bind the exact environment-manifest bytes."""
    docs = _base_docs()
    environment = json.loads(docs[f"{ROOT}/environment-manifest.json"])
    environment["packages"].append({"name": "transformers", "version": "changed"})
    docs[f"{ROOT}/environment-manifest.json"] = _json_bytes(environment)
    bundle = tmp_path / "environment-drift.zip"
    _write_bundle(bundle, docs)
    with pytest.raises(
        VERIFIER.EvidenceError,
        match="environment-manifest hash mismatch",
    ):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_reference_only_selection(tmp_path: Path) -> None:
    """A reference-only comparator cannot become the selected MESC foundation."""
    docs = _base_docs()
    config = json.loads(docs[f"{ROOT}/experiment-config.json"])
    config["candidate_roster"][0]["candidate_class"] = "REFERENCE_ONLY"
    _replace_config(docs, config)
    decision = json.loads(docs[f"{ROOT}/decision/foundation-decision.json"])
    decision["decision_disposition"] = "SELECT_CHALLENGER"
    decision["selected_candidate_id"] = config["candidate_roster"][0]["candidate_id"]
    decision["selected_candidate_revision"] = config["candidate_roster"][0]["candidate_revision"]
    docs[f"{ROOT}/decision/foundation-decision.json"] = _json_bytes(decision)
    bundle = tmp_path / "reference-only.zip"
    _write_bundle(bundle, docs)
    with pytest.raises(
        VERIFIER.EvidenceError,
        match="reference-only candidate cannot be selected",
    ):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_non_json_payload(tmp_path: Path) -> None:
    """Weights and binary payloads cannot be smuggled into evidence bundles."""
    bundle = tmp_path / "weights.zip"
    _write_bundle(
        bundle,
        _base_docs(),
        extra_members={f"{ROOT}/candidate-snapshots/model.safetensors": b"not-weights"},
    )
    with pytest.raises(VERIFIER.EvidenceError, match="unexpected non-JSON payload"):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_path_traversal(tmp_path: Path) -> None:
    """Traversal paths are rejected before archive extraction or use."""
    bundle = tmp_path / "traversal.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr(f"{ROOT}/../escape.json", b"{}")
    with pytest.raises(VERIFIER.EvidenceError, match="path traversal"):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_oversized_member_before_read(tmp_path: Path) -> None:
    """Declared oversized members fail before their bytes are retained."""
    bundle = tmp_path / "oversized.zip"
    oversized = b"x" * (VERIFIER.MAX_MEMBER_UNCOMPRESSED_BYTES + 1)
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(f"{ROOT}/oversized.json", oversized)
    with pytest.raises(VERIFIER.EvidenceError, match="ZIP member exceeds size limit"):
        VERIFIER.verify(str(bundle))
