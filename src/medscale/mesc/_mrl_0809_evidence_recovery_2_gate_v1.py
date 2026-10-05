"""Fail-closed authority gate for MRL-0809 successor-v2 evidence recovery 2."""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Never, cast

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_0809_evidence_recovery_1_gate_v1 import (
    MRL0809EvidenceRecovery1GateError,
    validate_evidence_recovery_1_authority,
)

_EXPERIMENT: Final = "specs/mesc-experiment-0"
AUTHORIZATION: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2-evidence-recovery-2-authorization.json"
DECISION: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2/founder-decision-evidence-recovery-2.md"
PREDECESSOR_FAILURE: Final = (
    f"{_EXPERIMENT}/mrl-0809-successor-v2-evidence-recovery-1-failure-record.json"
)
STATIC_MANIFEST: Final = f"{_EXPERIMENT}/mrl-0809-evidence-recovery-2-static-prerequisites-v1.json"

_AUTHORIZATION_SHA256: Final = "d3c1edc0bb212db0717fe14694b80923cd09dea1ba4e4e2dbe5583d74b59d722"
_DECISION_SHA256: Final = "878c98f53600e299b34510d4ca1d4a355dd5ca7ee4104a6eba60aaad56380d5e"
_PREDECESSOR_FAILURE_SHA256: Final = (
    "4bb9e9c5bfd85e7315bc788cad3f92d0ab1e7736ee57d8d620093acfca13a23b"
)
_PREDECESSOR_MERGE_SHA: Final = "f9b7579189b77b06379d1a71d104d4b0267cf500"
_PREDECESSOR_MERGE_TREE: Final = "7bf4cbace9bce891da652a12ec3d7b6b4d9a8b03"
_AUTH_SCHEMA: Final = "MESC-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-2-AUTHORIZATION-V1"
_STATIC_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-2-STATIC-PREREQUISITES-V1"


class MRL0809EvidenceRecovery2GateError(ValueError):
    """Recovery-2 authority is absent, drifted, malformed, or not applicable."""


@dataclass(frozen=True, slots=True)
class EvidenceRecovery2AuthorityIdentity:
    authorization_sha256: str
    decision_sha256: str
    static_manifest_sha256: str
    predecessor_failure_sha256: str
    predecessor_merge_sha: str
    predecessor_merge_tree: str


def _fail(message: str) -> Never:
    raise MRL0809EvidenceRecovery2GateError(message)


def _reject_constant(value: str) -> Never:
    _fail(f"non-standard JSON constant is forbidden: {value}")


def _git_bytes(root: Path, revision: str, path: str) -> bytes:
    try:
        return subprocess.check_output(
            ("git", "-C", str(root), "show", f"{revision}:{path}"),
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809EvidenceRecovery2GateError(f"canonical source is unavailable: {path}") from exc


def _git_text(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ("git", "-C", str(root), *args),
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809EvidenceRecovery2GateError("git identity lookup failed") from exc


def _canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MRL0809EvidenceRecovery2GateError(f"{label} is not valid JSON") from exc
    if type(value) is not dict:
        _fail(f"{label} must be a JSON object")
    document = cast(dict[str, object], value)
    if canonical_json_bytes(document) != raw:
        _fail(f"{label} is not canonical JSON")
    return document


def _json_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MRL0809EvidenceRecovery2GateError(f"{label} is not valid JSON") from exc
    if type(value) is not dict:
        _fail(f"{label} must be a JSON object")
    return cast(dict[str, object], value)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail(f"{label} must be an object")
    return cast(dict[str, object], value)


def _require_ancestor(root: Path, ancestor: str, revision: str) -> None:
    try:
        subprocess.run(
            ("git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, revision),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809EvidenceRecovery2GateError(
            "Recovery-1 canonical outcome is not an ancestor"
        ) from exc


def _validate_predecessor(raw: bytes) -> None:
    document = _json_object(raw, label="Recovery-1 failure record")
    if document.get("disposition") != "FAIL_EVIDENCE_RETENTION_AFTER_RUNTIME_PASS":
        _fail("Recovery-1 disposition drifted")
    authority = _mapping(document.get("authority"), label="Recovery-1 authority")
    if authority.get("launch_authorization_consumed") is not True:
        _fail("Recovery-1 launch is not recorded as consumed")
    retention = _mapping(document.get("evidence_retention"), label="Recovery-1 evidence retention")
    if retention.get("objective_state") != "FAILED":
        _fail("Recovery-1 evidence-retention failure drifted")
    verification = _mapping(
        document.get("independent_verification"),
        label="Recovery-1 independent verification",
    )
    if verification.get("state") != "BLOCKED":
        _fail("Recovery-1 independent-verification state drifted")
    trust = _mapping(document.get("trust_admission"), label="Recovery-1 trust admission")
    if trust != {"eligible": False, "state": "NOT_ADMITTED"}:
        _fail("Recovery-1 trust-admission state drifted")
    non_grants = _mapping(document.get("non_grants"), label="Recovery-1 non-grants")
    if not non_grants or any(value is not False for value in non_grants.values()):
        _fail("Recovery-1 non-grants were weakened")


def _validate_authorization(raw: bytes) -> None:
    document = _canonical_object(raw, label="Recovery-2 authorization")
    if document.get("schema_version") != _AUTH_SCHEMA:
        _fail("Recovery-2 authorization schema drifted")
    if document.get("decision_id") != "FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-2":
        _fail("Recovery-2 decision identity drifted")
    if document.get("activation_precondition") != (
        "ACCEPTED_EVIDENCE_RECOVERY_2_IMPLEMENTATION_CANONICAL_AND_FRESH_MAIN_QUALIFIED"
    ):
        _fail("Recovery-2 effectiveness boundary drifted")
    decision = _mapping(document.get("decision_record"), label="Recovery-2 decision record")
    if decision != {"path": DECISION, "sha256": _DECISION_SHA256}:
        _fail("Recovery-2 decision binding drifted")
    predecessor = _mapping(document.get("predecessor"), label="Recovery-2 predecessor")
    if predecessor != {
        "canonical_outcome_merge_sha": _PREDECESSOR_MERGE_SHA,
        "canonical_outcome_merge_tree": _PREDECESSOR_MERGE_TREE,
        "recovery_1_disposition": "FAIL_EVIDENCE_RETENTION_AFTER_RUNTIME_PASS",
        "recovery_1_failure_record_path": PREDECESSOR_FAILURE,
        "recovery_1_failure_record_sha256": _PREDECESSOR_FAILURE_SHA256,
        "recovery_1_launch_consumed": True,
    }:
        _fail("Recovery-2 predecessor binding drifted")
    grant = _mapping(document.get("grant"), label="Recovery-2 grant")
    if grant != {
        "gpu_class": "STANDARD_T4",
        "input": "SYNTHETIC_ONLY",
        "launches_authorized": 1,
        "monetary_cost_microunits": 0,
        "provider_class": "GOOGLE_COLAB_FREE",
        "purpose": "EVIDENCE_RECOVERY_ONLY",
        "runtime_representation": "bitsandbytes-nf4-v1",
    }:
        _fail("Recovery-2 bounded grant drifted")
    expected_candidates = [
        {
            "model_id": "Qwen/Qwen3-8B",
            "revision": "b968826d9c46dd6066d109eabc6255188de91218",
        },
        {
            "model_id": "google/gemma-4-12B-it",
            "revision": "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
        },
    ]
    if document.get("candidates") != expected_candidates:
        _fail("Recovery-2 candidate roster drifted")
    consumption = _mapping(
        document.get("launch_consumption"), label="Recovery-2 launch consumption"
    )
    if consumption != {
        "automatic_relaunch": False,
        "automatic_retry": False,
        "consumed_on_hosted_launch_invocation": True,
        "local_receipt_required_before_hosted_allocation": True,
        "preflight_failure_exhausts_launch": True,
        "provider_or_session_failure_exhausts_launch": True,
        "remote_receipt_required_before_bmm_sequence": True,
    }:
        _fail("Recovery-2 launch-consumption semantics drifted")
    retention = _mapping(document.get("retention"), label="Recovery-2 retention")
    if retention != {
        "complete_local_evidence_required_for_success": True,
        "driver_exit_requires_host_ack": True,
        "host_continuous_copyout": True,
        "local_byte_hash_verification_required": True,
        "local_fsync_required": True,
        "stdout_recovery_sufficient": False,
        "watcher_required_before_driver": True,
    }:
        _fail("Recovery-2 retention policy drifted")
    non_grants = _mapping(document.get("non_grants"), label="Recovery-2 non-grants")
    if not non_grants or any(value is not False for value in non_grants.values()):
        _fail("Recovery-2 non-grants were weakened")


def validate_evidence_recovery_2_authority(
    root: Path, revision: str
) -> EvidenceRecovery2AuthorityIdentity:
    """Validate immutable Recovery-1 state and accepted Recovery-2 authority."""

    root = root.resolve(strict=True)
    try:
        validate_evidence_recovery_1_authority(root, revision)
    except MRL0809EvidenceRecovery1GateError as exc:
        raise MRL0809EvidenceRecovery2GateError(
            "preserved Recovery-1/Retry-2 authority no longer validates"
        ) from exc

    _require_ancestor(root, _PREDECESSOR_MERGE_SHA, revision)
    if (
        _git_text(root, "show", "-s", "--format=%T", _PREDECESSOR_MERGE_SHA)
        != _PREDECESSOR_MERGE_TREE
    ):
        _fail("Recovery-1 canonical merge tree drifted")

    predecessor_raw = _git_bytes(root, revision, PREDECESSOR_FAILURE)
    if hashlib.sha256(predecessor_raw).hexdigest() != _PREDECESSOR_FAILURE_SHA256:
        _fail("Recovery-1 failure-record bytes drifted")
    _validate_predecessor(predecessor_raw)

    decision_raw = _git_bytes(root, revision, DECISION)
    if hashlib.sha256(decision_raw).hexdigest() != _DECISION_SHA256:
        _fail("accepted Founder Recovery-2 decision bytes drifted")

    authorization_raw = _git_bytes(root, revision, AUTHORIZATION)
    if hashlib.sha256(authorization_raw).hexdigest() != _AUTHORIZATION_SHA256:
        _fail("Recovery-2 authorization bytes drifted")
    _validate_authorization(authorization_raw)

    manifest_raw = _git_bytes(root, revision, STATIC_MANIFEST)
    manifest = _canonical_object(manifest_raw, label="Recovery-2 static manifest")
    if manifest.get("schema_version") != _STATIC_SCHEMA:
        _fail("Recovery-2 static manifest schema drifted")
    if manifest.get("decision_sha256") != _DECISION_SHA256:
        _fail("Recovery-2 static manifest decision binding drifted")
    if manifest.get("authorization_sha256") != _AUTHORIZATION_SHA256:
        _fail("Recovery-2 static manifest authorization binding drifted")
    if manifest.get("predecessor_failure_sha256") != _PREDECESSOR_FAILURE_SHA256:
        _fail("Recovery-2 static manifest predecessor binding drifted")

    sources = manifest.get("sources")
    if type(sources) is not list or not sources:
        _fail("Recovery-2 static sources must be a non-empty array")
    seen: set[str] = set()
    previous = ""
    for item in cast(list[object], sources):
        row = _mapping(item, label="Recovery-2 static source")
        if set(row) != {"path", "sha256"}:
            _fail("Recovery-2 source binding envelope drifted")
        path = row.get("path")
        digest = row.get("sha256")
        if type(path) is not str or not path or path <= previous or path in seen:
            _fail("Recovery-2 source paths must be unique and strictly sorted")
        if type(digest) is not str or len(digest) != 64:
            _fail(f"Recovery-2 source digest is malformed: {path}")
        if hashlib.sha256(_git_bytes(root, revision, path)).hexdigest() != digest:
            _fail(f"Recovery-2 source drifted: {path}")
        seen.add(path)
        previous = path

    required = {
        "scripts/mesc_mrl_0809_evidence_recovery_2_driver.py",
        "scripts/mesc_mrl_0809_evidence_recovery_2_host_controller.py",
        "scripts/mesc_mrl_0809_stage4_v2_bmm_repair_driver.py",
        "src/medscale/mesc/_mrl_0809_evidence_recovery_2_gate_v1.py",
    }
    if not required <= seen:
        _fail("Recovery-2 static manifest omitted a required runtime source")

    return EvidenceRecovery2AuthorityIdentity(
        authorization_sha256=_AUTHORIZATION_SHA256,
        decision_sha256=_DECISION_SHA256,
        static_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
        predecessor_failure_sha256=_PREDECESSOR_FAILURE_SHA256,
        predecessor_merge_sha=_PREDECESSOR_MERGE_SHA,
        predecessor_merge_tree=_PREDECESSOR_MERGE_TREE,
    )
