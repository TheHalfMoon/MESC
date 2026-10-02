"""Fail-closed authority gate for the single MRL-0809 Stage-4 retry."""

from __future__ import annotations

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Never

from medscale.mesc._mrl_0809_successor_gate_v2_repair_1 import (
    MRL0809RepairGateError,
    validate_repair_static_prerequisites,
)

_EXPERIMENT: Final = "specs/mesc-experiment-0"
AUTHORIZATION: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2-stage4-retry-authorization.json"
DECISION: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2/founder-decision-stage4-retry.md"

_AUTHORIZATION_SHA256: Final = "e0d4361b36fa9a78a02da2d8582f395897fec8ed1104438c943c50d1328e03d5"
_DECISION_SHA256: Final = "0f9746a510c35b4a249ec1b832c7a4222abe27f2c4304bc360822e76d965fa75"
_REPAIR_MERGE_SHA: Final = "66c8d33eb48433f50b9e313ede804cf5fb31271a"
_REPAIR_MERGE_TREE: Final = "8d6a818294f763c7e49ba0acfa172848f44607ee"
_REPAIR_MANIFEST_SHA256: Final = "d943a8bc4fbc7f5c8baf8716dd206b6262966c43c37a7a257645518a620f2c7d"
_DEPENDENCY_LOCK_SHA256: Final = "6fa0e0b49d19e305032ecd04940db0b9e252dd23b6fbec588b224f739048efc4"
_PRESERVED_V2_MANIFEST_SHA256: Final = "56de494cf30b6d3dd3aa005e63d55ea7490f7645dd37cbb388188d635813a36d"


class MRL0809Stage4RetryGateError(ValueError):
    """The accepted Stage-4 retry authority is absent, drifted, or inapplicable."""


@dataclass(frozen=True, slots=True)
class Stage4RetryAuthorityIdentity:
    authorization_sha256: str
    decision_sha256: str
    repair_merge_sha: str
    repair_merge_tree: str


def _fail(message: str) -> Never:
    raise MRL0809Stage4RetryGateError(message)


def _git_bytes(root: Path, revision: str, path: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), "show", f"{revision}:{path}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        _fail(f"required retry-authority path is unavailable: {path}")
    return completed.stdout


def _git_text(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        check=False,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        _fail(f"git authority check failed: {' '.join(args)}")
    return completed.stdout.strip()


def _require_ancestor(root: Path, ancestor: str, revision: str) -> None:
    completed = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", ancestor, revision],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        _fail("runtime revision does not descend from the canonical repair merge")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def validate_stage4_retry_authority(
    root: Path,
    revision: str,
) -> Stage4RetryAuthorityIdentity:
    """Validate the accepted single-attempt authority against one repository revision."""

    root = root.resolve(strict=True)
    try:
        repair = validate_repair_static_prerequisites(root, revision)
    except MRL0809RepairGateError as exc:
        raise MRL0809Stage4RetryGateError(
            "preserved repair prerequisites no longer validate"
        ) from exc

    if repair.manifest_sha256 != _REPAIR_MANIFEST_SHA256:
        _fail("repair static manifest identity drifted from Founder binding")
    if repair.dependency_lock_sha256 != _DEPENDENCY_LOCK_SHA256:
        _fail("dependency lock identity drifted from Founder binding")
    if repair.preserved_v2_manifest_sha256 != _PRESERVED_V2_MANIFEST_SHA256:
        _fail("preserved successor-v2 manifest identity drifted from Founder binding")

    _require_ancestor(root, _REPAIR_MERGE_SHA, revision)
    tree = _git_text(root, "show", "-s", "--format=%T", _REPAIR_MERGE_SHA)
    if tree != _REPAIR_MERGE_TREE:
        _fail("canonical repair merge tree does not match Founder binding")

    decision_raw = _git_bytes(root, revision, DECISION)
    decision_sha = _sha256(decision_raw)
    if decision_sha != _DECISION_SHA256:
        _fail("accepted Founder retry decision bytes drifted")

    authorization_raw = _git_bytes(root, revision, AUTHORIZATION)
    authorization_sha = _sha256(authorization_raw)
    if authorization_sha != _AUTHORIZATION_SHA256:
        _fail("machine-readable retry authorization bytes drifted")

    required_fragments = (
        b'"attempts_authorized":1',
        b'"provider_class":"GOOGLE_COLAB_FREE"',
        b'"gpu_class":"STANDARD_T4"',
        b'"monetary_cost_microunits":0',
        b'"prior_consumed_v2_attempt":"FAIL"',
        b'"overwrite_or_relabel_allowed":false',
        b'"scientific_rq1_execution":false',
        b'"paid_compute":false',
        b'"cpu_offload":false',
        b'"disk_offload":false',
    )
    if any(fragment not in authorization_raw for fragment in required_fragments):
        _fail("retry authorization no longer expresses the accepted bounded grant")

    return Stage4RetryAuthorityIdentity(
        authorization_sha256=authorization_sha,
        decision_sha256=decision_sha,
        repair_merge_sha=_REPAIR_MERGE_SHA,
        repair_merge_tree=_REPAIR_MERGE_TREE,
    )
