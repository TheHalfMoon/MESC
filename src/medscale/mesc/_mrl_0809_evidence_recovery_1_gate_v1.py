"""Fail-closed authority gate for MRL-0809 successor-v2 evidence recovery 1."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Never, cast

from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes
from medscale.mesc._mrl_0809_stage4_retry_2_gate_v1 import (
    MRL0809Stage4Retry2GateError,
    validate_stage4_retry_2_authority,
)

_EXPERIMENT: Final = "specs/mesc-experiment-0"
AUTHORIZATION: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2-evidence-recovery-1-authorization.json"
DECISION: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2/founder-decision-evidence-recovery-1.md"
PREDECESSOR_RESULT: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2-stage4-retry-2-result.json"
STATIC_MANIFEST: Final = f"{_EXPERIMENT}/mrl-0809-evidence-recovery-1-static-prerequisites-v1.json"

_AUTHORIZATION_SHA256: Final = "2d785a51faeec8fd4fb66890196ed7becd16b44190121228653802e2ae6d9327"
_DECISION_SHA256: Final = "d4a8c8deef9a014e6d39a56800f55337e130ae0d517eed1d2316300db7979e43"
_PREDECESSOR_RESULT_SHA256: Final = (
    "2346c595176a5cbeaff40897a4be64e0ebdad0e40c58438bb6f6a4d98304fda3"
)
_PREDECESSOR_MERGE_SHA: Final = "1a634525e95ae1bb6a9fa01745ecd63c2d82684a"
_PREDECESSOR_MERGE_TREE: Final = "8c60c1ea30757fd743de8bee462e5f81c292ecb1"
_AUTH_SCHEMA: Final = "MESC-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-1-AUTHORIZATION-V1"
_STATIC_SCHEMA: Final = "MESC-MRL-0809-EVIDENCE-RECOVERY-1-STATIC-PREREQUISITES-V1"
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)


class MRL0809EvidenceRecovery1GateError(ValueError):
    """Evidence-recovery authority is absent, drifted, malformed, or not applicable."""


@dataclass(frozen=True, slots=True)
class EvidenceRecovery1AuthorityIdentity:
    authorization_sha256: str
    decision_sha256: str
    static_manifest_sha256: str
    predecessor_result_sha256: str
    predecessor_merge_sha: str
    predecessor_merge_tree: str


def _fail(message: str) -> Never:
    raise MRL0809EvidenceRecovery1GateError(message)


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
    except MRL0809EvidenceRecovery1GateError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        CanonicalContractError,
    ) as exc:
        raise MRL0809EvidenceRecovery1GateError(f"{label} is invalid canonical JSON") from exc
    if canonical != raw:
        _fail(f"{label} is not canonical JSON")
    return document


def _git_bytes(root: Path, revision: str, path: str) -> bytes:
    if _SHA40.fullmatch(revision) is None:
        _fail("evidence-recovery revision SHA is malformed")
    try:
        return subprocess.run(
            ("git", "show", f"{revision}:{path}"),
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809EvidenceRecovery1GateError(
            f"evidence-recovery source missing: {path}"
        ) from exc


def _git_text(root: Path, *args: str) -> str:
    try:
        return subprocess.run(
            ("git", *args),
            cwd=root,
            check=True,
            text=True,
            encoding="utf-8",
            capture_output=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809EvidenceRecovery1GateError(
            f"git evidence-recovery authority check failed: {' '.join(args)}"
        ) from exc


def _require_ancestor(root: Path, ancestor: str, revision: str) -> None:
    completed = subprocess.run(
        ("git", "merge-base", "--is-ancestor", ancestor, revision),
        cwd=root,
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        _fail("runtime revision does not descend from the canonical Retry-2 outcome merge")


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail(f"{label} must be an object")
    return cast(dict[str, object], value)


def _sha256(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be 64 lowercase hex")
    return value


def _validate_predecessor(raw: bytes) -> None:
    document = _canonical_object(raw, label="Retry-2 outcome record")
    if document.get("schema_version") != "MESC-MRL-0809-SUCCESSOR-V2-STAGE4-RETRY-2-RESULT-V1":
        _fail("Retry-2 outcome schema drifted")
    if document.get("disposition") != "PASS_RUNTIME_SEQUENCE_UNADMITTED":
        _fail("Retry-2 governed disposition drifted")
    authority = _mapping(document.get("authority"), label="Retry-2 outcome authority")
    if authority.get("launch_authorization_consumed") is not True:
        _fail("Retry-2 launch consumption was weakened")
    if authority.get("automatic_retry_authorized") is not False:
        _fail("Retry-2 automatic retry prohibition was weakened")
    if authority.get("automatic_relaunch_authorized") is not False:
        _fail("Retry-2 automatic relaunch prohibition was weakened")
    independent = _mapping(
        document.get("independent_verification"), label="independent verification"
    )
    if independent != {
        "reason": "FULL_GEMMA_OBSERVATION_AND_ASSEMBLED_RECEIPT_BYTES_UNAVAILABLE",
        "state": "BLOCKED",
    }:
        _fail("Retry-2 evidence-retention blocker drifted")
    trust = _mapping(document.get("trust_admission"), label="trust admission")
    if trust != {"eligible": False, "state": "NOT_ADMITTED"}:
        _fail("Retry-2 trust-admission state drifted")
    non_grants = _mapping(document.get("non_grants"), label="Retry-2 non-grants")
    if not non_grants or any(value is not False for value in non_grants.values()):
        _fail("Retry-2 non-grants were weakened")


def _validate_authorization(raw: bytes) -> None:
    document = _canonical_object(raw, label="evidence-recovery authorization")
    if document.get("schema_version") != _AUTH_SCHEMA:
        _fail("evidence-recovery authorization schema drifted")
    if document.get("decision_id") != "FD-MRL-0809-SUCCESSOR-V2-EVIDENCE-RECOVERY-1":
        _fail("evidence-recovery decision identity drifted")
    if document.get("activation_precondition") != (
        "ACCEPTED_EVIDENCE_RECOVERY_1_IMPLEMENTATION_CANONICAL_AND_FRESH_MAIN_QUALIFIED"
    ):
        _fail("evidence-recovery effectiveness boundary drifted")
    decision = _mapping(document.get("decision_record"), label="decision record")
    if decision != {"path": DECISION, "sha256": _DECISION_SHA256}:
        _fail("evidence-recovery decision binding drifted")
    predecessor = _mapping(document.get("predecessor"), label="predecessor binding")
    if predecessor != {
        "canonical_outcome_merge_sha": _PREDECESSOR_MERGE_SHA,
        "canonical_outcome_merge_tree": _PREDECESSOR_MERGE_TREE,
        "retry_2_disposition": "PASS_RUNTIME_SEQUENCE_UNADMITTED",
        "retry_2_launch_consumed": True,
        "retry_2_outcome_record_path": PREDECESSOR_RESULT,
        "retry_2_outcome_record_sha256": _PREDECESSOR_RESULT_SHA256,
    }:
        _fail("evidence-recovery predecessor binding drifted")
    grant = _mapping(document.get("grant"), label="evidence-recovery grant")
    if grant != {
        "gpu_class": "STANDARD_T4",
        "input": "SYNTHETIC_ONLY",
        "launches_authorized": 1,
        "monetary_cost_microunits": 0,
        "provider_class": "GOOGLE_COLAB_FREE",
        "purpose": "EVIDENCE_RECOVERY_ONLY",
        "runtime_representation": "bitsandbytes-nf4-v1",
    }:
        _fail("evidence-recovery bounded grant drifted")
    if document.get("candidates") != [
        {"model_id": "Qwen/Qwen3-8B", "revision": "b968826d9c46dd6066d109eabc6255188de91218"},
        {
            "model_id": "google/gemma-4-12B-it",
            "revision": "707f0a3b8a3c7ad586ed01e27eafbad8a27dd0f7",
        },
    ]:
        _fail("evidence-recovery candidate roster drifted")
    consumption = _mapping(document.get("launch_consumption"), label="launch consumption")
    if consumption != {
        "automatic_relaunch": False,
        "automatic_retry": False,
        "consumed_on_hosted_launch_invocation": True,
        "preflight_failure_exhausts_launch": True,
        "provider_or_session_failure_exhausts_launch": True,
        "receipt_required_before_bmm_sequence": True,
    }:
        _fail("evidence-recovery launch-consumption semantics drifted")
    retention = _mapping(document.get("retention"), label="retention policy")
    if retention != {
        "bundle_emit_stdout": True,
        "bundle_required_before_success": True,
        "bundle_schema": "MESC-MRL-0809-EVIDENCE-RECOVERY-BUNDLE-V1",
        "full_bytes_required": True,
    }:
        _fail("evidence-recovery retention policy drifted")
    non_grants = _mapping(document.get("non_grants"), label="evidence-recovery non-grants")
    if not non_grants or any(value is not False for value in non_grants.values()):
        _fail("evidence-recovery non-grants were weakened")


def validate_evidence_recovery_1_authority(
    root: Path, revision: str
) -> EvidenceRecovery1AuthorityIdentity:
    """Validate predecessor preservation and the accepted evidence-recovery authority."""

    root = root.resolve(strict=True)
    try:
        validate_stage4_retry_2_authority(root, revision)
    except MRL0809Stage4Retry2GateError as exc:
        raise MRL0809EvidenceRecovery1GateError(
            "preserved Retry-2/BMM contract no longer validates"
        ) from exc

    _require_ancestor(root, _PREDECESSOR_MERGE_SHA, revision)
    if (
        _git_text(root, "show", "-s", "--format=%T", _PREDECESSOR_MERGE_SHA)
        != _PREDECESSOR_MERGE_TREE
    ):
        _fail("canonical Retry-2 outcome merge tree drifted")

    predecessor_raw = _git_bytes(root, revision, PREDECESSOR_RESULT)
    if hashlib.sha256(predecessor_raw).hexdigest() != _PREDECESSOR_RESULT_SHA256:
        _fail("canonical Retry-2 outcome record bytes drifted")
    _validate_predecessor(predecessor_raw)

    decision_raw = _git_bytes(root, revision, DECISION)
    if hashlib.sha256(decision_raw).hexdigest() != _DECISION_SHA256:
        _fail("accepted Founder evidence-recovery decision bytes drifted")

    authorization_raw = _git_bytes(root, revision, AUTHORIZATION)
    if hashlib.sha256(authorization_raw).hexdigest() != _AUTHORIZATION_SHA256:
        _fail("evidence-recovery authorization bytes drifted")
    _validate_authorization(authorization_raw)

    manifest_raw = _git_bytes(root, revision, STATIC_MANIFEST)
    manifest = _canonical_object(manifest_raw, label="evidence-recovery static manifest")
    if manifest.get("schema_version") != _STATIC_SCHEMA:
        _fail("evidence-recovery static manifest schema drifted")
    if manifest.get("decision_sha256") != _DECISION_SHA256:
        _fail("evidence-recovery static manifest decision binding drifted")
    if manifest.get("authorization_sha256") != _AUTHORIZATION_SHA256:
        _fail("evidence-recovery static manifest authorization binding drifted")
    if manifest.get("predecessor_result_sha256") != _PREDECESSOR_RESULT_SHA256:
        _fail("evidence-recovery static manifest predecessor binding drifted")

    sources = manifest.get("sources")
    if type(sources) is not list or not sources:
        _fail("evidence-recovery static sources must be a non-empty array")
    seen: set[str] = set()
    previous = ""
    for item in cast(list[object], sources):
        row = _mapping(item, label="evidence-recovery static source")
        if set(row) != {"path", "sha256"}:
            _fail("evidence-recovery source binding envelope drifted")
        path = row.get("path")
        if type(path) is not str or not path or path <= previous or path in seen:
            _fail("evidence-recovery source paths must be unique and strictly sorted")
        expected = _sha256(row.get("sha256"), label=f"source sha256: {path}")
        if hashlib.sha256(_git_bytes(root, revision, path)).hexdigest() != expected:
            _fail(f"evidence-recovery source drifted: {path}")
        seen.add(path)
        previous = path

    required = {
        "scripts/mesc_mrl_0809_evidence_recovery_1_driver.py",
        "scripts/mesc_mrl_0809_stage4_v2_bmm_repair_driver.py",
        "src/medscale/mesc/_mrl_0809_evidence_recovery_1_gate_v1.py",
    }
    if not required <= seen:
        _fail("evidence-recovery static manifest omitted a required runtime source")

    return EvidenceRecovery1AuthorityIdentity(
        authorization_sha256=_AUTHORIZATION_SHA256,
        decision_sha256=_DECISION_SHA256,
        static_manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
        predecessor_result_sha256=_PREDECESSOR_RESULT_SHA256,
        predecessor_merge_sha=_PREDECESSOR_MERGE_SHA,
        predecessor_merge_tree=_PREDECESSOR_MERGE_TREE,
    )
