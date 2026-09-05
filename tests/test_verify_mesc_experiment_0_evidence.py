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
    path = Path(__file__).resolve().parents[1] / "tools" / "verify_mesc_experiment_0_evidence.py"
    spec = importlib.util.spec_from_file_location("mesc_exp0_verifier", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VERIFIER = _load_verifier()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _base_docs() -> dict[str, bytes]:
    config = {
        "schema_version": "MESC-EXPERIMENT-0-CONFIG-V1",
        "status": "FROZEN_EXECUTION_CONFIG",
        "experiment_id": "exp0-test",
        "objective_id": "objective-test",
        "repository_sha": "a" * 40,
        "repository_tree": "b" * 40,
        "candidate_roster": [{"candidate_id": "example/model", "revision": "c" * 40}],
    }
    config_bytes = _json_bytes(config)
    config_sha = hashlib.sha256(config_bytes).hexdigest()

    runtime = {
        "schema_version": "MESC-EXPERIMENT-0-RUNTIME-V1",
        "experiment_config_sha256": config_sha,
        "repository_sha": config["repository_sha"],
        "repository_tree": config["repository_tree"],
    }
    decision = {
        "schema_version": "MESC-EXPERIMENT-0-DECISION-V1",
        "experiment_config_sha256": config_sha,
        "decision_disposition": "INCONCLUSIVE_OR_BLOCKED",
        "selected_candidate_id": None,
        "selected_candidate_revision": None,
    }
    return {
        f"{ROOT}/experiment-config.json": config_bytes,
        f"{ROOT}/runtime-receipt.json": _json_bytes(runtime),
        f"{ROOT}/environment-manifest.json": _json_bytes({"packages": []}),
        f"{ROOT}/decision/foundation-decision.json": _json_bytes(decision),
    }


def _write_bundle(
    path: Path,
    docs: dict[str, bytes],
    *,
    manifest_self_entry: bool = False,
    extra_members: dict[str, bytes] | None = None,
) -> None:
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
    bundle = tmp_path / "valid.zip"
    _write_bundle(bundle, _base_docs())

    result = VERIFIER.verify(str(bundle))

    assert result["status"] == "VERIFIED_STRUCTURE_AND_IDENTITY"
    assert result["repository_sha"] == "a" * 40
    assert result["decision_disposition"] == "INCONCLUSIVE_OR_BLOCKED"


def test_verify_rejects_manifest_self_reference(tmp_path: Path) -> None:
    bundle = tmp_path / "self-ref.zip"
    _write_bundle(bundle, _base_docs(), manifest_self_entry=True)

    with pytest.raises(VERIFIER.EvidenceError, match="must not list/hash itself"):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_secret_bearing_field(tmp_path: Path) -> None:
    docs = _base_docs()
    docs[f"{ROOT}/environment-manifest.json"] = _json_bytes({"api_key": "do-not-store"})
    bundle = tmp_path / "secret.zip"
    _write_bundle(bundle, docs)

    with pytest.raises(VERIFIER.EvidenceError, match="forbidden secret-bearing field"):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_non_json_payload(tmp_path: Path) -> None:
    bundle = tmp_path / "weights.zip"
    _write_bundle(
        bundle,
        _base_docs(),
        extra_members={f"{ROOT}/candidate-snapshots/model.safetensors": b"not-weights"},
    )

    with pytest.raises(VERIFIER.EvidenceError, match="unexpected non-JSON payload"):
        VERIFIER.verify(str(bundle))


def test_verify_rejects_path_traversal(tmp_path: Path) -> None:
    bundle = tmp_path / "traversal.zip"
    with zipfile.ZipFile(bundle, "w") as archive:
        archive.writestr(f"{ROOT}/../escape.json", b"{}")

    with pytest.raises(VERIFIER.EvidenceError, match="path traversal"):
        VERIFIER.verify(str(bundle))
