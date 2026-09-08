"""Mount-boundary rollback regressions for MRL-0801 acquisition."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from medscale.mesc import _mrl_0801_hf_acquisition_v1 as subject

_O_DIRECTORY: int = getattr(os, "O_DIRECTORY", 0)


def _acquired_file(path: Path) -> subject.HfAcquiredFileIdentity:
    observed = path.stat(follow_symlinks=False)
    return subject.HfAcquiredFileIdentity(
        path=path.name,
        byte_count=1,
        remote_etag="a" * 64,
        remote_etag_algorithm="sha256",
        local_sha256="a" * 64,
        owned_device=observed.st_dev,
        owned_inode=observed.st_ino,
    )


def test_rollback_never_recurses_into_nonempty_finalizer_directory(tmp_path: Path) -> None:
    root = tmp_path / "assets"
    root.mkdir()
    asset = root / "asset.safetensors"
    asset.write_bytes(b"x")
    unexpected = root / "unexpected-dir"
    unexpected.mkdir()
    payload = unexpected / "payload.bin"
    payload.write_bytes(b"external-content")

    root_fd = os.open(root, os.O_RDONLY | _O_DIRECTORY)
    try:
        subject._rollback_created_files(
            root_fd=root_fd,
            acquired=(_acquired_file(asset),),
            pre_finalizer_entries=frozenset({asset.name}),
        )
    finally:
        os.close(root_fd)

    assert not asset.exists()
    assert payload.read_bytes() == b"external-content"


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux bind-mount regression")
def test_rollback_does_not_descend_into_bind_mount(tmp_path: Path) -> None:
    mount = shutil.which("mount")
    umount = shutil.which("umount")
    if mount is None or umount is None:
        pytest.skip("mount utilities are unavailable")

    root = tmp_path / "assets"
    root.mkdir()
    asset = root / "asset.safetensors"
    asset.write_bytes(b"x")
    external = tmp_path / "external"
    external.mkdir()
    payload = external / "payload.bin"
    payload.write_bytes(b"external-content")
    mountpoint = root / "mounted"
    mountpoint.mkdir()

    mounted = subprocess.run(
        [mount, "--bind", str(external), str(mountpoint)],
        check=False,
        capture_output=True,
    )
    if mounted.returncode != 0:
        pytest.skip("bind mounts are not permitted in this test environment")
    try:
        root_fd = os.open(root, os.O_RDONLY | _O_DIRECTORY)
        try:
            subject._rollback_created_files(
                root_fd=root_fd,
                acquired=(_acquired_file(asset),),
                pre_finalizer_entries=frozenset({asset.name}),
            )
        finally:
            os.close(root_fd)
        assert not asset.exists()
        assert payload.read_bytes() == b"external-content"
    finally:
        subprocess.run([umount, str(mountpoint)], check=False, capture_output=True)
