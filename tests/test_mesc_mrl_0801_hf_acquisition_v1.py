"""Qualification tests for bounded MRL-0801 Hugging Face acquisition."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from medscale.mesc import _mrl_0801_hf_acquisition_v1 as subject
from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._mrl_0801_acquisition_custody_v1 import (
    MRL0801AcquisitionAuthorization,
    MRL0801AcquisitionCustodyError,
    MRL0801AssetCustodyReceipt,
    parse_mrl_0801_acquisition_authorization,
)

ROOT = Path(__file__).parents[1]
AUTH = ROOT / "specs/mesc-experiment-0/mrl-0801-acquisition-custody-authorization-v1.json"
MODEL = "google/gemma-4-31B-it"
REV = "842da3794eaa0b77d5f08bae87a17459d91ff475"
FILES = (
    "model.safetensors.index.json",
    "model-00001-of-00002.safetensors",
    "model-00002-of-00002.safetensors",
)
IDENTITY = subject.RepositoryExecutionIdentity("9" * 40, "8" * 40, "7" * 64)


def authorization() -> MRL0801AcquisitionAuthorization:
    return parse_mrl_0801_acquisition_authorization(AUTH.read_bytes())


def payloads() -> dict[str, bytes]:
    first, second = b"gemma-one", b"gemma-two"
    index = {
        "metadata": {"total_size": len(first) + len(second)},
        "weight_map": {"a": FILES[1], "b": FILES[2]},
    }
    return {
        FILES[0]: json.dumps(index, sort_keys=True, separators=(",", ":")).encode(),
        FILES[1]: first,
        FILES[2]: second,
    }


def git_blob(data: bytes) -> str:
    digest = hashlib.sha1(usedforsecurity=False)
    digest.update(f"blob {len(data)}\0".encode())
    digest.update(data)
    return digest.hexdigest()


class FakeTransport:
    def __init__(self, *, drift: str | None = None, corrupt: str | None = None) -> None:
        self.data = payloads()
        self.drift = drift
        self.corrupt = corrupt
        self.calls: dict[str, int] = {}
        self.downloads: list[str] = []

    def metadata(self, *, model_id: str, revision: str, path: str) -> subject.HfRemoteFileMetadata:
        assert model_id == MODEL
        self.calls[path] = self.calls.get(path, 0) + 1
        raw = self.data[path]
        etag = hashlib.sha256(raw).hexdigest() if path.endswith(".safetensors") else git_blob(raw)
        if self.drift == path and self.calls[path] > 1:
            etag = "f" * len(etag)
        return subject.HfRemoteFileMetadata(
            path=path,
            commit_sha=revision,
            byte_count=len(raw),
            etag=etag,
            location="https://huggingface.co/public/file",
        )

    def iter_bytes(self, *, metadata: subject.HfRemoteFileMetadata) -> Iterator[bytes]:
        self.downloads.append(metadata.path)
        raw = self.data[metadata.path]
        if self.corrupt == metadata.path:
            raw = b"x" * len(raw)
        yield raw


class ReplacingTransport(FakeTransport):
    def __init__(self, *, destination: Path, replacement: Path) -> None:
        super().__init__()
        self.destination = destination
        self.replacement = replacement
        self.replaced = False

    def iter_bytes(self, *, metadata: subject.HfRemoteFileMetadata) -> Iterator[bytes]:
        if not self.replaced:
            self.destination.rename(self.replacement)
            self.destination.mkdir()
            (self.destination / "sentinel.txt").write_text("replacement", encoding="utf-8")
            self.replaced = True
        yield from super().iter_bytes(metadata=metadata)


def fake_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    (root / ".git").mkdir()
    return root


def patch_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subject, "_capture_repository_execution_identity", lambda _: IDENTITY)
    monkeypatch.setattr(
        subject,
        "_validate_recorded_repository_execution_identity",
        lambda **_: None,
    )
    monkeypatch.setattr(subject, "_available_bytes", lambda _: 10**15)


def acquire(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    transport: FakeTransport,
) -> tuple[
    Path,
    MRL0801AssetCustodyReceipt,
    subject.MRL0801HfAcquisitionProvenanceReceipt,
]:
    patch_environment(monkeypatch)
    destination = tmp_path / "assets"
    destination.mkdir(parents=True)
    custody, receipt = subject.acquire_mrl_0801_hf_candidate(
        authorization=authorization(),
        transport=transport,
        repository_root=fake_repo(tmp_path),
        destination=destination,
        model_id=MODEL,
        revision=REV,
    )
    return destination, custody, receipt


def test_success_binds_remote_identity_to_existing_custody(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = FakeTransport()
    destination, custody, receipt = acquire(tmp_path, monkeypatch, transport)
    assert tuple(item.path for item in receipt.files) == FILES
    assert receipt.artifact_identity_sha256 == custody.artifact_identity_sha256
    assert receipt.weights_sha256 == custody.weights_sha256
    assert receipt.asset_custody_sha256 == custody.asset_custody_sha256
    assert receipt.executor_code_commit == IDENTITY.commit_sha
    assert transport.downloads == list(FILES)
    assert str(tmp_path).encode() not in receipt.canonical_bytes
    subject.validate_mrl_0801_hf_acquisition_provenance(
        receipt=receipt,
        custody=custody,
        authorization=authorization(),
        model_root=destination,
        transport=transport,
        repository_root=fake_repo(tmp_path / "review"),
    )


def test_spoofed_authorization_fails_before_transport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Spoof:
        def require_candidate(self, **_: object) -> object:
            return SimpleNamespace(allowed_files=("evil.bin",))

    patch_environment(monkeypatch)
    transport = FakeTransport()
    with pytest.raises(subject.MRL0801HfAcquisitionError, match="exact MRL0801"):
        subject.acquire_mrl_0801_hf_candidate(
            authorization=cast(MRL0801AcquisitionAuthorization, Spoof()),
            transport=transport,
            repository_root=fake_repo(tmp_path),
            destination=tmp_path / "assets",
            model_id=MODEL,
            revision=REV,
        )
    assert transport.calls == {}


def test_phi_and_mutable_revision_are_not_authorized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_environment(monkeypatch)
    for model_id, revision in (("microsoft/Phi-4-multimodal-instruct", REV), (MODEL, "main")):
        transport = FakeTransport()
        with pytest.raises(MRL0801AcquisitionCustodyError):
            subject.acquire_mrl_0801_hf_candidate(
                authorization=authorization(),
                transport=transport,
                repository_root=fake_repo(
                    tmp_path / hashlib.sha256(f"{model_id}{revision}".encode()).hexdigest()
                ),
                destination=tmp_path / hashlib.sha256(revision.encode()).hexdigest(),
                model_id=model_id,
                revision=revision,
            )
        assert transport.calls == {}


def test_metadata_drift_and_corrupt_bytes_roll_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for transport, pattern in (
        (FakeTransport(drift=FILES[1]), "changed between storage preflight"),
        (FakeTransport(corrupt=FILES[1]), "remote content identity"),
    ):
        patch_environment(monkeypatch)
        root = tmp_path / hashlib.sha256(pattern.encode()).hexdigest()
        destination = root / "assets"
        destination.mkdir(parents=True)
        with pytest.raises(subject.MRL0801HfAcquisitionError, match=pattern):
            subject.acquire_mrl_0801_hf_candidate(
                authorization=authorization(),
                transport=transport,
                repository_root=fake_repo(root),
                destination=destination,
                model_id=MODEL,
                revision=REV,
            )
        assert list(destination.iterdir()) == []


def test_storage_failure_occurs_before_model_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subject, "_capture_repository_execution_identity", lambda _: IDENTITY)
    monkeypatch.setattr(subject, "_available_bytes", lambda _: 1)
    destination = tmp_path / "assets"
    destination.mkdir()
    transport = FakeTransport()
    with pytest.raises(MRL0801AcquisitionCustodyError, match="below"):
        subject.acquire_mrl_0801_hf_candidate(
            authorization=authorization(),
            transport=transport,
            repository_root=fake_repo(tmp_path),
            destination=destination,
            model_id=MODEL,
            revision=REV,
        )
    assert transport.downloads == []


def test_destination_must_exist_and_remote_url_boundaries(tmp_path: Path) -> None:
    repo = fake_repo(tmp_path)
    with pytest.raises(subject.MRL0801HfAcquisitionError, match="outside Git"):
        subject._require_external_empty_destination(
            destination=repo / "assets",
            repository_root=repo,
        )
    with pytest.raises(subject.MRL0801HfAcquisitionError, match="existing real empty directory"):
        subject._require_external_empty_destination(
            destination=tmp_path / "missing",
            repository_root=repo,
        )
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(subject.MRL0801HfAcquisitionError, match="symbolic link"):
        subject._require_external_empty_destination(destination=link, repository_root=repo)
    for url in (
        "http://huggingface.co/file",
        "https://user:secret@huggingface.co/file",
        "https://127.0.0.1/file",
        "https://example.com/file",
    ):
        with pytest.raises(subject.MRL0801HfAcquisitionError):
            subject._require_safe_remote_url(url)


def test_destination_replacement_cannot_redirect_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_environment(monkeypatch)
    destination = tmp_path / "assets"
    destination.mkdir()
    original = tmp_path / "original-assets"
    transport = ReplacingTransport(destination=destination, replacement=original)
    with pytest.raises(subject.MRL0801HfAcquisitionError, match="destination path changed"):
        subject.acquire_mrl_0801_hf_candidate(
            authorization=authorization(),
            transport=transport,
            repository_root=fake_repo(tmp_path),
            destination=destination,
            model_id=MODEL,
            revision=REV,
        )
    assert list(original.iterdir()) == []
    assert (destination / "sentinel.txt").read_text(encoding="utf-8") == "replacement"


def test_finalizer_failure_removes_finalizer_created_entry_and_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_environment(monkeypatch)
    destination = tmp_path / "assets"
    destination.mkdir()

    def fail_finalize(
        _: MRL0801AssetCustodyReceipt,
        __: subject.MRL0801HfAcquisitionProvenanceReceipt,
    ) -> None:
        (destination / "unexpected.txt").write_text("unexpected", encoding="utf-8")
        raise OSError("receipt publication failed")

    with pytest.raises(OSError, match="receipt publication failed"):
        subject.acquire_mrl_0801_hf_candidate(
            authorization=authorization(),
            transport=FakeTransport(),
            repository_root=fake_repo(tmp_path),
            destination=destination,
            model_id=MODEL,
            revision=REV,
            finalizer=fail_finalize,
        )
    assert list(destination.iterdir()) == []


def test_finalizer_extra_entry_is_rejected_and_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_environment(monkeypatch)
    destination = tmp_path / "assets"
    destination.mkdir()

    def add_extra_entry(
        _: MRL0801AssetCustodyReceipt,
        __: subject.MRL0801HfAcquisitionProvenanceReceipt,
    ) -> None:
        (destination / "unexpected.txt").write_text("unexpected", encoding="utf-8")

    with pytest.raises(subject.MRL0801HfAcquisitionError, match="manifest changed"):
        subject.acquire_mrl_0801_hf_candidate(
            authorization=authorization(),
            transport=FakeTransport(),
            repository_root=fake_repo(tmp_path),
            destination=destination,
            model_id=MODEL,
            revision=REV,
            finalizer=add_extra_entry,
        )
    assert list(destination.iterdir()) == []


def test_finalizer_asset_mutation_is_rejected_and_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    patch_environment(monkeypatch)
    destination = tmp_path / "assets"
    destination.mkdir()

    def mutate_asset(
        _: MRL0801AssetCustodyReceipt,
        __: subject.MRL0801HfAcquisitionProvenanceReceipt,
    ) -> None:
        (destination / FILES[1]).write_bytes(b"tamper-me")

    with pytest.raises(subject.MRL0801HfAcquisitionError, match="custody changed"):
        subject.acquire_mrl_0801_hf_candidate(
            authorization=authorization(),
            transport=FakeTransport(),
            repository_root=fake_repo(tmp_path),
            destination=destination,
            model_id=MODEL,
            revision=REV,
            finalizer=mutate_asset,
        )
    assert list(destination.iterdir()) == []


def test_provenance_validation_requires_exact_receipt_types(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination, custody, receipt = acquire(tmp_path, monkeypatch, FakeTransport())
    fake_receipt = cast(subject.MRL0801HfAcquisitionProvenanceReceipt, SimpleNamespace())
    with pytest.raises(subject.MRL0801HfAcquisitionError, match="exact canonical"):
        subject.validate_mrl_0801_hf_acquisition_provenance(
            receipt=fake_receipt,
            custody=custody,
            authorization=authorization(),
            model_root=destination,
            transport=FakeTransport(),
            repository_root=fake_repo(tmp_path / "review-receipt"),
        )
    fake_custody = cast(MRL0801AssetCustodyReceipt, SimpleNamespace())
    with pytest.raises(subject.MRL0801HfAcquisitionError, match="exact canonical"):
        subject.validate_mrl_0801_hf_acquisition_provenance(
            receipt=receipt,
            custody=fake_custody,
            authorization=authorization(),
            model_root=destination,
            transport=FakeTransport(),
            repository_root=fake_repo(tmp_path / "review-custody"),
        )


def test_receipt_is_canonical_and_exact_boolean_typed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, _, receipt = acquire(tmp_path, monkeypatch, FakeTransport())
    document = cast(dict[str, object], json.loads(receipt.canonical_bytes))
    document["credentials_used"] = 0
    with pytest.raises(subject.MRL0801HfAcquisitionError, match="credentials_used"):
        subject.MRL0801HfAcquisitionProvenanceReceipt(canonical_json_bytes(document))
