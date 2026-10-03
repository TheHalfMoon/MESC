from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/mesc_mrl_0809_bmm_portability_preflight_v1.py"
)


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "mesc_mrl_0809_bmm_portability_preflight_v1_test", SCRIPT
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PREFLIGHT = _load()


def test_preflight_disables_bmm_before_cuda_smoke(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    events: list[str] = []
    registry = SimpleNamespace(
        deregister_op_overrides=lambda **kwargs: events.append(
            f"disable:{kwargs['disable_op_symbols']}"
        )
    )
    torch = SimpleNamespace(
        float32="float32",
        cuda=SimpleNamespace(
            is_available=lambda: True,
            device_count=lambda: 1,
            synchronize=lambda: events.append("sync"),
        ),
        device=lambda value: value,
        ones=lambda shape, **kwargs: (shape, kwargs),
        bmm=lambda left, right: events.append("bmm") or "result",
        equal=lambda result, expected: result == "result",
    )
    monkeypatch.setattr(PREFLIGHT.importlib.metadata, "version", lambda name: "2.13.0")
    monkeypatch.setattr(
        PREFLIGHT.importlib,
        "import_module",
        lambda name: registry if name == "torch._native.registry" else torch,
    )

    PREFLIGHT.main()

    assert events[0] == "disable:bmm"
    assert "bmm" in events
    document = json.loads(capsys.readouterr().out)
    assert document["bmm_result_verified"] is True
    assert document["disabled_op_symbols"] == ["bmm"]


def test_preflight_rejects_torch_version_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(PREFLIGHT.importlib.metadata, "version", lambda name: "2.13.1")
    with pytest.raises(PREFLIGHT.BMMPortabilityError, match="torch package identity drifted"):
        PREFLIGHT.main()
