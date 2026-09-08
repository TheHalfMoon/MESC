"""Regression tests for retained, fail-closed MRL-0801 publication witnesses."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from medscale.mesc import _mrl_0801_hf_acquisition_v1 as subject
from medscale.mesc._mrl_0801_acquisition_custody_v1 import (
    parse_mrl_0801_acquisition_authorization,
)

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/mesc_mrl_0801_hf_acquire.py"
AUTH = ROOT / "specs/mesc-experiment-0/mrl-0801-acquisition-custody-authorization-v1.json"
MODEL = "google/gemma-4-31B-it"
REVISION = "842da3794eaa0b77d5f08bae87a17459d91ff475"
IDENTITY = subject.RepositoryExecutionIdentity("9" * 40, "8" * 40, "7" * 64)
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


class NeverTransport:
    def __init__(self) -> None:
        self.metadata_calls = 0
        self.download_calls = 0

    def metadata(
        self,
        *,
        model_id: str,
        revision: str,
        path: str,
    ) -> subject.HfRemoteFileMetadata:
        self.metadata_calls += 1
        raise AssertionError(f"unexpected remote metadata access: {model_id}@{revision}:{path}")

    def iter_bytes(self, *, metadata: subject.HfRemoteFileMetadata) -> Any:
        self.download_calls += 1
        raise AssertionError(f"unexpected remote byte access: {metadata.path}")


def test_model_capability_witness_is_retained_and_blocks(tmp_path: Path) -> None:
    destination = tmp_path / "assets"
    destination.mkdir()
    root_fd = _open_directory(destination)
    try:
        with pytest.raises(subject.MRL0801HfAcquisitionError, match="witness retained"):
            subject._probe_atomic_descriptor_publication(root_fd=root_fd)
    finally:
        os.close(root_fd)

    witnesses = tuple(destination.glob(".mrl-0801-publication-witness-*"))
    assert len(witnesses) == 1
    assert witnesses[0].is_file()
    assert witnesses[0].read_bytes() == b""


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
            os.rename(
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
        with pytest.raises(subject.MRL0801HfAcquisitionError, match="witness retained"):
            subject._probe_atomic_descriptor_publication(root_fd=root_fd)
    finally:
        os.close(root_fd)

    assert raced
    assert (destination / raced["name"]).read_bytes() == b"foreign"
    assert (destination / raced["owned_name"]).read_bytes() == b""


def test_successful_model_capability_proof_blocks_before_remote_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "assets"
    destination.mkdir()
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / ".git").mkdir()
    transport = NeverTransport()
    authorization = parse_mrl_0801_acquisition_authorization(AUTH.read_bytes())
    monkeypatch.setattr(subject, "_capture_repository_execution_identity", lambda _: IDENTITY)

    with pytest.raises(subject.MRL0801HfAcquisitionError, match="remote access is blocked"):
        subject.acquire_mrl_0801_hf_candidate(
            authorization=authorization,
            transport=transport,
            repository_root=repository,
            destination=destination,
            model_id=MODEL,
            revision=REVISION,
        )

    assert transport.metadata_calls == 0
    assert transport.download_calls == 0
    witnesses = tuple(destination.glob(".mrl-0801-publication-witness-*"))
    assert len(witnesses) == 1
    assert witnesses[0].read_bytes() == b""


def test_receipt_capability_witness_is_retained_and_blocks(tmp_path: Path) -> None:
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
        with pytest.raises(cli.AcquisitionEntrypointError, match="witness retained"):
            cli._probe_receipt_atomic_publication(output)
    finally:
        os.close(descriptor)

    witnesses = tuple(receipt_parent.glob(".mrl-0801-receipt-witness-*"))
    assert len(witnesses) == 1
    assert witnesses[0].is_file()
    assert witnesses[0].read_bytes() == b""
    assert not (receipt_parent / "receipt.json").exists()


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
            os.rename(
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
        with pytest.raises(cli.AcquisitionEntrypointError, match="witness retained"):
            cli._probe_receipt_atomic_publication(output)
    finally:
        os.close(descriptor)

    assert raced
    assert (receipt_parent / raced["name"]).read_bytes() == b"foreign"
    assert (receipt_parent / raced["owned_name"]).read_bytes() == b""
    assert not (receipt_parent / "receipt.json").exists()


def test_receipt_binding_blocks_after_witness_without_creating_receipt(tmp_path: Path) -> None:
    cli = load_cli()
    repository = tmp_path / "repo"
    repository.mkdir()
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    receipt_parent = tmp_path / "receipts"
    receipt_parent.mkdir()
    receipt = receipt_parent / "receipt.json"

    with pytest.raises(cli.AcquisitionEntrypointError, match="acquisition is blocked"):
        cli._require_external_new_output(
            path=receipt,
            repository_root=repository,
            snapshot_root=snapshot,
        )

    assert not receipt.exists()
    witnesses = tuple(receipt_parent.glob(".mrl-0801-receipt-witness-*"))
    assert len(witnesses) == 1
    assert witnesses[0].read_bytes() == b""
