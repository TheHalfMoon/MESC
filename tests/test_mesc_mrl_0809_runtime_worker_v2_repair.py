from __future__ import annotations

import contextlib
import importlib.util
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/mesc_mrl_0809_runtime_worker_v2_repair.py"
_QWEN = "Qwen/Qwen3-8B"
_PROMPT_IDS = [
    151644,
    872,
    198,
    7985,
    825,
    2805,
    11652,
    911,
    264,
    6303,
    21495,
    13,
    151645,
    198,
    151644,
    77091,
    198,
]


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_runtime_worker_v2_repair_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


WORKER = _load()


class _Device:
    def __init__(self, device_type: str, index: int | None) -> None:
        self.type = device_type
        self.index = index


class _Parameter:
    def __init__(self, device_type: str = "cuda", index: int | None = 0) -> None:
        self.device = _Device(device_type, index)


class _Sequence(list[int]):
    def __getitem__(self, index: Any) -> Any:
        value = super().__getitem__(index)
        return _Sequence(value) if isinstance(index, slice) else value

    def tolist(self) -> list[int]:
        return list(self)


class _Step:
    def all(self) -> bool:
        return True


class _FakeTorch(SimpleNamespace):
    def __init__(self) -> None:
        self.float16 = "float16"
        self.cuda = SimpleNamespace(
            is_available=lambda: True,
            device_count=lambda: 1,
            memory_allocated=lambda: 0,
            reset_peak_memory_stats=lambda: None,
            synchronize=lambda: None,
            max_memory_allocated=lambda: 7 * 1024**3,
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

    def isfinite(self, step: _Step) -> _Step:
        return step


def _transformers(*, parameter_device: str = "cuda") -> SimpleNamespace:
    architecture = WORKER.EXPECTED_CANDIDATES[_QWEN]["architecture"]

    class Tokenizer:
        def apply_chat_template(self, messages: object, **kwargs: object) -> list[int]:
            del messages, kwargs
            return list(_PROMPT_IDS)

        def decode(self, ids: list[int], skip_special_tokens: bool) -> str:
            del ids, skip_special_tokens
            return "A blue triangle."

    def generate(self: object, **kwargs: object) -> SimpleNamespace:
        del self, kwargs
        return SimpleNamespace(
            sequences=[_Sequence([*_PROMPT_IDS, 11, 12])],
            logits=(_Step(), _Step()),
        )

    def named_parameters(self: object, recurse: bool = True) -> list[tuple[str, object]]:
        del self
        assert recurse is True
        index = 0 if parameter_device == "cuda" else None
        return [("weight", _Parameter(parameter_device, index))]

    def named_buffers(self: object, recurse: bool = True) -> list[tuple[str, object]]:
        del self
        assert recurse is True
        return [("buffer", _Parameter("cuda", 0))]

    model_class = type(
        str(architecture),
        (),
        {
            "training": False,
            "generate": generate,
            "named_parameters": named_parameters,
            "named_buffers": named_buffers,
        },
    )

    namespace = SimpleNamespace(
        AutoTokenizer=SimpleNamespace(from_pretrained=lambda path, **kwargs: Tokenizer()),
        AutoProcessor=SimpleNamespace(from_pretrained=lambda path, **kwargs: object()),
        BitsAndBytesConfig=lambda **kwargs: kwargs,
    )
    setattr(
        namespace,
        str(architecture),
        SimpleNamespace(from_pretrained=lambda path, **kwargs: model_class()),
    )
    return namespace


def _run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
    *,
    parameter_device: str = "cuda",
) -> dict[str, object]:
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    expected = WORKER.EXPECTED_CANDIDATES[_QWEN]
    monkeypatch.setattr(
        WORKER,
        "_metadata_digests",
        lambda candidate, path: {
            "config_sha256": expected["config_sha256"],
            "processor_config_sha256": expected["processor_config_sha256"],
            "tokenizer_config_sha256": expected["tokenizer_config_sha256"],
        },
    )
    monkeypatch.setattr(WORKER, "_package_versions", lambda: dict(WORKER.EXPECTED_PACKAGES))
    modules = {
        "resource": SimpleNamespace(
            RUSAGE_SELF=0,
            getrusage=lambda who: SimpleNamespace(ru_maxrss=4 * 1024 * 1024),
        ),
        "torch": _FakeTorch(),
        "transformers": _transformers(parameter_device=parameter_device),
    }
    monkeypatch.setattr(WORKER.importlib, "import_module", lambda name: modules[name])
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    monkeypatch.setenv("TRANSFORMERS_OFFLINE", "1")
    WORKER.run_worker(_QWEN, snapshot)
    return json.loads(capsysbinary.readouterr().out)


def test_worker_passes_without_hf_device_map_when_actual_tensors_are_cuda0(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    result = _run(tmp_path, monkeypatch, capsysbinary)
    assert result["schema_version"] == WORKER.SCHEMA_WORKER
    candidate = result["candidate"]
    assert candidate["all_modules_on_cuda_device_0"] is True
    assert candidate["load_completed"] is True
    assert candidate["synthetic_generation_completed"] is True


def test_worker_rejects_actual_cpu_parameter_even_without_hf_device_map(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    with pytest.raises(WORKER.RuntimeWorkerError, match="placement audit failed"):
        _run(
            tmp_path,
            monkeypatch,
            capsysbinary,
            parameter_device="cpu",
        )
