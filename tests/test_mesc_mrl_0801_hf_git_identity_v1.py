"""Git self-attestation qualification tests for MRL-0801 acquisition."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from medscale.mesc import _mrl_0801_hf_acquisition_v1 as subject

MODULE_PATH = Path("src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py")


def git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def test_repository_execution_identity_is_derived_from_exact_git_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    module = root / MODULE_PATH
    module.parent.mkdir(parents=True)
    module.write_bytes(b'"""fixture acquisition executor."""\n')

    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "test"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)

    monkeypatch.setattr(subject, "__file__", str(module))
    identity = subject._capture_repository_execution_identity(root)

    assert identity.commit_sha == git(root, "rev-parse", "HEAD")
    assert identity.tree_sha == git(root, "rev-parse", "HEAD^{tree}")
    assert identity.source_sha256 == hashlib.sha256(module.read_bytes()).hexdigest()
