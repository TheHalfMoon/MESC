#!/usr/bin/env python3
"""Produce or independently verify exact MRL-0805 no-training authority evidence.

This control-plane entrypoint validates the live GitHub Founder/operator authority source,
requires an exact clean canonical repository checkout, and writes only deterministic,
path-free evidence artifacts outside the repository. It grants no training authority.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Final, cast

sys.dont_write_bytecode = True

_MODULE: Final = Path("src/medscale/mesc/_mrl_0805_no_training_authority_v1.py")
_AUTH: Final = Path("specs/mesc-experiment-0/mrl-0805-no-training-evaluation-authorization-v1.json")
_SCRIPT: Final = Path("scripts/mesc_mrl_0805_authority_qualify.py")
_EXPECTED_ISSUE: Final = 415
_EXPECTED_ISSUE_NODE: Final = "I_kwDOTT9yMs8AAAABRG46tw"
_EXPECTED_ISSUE_BODY_SHA256: Final = (
    "83252dc19f6b6950aa0f3ce69eee5f461a164c0ea2affdcacfc1eaf80d4d5caf"
)
_EXPECTED_ISSUE_CREATED_AT: Final = "2026-09-13T21:54:13Z"
_EXPECTED_OWNER: Final = "TheHalfMoon"
_ARTIFACTS: Final = {
    "subject": "authorization-subject.json",
    "receipt": "execution-authority-receipt.json",
    "evidence": "mrl-0805-real-preflight-evidence.json",
}


class EntrypointError(RuntimeError):
    """Raised when exact-source or external-authority validation fails closed."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--verify-existing", action="store_true")
    return parser


def _run(
    arguments: list[str],
    *,
    cwd: Path | None = None,
    binary: bool = False,
) -> subprocess.CompletedProcess[bytes] | subprocess.CompletedProcess[str]:
    return subprocess.run(
        arguments,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=not binary,
        encoding=None if binary else "utf-8",
    )


def _git_text(root: Path, *arguments: str) -> str:
    completed = cast(
        subprocess.CompletedProcess[str],
        _run(["git", "-C", str(root), *arguments]),
    )
    if completed.returncode != 0:
        raise EntrypointError("repository Git identity cannot be resolved")
    return completed.stdout


def _git_bytes(root: Path, *arguments: str) -> bytes:
    completed = cast(
        subprocess.CompletedProcess[bytes],
        _run(["git", "-C", str(root), *arguments], binary=True),
    )
    if completed.returncode != 0:
        raise EntrypointError("repository Git bytes cannot be resolved")
    return completed.stdout


def _require_clean_repository(root: Path) -> tuple[Path, str, str]:
    repository = root.expanduser().resolve(strict=True)
    top = Path(_git_text(repository, "rev-parse", "--show-toplevel").strip()).resolve(strict=True)
    if top != repository:
        raise EntrypointError("repository_root is not the exact Git work-tree root")
    if _git_text(repository, "status", "--porcelain", "--untracked-files=all").strip():
        raise EntrypointError("repository work tree must be clean before execution")
    if _git_text(repository, "clean", "-ndx").strip():
        raise EntrypointError("repository work tree must contain no ignored or untracked state")
    tagged = _git_text(repository, "ls-files", "-v", "-z")
    for record in tagged.split("\0"):
        if not record:
            continue
        tag = record[0]
        if tag == "S" or tag.islower():
            raise EntrypointError("repository contains an unsafe Git index flag")
    for relative in (_MODULE, _AUTH, _SCRIPT):
        path = (repository / relative).resolve(strict=True)
        if path.is_symlink() or not path.is_file():
            raise EntrypointError(f"required source must be a regular file: {relative.as_posix()}")
        if path.read_bytes() != _git_bytes(repository, "show", f"HEAD:{relative.as_posix()}"):
            raise EntrypointError(f"repository bytes differ from exact HEAD: {relative.as_posix()}")
    head = _git_text(repository, "rev-parse", "HEAD").strip()
    tree = _git_text(repository, "rev-parse", "HEAD^{tree}").strip()
    origin_main = _git_text(repository, "rev-parse", "origin/main").strip()
    if head != origin_main:
        raise EntrypointError("repository HEAD must equal the local origin/main identity")
    return repository, head, tree


def _load_module(repository: Path) -> ModuleType:
    for name in tuple(sys.modules):
        if name == "medscale" or name.startswith("medscale."):
            raise EntrypointError(
                "preloaded medscale modules are prohibited before exact-source import"
            )
    source_root = str((repository / "src").resolve(strict=True))
    sys.path[:] = [entry for entry in sys.path if entry != source_root]
    sys.path.insert(0, source_root)
    module = importlib.import_module("medscale.mesc._mrl_0805_no_training_authority_v1")
    module_file = getattr(module, "__file__", None)
    expected = (repository / _MODULE).resolve(strict=True)
    if type(module_file) is not str or Path(module_file).resolve(strict=True) != expected:
        raise EntrypointError("MRL-0805 qualifier imported from a non-canonical source")
    return module


def _require_authorized_lineage(
    repository: Path,
    module: ModuleType,
    authorization_raw: bytes,
    *,
    head: str,
) -> object:
    authorization = module.parse_mrl_0805_no_training_authorization(authorization_raw)
    base_sha = authorization.main_sha
    base_tree = authorization.main_tree
    if _git_text(repository, "rev-parse", f"{base_sha}^{{tree}}").strip() != base_tree:
        raise EntrypointError("authorization canonical base tree does not match Git history")
    ancestry = _run(["git", "-C", str(repository), "merge-base", "--is-ancestor", base_sha, head])
    if ancestry.returncode != 0:
        raise EntrypointError("repository HEAD is outside the authorized canonical-base lineage")
    return authorization


def _strict_object(raw: str, *, label: str) -> dict[str, object]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise EntrypointError(f"{label} is not valid JSON") from exc
    if type(value) is not dict:
        raise EntrypointError(f"{label} must be one JSON object")
    return cast(dict[str, object], value)


def _require_live_issue() -> None:
    completed = cast(
        subprocess.CompletedProcess[str],
        _run(["gh", "api", "repos/TheHalfMoon/MESC/issues/415"]),
    )
    if completed.returncode != 0:
        raise EntrypointError("live Founder/operator authority issue cannot be fetched")
    issue = _strict_object(completed.stdout, label="live authority issue")
    author = issue.get("user")
    if type(author) is not dict:
        raise EntrypointError("live authority issue author is malformed")
    if issue.get("number") != _EXPECTED_ISSUE or issue.get("node_id") != _EXPECTED_ISSUE_NODE:
        raise EntrypointError("live authority issue identity does not match authorization")
    if author.get("login") != _EXPECTED_OWNER or issue.get("author_association") != "OWNER":
        raise EntrypointError("live authority issue is not owned by the repository owner")
    if issue.get("created_at") != _EXPECTED_ISSUE_CREATED_AT:
        raise EntrypointError("live authority issue creation identity does not match authorization")
    body = issue.get("body")
    if type(body) is not str:
        raise EntrypointError("live authority issue body is malformed")
    if hashlib.sha256(body.encode("utf-8")).hexdigest() != _EXPECTED_ISSUE_BODY_SHA256:
        raise EntrypointError("live authority issue body digest does not match authorization")


def _require_output_root(path: Path, repository: Path, *, verify_existing: bool) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if resolved.is_symlink() or not resolved.is_dir():
        raise EntrypointError("output_root must be an existing regular directory")
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
                "verification output_root must contain exactly expected artifacts"
            )
    elif entries:
        raise EntrypointError("production output_root must be empty")
    return resolved


def _read_regular(path: Path, *, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise EntrypointError(f"{label} must be a regular non-symlink file")
    return path.read_bytes()


def _write_new(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)


def _result_document(
    result: Any,
    *,
    mode: str,
    repository_sha: str,
    repository_tree: str,
) -> dict[str, object]:
    return {
        "authorization_artifact_sha256": result.authorization_artifact_sha256,
        "authorization_subject_sha256": result.authorization_subject_sha256,
        "evidence_sha256": result.evidence_sha256,
        "execution_authority_receipt_sha256": result.execution_authority_receipt_sha256,
        "mode": mode,
        "repository_sha": repository_sha,
        "repository_tree": repository_tree,
        "training_authorized": False,
        "training_prohibited": True,
    }


def main() -> int:
    args = _parser().parse_args()
    repository, head, tree = _require_clean_repository(args.repository_root)
    _require_live_issue()
    module = _load_module(repository)
    authorization_raw = _read_regular(repository / _AUTH, label="authorization")
    _require_authorized_lineage(repository, module, authorization_raw, head=head)
    output_root = _require_output_root(
        args.output_root,
        repository,
        verify_existing=args.verify_existing,
    )
    if args.verify_existing:
        result = module.verify_mrl_0805_no_training_authority_bundle(
            authorization_raw,
            repository_sha=head,
            repository_tree=tree,
            authorization_subject_bytes=_read_regular(
                output_root / _ARTIFACTS["subject"],
                label="authorization subject",
            ),
            execution_authority_receipt_bytes=_read_regular(
                output_root / _ARTIFACTS["receipt"],
                label="execution authority receipt",
            ),
            evidence_bytes=_read_regular(
                output_root / _ARTIFACTS["evidence"],
                label="real-preflight evidence",
            ),
        )
        mode = "VERIFY_EXISTING"
    else:
        result = module.qualify_mrl_0805_no_training_authority(
            authorization_raw,
            repository_sha=head,
            repository_tree=tree,
        )
        _write_new(output_root / _ARTIFACTS["subject"], result.authorization_subject_bytes)
        _write_new(output_root / _ARTIFACTS["receipt"], result.execution_authority_receipt_bytes)
        _write_new(output_root / _ARTIFACTS["evidence"], result.evidence_bytes)
        mode = "PRODUCE"
    print(
        json.dumps(
            _result_document(result, mode=mode, repository_sha=head, repository_tree=tree),
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (EntrypointError, OSError, ValueError) as exc:
        print(f"MRL-0805 qualification blocked: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
