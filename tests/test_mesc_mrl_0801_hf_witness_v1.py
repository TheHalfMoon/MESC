"""ADR-0037 regressions for external retained publication witnesses."""

from __future__ import annotations

import importlib.util
import os
import stat
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

from medscale.mesc import _mrl_0801_hf_acquisition_v1 as subject
from medscale.mesc._mrl_0801_acquisition_custody_v1 import parse_mrl_0801_acquisition_authorization

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/mesc_mrl_0801_hf_acquire.py"
AUTH = ROOT / "specs/mesc-experiment-0/mrl-0801-acquisition-custody-authorization-v1.json"
MODEL = "google/gemma-4-31B-it"
REVISION = "842da3794eaa0b77d5f08bae87a17459d91ff475"
IDENTITY = subject.RepositoryExecutionIdentity("9" * 40, "8" * 40, "7" * 64)
_O_DIRECTORY = os.__dict__.get("O_DIRECTORY", 0)
_O_CLOEXEC = os.__dict__.get("O_CLOEXEC", 0)
_O_TMPFILE = os.__dict__.get("O_TMPFILE", 0)

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


def fake_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    (root / ".git").mkdir()
    return root


class MarkerTransport:
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
        raise RuntimeError(f"metadata-reached:{model_id}@{revision}:{path}")

    def iter_bytes(self, *, metadata: subject.HfRemoteFileMetadata) -> Iterator[bytes]:
        self.download_calls += 1
        yield b"unexpected"


def test_model_capability_witness_is_external_retained_and_destination_stays_empty(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "assets"
    destination.mkdir()
    witness_dir = tmp_path / "witnesses"
    witness_dir.mkdir()
    repository = fake_repo(tmp_path)
    destination_root = subject._require_external_empty_destination(
        destination=destination,
        repository_root=repository,
    )
    witness = subject._require_external_witness_root(
        witness_root=witness_dir,
        repository_root=repository,
        transaction_root=destination_root,
    )
    try:
        name = subject._probe_atomic_descriptor_publication(
            source_root_fd=destination_root.descriptor,
            witness_root=witness,
        )
        assert name.startswith(".mrl-0801-publication-witness-")
        assert list(destination.iterdir()) == []
        assert (witness_dir / name).read_bytes() == b""
    finally:
        os.close(witness.descriptor)
        os.close(destination_root.descriptor)


def test_successful_model_capability_proof_permits_metadata_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "assets"
    destination.mkdir()
    witness_dir = tmp_path / "witnesses"
    witness_dir.mkdir()
    repository = fake_repo(tmp_path)
    transport = MarkerTransport()
    authorization = parse_mrl_0801_acquisition_authorization(AUTH.read_bytes())
    monkeypatch.setattr(subject, "_capture_repository_execution_identity", lambda _: IDENTITY)

    with pytest.raises(RuntimeError, match="metadata-reached"):
        subject.acquire_mrl_0801_hf_candidate(
            authorization=authorization,
            transport=transport,
            repository_root=repository,
            destination=destination,
            witness_root=witness_dir,
            model_id=MODEL,
            revision=REVISION,
        )

    assert transport.metadata_calls == 1
    assert transport.download_calls == 0
    assert list(destination.iterdir()) == []
    assert len(tuple(witness_dir.glob(".mrl-0801-publication-witness-*"))) == 1


def test_model_witness_root_device_mismatch_is_rejected_before_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "assets"
    destination.mkdir()
    witness_dir = tmp_path / "witnesses"
    witness_dir.mkdir()
    repository = fake_repo(tmp_path)
    destination_root = subject._require_external_empty_destination(
        destination=destination,
        repository_root=repository,
    )
    witness_root = subject._require_external_witness_root(
        witness_root=witness_dir,
        repository_root=repository,
        transaction_root=destination_root,
    )
    real_fstat = os.fstat

    def mismatched(fd: int) -> os.stat_result:
        observed = real_fstat(fd)
        if not stat.S_ISREG(observed.st_mode):
            return observed
        values = list(observed)
        values[2] = observed.st_dev + 1
        return os.stat_result(values)

    monkeypatch.setattr(subject.os, "fstat", mismatched)
    try:
        with pytest.raises(subject.MRL0801HfAcquisitionError, match="transaction filesystem"):
            subject._probe_atomic_descriptor_publication(
                source_root_fd=destination_root.descriptor,
                witness_root=witness_root,
            )
    finally:
        os.close(witness_root.descriptor)
        os.close(destination_root.descriptor)


def test_model_witness_foreign_replacement_is_never_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "assets"
    destination.mkdir()
    witness_dir = tmp_path / "witnesses"
    witness_dir.mkdir()
    repository = fake_repo(tmp_path)
    destination_root = subject._require_external_empty_destination(
        destination=destination,
        repository_root=repository,
    )
    witness = subject._require_external_witness_root(
        witness_root=witness_dir,
        repository_root=repository,
        transaction_root=destination_root,
    )
    original_stat = subject._descriptor_entry_stat
    raced: dict[str, str] = {}

    def replace_after_identity(*, root_fd: int, name: str) -> os.stat_result | None:
        observed = original_stat(root_fd=root_fd, name=name)
        if observed is not None and name.startswith(".mrl-0801-publication-witness-") and not raced:
            owned_name = f"{name}.owned"
            os.rename(name, owned_name, src_dir_fd=root_fd, dst_dir_fd=root_fd)
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
            raced["owned"] = owned_name
        return observed

    monkeypatch.setattr(subject, "_descriptor_entry_stat", replace_after_identity)
    try:
        subject._probe_atomic_descriptor_publication(
            source_root_fd=destination_root.descriptor,
            witness_root=witness,
        )
    finally:
        os.close(witness.descriptor)
        os.close(destination_root.descriptor)

    assert (witness_dir / raced["name"]).read_bytes() == b"foreign"
    assert (witness_dir / raced["owned"]).read_bytes() == b""
    assert list(destination.iterdir()) == []


def test_receipt_capability_witness_is_external_and_retained(tmp_path: Path) -> None:
    cli = load_cli()
    repository = tmp_path / "repo"
    repository.mkdir()
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    receipt_parent = tmp_path / "receipts"
    receipt_parent.mkdir()
    witness_dir = tmp_path / "receipt-witnesses"
    witness_dir.mkdir()
    output = cli._require_external_new_output(
        path=receipt_parent / "receipt.json",
        repository_root=repository,
        snapshot_root=snapshot,
    )
    witness = cli._require_external_witness_root(
        path=witness_dir,
        repository_root=repository,
        snapshot_root=snapshot,
    )
    try:
        name = cli._probe_receipt_atomic_publication(output, witness)
        assert not (receipt_parent / "receipt.json").exists()
        assert list(receipt_parent.iterdir()) == []
        assert (witness_dir / name).read_bytes() == b""
    finally:
        os.close(witness.descriptor)
        os.close(output.descriptor)
