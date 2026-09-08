"""Atomic publication regression tests for MRL-0801 acquisition."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from medscale.mesc import _mrl_0801_hf_acquisition_v1 as subject

REVISION = "8" * 40
ASSET = "model.safetensors"


class ByteTransport:
    def __init__(self, data: bytes) -> None:
        self.data = data

    def metadata(
        self,
        *,
        model_id: str,
        revision: str,
        path: str,
    ) -> subject.HfRemoteFileMetadata:
        del model_id, revision, path
        raise AssertionError("metadata is not used by the single-file publication helper")

    def iter_bytes(self, *, metadata: subject.HfRemoteFileMetadata) -> Iterator[bytes]:
        del metadata
        yield self.data


def root_descriptor(root: Path) -> int:
    if subject._O_DIRECTORY == 0 or subject._O_NOFOLLOW == 0:
        pytest.skip("descriptor-safe acquisition primitives are unavailable on this platform")
    return os.open(root, os.O_RDONLY | subject._O_DIRECTORY | subject._O_NOFOLLOW)


def remote_metadata(data: bytes, *, byte_count: int) -> subject.HfRemoteFileMetadata:
    return subject.HfRemoteFileMetadata(
        path=ASSET,
        commit_sha=REVISION,
        byte_count=byte_count,
        etag=hashlib.sha256(data).hexdigest(),
        location="https://huggingface.co/public/file",
    )


def test_unnamed_descriptor_publication_succeeds_without_target(tmp_path: Path) -> None:
    descriptor = root_descriptor(tmp_path)
    temporary = -1
    try:
        temporary = subject._open_unnamed_temp_file(root_fd=descriptor)
        os.write(temporary, b"new-bytes")
        subject._publish_open_descriptor_no_replace(
            source_fd=temporary,
            root_fd=descriptor,
            target_name="asset",
        )
    finally:
        if temporary >= 0:
            os.close(temporary)
        os.close(descriptor)

    assert (tmp_path / "asset").read_bytes() == b"new-bytes"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["asset"]


def test_unnamed_descriptor_publication_preserves_racing_target(tmp_path: Path) -> None:
    target = tmp_path / "asset"
    target.write_bytes(b"existing-bytes")
    descriptor = root_descriptor(tmp_path)
    temporary = -1
    try:
        temporary = subject._open_unnamed_temp_file(root_fd=descriptor)
        os.write(temporary, b"new-bytes")
        with pytest.raises(subject.MRL0801HfAcquisitionError, match="refuses to overwrite"):
            subject._publish_open_descriptor_no_replace(
                source_fd=temporary,
                root_fd=descriptor,
                target_name=target.name,
            )
    finally:
        if temporary >= 0:
            os.close(temporary)
        os.close(descriptor)

    assert target.read_bytes() == b"existing-bytes"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["asset"]


@pytest.mark.parametrize(
    ("declared_delta", "pattern"),
    ((1, "byte count differs"), (-1, "exceeded authoritative byte count")),
)
def test_short_and_oversized_downloads_leave_no_named_partial(
    tmp_path: Path,
    declared_delta: int,
    pattern: str,
) -> None:
    data = b"model-bytes"
    descriptor = root_descriptor(tmp_path)
    try:
        with pytest.raises(subject.MRL0801HfAcquisitionError, match=pattern):
            subject._acquire_one_file(
                root_fd=descriptor,
                transport=ByteTransport(data),
                metadata=remote_metadata(data, byte_count=len(data) + declared_delta),
            )
    finally:
        os.close(descriptor)

    assert list(tmp_path.iterdir()) == []


def test_existing_target_blocks_acquisition_without_mutation(tmp_path: Path) -> None:
    data = b"model-bytes"
    target = tmp_path / ASSET
    target.write_bytes(b"existing")
    descriptor = root_descriptor(tmp_path)
    try:
        with pytest.raises(subject.MRL0801HfAcquisitionError, match="overwrite"):
            subject._acquire_one_file(
                root_fd=descriptor,
                transport=ByteTransport(data),
                metadata=remote_metadata(data, byte_count=len(data)),
            )
    finally:
        os.close(descriptor)

    assert target.read_bytes() == b"existing"


def test_late_rollback_retains_published_transaction_file(tmp_path: Path) -> None:
    data = b"model-bytes"
    descriptor = root_descriptor(tmp_path)
    try:
        acquired = subject._acquire_one_file(
            root_fd=descriptor,
            transport=ByteTransport(data),
            metadata=remote_metadata(data, byte_count=len(data)),
        )
        subject._rollback_created_files(root_fd=descriptor, acquired=(acquired,))
    finally:
        os.close(descriptor)

    assert (tmp_path / ASSET).read_bytes() == data


def test_rollback_never_unlinks_replacement_or_owned_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    data = b"model-bytes"
    descriptor = root_descriptor(tmp_path)
    try:
        acquired = subject._acquire_one_file(
            root_fd=descriptor,
            transport=ByteTransport(data),
            metadata=remote_metadata(data, byte_count=len(data)),
        )
        target = tmp_path / ASSET
        original = tmp_path / "original-model.safetensors"
        target.rename(original)
        target.write_bytes(b"foreign-replacement")

        def forbidden_unlink(*args: object, **kwargs: object) -> None:
            del args, kwargs
            raise AssertionError("rollback must not unlink public entries")

        monkeypatch.setattr(os, "unlink", forbidden_unlink)
        subject._rollback_created_files(root_fd=descriptor, acquired=(acquired,))
    finally:
        os.close(descriptor)

    assert target.read_bytes() == b"foreign-replacement"
    assert original.read_bytes() == data
