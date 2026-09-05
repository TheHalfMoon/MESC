"""Trusted real-preflight binding for deterministic MRL machine-state projections.

The previously accepted closeout-evidence facade is preserved byte-for-byte in
``_mrl_machine_state_generation_closeout_v1``. This module layers the MRL-8 real-evidence
admission path over that implementation without weakening its historical closeout rules.

Real-evidence plumbing is not authority. The production trust registry remains the
admission boundary, projections remain derived/non-authoritative, and an empty admission
index preserves MRL-0801..MRL-0808 as PLANNED.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from medscale.mesc import _mrl_machine_state_generation_closeout_v1 as _closeout
from medscale.mesc import _mrl_machine_state_generation_legacy_v1 as _legacy
from medscale.mesc import _mrl_real_preflight_evidence_v1 as _real_preflight
from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_capability_matrix_v1 import CapabilityMatrixProjection
from medscale.mesc._mrl_project_state_v1 import ProjectStateEntry, ProjectStateProjection
from medscale.mesc._mrl_research_program_index_v1 import ResearchProgramIndexProjection

__all__ = [
    "MachineStateGenerationError",
    "MachineStateRenderSet",
    "admit_project_state_projection",
    "generate_machine_state",
    "load_canonical_snapshot",
]

_REAL_EVIDENCE_INDEX: Final = (
    "specs/mesc-research-loop-v1/real-preflight-evidence-index-v1.json"
)
_REAL_EVIDENCE_SOURCE: Final = "src/medscale/mesc/_mrl_real_preflight_evidence_v1.py"
_REAL_EVIDENCE_SLOT_DIR: Final = "specs/mesc-research-loop-v1/real-preflight-evidence"
_REAL_INDEX_SCHEMA_VERSION: Final = "MRL-REAL-PREFLIGHT-EVIDENCE-INDEX-V1"
_REAL_SLOT_SCHEMA_VERSION: Final = "MRL-REAL-PREFLIGHT-EVIDENCE-SLOT-V1"
_REAL_INDEX_RECORD_FIELDS: Final = frozenset(
    {"evidence_path", "evidence_sha256", "task_id"}
)
_SHA64: Final = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class _RealEvidenceIndexRecord:
    task_id: str
    evidence_path: str
    evidence_sha256: str


MachineStateGenerationError = _closeout.MachineStateGenerationError
MachineStateRenderSet = _closeout.MachineStateRenderSet
_REAL_EVIDENCE = _closeout._REAL_EVIDENCE
_REAL_EVIDENCE_SLOT_PATHS: Final = tuple(
    f"{_REAL_EVIDENCE_SLOT_DIR}/{task_id}.json" for task_id in sorted(_REAL_EVIDENCE)
)

# Keep historical/private compatibility used by the accepted closeout regression suite.
_CloseoutEvidence = _closeout._CloseoutEvidence
_dependencies = _closeout._dependencies
_parse_closeout_evidence = _closeout._parse_closeout_evidence
_evidence_by_task = _closeout._evidence_by_task
_merge_shape_closure = _closeout._merge_shape_closure

_closeout_project = _legacy._project
_project_sources = tuple(
    sorted(
        set(_legacy._PROJECT_SOURCES)
        | {
            _REAL_EVIDENCE_INDEX,
            _REAL_EVIDENCE_SOURCE,
            *_REAL_EVIDENCE_SLOT_PATHS,
        }
    )
)
_all_sources = tuple(
    sorted(
        set(_legacy._ALL_SOURCES)
        | {
            _REAL_EVIDENCE_INDEX,
            _REAL_EVIDENCE_SOURCE,
            *_REAL_EVIDENCE_SLOT_PATHS,
        }
    )
)
vars(_legacy)["_PROJECT_SOURCES"] = _project_sources
vars(_legacy)["_ALL_SOURCES"] = _all_sources


def _slot_path(task_id: str) -> str:
    if task_id not in _REAL_EVIDENCE:
        raise MachineStateGenerationError(f"unsupported MRL real-evidence task: {task_id}")
    return f"{_REAL_EVIDENCE_SLOT_DIR}/{task_id}.json"


def _absent_slot_bytes(task_id: str) -> bytes:
    return canonical_json_bytes(
        {
            "schema_version": _REAL_SLOT_SCHEMA_VERSION,
            "state": "ABSENT",
            "task_id": task_id,
        }
    )


def _parse_real_evidence_index(raw: bytes) -> dict[str, _RealEvidenceIndexRecord]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MachineStateGenerationError("MRL real-evidence index is not UTF-8") from exc
    try:
        loaded: object = json.loads(text, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as exc:
        raise MachineStateGenerationError("MRL real-evidence index is not valid JSON") from exc
    if type(loaded) is not dict:
        raise MachineStateGenerationError("MRL real-evidence index must be a JSON object")
    document = cast(dict[str, object], loaded)
    if set(document) != {"records", "schema_version"}:
        raise MachineStateGenerationError("MRL real-evidence index top-level schema is invalid")
    if document["schema_version"] != _REAL_INDEX_SCHEMA_VERSION:
        raise MachineStateGenerationError("MRL real-evidence index schema version is invalid")
    if raw != canonical_json_bytes(document):
        raise MachineStateGenerationError(
            "MRL real-evidence index must use exact canonical JSON bytes"
        )
    rows = document["records"]
    if type(rows) is not list:
        raise MachineStateGenerationError("MRL real-evidence index records must be an array")

    records: list[_RealEvidenceIndexRecord] = []
    for value in cast(list[object], rows):
        if type(value) is not dict or set(value) != _REAL_INDEX_RECORD_FIELDS:
            raise MachineStateGenerationError("MRL real-evidence index record schema is invalid")
        row = cast(dict[str, object], value)
        task_id = row["task_id"]
        evidence_path = row["evidence_path"]
        evidence_sha256 = row["evidence_sha256"]
        if type(task_id) is not str or task_id not in _REAL_EVIDENCE:
            raise MachineStateGenerationError("MRL real-evidence index task identity is invalid")
        if type(evidence_path) is not str or evidence_path != _slot_path(task_id):
            raise MachineStateGenerationError(
                "MRL real-evidence index path must equal the fixed canonical task slot"
            )
        if type(evidence_sha256) is not str or _SHA64.fullmatch(evidence_sha256) is None:
            raise MachineStateGenerationError("MRL real-evidence index SHA-256 is invalid")
        records.append(_RealEvidenceIndexRecord(task_id, evidence_path, evidence_sha256))

    task_ids = tuple(record.task_id for record in records)
    paths = tuple(record.evidence_path for record in records)
    if task_ids != tuple(sorted(task_ids)) or len(task_ids) != len(set(task_ids)):
        raise MachineStateGenerationError(
            "MRL real-evidence index records must be task-sorted and task-unique"
        )
    if len(paths) != len(set(paths)):
        raise MachineStateGenerationError("MRL real-evidence index paths must be unique")
    return {record.task_id: record for record in records}


def _admitted_real_evidence_by_task(
    root: Path,
    decision_base: str,
) -> dict[str, _RealEvidenceIndexRecord]:
    index_raw = _legacy._git_bytes(root, "show", f"{decision_base}:{_REAL_EVIDENCE_INDEX}")
    indexed = _parse_real_evidence_index(index_raw)
    admitted: dict[str, _RealEvidenceIndexRecord] = {}

    for task_id in sorted(_REAL_EVIDENCE):
        path = _slot_path(task_id)
        slot_raw = _legacy._git_bytes(root, "show", f"{decision_base}:{path}")
        record = indexed.get(task_id)
        if record is None:
            if slot_raw != _absent_slot_bytes(task_id):
                raise MachineStateGenerationError(
                    f"MRL real-evidence slot {task_id} is non-empty but absent "
                    "from the admission index"
                )
            continue

        digest = hashlib.sha256(slot_raw).hexdigest()
        if digest != record.evidence_sha256:
            raise MachineStateGenerationError(
                f"MRL real-evidence slot digest mismatch for {task_id}"
            )
        try:
            parsed = _real_preflight.admit_mrl_real_preflight_evidence(
                slot_raw,
                expected_task_id=cast(_real_preflight.MRLRealPreflightTask, task_id),
            )
        except _real_preflight.MRLRealPreflightEvidenceError as exc:
            raise MachineStateGenerationError(
                f"MRL real-evidence admission failed for {task_id}: {exc}"
            ) from exc
        if parsed.task_id != task_id or parsed.evidence_sha256 != record.evidence_sha256:
            raise MachineStateGenerationError(
                f"MRL real-evidence admitted identity mismatch for {task_id}"
            )
        admitted[task_id] = record
    return admitted


def _closure_proof(
    root: Path,
    decision_base: str,
    canonical_main_sha: str,
    task_id: str,
) -> tuple[str, str] | None:
    """Return closure only when canonical transition and required evidence agree exactly."""
    if task_id in _REAL_EVIDENCE:
        if decision_base != canonical_main_sha:
            return None

        # Historical repository-only closeout evidence can never close a real-evidence task.
        if _evidence_by_task(root, decision_base).get(task_id) is not None:
            return None

        record = _admitted_real_evidence_by_task(root, decision_base).get(task_id)
        if record is None:
            raise MachineStateGenerationError(
                f"checked real-evidence task {task_id} lacks a canonical admitted evidence record"
            )
        # Legacy assembly expects a commit-shaped closure tuple. _project replaces these
        # temporary refs with the exact real-evidence digest/path refs below.
        return (decision_base, decision_base)

    transition = _merge_shape_closure(
        root,
        decision_base,
        canonical_main_sha,
        task_id,
    )
    if transition is None:
        return None
    record = _evidence_by_task(root, decision_base).get(task_id)
    if record is None:
        return None
    if record.canonical_merge_sha != transition[0] or record.qualified_head_sha != transition[1]:
        return None
    return transition


def _project(
    snapshot: _legacy.CanonicalRepositorySnapshot,
    research: ResearchProgramIndexProjection,
    capability: CapabilityMatrixProjection,
) -> ProjectStateProjection:
    """Derive project state after validating every claimed real-evidence admission."""
    admitted = _admitted_real_evidence_by_task(
        snapshot.repository_root,
        snapshot.commit_sha,
    )
    projected = _closeout_project(snapshot, research, capability)

    entries: list[ProjectStateEntry] = []
    for entry in projected.entries:
        if entry.state_id not in _REAL_EVIDENCE or entry.lifecycle_state != "CLOSED_CANONICAL":
            entries.append(entry)
            continue
        record = admitted.get(entry.state_id)
        if record is None:
            raise MachineStateGenerationError(
                f"closed real-evidence task {entry.state_id} lacks admitted evidence"
            )
        refs = tuple(
            sorted(
                (
                    f"canonical-main:{snapshot.canonical_main_sha}",
                    f"real-preflight-evidence:{record.evidence_sha256}",
                    f"real-preflight-path:{record.evidence_path}",
                )
            )
        )
        entries.append(
            ProjectStateEntry(
                entry.state_id,
                entry.lifecycle_state,
                entry.canonical_source_paths,
                entry.dependency_ids,
                refs,
            )
        )

    return ProjectStateProjection(
        projected.research_program_index,
        projected.capability_matrix,
        projected.sources,
        tuple(entries),
    )


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MachineStateGenerationError(
                f"duplicate MRL real-evidence JSON member rejected: {key}"
            )
        result[key] = value
    return result


vars(_legacy)["_closure_proof"] = _closure_proof
vars(_legacy)["_project"] = _project

admit_project_state_projection = _legacy.admit_project_state_projection
generate_machine_state = _legacy.generate_machine_state
load_canonical_snapshot = _legacy.load_canonical_snapshot
