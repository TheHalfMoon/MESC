"""Deterministic generation/check engine for MRL machine-state projections.

MRL-0704 reads a fixed set of canonical sources from one exact Git commit, derives the
three MRL-7 projections, and renders canonical bytes. Generated views are
non-authoritative and are intentionally emitted outside their represented Git commit to
avoid self-referential commit hashing.

MRL-0705 owns CI drift/manual-edit enforcement. This module grants no execution,
training, promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

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
    "generate_machine_state",
    "load_canonical_snapshot",
]

_REGISTRY_PATH: Final = "docs/research/research_program_registry.md"
_QUESTIONS_PATH: Final = "docs/research/research_questions.md"
_ROADMAP_PATH: Final = "ROADMAP.md"
_RECONCILIATION_PATH: Final = "docs/strategy/mesc_pr122_post_b0_reconciliation_2026-08-19.md"
_TASKS_PATH: Final = "specs/mesc-research-loop-v1/tasks.md"
_SOURCE_PATHS: Final = (
    _ROADMAP_PATH,
    _REGISTRY_PATH,
    _QUESTIONS_PATH,
    _RECONCILIATION_PATH,
    _TASKS_PATH,
)
_OUTPUT_NAMES: Final = (
    "CAPABILITY_MATRIX.json",
    "PROJECT_STATE.json",
    "RESEARCH_PROGRAM_INDEX.json",
)
_TASK_PATTERN: Final = re.compile(r"^- \[([ x])\] \*\*(MRL-[0-9]{4}) — ")
_DEPENDENCY_PATTERN: Final = re.compile(r"MRL-([0-9]{4})(?:\.\.(?:MRL-)?([0-9]{4}))?")


class MachineStateGenerationError(ValueError):
    """Fail-closed error for canonical MRL machine-state generation/checking."""


@dataclass(frozen=True, slots=True)
class CanonicalSourceSnapshot:
    """One exact source as stored in the represented Git commit."""

    path: str
    git_blob_sha: str
    sha256: str
    content: str


@dataclass(frozen=True, slots=True)
class CanonicalRepositorySnapshot:
    """Fixed canonical inputs used to derive all MRL-7 projections."""

    commit_sha: str
    tree_sha: str
    sources: tuple[CanonicalSourceSnapshot, ...]

    def source(self, path: str) -> CanonicalSourceSnapshot:
        matches = tuple(source for source in self.sources if source.path == path)
        if len(matches) != 1:
            raise MachineStateGenerationError(f"canonical source missing or duplicated: {path}")
        return matches[0]


@dataclass(frozen=True, slots=True)
class MachineStateRenderSet:
    """Canonical bytes for all three projections represented by one Git commit."""

    commit_sha: str
    tree_sha: str
    capability_matrix: bytes
    project_state: bytes
    research_program_index: bytes

    def files(self) -> tuple[tuple[str, bytes], ...]:
        """Return projection files in deterministic filename order."""
        return (
            ("CAPABILITY_MATRIX.json", self.capability_matrix),
            ("PROJECT_STATE.json", self.project_state),
            ("RESEARCH_PROGRAM_INDEX.json", self.research_program_index),
        )


def load_canonical_snapshot(repository_root: Path) -> CanonicalRepositorySnapshot:
    """Read the fixed MRL-7 source set from the exact local Git HEAD commit."""
    root = repository_root.resolve()
    commit_sha = _run_git_text(root, "rev-parse", "HEAD")
    tree_sha = _run_git_text(root, "rev-parse", "HEAD^{tree}")
    sources = tuple(_load_source(root, path) for path in _SOURCE_PATHS)
    return CanonicalRepositorySnapshot(
        commit_sha=commit_sha,
        tree_sha=tree_sha,
        sources=sources,
    )


def generate_machine_state(
    repository_root: Path,
    output_dir: Path,
    *,
    check: bool = False,
) -> MachineStateRenderSet:
    """Generate projections or fail closed when existing outputs differ byte-for-byte."""
    snapshot = load_canonical_snapshot(repository_root)
    render_set = _render_snapshot(snapshot)
    destination = output_dir.resolve()
    if check:
        _check_outputs(destination, render_set)
    else:
        destination.mkdir(parents=True, exist_ok=True)
        for filename, payload in render_set.files():
            (destination / filename).write_bytes(payload)
    return render_set


def _render_snapshot(snapshot: CanonicalRepositorySnapshot) -> MachineStateRenderSet:
    research_program_index = _build_research_program_index(snapshot)
    capability_matrix = _build_capability_matrix(snapshot)
    project_state = _build_project_state(
        snapshot,
        research_program_index,
        capability_matrix,
    )
    return MachineStateRenderSet(
        commit_sha=snapshot.commit_sha,
        tree_sha=snapshot.tree_sha,
        capability_matrix=capability_matrix.semantic_bytes,
        project_state=project_state.semantic_bytes,
        research_program_index=research_program_index.semantic_bytes,
    )


def _build_research_program_index(
    snapshot: CanonicalRepositorySnapshot,
) -> ResearchProgramIndexProjection:
    registry = snapshot.source(_REGISTRY_PATH)
    questions_source = snapshot.source(_QUESTIONS_PATH)
    sources = tuple(
        sorted(
            (
                _research_source_binding(registry),
                _research_source_binding(questions_source),
            ),
            key=lambda item: item.path,
        )
    )
    questions = _parse_foundational_questions(registry.content)
    namespaces = _parse_namespaces(registry.content)
    return ResearchProgramIndexProjection(
        repository=RepositoryBinding(
            commit_sha=snapshot.commit_sha,
            tree_sha=snapshot.tree_sha,
        ),
        sources=sources,
        questions=questions,
        namespaces=namespaces,
    )


def _parse_foundational_questions(text: str) -> tuple[ResearchQuestionIndexEntry, ...]:
    rows: list[ResearchQuestionIndexEntry] = []
    for line in text.splitlines():
        cells = _table_cells(line)
        if len(cells) != 3 or not cells[0].startswith("`RQ"):
            continue
        question_id = _strip_code(cells[0])
        if question_id not in {f"RQ{index}" for index in range(1, 8)}:
            continue
        source_path = _strip_code(cells[1])
        status = cells[2].split("—", 1)[0].strip()
        rows.append(
            ResearchQuestionIndexEntry(
                question_id=question_id,
                program="Foundational MESC research",
                status=status,
                canonical_source_path=source_path,
            )
        )
    result = tuple(sorted(rows, key=lambda item: item.question_id))
    if tuple(item.question_id for item in result) != tuple(f"RQ{index}" for index in range(1, 8)):
        raise MachineStateGenerationError(
            "research registry must preserve exactly one RQ1-RQ7 foundational row"
        )
    return result


def _parse_namespaces(text: str) -> tuple[ResearchProgramNamespace, ...]:
    rows: list[ResearchProgramNamespace] = []
    in_namespace_table = False
    for line in text.splitlines():
        if line == "## Later-program namespaces":
            in_namespace_table = True
            continue
        if in_namespace_table and line.startswith("## "):
            break
        if not in_namespace_table:
            continue
        cells = _table_cells(line)
        if len(cells) != 5 or "<NNNN>" not in cells[1]:
            continue
        rows.append(
            ResearchProgramNamespace(
                program=cells[0],
                question_namespace=_strip_code(cells[1]),
                program_status=cells[2],
                canonical_source_paths=(_REGISTRY_PATH,),
                question_catalog_status=cells[4],
            )
        )
    if not rows:
        raise MachineStateGenerationError("research registry contains no later-program namespaces")
    return tuple(sorted(rows, key=lambda item: item.question_namespace))


def _build_capability_matrix(
    snapshot: CanonicalRepositorySnapshot,
) -> CapabilityMatrixProjection:
    roadmap = snapshot.source(_ROADMAP_PATH)
    reconciliation = snapshot.source(_RECONCILIATION_PATH)
    _require_text_fragment(
        roadmap.content,
        "| **T0** | Repository & engineering foundation | ✅ complete | — |",
        _ROADMAP_PATH,
    )
    _require_text_fragment(
        reconciliation.content,
        "`3f34b35daf4050d010a5f0061d6e8387f9649c10`",
        _RECONCILIATION_PATH,
    )
    _require_text_fragment(
        reconciliation.content,
        "- training/fine-tuning: NOT AUTHORIZED",
        _RECONCILIATION_PATH,
    )
    sources = tuple(
        sorted(
            (
                _capability_source_binding(roadmap),
                _capability_source_binding(reconciliation),
            ),
            key=lambda item: item.path,
        )
    )
    capabilities = (
        CapabilityMatrixEntry(
            capability_id="PILOT_01_B0_BASELINE",
            implementation_state="HISTORICAL",
            evidence_state="PROVEN",
            authority_state="NOT_APPLICABLE",
            canonical_source_paths=(_RECONCILIATION_PATH,),
            evidence_refs=("merge:3f34b35daf4050d010a5f0061d6e8387f9649c10",),
        ),
        CapabilityMatrixEntry(
            capability_id="T0_REPOSITORY_FOUNDATION",
            implementation_state="IMPLEMENTED",
            evidence_state="PROVEN",
            authority_state="NOT_APPLICABLE",
            canonical_source_paths=(_ROADMAP_PATH,),
            evidence_refs=("roadmap:T0",),
        ),
        CapabilityMatrixEntry(
            capability_id="TRAINING_EXECUTION",
            implementation_state="NOT_STARTED",
            evidence_state="UNPROVEN",
            authority_state="NOT_AUTHORIZED",
            canonical_source_paths=(_RECONCILIATION_PATH,),
        ),
    )
    return CapabilityMatrixProjection(
        repository=CapabilityRepositoryBinding(
            commit_sha=snapshot.commit_sha,
            tree_sha=snapshot.tree_sha,
        ),
        sources=sources,
        capabilities=capabilities,
    )


def _build_project_state(
    snapshot: CanonicalRepositorySnapshot,
    research_program_index: ResearchProgramIndexProjection,
    capability_matrix: CapabilityMatrixProjection,
) -> ProjectStateProjection:
    tasks = snapshot.source(_TASKS_PATH)
    records = _parse_task_records(tasks.content)
    checked = {task_id for task_id, is_checked, _ in records if is_checked}
    entries: list[ProjectStateEntry] = []
    for task_id, is_checked, dependencies in records:
        if is_checked:
            lifecycle_state = "CLOSED_CANONICAL"
            evidence_refs = (f"ledger:{tasks.git_blob_sha}:{task_id}",)
        elif all(dependency in checked for dependency in dependencies):
            lifecycle_state = "ELIGIBLE"
            evidence_refs = ()
        else:
            lifecycle_state = "PLANNED"
            evidence_refs = ()
        entries.append(
            ProjectStateEntry(
                state_id=task_id,
                lifecycle_state=lifecycle_state,
                canonical_source_paths=(_TASKS_PATH,),
                dependency_ids=dependencies,
                evidence_refs=evidence_refs,
            )
        )
    return ProjectStateProjection(
        research_program_index=research_program_index,
        capability_matrix=capability_matrix,
        sources=(
            ProjectStateSourceBinding(
                path=tasks.path,
                git_blob_sha=tasks.git_blob_sha,
                sha256=tasks.sha256,
            ),
        ),
        entries=tuple(entries),
    )


def _parse_task_records(text: str) -> tuple[tuple[str, bool, tuple[str, ...]], ...]:
    lines = text.splitlines()
    records: list[tuple[str, bool, tuple[str, ...]]] = []
    for index, line in enumerate(lines):
        match = _TASK_PATTERN.match(line)
        if match is None:
            continue
        task_id = match.group(2)
        block: list[str] = []
        cursor = index + 1
        while cursor < len(lines) and _TASK_PATTERN.match(lines[cursor]) is None:
            if lines[cursor].startswith("## ") or lines[cursor].startswith("### "):
                break
            block.append(lines[cursor])
            cursor += 1
        dependencies = _extract_dependencies(block, task_id)
        records.append((task_id, match.group(1) == "x", dependencies))
    identifiers = tuple(record[0] for record in records)
    if not identifiers or len(set(identifiers)) != len(identifiers):
        raise MachineStateGenerationError("MRL task ledger has missing or duplicate task IDs")
    known = set(identifiers)
    for task_id, _, dependencies in records:
        missing = tuple(dependency for dependency in dependencies if dependency not in known)
        if missing:
            raise MachineStateGenerationError(
                f"MRL task {task_id} references unknown dependency {missing[0]}"
            )
    return tuple(sorted(records, key=lambda item: item[0]))


def _extract_dependencies(lines: list[str], task_id: str) -> tuple[str, ...]:
    relevant = "\n".join(line for line in lines if "Depends on:" in line or "Requires:" in line)
    dependencies: set[str] = set()
    for match in _DEPENDENCY_PATTERN.finditer(relevant):
        start = int(match.group(1))
        end_text = match.group(2)
        if end_text is None:
            dependencies.add(f"MRL-{start:04d}")
            continue
        end = int(end_text)
        if end < start:
            raise MachineStateGenerationError("MRL dependency range is descending")
        dependencies.update(f"MRL-{value:04d}" for value in range(start, end + 1))
    dependencies.discard(task_id)
    return tuple(sorted(dependencies))


def _research_source_binding(source: CanonicalSourceSnapshot) -> SourceBinding:
    return SourceBinding(
        path=source.path,
        git_blob_sha=source.git_blob_sha,
        sha256=source.sha256,
    )


def _capability_source_binding(source: CanonicalSourceSnapshot) -> CapabilitySourceBinding:
    return CapabilitySourceBinding(
        path=source.path,
        git_blob_sha=source.git_blob_sha,
        sha256=source.sha256,
    )


def _load_source(root: Path, path: str) -> CanonicalSourceSnapshot:
    payload = _run_git_bytes(root, "show", f"HEAD:{path}")
    try:
        content = payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MachineStateGenerationError(f"canonical source is not UTF-8: {path}") from exc
    return CanonicalSourceSnapshot(
        path=path,
        git_blob_sha=_run_git_text(root, "rev-parse", f"HEAD:{path}"),
        sha256=hashlib.sha256(payload).hexdigest(),
        content=content,
    )


def _run_git_text(root: Path, *arguments: str) -> str:
    payload = _run_git_bytes(root, *arguments)
    try:
        return payload.decode("ascii").strip()
    except UnicodeDecodeError as exc:
        raise MachineStateGenerationError("Git identity output was not ASCII") from exc


def _run_git_bytes(root: Path, *arguments: str) -> bytes:
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


def _table_cells(line: str) -> tuple[str, ...]:
    if not line.startswith("|") or not line.endswith("|"):
        return ()
    cells = tuple(cell.strip() for cell in line[1:-1].split("|"))
    if cells and all(cell and set(cell) <= {"-", ":"} for cell in cells):
        return ()
    return cells


def _strip_code(value: str) -> str:
    if len(value) >= 2 and value.startswith("`") and value.endswith("`"):
        return value[1:-1]
    return value


def _require_text_fragment(text: str, fragment: str, path: str) -> None:
    if fragment not in text:
        raise MachineStateGenerationError(
            f"canonical source no longer matches frozen derivation rule: {path}"
        )


def _check_outputs(output_dir: Path, render_set: MachineStateRenderSet) -> None:
    for filename, expected in render_set.files():
        path = output_dir / filename
        try:
            actual = path.read_bytes()
        except OSError as exc:
            raise MachineStateGenerationError(
                f"machine-state projection missing or unreadable: {filename}"
            ) from exc
        if actual != expected:
            raise MachineStateGenerationError(
                f"machine-state projection drift detected: {filename}"
            )
    unexpected = tuple(
        sorted(
            path.name
            for path in output_dir.iterdir()
            if path.is_file() and path.name.endswith(".json") and path.name not in _OUTPUT_NAMES
        )
    )
    if unexpected:
        raise MachineStateGenerationError(f"unexpected machine-state JSON output: {unexpected[0]}")
