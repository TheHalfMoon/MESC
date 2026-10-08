"""Adversarial coverage for the MRL-0809 successor (v2) runtime-feasibility harness."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes as repository_canonical_json
from medscale.mesc._mrl_0809_runtime_feasibility_v2 import (
    MRL0809SuccessorRuntimeFeasibilityError,
    validate_successor_runtime_feasibility_receipt,
)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mesc_mrl_0809_runtime_feasibility_v2.py"
V1_SCRIPT = ROOT / "scripts/mesc_mrl_0809_runtime_feasibility.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_runtime_feasibility_v2_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HARNESS = _load()


def _load_v1() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mesc_mrl_0809_v1_reference", V1_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_QWEN = "Qwen/Qwen3-8B"
_GEMMA = "google/gemma-4-12B-it"
_GIB = 1024**3
_PROMPT_IDS = {
    _QWEN: [
        151644, 872, 198, 7985, 825, 2805, 11652, 911, 264, 6303, 21495, 13, 151645, 198,
        151644, 77091, 198,
    ],
    _GEMMA: [
        2, 105, 2364, 107, 6974, 886, 2822, 13315, 1003, 496, 3730, 17852, 236761, 106, 107,
        105, 4368, 107, 100, 45518, 107, 101,
    ],
}  # fmt: skip


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _roster_row(model_id: str) -> dict[str, Any]:
    roster = json.loads((ROOT / HARNESS.ROSTER).read_bytes())
    (row,) = [item for item in roster["active_candidates"] if item["candidate_id"] == model_id]
    assert isinstance(row, dict)
    return row


# --- static contract -------------------------------------------------------------------------


def test_harness_canonical_json_matches_repository_contract() -> None:
    value = {"b": [None, True, 7, "text"], "a": {"z": 1, "y": "é"}}
    assert HARNESS.canonical_json_bytes(value) == repository_canonical_json(value)


def test_v2_harness_is_separate_from_the_preserved_v1_harness() -> None:
    record = json.loads(
        (ROOT / "specs/mesc-experiment-0/mrl-0809-v1-infeasibility-record.json").read_bytes()
    )
    preserved = record["v1_contract_preserved_at_successor_base"]["runtime_feasibility_harness"]
    assert preserved["path"] == V1_SCRIPT.relative_to(ROOT).as_posix()
    assert _sha(V1_SCRIPT.read_bytes()) == preserved["sha256"]
    assert _sha(SCRIPT.read_bytes()) != preserved["sha256"]
    assert HARNESS.HARNESS.as_posix() == "scripts/mesc_mrl_0809_runtime_feasibility_v2.py"
    assert HARNESS.STATIC_MANIFEST.name == "mrl-0809-static-prerequisites-v2.json"
    assert {
        HARNESS.SCHEMA_STAGE,
        HARNESS.SCHEMA_WORKER,
        HARNESS.SCHEMA_OBSERVATION,
        HARNESS.SCHEMA_PROBE_START,
        HARNESS.SCHEMA_RECEIPT,
        HARNESS.SCHEMA_VERIFY,
        HARNESS.STAGING_POLICY_SCHEMA,
    } == {
        "MESC-MRL-0809-SUCCESSOR-STAGE-RECEIPT-V1",
        "MESC-MRL-0809-CANDIDATE-WORKER-V2",
        "MESC-MRL-0809-CANDIDATE-OBSERVATION-V2",
        "MESC-MRL-0809-SUCCESSOR-PROBE-START-V1",
        "MESC-MRL-0809-RUNTIME-MODEL-FEASIBILITY-V2",
        "MESC-MRL-0809-INDEPENDENT-RECEIPT-VERIFICATION-V2",
        "MESC-MRL-0809-SUCCESSOR-STAGING-POLICY-V1",
    }
    v1 = _load_v1()
    assert HARNESS.SCHEMA_RECEIPT != v1.SCHEMA_RECEIPT
    assert HARNESS.SCHEMA_VERIFY != v1.SCHEMA_VERIFY
    assert set(HARNESS.EXPECTED_CANDIDATES).isdisjoint(v1.EXPECTED_CANDIDATES)
    text = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("Qwen3.8-27B", "gemma-4-31B", "MRL0801_AUTH", 'device_map="auto"'):
        assert forbidden not in text


def test_roster_staging_bound_uses_the_largest_frozen_payload() -> None:
    assert HARNESS._required_roster_staging_free_bytes() == (
        max(HARNESS.EXPECTED_SELECTED_PAYLOAD_BYTES.values())
        + HARNESS.STAGING_CONTROL_RESERVE_BYTES
    )


def test_roster_allowlists_are_exact_and_bound(tmp_path: Path) -> None:
    for model_id in (_QWEN, _GEMMA):
        allowed = HARNESS._roster_weight_allowlist(ROOT, model_id)
        assert list(allowed) == _roster_row(model_id)["allowed_weight_files"]
    fake_root = tmp_path / "repo"
    (fake_root / HARNESS.ROSTER).parent.mkdir(parents=True)
    raw = (ROOT / HARNESS.ROSTER).read_bytes()
    (fake_root / HARNESS.ROSTER).write_bytes(raw.replace(b"model-00001", b"model-00009", 1))
    with pytest.raises(HARNESS.HarnessError, match="roster identity drifted"):
        HARNESS._roster_weight_allowlist(fake_root, _QWEN)


def test_metadata_digests_follow_the_frozen_processor_policy(tmp_path: Path) -> None:
    for name in ("config.json", "tokenizer_config.json"):
        (tmp_path / name).write_bytes(b"{}\n")
    digests = HARNESS._metadata_digests(_QWEN, tmp_path)
    assert digests["processor_config_sha256"] is None
    with pytest.raises(HARNESS.HarnessError, match=r"processor_config\.json"):
        HARNESS._metadata_digests(_GEMMA, tmp_path)
    (tmp_path / "processor_config.json").write_bytes(b"{}\n")
    assert HARNESS._metadata_digests(_GEMMA, tmp_path)["processor_config_sha256"] == _sha(b"{}\n")


# --- stage receipts ---------------------------------------------------------------------------


def _staging_policy(selected_bytes: int) -> dict[str, object]:
    roster_required = HARNESS._required_roster_staging_free_bytes()
    return {
        "control_reserve_bytes": HARNESS.STAGING_CONTROL_RESERVE_BYTES,
        "download_max_workers": HARNESS.STAGING_MAX_WORKERS,
        "global_cache_reuse": False,
        "observed_free_bytes_after": HARNESS.STAGING_CONTROL_RESERVE_BYTES + 1,
        "observed_free_bytes_before": roster_required + 1,
        "required_free_bytes_before": selected_bytes + HARNESS.STAGING_CONTROL_RESERVE_BYTES,
        "roster_preflight_candidates": sorted(HARNESS.EXPECTED_CANDIDATES),
        "roster_required_free_bytes_before": roster_required,
        "schema_version": HARNESS.STAGING_POLICY_SCHEMA,
        "selected_payload_bytes": selected_bytes,
        "xet_enabled": False,
    }


def _stage_receipt(model_id: str) -> dict[str, Any]:
    expected = HARNESS.EXPECTED_CANDIDATES[model_id]
    row = _roster_row(model_id)
    total = HARNESS.EXPECTED_SELECTED_PAYLOAD_BYTES[model_id]
    weights = {item["path"]: item for item in row["weight_files"]}
    metadata = [name for name in row["selected_payload_files"] if name not in weights]
    remaining = total - sum(item["byte_count"] for item in weights.values())
    payload: dict[str, dict[str, object]] = {
        name: {"byte_count": item["byte_count"], "path": name, "sha256": item["sha256"]}
        for name, item in weights.items()
    }
    for index, name in enumerate(metadata):
        size = remaining - (len(metadata) - 1) if index == 0 else 1
        payload[name] = {"byte_count": size, "path": name, "sha256": _sha(name.encode())}
    rows = [payload[name] for name in sorted(payload)]
    return {
        "artifact_identity_sha256": expected["artifact_identity_sha256"],
        "candidate_roster_sha256": HARNESS.CANDIDATE_ROSTER_SHA256,
        "config_sha256": expected["config_sha256"],
        "model_id": model_id,
        "payload_manifest": rows,
        "processor_config_sha256": expected["processor_config_sha256"],
        "remote_selected_bytes": total,
        "remote_selected_files": [item["path"] for item in rows],
        "revision": expected["revision"],
        "schema_version": HARNESS.SCHEMA_STAGE,
        "snapshot_file_count": len(rows),
        "snapshot_total_bytes": total,
        "staging_policy": _staging_policy(total),
        "tokenizer_config_sha256": expected["tokenizer_config_sha256"],
        "weight_files": row["weight_files"],
        "weights_sha256": expected["weights_sha256"],
    }


@pytest.mark.parametrize("model_id", [_QWEN, _GEMMA])
def test_stage_receipt_envelope_rederives_the_frozen_weight_identity(model_id: str) -> None:
    assert HARNESS._validate_stage_receipt_envelope(_stage_receipt(model_id)) == model_id


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("candidate_roster_sha256", "0" * 64),
        ("weights_sha256", "0" * 64),
        ("revision", "0" * 40),
        ("remote_selected_bytes", 1),
        ("processor_config_sha256", "0" * 64),
    ],
)
def test_stage_receipt_envelope_rejects_identity_drift(key: str, value: object) -> None:
    receipt = _stage_receipt(_QWEN)
    receipt[key] = value
    with pytest.raises(HARNESS.HarnessError):
        HARNESS._validate_stage_receipt_envelope(receipt)


def test_stage_receipt_envelope_rejects_a_forged_weight_shard() -> None:
    receipt = _stage_receipt(_GEMMA)
    receipt["weight_files"] = [dict(receipt["weight_files"][0], sha256="0" * 64)]
    with pytest.raises(HARNESS.HarnessError):
        HARNESS._validate_stage_receipt_envelope(receipt)


# --- assembly and independent verification -----------------------------------------------------


def _generation(model_id: str) -> dict[str, object]:
    return {
        "all_generated_logits_finite": True,
        "decoded_text_sha256": "d" * 64,
        "generated_token_ids": [11, 12],
        "prompt_construction": HARNESS.PROMPT_CONSTRUCTION,
        "prompt_token_ids_sha256": HARNESS.EXPECTED_CANDIDATES[model_id]["prompt_token_ids_sha256"],
        "synthetic_prompt_sha256": _sha(HARNESS.SYNTHETIC_PROMPT.encode("utf-8")),
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
    expected = HARNESS.EXPECTED_CANDIDATES[model_id]
    generation = _generation(model_id)
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
    candidate = {
        "all_modules_on_cuda_device_0": True,
        "architecture": expected["architecture"],
        "config_sha256": expected["config_sha256"],
        "load_completed": True,
        "model_id": model_id,
        "peak_cpu_memory_bytes": 4 * _GIB,
        "peak_gpu_memory_bytes": 8 * _GIB,
        "processor_config_sha256": expected["processor_config_sha256"],
        "processor_loaded": expected["processor_policy"] == HARNESS.AUTO_PROCESSOR,
        "processor_policy": expected["processor_policy"],
        "revision": expected["revision"],
        "runtime_representation": HARNESS.RUNTIME_REPRESENTATION,
        "synthetic_generation_completed": True,
        "synthetic_generation_sha256": _sha(HARNESS.canonical_json_bytes(generation)),
        "text_only_generation": True,
        "text_vocab_size": expected["text_vocab_size"],
        "tokenizer_config_sha256": expected["tokenizer_config_sha256"],
        "tokenizer_loaded": True,
        "unloaded_after_probe": True,
    }
    return {
        "candidate": candidate,
        "dependency_lock_sha256": lock_sha,
        "generation_evidence": generation,
        "provider_execution_id": execution_id,
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "runtime_identity": identity,
        "runtime_identity_sha256": identity_sha,
        "schema_version": HARNESS.SCHEMA_OBSERVATION,
        "stage_artifact_identity_sha256": expected["artifact_identity_sha256"],
        "stage_receipt_sha256": stage_receipt_sha256,
        "stage_weights_sha256": expected["weights_sha256"],
        "static_prerequisite_manifest_sha256": manifest_sha,
    }


def _fixture_repository(tmp_path: Path) -> tuple[Path, str, str]:
    root = tmp_path / "repo"
    (root / HARNESS.STATIC_MANIFEST).parent.mkdir(parents=True)
    (root / HARNESS.STATIC_MANIFEST).write_bytes(b"manifest-fixture\n")
    (root / HARNESS.LOCKFILE).write_bytes(b"lock-fixture\n")
    (root / HARNESS.HARNESS).parent.mkdir(parents=True)
    (root / HARNESS.HARNESS).write_bytes(SCRIPT.read_bytes())
    return (
        root,
        HARNESS.sha256_file(root / HARNESS.STATIC_MANIFEST),
        HARNESS.sha256_file(root / HARNESS.LOCKFILE),
    )


def _write_observations(
    evidence: Path, manifest_sha: str, lock_sha: str, **overrides: object
) -> list[Path]:
    paths: list[Path] = []
    for index, model_id in enumerate((_QWEN, _GEMMA)):
        document = _observation(
            model_id=model_id,
            repository_sha="1" * 40,
            repository_tree="2" * 40,
            manifest_sha=manifest_sha,
            lock_sha=lock_sha,
            **overrides,  # type: ignore[arg-type]
        )
        path = evidence / f"candidate-{index}.json"
        path.write_bytes(HARNESS.canonical_json_bytes(document))
        paths.append(path)
    return paths


def test_assembly_self_validates_with_the_v2_validator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest_sha, lock_sha = _fixture_repository(tmp_path)
    monkeypatch.setattr(HARNESS, "_require_repository", lambda value: ("1" * 40, "2" * 40))
    evidence = tmp_path / "custody"
    evidence.mkdir()
    output = evidence / "runtime-feasibility.json"
    HARNESS.assemble_receipt(root, _write_observations(evidence, manifest_sha, lock_sha), output)
    raw = output.read_bytes()
    validated = validate_successor_runtime_feasibility_receipt(
        raw,
        expected_static_prerequisite_manifest_sha256=manifest_sha,
        expected_dependency_lock_sha256=lock_sha,
        expected_repository_sha="1" * 40,
        expected_repository_tree="2" * 40,
    )
    assert validated.receipt_sha256 == _sha(raw)
    document = json.loads(raw)
    assert document["offload_performed"] is False
    assert document["v1_infeasibility_record_sha256"] == HARNESS.V1_INFEASIBILITY_RECORD_SHA256


def test_assembly_rejects_a_cross_session_candidate_mix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest_sha, lock_sha = _fixture_repository(tmp_path)
    monkeypatch.setattr(HARNESS, "_require_repository", lambda value: ("1" * 40, "2" * 40))
    evidence = tmp_path / "custody"
    evidence.mkdir()
    paths = _write_observations(evidence, manifest_sha, lock_sha)
    mixed = _observation(
        model_id=_GEMMA,
        repository_sha="1" * 40,
        repository_tree="2" * 40,
        manifest_sha=manifest_sha,
        lock_sha=lock_sha,
        execution_id="colab-other",
    )
    paths[1].write_bytes(HARNESS.canonical_json_bytes(mixed))
    with pytest.raises(HARNESS.HarnessError, match="provider_execution_id"):
        HARNESS.assemble_receipt(root, paths, evidence / "receipt.json")


def test_assembly_rejects_a_headroom_violation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest_sha, lock_sha = _fixture_repository(tmp_path)
    monkeypatch.setattr(HARNESS, "_require_repository", lambda value: ("1" * 40, "2" * 40))
    evidence = tmp_path / "custody"
    evidence.mkdir()
    paths = _write_observations(evidence, manifest_sha, lock_sha)
    document = json.loads(paths[0].read_bytes())
    document["candidate"]["peak_gpu_memory_bytes"] = 13 * _GIB
    paths[0].write_bytes(HARNESS.canonical_json_bytes(document))
    with pytest.raises(MRL0809SuccessorRuntimeFeasibilityError, match="headroom"):
        HARNESS.assemble_receipt(root, paths, evidence / "receipt.json")


def test_independent_verifier_binds_stage_receipts_and_the_exact_v2_harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, manifest_sha, lock_sha = _fixture_repository(tmp_path)
    monkeypatch.setattr(HARNESS, "_require_repository", lambda value: ("1" * 40, "2" * 40))
    evidence = tmp_path / "custody"
    evidence.mkdir()
    harness_sha = HARNESS.sha256_file(root / HARNESS.HARNESS)
    stages: list[Path] = []
    stage_digests: dict[str, str] = {}
    for model_id in (_QWEN, _GEMMA):
        raw = HARNESS.canonical_json_bytes(_stage_receipt(model_id))
        path = evidence / f"{model_id.replace('/', '__')}.stage.json"
        path.write_bytes(raw)
        stages.append(path)
        stage_digests[model_id] = _sha(raw)
    paths: list[Path] = []
    for index, model_id in enumerate((_QWEN, _GEMMA)):
        document = _observation(
            model_id=model_id,
            repository_sha="1" * 40,
            repository_tree="2" * 40,
            manifest_sha=manifest_sha,
            lock_sha=lock_sha,
            harness_sha256=harness_sha,
            stage_receipt_sha256=stage_digests[model_id],
        )
        path = evidence / f"candidate-{index}.json"
        path.write_bytes(HARNESS.canonical_json_bytes(document))
        paths.append(path)
    receipt = evidence / "runtime-feasibility.json"
    HARNESS.assemble_receipt(root, paths, receipt)
    verification = evidence / "verification.json"
    HARNESS.verify_receipt(root, receipt, stages, verification)
    document = json.loads(verification.read_bytes())
    assert document["schema_version"] == HARNESS.SCHEMA_VERIFY
    assert document["harness_sha256"] == harness_sha
    (root / HARNESS.HARNESS).write_bytes(SCRIPT.read_bytes() + b"\n")
    with pytest.raises(HARNESS.HarnessError, match="exact canonical harness"):
        HARNESS.verify_receipt(root, receipt, stages, evidence / "verification-2.json")


# --- probe start marker -------------------------------------------------------------------------


def test_probe_writes_the_attempt_start_marker_before_launching_the_worker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    (root / HARNESS.HARNESS).parent.mkdir(parents=True)
    (root / HARNESS.HARNESS).write_bytes(b"harness\n")
    evidence = tmp_path / "custody"
    evidence.mkdir()
    snapshot = evidence / "snapshot"
    snapshot.mkdir()
    observation = evidence / "qwen.observation.json"
    monkeypatch.setattr(
        HARNESS,
        "_require_colab_identity",
        lambda: ("colab-fixture", "release-fixture", "Tesla T4", "GPU-fixture", 1),
    )
    monkeypatch.setattr(HARNESS, "_require_repository", lambda value: ("1" * 40, "2" * 40))
    monkeypatch.setattr(HARNESS, "_read_stage_receipt", lambda *args, **kwargs: ({}, "c" * 64))
    monkeypatch.setattr(HARNESS.shutil, "which", lambda name: sys.executable)
    monkeypatch.setattr(HARNESS.subprocess, "check_output", lambda *a, **k: "bubblewrap 0.11.0")
    monkeypatch.setattr(HARNESS, "_require_cuda_sandbox_support", lambda: None)
    monkeypatch.setattr(HARNESS, "_python_layout", lambda value: (tmp_path, tmp_path, "3.11.15"))
    monkeypatch.setattr(HARNESS, "_package_versions", lambda: dict(HARNESS.EXPECTED_PACKAGES))
    monkeypatch.setattr(HARNESS, "_nvidia_nodes", lambda: ())
    monkeypatch.setattr(HARNESS, "_sandbox_prefix", lambda **kwargs: ["bwrap"])
    marker = observation.with_name(observation.name + ".probe-start.json")

    def worker(**kwargs: object) -> dict[str, object]:
        assert marker.is_file()
        raise HARNESS.HarnessError("isolated candidate probe failed: CUDA out of memory")

    monkeypatch.setattr(HARNESS, "_run_worker", worker)
    with pytest.raises(HARNESS.HarnessError, match="out of memory"):
        HARNESS.probe_candidate(
            root=root,
            candidate=_QWEN,
            snapshot=snapshot,
            stage_receipt=evidence / "qwen.stage.json",
            observation_out=observation,
            python_executable=Path(sys.executable),
        )
    document = json.loads(marker.read_bytes())
    assert document["schema_version"] == HARNESS.SCHEMA_PROBE_START
    assert document["candidate"] == _QWEN
    assert not observation.exists()


# --- isolated worker with a fake runtime ---------------------------------------------------------


class _Sequence(list[int]):
    def __getitem__(self, index: Any) -> Any:
        value = super().__getitem__(index)
        return _Sequence(value) if isinstance(index, slice) else value

    def tolist(self) -> list[int]:
        return list(self)


class _Step:
    def __init__(self, finite: bool) -> None:
        self.finite = finite


class _FakeTorch(SimpleNamespace):
    def __init__(self, *, peak: int, finite: bool) -> None:
        self.float16 = "float16"
        self._finite = finite
        self.cuda = SimpleNamespace(
            is_available=lambda: True,
            device_count=lambda: 1,
            memory_allocated=lambda: 0,
            reset_peak_memory_stats=lambda: None,
            synchronize=lambda: None,
            max_memory_allocated=lambda: peak,
            empty_cache=lambda: None,
        )

    def device(self, value: str) -> str:
        return value

    def tensor(self, rows: list[list[int]], device: str) -> list[list[int]]:
        return rows

    def ones_like(self, value: object) -> object:
        return value

    @contextlib.contextmanager
    def inference_mode(self) -> Iterator[None]:
        yield

    def isfinite(self, step: _Step) -> SimpleNamespace:
        return SimpleNamespace(all=lambda: step.finite)


def _fake_transformers(
    *,
    model_id: str,
    device_map: dict[str, object],
    prompt_ids: list[int],
    finite: bool,
    calls: list[str],
) -> SimpleNamespace:
    architecture = HARNESS.EXPECTED_CANDIDATES[model_id]["architecture"]

    class Tokenizer:
        def apply_chat_template(self, messages: object, **kwargs: object) -> list[int]:
            calls.append("chat_template")
            return prompt_ids

        def decode(self, ids: list[int], skip_special_tokens: bool) -> str:
            return "A blue triangle."

    def generate(self: object, **kwargs: object) -> SimpleNamespace:
        calls.append("generate")
        assert kwargs["do_sample"] is False and kwargs["num_beams"] == 1
        return SimpleNamespace(
            sequences=[_Sequence([*prompt_ids, 11, 12, 13])],
            logits=(_Step(True), _Step(finite), _Step(True)),
        )

    model_class = type(
        architecture,
        (),
        {"hf_device_map": device_map, "training": False, "generate": generate},
    )

    def load_model(path: str, **kwargs: object) -> object:
        calls.append("load_model")
        assert kwargs["device_map"] == {"": 0}
        assert kwargs["trust_remote_code"] is False
        return model_class()

    def load_processor(path: str, **kwargs: object) -> object:
        calls.append("processor")
        return object()

    namespace = SimpleNamespace(
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda path, **kwargs: Tokenizer()),
        AutoProcessor=SimpleNamespace(from_pretrained=load_processor),
        BitsAndBytesConfig=lambda **kwargs: kwargs,
    )
    setattr(namespace, architecture, SimpleNamespace(from_pretrained=load_model))
    return namespace


def _run_fake_worker(
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
    *,
    model_id: str,
    device_map: dict[str, object] | None = None,
    prompt_ids: list[int] | None = None,
    finite: bool = True,
    peak: int = 7 * _GIB,
) -> tuple[dict[str, Any], list[str]]:
    calls: list[str] = []
    fake_torch = _FakeTorch(peak=peak, finite=finite)
    fake_transformers = _fake_transformers(
        model_id=model_id,
        device_map=device_map if device_map is not None else {"": 0},
        prompt_ids=prompt_ids if prompt_ids is not None else _PROMPT_IDS[model_id],
        finite=finite,
        calls=calls,
    )
    modules = {
        "resource": SimpleNamespace(
            RUSAGE_SELF=0, getrusage=lambda who: SimpleNamespace(ru_maxrss=4 * 1024 * 1024)
        ),
        "torch": fake_torch,
        "transformers": fake_transformers,
    }
    monkeypatch.setattr(HARNESS.importlib, "import_module", lambda name: modules[name])
    expected = HARNESS.EXPECTED_CANDIDATES[model_id]
    digests = {
        "config_sha256": expected["config_sha256"],
        "processor_config_sha256": expected["processor_config_sha256"],
        "tokenizer_config_sha256": expected["tokenizer_config_sha256"],
    }
    monkeypatch.setattr(HARNESS, "_validate_snapshot", lambda candidate, snapshot: (digests, 1, 1))
    monkeypatch.setattr(HARNESS, "_package_versions", lambda: dict(HARNESS.EXPECTED_PACKAGES))
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    HARNESS._worker(model_id, Path("snapshot"))
    return json.loads(capsysbinary.readouterr().out), calls


@pytest.mark.parametrize("model_id", [_QWEN, _GEMMA])
def test_worker_emits_policy_exact_evidence(
    model_id: str,
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    worker, calls = _run_fake_worker(monkeypatch, capsysbinary, model_id=model_id)
    candidate = worker["candidate"]
    generation = worker["generation_evidence"]
    uses_processor = model_id == _GEMMA
    assert ("processor" in calls) is uses_processor
    assert candidate["processor_loaded"] is uses_processor
    assert candidate["all_modules_on_cuda_device_0"] is True
    assert generation["all_generated_logits_finite"] is True
    assert (
        generation["prompt_token_ids_sha256"]
        == (HARNESS.EXPECTED_CANDIDATES[model_id]["prompt_token_ids_sha256"])
    )
    assert generation["generated_token_ids"] == [11, 12, 13]
    assert candidate["synthetic_generation_sha256"] == _sha(
        HARNESS.canonical_json_bytes(generation)
    )
    assert calls.index("chat_template") < calls.index("load_model") < calls.index("generate")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"device_map": {"model.layers.0": "cpu"}}, "offload is prohibited"),
        ({"device_map": {"model.layers.0": "disk"}}, "offload is prohibited"),
        ({"finite": False}, "non-finite logits"),
        ({"peak": 12 * _GIB + 1}, "headroom ceiling"),
        ({"prompt_ids": [1, 2, 3]}, "prompt tokens drifted"),
    ],
)
def test_worker_fails_closed(
    overrides: dict[str, object],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    with pytest.raises(HARNESS.HarnessError, match=message):
        _run_fake_worker(monkeypatch, capsysbinary, model_id=_GEMMA, **overrides)  # type: ignore[arg-type]
