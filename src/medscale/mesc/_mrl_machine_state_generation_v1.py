"""Deterministic generation and admission for MRL machine-state projections.

Project-state bytes are derived from exact Git objects and canonical closeout merge
transitions. Projected task fields are never trusted as evidence. This module performs
repository inspection only and grants no execution, model, data, runtime, GPU, training,
promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from medscale.mesc._canonical_json_v1 import canonical_json_bytes, canonical_sha256
from medscale.mesc._mrl_capability_matrix_v1 import (
    CapabilityMatrixEntry,
    CapabilityMatrixProjection,
    CapabilityRepositoryBinding,
    CapabilitySourceBinding,
)
from medscale.mesc._mrl_project_state_v1 import (
    ProjectStateEntry,
    ProjectStateProjection,
    ProjectStateSourceBinding,
)
from medscale.mesc._mrl_research_program_index_v1 import (
    RepositoryBinding,
    ResearchProgramIndexProjection,
    ResearchProgramNamespace,
    ResearchQuestionIndexEntry,
    SourceBinding,
)

__all__ = [
    "MachineStateGenerationError",
    "MachineStateRenderSet",
    "admit_project_state_projection",
    "generate_machine_state",
    "load_canonical_snapshot",
]

_REGISTRY: Final = "docs/research/research_program_registry.md"
_QUESTIONS: Final = "docs/research/research_questions.md"
_ROADMAP: Final = "ROADMAP.md"
_RECONCILIATION: Final = "docs/strategy/mesc_pr122_post_b0_reconciliation_2026-08-19.md"
_TASKS: Final = "specs/mesc-research-loop-v1/tasks.md"
_PROJECT_SOURCES: Final = tuple(
    sorted(
        {
            "docs/adr/0035-mrl-governance-constitution.md",
            "specs/mesc-research-loop-v1/README.md",
            "specs/mesc-research-loop-v1/plan.md",
            "specs/mesc-research-loop-v1/project-state-contract.md",
            "specs/mesc-research-loop-v1/project-state-v1.schema.json",
            "specs/mesc-research-loop-v1/spec.md",
            _TASKS,
            "specs/mesc-training-readiness-v1/README.md",
            "src/medscale/mesc/_training_authorization_trust_v1.py",
            "src/medscale/mesc/_training_runtime_qualification_v1.py",
        }
    )
)
_ALL_SOURCES: Final = tuple(
    sorted(set(_PROJECT_SOURCES) | {_REGISTRY, _QUESTIONS, _ROADMAP, _RECONCILIATION})
)
_OUTPUTS: Final = (
    "CAPABILITY_MATRIX.json",
    "PROJECT_STATE.json",
    "RESEARCH_PROGRAM_INDEX.json",
)
_TASK_RE: Final = re.compile(r"^- \[([ x])\] \*\*(MRL-[0-9]{4}) — ")
_DEP_RE: Final = re.compile(r"MRL-([0-9]{4})(?:\.\.(?:MRL-)?([0-9]{4}))?")
_SHA40: Final = re.compile(r"^[0-9a-f]{40}$")
_SHA64: Final = re.compile(r"^[0-9a-f]{64}$")
_PATH_PART: Final = re.compile(r"^[A-Za-z0-9._-]+$")
_STATES: Final = frozenset(
    {
        "PLANNED",
        "ELIGIBLE",
        "IN_PROGRESS",
        "BLOCKED",
        "QUALIFYING",
        "CLOSED_CANONICAL",
    }
)
_REAL_EVIDENCE: Final = frozenset({f"MRL-08{n:02d}" for n in range(1, 10)} | {"MRL-0899"})
_MRL3_FRESHNESS: Final = (
    "src/medscale/mesc/_mrl_adaptive_budget_exhaustion_v1.py",
    "src/medscale/mesc/_mrl_adaptive_campaign_accounting_v1.py",
    "src/medscale/mesc/_mrl_hard_medical_non_regression_v1.py",
    "src/medscale/mesc/_mrl_pareto_comparison_v1.py",
    "src/medscale/mesc/_mrl_replication_set_policy_v1.py",
    "src/medscale/mesc/_mrl_sealed_evaluation_evidence_v1.py",
    "src/medscale/mesc/_mrl_sealed_evaluation_interface_v1.py",
    "tests/test_mesc_mrl_adaptive_budget_exhaustion_v1.py",
    "tests/test_mesc_mrl_adaptive_campaign_accounting_v1.py",
    "tests/test_mesc_mrl_hard_medical_non_regression_v1.py",
    "tests/test_mesc_mrl_pareto_comparison_v1.py",
    "tests/test_mesc_mrl_replication_set_policy_v1.py",
    "tests/test_mesc_mrl_sealed_evaluation_evidence_v1.py",
    "tests/test_mesc_mrl_sealed_evaluation_interface_v1.py",
)
_MRL7_FRESHNESS: Final = (
    ".github/workflows/ci.yml",
    ".github/workflows/codeql.yml",
    "src/medscale/mesc/_mrl_machine_state_generation_v1.py",
    "src/medscale/mesc/_mrl_project_state_v1.py",
    "tests/test_mesc_mrl_machine_state_ci_gate_v1.py",
    "tests/test_mesc_mrl_machine_state_exact_head_gate_v1.py",
    "tests/test_mesc_mrl_machine_state_generation_v1.py",
    "tests/test_mesc_mrl_project_state_admission_v1.py",
    "tests/test_mesc_mrl_project_state_v1.py",
)
_FRESHNESS: Final = {
    "MRL-0399": _MRL3_FRESHNESS,
    "MRL-0799": _MRL7_FRESHNESS,
}


class MachineStateGenerationError(ValueError):
    """Fail-closed error for machine-state generation or admission."""


@dataclass(frozen=True, slots=True)
class CanonicalSourceSnapshot:
    path: str
    git_blob_sha: str
    sha256: str
    content: str


@dataclass(frozen=True, slots=True)
class CanonicalRepositorySnapshot:
    repository_root: Path
    commit_sha: str
    tree_sha: str
    sources: tuple[CanonicalSourceSnapshot, ...]

    def source(self, path: str) -> CanonicalSourceSnapshot:
        rows = tuple(item for item in self.sources if item.path == path)
        if len(rows) != 1:
            raise MachineStateGenerationError(f"canonical source missing or duplicated: {path}")
        return rows[0]


@dataclass(frozen=True, slots=True)
class MachineStateRenderSet:
    commit_sha: str
    tree_sha: str
    capability_matrix: bytes
    project_state: bytes
    research_program_index: bytes

    def files(self) -> tuple[tuple[str, bytes], ...]:
        return (
            ("CAPABILITY_MATRIX.json", self.capability_matrix),
            ("PROJECT_STATE.json", self.project_state),
            ("RESEARCH_PROGRAM_INDEX.json", self.research_program_index),
        )


def load_canonical_snapshot(repository_root: Path) -> CanonicalRepositorySnapshot:
    """Load the fixed source set from the exact local Git HEAD."""
    root = repository_root.resolve()
    return CanonicalRepositorySnapshot(
        repository_root=root,
        commit_sha=_git(root, "rev-parse", "HEAD"),
        tree_sha=_git(root, "rev-parse", "HEAD^{tree}"),
        sources=tuple(_load_source(root, path) for path in _ALL_SOURCES),
    )


def generate_machine_state(
    repository_root: Path,
    output_dir: Path,
    *,
    check: bool = False,
) -> MachineStateRenderSet:
    """Generate exact projections or check existing output bytes."""
    snapshot = load_canonical_snapshot(repository_root)
    research = _research(snapshot)
    capability = _capability(snapshot)
    project = _project(snapshot, research, capability)
    rendered = MachineStateRenderSet(
        snapshot.commit_sha,
        snapshot.tree_sha,
        capability.semantic_bytes,
        project.semantic_bytes,
        research.semantic_bytes,
    )
    destination = output_dir.resolve()
    if check:
        _check(destination, rendered)
    else:
        destination.mkdir(parents=True, exist_ok=True)
        for name, payload in rendered.files():
            (destination / name).write_bytes(payload)
    return rendered


def admit_project_state_projection(
    repository_root: Path,
    payload: bytes,
) -> dict[str, object]:
    """Admit exact project-state bytes only after independent recomputation."""
    supplied = _validate_document(payload)
    snapshot = load_canonical_snapshot(repository_root)
    expected_repo = {
        "commit_sha": snapshot.commit_sha,
        "tree_sha": snapshot.tree_sha,
    }
    if supplied["repository"] != expected_repo:
        raise MachineStateGenerationError("project-state projection is stale for current Git HEAD")
    expected = _project(
        snapshot,
        _research(snapshot),
        _capability(snapshot),
    ).semantic_bytes
    if payload != expected:
        raise MachineStateGenerationError(
            "project-state projection does not match independent canonical recomputation"
        )
    return supplied


def _research(snapshot: CanonicalRepositorySnapshot) -> ResearchProgramIndexProjection:
    registry = snapshot.source(_REGISTRY)
    questions = snapshot.source(_QUESTIONS)
    sources = tuple(
        sorted(
            (_research_source(registry), _research_source(questions)),
            key=lambda item: item.path,
        )
    )
    return ResearchProgramIndexProjection(
        repository=RepositoryBinding(snapshot.commit_sha, snapshot.tree_sha),
        sources=sources,
        questions=_foundational_questions(registry.content),
        namespaces=_namespaces(registry.content),
    )


def _foundational_questions(text: str) -> tuple[ResearchQuestionIndexEntry, ...]:
    rows: list[ResearchQuestionIndexEntry] = []
    for line in text.splitlines():
        cells = _cells(line)
        if len(cells) != 3 or not cells[0].startswith("`RQ"):
            continue
        question_id = _uncode(cells[0])
        if question_id not in {f"RQ{index}" for index in range(1, 8)}:
            continue
        rows.append(
            ResearchQuestionIndexEntry(
                question_id,
                "Foundational MESC research",
                cells[2].split("—", 1)[0].strip(),
                _uncode(cells[1]),
            )
        )
    result = tuple(sorted(rows, key=lambda item: item.question_id))
    expected = tuple(f"RQ{index}" for index in range(1, 8))
    if tuple(row.question_id for row in result) != expected:
        raise MachineStateGenerationError("research registry must preserve exactly RQ1-RQ7")
    return result


def _namespaces(text: str) -> tuple[ResearchProgramNamespace, ...]:
    rows: list[ResearchProgramNamespace] = []
    active = False
    for line in text.splitlines():
        if line == "## Later-program namespaces":
            active = True
            continue
        if active and line.startswith("## "):
            break
        if not active:
            continue
        cells = _cells(line)
        if len(cells) == 5 and "<NNNN>" in cells[1]:
            rows.append(
                ResearchProgramNamespace(
                    cells[0],
                    _uncode(cells[1]),
                    cells[2],
                    (_REGISTRY,),
                    cells[4],
                )
            )
    if not rows:
        raise MachineStateGenerationError("research registry contains no later-program namespaces")
    return tuple(sorted(rows, key=lambda item: item.question_namespace))


def _capability(snapshot: CanonicalRepositorySnapshot) -> CapabilityMatrixProjection:
    roadmap = snapshot.source(_ROADMAP)
    reconciliation = snapshot.source(_RECONCILIATION)
    _contains(
        roadmap.content,
        "| **T0** | Repository & engineering foundation | ✅ complete | — |",
        _ROADMAP,
    )
    _contains(
        reconciliation.content,
        "`3f34b35daf4050d010a5f0061d6e8387f9649c10`",
        _RECONCILIATION,
    )
    _contains(
        reconciliation.content,
        "- training/fine-tuning: NOT AUTHORIZED",
        _RECONCILIATION,
    )
    sources = tuple(
        sorted(
            (_cap_source(roadmap), _cap_source(reconciliation)),
            key=lambda item: item.path,
        )
    )
    rows = (
        CapabilityMatrixEntry(
            "PILOT_01_B0_BASELINE",
            "HISTORICAL",
            "PROVEN",
            "NOT_APPLICABLE",
            (_RECONCILIATION,),
            ("merge:3f34b35daf4050d010a5f0061d6e8387f9649c10",),
        ),
        CapabilityMatrixEntry(
            "T0_REPOSITORY_FOUNDATION",
            "IMPLEMENTED",
            "PROVEN",
            "NOT_APPLICABLE",
            (_ROADMAP,),
            ("roadmap:T0",),
        ),
        CapabilityMatrixEntry(
            "TRAINING_EXECUTION",
            "NOT_STARTED",
            "UNPROVEN",
            "NOT_AUTHORIZED",
            (_RECONCILIATION,),
        ),
    )
    return CapabilityMatrixProjection(
        CapabilityRepositoryBinding(snapshot.commit_sha, snapshot.tree_sha),
        sources,
        rows,
    )


def _project(
    snapshot: CanonicalRepositorySnapshot,
    research: ResearchProgramIndexProjection,
    capability: CapabilityMatrixProjection,
) -> ProjectStateProjection:
    records = _task_records(snapshot.source(_TASKS).content)
    closed: set[str] = set()
    evidence: dict[str, tuple[str, ...]] = {}
    for task_id, checked, _dependencies in records:
        proof = _closure_proof(snapshot.repository_root, task_id) if checked else None
        if proof is not None and not _stale(
            snapshot.repository_root,
            task_id,
            proof[0],
        ):
            closed.add(task_id)
            evidence[task_id] = (
                f"canonical-merge:{proof[0]}",
                f"qualified-head:{proof[1]}",
            )

    entries: list[ProjectStateEntry] = []
    for task_id, _checked, dependencies in records:
        if task_id in closed:
            state = "CLOSED_CANONICAL"
            refs = evidence[task_id]
        elif task_id in _REAL_EVIDENCE:
            state, refs = "PLANNED", ()
        elif all(dependency in closed for dependency in dependencies) and _special_gate(
            snapshot,
            task_id,
        ):
            state, refs = "ELIGIBLE", ()
        else:
            state, refs = "PLANNED", ()
        entries.append(
            ProjectStateEntry(
                task_id,
                state,
                _PROJECT_SOURCES,
                dependencies,
                refs,
            )
        )

    sources = tuple(
        ProjectStateSourceBinding(source.path, source.git_blob_sha, source.sha256)
        for source in (snapshot.source(path) for path in _PROJECT_SOURCES)
    )
    return ProjectStateProjection(
        research,
        capability,
        sources,
        tuple(entries),
    )


def _special_gate(snapshot: CanonicalRepositorySnapshot, task_id: str) -> bool:
    if task_id != "MRL-0800":
        return True
    trust = snapshot.source("src/medscale/mesc/_training_authorization_trust_v1.py").content
    runtime = snapshot.source("src/medscale/mesc/_training_runtime_qualification_v1.py").content
    readiness = snapshot.source("specs/mesc-training-readiness-v1/README.md").content
    return (
        "TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256: frozenset[str] = frozenset()" in trust
        and "Fail-closed MESC training runtime-qualification" in runtime
        and "PRE-EXECUTION / NO TRAINING PERFORMED" in readiness
    )


def _task_records(text: str) -> tuple[tuple[str, bool, tuple[str, ...]], ...]:
    lines = text.splitlines()
    rows: list[tuple[str, bool, tuple[str, ...]]] = []
    for index, line in enumerate(lines):
        match = _TASK_RE.match(line)
        if match is None:
            continue
        block: list[str] = []
        cursor = index + 1
        while cursor < len(lines) and _TASK_RE.match(lines[cursor]) is None:
            if lines[cursor].startswith(("## ", "### ")):
                break
            block.append(lines[cursor])
            cursor += 1
        task_id = match.group(2)
        rows.append(
            (
                task_id,
                match.group(1) == "x",
                _dependencies(block, task_id),
            )
        )
    ids = tuple(row[0] for row in rows)
    if not ids or len(set(ids)) != len(ids):
        raise MachineStateGenerationError("MRL task ledger has missing or duplicate task IDs")
    known = set(ids)
    for task_id, _checked, dependencies in rows:
        missing = tuple(item for item in dependencies if item not in known)
        if missing:
            raise MachineStateGenerationError(
                f"MRL task {task_id} references unknown dependency {missing[0]}"
            )
    return tuple(sorted(rows, key=lambda row: row[0]))


def _dependencies(lines: list[str], task_id: str) -> tuple[str, ...]:
    text = "\n".join(line for line in lines if "Depends on:" in line or "Requires:" in line)
    result: set[str] = set()
    for match in _DEP_RE.finditer(text):
        start = int(match.group(1))
        end_text = match.group(2)
        if end_text is None:
            result.add(f"MRL-{start:04d}")
            continue
        end = int(end_text)
        if end < start:
            raise MachineStateGenerationError("MRL dependency range is descending")
        result.update(f"MRL-{value:04d}" for value in range(start, end + 1))
    result.discard(task_id)
    return tuple(sorted(result))


def _closure_proof(root: Path, task_id: str) -> tuple[str, str] | None:
    history = _git(
        root,
        "log",
        "--first-parent",
        "--format=%H%x09%P",
        "HEAD",
        "--",
        _TASKS,
    )
    for line in history.splitlines():
        fields = line.split("\t", 1)
        if len(fields) != 2:
            continue
        commit, parents_text = fields
        parents = tuple(parents_text.split())
        if not parents:
            continue
        current = _task_checked_at(root, commit, task_id)
        previous = _task_checked_at(root, parents[0], task_id)
        if current == previous:
            continue
        if current and not previous and len(parents) == 2:
            return commit, parents[1]
        return None
    return None


def _task_checked_at(root: Path, revision: str, task_id: str) -> bool:
    try:
        text = _git_bytes(root, "show", f"{revision}:{_TASKS}").decode("utf-8")
    except (MachineStateGenerationError, UnicodeDecodeError) as exc:
        raise MachineStateGenerationError("cannot reproduce historical MRL task ledger") from exc
    matches = [
        match.group(1) == "x"
        for line in text.splitlines()
        if (match := _TASK_RE.match(line)) is not None and match.group(2) == task_id
    ]
    if len(matches) != 1:
        raise MachineStateGenerationError(
            f"historical task identity is missing or duplicated: {task_id}"
        )
    return matches[0]


def _stale(root: Path, task_id: str, merge_sha: str) -> bool:
    paths = _FRESHNESS.get(task_id)
    if paths is None:
        return False
    return bool(
        _git(
            root,
            "rev-list",
            "-1",
            f"{merge_sha}..HEAD",
            "--",
            *paths,
        )
    )


def _validate_document(payload: bytes) -> dict[str, object]:
    try:
        text = payload.decode("utf-8")
        loaded = json.loads(text, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MachineStateGenerationError(
            "project-state projection is not valid UTF-8 JSON"
        ) from exc
    if type(loaded) is not dict:
        raise MachineStateGenerationError("project-state projection must be a JSON object")
    document = cast(dict[str, object], loaded)
    required = {
        "can_authorize",
        "projection_kind",
        "repository",
        "schema_version",
        "source_set_sha256",
        "sources",
        "tasks",
    }
    if set(document) != required:
        raise MachineStateGenerationError("project-state top-level schema is invalid")
    if (
        document["schema_version"] != "MRL-PROJECT-STATE-V1"
        or document["projection_kind"] != "DERIVED_NON_AUTHORITATIVE"
        or document["can_authorize"] is not False
    ):
        raise MachineStateGenerationError("project-state authority/schema constants are invalid")
    _validate_repo(document["repository"])
    sources = _validate_sources(document["sources"])
    tasks = _validate_tasks(document["tasks"])
    digest = document["source_set_sha256"]
    if (
        type(digest) is not str
        or _SHA64.fullmatch(digest) is None
        or canonical_sha256(sources) != digest
    ):
        raise MachineStateGenerationError("project-state source_set_sha256 does not reproduce")
    if canonical_json_bytes(document) != payload:
        raise MachineStateGenerationError("project-state projection is not canonical JSON bytes")
    ids = [cast(str, row["task_id"]) for row in tasks]
    if ids != sorted(ids):
        raise MachineStateGenerationError("project-state tasks must be sorted by task_id")
    return document


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MachineStateGenerationError(f"duplicate JSON member rejected: {key}")
        result[key] = value
    return result


def _validate_repo(value: object) -> None:
    if type(value) is not dict or set(value) != {"commit_sha", "tree_sha"}:
        raise MachineStateGenerationError("project-state repository object is invalid")
    repo = cast(dict[str, object], value)
    for field in ("commit_sha", "tree_sha"):
        item = repo[field]
        if type(item) is not str or _SHA40.fullmatch(item) is None:
            raise MachineStateGenerationError("project-state repository identity is invalid")


def _validate_sources(value: object) -> list[dict[str, object]]:
    if type(value) is not list or not value:
        raise MachineStateGenerationError("project-state sources must be a non-empty array")
    rows = cast(list[object], value)
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        if type(row) is not dict or set(row) != {"git_blob_sha", "path", "sha256"}:
            raise MachineStateGenerationError("project-state source object is invalid")
        item = cast(dict[str, object], row)
        path = item["path"]
        _validate_path(path)
        path_text = cast(str, path)
        if path_text in seen:
            raise MachineStateGenerationError("project-state source path is duplicated")
        seen.add(path_text)
        blob = item["git_blob_sha"]
        digest = item["sha256"]
        if (
            type(blob) is not str
            or _SHA40.fullmatch(blob) is None
            or type(digest) is not str
            or _SHA64.fullmatch(digest) is None
        ):
            raise MachineStateGenerationError("project-state source identity is invalid")
        result.append(item)
    paths = [cast(str, row["path"]) for row in result]
    if paths != sorted(paths):
        raise MachineStateGenerationError("project-state sources must be sorted by path")
    return result


def _validate_tasks(value: object) -> list[dict[str, object]]:
    if type(value) is not list:
        raise MachineStateGenerationError("project-state tasks must be an array")
    rows = cast(list[object], value)
    result: list[dict[str, object]] = []
    seen: set[str] = set()
    for row in rows:
        if type(row) is not dict or set(row) != {
            "dependencies",
            "evidence_refs",
            "state",
            "task_id",
        }:
            raise MachineStateGenerationError("project-state task object is invalid")
        item = cast(dict[str, object], row)
        task_id = item["task_id"]
        if (
            type(task_id) is not str
            or re.fullmatch(r"MRL-[0-9]{4}", task_id) is None
            or task_id in seen
        ):
            raise MachineStateGenerationError("project-state task_id is invalid or duplicated")
        seen.add(task_id)
        state = item["state"]
        if type(state) is not str or state not in _STATES:
            raise MachineStateGenerationError("project-state task state is invalid")
        dependencies = _string_array(
            item["dependencies"],
            "dependencies",
            True,
        )
        evidence = _string_array(
            item["evidence_refs"],
            "evidence_refs",
            False,
        )
        if task_id in dependencies:
            raise MachineStateGenerationError("project-state task cannot depend on itself")
        if state == "CLOSED_CANONICAL" and not evidence:
            raise MachineStateGenerationError("CLOSED_CANONICAL requires evidence_refs")
        if state != "CLOSED_CANONICAL" and evidence:
            raise MachineStateGenerationError("non-closed task cannot carry closure evidence_refs")
        result.append(item)
    return result


def _string_array(
    value: object,
    label: str,
    task_ids: bool,
) -> list[str]:
    if type(value) is not list:
        raise MachineStateGenerationError(f"project-state {label} must be an array")
    rows = cast(list[object], value)
    if any(type(row) is not str or not row for row in rows):
        raise MachineStateGenerationError(f"project-state {label} contains invalid text")
    strings = cast(list[str], rows)
    if task_ids and any(re.fullmatch(r"MRL-[0-9]{4}", row) is None for row in strings):
        raise MachineStateGenerationError(f"project-state {label} contains invalid task identity")
    if strings != sorted(strings) or len(strings) != len(set(strings)):
        raise MachineStateGenerationError(f"project-state {label} must be sorted and unique")
    return strings


def _validate_path(value: object) -> None:
    if (
        type(value) is not str
        or not value
        or len(value) > 4096
        or not value.isascii()
        or value.startswith("/")
        or "\\" in value
    ):
        raise MachineStateGenerationError("project-state source path is invalid")
    parts = value.split("/")
    if any(part in {"", ".", ".."} or _PATH_PART.fullmatch(part) is None for part in parts):
        raise MachineStateGenerationError("project-state source path is ambiguous")


def _load_source(root: Path, path: str) -> CanonicalSourceSnapshot:
    if _git(root, "cat-file", "-t", f"HEAD:{path}") != "blob":
        raise MachineStateGenerationError(f"canonical source is not a Git blob: {path}")
    payload = _git_bytes(root, "show", f"HEAD:{path}")
    try:
        content = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MachineStateGenerationError(f"canonical source is not UTF-8: {path}") from exc
    return CanonicalSourceSnapshot(
        path,
        _git(root, "rev-parse", f"HEAD:{path}"),
        hashlib.sha256(payload).hexdigest(),
        content,
    )


def _research_source(source: CanonicalSourceSnapshot) -> SourceBinding:
    return SourceBinding(
        source.path,
        source.git_blob_sha,
        source.sha256,
    )


def _cap_source(source: CanonicalSourceSnapshot) -> CapabilitySourceBinding:
    return CapabilitySourceBinding(
        source.path,
        source.git_blob_sha,
        source.sha256,
    )


def _git(root: Path, *arguments: str) -> str:
    try:
        return _git_bytes(root, *arguments).decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise MachineStateGenerationError("Git identity output was not ASCII") from exc


def _git_bytes(root: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(
            ("git", *arguments),
            cwd=root,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise MachineStateGenerationError(f"Git command failed: git {' '.join(arguments)}") from exc
    return completed.stdout


def _cells(line: str) -> tuple[str, ...]:
    if not line.startswith("|") or not line.endswith("|"):
        return ()
    cells = tuple(cell.strip() for cell in line[1:-1].split("|"))
    if cells and all(cell and set(cell) <= {"-", ":"} for cell in cells):
        return ()
    return cells


def _uncode(value: str) -> str:
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value


def _contains(text: str, fragment: str, path: str) -> None:
    if fragment not in text:
        raise MachineStateGenerationError(
            f"canonical source no longer matches derivation rule: {path}"
        )


def _check(output_dir: Path, rendered: MachineStateRenderSet) -> None:
    for name, expected in rendered.files():
        try:
            actual = (output_dir / name).read_bytes()
        except OSError as exc:
            raise MachineStateGenerationError(
                f"machine-state projection missing or unreadable: {name}"
            ) from exc
        if actual != expected:
            raise MachineStateGenerationError(f"machine-state projection drift detected: {name}")
    unexpected = sorted(
        path.name
        for path in output_dir.iterdir()
        if path.is_file() and path.name.endswith(".json") and path.name not in _OUTPUTS
    )
    if unexpected:
        raise MachineStateGenerationError(f"unexpected machine-state JSON output: {unexpected[0]}")
