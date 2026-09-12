#!/usr/bin/env python3
"""Produce or independently verify exact MRL-0803 Experiment-0 isolation evidence."""

from __future__ import annotations

import argparse
import importlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import ModuleType
from typing import Any

_MODULE = Path("src/medscale/mesc/_mrl_0803_isolation_v1.py")
_AUTH = Path("specs/mesc-experiment-0/mrl-0803-isolation-authorization-v1.json")
_SCRIPT = Path("scripts/mesc_mrl_0803_isolation_qualify.py")
_ARTIFACTS = {
    "split_manifest_bytes": "split-manifest.json",
    "lineage_report_bytes": "lineage-report.json",
    "decontamination_report_bytes": "decontamination-report.json",
    "tier1_bytes": "tier1-search.jsonl",
    "tier2_bytes": "tier2-replication.jsonl",
    "tier3_bytes": "tier3-sealed.jsonl",
    "evidence_bytes": "mrl-0803-real-preflight-evidence.json",
}


class EntrypointError(RuntimeError):
    """Raised when exact-source execution or artifact custody cannot be established."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--verify-existing", action="store_true")
    return parser


def _git_text(root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        raise EntrypointError("repository Git identity cannot be resolved")
    return completed.stdout


def _git_bytes(root: Path, *arguments: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise EntrypointError("repository Git identity cannot be resolved")
    return completed.stdout


def _require_clean_repository(root: Path) -> Path:
    repository = root.resolve(strict=True)
    top = Path(_git_text(repository, "rev-parse", "--show-toplevel").strip()).resolve(strict=True)
    if top != repository:
        raise EntrypointError("repository_root is not the exact Git work-tree root")
    for arguments in (
        ("diff-files", "--quiet", "--"),
        ("diff-index", "--cached", "--quiet", "HEAD", "--"),
    ):
        completed = subprocess.run(
            ["git", "-C", str(repository), *arguments],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode != 0:
            raise EntrypointError("repository tracked bytes must match exact HEAD before execution")
    tagged = _git_text(repository, "ls-files", "-v", "-z")
    for record in tagged.split("\0"):
        if not record:
            continue
        tag = record[0]
        if tag == "S" or tag.islower():
            raise EntrypointError("repository contains an unsafe Git index flag")
    if _git_text(repository, "status", "--porcelain", "--untracked-files=all").strip():
        raise EntrypointError("repository work tree must be clean before execution")
    if _git_text(repository, "clean", "-ndx").strip():
        raise EntrypointError(
            "repository work tree must contain no ignored or untracked state before execution"
        )
    for relative in (_MODULE, _AUTH, _SCRIPT):
        path = (repository / relative).resolve(strict=True)
        if path.read_bytes() != _git_bytes(repository, "show", f"HEAD:{relative.as_posix()}"):
            raise EntrypointError(f"repository bytes differ from exact HEAD: {relative.as_posix()}")
    return repository


def _require_authorized_repository_identity(
    repository: Path, authorization_raw: bytes
) -> tuple[str, str]:
    try:
        document = json.loads(authorization_raw.decode("utf-8"))
        authorized_base = document["authorized_base"]
        base_sha = authorized_base["main_sha"]
        base_tree = authorized_base["main_tree"]
    except (KeyError, TypeError, UnicodeDecodeError, ValueError) as exc:
        raise EntrypointError("authorization lacks exact canonical base identity") from exc
    if type(base_sha) is not str or type(base_tree) is not str:
        raise EntrypointError("authorization canonical base identity is invalid")
    if _git_text(repository, "rev-parse", f"{base_sha}^{{tree}}").strip() != base_tree:
        raise EntrypointError("authorization canonical base tree does not match Git history")
    ancestry = subprocess.run(
        ["git", "-C", str(repository), "merge-base", "--is-ancestor", base_sha, "HEAD"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if ancestry.returncode != 0:
        raise EntrypointError("repository HEAD is outside the authorized canonical-base lineage")
    return (
        _git_text(repository, "rev-parse", "HEAD").strip(),
        _git_text(repository, "rev-parse", "HEAD^{tree}").strip(),
    )


def _require_loaded_medscale_modules_match_head(repository: Path) -> None:
    source_root = (repository / "src").resolve(strict=True)
    for name, module in tuple(sys.modules.items()):
        if name != "medscale" and not name.startswith("medscale."):
            continue
        if module is None:
            raise EntrypointError("loaded medscale module identity is unavailable")
        module_file = getattr(module, "__file__", None)
        if type(module_file) is not str:
            raise EntrypointError("loaded medscale module has no exact source file")
        try:
            resolved = Path(module_file).resolve(strict=True)
            relative = resolved.relative_to(source_root)
        except (OSError, ValueError):
            raise EntrypointError(
                "loaded medscale module is outside the exact checked-out repository source"
            ) from None
        repository_relative = Path("src") / relative
        if resolved.read_bytes() != _git_bytes(
            repository, "show", f"HEAD:{repository_relative.as_posix()}"
        ):
            raise EntrypointError("loaded medscale module bytes differ from the exact Git commit")


def _load_module(repository: Path) -> ModuleType:
    for name in tuple(sys.modules):
        if name == "medscale" or name.startswith("medscale."):
            raise EntrypointError(
                "preloaded medscale modules are prohibited before exact-source import"
            )
    source_root = str((repository / "src").resolve(strict=True))
    sys.path[:] = [entry for entry in sys.path if entry != source_root]
    sys.path.insert(0, source_root)
    module = importlib.import_module("medscale.mesc._mrl_0803_isolation_v1")
    module_file = getattr(module, "__file__", None)
    expected = (repository / _MODULE).resolve(strict=True)
    if type(module_file) is not str or Path(module_file).resolve(strict=True) != expected:
        raise EntrypointError("MRL-0803 executor imported from a non-canonical source")
    _require_loaded_medscale_modules_match_head(repository)
    return module


def _require_external_file(path: Path, repository: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise EntrypointError(f"{label} must be an existing regular file")
    try:
        resolved.relative_to(repository)
    except ValueError:
        return resolved
    raise EntrypointError(f"{label} must remain outside the repository work tree")


def _require_output_root(path: Path, repository: Path, *, verify_existing: bool) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_dir():
        raise EntrypointError("output_root must be an existing directory")
    try:
        resolved.relative_to(repository)
    except ValueError:
        pass
    else:
        raise EntrypointError("output_root must remain outside the repository work tree")
    entries = tuple(resolved.iterdir())
    if verify_existing:
        if {entry.name for entry in entries} != set(_ARTIFACTS.values()):
            raise EntrypointError(
                "verification output_root must contain exactly the expected artifacts"
            )
    elif entries:
        raise EntrypointError("production output_root must be empty")
    return resolved


def _write_new(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)


def _read_verification_artifacts(output_root: Path) -> dict[str, bytes]:
    supplied: dict[str, bytes] = {}
    for field, filename in _ARTIFACTS.items():
        artifact = output_root / filename
        if artifact.is_symlink() or not artifact.is_file():
            raise EntrypointError(
                f"verification artifact must be a regular non-symlink file: {filename}"
            )
        supplied[field] = artifact.read_bytes()
    return supplied


def _publish_bundle_atomically(output_root: Path, result: Any) -> None:
    parent = output_root.parent
    stage = Path(tempfile.mkdtemp(prefix=f".{output_root.name}.mrl0803-stage-", dir=parent))
    published = False
    try:
        for field, filename in _ARTIFACTS.items():
            _write_new(stage / filename, getattr(result, field))
        if output_root.is_symlink() or not output_root.is_dir():
            raise EntrypointError("production output_root changed before atomic publication")
        if any(output_root.iterdir()):
            raise EntrypointError("production output_root changed before atomic publication")
        stage.replace(output_root)
        published = True
    finally:
        if not published and stage.exists():
            shutil.rmtree(stage)


def _print_result(result: Any) -> None:
    print(f"split_manifest_sha256={result.split_manifest_sha256}")
    print(f"lineage_report_sha256={result.lineage_report_sha256}")
    print(f"decontamination_report_sha256={result.decontamination_report_sha256}")
    print(f"heldout_evaluation_sha256={result.heldout_evaluation_sha256}")
    print(f"evidence_sha256={result.evidence_sha256}")
    print("tier_counts=" + ",".join(str(value) for value in result.tier_counts))


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        repository = _require_clean_repository(args.repository_root)
        corpus_path = _require_external_file(args.corpus, repository, label="corpus")
        output_root = _require_output_root(
            args.output_root, repository, verify_existing=args.verify_existing
        )
        module = _load_module(repository)
        authorization_raw = (repository / _AUTH).read_bytes()
        repository_commit, repository_tree = _require_authorized_repository_identity(
            repository, authorization_raw
        )
        authorization = module.parse_mrl_0803_isolation_authorization(authorization_raw)
        corpus_bytes = corpus_path.read_bytes()
        if args.verify_existing:
            supplied = _read_verification_artifacts(output_root)
            result = module.verify_mrl_0803_isolation_bundle(
                corpus_bytes,
                authorization=authorization,
                repository_commit=repository_commit,
                repository_tree=repository_tree,
                **supplied,
            )
        else:
            result = module.qualify_mrl_0803_isolation(
                corpus_bytes,
                authorization=authorization,
                repository_commit=repository_commit,
                repository_tree=repository_tree,
            )
            _publish_bundle_atomically(output_root, result)
    except (EntrypointError, OSError, ValueError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    _print_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
