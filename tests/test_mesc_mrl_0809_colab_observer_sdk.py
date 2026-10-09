"""Official CLI 0.7.4-shaped observer boundary tests; no provider calls."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts/mesc_mrl_0809_evidence_recovery_3_control_plane.py"
)
SPEC = importlib.util.spec_from_file_location("mesc_colab_observer_sdk_test", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
observer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(observer)

SESSION = "mesc-evidence-recovery-3"


def sdk(monkeypatch: pytest.MonkeyPatch, *, active: bool) -> SimpleNamespace:
    assignment = SimpleNamespace(
        endpoint="PRIVATE_ENDPOINT", accelerator="T4", variant="GPU", machine_shape="STANDARD"
    )
    entry = SimpleNamespace(
        name=SESSION,
        endpoint="PRIVATE_ENDPOINT",
        accelerator="T4",
        variant="GPU",
        machine_shape="STANDARD",
    )
    client = SimpleNamespace(
        get_consumption_user_info=lambda: SimpleNamespace(
            paid_compute_units_balance=0.0,
            consumption_rate_hourly=1.07 if active else 0.0,
            assignments_count=1 if active else 0,
        ),
        list_assignments=lambda: [assignment] if active else [],
    )
    state = SimpleNamespace(client=client, get_session=lambda name: entry if active else None)
    modules = {
        "colab_cli.client": SimpleNamespace(
            Accelerator=SimpleNamespace(T4="T4"),
            AssignmentVariant=SimpleNamespace(GPU="GPU"),
            Shape=SimpleNamespace(STANDARD="STANDARD"),
        ),
        # The official distribution has common.py with a State instance, not
        # a common/state.py package. A nonexistent import must fail this test.
        "colab_cli.common": SimpleNamespace(state=state),
    }

    def import_module(name: str) -> SimpleNamespace:
        if name not in modules:
            raise ModuleNotFoundError(name)
        return modules[name]

    monkeypatch.setattr(observer, "importlib", SimpleNamespace(import_module=import_module))
    return assignment


def test_official_sdk_module_shape_supports_before_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk(monkeypatch, active=False)
    document = observer.observe("BEFORE_ALLOCATION", SESSION)
    assert document["account_assignments"] == document["server_assignments"] == 0
    assert document["session"] is None


def test_official_listed_assignment_supports_independent_after_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sdk(monkeypatch, active=True)
    document = observer.observe("AFTER_ALLOCATION", SESSION)
    assert document["session"] == {
        "name": SESSION,
        "accelerator": "T4",
        "variant": "GPU",
        "machine_shape": "STANDARD",
    }
    assert document["nominal_rate_hourly"] == 1.07
    assert "PRIVATE_ENDPOINT" not in str(document)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("endpoint", "OTHER_PRIVATE_ENDPOINT"),
        ("accelerator", "A100"),
        ("variant", "TPU"),
        ("machine_shape", "HIGHMEM"),
    ],
)
def test_local_session_cannot_override_server_identity(
    monkeypatch: pytest.MonkeyPatch, field: str, value: str
) -> None:
    assignment = sdk(monkeypatch, active=True)
    setattr(assignment, field, value)
    with pytest.raises(ValueError, match="provider assignment does not match") as error:
        observer.observe("AFTER_ALLOCATION", SESSION)
    assert "PRIVATE_ENDPOINT" not in str(error.value)
