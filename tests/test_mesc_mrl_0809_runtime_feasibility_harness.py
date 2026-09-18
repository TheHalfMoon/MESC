"""Adversarial coverage for the bounded MRL-0809 runtime-feasibility harness."""

from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes as repository_canonical_json

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mesc_mrl_0809_runtime_feasibility.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mesc_mrl_0809_runtime_feasibility_test", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HARNESS = _load()
_QWEN = "Qwen/Qwen3.8-27B"
_GEMMA = "google/gemma-4-31B-it"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _staging_policy(selected_bytes: int) -> dict[str, object]:
    required = selected_bytes + HARNESS.STAGING_CONTROL_RESERVE_BYTES
    roster_required = HARNESS._required_roster_staging_free_bytes()
    return {
        "control_reserve_bytes": HARNESS.STAGING_CONTROL_RESERVE_BYTES,
        "download_max_workers": HARNESS.STAGING_MAX_WORKERS,
        "global_cache_reuse": False,
        "observed_free_bytes_after": HARNESS.STAGING_CONTROL_RESERVE_BYTES + 1,
        "observed_free_bytes_before": roster_required + 1,
        "required_free_bytes_before": required,
        "roster_preflight_candidates": sorted(HARNESS.EXPECTED_CANDIDATES),
        "roster_required_free_bytes_before": roster_required,
        "schema_version": HARNESS.STAGING_POLICY_SCHEMA,
        "selected_payload_bytes": selected_bytes,
        "xet_enabled": False,
    }


def test_harness_canonical_json_matches_repository_contract() -> None:
    value = {
        "a": [None, True, 7, "text"],
        "z": {"nested": False},
    }
    assert HARNESS.canonical_json_bytes(value) == repository_canonical_json(value)
    with pytest.raises(HARNESS.HarnessError, match="floating-point"):
        HARNESS.canonical_json_bytes({"x": 1.5})
    with pytest.raises(HARNESS.HarnessError, match="keys"):
        HARNESS.canonical_json_bytes({1: "forbidden"})


def test_parser_rejects_duplicate_and_noncanonical_json() -> None:
    with pytest.raises(HARNESS.HarnessError, match="invalid JSON"):
        HARNESS.parse_canonical_object(b'{"a":1,"a":2}\n', label="receipt")
    with pytest.raises(HARNESS.HarnessError, match="not canonical JSON"):
        HARNESS.parse_canonical_object(b'{"b":2, "a":1}\n', label="receipt")


def test_snapshot_validation_binds_exact_metadata_and_weights(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    config = b'{"architecture":"fixture"}\n'
    tokenizer = b'{"tokenizer":"fixture"}\n'
    processor = b'{"processor":"fixture"}\n'
    (snapshot / "config.json").write_bytes(config)
    (snapshot / "tokenizer_config.json").write_bytes(tokenizer)
    (snapshot / "processor_config.json").write_bytes(processor)
    (snapshot / "model-00001-of-00001.safetensors").write_bytes(b"synthetic-weight-fixture")

    expected = dict(HARNESS.EXPECTED_CANDIDATES[_QWEN])
    expected["config_sha256"] = _sha(config)
    expected["tokenizer_config_sha256"] = _sha(tokenizer)
    expected["processor_config_sha256"] = _sha(processor)
    monkeypatch.setitem(HARNESS.EXPECTED_CANDIDATES, _QWEN, expected)

    digests, file_count, total_bytes = HARNESS._validate_snapshot(_QWEN, snapshot)
    assert digests["config_sha256"] == _sha(config)
    assert file_count == 4
    assert total_bytes > 0

    (snapshot / "config.json").write_bytes(config + b" ")
    with pytest.raises(HARNESS.HarnessError, match="config_sha256 drifted"):
        HARNESS._validate_snapshot(_QWEN, snapshot)


def test_payload_manifest_rejects_symlink_and_nested_payload(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    target = snapshot / "config.json"
    target.write_bytes(b"fixture\n")
    link = snapshot / "tokenizer.json"
    link.symlink_to(target.name)
    with pytest.raises(HARNESS.HarnessError, match="must not be symlinks"):
        HARNESS._payload_manifest(snapshot)

    link.unlink()
    nested = snapshot / "nested"
    nested.mkdir()
    (nested / "tokenizer.json").write_bytes(b"fixture\n")
    with pytest.raises(HARNESS.HarnessError, match="root-level basenames"):
        HARNESS._payload_manifest(snapshot)


def test_stage_receipt_binds_entire_payload_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    files = {
        "config.json": b'{"architecture":"fixture"}\n',
        "tokenizer_config.json": b'{"tokenizer":"fixture"}\n',
        "processor_config.json": b'{"processor":"fixture"}\n',
        "tokenizer.json": b"tokenizer-A\n",
        "model.safetensors": b"synthetic-weight-fixture",
    }
    for name, raw in files.items():
        (snapshot / name).write_bytes(raw)

    expected = dict(HARNESS.EXPECTED_CANDIDATES[_QWEN])
    expected["config_sha256"] = _sha(files["config.json"])
    expected["tokenizer_config_sha256"] = _sha(files["tokenizer_config.json"])
    expected["processor_config_sha256"] = _sha(files["processor_config.json"])
    monkeypatch.setitem(HARNESS.EXPECTED_CANDIDATES, _QWEN, expected)

    weight_manifest = [
        {
            "byte_count": len(files["model.safetensors"]),
            "kind": "weight",
            "path": "model.safetensors",
            "sha256": _sha(files["model.safetensors"]),
        }
    ]
    monkeypatch.setattr(
        HARNESS,
        "_validate_weight_identity",
        lambda candidate, value: (
            expected["weights_sha256"],
            expected["artifact_identity_sha256"],
            weight_manifest,
        ),
    )
    monkeypatch.setattr(
        HARNESS,
        "_mrl0801_weight_allowlist",
        lambda root, candidate: ("model.safetensors",),
    )

    payload_manifest = HARNESS._payload_manifest(snapshot)
    selected_files = tuple(item["path"] for item in payload_manifest)
    selected_bytes = sum(item["byte_count"] for item in payload_manifest)
    receipt = {
        "artifact_identity_sha256": expected["artifact_identity_sha256"],
        "config_sha256": expected["config_sha256"],
        "model_id": _QWEN,
        "mrl_0801_authorization_sha256": HARNESS.MRL0801_AUTH_SHA256,
        "payload_manifest": payload_manifest,
        "processor_config_sha256": expected["processor_config_sha256"],
        "remote_selected_bytes": selected_bytes,
        "remote_selected_files": list(selected_files),
        "revision": expected["revision"],
        "schema_version": HARNESS.SCHEMA_STAGE,
        "staging_policy": _staging_policy(selected_bytes),
        "snapshot_file_count": len(payload_manifest),
        "snapshot_total_bytes": selected_bytes,
        "tokenizer_config_sha256": expected["tokenizer_config_sha256"],
        "weight_files": weight_manifest,
        "weights_sha256": expected["weights_sha256"],
    }
    receipt_path = tmp_path / "stage.json"
    receipt_path.write_bytes(HARNESS.canonical_json_bytes(receipt))

    HARNESS._read_stage_receipt(_QWEN, snapshot, receipt_path, root=tmp_path)

    original = (snapshot / "tokenizer.json").read_bytes()
    (snapshot / "tokenizer.json").write_bytes(original.replace(b"A", b"B"))
    assert (snapshot / "tokenizer.json").stat().st_size == len(original)
    with pytest.raises(HARNESS.HarnessError, match="payload manifest drifted"):
        HARNESS._read_stage_receipt(_QWEN, snapshot, receipt_path, root=tmp_path)


def test_evidence_paths_must_remain_outside_repository(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    inside = root / "evidence.json"
    with pytest.raises(HARNESS.HarnessError, match="outside the repository"):
        HARNESS._require_outside_repository(inside, root, label="evidence")
    outside = tmp_path / "custody" / "evidence.json"
    outside.parent.mkdir()
    assert HARNESS._require_outside_repository(outside, root, label="evidence") == outside


def test_gpu_context_is_exact_tesla_t4(monkeypatch: pytest.MonkeyPatch) -> None:
    def t4(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["nvidia-smi"],
            returncode=0,
            stdout="Tesla T4, GPU-test, 15360\n",
            stderr="",
        )

    monkeypatch.setattr(HARNESS.subprocess, "run", t4)
    name, uuid, vram = HARNESS._gpu_context()
    assert (name, uuid, vram) == ("Tesla T4", "GPU-test", 15360 * 1024 * 1024)

    def wrong(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=["nvidia-smi"],
            returncode=0,
            stdout="NVIDIA A100-SXM4-40GB, GPU-test, 40960\n",
            stderr="",
        )

    monkeypatch.setattr(HARNESS.subprocess, "run", wrong)
    with pytest.raises(HARNESS.HarnessError, match="Tesla T4"):
        HARNESS._gpu_context()


def test_package_versions_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        HARNESS.importlib.metadata,
        "version",
        lambda name: HARNESS.EXPECTED_PACKAGES[name],
    )
    assert HARNESS._package_versions() == HARNESS.EXPECTED_PACKAGES

    monkeypatch.setattr(
        HARNESS.importlib.metadata,
        "version",
        lambda name: "0.0.0" if name == "torch" else HARNESS.EXPECTED_PACKAGES[name],
    )
    with pytest.raises(HARNESS.HarnessError, match="torch must be exactly"):
        HARNESS._package_versions()


def test_sandbox_mounts_only_runtime_material_not_repository(tmp_path: Path) -> None:
    harness = tmp_path / "harness.py"
    snapshot = tmp_path / "snapshot"
    base = tmp_path / "python-base"
    site = tmp_path / "site-packages"
    prefix = HARNESS._sandbox_prefix(
        bwrap=Path("/usr/bin/bwrap"),
        harness=harness,
        snapshot=snapshot,
        base_prefix=base,
        site_packages=site,
        nvidia_nodes=(Path("/dev/nvidia0"),),
    )
    rendered = "\n".join(prefix)
    assert "--unshare-all" in prefix
    assert "/mesc-run/harness.py" in prefix
    assert "/mesc-run/model-weights" in prefix
    assert "/mesc-run/python-base" in prefix
    assert "/mesc-run/site-packages" in prefix
    assert "/mesc-run/repository" not in rendered
    assert "scientific-corpus" not in rendered
    assert "tier3" not in rendered.lower()


def test_runtime_identity_binds_harness_bytes() -> None:
    kwargs = {
        "bwrap_sha256": "a" * 64,
        "bwrap_version": "bubblewrap 0.11.0",
        "colab_release_tag": "release-fixture",
        "gpu_model": "Tesla T4",
        "gpu_uuid": "GPU-fixture",
        "gpu_vram_bytes": 1,
        "kernel_release": "kernel-fixture",
        "package_versions": dict(HARNESS.EXPECTED_PACKAGES),
        "provider_execution_id": "colab-fixture",
        "python_version": "3.11.15",
        "harness_sha256": "b" * 64,
    }
    first, first_sha = HARNESS._runtime_identity(**kwargs)
    second, second_sha = HARNESS._runtime_identity(**kwargs)
    assert first == second
    assert first_sha == second_sha
    assert first["harness_sha256"] == "b" * 64

    changed = dict(kwargs)
    changed["harness_sha256"] = "c" * 64
    _, changed_sha = HARNESS._runtime_identity(**changed)
    assert changed_sha != first_sha


def _candidate(model_id: str, generation: dict[str, object]) -> dict[str, object]:
    expected = HARNESS.EXPECTED_CANDIDATES[model_id]
    return {
        "architecture": expected["architecture"],
        "config_sha256": expected["config_sha256"],
        "load_completed": True,
        "model_id": model_id,
        "peak_cpu_memory_bytes": 1024,
        "peak_gpu_memory_bytes": 2048,
        "processor_config_sha256": expected["processor_config_sha256"],
        "revision": expected["revision"],
        "runtime_representation": HARNESS.RUNTIME_REPRESENTATION,
        "synthetic_generation_completed": True,
        "synthetic_generation_sha256": _sha(HARNESS.canonical_json_bytes(generation)),
        "text_only_generation": True,
        "text_vocab_size": expected["text_vocab_size"],
        "tokenizer_config_sha256": expected["tokenizer_config_sha256"],
        "unloaded_after_probe": True,
    }


def _observation(
    *,
    model_id: str,
    repository_sha: str,
    repository_tree: str,
    manifest_sha: str,
    lock_sha: str,
    execution_id: str = "colab-fixture",
    harness_sha256: str = "f" * 64,
    stage_receipt_sha256: str = "a" * 64,
) -> dict[str, object]:
    generation: dict[str, object] = {
        "decoded_text_sha256": "d" * 64,
        "generated_token_ids": [11, 12],
        "synthetic_prompt_sha256": (
            "19db6d407fdb52d48b9894900e3f0afe9e81b4a12e96669ef8a863419ba4d60d"
        ),
    }
    identity, identity_sha = HARNESS._runtime_identity(
        bwrap_sha256="a" * 64,
        bwrap_version="bubblewrap 0.11.0",
        colab_release_tag="release-fixture",
        gpu_model="Tesla T4",
        gpu_uuid="GPU-fixture",
        gpu_vram_bytes=15360 * 1024 * 1024,
        kernel_release="kernel-fixture",
        package_versions=dict(HARNESS.EXPECTED_PACKAGES),
        provider_execution_id=execution_id,
        python_version="3.11.15",
        harness_sha256=harness_sha256,
    )
    return {
        "candidate": _candidate(model_id, generation),
        "dependency_lock_sha256": lock_sha,
        "generation_evidence": generation,
        "provider_execution_id": execution_id,
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "runtime_identity": identity,
        "runtime_identity_sha256": identity_sha,
        "schema_version": HARNESS.SCHEMA_OBSERVATION,
        "stage_artifact_identity_sha256": HARNESS.EXPECTED_CANDIDATES[model_id][
            "artifact_identity_sha256"
        ],
        "stage_receipt_sha256": stage_receipt_sha256,
        "stage_weights_sha256": HARNESS.EXPECTED_CANDIDATES[model_id]["weights_sha256"],
        "static_prerequisite_manifest_sha256": manifest_sha,
    }


def _stage_receipt(model_id: str) -> dict[str, object]:
    expected = HARNESS.EXPECTED_CANDIDATES[model_id]
    payload = [
        {"byte_count": 1, "path": "config.json", "sha256": expected["config_sha256"]},
        {"byte_count": 1, "path": "model.safetensors", "sha256": "a" * 64},
        {
            "byte_count": 1,
            "path": "processor_config.json",
            "sha256": expected["processor_config_sha256"],
        },
        {
            "byte_count": 1,
            "path": "tokenizer_config.json",
            "sha256": expected["tokenizer_config_sha256"],
        },
    ]
    return {
        "artifact_identity_sha256": expected["artifact_identity_sha256"],
        "config_sha256": expected["config_sha256"],
        "model_id": model_id,
        "mrl_0801_authorization_sha256": HARNESS.MRL0801_AUTH_SHA256,
        "payload_manifest": payload,
        "processor_config_sha256": expected["processor_config_sha256"],
        "remote_selected_bytes": 4,
        "remote_selected_files": [row["path"] for row in payload],
        "revision": expected["revision"],
        "schema_version": HARNESS.SCHEMA_STAGE,
        "staging_policy": _staging_policy(4),
        "snapshot_file_count": 4,
        "snapshot_total_bytes": 4,
        "tokenizer_config_sha256": expected["tokenizer_config_sha256"],
        "weight_files": [
            {
                "byte_count": 1,
                "kind": "weight",
                "path": "model.safetensors",
                "sha256": "a" * 64,
            }
        ],
        "weights_sha256": expected["weights_sha256"],
    }


def test_assembly_self_validates_with_canonical_validator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    (root / HARNESS.STATIC_MANIFEST.parent).mkdir(parents=True)
    (root / HARNESS.STATIC_MANIFEST).write_bytes(b"manifest-fixture\n")
    (root / HARNESS.LOCKFILE).write_bytes(b"lock-fixture\n")
    evidence = tmp_path / "custody"
    evidence.mkdir()

    repository_sha = "1" * 40
    repository_tree = "2" * 40
    manifest_sha = HARNESS.sha256_file(root / HARNESS.STATIC_MANIFEST)
    lock_sha = HARNESS.sha256_file(root / HARNESS.LOCKFILE)
    monkeypatch.setattr(
        HARNESS,
        "_require_repository",
        lambda value: (repository_sha, repository_tree),
    )

    observations: list[Path] = []
    for index, model_id in enumerate((_QWEN, _GEMMA)):
        path = evidence / f"candidate-{index}.json"
        path.write_bytes(
            HARNESS.canonical_json_bytes(
                _observation(
                    model_id=model_id,
                    repository_sha=repository_sha,
                    repository_tree=repository_tree,
                    manifest_sha=manifest_sha,
                    lock_sha=lock_sha,
                )
            )
        )
        observations.append(path)

    output = evidence / "runtime-feasibility.json"
    HARNESS.assemble_receipt(root, observations, output)
    raw = output.read_bytes()

    from medscale.mesc._mrl_0809_runtime_feasibility_v1 import (
        validate_runtime_feasibility_receipt,
    )

    validated = validate_runtime_feasibility_receipt(
        raw,
        expected_static_prerequisite_manifest_sha256=manifest_sha,
        expected_dependency_lock_sha256=lock_sha,
        expected_repository_sha=repository_sha,
        expected_repository_tree=repository_tree,
    )
    assert validated.receipt_sha256 == _sha(raw)
    assert validated.runtime_representation == HARNESS.RUNTIME_REPRESENTATION
    assert validated.runtime_identity["harness_sha256"] == "f" * 64
    document = HARNESS.parse_canonical_object(raw, label="assembled receipt")
    candidates = document["candidates"]
    assert isinstance(candidates, list)
    for row in candidates:
        assert isinstance(row, dict)
        expected = HARNESS.EXPECTED_CANDIDATES[row["model_id"]]
        assert row["weights_sha256"] == expected["weights_sha256"]
        assert row["artifact_identity_sha256"] == expected["artifact_identity_sha256"]


def test_assembly_rejects_cross_session_candidate_mix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    (root / HARNESS.STATIC_MANIFEST.parent).mkdir(parents=True)
    (root / HARNESS.STATIC_MANIFEST).write_bytes(b"manifest-fixture\n")
    (root / HARNESS.LOCKFILE).write_bytes(b"lock-fixture\n")
    evidence = tmp_path / "custody"
    evidence.mkdir()
    repository_sha = "1" * 40
    repository_tree = "2" * 40
    manifest_sha = HARNESS.sha256_file(root / HARNESS.STATIC_MANIFEST)
    lock_sha = HARNESS.sha256_file(root / HARNESS.LOCKFILE)
    monkeypatch.setattr(
        HARNESS,
        "_require_repository",
        lambda value: (repository_sha, repository_tree),
    )

    paths: list[Path] = []
    for index, (model_id, execution_id) in enumerate(((_QWEN, "colab-a"), (_GEMMA, "colab-b"))):
        path = evidence / f"candidate-{index}.json"
        path.write_bytes(
            HARNESS.canonical_json_bytes(
                _observation(
                    model_id=model_id,
                    repository_sha=repository_sha,
                    repository_tree=repository_tree,
                    manifest_sha=manifest_sha,
                    lock_sha=lock_sha,
                    execution_id=execution_id,
                )
            )
        )
        paths.append(path)

    with pytest.raises(HARNESS.HarnessError, match="provider_execution_id"):
        HARNESS.assemble_receipt(root, paths, evidence / "receipt.json")


def test_remote_capacity_preflight_returns_exact_file_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    root = tmp_path / "repo"
    auth = root / HARNESS.MRL0801_AUTH
    auth.parent.mkdir(parents=True)
    auth.write_bytes((ROOT / HARNESS.MRL0801_AUTH).read_bytes())
    weights = HARNESS._mrl0801_weight_allowlist(root, _QWEN)

    siblings = [
        SimpleNamespace(rfilename=name, size=100)
        for name in (
            *weights,
            "config.json",
            "tokenizer_config.json",
            "processor_config.json",
            "tokenizer.json",
            "tokenizer/nested-should-not-stage.json",
            "README.md",
        )
    ]

    class Hub:
        @staticmethod
        def model_info(model_id: str, *, revision: str, files_metadata: bool) -> SimpleNamespace:
            assert model_id == _QWEN
            assert revision == HARNESS.EXPECTED_CANDIDATES[_QWEN]["revision"]
            assert files_metadata is True
            return SimpleNamespace(siblings=siblings)

    monkeypatch.setattr(
        HARNESS.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=100 * 1024 * 1024 * 1024),
    )
    selected, total, free_before = HARNESS._remote_capacity_preflight(
        hub=Hub(),
        root=root,
        candidate=_QWEN,
        destination_parent=tmp_path,
    )
    assert set(weights) <= set(selected)
    assert "config.json" in selected
    assert "tokenizer.json" in selected
    assert "tokenizer/nested-should-not-stage.json" not in selected
    assert "README.md" not in selected
    assert not any("*" in name for name in selected)
    assert total == len(selected) * 100
    assert free_before == 100 * 1024 * 1024 * 1024

    monkeypatch.setattr(
        HARNESS.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=1),
    )
    with pytest.raises(HARNESS.HarnessError, match="insufficient free storage"):
        HARNESS._remote_capacity_preflight(
            hub=Hub(),
            root=root,
            candidate=_QWEN,
            destination_parent=tmp_path,
        )


def test_storage_policy_uses_exact_payload_plus_control_reserve() -> None:
    selected = 62_578_656_403
    required = HARNESS._required_staging_free_bytes(selected)
    roster_required = HARNESS._required_roster_staging_free_bytes()
    assert required == selected + 1024 * 1024 * 1024
    assert required == 63_652_398_227
    assert roster_required == required

    policy = HARNESS._staging_policy(
        selected_total=selected,
        free_before=roster_required,
        free_after=HARNESS.STAGING_CONTROL_RESERVE_BYTES,
    )
    receipt = {
        "remote_selected_bytes": selected,
        "staging_policy": policy,
    }
    HARNESS._validate_staging_policy_envelope(receipt)


def test_storage_policy_fails_closed_for_drift_or_insufficient_reserve() -> None:
    selected = 1_000
    roster_required = HARNESS._required_roster_staging_free_bytes()
    with pytest.raises(HARNESS.HarnessError, match="roster bound"):
        HARNESS._staging_policy(
            selected_total=selected,
            free_before=roster_required - 1,
            free_after=HARNESS.STAGING_CONTROL_RESERVE_BYTES,
        )
    with pytest.raises(HARNESS.HarnessError, match="control reserve"):
        HARNESS._staging_policy(
            selected_total=selected,
            free_before=roster_required,
            free_after=HARNESS.STAGING_CONTROL_RESERVE_BYTES - 1,
        )

    policy = _staging_policy(selected)
    policy["download_max_workers"] = 2
    with pytest.raises(HARNESS.HarnessError, match="staging policy drifted"):
        HARNESS._validate_staging_policy_envelope(
            {"remote_selected_bytes": selected, "staging_policy": policy}
        )

    policy = _staging_policy(selected)
    policy["roster_preflight_candidates"] = [_QWEN]
    with pytest.raises(HARNESS.HarnessError, match="roster preflight candidate set drifted"):
        HARNESS._validate_staging_policy_envelope(
            {"remote_selected_bytes": selected, "staging_policy": policy}
        )


def test_prepare_hub_download_forces_xet_off(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    hub = SimpleNamespace()
    imports: list[str] = []

    def fake_import(name: str) -> object:
        imports.append(name)
        if name == "huggingface_hub":
            assert HARNESS.os.environ["HF_HUB_DISABLE_XET"] == "1"
            assert HARNESS.os.environ["HF_XET_CHUNK_CACHE_SIZE_BYTES"] == "0"
            return hub
        if name == "huggingface_hub.constants":
            return SimpleNamespace(HF_HUB_DISABLE_XET=True)
        raise AssertionError(name)

    monkeypatch.setattr(HARNESS.importlib, "import_module", fake_import)
    monkeypatch.delenv("HF_HUB_DISABLE_XET", raising=False)
    monkeypatch.delenv("HF_XET_CHUNK_CACHE_SIZE_BYTES", raising=False)
    assert HARNESS._prepare_hub_download() is hub
    assert imports == ["huggingface_hub", "huggingface_hub.constants"]


def test_stage_candidate_serializes_download_and_removes_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    root = tmp_path / "repo"
    root.mkdir()
    custody = tmp_path / "custody"
    custody.mkdir()
    destination = custody / "snapshot"
    receipt_path = custody / "stage.json"
    selected = (
        "config.json",
        "model.safetensors",
        "processor_config.json",
        "tokenizer_config.json",
    )
    selected_total = len(selected)
    roster_required = HARNESS._required_roster_staging_free_bytes()
    free_before = roster_required + 100
    free_after = HARNESS.STAGING_CONTROL_RESERVE_BYTES + 50
    expected = HARNESS.EXPECTED_CANDIDATES[_QWEN]
    captured: dict[str, object] = {}

    class Hub:
        @staticmethod
        def snapshot_download(**kwargs: object) -> str:
            captured.update(kwargs)
            local_dir = Path(str(kwargs["local_dir"]))
            for name in selected:
                (local_dir / name).write_bytes(b"x")
            metadata = local_dir / ".cache" / "huggingface"
            metadata.mkdir(parents=True, exist_ok=True)
            (metadata / "fixture").write_bytes(b"metadata")
            return str(local_dir)

    monkeypatch.setattr(HARNESS, "_require_repository", lambda value: ("1" * 40, "2" * 40))
    monkeypatch.setattr(
        HARNESS,
        "_require_colab_identity",
        lambda: ("session", "release", "Tesla T4", "GPU-test", 1),
    )
    monkeypatch.setattr(HARNESS, "_package_versions", lambda: dict(HARNESS.EXPECTED_PACKAGES))
    monkeypatch.setattr(HARNESS, "_prepare_hub_download", lambda: Hub())
    monkeypatch.setattr(
        HARNESS,
        "_remote_roster_capacity_preflight",
        lambda **kwargs: (selected, selected_total, free_before, roster_required),
    )
    monkeypatch.setattr(
        HARNESS.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=free_after),
    )
    monkeypatch.setattr(
        HARNESS,
        "_validate_snapshot",
        lambda candidate, snapshot: (
            {
                "config_sha256": expected["config_sha256"],
                "processor_config_sha256": expected["processor_config_sha256"],
                "tokenizer_config_sha256": expected["tokenizer_config_sha256"],
            },
            selected_total,
            selected_total,
        ),
    )
    weight_sha = _sha(b"x")
    weight_manifest = [
        {
            "byte_count": 1,
            "kind": "weight",
            "path": "model.safetensors",
            "sha256": weight_sha,
        }
    ]
    monkeypatch.setattr(
        HARNESS,
        "_validate_weight_identity",
        lambda candidate, snapshot: (
            expected["weights_sha256"],
            expected["artifact_identity_sha256"],
            weight_manifest,
        ),
    )

    HARNESS.stage_candidate(root, _QWEN, destination, receipt_path)

    assert captured["max_workers"] == 1
    assert captured["local_dir"] == str(destination)
    assert captured["allow_patterns"] == list(selected)
    assert captured["cache_dir"] == str(destination / ".cache" / "mesc-hub-cache")
    assert not (destination / ".cache").exists()
    receipt = HARNESS.parse_canonical_object(receipt_path.read_bytes(), label="stage receipt")
    assert receipt["staging_policy"] == HARNESS._staging_policy(
        selected_total=selected_total,
        free_before=free_before,
        free_after=free_after,
    )


def test_roster_preflight_checks_both_frozen_candidates_before_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    observed: list[str] = []

    def payload(*, hub: object, root: Path, candidate: str) -> tuple[tuple[str, ...], int]:
        observed.append(candidate)
        return (f"{candidate.replace('/', '-')}.bin",), HARNESS.EXPECTED_SELECTED_PAYLOAD_BYTES[
            candidate
        ]

    monkeypatch.setattr(HARNESS, "_remote_selected_payload", payload)
    roster_required = HARNESS._required_roster_staging_free_bytes()
    monkeypatch.setattr(
        HARNESS.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=roster_required),
    )
    selected, total, free_before, required = HARNESS._remote_roster_capacity_preflight(
        hub=object(),
        root=tmp_path,
        candidate=_QWEN,
        destination_parent=tmp_path,
    )
    assert observed == list(HARNESS.EXPECTED_CANDIDATES)
    assert selected == ("Qwen-Qwen3.8-27B.bin",)
    assert total == HARNESS.EXPECTED_SELECTED_PAYLOAD_BYTES[_QWEN]
    assert free_before == roster_required
    assert required == roster_required

    observed.clear()
    monkeypatch.setattr(
        HARNESS.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=roster_required - 1),
    )
    with pytest.raises(HARNESS.HarnessError, match="dual-candidate roster staging"):
        HARNESS._remote_roster_capacity_preflight(
            hub=object(),
            root=tmp_path,
            candidate=_QWEN,
            destination_parent=tmp_path,
        )
    assert observed == list(HARNESS.EXPECTED_CANDIDATES)


def test_roster_preflight_rejects_frozen_payload_size_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    def payload(*, hub: object, root: Path, candidate: str) -> tuple[tuple[str, ...], int]:
        expected = HARNESS.EXPECTED_SELECTED_PAYLOAD_BYTES[candidate]
        return ("fixture.bin",), expected + (1 if candidate == _GEMMA else 0)

    monkeypatch.setattr(HARNESS, "_remote_selected_payload", payload)
    monkeypatch.setattr(
        HARNESS.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=100 * 1024 * 1024 * 1024),
    )
    with pytest.raises(HARNESS.HarnessError, match="payload byte total drifted"):
        HARNESS._remote_roster_capacity_preflight(
            hub=object(),
            root=tmp_path,
            candidate=_QWEN,
            destination_parent=tmp_path,
        )


def test_weight_identity_must_match_mrl0801(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    expected = HARNESS.EXPECTED_CANDIDATES[_QWEN]
    original_import = HARNESS.importlib.import_module

    class IdentityModule:
        @staticmethod
        def identify_hf_safetensors_artifact(**kwargs: object) -> SimpleNamespace:
            assert kwargs["model_id"] == _QWEN
            assert kwargs["revision"] == expected["revision"]
            file_record = SimpleNamespace(
                to_dict=lambda: {
                    "byte_count": 1,
                    "kind": "weight",
                    "path": "model.safetensors",
                    "sha256": "a" * 64,
                }
            )
            return SimpleNamespace(
                weights_sha256=expected["weights_sha256"],
                verifier_receipt_sha256=expected["artifact_identity_sha256"],
                files=(file_record,),
            )

    def import_ok(name: str) -> object:
        if name == "medscale.mesc._training_hf_safetensors_identity_v1":
            return IdentityModule
        return original_import(name)

    monkeypatch.setattr(HARNESS.importlib, "import_module", import_ok)
    weights_sha256, artifact_sha256, files = HARNESS._validate_weight_identity(_QWEN, tmp_path)
    assert weights_sha256 == expected["weights_sha256"]
    assert artifact_sha256 == expected["artifact_identity_sha256"]
    assert files == [
        {
            "byte_count": 1,
            "kind": "weight",
            "path": "model.safetensors",
            "sha256": "a" * 64,
        }
    ]

    class DriftedIdentityModule:
        @staticmethod
        def identify_hf_safetensors_artifact(**kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(
                weights_sha256="0" * 64,
                verifier_receipt_sha256=expected["artifact_identity_sha256"],
            )

    def import_drift(name: str) -> object:
        if name == "medscale.mesc._training_hf_safetensors_identity_v1":
            return DriftedIdentityModule
        return original_import(name)

    monkeypatch.setattr(HARNESS.importlib, "import_module", import_drift)
    with pytest.raises(HARNESS.HarnessError, match="weights_sha256 drifted"):
        HARNESS._validate_weight_identity(_QWEN, tmp_path)


def test_mrl0801_weight_allowlists_are_exact_and_frozen() -> None:
    qwen = HARNESS._mrl0801_weight_allowlist(ROOT, _QWEN)
    gemma = HARNESS._mrl0801_weight_allowlist(ROOT, _GEMMA)
    assert qwen[0] == "model.safetensors.index.json"
    assert len(qwen) == 19
    assert qwen[-1] == "model-00018-of-00018.safetensors"
    assert gemma == (
        "model.safetensors.index.json",
        "model-00001-of-00002.safetensors",
        "model-00002-of-00002.safetensors",
    )


def test_remote_capacity_preflight_is_bounded_and_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    weight_files = (
        "model.safetensors.index.json",
        "model-00001-of-00001.safetensors",
    )
    monkeypatch.setattr(
        HARNESS,
        "_mrl0801_weight_allowlist",
        lambda root, candidate: weight_files,
    )

    class Hub:
        @staticmethod
        def model_info(model_id: str, *, revision: str, files_metadata: bool) -> object:
            assert model_id == _QWEN
            assert revision == HARNESS.EXPECTED_CANDIDATES[_QWEN]["revision"]
            assert files_metadata is True
            return SimpleNamespace(
                siblings=[
                    SimpleNamespace(rfilename="model.safetensors.index.json", size=100),
                    SimpleNamespace(rfilename="model-00001-of-00001.safetensors", size=1_000),
                    SimpleNamespace(rfilename="config.json", size=20),
                    SimpleNamespace(rfilename="tokenizer_config.json", size=30),
                    SimpleNamespace(rfilename="processor_config.json", size=40),
                    SimpleNamespace(rfilename="README.md", size=999_999),
                ]
            )

    monkeypatch.setattr(
        HARNESS.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=100 * 1024 * 1024 * 1024),
    )
    selected, total, free_before = HARNESS._remote_capacity_preflight(
        hub=Hub(),
        root=ROOT,
        candidate=_QWEN,
        destination_parent=tmp_path,
    )
    assert "README.md" not in selected
    assert set(weight_files) <= set(selected)
    assert {"config.json", "tokenizer_config.json", "processor_config.json"} <= set(selected)
    assert total == 1_190
    assert free_before == 100 * 1024 * 1024 * 1024

    monkeypatch.setattr(
        HARNESS.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=1),
    )
    with pytest.raises(HARNESS.HarnessError, match="insufficient free storage"):
        HARNESS._remote_capacity_preflight(
            hub=Hub(),
            root=ROOT,
            candidate=_QWEN,
            destination_parent=tmp_path,
        )


def _install_synthetic_stage_identities(monkeypatch: pytest.MonkeyPatch) -> None:
    from medscale.mesc import _mrl_0809_runtime_feasibility_v1 as validator
    from medscale.mesc._training_hf_safetensors_identity_v1 import (
        HfArtifactFileIdentity,
        HfSafeTensorsArtifactIdentity,
    )

    file_identity = HfArtifactFileIdentity(
        path="model.safetensors",
        kind="weight",
        sha256="a" * 64,
        byte_count=1,
    )
    for model_id in (_QWEN, _GEMMA):
        current = dict(HARNESS.EXPECTED_CANDIDATES[model_id])
        identity = HfSafeTensorsArtifactIdentity(
            model_id=model_id,
            revision=current["revision"],
            layout="single",
            files=(file_identity,),
        )
        current["weights_sha256"] = identity.weights_sha256
        current["artifact_identity_sha256"] = identity.verifier_receipt_sha256
        monkeypatch.setitem(HARNESS.EXPECTED_CANDIDATES, model_id, current)

        validator_current = dict(validator._EXPECTED_CANDIDATES[model_id])
        validator_current["weights_sha256"] = identity.weights_sha256
        validator_current["artifact_identity_sha256"] = identity.verifier_receipt_sha256
        monkeypatch.setitem(validator._EXPECTED_CANDIDATES, model_id, validator_current)


def test_stage_receipt_envelope_rederives_weight_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_synthetic_stage_identities(monkeypatch)
    receipt = _stage_receipt(_QWEN)
    assert HARNESS._validate_stage_receipt_envelope(receipt) == _QWEN

    payload = receipt["payload_manifest"]
    assert isinstance(payload, list)
    weight_payload = next(row for row in payload if row["path"] == "model.safetensors")
    weight_payload["sha256"] = "b" * 64
    weight_files = receipt["weight_files"]
    assert isinstance(weight_files, list)
    weight_files[0]["sha256"] = "b" * 64
    with pytest.raises(HARNESS.HarnessError, match="does not derive weights_sha256"):
        HARNESS._validate_stage_receipt_envelope(receipt)


def test_observation_rejects_non_object_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "observation.json"
    document = _observation(
        model_id=_QWEN,
        repository_sha="1" * 40,
        repository_tree="2" * 40,
        manifest_sha="a" * 64,
        lock_sha="b" * 64,
    )
    document["candidate"] = []
    path.write_bytes(HARNESS.canonical_json_bytes(document))
    with pytest.raises(HARNESS.HarnessError, match="candidate must be an object"):
        HARNESS._validated_observation(path)

    document = _observation(
        model_id=_QWEN,
        repository_sha="1" * 40,
        repository_tree="2" * 40,
        manifest_sha="a" * 64,
        lock_sha="b" * 64,
    )
    document["generation_evidence"] = []
    path.write_bytes(HARNESS.canonical_json_bytes(document))
    with pytest.raises(HARNESS.HarnessError, match="generation evidence must be an object"):
        HARNESS._validated_observation(path)


def test_independent_verifier_binds_stage_receipts_and_exact_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_synthetic_stage_identities(monkeypatch)
    root = tmp_path / "repo"
    (root / HARNESS.STATIC_MANIFEST.parent).mkdir(parents=True)
    (root / HARNESS.STATIC_MANIFEST).write_bytes(b"manifest-fixture\n")
    (root / HARNESS.LOCKFILE).write_bytes(b"lock-fixture\n")
    harness_path = root / HARNESS.HARNESS
    harness_path.parent.mkdir(parents=True, exist_ok=True)
    harness_path.write_bytes(SCRIPT.read_bytes())
    evidence = tmp_path / "custody"
    evidence.mkdir()
    repository_sha = "1" * 40
    repository_tree = "2" * 40
    manifest_sha = HARNESS.sha256_file(root / HARNESS.STATIC_MANIFEST)
    lock_sha = HARNESS.sha256_file(root / HARNESS.LOCKFILE)
    harness_sha = HARNESS.sha256_file(harness_path)
    monkeypatch.setattr(
        HARNESS,
        "_require_repository",
        lambda value: (repository_sha, repository_tree),
    )

    stage_paths: list[Path] = []
    observations: list[Path] = []
    for index, model_id in enumerate((_QWEN, _GEMMA)):
        stage_path = evidence / f"stage-{index}.json"
        stage_raw = HARNESS.canonical_json_bytes(_stage_receipt(model_id))
        stage_path.write_bytes(stage_raw)
        stage_paths.append(stage_path)
        observation_path = evidence / f"candidate-{index}.json"
        observation_path.write_bytes(
            HARNESS.canonical_json_bytes(
                _observation(
                    model_id=model_id,
                    repository_sha=repository_sha,
                    repository_tree=repository_tree,
                    manifest_sha=manifest_sha,
                    lock_sha=lock_sha,
                    harness_sha256=harness_sha,
                    stage_receipt_sha256=_sha(stage_raw),
                )
            )
        )
        observations.append(observation_path)

    receipt_path = evidence / "runtime-feasibility.json"
    HARNESS.assemble_receipt(root, observations, receipt_path)
    verification_path = evidence / "independent-verification.json"
    HARNESS.verify_receipt(root, receipt_path, stage_paths, verification_path)
    verification = HARNESS.parse_canonical_object(
        verification_path.read_bytes(), label="independent verification"
    )
    assert verification["schema_version"] == HARNESS.SCHEMA_VERIFY
    assert verification["disposition"] == "PASS"
    assert verification["harness_sha256"] == harness_sha
    assert verification["runtime_feasibility_receipt_sha256"] == _sha(receipt_path.read_bytes())
    assert verification["stage_receipts"] == [
        {"model_id": _QWEN, "sha256": _sha(stage_paths[0].read_bytes())},
        {"model_id": _GEMMA, "sha256": _sha(stage_paths[1].read_bytes())},
    ]

    tampered = HARNESS.parse_canonical_object(stage_paths[0].read_bytes(), label="stage receipt")
    tampered["remote_selected_bytes"] = 5
    tampered_path = evidence / "stage-tampered.json"
    tampered_path.write_bytes(HARNESS.canonical_json_bytes(tampered))
    with pytest.raises(
        HARNESS.HarnessError,
        match=r"staging payload byte count|payload size/count|digest does not match",
    ):
        HARNESS.verify_receipt(
            root,
            receipt_path,
            [tampered_path, stage_paths[1]],
            evidence / "should-not-exist.json",
        )


def test_independent_verifier_rejects_harness_identity_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_synthetic_stage_identities(monkeypatch)
    root = tmp_path / "repo"
    (root / HARNESS.STATIC_MANIFEST.parent).mkdir(parents=True)
    (root / HARNESS.STATIC_MANIFEST).write_bytes(b"manifest-fixture\n")
    (root / HARNESS.LOCKFILE).write_bytes(b"lock-fixture\n")
    harness_path = root / HARNESS.HARNESS
    harness_path.parent.mkdir(parents=True, exist_ok=True)
    harness_path.write_bytes(SCRIPT.read_bytes())
    evidence = tmp_path / "custody"
    evidence.mkdir()
    repository_sha = "1" * 40
    repository_tree = "2" * 40
    manifest_sha = HARNESS.sha256_file(root / HARNESS.STATIC_MANIFEST)
    lock_sha = HARNESS.sha256_file(root / HARNESS.LOCKFILE)
    monkeypatch.setattr(
        HARNESS,
        "_require_repository",
        lambda value: (repository_sha, repository_tree),
    )

    stage_paths: list[Path] = []
    observations: list[Path] = []
    for index, model_id in enumerate((_QWEN, _GEMMA)):
        stage_path = evidence / f"stage-{index}.json"
        stage_raw = HARNESS.canonical_json_bytes(_stage_receipt(model_id))
        stage_path.write_bytes(stage_raw)
        stage_paths.append(stage_path)
        observation_path = evidence / f"candidate-{index}.json"
        observation_path.write_bytes(
            HARNESS.canonical_json_bytes(
                _observation(
                    model_id=model_id,
                    repository_sha=repository_sha,
                    repository_tree=repository_tree,
                    manifest_sha=manifest_sha,
                    lock_sha=lock_sha,
                    harness_sha256="0" * 64,
                    stage_receipt_sha256=_sha(stage_raw),
                )
            )
        )
        observations.append(observation_path)

    receipt_path = evidence / "runtime-feasibility.json"
    HARNESS.assemble_receipt(root, observations, receipt_path)
    with pytest.raises(HARNESS.HarnessError, match="exact canonical harness bytes"):
        HARNESS.verify_receipt(
            root,
            receipt_path,
            stage_paths,
            evidence / "should-not-exist.json",
        )
