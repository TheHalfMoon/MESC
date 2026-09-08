"""CLI boundary tests for MRL-0801 public acquisition."""

from __future__ import annotations

import importlib.util
import os
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


def clear_medscale_modules(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in tuple(sys.modules):
        if name == "medscale" or name.startswith("medscale."):
            monkeypatch.delitem(sys.modules, name, raising=False)


def test_dirty_tracked_repository_is_rejected_before_import(tmp_path: Path) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    module = root / "src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py"
    module.write_text("x = 2\n", encoding="utf-8")
    with pytest.raises(cli.AcquisitionEntrypointError, match="clean"):
        cli._require_clean_repository_before_import(root)


def test_untracked_repository_bytes_are_rejected_before_import(tmp_path: Path) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    (root / "src/medscale/mesc/untracked.py").write_text("x = 1\n", encoding="utf-8")
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


def test_receipt_output_parent_must_preexist_without_filesystem_mutation(tmp_path: Path) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    missing_root = tmp_path / "missing"
    receipt = missing_root / "receipts/receipt.json"

    assert not missing_root.exists()
    with pytest.raises(cli.AcquisitionEntrypointError, match="parent must already exist"):
        cli._require_external_new_output(
            path=receipt,
            repository_root=root,
            snapshot_root=snapshot,
        )

    assert not missing_root.exists()
    assert not (root / "receipts").exists()
    assert not (snapshot / "receipts").exists()


def test_receipt_atomic_publication_capability_is_verified_before_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    receipt = tmp_path / "receipts/receipt.json"
    receipt.parent.mkdir()
    witness_dir = tmp_path / "receipt-witnesses"
    witness_dir.mkdir()
    output = cli._require_external_new_output(
        path=receipt,
        repository_root=root,
        snapshot_root=snapshot,
    )
    witness = cli._require_external_witness_root(
        path=witness_dir,
        repository_root=root,
        snapshot_root=snapshot,
    )

    def unsupported_publication(**_: object) -> None:
        raise cli.AcquisitionEntrypointError(
            "atomic receipt publication is unsupported on this filesystem"
        )

    monkeypatch.setattr(cli, "_publish_open_descriptor_no_replace", unsupported_publication)
    try:
        with pytest.raises(cli.AcquisitionEntrypointError, match="atomic receipt publication"):
            cli._probe_receipt_atomic_publication(output, witness)
        assert not receipt.exists()
        assert list(witness_dir.iterdir()) == []
    finally:
        os.close(witness.descriptor)
        os.close(output.descriptor)


def test_receipt_target_race_after_capability_probe_is_rejected(
    tmp_path: Path,
) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    receipt = tmp_path / "receipts/receipt.json"
    receipt.parent.mkdir()
    witness_dir = tmp_path / "receipt-witnesses"
    witness_dir.mkdir()
    output = cli._require_external_new_output(
        path=receipt,
        repository_root=root,
        snapshot_root=snapshot,
    )
    witness = cli._require_external_witness_root(
        path=witness_dir,
        repository_root=root,
        snapshot_root=snapshot,
    )
    try:
        cli._probe_receipt_atomic_publication(output, witness)
        receipt.write_bytes(b"foreign")
        with pytest.raises(cli.AcquisitionEntrypointError, match="must not already exist"):
            cli._write_exact_new(output, b"ours")
        assert receipt.read_bytes() == b"foreign"
        assert len(tuple(witness_dir.glob(".mrl-0801-receipt-witness-*"))) == 1
    finally:
        os.close(witness.descriptor)
        os.close(output.descriptor)


def test_receipt_witness_root_inside_foreign_git_work_tree_is_rejected(tmp_path: Path) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    foreign = tmp_path / "foreign-repo"
    foreign.mkdir()
    (foreign / ".git").mkdir()
    witness = foreign / "witnesses"
    witness.mkdir()

    with pytest.raises(cli.AcquisitionEntrypointError, match="Git work tree"):
        cli._require_external_witness_root(
            path=witness,
            repository_root=root,
            snapshot_root=snapshot,
        )


def test_receipt_output_is_published_descriptor_relative(tmp_path: Path) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    receipt = tmp_path / "receipts/receipt.json"
    receipt.parent.mkdir()
    output = cli._require_external_new_output(
        path=receipt,
        repository_root=root,
        snapshot_root=snapshot,
    )
    try:
        cli._write_exact_new(output, b"{}")
        assert receipt.read_bytes() == b"{}"
    finally:
        os.close(output.descriptor)


def test_receipt_output_parent_swap_cannot_redirect_publication_into_repo(tmp_path: Path) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    receipt_parent = tmp_path / "receipts"
    receipt_parent.mkdir()
    receipt = receipt_parent / "receipt.json"
    output = cli._require_external_new_output(
        path=receipt,
        repository_root=root,
        snapshot_root=snapshot,
    )
    original_parent = tmp_path / "receipts-original"
    receipt_parent.rename(original_parent)
    receipt_parent.symlink_to(root, target_is_directory=True)
    try:
        with pytest.raises(cli.AcquisitionEntrypointError, match="parent changed"):
            cli._write_exact_new(output, b"{}")
        assert not (root / "receipt.json").exists()
        assert not (original_parent / "receipt.json").exists()
    finally:
        os.close(output.descriptor)


def test_receipt_cleanup_preserves_foreign_racing_entry(tmp_path: Path) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    receipt = tmp_path / "receipts/receipt.json"
    receipt.parent.mkdir()
    output = cli._require_external_new_output(
        path=receipt,
        repository_root=root,
        snapshot_root=snapshot,
    )
    receipt.write_bytes(b"foreign")
    try:
        with pytest.raises(cli.AcquisitionEntrypointError, match="must not already exist"):
            cli._write_exact_new(output, b"ours")
        assert receipt.read_bytes() == b"foreign"
    finally:
        os.close(output.descriptor)


def test_receipt_publication_race_preserves_foreign_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    receipt = tmp_path / "receipts/receipt.json"
    receipt.parent.mkdir()
    output = cli._require_external_new_output(
        path=receipt,
        repository_root=root,
        snapshot_root=snapshot,
    )
    original_publish = cli._publish_open_descriptor_no_replace

    def race(*, source_fd: int, output: object) -> None:
        receipt.write_bytes(b"foreign")
        original_publish(source_fd=source_fd, output=output)

    monkeypatch.setattr(cli, "_publish_open_descriptor_no_replace", race)
    try:
        with pytest.raises(cli.AcquisitionEntrypointError, match="must not already exist"):
            cli._write_exact_new(output, b"ours")
        assert receipt.read_bytes() == b"foreign"
    finally:
        os.close(output.descriptor)


def test_any_preloaded_medscale_module_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    clear_medscale_modules(monkeypatch)
    foreign = tmp_path / "foreign/medscale/__init__.py"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("", encoding="utf-8")
    foreign_module = ModuleType("medscale")
    foreign_module.__file__ = str(foreign)
    monkeypatch.setitem(sys.modules, "medscale", foreign_module)
    with pytest.raises(cli.AcquisitionEntrypointError, match="preloaded medscale modules"):
        cli._import_exact_repository_modules(root)


def test_preloaded_transitive_medscale_module_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    clear_medscale_modules(monkeypatch)
    foreign = tmp_path / "foreign/_canonical_json_v1.py"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("", encoding="utf-8")
    foreign_module = ModuleType("medscale.mesc._canonical_json_v1")
    foreign_module.__file__ = str(foreign)
    monkeypatch.setitem(sys.modules, "medscale.mesc._canonical_json_v1", foreign_module)
    with pytest.raises(cli.AcquisitionEntrypointError, match="preloaded medscale modules"):
        cli._import_exact_repository_modules(root)


def test_exact_source_root_is_repositioned_first(monkeypatch: pytest.MonkeyPatch) -> None:
    cli = load_cli()
    exact_source = "/repo/src"
    foreign_source = "/foreign"
    monkeypatch.setattr(sys, "path", [foreign_source, exact_source, "/other", exact_source])

    cli._prepend_exact_source_root(exact_source)

    assert sys.path[0] == exact_source
    assert sys.path.count(exact_source) == 1
    assert sys.path[1] == foreign_source
