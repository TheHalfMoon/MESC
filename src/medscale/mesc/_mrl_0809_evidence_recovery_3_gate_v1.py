"""Versioned, fail-closed Recovery-3 engineering authority.

Founder acceptance authorizes implementation only; launch is NOT effective.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Never, cast

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_0809_evidence_recovery_2_gate_v1 import (
    MRL0809EvidenceRecovery2GateError,
    validate_evidence_recovery_2_authority,
)

_PREFIX: Final = "specs/mesc-experiment-0"
AUTHORIZATION: Final = f"{_PREFIX}/mrl-0809-successor-v2-evidence-recovery-3-authorization.json"
PREDECESSOR_FAILURE: Final = (
    f"{_PREFIX}/mrl-0809-successor-v2-evidence-recovery-2-failure-record.json"
)
DECISION: Final = "docs/execution/mrl_0809_evidence_recovery_3_implementation_entry.md"
STATIC_MANIFEST: Final = f"{_PREFIX}/mrl-0809-evidence-recovery-3-static-prerequisites-v1.json"

_AUTHORIZATION_SHA256: Final = "2ce48b1c824881dac0500a8b1051c758ab17ff0119e9db2487da3a758184d1f9"
_DECISION_SHA256: Final = "46fd6c249532af87d651c139865e218543677fd671de0b3c5b00315d13fd94d2"
_PREDECESSOR_FAILURE_SHA256: Final = (
    "af1c2ddb2c5b7b046ce441a6cbe717071fd3962114f280c4deea01fdb62aafba"
)
_PREDECESSOR_MERGE_SHA: Final = "60ec9973694a8b64cc2ae58cd5e5a2e410d91b91"
_PREDECESSOR_MERGE_TREE: Final = "0add794a81ba68aaa61fd2f23da7280baefbf9e7"
_SCHEMA: Final = "MESC-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3-AUTHORIZATION-V1"
_STATIC_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-3-STATIC-PREREQUISITES-V1"


class MRL0809EvidenceRecovery3GateError(ValueError):
    """The implementation authority is absent, mismatched, or not effective."""


@dataclass(frozen=True, slots=True)
class EvidenceRecovery3AuthorityIdentity:
    authorization_sha256: str
    decision_sha256: str
    static_manifest_sha256: str
    predecessor_failure_sha256: str
    predecessor_merge_sha: str
    predecessor_merge_tree: str


def _fail(message: str) -> Never:
    raise MRL0809EvidenceRecovery3GateError(message)


def _git_bytes(root: Path, revision: str, path: str) -> bytes:
    try:
        return subprocess.check_output(
            ("git", "-C", str(root), "show", f"{revision}:{path}"),
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809EvidenceRecovery3GateError(f"canonical source is unavailable: {path}") from exc


def _git_text(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ("git", "-C", str(root), *args),
            text=True,
            encoding="utf-8",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809EvidenceRecovery3GateError("git identity lookup failed") from exc


def _canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MRL0809EvidenceRecovery3GateError(f"{label} is not valid JSON") from exc
    if type(value) is not dict:
        _fail(f"{label} must be a JSON object")
    document = cast(dict[str, object], value)
    if canonical_json_bytes(document) != raw:
        _fail(f"{label} is not canonical JSON")
    return document


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail(f"{label} must be an object")
    return cast(dict[str, object], value)


def _check_ancestor(root: Path, revision: str) -> None:
    try:
        subprocess.run(
            (
                "git",
                "-C",
                str(root),
                "merge-base",
                "--is-ancestor",
                _PREDECESSOR_MERGE_SHA,
                revision,
            ),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809EvidenceRecovery3GateError(
            "Recovery-2 canonical outcome merge is not an ancestor"
        ) from exc
    if (
        _git_text(root, "show", "-s", "--format=%T", _PREDECESSOR_MERGE_SHA)
        != _PREDECESSOR_MERGE_TREE
    ):
        _fail("Recovery-2 canonical outcome merge tree drifted")


def _check_failure(raw: bytes) -> None:
    failure = _canonical_object(raw, label="Recovery-2 failure record")
    if (
        failure.get("schema_version")
        != "MESC-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-2-FAILURE-RECORD-V1"
    ):
        _fail("Recovery-2 failure schema drifted")
    if failure.get("disposition") != "FAIL_HOST_PREFLIGHT_BEFORE_RUNTIME":
        _fail("Recovery-2 failure disposition drifted")
    authority = _mapping(failure.get("authority"), label="predecessor authority")
    if authority.get("launch_authorization_consumed") is not True:
        _fail("Recovery-2 launch is not consumed")
    execution = _mapping(failure.get("execution"), label="predecessor execution")
    if (
        execution.get("allocation_invocations") != 1
        or execution.get("recovery_driver_invocations") != 0
        or execution.get("model_staging_invocations") != 0
        or execution.get("candidate_probe_invocations") != 0
        or execution.get("provider_session_unassigned_observed") is not True
    ):
        _fail("Recovery-2 consumed/pre-runtime outcome drifted")
    billing = _mapping(failure.get("billing_observations"), label="predecessor billing")
    if billing.get("paid_unit_purchase_commands") != 0:
        _fail("Recovery-2 paid-unit purchase observations drifted")
    trust = _mapping(failure.get("trust_admission"), label="predecessor trust")
    if trust != {"eligible": False, "state": "NOT_ADMITTED"}:
        _fail("Recovery-2 research trust was improperly admitted")
    non_grants = _mapping(failure.get("non_grants"), label="predecessor non-grants")
    if not non_grants or any(value is not False for value in non_grants.values()):
        _fail("Recovery-2 non-grants were weakened")


def _check_authorization(raw: bytes) -> None:
    doc = _canonical_object(raw, label="Recovery-3 authorization")
    if doc.get("schema_version") != _SCHEMA or doc.get("decision_id") != (
        "FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-3"
    ):
        _fail("Recovery-3 authorization identity drifted")
    if doc.get("authorization_state") != "IMPLEMENTATION_ONLY_LAUNCH_NOT_EFFECTIVE":
        _fail("Recovery-3 implementation-only boundary drifted")
    if doc.get("founder_acceptance_url") != (
        "https://github.com/TheHalfMoon/MESC/issues/450#issuecomment-6064511682"
    ):
        _fail("Founder acceptance link drifted")
    if doc.get("decision_record") != {"path": DECISION, "sha256": _DECISION_SHA256}:
        _fail("Recovery-3 accepted decision record drifted")
    if doc.get("effectiveness_precondition") != (
        "FOUNDER_FINAL_SHA_APPROVAL_NORMAL_MERGE_FOUR_FRESH_MAIN_CHECKS_CLEAN_LIVE_AUTHORITY_GATE"
    ):
        _fail("Recovery-3 launch-effectiveness boundary drifted")
    if doc.get("predecessor") != {
        "canonical_outcome_merge_sha": _PREDECESSOR_MERGE_SHA,
        "canonical_outcome_merge_tree": _PREDECESSOR_MERGE_TREE,
        "recovery_2_disposition": "FAIL_HOST_PREFLIGHT_BEFORE_RUNTIME",
        "recovery_2_failure_record_path": PREDECESSOR_FAILURE,
        "recovery_2_failure_record_sha256": _PREDECESSOR_FAILURE_SHA256,
        "recovery_2_launch_consumed": True,
    }:
        _fail("Recovery-3 predecessor binding drifted")
    if doc.get("grant") != {
        "gpu_class": "STANDARD_T4",
        "input": "SYNTHETIC_ONLY",
        "launches_authorized": 1,
        "monetary_cost_microunits": 0,
        "provider_class": "GOOGLE_COLAB_FREE",
        "purpose": "EVIDENCE_RECOVERY_ONLY",
        "runtime_representation": "bitsandbytes-nf4-v1",
    }:
        _fail("Recovery-3 bounded grant drifted")
    if doc.get("candidates") != [
        {"model_id": "Qwen/Qwen3-8B", "revision": "b968826d9c46dd6066d109eabc6255188de91218"},
        {
            "model_id": "google/gemma-4-12B-it",
            "revision": "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
        },
    ]:
        _fail("Recovery-3 frozen candidate roster drifted")
    preflight = _mapping(doc.get("preflight"), label="Recovery-3 preflight")
    if preflight != {
        "active_nominal_rate_must_be_zero": False,
        "positive_paid_units_forbidden": True,
        "free_t4_control_plane_required": True,
        "provider_endpoint_redaction_required": True,
        "read_only_before_after_verification": True,
    }:
        _fail("Recovery-3 paid-unit preflight weakened")
    for key in ("launch_consumption", "retention"):
        policy = _mapping(doc.get(key), label=key)
        if not policy or any(type(value) is not bool for value in policy.values()):
            _fail(f"Recovery-3 {key} policy is malformed")
    for key in (
        "automatic_relaunch",
        "automatic_retry",
    ):
        if (
            _mapping(doc.get("launch_consumption"), label="launch consumption").get(key)
            is not False
        ):
            _fail("Recovery-3 automatic relaunch/retry is forbidden")
    non_grants = _mapping(doc.get("non_grants"), label="non-grants")
    if not non_grants or any(value is not False for value in non_grants.values()):
        _fail("Recovery-3 non-grants drifted")


def validate_evidence_recovery_3_authority(
    root: Path, revision: str
) -> EvidenceRecovery3AuthorityIdentity:
    """Validate the accepted *implementation* decision at a real Git commit."""
    root = root.resolve(strict=True)
    try:
        validate_evidence_recovery_2_authority(root, revision)
    except MRL0809EvidenceRecovery2GateError as exc:
        raise MRL0809EvidenceRecovery3GateError(
            "preserved Recovery-2 authority chain failed"
        ) from exc
    _check_ancestor(root, revision)
    predecessor_raw = _git_bytes(root, revision, PREDECESSOR_FAILURE)
    if hashlib.sha256(predecessor_raw).hexdigest() != _PREDECESSOR_FAILURE_SHA256:
        _fail("Recovery-2 canonical failure-record bytes drifted")
    _check_failure(predecessor_raw)
    decision_raw = _git_bytes(root, revision, DECISION)
    if hashlib.sha256(decision_raw).hexdigest() != _DECISION_SHA256:
        _fail("Recovery-3 implementation decision bytes drifted")
    auth_raw = _git_bytes(root, revision, AUTHORIZATION)
    if hashlib.sha256(auth_raw).hexdigest() != _AUTHORIZATION_SHA256:
        _fail("Recovery-3 authorization bytes drifted")
    _check_authorization(auth_raw)
    raw = _git_bytes(root, revision, STATIC_MANIFEST)
    manifest = _canonical_object(raw, label="Recovery-3 source manifest")
    if manifest.get("schema_version") != _STATIC_SCHEMA:
        _fail("Recovery-3 manifest schema drifted")
    for name, expected in (
        ("authorization_sha256", _AUTHORIZATION_SHA256),
        ("decision_sha256", _DECISION_SHA256),
        ("predecessor_failure_sha256", _PREDECESSOR_FAILURE_SHA256),
        ("predecessor_merge_sha", _PREDECESSOR_MERGE_SHA),
        ("predecessor_merge_tree", _PREDECESSOR_MERGE_TREE),
    ):
        if manifest.get(name) != expected:
            _fail(f"Recovery-3 manifest binding drifted: {name}")
    sources = manifest.get("sources")
    if type(sources) is not list or not sources:
        _fail("Recovery-3 static sources are missing")
    previous = ""
    seen: set[str] = set()
    for item in cast(list[object], sources):
        row = _mapping(item, label="Recovery-3 static source")
        if set(row) != {"path", "sha256"}:
            _fail("Recovery-3 source entry drifted")
        path = row.get("path")
        sha = row.get("sha256")
        if type(path) is not str or not path or path <= previous or path in seen:
            _fail("Recovery-3 source paths are not strictly sorted and unique")
        if type(sha) is not str or len(sha) != 64:
            _fail("Recovery-3 source digest is invalid")
        if hashlib.sha256(_git_bytes(root, revision, path)).hexdigest() != sha:
            _fail(f"Recovery-3 source changed: {path}")
        previous = path
        seen.add(path)
    required = {
        "src/medscale/mesc/_mrl_0809_evidence_recovery_3_gate_v1.py",
        "src/medscale/mesc/_mrl_0809_evidence_recovery_3_control_plane_v1.py",
        "scripts/mesc_mrl_0809_evidence_recovery_3_control_plane.py",
        "scripts/mesc_mrl_0809_evidence_recovery_3_driver.py",
        "scripts/mesc_mrl_0809_evidence_recovery_3_host_controller.py",
    }
    if not required <= seen:
        _fail("Recovery-3 essential runtime/preflight sources are not frozen")
    return EvidenceRecovery3AuthorityIdentity(
        authorization_sha256=_AUTHORIZATION_SHA256,
        decision_sha256=_DECISION_SHA256,
        static_manifest_sha256=hashlib.sha256(raw).hexdigest(),
        predecessor_failure_sha256=_PREDECESSOR_FAILURE_SHA256,
        predecessor_merge_sha=_PREDECESSOR_MERGE_SHA,
        predecessor_merge_tree=_PREDECESSOR_MERGE_TREE,
    )


def require_recovery_3_launch_effectiveness(root: Path, revision: str) -> None:
    """Reject all launch attempts until a separately approved final-head grant exists.

    This implementation-only change deliberately cannot arm itself.
    A successor authorized by the Founder must add a separate effective
    admission artifact, implement independent fresh-main workflow checks,
    and then explicitly replace this fail-closed function.
    """
    validate_evidence_recovery_3_authority(root, revision)
    _fail("Recovery-3 launch NOT_EFFECTIVE: missing final-head approval and main qualification")
