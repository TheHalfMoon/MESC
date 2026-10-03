from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/mesc_mrl_0809_runtime_worker_v2_bmm_repair.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_runtime_worker_v2_bmm_repair_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


WORKER = _load()


def test_bmm_override_is_disabled_with_exact_op_symbol(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    registry = SimpleNamespace(deregister_op_overrides=lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(WORKER.importlib, "import_module", lambda name: registry)

    WORKER._disable_experimental_native_bmm_override()

    assert calls == [{"disable_op_symbols": "bmm"}]


def test_bmm_override_disable_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    registry = SimpleNamespace(deregister_op_overrides=None)
    monkeypatch.setattr(WORKER.importlib, "import_module", lambda name: registry)

    with pytest.raises(WORKER.RuntimeWorkerError, match="failed to disable"):
        WORKER._disable_experimental_native_bmm_override()
