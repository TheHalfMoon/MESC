"""Atomic publication regression tests for MRL-0801 acquisition."""
from pathlib import Path

import pytest

from medscale.mesc import _mrl_0801_hf_acquisition_v1 as subject


def test_publish_partial_no_replace_succeeds_without_target(tmp_path: Path) -> None:
    partial = tmp_path / ".asset.partial"
    target = tmp_path / "asset"
    partial.write_bytes(b"new-bytes")

    subject._publish_partial_no_replace(partial=partial, target=target)

    assert target.read_bytes() == b"new-bytes"
    assert not partial.exists()


def test_publish_partial_no_replace_preserves_racing_target(tmp_path: Path) -> None:
    partial = tmp_path / ".asset.partial"
    target = tmp_path / "asset"
    partial.write_bytes(b"new-bytes")
    target.write_bytes(b"existing-bytes")

    with pytest.raises(subject.MRL0801HfAcquisitionError, match="refuses to overwrite"):
        subject._publish_partial_no_replace(partial=partial, target=target)

    assert target.read_bytes() == b"existing-bytes"
    assert partial.read_bytes() == b"new-bytes"
