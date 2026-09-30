"""Fail-closed MRL-0809 successor (v2) static/runtime prerequisite gate.

The successor gate never replaces the v1 gate. It returns True only when all of these hold
at one exact Git commit:
- the v1 contract is still intact: the v1 static prerequisites validate, and every v1 file
  bound by the v1 infeasibility record is byte-identical, including the ABSENT v1 slot and
  the empty v1 trust root;
- the Founder successor authorization, the v2 roster and the v1 infeasibility record match
  their frozen digests;
- the v2 MRL-0806 authorization and RQ1 protocol differ from v1 only in the declared
  candidate-binding fields;
- the v2 static prerequisite manifest validates;
- a separately trusted v2 runtime-feasibility PASS exists, produced at an ancestor commit.
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
from medscale.mesc._mrl_0809_prerequisite_gate_v1 import (
    MRL0809PrerequisiteGateError,
    validate_static_prerequisites,
)
from medscale.mesc._mrl_0809_runtime_feasibility_v2 import (
    CANDIDATE_ROSTER_SHA256,
    EXPECTED_CANDIDATES,
    SUCCESSOR_AUTHORIZATION_SHA256,
    V1_INFEASIBILITY_RECORD_SHA256,
    MRL0809SuccessorRuntimeFeasibilityError,
    validate_successor_runtime_feasibility_receipt,
)

_EXPERIMENT: Final = "specs/mesc-experiment-0"
STATIC_MANIFEST: Final = f"{_EXPERIMENT}/mrl-0809-static-prerequisites-v2.json"
TRUST: Final = f"{_EXPERIMENT}/mrl-0809-runtime-feasibility-trust-v2.json"
SLOT: Final = f"{_EXPERIMENT}/mrl-0809-runtime-feasibility-slot-v2.json"
AUTHORIZATION: Final = f"{_EXPERIMENT}/mrl-0809-successor-v2-authorization.json"
ROSTER: Final = f"{_EXPERIMENT}/candidate-roster-v2.json"
V1_RECORD: Final = f"{_EXPERIMENT}/mrl-0809-v1-infeasibility-record.json"
OBJECTIVE_V1: Final = f"{_EXPERIMENT}/mrl-0806-objective-budgets-authorization-v1.json"
OBJECTIVE_V2: Final = f"{_EXPERIMENT}/mrl-0806-objective-budgets-authorization-v2.json"
PROTOCOL_V1: Final = f"{_EXPERIMENT}/mrl-0806-rq1-protocol-v1.json"
PROTOCOL_V2: Final = f"{_EXPERIMENT}/mrl-0806-rq1-protocol-v2.json"
V1_STATIC_MANIFEST: Final = f"{_EXPERIMENT}/mrl-0809-static-prerequisites-v1.json"

_STATIC_SCHEMA: Final = "MESC-MRL-0809-STATIC-PREREQUISITES-V2"
_TRUST_SCHEMA: Final = "MESC-MRL-0809-RUNTIME-FEASIBILITY-TRUST-V2"
_SLOT_SCHEMA: Final = "MESC-MRL-0809-RUNTIME-FEASIBILITY-SLOT-V2"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_V1_SLOT_ABSENT: Final = {
    "schema_version": "MESC-MRL-0809-RUNTIME-FEASIBILITY-SLOT-V1",
    "state": "ABSENT",
    "task_id": "MRL-0809",
}
_V1_TRUST_EMPTY: Final = {
    "schema_version": "MESC-MRL-0809-RUNTIME-FEASIBILITY-TRUST-V1",
    "trusted_receipt_sha256": [],
}
_OBJECTIVE_CHANGED_FROZEN: Final = frozenset({"candidate_roster_sha256", "rq1_protocol_sha256"})
_ROSTER_BOUND_EVIDENCE: Final = frozenset({"MRL-0801", "MRL-0805"})
_PROTOCOL_CHANGED: Final = frozenset(
    {"candidate_roster_sha256", "candidates", "preflight_evidence_sha256"}
)
_BINDING_PATHS: Final[dict[str, str]] = {
    "candidate_roster": ROSTER,
    "mrl_0806_objective_budgets_authorization_v2": OBJECTIVE_V2,
    "mrl_0806_rq1_protocol_v2": PROTOCOL_V2,
    "successor_authorization": AUTHORIZATION,
    "v1_infeasibility_record": V1_RECORD,
    "v1_static_prerequisite_manifest": V1_STATIC_MANIFEST,
}


class MRL0809SuccessorGateError(ValueError):
    """Canonical MRL-0809 successor material is malformed, drifted, or weakens v1."""


@dataclass(frozen=True, slots=True)
class SuccessorStaticIdentity:
    """Validated successor static-prerequisite identity at one exact Git commit."""

    manifest_sha256: str
    dependency_lock_sha256: str


def _fail(message: str) -> Never:
    raise MRL0809SuccessorGateError(message)


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
            raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant
        )
        if type(value) is not dict:
            _fail(f"{label} must be a JSON object")
        document = cast(dict[str, object], value)
        canonical = canonical_json_bytes(document)
    except MRL0809SuccessorGateError:
        raise
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        RecursionError,
        CanonicalContractError,
    ) as exc:
        raise MRL0809SuccessorGateError(f"{label} is invalid canonical JSON") from exc
    if canonical != raw:
        _fail(f"{label} is not canonical JSON")
    return document


def _git_bytes(root: Path, revision: str, path: str) -> bytes:
    if _SHA40.fullmatch(revision) is None:
        _fail("decision-base SHA is malformed")
    try:
        completed = subprocess.run(
            ("git", "show", f"{revision}:{path}"), cwd=root, check=True, capture_output=True
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MRL0809SuccessorGateError(f"canonical successor source missing: {path}") from exc
    return completed.stdout


def _document(root: Path, revision: str, path: str) -> tuple[bytes, dict[str, object]]:
    raw = _git_bytes(root, revision, path)
    return raw, _canonical_object(raw, label=path)


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be 64 lowercase hex")
    return value


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not dict:
        _fail(f"{label} must be an object")
    return cast(dict[str, object], value)


def _validate_v1_preserved(root: Path, revision: str) -> None:
    raw, record = _document(root, revision, V1_RECORD)
    if hashlib.sha256(raw).hexdigest() != V1_INFEASIBILITY_RECORD_SHA256:
        _fail("v1 infeasibility record drifted")
    if (
        record.get("v1_disposition") != "INFEASIBLE_ON_FROZEN_STANDARD_T4_CONTRACT"
        or record.get("pass_claimed") is not False
        or record.get("gemma_tested") is not False
        or record.get("retry_authorized") is not False
    ):
        _fail("v1 infeasibility record no longer records the frozen negative result")
    preserved = _mapping(
        record.get("v1_contract_preserved_at_successor_base"), label="v1 preserved contract"
    )
    if not preserved:
        _fail("v1 preserved contract is empty")
    for key, value in sorted(preserved.items()):
        binding = _mapping(value, label=f"v1 preserved binding {key}")
        path = binding.get("path")
        if type(path) is not str or set(binding) != {"path", "sha256"}:
            _fail(f"v1 preserved binding {key} is malformed")
        expected = _sha(binding["sha256"], label=f"v1 preserved sha {key}")
        if hashlib.sha256(_git_bytes(root, revision, path)).hexdigest() != expected:
            _fail(f"v1 artifact was modified: {path}")
    slot = _canonical_object(
        _git_bytes(root, revision, f"{_EXPERIMENT}/mrl-0809-runtime-feasibility-slot-v1.json"),
        label="v1 slot",
    )
    trust = _canonical_object(
        _git_bytes(root, revision, f"{_EXPERIMENT}/mrl-0809-runtime-feasibility-trust-v1.json"),
        label="v1 trust root",
    )
    if slot != _V1_SLOT_ABSENT or trust != _V1_TRUST_EMPTY:
        _fail("v1 runtime-feasibility slot or trust root no longer preserves the v1 result")
    try:
        validate_static_prerequisites(root, revision)
    except MRL0809PrerequisiteGateError as exc:
        raise MRL0809SuccessorGateError("v1 static prerequisites no longer validate") from exc


def _validate_authorization(root: Path, revision: str) -> None:
    raw, document = _document(root, revision, AUTHORIZATION)
    if hashlib.sha256(raw).hexdigest() != SUCCESSOR_AUTHORIZATION_SHA256:
        _fail("successor authorization drifted")
    source = _mapping(document.get("authority_source"), label="authority_source")
    record_path = source.get("decision_record_path")
    if type(record_path) is not str:
        _fail("successor authorization decision record path is missing")
    record_sha = hashlib.sha256(_git_bytes(root, revision, record_path)).hexdigest()
    if record_sha != source.get("decision_record_sha256"):
        _fail("Founder decision record drifted from the successor authorization")
    non_grants = _mapping(document.get("non_grants"), label="non_grants")
    if not non_grants or any(value is not False for value in non_grants.values()):
        _fail("successor authorization non-grants were weakened")
    stage4 = _mapping(document.get("stage4"), label="stage4")
    if stage4.get("attempts_authorized") != 1 or stage4.get("input") != "SYNTHETIC_ONLY":
        _fail("successor Stage-4 attempt bound drifted")
    runtime = _mapping(document.get("runtime"), label="runtime")
    if (
        runtime.get("monetary_cost_microunits") != 0
        or runtime.get("isolated_load_network") is not False
        or runtime.get("isolated_generation_network") is not False
        or runtime.get("gpu_class") != "STANDARD_T4"
        or runtime.get("credentials") != "NONE"
    ):
        _fail("successor runtime policy drifted")
    policy = _mapping(document.get("candidate_policy"), label="candidate_policy")
    for key in (
        "automatic_device_map_allowed",
        "cpu_offload_allowed",
        "disk_offload_allowed",
        "gated_credentials_allowed",
        "remote_code_allowed",
    ):
        if policy.get(key) is not False:
            _fail(f"successor candidate policy weakened: {key}")
    roster = _mapping(document.get("candidate_roster"), label="candidate_roster binding")
    v1 = _mapping(document.get("v1"), label="v1 binding")
    record = _mapping(v1.get("infeasibility_record"), label="v1 infeasibility binding")
    if (
        roster.get("sha256") != CANDIDATE_ROSTER_SHA256
        or record.get("sha256") != V1_INFEASIBILITY_RECORD_SHA256
        or v1.get("retry_authorized") is not False
    ):
        _fail("successor authorization bindings drifted")


def _validate_roster(root: Path, revision: str) -> None:
    raw, roster = _document(root, revision, ROSTER)
    if hashlib.sha256(raw).hexdigest() != CANDIDATE_ROSTER_SHA256:
        _fail("successor candidate roster drifted")
    strategy = _mapping(roster.get("flagship_strategy"), label="flagship_strategy")
    if (
        strategy.get("state") != "UNCHANGED"
        or strategy.get("preferred_foundation_candidate") != "Qwen/Qwen3.8-27B"
    ):
        _fail("successor roster weakens the unchanged flagship strategy")
    rows = roster.get("active_candidates")
    if type(rows) is not list or roster.get("candidate_count") != 2 or len(rows) != 2:
        _fail("successor roster must freeze exactly two candidates")
    seen: list[str] = []
    for item in cast(list[object], rows):
        row = _mapping(item, label="roster candidate")
        model_id = row.get("candidate_id")
        expected = EXPECTED_CANDIDATES.get(model_id) if type(model_id) is str else None
        if expected is None:
            _fail("roster candidate is outside the validator identity table")
        pairs = {
            "architecture": "architecture",
            "artifact_identity_sha256": "artifact_identity_sha256",
            "candidate_revision": "revision",
            "config_sha256": "config_sha256",
            "processor_config_sha256": "processor_config_sha256",
            "processor_policy": "processor_policy",
            "prompt_token_ids_sha256": "prompt_token_ids_sha256",
            "text_vocab_size": "text_vocab_size",
            "tokenizer_config_sha256": "tokenizer_config_sha256",
            "weights_sha256": "weights_sha256",
        }
        for roster_key, expected_key in pairs.items():
            if row.get(roster_key) != expected[expected_key]:
                _fail(f"roster {roster_key} disagrees with the validator for {model_id}")
        if row.get("trust_remote_code") is not False or row.get("gated") is not False:
            _fail("roster candidate requires remote code or gated access")
        seen.append(cast(str, model_id))
    if tuple(seen) != tuple(sorted(EXPECTED_CANDIDATES)):
        _fail("roster candidates must be exact and sorted")


def _validate_objective_and_protocol(root: Path, revision: str) -> None:
    v1_raw, v1 = _document(root, revision, OBJECTIVE_V1)
    _, v2 = _document(root, revision, OBJECTIVE_V2)
    p1_raw, p1 = _document(root, revision, PROTOCOL_V1)
    p2_raw, p2 = _document(root, revision, PROTOCOL_V2)
    predecessor = _mapping(v2.get("predecessor_authorization"), label="predecessor_authorization")
    if predecessor.get("sha256") != hashlib.sha256(v1_raw).hexdigest():
        _fail("v2 MRL-0806 authorization does not bind the preserved v1 authorization")
    source = _mapping(v2.get("authority_source"), label="v2 authority_source")
    if source.get("successor_authorization_sha256") != SUCCESSOR_AUTHORIZATION_SHA256:
        _fail("v2 MRL-0806 authorization does not bind the successor authorization")
    for key in ("candidate_id", "experiment_id", "policy", "research_question"):
        if v2.get(key) != v1.get(key):
            _fail(f"v2 MRL-0806 authorization changed carried-forward field: {key}")
    frozen_v1 = _mapping(v1.get("frozen_artifacts"), label="v1 frozen_artifacts")
    frozen_v2 = _mapping(v2.get("frozen_artifacts"), label="v2 frozen_artifacts")
    if set(frozen_v1) != set(frozen_v2):
        _fail("v2 MRL-0806 frozen artifact set drifted")
    for key, value in frozen_v1.items():
        if key not in _OBJECTIVE_CHANGED_FROZEN and frozen_v2[key] != value:
            _fail(f"v2 MRL-0806 changed the scientific artifact: {key}")
    if frozen_v2["candidate_roster_sha256"] != CANDIDATE_ROSTER_SHA256:
        _fail("v2 MRL-0806 does not bind the successor roster")
    if frozen_v2["rq1_protocol_sha256"] != hashlib.sha256(p2_raw).hexdigest():
        _fail("v2 MRL-0806 does not bind the v2 RQ1 protocol")
    if frozen_v1["rq1_protocol_sha256"] != hashlib.sha256(p1_raw).hexdigest():
        _fail("v1 RQ1 protocol drifted from the preserved v1 authorization")
    evidence_v1 = _mapping(v1.get("predecessor_evidence"), label="v1 predecessor_evidence")
    evidence_v2 = _mapping(v2.get("predecessor_evidence"), label="v2 predecessor_evidence")
    if set(evidence_v1) != set(evidence_v2):
        _fail("v2 MRL-0806 predecessor evidence set drifted")
    for key, value in evidence_v1.items():
        expected_value = None if key in _ROSTER_BOUND_EVIDENCE else value
        if evidence_v2[key] != expected_value:
            _fail(f"v2 MRL-0806 predecessor evidence drifted: {key}")
    if set(p1) != set(p2):
        _fail("v2 RQ1 protocol key set drifted")
    for key, value in p1.items():
        if key not in _PROTOCOL_CHANGED and p2[key] != value:
            _fail(f"v2 RQ1 protocol changed a scientific field: {key}")
    if p2["candidate_roster_sha256"] != CANDIDATE_ROSTER_SHA256:
        _fail("v2 RQ1 protocol does not bind the successor roster")
    protocol_rows = p2["candidates"]
    if type(protocol_rows) is not list:
        _fail("v2 RQ1 protocol candidates must be an array")
    protocol_ids = [
        _mapping(row, label="protocol candidate").get("model_id")
        for row in cast(list[object], protocol_rows)
    ]
    if protocol_ids != sorted(EXPECTED_CANDIDATES):
        _fail("v2 RQ1 protocol candidates disagree with the successor roster")
    p1_evidence = _mapping(p1["preflight_evidence_sha256"], label="v1 protocol evidence")
    p2_evidence = _mapping(p2["preflight_evidence_sha256"], label="v2 protocol evidence")
    if set(p1_evidence) != set(p2_evidence):
        _fail("v2 RQ1 protocol preflight evidence set drifted")
    for key, value in p1_evidence.items():
        expected_value = None if key in _ROSTER_BOUND_EVIDENCE else value
        if p2_evidence[key] != expected_value:
            _fail(f"v2 RQ1 protocol preflight evidence drifted: {key}")


def validate_successor_static_prerequisites(
    root: Path, decision_base: str
) -> SuccessorStaticIdentity:
    """Rebuild the successor static identity; v1 preservation is a precondition."""
    _validate_v1_preserved(root, decision_base)
    _validate_authorization(root, decision_base)
    _validate_roster(root, decision_base)
    _validate_objective_and_protocol(root, decision_base)
    raw, document = _document(root, decision_base, STATIC_MANIFEST)
    if set(document) != {
        "dependency_lock_sha256",
        "schema_version",
        "sources",
        "successor_bindings",
    }:
        _fail("successor static prerequisite manifest schema is invalid")
    if document["schema_version"] != _STATIC_SCHEMA:
        _fail("successor static prerequisite manifest version drifted")
    lock_sha = _sha(document["dependency_lock_sha256"], label="dependency lock SHA")
    v1_manifest = _canonical_object(
        _git_bytes(root, decision_base, V1_STATIC_MANIFEST), label="v1 static manifest"
    )
    if lock_sha != v1_manifest.get("dependency_lock_sha256"):
        _fail("successor dependency lock differs from the v1 runtime lock")
    bindings = _mapping(document["successor_bindings"], label="successor_bindings")
    if set(bindings) != set(_BINDING_PATHS):
        _fail("successor bindings are incomplete")
    for key, path in _BINDING_PATHS.items():
        binding = _mapping(bindings[key], label=f"successor binding {key}")
        if binding != {
            "path": path,
            "sha256": hashlib.sha256(_git_bytes(root, decision_base, path)).hexdigest(),
        }:
            _fail(f"successor binding drifted: {key}")
    rows = document["sources"]
    if type(rows) is not list or not rows:
        _fail("successor static prerequisite sources must be non-empty")
    paths: list[str] = []
    observed_lock: str | None = None
    for item in cast(list[object], rows):
        row = _mapping(item, label="successor source record")
        source_path = row.get("path")
        if (
            set(row) != {"path", "sha256"}
            or type(source_path) is not str
            or not source_path
            or source_path.startswith("/")
            or ".." in Path(source_path).parts
        ):
            _fail("successor static prerequisite source record is invalid")
        actual = hashlib.sha256(_git_bytes(root, decision_base, source_path)).hexdigest()
        if actual != _sha(row["sha256"], label=f"source SHA for {source_path}"):
            _fail(f"successor static prerequisite source drifted: {source_path}")
        if source_path == "uv.lock":
            observed_lock = actual
        paths.append(source_path)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        _fail("successor static prerequisite sources must be sorted and unique")
    if observed_lock != lock_sha:
        _fail("successor dependency lock identity does not match source binding")
    return SuccessorStaticIdentity(
        manifest_sha256=hashlib.sha256(raw).hexdigest(), dependency_lock_sha256=lock_sha
    )


def _trusted_receipts(root: Path, decision_base: str) -> tuple[str, ...]:
    _, document = _document(root, decision_base, TRUST)
    if set(document) != {"schema_version", "trusted_receipt_sha256"}:
        _fail("successor trust schema is invalid")
    if document["schema_version"] != _TRUST_SCHEMA:
        _fail("successor trust schema version drifted")
    raw = document["trusted_receipt_sha256"]
    if type(raw) is not list:
        _fail("successor trusted receipt digests must be an array")
    result = tuple(_sha(item, label="trusted receipt SHA") for item in cast(list[object], raw))
    if result != tuple(sorted(result)) or len(result) != len(set(result)):
        _fail("successor trusted receipt digests must be sorted and unique")
    return result


def _is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    if _SHA40.fullmatch(ancestor) is None or _SHA40.fullmatch(descendant) is None:
        return False
    completed = subprocess.run(
        ("git", "merge-base", "--is-ancestor", ancestor, descendant),
        cwd=root,
        check=False,
        capture_output=True,
    )
    if completed.returncode in (0, 1):
        return completed.returncode == 0
    _fail("Git ancestry check failed")


def mrl0809_successor_gate(root: Path, decision_base: str) -> bool:
    """Return True only for an intact v1 record plus a separately trusted v2 PASS."""
    static = validate_successor_static_prerequisites(root, decision_base)
    trusted = _trusted_receipts(root, decision_base)
    _, slot = _document(root, decision_base, SLOT)
    if slot.get("schema_version") != _SLOT_SCHEMA or slot.get("task_id") != "MRL-0809":
        _fail("successor runtime-feasibility slot identity drifted")
    state = slot.get("state")
    if state == "ABSENT":
        if set(slot) != {"schema_version", "state", "task_id"}:
            _fail("ABSENT successor slot schema is invalid")
        return False
    if state != "PRESENT" or set(slot) != {"receipt", "schema_version", "state", "task_id"}:
        _fail("successor runtime-feasibility slot state/schema is invalid")
    receipt_value = _mapping(slot["receipt"], label="successor slot receipt")
    receipt_bytes = canonical_json_bytes(receipt_value)
    if hashlib.sha256(receipt_bytes).hexdigest() not in trusted:
        return False
    try:
        receipt = validate_successor_runtime_feasibility_receipt(
            receipt_bytes,
            expected_static_prerequisite_manifest_sha256=static.manifest_sha256,
            expected_dependency_lock_sha256=static.dependency_lock_sha256,
        )
    except MRL0809SuccessorRuntimeFeasibilityError as exc:
        raise MRL0809SuccessorGateError("successor receipt failed validation") from exc
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
        raise MRL0809SuccessorGateError("successor producer tree lookup failed") from exc
    return tree == receipt.repository_tree


__all__ = [
    "MRL0809SuccessorGateError",
    "SuccessorStaticIdentity",
    "mrl0809_successor_gate",
    "validate_successor_static_prerequisites",
]
