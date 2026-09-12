#!/usr/bin/env python3
"""Produce or independently verify exact MRL-0804 hosted-runtime evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_MODULE = Path("src/medscale/mesc/_mrl_0804_runtime_v1.py")
_AUTH = Path("specs/mesc-experiment-0/mrl-0804-runtime-authorization-v1.json")
_PROBE = Path("scripts/mesc_mrl_0804_gpu_probe.py")
_SCRIPT = Path("scripts/mesc_mrl_0804_runtime_qualify.py")
_LOCK = Path("uv.lock")
_ARTIFACTS = {
    "observation": "runtime-observation.json",
    "smoke": "runtime-smoke.json",
    "identity": "runtime-identity.json",
    "qualification": "runtime-qualification-receipt.json",
    "evidence": "mrl-0804-real-preflight-evidence.json",
}


class EntrypointError(RuntimeError):
    """Raised when exact-source execution or artifact custody cannot be established."""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--observation", type=Path)
    parser.add_argument("--smoke", type=Path)
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
        raise EntrypointError("repository Git bytes cannot be resolved")
    return completed.stdout


def _require_clean_repository(root: Path) -> Path:
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
    for relative in (_MODULE, _AUTH, _PROBE, _SCRIPT, _LOCK):
        path = (repository / relative).resolve(strict=True)
        if path.is_symlink() or not path.is_file():
            raise EntrypointError(f"required source must be a regular file: {relative.as_posix()}")
        if path.read_bytes() != _git_bytes(repository, "show", f"HEAD:{relative.as_posix()}"):
            raise EntrypointError(f"repository bytes differ from exact HEAD: {relative.as_posix()}")
    return repository


def _require_authorized_lineage(repository: Path, authorization_raw: bytes) -> tuple[str, str]:
    try:
        document = json.loads(authorization_raw.decode("utf-8"))
        base = document["authorized_base"]
        base_sha = base["main_sha"]
        base_tree = base["main_tree"]
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


def _load_module(repository: Path) -> ModuleType:
    for name in tuple(sys.modules):
        if name == "medscale" or name.startswith("medscale."):
            raise EntrypointError(
                "preloaded medscale modules are prohibited before exact-source import"
            )
    source_root = str((repository / "src").resolve(strict=True))
    sys.path[:] = [entry for entry in sys.path if entry != source_root]
    sys.path.insert(0, source_root)
    module = importlib.import_module("medscale.mesc._mrl_0804_runtime_v1")
    module_file = getattr(module, "__file__", None)
    expected = (repository / _MODULE).resolve(strict=True)
    if type(module_file) is not str or Path(module_file).resolve(strict=True) != expected:
        raise EntrypointError("MRL-0804 qualifier imported from a non-canonical source")
    return module


def _require_external_file(path: Path, repository: Path, *, label: str) -> Path:
    resolved = path.expanduser().resolve(strict=True)
    if resolved.is_symlink() or not resolved.is_file():
        raise EntrypointError(f"{label} must be an existing regular non-symlink file")
    try:
        resolved.relative_to(repository)
    except ValueError:
        return resolved
    raise EntrypointError(f"{label} must remain outside the repository work tree")


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


def _read_regular_file(path: Path, *, label: str) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise EntrypointError(f"{label} must be a regular non-symlink file")
    before = path.stat(follow_symlinks=False)
    payload = path.read_bytes()
    after = path.stat(follow_symlinks=False)
    stable = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if not stable or len(payload) != after.st_size:
        raise EntrypointError(f"{label} changed while being read")
    return payload


def _write_new(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)


def _exact_source_identities(repository: Path) -> tuple[str, str]:
    lock_sha = hashlib.sha256((repository / _LOCK).read_bytes()).hexdigest()
    probe_sha = hashlib.sha256((repository / _PROBE).read_bytes()).hexdigest()
    return lock_sha, probe_sha


def _produce(
    *,
    repository: Path,
    module: ModuleType,
    output_root: Path,
    observation_path: Path,
    smoke_path: Path,
    repository_sha: str,
    repository_tree: str,
    lock_sha: str,
    probe_sha: str,
) -> Any:
    authorization_raw = (repository / _AUTH).read_bytes()
    authorization = module.parse_mrl_0804_runtime_authorization(authorization_raw)
    observation = _read_regular_file(observation_path, label="observation")
    smoke = _read_regular_file(smoke_path, label="smoke")
    result = module.qualify_mrl_0804_runtime(
        observation,
        smoke,
        authorization=authorization,
        repository_sha=repository_sha,
        repository_tree=repository_tree,
        dependency_lock_sha256=lock_sha,
        probe_source_sha256=probe_sha,
    )
    payloads = {
        "observation": result.observation_bytes,
        "smoke": result.smoke_receipt_bytes,
        "identity": result.runtime_identity_bytes,
        "qualification": result.qualification_receipt_bytes,
        "evidence": result.evidence_bytes,
    }
    for key, payload in payloads.items():
        _write_new(output_root / _ARTIFACTS[key], payload)
    return result


def _verify(
    *,
    repository: Path,
    module: ModuleType,
    output_root: Path,
    repository_sha: str,
    repository_tree: str,
    lock_sha: str,
    probe_sha: str,
) -> Any:
    authorization = module.parse_mrl_0804_runtime_authorization((repository / _AUTH).read_bytes())
    payloads = {
        key: _read_regular_file(output_root / name, label=name) for key, name in _ARTIFACTS.items()
    }
    return module.verify_mrl_0804_runtime_bundle(
        payloads["observation"],
        payloads["smoke"],
        authorization=authorization,
        repository_sha=repository_sha,
        repository_tree=repository_tree,
        dependency_lock_sha256=lock_sha,
        probe_source_sha256=probe_sha,
        runtime_identity_bytes=payloads["identity"],
        qualification_receipt_bytes=payloads["qualification"],
        evidence_bytes=payloads["evidence"],
    )


def main() -> int:
    args = _parser().parse_args()
    repository = _require_clean_repository(args.repository_root)
    authorization_raw = (repository / _AUTH).read_bytes()
    repository_sha, repository_tree = _require_authorized_lineage(repository, authorization_raw)
    lock_sha, probe_sha = _exact_source_identities(repository)
    module = _load_module(repository)
    output_root = _require_output_root(
        args.output_root, repository, verify_existing=args.verify_existing
    )

    if args.verify_existing:
        if args.observation is not None or args.smoke is not None:
            raise EntrypointError("verification mode reads observation/smoke from the exact bundle")
        result = _verify(
            repository=repository,
            module=module,
            output_root=output_root,
            repository_sha=repository_sha,
            repository_tree=repository_tree,
            lock_sha=lock_sha,
            probe_sha=probe_sha,
        )
        mode = "VERIFY_EXISTING"
    else:
        if args.observation is None or args.smoke is None:
            raise EntrypointError("production mode requires --observation and --smoke")
        observation_path = _require_external_file(args.observation, repository, label="observation")
        smoke_path = _require_external_file(args.smoke, repository, label="smoke")
        result = _produce(
            repository=repository,
            module=module,
            output_root=output_root,
            observation_path=observation_path,
            smoke_path=smoke_path,
            repository_sha=repository_sha,
            repository_tree=repository_tree,
            lock_sha=lock_sha,
            probe_sha=probe_sha,
        )
        mode = "PRODUCE"

    print(
        json.dumps(
            {
                "dependency_lock_sha256": lock_sha,
                "evidence_sha256": result.evidence_sha256,
                "mode": mode,
                "probe_source_sha256": probe_sha,
                "qualification_receipt_sha256": result.qualification_receipt_sha256,
                "repository_sha": repository_sha,
                "repository_tree": repository_tree,
                "runtime_identity_sha256": result.runtime_identity_sha256,
                "smoke_receipt_sha256": result.smoke_receipt_sha256,
                "task_id": "MRL-0804",
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
