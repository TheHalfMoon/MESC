"""Fail-closed MRL-0809 static/runtime prerequisite gate."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Never, cast

from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes
from medscale.mesc._mrl_0809_runtime_feasibility_v1 import (
    MRL0809RuntimeFeasibilityError,
    validate_runtime_feasibility_receipt,
)

_STATIC_MANIFEST: Final = "specs/mesc-experiment-0/mrl-0809-static-prerequisites-v1.json"
_TRUST: Final = "specs/mesc-experiment-0/mrl-0809-runtime-feasibility-trust-v1.json"
_SLOT: Final = "specs/mesc-experiment-0/mrl-0809-runtime-feasibility-slot-v1.json"
_STATIC_SCHEMA: Final = "MESC-MRL-0809-STATIC-PREREQUISITES-V1"
_TRUST_SCHEMA: Final = "MESC-MRL-0809-RUNTIME-FEASIBILITY-TRUST-V1"
_SLOT_SCHEMA: Final = "MESC-MRL-0809-RUNTIME-FEASIBILITY-SLOT-V1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_EXPECTED_GRAMMAR_SHA256: Final = "b63ff5003471f3af8c3624e508f08a418f7e9f7f6ed18ecf743d7f6ad8b7f16c"
_EXPECTED_ENGINE: Final = {
    "name": "xgrammar",
    "sdist_sha256": "7674afeee5e6eff9672627b62d5ab0aa2347ea51674f4d78a5c160029f92bc3e",
    "source_commit": "82505d0d987c36a4209fb3d8571cf6b0f28b5acd",
    "tag": "v0.2.7",
    "version": "0.2.7",
    "wheel_cp311_linux_x86_64_sha256": (
        "e3a4cb4214b228d2fecefe46f46d2f2b0d6c8468fd448319250cae6bccb73339"
    ),
}


class MRL0809PrerequisiteGateError(ValueError):
    """Canonical MRL-0809 prerequisite material is malformed or inconsistent."""


@dataclass(frozen=True, slots=True)
class StaticPrerequisiteIdentity:
    """Validated static prerequisite identity at one exact Git commit."""

    manifest_sha256: str
    dependency_lock_sha256: str


def _reject_constant(value: str) -> Never:
    raise MRL0809PrerequisiteGateError(f"non-standard JSON constant prohibited: {value}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MRL0809PrerequisiteGateError(f"duplicate JSON member rejected: {key}")
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
            raise MRL0809PrerequisiteGateError(f"{label} must be a JSON object")
        document = cast(dict[str, object], value)
        canonical = canonical_json_bytes(document)
    except MRL0809PrerequisiteGateError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        CanonicalContractError,
    ) as exc:
        raise MRL0809PrerequisiteGateError(f"{label} is invalid canonical JSON") from exc
    if canonical != raw:
        raise MRL0809PrerequisiteGateError(f"{label} is not canonical JSON")
    return document


def _git_bytes(root: Path, revision: str, path: str) -> bytes:
    if _SHA40.fullmatch(revision) is None:
        raise MRL0809PrerequisiteGateError("decision-base SHA is malformed")
    try:
        completed = subprocess.run(
            ("git", "show", f"{revision}:{path}"),
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809PrerequisiteGateError(
            f"canonical prerequisite source missing: {path}"
        ) from exc
    return completed.stdout


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise MRL0809PrerequisiteGateError(f"{label} must be 64 lowercase hex")
    return value


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    if _SHA40.fullmatch(ancestor) is None or _SHA40.fullmatch(descendant) is None:
        return False
    completed = subprocess.run(
        ("git", "merge-base", "--is-ancestor", ancestor, descendant),
        cwd=root,
        check=False,
        capture_output=True,
    )
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    raise MRL0809PrerequisiteGateError("Git ancestry check failed")


def validate_static_prerequisites(root: Path, decision_base: str) -> StaticPrerequisiteIdentity:
    """Rebuild the immutable static-prerequisite identity from exact Git bytes."""
    raw = _git_bytes(root, decision_base, _STATIC_MANIFEST)
    document = _canonical_object(raw, label="MRL-0809 static prerequisite manifest")
    if set(document) != {
        "dependency_lock_sha256",
        "fhir_version",
        "generated_grammar_sha256",
        "grammar_engine",
        "schema_version",
        "sources",
    }:
        raise MRL0809PrerequisiteGateError("static prerequisite manifest schema is invalid")
    if document["schema_version"] != _STATIC_SCHEMA or document["fhir_version"] != "4.0.1":
        raise MRL0809PrerequisiteGateError("static prerequisite manifest version drifted")
    if document["generated_grammar_sha256"] != _EXPECTED_GRAMMAR_SHA256:
        raise MRL0809PrerequisiteGateError("static prerequisite grammar identity drifted")
    if document["grammar_engine"] != _EXPECTED_ENGINE:
        raise MRL0809PrerequisiteGateError("static prerequisite grammar engine identity drifted")
    dependency_lock_sha = _sha(document["dependency_lock_sha256"], label="dependency lock SHA")
    source_rows = document["sources"]
    if type(source_rows) is not list or not source_rows:
        raise MRL0809PrerequisiteGateError("static prerequisite sources must be non-empty")
    paths: list[str] = []
    observed_lock_sha: str | None = None
    for item in cast(list[object], source_rows):
        if type(item) is not dict or set(item) != {"path", "sha256"}:
            raise MRL0809PrerequisiteGateError("static prerequisite source record is invalid")
        row = cast(dict[str, object], item)
        path = row["path"]
        if type(path) is not str or not path or path.startswith("/") or ".." in Path(path).parts:
            raise MRL0809PrerequisiteGateError("static prerequisite source path is invalid")
        expected = _sha(row["sha256"], label=f"source SHA for {path}")
        actual = hashlib.sha256(_git_bytes(root, decision_base, path)).hexdigest()
        if actual != expected:
            raise MRL0809PrerequisiteGateError(f"static prerequisite source drifted: {path}")
        if path == "uv.lock":
            observed_lock_sha = actual
        paths.append(path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise MRL0809PrerequisiteGateError("static prerequisite sources must be sorted and unique")
    if observed_lock_sha != dependency_lock_sha:
        raise MRL0809PrerequisiteGateError("dependency lock identity does not match source binding")
    return StaticPrerequisiteIdentity(
        manifest_sha256=hashlib.sha256(raw).hexdigest(),
        dependency_lock_sha256=dependency_lock_sha,
    )


def _trusted_receipts(root: Path, decision_base: str) -> tuple[str, ...]:
    document = _canonical_object(
        _git_bytes(root, decision_base, _TRUST), label="MRL-0809 runtime-feasibility trust root"
    )
    if set(document) != {"schema_version", "trusted_receipt_sha256"}:
        raise MRL0809PrerequisiteGateError("runtime-feasibility trust schema is invalid")
    if document["schema_version"] != _TRUST_SCHEMA:
        raise MRL0809PrerequisiteGateError("runtime-feasibility trust schema version drifted")
    raw = document["trusted_receipt_sha256"]
    if type(raw) is not list:
        raise MRL0809PrerequisiteGateError("trusted receipt digests must be an array")
    result = tuple(_sha(item, label="trusted receipt SHA") for item in cast(list[object], raw))
    if result != tuple(sorted(result)) or len(result) != len(set(result)):
        raise MRL0809PrerequisiteGateError("trusted receipt digests must be sorted and unique")
    return result


def mrl0809_prerequisite_gate(root: Path, decision_base: str) -> bool:
    """Return True only for static-valid plus separately trusted runtime feasibility."""
    static = validate_static_prerequisites(root, decision_base)
    trusted = _trusted_receipts(root, decision_base)
    slot = _canonical_object(
        _git_bytes(root, decision_base, _SLOT), label="MRL-0809 runtime-feasibility slot"
    )
    if slot.get("schema_version") != _SLOT_SCHEMA or slot.get("task_id") != "MRL-0809":
        raise MRL0809PrerequisiteGateError("runtime-feasibility slot identity drifted")
    state = slot.get("state")
    if state == "ABSENT":
        if set(slot) != {"schema_version", "state", "task_id"}:
            raise MRL0809PrerequisiteGateError("ABSENT runtime-feasibility slot schema is invalid")
        return False
    if state != "PRESENT" or set(slot) != {"receipt", "schema_version", "state", "task_id"}:
        raise MRL0809PrerequisiteGateError("runtime-feasibility slot state/schema is invalid")
    receipt_value = slot["receipt"]
    if type(receipt_value) is not dict:
        raise MRL0809PrerequisiteGateError("runtime-feasibility slot receipt must be an object")
    receipt_bytes = canonical_json_bytes(receipt_value)
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    if receipt_sha not in trusted:
        return False
    try:
        receipt = validate_runtime_feasibility_receipt(
            receipt_bytes,
            expected_static_prerequisite_manifest_sha256=static.manifest_sha256,
            expected_dependency_lock_sha256=static.dependency_lock_sha256,
        )
    except MRL0809RuntimeFeasibilityError as exc:
        raise MRL0809PrerequisiteGateError("runtime-feasibility receipt failed validation") from exc
    if not _is_ancestor(root, receipt.repository_sha, decision_base):
        return False
    try:
        tree = subprocess.run(
            ("git", "rev-parse", f"{receipt.repository_sha}^{{tree}}"),
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809PrerequisiteGateError(
            "runtime-feasibility producer tree lookup failed"
        ) from exc
    return tree == receipt.repository_tree


__all__ = [
    "MRL0809PrerequisiteGateError",
    "StaticPrerequisiteIdentity",
    "mrl0809_prerequisite_gate",
    "validate_static_prerequisites",
]
