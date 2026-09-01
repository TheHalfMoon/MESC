"""Evidence-bound admission facade for deterministic MRL machine-state projections.

The implementation that existed before the closeout-evidence repair is preserved
byte-for-byte in ``_mrl_machine_state_generation_legacy_v1``. This facade adds one
canonical source and replaces merge-shape-only closure with fail-closed admission
against independently harvested exact-head GitHub qualification evidence.

The manifest is evidence, not authority: projections remain derived and
non-authoritative, and no model/data/runtime/training/release authority is granted.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from medscale.mesc import _mrl_machine_state_generation_legacy_v1 as _legacy

__all__ = [
    "MachineStateGenerationError",
    "MachineStateRenderSet",
    "admit_project_state_projection",
    "generate_machine_state",
    "load_canonical_snapshot",
]

_CLOSEOUT_EVIDENCE: Final = "specs/mesc-research-loop-v1/closeout-evidence-v1.json"
_SCHEMA_VERSION: Final = "MRL-CLOSEOUT-EVIDENCE-V1"
_REPOSITORY_PROFILE: Final = "MRL_REPOSITORY_EXACT_HEAD_V1"
_REVIEWED_PROFILE: Final = "MRL_REVIEWED_EXACT_HEAD_V1"
_CONSTITUTION_PROFILE: Final = "MRL_CONSTITUTION_EXACT_HEAD_V1"
_PROFILES: Final = frozenset(
    {_REPOSITORY_PROFILE, _REVIEWED_PROFILE, _CONSTITUTION_PROFILE}
)
_REVIEW_REQUIRED_TASKS: Final = frozenset(
    {"MRL-0100", "MRL-0101", "MRL-0102", "MRL-0103", "MRL-0109"}
)
_TASK_ID: Final = re.compile(r"^MRL-[0-9]{4}$")
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$")
_INDEPENDENT_REF: Final = re.compile(r"^(?:comment|review):[1-9][0-9]*$")
_RECORD_FIELDS: Final = frozenset(
    {
        "canonical_merge_sha",
        "coderabbit_success_status_ids",
        "evidence_profile",
        "independent_exact_head_evidence_refs",
        "owner_exact_head_review_ids",
        "pr_number",
        "qodo_exact_head_comment_ids",
        "qualified_head_sha",
        "successful_ci_run_ids",
        "successful_codeql_run_ids",
        "task_ids",
    }
)


@dataclass(frozen=True, slots=True)
class _CloseoutEvidence:
    canonical_merge_sha: str
    qualified_head_sha: str
    pr_number: int
    evidence_profile: str
    successful_ci_run_ids: tuple[int, ...]
    successful_codeql_run_ids: tuple[int, ...]
    independent_exact_head_evidence_refs: tuple[str, ...]
    qodo_exact_head_comment_ids: tuple[int, ...]
    owner_exact_head_review_ids: tuple[int, ...]
    coderabbit_success_status_ids: tuple[int, ...]
    task_ids: tuple[str, ...]


MachineStateGenerationError = _legacy.MachineStateGenerationError
MachineStateRenderSet = _legacy.MachineStateRenderSet
_REAL_EVIDENCE = _legacy._REAL_EVIDENCE

_merge_shape_closure = _legacy._closure_proof

_project_sources = tuple(sorted(set(_legacy._PROJECT_SOURCES) | {_CLOSEOUT_EVIDENCE}))
_all_sources = tuple(sorted(set(_legacy._ALL_SOURCES) | {_CLOSEOUT_EVIDENCE}))
vars(_legacy)["_PROJECT_SOURCES"] = _project_sources
vars(_legacy)["_ALL_SOURCES"] = _all_sources


def _closure_proof(
    root: Path,
    decision_base: str,
    canonical_main_sha: str,
    task_id: str,
) -> tuple[str, str] | None:
    """Return closure only when Git transition and admitted evidence agree exactly."""
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
    if (
        record.canonical_merge_sha != transition[0]
        or record.qualified_head_sha != transition[1]
    ):
        return None
    return transition


def _evidence_by_task(
    root: Path,
    decision_base: str,
) -> dict[str, _CloseoutEvidence]:
    try:
        payload = _legacy._git_bytes(
            root,
            "show",
            f"{decision_base}:{_CLOSEOUT_EVIDENCE}",
        )
    except MachineStateGenerationError:
        return {}
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MachineStateGenerationError(
            "MRL closeout evidence manifest is not UTF-8"
        ) from exc
    return _parse_closeout_evidence(text)


def _parse_closeout_evidence(text: str) -> dict[str, _CloseoutEvidence]:
    try:
        loaded: object = json.loads(text, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as exc:
        raise MachineStateGenerationError(
            "MRL closeout evidence manifest is not valid JSON"
        ) from exc
    if type(loaded) is not dict:
        raise MachineStateGenerationError(
            "MRL closeout evidence manifest must be a JSON object"
        )
    document = cast(dict[str, object], loaded)
    if set(document) != {"records", "schema_version"}:
        raise MachineStateGenerationError(
            "MRL closeout evidence top-level schema is invalid"
        )
    if document["schema_version"] != _SCHEMA_VERSION:
        raise MachineStateGenerationError(
            "MRL closeout evidence schema version is invalid"
        )
    rows = document["records"]
    if type(rows) is not list or not rows:
        raise MachineStateGenerationError(
            "MRL closeout evidence records must be a non-empty array"
        )

    records: list[_CloseoutEvidence] = []
    for row in cast(list[object], rows):
        records.append(_parse_record(row))

    first_ids = tuple(record.task_ids[0] for record in records)
    if first_ids != tuple(sorted(first_ids)):
        raise MachineStateGenerationError(
            "MRL closeout evidence records must be sorted by first task_id"
        )

    result: dict[str, _CloseoutEvidence] = {}
    for record in records:
        for task_id in record.task_ids:
            if task_id in result:
                raise MachineStateGenerationError(
                    f"MRL closeout evidence duplicates task: {task_id}"
                )
            result[task_id] = record
    return result


def _parse_record(value: object) -> _CloseoutEvidence:
    if type(value) is not dict or set(value) != _RECORD_FIELDS:
        raise MachineStateGenerationError(
            "MRL closeout evidence record schema is invalid"
        )
    row = cast(dict[str, object], value)
    canonical_merge_sha = _sha40(row["canonical_merge_sha"], "canonical merge")
    qualified_head_sha = _sha40(row["qualified_head_sha"], "qualified head")
    pr_number = _positive_int(row["pr_number"], "PR number")
    evidence_profile = row["evidence_profile"]
    if type(evidence_profile) is not str or evidence_profile not in _PROFILES:
        raise MachineStateGenerationError(
            "MRL closeout evidence profile is invalid"
        )
    profile = cast(str, evidence_profile)
    task_ids = _task_ids(row["task_ids"])
    ci = _positive_ids(row["successful_ci_run_ids"], "CI run IDs")
    codeql = _positive_ids(row["successful_codeql_run_ids"], "CodeQL run IDs")
    independent = _independent_refs(row["independent_exact_head_evidence_refs"])
    qodo = _positive_ids(
        row["qodo_exact_head_comment_ids"],
        "Qodo exact-head comment IDs",
        allow_empty=True,
    )
    owner = _positive_ids(
        row["owner_exact_head_review_ids"],
        "owner exact-head review IDs",
        allow_empty=True,
    )
    coderabbit = _positive_ids(
        row["coderabbit_success_status_ids"],
        "CodeRabbit success status IDs",
        allow_empty=True,
    )

    if not ci or not codeql:
        raise MachineStateGenerationError(
            "MRL closeout evidence requires successful exact-head CI and CodeQL"
        )

    contains_constitution_gate = "MRL-0099" in task_ids
    contains_review_gate = bool(_REVIEW_REQUIRED_TASKS.intersection(task_ids))
    if contains_constitution_gate:
        if (
            profile != _CONSTITUTION_PROFILE
            or independent
            or not qodo
            or not owner
            or not coderabbit
        ):
            raise MachineStateGenerationError(
                "MRL-0099 evidence does not satisfy the constitution exact-head profile"
            )
    elif contains_review_gate:
        if (
            profile != _REVIEWED_PROFILE
            or not independent
            or qodo
            or owner
            or coderabbit
        ):
            raise MachineStateGenerationError(
                "review-required MRL closeout evidence has the wrong profile"
            )
    elif profile != _REPOSITORY_PROFILE or independent or qodo or owner or coderabbit:
        raise MachineStateGenerationError(
            "repository-only MRL closeout evidence has the wrong profile"
        )

    return _CloseoutEvidence(
        canonical_merge_sha=canonical_merge_sha,
        qualified_head_sha=qualified_head_sha,
        pr_number=pr_number,
        evidence_profile=profile,
        successful_ci_run_ids=ci,
        successful_codeql_run_ids=codeql,
        independent_exact_head_evidence_refs=independent,
        qodo_exact_head_comment_ids=qodo,
        owner_exact_head_review_ids=owner,
        coderabbit_success_status_ids=coderabbit,
        task_ids=task_ids,
    )


def _sha40(value: object, label: str) -> str:
    if type(value) is not str or _SHA40.fullmatch(value) is None:
        raise MachineStateGenerationError(
            f"MRL closeout evidence {label} SHA is invalid"
        )
    return cast(str, value)


def _positive_int(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise MachineStateGenerationError(
            f"MRL closeout evidence {label} is invalid"
        )
    return cast(int, value)


def _positive_ids(
    value: object,
    label: str,
    *,
    allow_empty: bool = False,
) -> tuple[int, ...]:
    if type(value) is not list:
        raise MachineStateGenerationError(
            f"MRL closeout evidence {label} must be an array"
        )
    raw = cast(list[object], value)
    result = tuple(_positive_int(item, label) for item in raw)
    if not allow_empty and not result:
        raise MachineStateGenerationError(
            f"MRL closeout evidence {label} must not be empty"
        )
    if result != tuple(sorted(result)) or len(result) != len(set(result)):
        raise MachineStateGenerationError(
            f"MRL closeout evidence {label} must be sorted and unique"
        )
    return result


def _independent_refs(value: object) -> tuple[str, ...]:
    if type(value) is not list:
        raise MachineStateGenerationError(
            "MRL closeout evidence independent exact-head evidence refs must be an array"
        )
    raw = cast(list[object], value)
    result: list[str] = []
    for item in raw:
        if type(item) is not str or _INDEPENDENT_REF.fullmatch(item) is None:
            raise MachineStateGenerationError(
                "MRL closeout evidence independent exact-head evidence ref is invalid"
            )
        result.append(cast(str, item))
    refs = tuple(result)
    if refs != tuple(sorted(refs)) or len(refs) != len(set(refs)):
        raise MachineStateGenerationError(
            "MRL closeout evidence independent exact-head evidence refs must be sorted and unique"
        )
    return refs


def _task_ids(value: object) -> tuple[str, ...]:
    if type(value) is not list:
        raise MachineStateGenerationError(
            "MRL closeout evidence task_ids must be an array"
        )
    raw = cast(list[object], value)
    if not raw:
        raise MachineStateGenerationError(
            "MRL closeout evidence task_ids must not be empty"
        )
    result: list[str] = []
    for item in raw:
        if type(item) is not str or _TASK_ID.fullmatch(item) is None:
            raise MachineStateGenerationError(
                "MRL closeout evidence task identity is invalid"
            )
        result.append(cast(str, item))
    task_ids = tuple(result)
    if task_ids != tuple(sorted(task_ids)) or len(task_ids) != len(set(task_ids)):
        raise MachineStateGenerationError(
            "MRL closeout evidence task_ids must be sorted and unique"
        )
    return task_ids


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MachineStateGenerationError(
                f"duplicate MRL closeout evidence JSON member rejected: {key}"
            )
        result[key] = value
    return result


vars(_legacy)["_closure_proof"] = _closure_proof

admit_project_state_projection = _legacy.admit_project_state_projection
generate_machine_state = _legacy.generate_machine_state
load_canonical_snapshot = _legacy.load_canonical_snapshot