from __future__ import annotations

"""CW-006 real backend acceptance tests for offline local snapshot loading."""

import ast
import inspect
import sys
import types
from pathlib import Path
from uuid import UUID

import pytest
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"

sys.path.insert(0, str(WORKSPACE_SRC))

from medscale_workspace import asr as asr_mod
from medscale_workspace.asr import AsrStatus
from medscale_workspace.errors import AsrBackendError
from medscale_workspace.errors import AsrError
from medscale_workspace.errors import AsrInputError
from medscale_workspace.errors import AsrManifestError
from medscale_workspace.errors import AsrModelUnavailableError
from medscale_workspace.errors import AsrRevisionError

WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
SESSION_ONE = UUID("9c0d1e2f-3a4b-4c5d-8e6f-7a8b9c0d1e2f")
INPUT_ONE = UUID("1b2c3d4e-5f6a-7b8c-9d0e-1f2a3b4c5d6e")
T1 = "2026-09-22T10:00:00+03:00"
T2 = "2026-09-22T10:01:00+03:00"
INPUT_REVISION = "chunk-00000001"

def synthetic_audio(sequence: int) -> bytes:
    return f"synthetic-pcm-{sequence:08d}".encode("ascii")

def drifted_manifest(field: str, value: object):
    base = asr_mod.expected_manifest().to_document()
    base[field] = value
    return asr_mod.AsrManifest.from_document(base)

def test_no_top_level_heavy_imports() -> None:
    """Base shell must import without torch or transformers at top level."""
    path = WORKSPACE_SRC / "medscale_workspace" / "asr.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top_names: list = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_names.append(alias.name.split(".")[0])
        if isinstance(node, ast.ImportFrom):
            if node.module is not None:
                top_names.append(node.module.split(".")[0])
    assert "torch" not in top_names
    assert "transformers" not in top_names
    assert "numpy" not in top_names

def test_missing_optional_deps_fail_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing asr-local deps must raise a typed CW-006 error."""
    monkeypatch.setitem(sys.modules, "torch", None)
    monkeypatch.setitem(sys.modules, "transformers", None)
    with pytest.raises(AsrBackendError):
        asr_mod._require_asr_runtime()

def test_snapshot_path_required(tmp_path: Path) -> None:
    """A Hub model id must never satisfy the local snapshot path."""
    manifest = asr_mod.expected_manifest()
    with pytest.raises(AsrError):
        asr_mod.verify_local_snapshot(asr_mod.MODEL_ID, manifest)
    with pytest.raises(AsrError):
        asr_mod.verify_local_snapshot(tmp_path / "absent-dir", manifest)
    with pytest.raises(AsrError):
        asr_mod.TransformersWhisperBackend(asr_mod.MODEL_ID, manifest)

def test_mutable_snapshot_rejected(tmp_path: Path) -> None:
    """Mutable revisions must never trigger acquisition."""
    manifest = asr_mod.expected_manifest()
    for mutable in ("main", "latest"):
        with pytest.raises(AsrError):
            asr_mod.verify_local_snapshot(mutable, manifest)

def test_manifest_mismatch_blocks_loading(tmp_path: Path) -> None:
    """Drifted manifests must block loading before any model use."""
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    with pytest.raises(AsrRevisionError):
        asr_mod.verify_local_snapshot(snapshot, drifted_manifest("runtime_version", "4.44.0"))
    with pytest.raises(AsrRevisionError):
        asr_mod.verify_local_snapshot(snapshot, drifted_manifest("model_revision", "0" * 40))
    with pytest.raises(AsrManifestError):
        asr_mod.verify_local_snapshot(snapshot, drifted_manifest("model_id", "openai/whisper-large-v3"))
    with pytest.raises(AsrManifestError):
        asr_mod.verify_local_snapshot(snapshot, drifted_manifest("weight_sha256", "0" * 64))

def test_trust_remote_code_cannot_be_enabled() -> None:
    """Real backend APIs must not expose remote code switches."""
    init_params = inspect.signature(asr_mod.TransformersWhisperBackend.__init__).parameters
    assert "trust_remote_code" not in init_params
    assert "local_files_only" not in init_params
    assert "allow_download" not in init_params
    assert "model_id" not in init_params
    fn_params = inspect.signature(asr_mod.transcribe_with_transformers).parameters
    assert "trust_remote_code" not in fn_params
    assert "local_files_only" not in fn_params
    assert "allow_download" not in fn_params
    assert "model_id" not in fn_params
    path = WORKSPACE_SRC / "medscale_workspace" / "asr.py"
    text = path.read_text(encoding="utf-8")
    assert "local_files_only=True" in text
    assert "trust_remote_code=False" in text
    assert "trust_remote_code=True" not in text
    assert "local_files_only=False" not in text
    assert "allow_download=True" not in text

def test_no_network_fallback_in_source() -> None:
    """Protected path must contain no remote acquisition primitives."""
    path = WORKSPACE_SRC / "medscale_workspace" / "asr.py"
    text = path.read_text(encoding="utf-8")
    forbidden = ["hf_hub_download", "snapshot_download", "InferenceClient"]
    for token in forbidden:
        assert token not in text
    network_tokens = ["import requests", "import urllib", "import httpx"]
    for token in network_tokens:
        assert token not in text
    assert "http://" not in text
    assert "https://" not in text

class _FakeTensor:
    def to(self, device: object) -> object:
        return self

class _FakeProcessorInstance:
    def __call__(self, waveform: object, sampling_rate: int = 16000, return_tensors: str = "pt") -> dict:
        return {"input_features": _FakeTensor()}

    def batch_decode(self, generated: object, skip_special_tokens: bool = True) -> list:
        return ["hello world"]

class _FakeModelInstance:
    def to(self, device: object) -> object:
        return self

    def eval(self) -> None:
        return None

    def generate(self, features: object) -> list:
        return [[1, 2, 3]]

class _NoGrad:
    def __enter__(self) -> None:
        return None

    def __exit__(self, *args: object) -> bool:
        return False

def _install_fake_runtime(monkeypatch: pytest.MonkeyPatch, calls: list) -> None:
    """Install fake transformers and torch modules bound to exact versions."""
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.__version__ = asr_mod.RUNTIME_VERSION
    fake_torch = types.ModuleType("torch")
    fake_torch.__version__ = asr_mod.TORCH_VERSION
    fake_torch.float32 = "float32"
    fake_torch.no_grad = lambda: _NoGrad()
    class FakeProcessorClass:
        @staticmethod
        def from_pretrained(name: object, **kwargs: object) -> object:
            calls.append(("processor", str(name), dict(kwargs)))
            return _FakeProcessorInstance()

    class FakeModelClass:
        @staticmethod
        def from_pretrained(name: object, **kwargs: object) -> object:
            calls.append(("model", str(name), dict(kwargs)))
            return _FakeModelInstance()
    fake_transformers.WhisperProcessor = FakeProcessorClass
    fake_transformers.WhisperForConditionalGeneration = FakeModelClass
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

def _make_snapshot_dir(path: Path) -> Path:
    """Create required snapshot member files with placeholder bytes."""
    path.mkdir(parents=True, exist_ok=True)
    for name in asr_mod.SNAPSHOT_REQUIRED_FILES:
        (path / name).write_bytes(b"placeholder")
    return path

def test_loader_calls_are_local_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Every loader call must use the local path with fail-closed flags."""
    calls: list = []
    _install_fake_runtime(monkeypatch, calls)
    snapshot = _make_snapshot_dir(tmp_path / "snapshot")
    manifest = asr_mod.expected_manifest()
    monkeypatch.setattr(asr_mod, "_verify_snapshot_weight", lambda path, manifest: path)
    monkeypatch.setattr(asr_mod, "_verify_git_blob", lambda path, expected, label: expected)
    backend = asr_mod.TransformersWhisperBackend(snapshot, manifest)
    assert len(calls) == 2
    for kind, name, kwargs in calls:
        assert name == str(snapshot)
        assert name != asr_mod.MODEL_ID
        assert kwargs.get("local_files_only") is True
        assert kwargs.get("trust_remote_code") is False
        assert "model_id" not in kwargs
    assert isinstance(backend, asr_mod.TransformersWhisperBackend)

def test_real_backend_output_passes_same_validation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Fake real backend output must survive the shared validation boundary."""
    calls: list = []
    _install_fake_runtime(monkeypatch, calls)
    snapshot = _make_snapshot_dir(tmp_path / "snapshot")
    manifest = asr_mod.expected_manifest()
    monkeypatch.setattr(asr_mod, "_verify_snapshot_weight", lambda path, manifest: path)
    monkeypatch.setattr(asr_mod, "_verify_git_blob", lambda path, expected, label: expected)
    backend = asr_mod.TransformersWhisperBackend(snapshot, manifest)
    result = asr_mod.transcribe_with_backend(
        WORKSPACE_ALPHA,
        SESSION_ONE,
        INPUT_ONE,
        INPUT_REVISION,
        synthetic_audio(7),
        "en",
        T1,
        T2,
        manifest,
        True,
        asr_mod.MODEL_REVISION,
        False,
        True,
        False,
        backend,
    )
    assert result.status is AsrStatus.SUCCESS
    assert result.transcript == "hello world"
    assert len(result.segments) == 1
    assert result.segments[0].text == "hello world"
    assert result.model_id == asr_mod.MODEL_ID
    assert result.model_revision == asr_mod.MODEL_REVISION
    assert result.runtime_name == asr_mod.RUNTIME_NAME
    assert result.runtime_version == asr_mod.RUNTIME_VERSION

def test_real_path_rejects_malformed_backend_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Shared boundary must reject bad output even on the real path."""
    calls: list = []
    _install_fake_runtime(monkeypatch, calls)
    snapshot = _make_snapshot_dir(tmp_path / "snapshot")
    manifest = asr_mod.expected_manifest()
    monkeypatch.setattr(asr_mod, "_verify_snapshot_weight", lambda path, manifest: path)
    monkeypatch.setattr(asr_mod, "_verify_git_blob", lambda path, expected, label: expected)
    backend = asr_mod.TransformersWhisperBackend(snapshot, manifest)
    def bad_backend(audio_bytes: bytes, manifest: object, requested: str) -> tuple:
        return ("success", "", (), "en", "")

    with pytest.raises(AsrError):
        asr_mod.transcribe_with_backend(
            WORKSPACE_ALPHA,
            SESSION_ONE,
            INPUT_ONE,
            INPUT_REVISION,
            synthetic_audio(3),
            "en",
            T1,
            T2,
            manifest,
            True,
            asr_mod.MODEL_REVISION,
            False,
            True,
            False,
            bad_backend,
        )

def test_adapter_contract_version_bound() -> None:
    """Adapter contract version must equal the governed producer version."""
    assert asr_mod.adapter_contract_version() == "cw006-v1"
    assert asr_mod.adapter_contract_version() == asr_mod.PRODUCER_VERSION
