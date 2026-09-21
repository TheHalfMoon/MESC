"""Clinical Workspace boundary and offline-shell acceptance tests.

CW-001 introduced the boundary, the fail-closed guard and the synthetic offline
shell. CW-002 extends the guard (ADR-0039 decision 7, amendment A1.12) to admit
exactly the governed storage capability, so the messages and the package dependency
assertion below carry the CW-002 profile while every CW-001 prohibition stays
asserted unchanged.
"""

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


def test_workspace_package_declares_exactly_one_aead_dependency() -> None:
    config = tomllib.loads((_WORKSPACE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert config["project"]["name"] == "medscale-workspace"
    # CW-002 admits exactly one runtime dependency, for the AEAD primitive only.
    assert config["project"]["dependencies"] == ["cryptography==50.0.1"]
    assert config["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"] == [
        "src/medscale_workspace"
    ]


def test_workspace_boundary_guard_passes_current_source() -> None:
    result = _run_guard()
    assert result.returncode == 0, result.stderr
    assert "CW-002 workspace boundary PASS" in result.stdout


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


def test_workspace_boundary_guard_rejects_builtins_introspection(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        'getattr(__builtins__, "__import__")("socket")\n',
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "call shape cannot be verified fail-closed" in result.stderr
    assert (
        "forbidden capability reference is not allowed in the Clinical Workspace: __builtins__"
        in result.stderr
    )


def test_workspace_boundary_guard_rejects_capability_binding_forms(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        'for loader in [__import__]:\n    loader("socket")\n',
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "forbidden capability reference is not allowed in the Clinical Workspace: __import__"
        in result.stderr
    )


def test_workspace_boundary_guard_rejects_dictionary_indirection(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        'table = {}\nloader = table["__import__"]\nloader("socket")\n',
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "dynamic import/code/file primitive is forbidden" in result.stderr


def test_workspace_boundary_guard_rejects_reflective_capability_access(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("reader = globals()\n", encoding="utf-8")
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "reflective capability access is forbidden" in result.stderr


def test_workspace_boundary_guard_rejects_unverifiable_call_shape(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        'table = {"handler": print}\ntable["handler"]("x")\n',
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "call shape cannot be verified fail-closed" in result.stderr


def test_workspace_boundary_guard_rejects_object_graph_traversal(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "candidates = ().__class__.__base__.__subclasses__()\n"
        "runner = candidates[0]\n"
        'runner("id")\n',
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "object-graph capability attribute is forbidden in the Clinical Workspace: __class__"
        in result.stderr
    )
    assert (
        "object-graph capability attribute is forbidden in the Clinical Workspace: __subclasses__"
        in result.stderr
    )


def test_workspace_boundary_guard_rejects_dunder_capability_dictionary(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("print(object.__dict__['__subclasses__'])\n", encoding="utf-8")
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "object-graph capability attribute is forbidden in the Clinical Workspace: __dict__"
        in result.stderr
    )


def test_workspace_boundary_guard_rejects_frame_globals_escape(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "try:\n"
        '    raise ValueError("x")\n'
        "except ValueError as exc:\n"
        "    frames = exc.__traceback__.tb_frame.f_globals\n"
        '    caps = frames["__buil" + "tins__"]\n'
        '    loader = caps["__imp" + "ort__"]\n'
        '    loader("socket")\n',
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "object-graph capability attribute is forbidden in the Clinical Workspace: __traceback__"
        in result.stderr
    )
    assert (
        "object-graph capability attribute is forbidden in the Clinical Workspace: f_globals"
        in result.stderr
    )
    assert "dynamic import/code/file primitive is forbidden" in result.stderr


def test_workspace_boundary_guard_folds_concatenated_capability_keys(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        'table = {}\nloader = table["__imp" + "ort__"]\nloader("socket")\n',
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "dynamic import/code/file primitive is forbidden" in result.stderr


def test_workspace_boundary_guard_rejects_runtime_importing_builtin(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("help()\n", encoding="utf-8")
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "runtime code-importing builtin is forbidden in the Clinical Workspace: help"
        in result.stderr
    )


def test_workspace_boundary_guard_allows_ordinary_dunder_use(tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text(
        "__all__ = ['Thing']\n"
        "\n"
        "\n"
        "class Thing:\n"
        "    def __init__(self, name: str) -> None:\n"
        "        self.name = name\n"
        "\n"
        "\n"
        "def build() -> str:\n"
        "    return Thing('alpha').name\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    print(build())\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    # The CW-002 structural rules require the four admitted modules to exist, so a
    # lone benign module reports the missing structure and nothing else.
    assert "CW-002 requires storage.py" in result.stderr
    for forbidden in ("forbidden", "call shape cannot be verified", "not allowlisted"):
        assert forbidden not in result.stderr, result.stderr


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


def test_synthetic_encounter_rejects_non_patient_identity() -> None:
    code = f"""
import sys

sys.path.insert(0, {str(_WORKSPACE_SRC)!r})

from medscale_workspace.fixtures import (
    SYNTHETIC_WORKSPACE_ID,
    SyntheticPatient,
    synthetic_encounter,
)
from medscale_workspace.identity import WorkspaceObjectType, synthetic_identity

encounter_shaped = SyntheticPatient(
    identity=synthetic_identity(
        SYNTHETIC_WORKSPACE_ID,
        WorkspaceObjectType.ENCOUNTER,
        "encounter-shaped",
    )
)
try:
    synthetic_encounter(encounter_shaped)
except ValueError as exc:
    assert str(exc) == "patient identity must have object type PATIENT"
else:
    raise AssertionError("encounter-typed identity was accepted as a patient")
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_synthetic_encounter_identity_is_patient_specific() -> None:
    code = f"""
import sys

sys.path.insert(0, {str(_WORKSPACE_SRC)!r})

from medscale_workspace.fixtures import (
    SYNTHETIC_WORKSPACE_ID,
    SyntheticPatient,
    synthetic_encounter,
    synthetic_patient,
)
from medscale_workspace.identity import WorkspaceObjectType, synthetic_identity

canonical = synthetic_encounter()
assert canonical.identity.object_id == synthetic_encounter().identity.object_id
assert canonical.patient_id == synthetic_patient().identity.object_id

other_patient = SyntheticPatient(
    identity=synthetic_identity(
        SYNTHETIC_WORKSPACE_ID,
        WorkspaceObjectType.PATIENT,
        "patient-beta",
    )
)
other = synthetic_encounter(other_patient)
assert other.patient_id == other_patient.identity.object_id
assert other.identity.object_id != canonical.identity.object_id
assert other.identity.object_id == synthetic_encounter(other_patient).identity.object_id
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
        "persistent_write": True,
    }
    # CW-002 widens exactly one capability, and declares what replaced it.
    assert payload["storage"] == {
        "engine": "sqlite3",
        "payload_encryption": "AES-256-GCM",
        "key_derivation": "HKDF-SHA-256",
        "plaintext_fallback": False,
        "platform_key_provider": "unavailable-fail-closed",
    }
    assert payload["encounter"]["patient_id"] == payload["patient"]["object_id"]


# ---------------------------------------------------------------------------
# CW-002 capability-expansion rules (ADR-0039 decision 7, amendment A1.12)
# ---------------------------------------------------------------------------


def test_cw002_guard_admits_the_governed_capability_and_nothing_more(tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text(
        "import hashlib\nimport hmac\nimport secrets\nimport sqlite3\nimport uuid\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    # The guarded source set is scanned as a whole; a lone module is not a store, so
    # the structural rules report the missing CW-002 modules instead of passing.
    assert "CW-002 requires storage.py" in result.stderr
    assert "must import sqlite3" not in result.stderr
    assert "stdlib import is not allowlisted" not in result.stderr


def test_cw002_guard_rejects_an_unadmitted_stdlib_capability(tmp_path: Path) -> None:
    expected = {
        "import os": "boundary escape import is forbidden: os",
        "import pathlib": "stdlib import is not allowlisted: pathlib",
        "import socket": "network-capable import is forbidden: socket",
        "import subprocess": "boundary escape import is forbidden: subprocess",
    }
    for module, message in expected.items():
        (tmp_path / "bad.py").write_text(f"{module}\n", encoding="utf-8")
        result = _run_guard(tmp_path)
        assert result.returncode == 1, module
        assert message in result.stderr, module


def test_cw002_guard_rejects_an_unadmitted_third_party_module(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text("import paramiko\n", encoding="utf-8")
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "undeclared third-party import is forbidden: paramiko" in result.stderr


def test_cw002_guard_rejects_a_wider_cryptography_import(tmp_path: Path) -> None:
    (tmp_path / "bad.py").write_text(
        "from cryptography.hazmat.primitives import hashes\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "undeclared third-party import is forbidden: cryptography.hazmat.primitives"
        in result.stderr
    )


def test_cw002_guard_rejects_sqlite_outside_the_storage_module(tmp_path: Path) -> None:
    (tmp_path / "leak.py").write_text(
        "import sqlite3\n\n\nsqlite3.connect('elsewhere.sqlite3')\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "sqlite3 may be imported only by storage.py" in result.stderr
    assert "sqlite3.connect is admitted only in storage.py" in result.stderr


def test_cw002_guard_rejects_a_store_path_that_bypasses_the_resolver(tmp_path: Path) -> None:
    (tmp_path / "storage.py").write_text(
        "import sqlite3\n\n\ndef open_store(path: str) -> None:\n    sqlite3.connect(path)\n",
        encoding="utf-8",
    )
    (tmp_path / "store_path.py").write_text(
        "def resolve_workspace_store_path(root: str, workspace_id: str) -> str:\n"
        "    return root + workspace_id\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "sqlite3.connect must take its path from resolve_workspace_store_path" in result.stderr


def test_cw002_guard_requires_exactly_one_store_path_resolver(tmp_path: Path) -> None:
    (tmp_path / "storage.py").write_text("import sqlite3\n", encoding="utf-8")
    (tmp_path / "store_path.py").write_text(
        "def resolve_workspace_store_path(root: str, workspace_id: str) -> str:\n    return root\n",
        encoding="utf-8",
    )
    (tmp_path / "duplicate.py").write_text(
        "def resolve_workspace_store_path(root: str, workspace_id: str) -> str:\n    return root\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "must be defined exactly once in store_path.py" in result.stderr


def test_cw002_guard_rejects_the_reserved_password_kdf(tmp_path: Path) -> None:
    (tmp_path / "keyderive.py").write_text(
        '# the reserved password-derived path must not appear at all\nRESERVED = "scrypt"\n',
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "the reserved password KDF is not admitted in CW-002" in result.stderr


def test_cw002_guard_rejects_a_non_96_bit_nonce_constant(tmp_path: Path) -> None:
    (tmp_path / "aead.py").write_text(
        "import secrets\n\nNONCE_SIZE_BYTES = 8\n\n\ndef nonce() -> bytes:\n"
        "    return secrets.token_bytes(NONCE_SIZE_BYTES)\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert "NONCE_SIZE_BYTES must be declared as 12" in result.stderr


def test_cw002_guard_rejects_a_production_resolver_that_can_reach_test_keys(
    tmp_path: Path,
) -> None:
    (tmp_path / "keyprovider.py").write_text(
        "class InMemoryTestKeyProvider:\n    pass\n\n\n"
        "def resolve_platform_key_provider() -> object:\n"
        "    return InMemoryTestKeyProvider()\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "the production provider resolver must not reach InMemoryTestKeyProvider" in result.stderr
    )


def test_cw003_guard_rejects_private_store_connection_access(tmp_path: Path) -> None:
    """CW-003 spines must use the public store API, never the private connection."""

    (tmp_path / "audit.py").write_text(
        "def events(store: object) -> object:\n    return store._connection.execute('SELECT 1')\n",
        encoding="utf-8",
    )
    result = _run_guard(tmp_path)
    assert result.returncode == 1
    assert (
        "only storage.py may touch the private store connection; every other module must "
        "use the public store API" in result.stderr
    )
