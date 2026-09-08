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


def test_publish_partial_no_replace_succeeds_without_target(tmp_path: Path) -> None:
    partial = tmp_path / ".asset.partial"
    target = tmp_path / "asset"
    partial.write_bytes(b"new-bytes")
    descriptor = root_descriptor(tmp_path)
    try:
        subject._publish_partial_no_replace(
            root_fd=descriptor,
            partial_name=partial.name,
            target_name=target.name,
        )
    finally:
        os.close(descriptor)

    assert target.read_bytes() == b"new-bytes"
    assert not partial.exists()


def test_publish_partial_no_replace_preserves_racing_target(tmp_path: Path) -> None:
    partial = tmp_path / ".asset.partial"
    target = tmp_path / "asset"
    partial.write_bytes(b"new-bytes")
    target.write_bytes(b"existing-bytes")
    descriptor = root_descriptor(tmp_path)
    try:
        with pytest.raises(subject.MRL0801HfAcquisitionError, match="refuses to overwrite"):
            subject._publish_partial_no_replace(
                root_fd=descriptor,
                partial_name=partial.name,
                target_name=target.name,
            )
    finally:
        os.close(descriptor)

    assert target.read_bytes() == b"existing-bytes"
    assert partial.read_bytes() == b"new-bytes"


@pytest.mark.parametrize(
    ("declared_delta", "pattern"),
    ((1, "byte count differs"), (-1, "exceeded authoritative byte count")),
)
def test_short_and_oversized_downloads_fail_and_remove_partial(
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


def test_stale_partial_blocks_acquisition_without_mutation(tmp_path: Path) -> None:
    data = b"model-bytes"
    partial = tmp_path / f".{ASSET}.mrl-0801-partial"
    partial.write_bytes(b"stale")
    descriptor = root_descriptor(tmp_path)
    try:
        with pytest.raises(subject.MRL0801HfAcquisitionError, match="stale partial"):
            subject._acquire_one_file(
                root_fd=descriptor,
                transport=ByteTransport(data),
                metadata=remote_metadata(data, byte_count=len(data)),
            )
    finally:
        os.close(descriptor)

    assert partial.read_bytes() == b"stale"
    assert not (tmp_path / ASSET).exists()
