"""Fail-closed authority gate for MRL-0809 Stage-4 retry-2."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Never, cast

from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes
from medscale.mesc._mrl_0809_successor_gate_v2_bmm_repair_1 import (
    MRL0809BMMRepairGateError,
    validate_bmm_repair_static_prerequisites,
)

_EXPERIMENT: Final = "specs/mesc-experiment-0"
AUTHORIZATION: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2-stage4-retry-2-authorization.json"
DECISION: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2/founder-decision-stage4-retry-2.md"
STATIC_MANIFEST: Final = f"{_EXPERIMENT}/mrl-0809-stage4-retry-2-static-prerequisites-v1.json"

_AUTHORIZATION_SHA256: Final = "673407d170cc3c43e9d162d1b71d62ef9732397be971efd7f8414ea03bb75e72"
_DECISION_SHA256: Final = "a2e51e5042398bcdd164e770bf3a85f87077aba16f9eb76cf83339244c9a6b45"
_BMM_REPAIR_MERGE_SHA: Final = "07a20c8a01a6b3562b98fa48fbd19ed11be7a8eb"
_BMM_REPAIR_MERGE_TREE: Final = "0ae92820f266bf17a23507e3286ae33f968a2972"
_BMM_REPAIR_MANIFEST_SHA256: Final = (
    "1868f5501903b921ace2db47511b89c50b0017136e3ebe4180a7493fdc395728"
)
_DEPENDENCY_LOCK_SHA256: Final = "6fa0e0b49d19e305032ecd04940db0b9e252dd23b6fbec588b224f739048efc4"
_PRESERVED_REPAIR_MANIFEST_SHA256: Final = (
    "d943a8bc4fbc7f5c8baf8716dd206b6262966c43c37a7a257645518a620f2c7d"
)
_CONSUMED_RETRY_1_FAILURE_SHA256: Final = (
    "6b8ed146e82b705bc536530e60a10b0c81c32f3ab3dd16f4155562706a9ecf0f"
)
_STATIC_SCHEMA: Final = "MESC-MRL-0809-STAGE4-RETRY-2-STATIC-PREREQUISITES-V1"
_AUTH_SCHEMA: Final = "MESC-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-2-AUTHORIZATION-V1"
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)


class MRL0809Stage4Retry2GateError(ValueError):
    """Retry-2 authority is absent, drifted, malformed, or not applicable."""


@dataclass(frozen=True, slots=True)
class Stage4Retry2AuthorityIdentity:
    authorization_sha256: str
    decision_sha256: str
    static_manifest_sha256: str
    bmm_repair_merge_sha: str
    bmm_repair_merge_tree: str


def _fail(message: str) -> Never:
    raise MRL0809Stage4Retry2GateError(message)


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
    except MRL0809Stage4Retry2GateError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        CanonicalContractError,
    ) as exc:
        raise MRL0809Stage4Retry2GateError(f"{label} is invalid canonical JSON") from exc
    if canonical != raw:
        _fail(f"{label} is not canonical JSON")
    return document


def _git_bytes(root: Path, revision: str, path: str) -> bytes:
    if _SHA40.fullmatch(revision) is None:
        _fail("retry-2 revision SHA is malformed")
    try:
        completed = subprocess.run(
            ("git", "show", f"{revision}:{path}"),
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809Stage4Retry2GateError(f"retry-2 source missing: {path}") from exc
    return completed.stdout


def _git_text(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ("git", *args),
            cwd=root,
            check=True,
            text=True,
            encoding="utf-8",
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809Stage4Retry2GateError(
            f"git retry-2 authority check failed: {' '.join(args)}"
        ) from exc
    return completed.stdout.strip()


def _require_ancestor(root: Path, ancestor: str, revision: str) -> None:
    completed = subprocess.run(
        ("git", "merge-base", "--is-ancestor", ancestor, revision),
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        _fail("runtime revision does not descend from the canonical BMM repair merge")


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail(f"{label} must be an object")
    return cast(dict[str, object], value)


def _sha256(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be 64 lowercase hex")
    return value


def _validate_authorization(raw: bytes) -> None:
    document = _canonical_object(raw, label="retry-2 authorization")
    if document.get("schema_version") != _AUTH_SCHEMA:
        _fail("retry-2 authorization schema drifted")
    if document.get("decision_id") != "FD-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-2":
        _fail("retry-2 decision identity drifted")
    if document.get("activation_precondition") != (
        "ACCEPTED_RETRY_2_IMPLEMENTATION_CANONICAL_AND_FRESH_MAIN_QUALIFIED"
    ):
        _fail("retry-2 effectiveness boundary drifted")

    decision = _mapping(document.get("decision_record"), label="decision record")
    if decision != {"path": DECISION, "sha256": _DECISION_SHA256}:
        _fail("retry-2 decision binding drifted")

    binding = _mapping(document.get("bmm_repair_binding"), label="BMM repair binding")
    expected_binding = {
        "bmm_repair_static_manifest_sha256": _BMM_REPAIR_MANIFEST_SHA256,
        "consumed_retry_1_failure_record_sha256": _CONSUMED_RETRY_1_FAILURE_SHA256,
        "dependency_lock_sha256": _DEPENDENCY_LOCK_SHA256,
        "merge_sha": _BMM_REPAIR_MERGE_SHA,
        "merge_tree": _BMM_REPAIR_MERGE_TREE,
        "preserved_repair_static_manifest_sha256": _PRESERVED_REPAIR_MANIFEST_SHA256,
    }
    if binding != expected_binding:
        _fail("retry-2 BMM repair binding drifted")

    grant = _mapping(document.get("grant"), label="retry-2 grant")
    if grant != {
        "gpu_class": "STANDARD_T4",
        "input": "SYNTHETIC_ONLY",
        "launches_authorized": 1,
        "max_peak_gpu_memory_bytes": 12884901888,
        "monetary_cost_microunits": 0,
        "provider_class": "GOOGLE_COLAB_FREE",
        "runtime_representation": "bitsandbytes-nf4-v1",
    }:
        _fail("retry-2 bounded grant drifted")

    candidates = document.get("candidates")
    if candidates != [
        {"model_id": "Qwen/Qwen3-8B", "revision": "b968826d9c46dd6066d109eabc6255188de91218"},
        {
            "model_id": "google/gemma-4-12B-it",
            "revision": "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
        },
    ]:
        _fail("retry-2 candidate roster drifted")

    consumption = _mapping(document.get("launch_consumption"), label="launch consumption")
    if consumption != {
        "automatic_relaunch": False,
        "automatic_retry": False,
        "consumed_on_hosted_launch_invocation": True,
        "preflight_failure_exhausts_launch": True,
        "provider_or_session_failure_exhausts_launch": True,
        "receipt_required_before_bmm_sequence": True,
    }:
        _fail("retry-2 launch-consumption semantics drifted")

    historical = _mapping(document.get("historical"), label="historical evidence")
    if historical.get("overwrite_or_relabel_allowed") is not False:
        _fail("historical evidence immutability was weakened")
    if (
        historical.get("prior_retry_1") != "FAIL"
        or historical.get("prior_retry_1_qwen_stage") != "PASS"
        or historical.get("prior_retry_1_qwen_probe") != "FAIL"
        or historical.get("prior_retry_1_failure_class")
        != "SANDBOX_TRITON_CUDA_HELPER_BUILD_FAILURE"
        or historical.get("prior_retry_1_cuda_oom_observed") is not False
        or historical.get("prior_retry_1_gemma_stage") != "NOT_RUN"
        or historical.get("prior_retry_1_gemma_probe") != "NOT_RUN"
    ):
        _fail("retry-1 historical evidence drifted")

    non_grants = _mapping(document.get("non_grants"), label="retry-2 non-grants")
    if not non_grants or any(value is not False for value in non_grants.values()):
        _fail("retry-2 non-grants were weakened")


def validate_stage4_retry_2_authority(
    root: Path,
    revision: str,
) -> Stage4Retry2AuthorityIdentity:
    """Validate BMM repair preservation and accepted retry-2 authority."""

    root = root.resolve(strict=True)
    try:
        bmm = validate_bmm_repair_static_prerequisites(root, revision)
    except MRL0809BMMRepairGateError as exc:
        raise MRL0809Stage4Retry2GateError(
            "preserved BMM repair prerequisites no longer validate"
        ) from exc

    if bmm.manifest_sha256 != _BMM_REPAIR_MANIFEST_SHA256:
        _fail("BMM repair static manifest identity drifted")
    if bmm.dependency_lock_sha256 != _DEPENDENCY_LOCK_SHA256:
        _fail("dependency lock identity drifted")
    if bmm.preserved_repair_manifest_sha256 != _PRESERVED_REPAIR_MANIFEST_SHA256:
        _fail("preserved repair manifest identity drifted")
    if bmm.consumed_failure_record_sha256 != _CONSUMED_RETRY_1_FAILURE_SHA256:
        _fail("consumed retry-1 failure identity drifted")

    _require_ancestor(root, _BMM_REPAIR_MERGE_SHA, revision)
    if _git_text(root, "show", "-s", "--format=%T", _BMM_REPAIR_MERGE_SHA) != (
        _BMM_REPAIR_MERGE_TREE
    ):
        _fail("canonical BMM repair merge tree drifted")

    decision_raw = _git_bytes(root, revision, DECISION)
    if hashlib.sha256(decision_raw).hexdigest() != _DECISION_SHA256:
        _fail("accepted Founder retry-2 decision bytes drifted")

    authorization_raw = _git_bytes(root, revision, AUTHORIZATION)
    if hashlib.sha256(authorization_raw).hexdigest() != _AUTHORIZATION_SHA256:
        _fail("retry-2 authorization bytes drifted")
    _validate_authorization(authorization_raw)

    manifest_raw = _git_bytes(root, revision, STATIC_MANIFEST)
    manifest = _canonical_object(manifest_raw, label="retry-2 static manifest")
    if manifest.get("schema_version") != _STATIC_SCHEMA:
        _fail("retry-2 static manifest schema drifted")
    if manifest.get("decision_sha256") != _DECISION_SHA256:
        _fail("retry-2 static manifest decision binding drifted")
    if manifest.get("authorization_sha256") != _AUTHORIZATION_SHA256:
        _fail("retry-2 static manifest authorization binding drifted")
    if manifest.get("bmm_repair_static_manifest_sha256") != _BMM_REPAIR_MANIFEST_SHA256:
        _fail("retry-2 static manifest BMM binding drifted")

    sources = manifest.get("sources")
    if type(sources) is not list or not sources:
        _fail("retry-2 static sources must be a non-empty array")
    seen: set[str] = set()
    previous = ""
    for item in cast(list[object], sources):
        row = _mapping(item, label="retry-2 static source")
        if set(row) != {"path", "sha256"}:
            _fail("retry-2 source binding envelope drifted")
        path = row.get("path")
        if type(path) is not str or not path or path <= previous or path in seen:
            _fail("retry-2 source paths must be unique and strictly sorted")
        expected = _sha256(row.get("sha256"), label=f"retry-2 source sha256: {path}")
        if hashlib.sha256(_git_bytes(root, revision, path)).hexdigest() != expected:
            _fail(f"retry-2 source drifted: {path}")
        seen.add(path)
        previous = path

    required = {
        "scripts/mesc_mrl_0809_stage4_v2_retry_2_driver.py",
        "src/medscale/mesc/_mrl_0809_stage4_retry_2_gate_v1.py",
    }
    if not required <= seen:
        _fail("retry-2 static manifest omitted a required runtime source")

    return Stage4Retry2AuthorityIdentity(
        authorization_sha256=_AUTHORIZATION_SHA256,
        decision_sha256=_DECISION_SHA256,
        static_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
        bmm_repair_merge_sha=_BMM_REPAIR_MERGE_SHA,
        bmm_repair_merge_tree=_BMM_REPAIR_MERGE_TREE,
    )
