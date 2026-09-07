"""Atomic publication regression tests for MRL-0801 acquisition."""

import os
from pathlib import Path

import pytest

from medscale.mesc import _mrl_0801_hf_acquisition_v1 as subject


def root_descriptor(root: Path) -> int:
    return os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)


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
