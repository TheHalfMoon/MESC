"""CLI boundary tests for MRL-0801 public acquisition."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/mesc_mrl_0801_hf_acquire.py"


def load_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mesc_mrl_0801_hf_acquire_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "test"], check=True)
    module = root / "src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py"
    module.parent.mkdir(parents=True)
    module.write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)
    return root


def test_dirty_tracked_repository_is_rejected_before_import(tmp_path: Path) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    module = root / "src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py"
    module.write_text("x = 2\n", encoding="utf-8")
    with pytest.raises(cli.AcquisitionEntrypointError, match="clean"):
        cli._require_clean_repository_before_import(root)


def test_receipt_outputs_must_be_outside_repo_snapshot_and_symlinks(tmp_path: Path) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    with pytest.raises(cli.AcquisitionEntrypointError, match="outside the repository"):
        cli._require_external_new_output(
            path=root / "receipt.json",
            repository_root=root,
            snapshot_root=snapshot,
        )
    with pytest.raises(cli.AcquisitionEntrypointError, match="outside the raw snapshot"):
        cli._require_external_new_output(
            path=snapshot / "receipt.json",
            repository_root=root,
            snapshot_root=snapshot,
        )
    target = tmp_path / "target"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target, target_is_directory=True)
    with pytest.raises(cli.AcquisitionEntrypointError, match="symbolic link"):
        cli._require_external_new_output(
            path=link / "receipt.json",
            repository_root=root,
            snapshot_root=snapshot,
        )


def test_preloaded_medscale_from_other_source_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    foreign = tmp_path / "foreign/medscale/__init__.py"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("", encoding="utf-8")
    foreign_module = ModuleType("medscale")
    foreign_module.__file__ = str(foreign)
    monkeypatch.setitem(sys.modules, "medscale", foreign_module)
    with pytest.raises(cli.AcquisitionEntrypointError, match="outside"):
        cli._import_exact_repository_modules(root)


def test_nonexistent_preloaded_module_path_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    missing_module = ModuleType("medscale")
    missing_module.__file__ = str(tmp_path / "missing.py")
    monkeypatch.setitem(sys.modules, "medscale", missing_module)
    with pytest.raises(cli.AcquisitionEntrypointError, match="outside"):
        cli._import_exact_repository_modules(root)


def test_rollback_only_removes_exact_completed_snapshot_files(tmp_path: Path) -> None:
    cli = load_cli()
    root = tmp_path / "snapshot"
    root.mkdir()
    created = root / "model.safetensors.index.json"
    created.write_text("x", encoding="utf-8")
    unrelated = root / "keep.txt"
    unrelated.write_text("keep", encoding="utf-8")
    cli._rollback_completed_snapshot(root, (created.name,))
    assert not created.exists()
    assert unrelated.read_text(encoding="utf-8") == "keep"
