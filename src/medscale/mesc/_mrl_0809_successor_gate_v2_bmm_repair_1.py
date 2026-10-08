"""Fail-closed static gate for the MRL-0809 successor v2 BMM portability repair."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Never, cast

from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes
from medscale.mesc._mrl_0809_successor_gate_v2_repair_1 import (
    MRL0809RepairGateError,
    validate_repair_static_prerequisites,
)

_EXPERIMENT: Final = "specs/mesc-experiment-0"
STATIC_MANIFEST: Final = f"{_EXPERIMENT}/mrl-0809-static-prerequisites-v2-bmm-repair-1.json"
PRESERVED_REPAIR_MANIFEST: Final = f"{_EXPERIMENT}/mrl-0809-static-prerequisites-v2-repair-1.json"
FAILURE_RECORD: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2-stage4-retry-1-failure-record.json"
RETRY_AUTHORIZATION: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2-stage4-retry-authorization.json"

_STATIC_SCHEMA: Final = "MESC-MRL-0809-STATIC-PREREQUISITES-V2-BMM-REPAIR-1"
_FAILURE_SCHEMA: Final = "MESC-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-1-FAILURE-RECORD-V1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)


class MRL0809BMMRepairGateError(ValueError):
    """BMM repair material is malformed, drifted, or weakens the consumed-attempt boundary."""


@dataclass(frozen=True, slots=True)
class BMMRepairStaticIdentity:
    manifest_sha256: str
    dependency_lock_sha256: str
    preserved_repair_manifest_sha256: str
    consumed_failure_record_sha256: str


def _fail(message: str) -> Never:
    raise MRL0809BMMRepairGateError(message)


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
    except MRL0809BMMRepairGateError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        CanonicalContractError,
    ) as exc:
        raise MRL0809BMMRepairGateError(f"{label} is invalid canonical JSON") from exc
    if canonical != raw:
        _fail(f"{label} is not canonical JSON")
    return document


def _git_bytes(root: Path, revision: str, path: str) -> bytes:
    if _SHA40.fullmatch(revision) is None:
        _fail("BMM repair revision SHA is malformed")
    try:
        completed = subprocess.run(
            ("git", "show", f"{revision}:{path}"), cwd=root, check=True, capture_output=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809BMMRepairGateError(f"BMM repair source missing: {path}") from exc
    return completed.stdout


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be 64 lowercase hex")
    return value


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail(f"{label} must be an object")
    return cast(dict[str, object], value)


def _validate_consumed_failure(root: Path, revision: str, expected_sha: str) -> None:
    raw = _git_bytes(root, revision, FAILURE_RECORD)
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        _fail("consumed retry failure record drifted")
    document = _canonical_object(raw, label="consumed retry failure record")
    if document.get("schema_version") != _FAILURE_SCHEMA or document.get("task_id") != "MRL-0809":
        _fail("consumed retry failure record identity drifted")
    if (
        document.get("disposition") != "FAIL"
        or document.get("retry_authorized_after_failure") is not False
    ):
        _fail("consumed retry failure disposition was weakened")
    if (
        document.get("retry_authorization_sha256")
        != "e0d4361b36fa9a78a02da2d8582f395897fec8ed1104438c943c50d1328e03d5"
    ):
        _fail("consumed retry authorization identity drifted")
    if hashlib.sha256(_git_bytes(root, revision, RETRY_AUTHORIZATION)).hexdigest() != (
        document.get("retry_authorization_sha256")
    ):
        _fail("retry authorization bytes drifted")

    attempt = _mapping(document.get("attempt"), label="consumed retry attempt")
    if attempt.get("attempt_consumed") is not True:
        _fail("retry-1 must remain consumed")
    if (
        attempt.get("canonical_sha") != "2d8af295b86144a06ce6fe9aad741fed07c2f5d7"
        or attempt.get("canonical_tree") != "5cc4c44d83aa9e51c63c7283a3b037dfa2e3a7ff"
    ):
        _fail("consumed retry canonical identity drifted")
    candidate = _mapping(attempt.get("candidate"), label="consumed Qwen result")
    if (
        candidate.get("model_id") != "Qwen/Qwen3-8B"
        or candidate.get("revision") != "b968826d9c46dd6066d109eabc6255188de91218"
        or candidate.get("stage") != "PASS"
        or candidate.get("probe") != "FAIL"
        or candidate.get("oom_observed") is not False
        or candidate.get("failure_class") != "SANDBOX_TRITON_CUDA_HELPER_BUILD_FAILURE"
    ):
        _fail("consumed Qwen result drifted or was relabeled")
    gemma = _mapping(attempt.get("gemma"), label="consumed Gemma result")
    if gemma != {"probe": "NOT_RUN", "stage": "NOT_RUN"}:
        _fail("Gemma result must remain NOT_RUN")
    runtime = _mapping(attempt.get("runtime"), label="consumed runtime")
    if (
        runtime.get("provider_class") != "GOOGLE_COLAB_FREE"
        or runtime.get("gpu_name") != "Tesla T4"
        or runtime.get("gpu_memory_mib") != 15360
        or runtime.get("monetary_cost_microunits") != 0
    ):
        _fail("consumed runtime class drifted")


def validate_bmm_repair_static_prerequisites(root: Path, revision: str) -> BMMRepairStaticIdentity:
    """Validate repair-1 first, then the consumed retry and BMM portability extension."""

    root = root.resolve(strict=True)
    try:
        preserved = validate_repair_static_prerequisites(root, revision)
    except MRL0809RepairGateError as exc:
        raise MRL0809BMMRepairGateError(
            "preserved repair-1 prerequisites no longer validate"
        ) from exc

    manifest_raw = _git_bytes(root, revision, STATIC_MANIFEST)
    manifest = _canonical_object(manifest_raw, label="BMM repair static manifest")
    if manifest.get("schema_version") != _STATIC_SCHEMA:
        _fail("BMM repair static manifest schema drifted")
    if set(manifest) != {
        "consumed_retry_failure_record",
        "dependency_lock_sha256",
        "preserved_repair_static_manifest",
        "schema_version",
        "sources",
    }:
        _fail("BMM repair static manifest envelope drifted")
    lock_sha = _sha(manifest.get("dependency_lock_sha256"), label="BMM repair dependency lock")
    if lock_sha != preserved.dependency_lock_sha256:
        _fail("BMM repair dependency lock differs from repair-1")
    if hashlib.sha256(_git_bytes(root, revision, "uv.lock")).hexdigest() != lock_sha:
        _fail("BMM repair dependency lock bytes drifted")

    old = _mapping(manifest.get("preserved_repair_static_manifest"), label="repair-1 binding")
    if set(old) != {"path", "sha256"} or old.get("path") != PRESERVED_REPAIR_MANIFEST:
        _fail("repair-1 static manifest binding drifted")
    old_sha = _sha(old.get("sha256"), label="repair-1 manifest sha256")
    if (
        old_sha != preserved.manifest_sha256
        or hashlib.sha256(_git_bytes(root, revision, PRESERVED_REPAIR_MANIFEST)).hexdigest()
        != old_sha
    ):
        _fail("repair-1 static manifest identity drifted")

    failure = _mapping(
        manifest.get("consumed_retry_failure_record"), label="failure record binding"
    )
    if set(failure) != {"path", "sha256"} or failure.get("path") != FAILURE_RECORD:
        _fail("failure record binding drifted")
    failure_sha = _sha(failure.get("sha256"), label="failure record sha256")
    _validate_consumed_failure(root, revision, failure_sha)

    sources = manifest.get("sources")
    if type(sources) is not list or not sources:
        _fail("BMM repair static sources must be a non-empty array")
    seen: set[str] = set()
    previous = ""
    for item in cast(list[object], sources):
        row = _mapping(item, label="BMM repair source")
        if set(row) != {"path", "sha256"}:
            _fail("BMM repair source binding envelope drifted")
        path = row.get("path")
        if type(path) is not str or not path or path <= previous or path in seen:
            _fail("BMM repair source paths must be unique and strictly sorted")
        expected = _sha(row.get("sha256"), label=f"source sha256: {path}")
        if hashlib.sha256(_git_bytes(root, revision, path)).hexdigest() != expected:
            _fail(f"BMM repair source drifted: {path}")
        seen.add(path)
        previous = path
    required = {
        "docs/execution/mrl_0809_successor_v2_stage4_retry_1_failure_postmortem.md",
        "scripts/mesc_mrl_0809_bmm_portability_preflight_v1.py",
        "scripts/mesc_mrl_0809_runtime_feasibility_v2_bmm_repair.py",
        "scripts/mesc_mrl_0809_runtime_worker_v2_bmm_repair.py",
        "scripts/mesc_mrl_0809_stage4_v2_bmm_repair_driver.py",
        "scripts/mesc_mrl_0809_stage4_v2_retry_driver.py",
        "src/medscale/mesc/_mrl_0809_successor_gate_v2_bmm_repair_1.py",
    }
    if not required <= seen:
        _fail("BMM repair static manifest omitted a required source")
    return BMMRepairStaticIdentity(
        manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
        dependency_lock_sha256=lock_sha,
        preserved_repair_manifest_sha256=old_sha,
        consumed_failure_record_sha256=failure_sha,
    )
