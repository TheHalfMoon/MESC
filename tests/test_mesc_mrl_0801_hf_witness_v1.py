"""Regression tests for retained MRL-0801 atomic-publication witnesses."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from medscale.mesc import _mrl_0801_hf_acquisition_v1 as subject

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/mesc_mrl_0801_hf_acquire.py"
_O_TMPFILE = os.__dict__.get("O_TMPFILE", 0)
_O_DIRECTORY = os.__dict__.get("O_DIRECTORY", 0)
_O_CLOEXEC = os.__dict__.get("O_CLOEXEC", 0)

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or _O_TMPFILE == 0 or _O_DIRECTORY == 0,
    reason="requires Linux O_TMPFILE and descriptor-relative directory support",
)


def load_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mesc_mrl_0801_hf_witness_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _open_directory(path: Path) -> int:
    return os.open(path, os.O_RDONLY | _O_DIRECTORY | _O_CLOEXEC)


def _skip_if_native_witness_is_unavailable(error: Exception) -> None:
    text = str(error)
    if "unsupported on this filesystem" in text or "unavailable" in text:
        pytest.skip(text)
    raise error


def test_model_capability_witness_is_retained_outside_destination(tmp_path: Path) -> None:
    destination = tmp_path / "assets"
    destination.mkdir()
    root_fd = _open_directory(destination)
    try:
        try:
            subject._probe_atomic_descriptor_publication(root_fd=root_fd)
        except subject.MRL0801HfAcquisitionError as error:
            _skip_if_native_witness_is_unavailable(error)
    finally:
        os.close(root_fd)

    witnesses = tuple(tmp_path.glob(".mrl-0801-publication-witness-*"))
    assert len(witnesses) == 1
    assert witnesses[0].is_file()
    assert witnesses[0].read_bytes() == b""
    assert list(destination.iterdir()) == []


def test_model_capability_witness_foreign_replacement_is_never_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "assets"
    destination.mkdir()
    original_stat = subject._descriptor_entry_stat
    raced: dict[str, str] = {}

    def replace_after_identity_check(*, root_fd: int, name: str) -> os.stat_result | None:
        observed = original_stat(root_fd=root_fd, name=name)
        if (
            observed is not None
            and name.startswith(".mrl-0801-publication-witness-")
            and not raced
        ):
            owned_name = f"{name}.owned"
            os.rename(  # noqa: PTH104 -- descriptor-relative race injection is required
                name,
                owned_name,
                src_dir_fd=root_fd,
                dst_dir_fd=root_fd,
            )
            foreign_fd = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=root_fd,
            )
            try:
                os.write(foreign_fd, b"foreign")
            finally:
                os.close(foreign_fd)
            raced["name"] = name
            raced["owned_name"] = owned_name
        return observed

    monkeypatch.setattr(subject, "_descriptor_entry_stat", replace_after_identity_check)
    root_fd = _open_directory(destination)
    try:
        try:
            subject._probe_atomic_descriptor_publication(root_fd=root_fd)
        except subject.MRL0801HfAcquisitionError as error:
            _skip_if_native_witness_is_unavailable(error)
    finally:
        os.close(root_fd)

    assert raced
    assert (tmp_path / raced["name"]).read_bytes() == b"foreign"
    assert (tmp_path / raced["owned_name"]).read_bytes() == b""
    assert list(destination.iterdir()) == []


def test_receipt_capability_witness_is_retained_outside_receipt_parent(tmp_path: Path) -> None:
    cli = load_cli()
    receipt_parent = tmp_path / "receipts"
    receipt_parent.mkdir()
    descriptor = _open_directory(receipt_parent)
    opened = os.fstat(descriptor)
    output = cli._BoundReceiptOutput(
        path=receipt_parent / "receipt.json",
        parent_path=receipt_parent,
        descriptor=descriptor,
        device=opened.st_dev,
        inode=opened.st_ino,
        name="receipt.json",
    )
    try:
        try:
            cli._probe_receipt_atomic_publication(output)
        except cli.AcquisitionEntrypointError as error:
            _skip_if_native_witness_is_unavailable(error)
    finally:
        os.close(descriptor)

    witnesses = tuple(tmp_path.glob(".mrl-0801-receipt-witness-*"))
    assert len(witnesses) == 1
    assert witnesses[0].is_file()
    assert witnesses[0].read_bytes() == b""
    assert list(receipt_parent.iterdir()) == []


def test_receipt_capability_witness_foreign_replacement_is_never_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = load_cli()
    receipt_parent = tmp_path / "receipts"
    receipt_parent.mkdir()
    original_stat = cli._descriptor_output_stat
    raced: dict[str, str] = {}

    def replace_after_identity_check(output: Any) -> os.stat_result | None:
        observed = original_stat(output)
        name = output.name
        descriptor = output.descriptor
        if (
            observed is not None
            and name.startswith(".mrl-0801-receipt-witness-")
            and not raced
        ):
            owned_name = f"{name}.owned"
            os.rename(  # noqa: PTH104 -- descriptor-relative race injection is required
                name,
                owned_name,
                src_dir_fd=descriptor,
                dst_dir_fd=descriptor,
            )
            foreign_fd = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=descriptor,
            )
            try:
                os.write(foreign_fd, b"foreign")
            finally:
                os.close(foreign_fd)
            raced["name"] = name
            raced["owned_name"] = owned_name
        return observed

    monkeypatch.setattr(cli, "_descriptor_output_stat", replace_after_identity_check)
    descriptor = _open_directory(receipt_parent)
    opened = os.fstat(descriptor)
    output = cli._BoundReceiptOutput(
        path=receipt_parent / "receipt.json",
        parent_path=receipt_parent,
        descriptor=descriptor,
        device=opened.st_dev,
        inode=opened.st_ino,
        name="receipt.json",
    )
    try:
        try:
            cli._probe_receipt_atomic_publication(output)
        except cli.AcquisitionEntrypointError as error:
            _skip_if_native_witness_is_unavailable(error)
    finally:
        os.close(descriptor)

    assert raced
    assert (tmp_path / raced["name"]).read_bytes() == b"foreign"
    assert (tmp_path / raced["owned_name"]).read_bytes() == b""
    assert list(receipt_parent.iterdir()) == []
