"""Fail-closed static gate for the MRL-0809 successor v2 repair-1 contract.

This gate extends, and never replaces or weakens, the preserved successor v2
static gate. It validates repository-repair material only. Runtime evidence
admission remains absent and no hosted attempt is authorized by this module.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Never, cast

from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes
from medscale.mesc._mrl_0809_successor_gate_v2 import (
    MRL0809SuccessorGateError,
    validate_successor_static_prerequisites,
)

_EXPERIMENT: Final = "specs/mesc-experiment-0"
STATIC_MANIFEST: Final = f"{_EXPERIMENT}/mrl-0809-static-prerequisites-v2-repair-1.json"
AUTHORIZATION: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2-stage4-repair-authorization.json"
TRUST: Final = f"{_EXPERIMENT}/mrl-0809-runtime-feasibility-trust-v2-repair-1.json"
SLOT: Final = f"{_EXPERIMENT}/mrl-0809-runtime-feasibility-slot-v2-repair-1.json"
PRESERVED_V2_MANIFEST: Final = f"{_EXPERIMENT}/mrl-0809-static-prerequisites-v2.json"

_STATIC_SCHEMA: Final = "MESC-MRL-0809-STATIC-PREREQUISITES-V2-REPAIR-1"
_AUTH_SCHEMA: Final = "MESC-MRL-0809-SUCCESSOR-V2-STAGE4-REPAIR-AUTHORIZATION-V1"
_TRUST_SCHEMA: Final = "MESC-MRL-0809-RUNTIME-FEASIBILITY-TRUST-V2-REPAIR-1"
_SLOT_SCHEMA: Final = "MESC-MRL-0809-RUNTIME-FEASIBILITY-SLOT-V2-REPAIR-1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_AUTHORIZATION_KEYS: Final = frozenset(
    {
        "decision_id",
        "decision_record",
        "non_grants",
        "repair_scope",
        "runtime_attempts_authorized",
        "schema_version",
    }
)
_NON_GRANT_KEYS: Final = frozenset(
    {
        "mrl0809_closeout",
        "mrl0899_closeout",
        "new_stage4_attempt",
        "offload_fallback",
        "paid_compute",
        "scientific_rq1_execution",
        "training",
        "weight_mutation",
    }
)
_DECISION_RECORD_KEYS: Final = frozenset({"path", "sha256"})
_DECISION_RECORD_PATH: Final = (
    f"{_EXPERIMENT}/mrl-0809-successor-v2/founder-decision-stage4-repair.md"
)
_DECISION_RECORD_SHA256: Final = (
    "7a8d7ed8e6c79879cf01c9d846af031a8f38ca74f8382ebd681d32736889c7f0"
)


class MRL0809RepairGateError(ValueError):
    """Repair-1 material is malformed, drifted, or weakens a preserved boundary."""


@dataclass(frozen=True, slots=True)
class RepairStaticIdentity:
    manifest_sha256: str
    dependency_lock_sha256: str
    preserved_v2_manifest_sha256: str


def _fail(message: str) -> Never:
    raise MRL0809RepairGateError(message)


def _reject_constant(value: str) -> Never:
    _fail(f"non-standard JSON constant prohibited: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail(f"duplicate JSON member rejected: {key}")
        result[key] = value
    return result


def _canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        if type(value) is not dict:
            _fail(f"{label} must be a JSON object")
        document = cast(dict[str, object], value)
        canonical = canonical_json_bytes(document)
    except MRL0809RepairGateError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        CanonicalContractError,
    ) as exc:
        raise MRL0809RepairGateError(f"{label} is invalid canonical JSON") from exc
    if canonical != raw:
        _fail(f"{label} is not canonical JSON")
    return document


def _git_bytes(root: Path, revision: str, path: str) -> bytes:
    if _SHA40.fullmatch(revision) is None:
        _fail("repair decision-base SHA is malformed")
    try:
        completed = subprocess.run(
            ("git", "show", f"{revision}:{path}"),
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809RepairGateError(f"repair source missing: {path}") from exc
    return completed.stdout


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be 64 lowercase hex")
    return value


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail(f"{label} must be an object")
    return cast(dict[str, object], value)


def _validate_repair_authority(root: Path, revision: str, expected_sha: str) -> None:
    raw = _git_bytes(root, revision, AUTHORIZATION)
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        _fail("repair authorization drifted")
    document = _canonical_object(raw, label="repair authorization")
    if set(document) != _AUTHORIZATION_KEYS:
        _fail("repair authorization envelope drifted")
    if document.get("schema_version") != _AUTH_SCHEMA:
        _fail("repair authorization schema drifted")
    runtime_attempts = document.get("runtime_attempts_authorized")
    if (
        document.get("decision_id") != "FD-MRL-0809-SUCCESSOR-V2-STAGE4-REPAIR-1"
        or document.get("repair_scope") != "REPOSITORY_REPAIR_ONLY"
        or type(runtime_attempts) is not int
        or runtime_attempts != 0
    ):
        _fail("repair authorization scope was weakened or changed")
    non_grants = _mapping(document.get("non_grants"), label="repair non_grants")
    if set(non_grants) != _NON_GRANT_KEYS or any(
        value is not False for value in non_grants.values()
    ):
        _fail("repair non-grants were weakened")
    decision = _mapping(document.get("decision_record"), label="repair decision_record")
    if set(decision) != _DECISION_RECORD_KEYS:
        _fail("repair decision record envelope drifted")
    path = decision.get("path")
    if path != _DECISION_RECORD_PATH:
        _fail("repair decision record path drifted")
    decision_sha = _sha(decision.get("sha256"), label="repair decision sha256")
    if decision_sha != _DECISION_RECORD_SHA256:
        _fail("Founder repair decision identity drifted")
    decision_raw = _git_bytes(root, revision, _DECISION_RECORD_PATH)
    if hashlib.sha256(decision_raw).hexdigest() != decision_sha:
        _fail("Founder repair decision record drifted")


def _validate_empty_runtime_state(root: Path, revision: str) -> None:
    trust = _canonical_object(_git_bytes(root, revision, TRUST), label="repair trust root")
    slot = _canonical_object(_git_bytes(root, revision, SLOT), label="repair evidence slot")
    if trust != {"schema_version": _TRUST_SCHEMA, "trusted_receipt_sha256": []}:
        _fail("repair trust root must remain empty before separate evidence admission")
    if slot != {"schema_version": _SLOT_SCHEMA, "state": "ABSENT", "task_id": "MRL-0809"}:
        _fail("repair evidence slot must remain ABSENT before separate evidence admission")


def validate_repair_static_prerequisites(root: Path, revision: str) -> RepairStaticIdentity:
    """Validate old successor v2 first, then the bounded repair-1 extension."""

    root = root.resolve(strict=True)
    try:
        preserved = validate_successor_static_prerequisites(root, revision)
    except MRL0809SuccessorGateError as exc:
        raise MRL0809RepairGateError(
            "preserved successor v2 prerequisites no longer validate"
        ) from exc

    manifest_raw = _git_bytes(root, revision, STATIC_MANIFEST)
    manifest = _canonical_object(manifest_raw, label="repair static manifest")
    if manifest.get("schema_version") != _STATIC_SCHEMA:
        _fail("repair static manifest schema drifted")
    if set(manifest) != {
        "dependency_lock_sha256",
        "preserved_v2_static_manifest",
        "repair_authorization",
        "schema_version",
        "sources",
    }:
        _fail("repair static manifest envelope drifted")

    lock_sha = _sha(manifest.get("dependency_lock_sha256"), label="repair dependency lock")
    if lock_sha != preserved.dependency_lock_sha256:
        _fail("repair dependency lock differs from preserved successor v2")
    if hashlib.sha256(_git_bytes(root, revision, "uv.lock")).hexdigest() != lock_sha:
        _fail("repair dependency lock bytes drifted")

    old_binding = _mapping(
        manifest.get("preserved_v2_static_manifest"),
        label="preserved v2 manifest binding",
    )
    if set(old_binding) != {"path", "sha256"}:
        _fail("preserved v2 manifest binding envelope drifted")
    if old_binding.get("path") != PRESERVED_V2_MANIFEST:
        _fail("repair manifest no longer binds the preserved v2 manifest path")
    old_sha = _sha(old_binding.get("sha256"), label="preserved v2 manifest sha256")
    actual_old_sha = hashlib.sha256(_git_bytes(root, revision, PRESERVED_V2_MANIFEST)).hexdigest()
    if old_sha != actual_old_sha or old_sha != preserved.manifest_sha256:
        _fail("preserved v2 static manifest identity drifted")

    auth_binding = _mapping(
        manifest.get("repair_authorization"),
        label="repair authorization binding",
    )
    if set(auth_binding) != {"path", "sha256"}:
        _fail("repair authorization binding envelope drifted")
    if auth_binding.get("path") != AUTHORIZATION:
        _fail("repair manifest authorization path drifted")
    auth_sha = _sha(auth_binding.get("sha256"), label="repair authorization sha256")
    _validate_repair_authority(root, revision, auth_sha)

    sources = manifest.get("sources")
    if type(sources) is not list or not sources:
        _fail("repair static sources must be a non-empty array")
    seen: set[str] = set()
    previous = ""
    for item in cast(list[object], sources):
        row = _mapping(item, label="repair static source")
        if set(row) != {"path", "sha256"}:
            _fail("repair source binding envelope drifted")
        path = row.get("path")
        if type(path) is not str or not path or path <= previous or path in seen:
            _fail("repair source paths must be unique and strictly sorted")
        expected = _sha(row.get("sha256"), label=f"repair source sha256: {path}")
        if hashlib.sha256(_git_bytes(root, revision, path)).hexdigest() != expected:
            _fail(f"repair source drifted: {path}")
        seen.add(path)
        previous = path

    required_sources = {
        "docs/execution/mrl_0809_runtime_feasibility_runbook_v2_repair_1.md",
        "scripts/mesc_mrl_0809_runtime_feasibility_v2_repair.py",
        "scripts/mesc_mrl_0809_runtime_worker_v2_repair.py",
        "scripts/mesc_mrl_0809_stage4_v2_repair_driver.py",
        "src/medscale/mesc/_mrl_0809_device_placement_audit_v1.py",
        "src/medscale/mesc/_mrl_0809_successor_gate_v2_repair_1.py",
    }
    if not required_sources <= seen:
        _fail("repair static manifest omitted a required repair source")

    _validate_empty_runtime_state(root, revision)
    return RepairStaticIdentity(
        manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
        dependency_lock_sha256=lock_sha,
        preserved_v2_manifest_sha256=old_sha,
    )
