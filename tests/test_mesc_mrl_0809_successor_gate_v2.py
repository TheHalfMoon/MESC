"""MRL-0809 successor (v2) machine-state gate: adversarial coverage on a cloned repository."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_machine_state_generation_v1 import (
    MachineStateGenerationError,
    generate_machine_state,
)

_ROOT = Path(__file__).resolve().parents[1]


def _receipt() -> dict[str, Any]:
    spec = importlib.util.spec_from_file_location(
        "mrl_0809_successor_v2_fixtures",
        Path(__file__).with_name("test_mesc_mrl_0809_successor_v2.py"),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt = module._receipt()
    assert isinstance(receipt, dict)
    return receipt


_EXP = Path("specs/mesc-experiment-0")
_V2_MANIFEST = _EXP / "mrl-0809-static-prerequisites-v2.json"
_V2_TRUST = _EXP / "mrl-0809-runtime-feasibility-trust-v2.json"
_V2_SLOT = _EXP / "mrl-0809-runtime-feasibility-slot-v2.json"
_V1_TRUST = _EXP / "mrl-0809-runtime-feasibility-trust-v1.json"
_V1_SLOT = _EXP / "mrl-0809-runtime-feasibility-slot-v1.json"
_V1_RECORD = _EXP / "mrl-0809-v1-infeasibility-record.json"
_ROSTER = _EXP / "candidate-roster-v2.json"
_OBJECTIVE_V2 = _EXP / "mrl-0806-objective-budgets-authorization-v2.json"
_V1_ROSTER = _EXP / "candidate-roster-v1.json"
_SUCCESSOR_FAILED = "MRL-0809 successor prerequisite gate failed closed"


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(("git", *args), cwd=root, check=True, capture_output=True, text=True)
    return completed.stdout.strip()


def _clone(tmp_path: Path) -> Path:
    destination = tmp_path / "repo"
    subprocess.run(
        ("git", "clone", "--quiet", "--no-hardlinks", str(_ROOT), str(destination)),
        check=True,
        capture_output=True,
        text=True,
    )
    source_head = _git(_ROOT, "rev-parse", "HEAD")
    _git(destination, "checkout", "--detach", source_head)
    _git(destination, "config", "user.name", "MRL-0809 successor test")
    _git(destination, "config", "user.email", "mrl0809-successor-test@example.invalid")
    _git(destination, "update-ref", "refs/remotes/origin/main", source_head)
    return destination


def _commit(root: Path, message: str, *paths: Path) -> str:
    _git(root, "add", *(str(path) for path in paths))
    _git(root, "commit", "-m", message)
    head = _git(root, "rev-parse", "HEAD")
    _git(root, "update-ref", "refs/remotes/origin/main", head)
    return head


def _task_state(root: Path, tmp_path: Path) -> str:
    output = tmp_path / "machine-state"
    generate_machine_state(root, output)
    payload = json.loads((output / "PROJECT_STATE.json").read_text(encoding="utf-8"))
    indexed = {row["task_id"]: row for row in payload["tasks"]}
    state = indexed["MRL-0809"]["state"]
    assert isinstance(state, str)
    return state


def _admit(root: Path, receipt: dict[str, Any], *, trusted: bool = True) -> None:
    receipt_bytes = canonical_json_bytes(receipt)
    trust = {
        "schema_version": "MESC-MRL-0809-RUNTIME-FEASIBILITY-TRUST-V2",
        "trusted_receipt_sha256": [hashlib.sha256(receipt_bytes).hexdigest()] if trusted else [],
    }
    slot = {
        "receipt": receipt,
        "schema_version": "MESC-MRL-0809-RUNTIME-FEASIBILITY-SLOT-V2",
        "state": "PRESENT",
        "task_id": "MRL-0809",
    }
    (root / _V2_TRUST).write_bytes(canonical_json_bytes(trust))
    (root / _V2_SLOT).write_bytes(canonical_json_bytes(slot))
    _commit(root, "test: admit successor runtime feasibility", _V2_TRUST, _V2_SLOT)


def _genuine_receipt(root: Path) -> dict[str, Any]:
    receipt = _receipt()
    receipt["repository_sha"] = _git(root, "rev-parse", "HEAD")
    receipt["repository_tree"] = _git(root, "rev-parse", "HEAD^{tree}")
    manifest = (root / _V2_MANIFEST).read_bytes()
    receipt["static_prerequisite_manifest_sha256"] = hashlib.sha256(manifest).hexdigest()
    receipt["dependency_lock_sha256"] = json.loads(manifest)["dependency_lock_sha256"]
    return receipt


def test_absent_successor_slot_keeps_mrl0809_planned(tmp_path: Path) -> None:
    assert _task_state(_clone(tmp_path), tmp_path) == "PLANNED"


def test_trusted_successor_pass_makes_mrl0809_eligible_and_leaves_v1_absent(
    tmp_path: Path,
) -> None:
    repo = _clone(tmp_path)
    _admit(repo, _genuine_receipt(repo))
    assert _task_state(repo, tmp_path) == "ELIGIBLE"
    assert json.loads((repo / _V1_SLOT).read_bytes())["state"] == "ABSENT"
    assert json.loads((repo / _V1_TRUST).read_bytes())["trusted_receipt_sha256"] == []


def test_untrusted_successor_receipt_keeps_mrl0809_planned(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    _admit(repo, _genuine_receipt(repo), trusted=False)
    assert _task_state(repo, tmp_path) == "PLANNED"


def test_trusted_but_forged_successor_receipt_fails_closed(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    receipt = _genuine_receipt(repo)
    receipt["offload_performed"] = True
    _admit(repo, receipt)
    with pytest.raises(MachineStateGenerationError, match=_SUCCESSOR_FAILED):
        _task_state(repo, tmp_path)


def test_successor_receipt_from_a_non_ancestor_commit_is_not_admitted(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    receipt = _genuine_receipt(repo)
    orphan = _git(repo, "commit-tree", receipt["repository_tree"], "-m", "orphan producer")
    receipt["repository_sha"] = orphan
    _admit(repo, receipt)
    assert _task_state(repo, tmp_path) == "PLANNED"


def test_successor_receipt_from_an_unknown_commit_fails_closed(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    receipt = _genuine_receipt(repo)
    receipt["repository_sha"] = "0" * 40
    _admit(repo, receipt)
    with pytest.raises(MachineStateGenerationError, match=_SUCCESSOR_FAILED):
        _task_state(repo, tmp_path)


def test_v1_slot_cannot_be_rewritten_into_a_pass(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    forged = {"forged": True}
    trust = {
        "schema_version": "MESC-MRL-0809-RUNTIME-FEASIBILITY-TRUST-V1",
        "trusted_receipt_sha256": [hashlib.sha256(canonical_json_bytes(forged)).hexdigest()],
    }
    slot = {
        "receipt": forged,
        "schema_version": "MESC-MRL-0809-RUNTIME-FEASIBILITY-SLOT-V1",
        "state": "PRESENT",
        "task_id": "MRL-0809",
    }
    (repo / _V1_TRUST).write_bytes(canonical_json_bytes(trust))
    (repo / _V1_SLOT).write_bytes(canonical_json_bytes(slot))
    _commit(repo, "test: forge v1 PASS", _V1_TRUST, _V1_SLOT)
    with pytest.raises(MachineStateGenerationError, match="MRL-0809"):
        _task_state(repo, tmp_path)


def test_v1_trust_root_overwrite_blocks_even_a_trusted_successor_pass(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    trust = {
        "schema_version": "MESC-MRL-0809-RUNTIME-FEASIBILITY-TRUST-V1",
        "trusted_receipt_sha256": ["a" * 64],
    }
    (repo / _V1_TRUST).write_bytes(canonical_json_bytes(trust))
    _commit(repo, "test: overwrite v1 trust root", _V1_TRUST)
    _admit(repo, _genuine_receipt(repo))
    with pytest.raises(MachineStateGenerationError, match=_SUCCESSOR_FAILED):
        _task_state(repo, tmp_path)


@pytest.mark.parametrize(
    ("path", "old", "new"),
    [
        (_V1_RECORD, b'"pass_claimed":false', b'"pass_claimed":true'),
        (_V1_RECORD, b'"gemma_tested":false', b'"gemma_tested":true'),
        (_ROSTER, b'"state":"UNCHANGED"', b'"state":"REPLACED"'),
        (_OBJECTIVE_V2, b'"research_question":"RQ1"', b'"research_question":"RQ2"'),
        (_V1_ROSTER, b'"PREFERRED_FOUNDATION_CANDIDATE"', b'"DEPRECATED_CANDIDATE"'),
    ],
)
def test_successor_artifact_or_v1_evidence_rewrite_fails_closed(
    tmp_path: Path, path: Path, old: bytes, new: bytes
) -> None:
    repo = _clone(tmp_path)
    raw = (repo / path).read_bytes()
    assert raw.count(old) == 1
    (repo / path).write_bytes(raw.replace(old, new))
    _commit(repo, "test: rewrite successor evidence", path)
    with pytest.raises(MachineStateGenerationError, match=_SUCCESSOR_FAILED):
        _task_state(repo, tmp_path)


def test_successor_bound_source_drift_fails_closed(tmp_path: Path) -> None:
    repo = _clone(tmp_path)
    harness = Path("scripts/mesc_mrl_0809_runtime_feasibility_v2.py")
    (repo / harness).write_bytes((repo / harness).read_bytes() + b"\n")
    _commit(repo, "test: drift successor harness", harness)
    with pytest.raises(MachineStateGenerationError, match=_SUCCESSOR_FAILED):
        _task_state(repo, tmp_path)
