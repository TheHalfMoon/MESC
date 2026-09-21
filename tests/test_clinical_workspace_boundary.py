"""CW-001 Clinical Workspace boundary and offline-shell acceptance tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_WORKSPACE_ROOT = _REPO_ROOT / "apps" / "workspace"
_WORKSPACE_SRC = _WORKSPACE_ROOT / "src"
_GUARD = _REPO_ROOT / "scripts" / "check_clinical_workspace_boundary.py"


def _run_guard(source: Path = _WORKSPACE_SRC) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_GUARD), "--source", str(source)],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def _run_workspace_snapshot_offline() -> subprocess.CompletedProcess[str]:
    code = f"""
import json
import socket
import sys
import urllib.request

def blocked(*args, **kwargs):
    raise AssertionError("network access attempted")

socket.socket = blocked
socket.create_connection = blocked
urllib.request.urlopen = blocked
sys.path.insert(0, {str(_WORKSPACE_SRC)!r})

from medscale_workspace.app import workspace_snapshot
print(json.dumps(workspace_snapshot(), sort_keys=True, separators=(",", ":")))
"""
    env = os.environ.copy()
    for key in tuple(env):
        if "proxy" in key.lower() or key.startswith("HF_"):
            env.pop(key, None)
    env["PYTHONNOUSERSITE"] = "1"
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def _run_workspace_cli_offline() -> subprocess.CompletedProcess[str]:
    code = f"""
import runpy
import socket
import sys
import urllib.request

def blocked(*args, **kwargs):
    raise AssertionError("network access attempted")

socket.socket = blocked
socket.create_connection = blocked
urllib.request.urlopen = blocked
sys.path.insert(0, {str(_WORKSPACE_SRC)!r})

runpy.run_module("medscale_workspace", run_name="__main__")
"""
    env = os.environ.copy()
    for key in tuple(env):
        if "proxy" in key.lower() or key.startswith("HF_"):
            env.pop(key, None)
    env["PYTHONNOUSERSITE"] = "1"
    return subprocess.run(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_root_research_package_remains_workspace_independent() -> None:
    config = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == ["src/medscale"]
    assert config["project"]["dependencies"] == []


def test_workspace_package_is_zero_dependency_and_separate() -> None:
    config = tomllib.loads((_WORKSPACE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["project"]["name"] == "medscale-workspace"
    assert config["project"]["dependencies"] == []
    assert config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "src/medscale_workspace"
    ]


def test_workspace_boundary_guard_passes_current_source() -> None:
    result = _run_guard()
    assert result.returncode == 0, result.stderr
    assert "CW-001 workspace boundary PASS" in result.stdout


def test_workspace_boundary_guard_rejects_research_import(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("from medscale import Corpus\n", encoding="utf-8")
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "Research Core import is forbidden" in result.stderr


def test_workspace_boundary_guard_rejects_network_import(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("import socket\n", encoding="utf-8")
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "network-capable import is forbidden" in result.stderr


def test_workspace_boundary_guard_rejects_boundary_escape_import(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("import subprocess\n", encoding="utf-8")
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "boundary escape import is forbidden" in result.stderr


def test_workspace_boundary_guard_rejects_nonallowlisted_stdlib(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("import pathlib\n", encoding="utf-8")
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "stdlib import is not allowlisted" in result.stderr


def test_workspace_boundary_guard_rejects_dynamic_import(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("__import__('medscale')\n", encoding="utf-8")
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "dynamic import/code/file primitive is forbidden" in result.stderr


def test_workspace_boundary_guard_rejects_import_alias(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "loader = __import__\nloader('socket')\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "dynamic import/code/file primitive is forbidden" in result.stderr


def test_workspace_boundary_guard_rejects_eval_alias(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "runner = eval\nrunner('1 + 1')\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "dynamic import/code/file primitive is forbidden" in result.stderr


def test_workspace_boundary_guard_rejects_persistent_write(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "class Sink:\n    pass\nSink().write_text('y')\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "persistent filesystem mutation is forbidden" in result.stderr


def test_synthetic_encounter_rejects_cross_workspace_patient() -> None:
    code = f"""
import sys
from uuid import UUID

sys.path.insert(0, {str(_WORKSPACE_SRC)!r})

from medscale_workspace.fixtures import SyntheticPatient, synthetic_encounter
from medscale_workspace.identity import WorkspaceObjectType, synthetic_identity

foreign_identity = synthetic_identity(
    UUID("00000000-0000-0000-0000-000000000001"),
    WorkspaceObjectType.PATIENT,
    "foreign-patient",
)
patient = SyntheticPatient(identity=foreign_identity)
try:
    synthetic_encounter(patient)
except ValueError as exc:
    assert str(exc) == "patient must belong to the synthetic workspace"
else:
    raise AssertionError("cross-workspace patient was accepted")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_workspace_cli_emits_no_object_or_display_data() -> None:
    result = _run_workspace_cli_offline()
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)
    assert payload == {
        "application": "medscale-workspace",
        "data_class": "SYNTHETIC",
        "mode": "offline-shell",
        "ready": True,
    }
    lowered = result.stdout.lower()
    assert "patient" not in lowered
    assert "encounter" not in lowered
    assert "object_id" not in lowered
    assert "display_name" not in lowered


def test_workspace_shell_runs_offline_with_deterministic_synthetic_identity() -> None:
    first = _run_workspace_snapshot_offline()
    second = _run_workspace_snapshot_offline()
    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert first.stdout == second.stdout

    payload = json.loads(first.stdout)
    assert payload["data_class"] == "SYNTHETIC"
    assert payload["capabilities"] == {
        "network": False,
        "microphone": False,
        "ehr": False,
        "external_model": False,
        "persistent_write": False,
    }
    assert payload["encounter"]["patient_id"] == payload["patient"]["object_id"]
