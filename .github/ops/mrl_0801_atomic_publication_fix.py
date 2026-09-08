from __future__ import annotations

import re
from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one replacement, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one regex replacement, found {count}")
    path.write_text(updated, encoding="utf-8")


module = Path("src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py")
replace_once(module, "import hashlib\nimport ipaddress\n", "import ctypes\nimport errno\nimport hashlib\nimport ipaddress\n")
replace_once(
    module,
    "from typing import IO, Final, Protocol, cast\n",
    "from typing import IO, Any, Final, Protocol, cast\n",
)
replace_once(
    module,
    '_O_CLOEXEC: Final = getattr(os, "O_CLOEXEC", 0)\n',
    '_O_CLOEXEC: Final = getattr(os, "O_CLOEXEC", 0)\n'
    '_O_TMPFILE: Final = getattr(os, "O_TMPFILE", 0)\n'
    '_AT_EMPTY_PATH: Final = 0x1000\n'
    '_UNSUPPORTED_LINKAT_ERRNOS: Final = frozenset(\n'
    '    {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)}\n'
    ')\n',
)

new_tail = r'''def _load_posix_symbol(name: str) -> Any:
    """Return one libc symbol, or None when the runtime does not expose it."""
    try:
        library = ctypes.CDLL(None, use_errno=True)
    except (OSError, TypeError):  # pragma: no cover - platform dependent
        return None
    return getattr(library, name, None)


def _open_unnamed_temp_file(*, root_fd: int) -> int:
    """Create an unnamed same-filesystem temporary file or fail closed."""
    if _O_TMPFILE == 0:
        raise MRL0801HfAcquisitionError("unnamed temporary-file publication is unavailable")
    try:
        descriptor = os.open(".", os.O_WRONLY | _O_TMPFILE | _O_CLOEXEC, 0o600, dir_fd=root_fd)
    except OSError as error:
        if error.errno in _UNSUPPORTED_LINKAT_ERRNOS:
            raise MRL0801HfAcquisitionError(
                "unnamed temporary-file publication is unsupported on this filesystem"
            ) from None
        raise MRL0801HfAcquisitionError(
            "unnamed temporary acquisition file could not be opened safely"
        ) from None
    return descriptor


def _publish_open_descriptor_no_replace(
    *,
    source_fd: int,
    root_fd: int,
    target_name: str,
) -> None:
    """Atomically link one open unnamed file to a new descriptor-relative name."""
    function = _load_posix_symbol("linkat")
    if function is None:
        raise MRL0801HfAcquisitionError("atomic descriptor publication is unavailable")
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    function.restype = ctypes.c_int
    ctypes.set_errno(0)
    status = function(
        source_fd,
        b"",
        root_fd,
        os.fsencode(target_name),
        _AT_EMPTY_PATH,
    )
    if status == 0:
        return
    code = ctypes.get_errno()
    if code == errno.EEXIST:
        raise MRL0801HfAcquisitionError(
            "executor refuses to overwrite an asset file created during publication"
        )
    if code in _UNSUPPORTED_LINKAT_ERRNOS:
        raise MRL0801HfAcquisitionError(
            "atomic descriptor publication is unsupported on this filesystem"
        )
    raise MRL0801HfAcquisitionError("asset publication failed safely")


def _acquire_one_file(
    *,
    root_fd: int,
    transport: HfPublicTransport,
    metadata: HfRemoteFileMetadata,
) -> HfAcquiredFileIdentity:
    relative = _validate_relative_path(metadata.path)
    target_name = relative.name
    if _descriptor_entry_exists(root_fd=root_fd, name=target_name):
        raise MRL0801HfAcquisitionError("executor refuses to overwrite an existing asset file")

    sha256 = hashlib.sha256()
    git_blob_sha1 = _new_git_blob_digest(metadata.byte_count)
    byte_count = 0
    descriptor = _open_unnamed_temp_file(root_fd=root_fd)
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise MRL0801HfAcquisitionError("unnamed acquisition descriptor is not a regular file")
        owned_identity = _stat_descriptor_identity(opened)
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            for chunk in transport.iter_bytes(metadata=metadata):
                if not isinstance(chunk, bytes) or not chunk:
                    raise MRL0801HfAcquisitionError("download transport yielded an invalid chunk")
                byte_count += len(chunk)
                if byte_count > metadata.byte_count:
                    raise MRL0801HfAcquisitionError("download exceeded authoritative byte count")
                sha256.update(chunk)
                git_blob_sha1.update(chunk)
                stream.write(chunk)
            stream.flush()
            os.fsync(stream.fileno())
        if byte_count != metadata.byte_count:
            raise MRL0801HfAcquisitionError("download byte count differs from remote metadata")
        local_sha256 = sha256.hexdigest()
        remote_identity = (
            local_sha256 if metadata.etag_algorithm == "sha256" else git_blob_sha1.hexdigest()
        )
        if remote_identity != metadata.etag:
            raise MRL0801HfAcquisitionError("download bytes differ from remote content identity")
        _publish_open_descriptor_no_replace(
            source_fd=descriptor,
            root_fd=root_fd,
            target_name=target_name,
        )
        published = _descriptor_entry_stat(root_fd=root_fd, name=target_name)
        if (
            published is None
            or not stat.S_ISREG(published.st_mode)
            or _stat_descriptor_identity(published) != owned_identity
        ):
            raise MRL0801HfAcquisitionError(
                "published asset identity changed after atomic publication"
            )
        return HfAcquiredFileIdentity(
            path=metadata.path,
            byte_count=byte_count,
            remote_etag=metadata.etag,
            remote_etag_algorithm=metadata.etag_algorithm,
            local_sha256=local_sha256,
            owned_device=owned_identity[0],
            owned_inode=owned_identity[1],
        )
    finally:
        os.close(descriptor)


def _rollback_created_files(
    *,
    root_fd: int,
    acquired: tuple[HfAcquiredFileIdentity, ...],
    pre_finalizer_entries: frozenset[str] | None = None,
) -> None:
    """Retain published transaction residue rather than perform a racy namespace unlink."""
    del root_fd, acquired, pre_finalizer_entries
'''
regex_once(
    module,
    r"def _unlink_descriptor_entry_if_owned\([\s\S]*\Z",
    new_tail,
)

cli = Path("scripts/mesc_mrl_0801_hf_acquire.py")
replace_once(cli, "import argparse\nimport contextlib\n", "import argparse\nimport contextlib\nimport ctypes\nimport errno\n")
replace_once(cli, "from types import ModuleType\n", "from types import ModuleType\nfrom typing import Any\n")
replace_once(
    cli,
    '_O_CLOEXEC: int = getattr(os, "O_CLOEXEC", 0)\n',
    '_O_CLOEXEC: int = getattr(os, "O_CLOEXEC", 0)\n'
    '_O_TMPFILE: int = getattr(os, "O_TMPFILE", 0)\n'
    '_AT_EMPTY_PATH = 0x1000\n'
    '_UNSUPPORTED_LINKAT_ERRNOS = frozenset(\n'
    '    {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)}\n'
    ')\n',
)

new_cli_write = r'''def _load_posix_symbol(name: str) -> Any:
    try:
        library = ctypes.CDLL(None, use_errno=True)
    except (OSError, TypeError):  # pragma: no cover - platform dependent
        return None
    return getattr(library, name, None)


def _publish_open_descriptor_no_replace(
    *,
    source_fd: int,
    output: _BoundReceiptOutput,
) -> None:
    function = _load_posix_symbol("linkat")
    if function is None:
        raise AcquisitionEntrypointError("atomic receipt publication is unavailable")
    function.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
    ]
    function.restype = ctypes.c_int
    ctypes.set_errno(0)
    status = function(
        source_fd,
        b"",
        output.descriptor,
        os.fsencode(output.name),
        _AT_EMPTY_PATH,
    )
    if status == 0:
        return
    code = ctypes.get_errno()
    if code == errno.EEXIST:
        raise AcquisitionEntrypointError("receipt output must not already exist")
    if code in _UNSUPPORTED_LINKAT_ERRNOS:
        raise AcquisitionEntrypointError(
            "atomic receipt publication is unsupported on this filesystem"
        )
    raise AcquisitionEntrypointError("receipt output could not be published safely")


def _write_exact_new(output: _BoundReceiptOutput, data: bytes) -> None:
    _require_bound_output_parent_identity(output)
    if output.created_device is not None or output.created_inode is not None:
        raise AcquisitionEntrypointError("receipt output is already owned by this transaction")
    if _descriptor_output_stat(output) is not None:
        raise AcquisitionEntrypointError("receipt output must not already exist")
    if _O_TMPFILE == 0:
        raise AcquisitionEntrypointError("unnamed receipt publication is unavailable")
    try:
        descriptor = os.open(
            ".",
            os.O_WRONLY | _O_TMPFILE | _O_CLOEXEC,
            0o600,
            dir_fd=output.descriptor,
        )
    except OSError as error:
        if error.errno in _UNSUPPORTED_LINKAT_ERRNOS:
            raise AcquisitionEntrypointError(
                "unnamed receipt publication is unsupported on this filesystem"
            ) from None
        raise AcquisitionEntrypointError("receipt output could not be created safely") from None
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            raise AcquisitionEntrypointError("receipt output descriptor is not a regular file")
        output.created_device = opened.st_dev
        output.created_inode = opened.st_ino
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        _require_bound_output_parent_identity(output)
        _publish_open_descriptor_no_replace(source_fd=descriptor, output=output)
        _require_bound_output_parent_identity(output)
        _require_owned_output_identity(output)
    finally:
        os.close(descriptor)


'''
regex_once(
    cli,
    r"def _unlink_bound_output\([\s\S]*?\n\ndef main\(",
    new_cli_write + "def main(",
)
replace_once(
    cli,
    '''    except (AcquisitionEntrypointError, ImportError, OSError, RuntimeError, ValueError):
        for output in (custody_output, provenance_output):
            if output is not None:
                with contextlib.suppress(OSError, AcquisitionEntrypointError):
                    _unlink_bound_output(output)
        print(
''',
    '''    except (AcquisitionEntrypointError, ImportError, OSError, RuntimeError, ValueError):
        print(
''',
)

spec = Path("specs/mesc-experiment-0/mrl-0801-hf-acquisition-provenance-v1.md")
replace_once(
    spec,
    "The executor requires no-follow directory-descriptor support and opens the destination once. The opened device/inode identity is bound for the transaction. File existence checks, exclusive partial-file creation, atomic publication, cleanup, and rollback operate descriptor-relative to that opened directory rather than by resolving the destination pathname again. Authorized V1 file paths are one canonical POSIX basename each.\n\nThe executor never overwrites existing asset files. Every file is streamed to an exclusive no-follow partial file with restrictive mode, fully hashed and size-checked, then atomically published with a same-directory no-replace hard link. The partial link is removed only after the target link exists. If a racing target appears, publication fails without modifying that target.\n\nBefore and after the path-based canonical SafeTensors custody handoff, the destination pathname must still resolve to the exact opened device/inode. If the pathname is concurrently removed, replaced, redirected, or changed to another directory, the transaction fails. Published model files carry an internal transaction-owned `(device, inode)` identity that is not serialized into provenance; rollback attempts deletion only while the directory entry still resolves to that exact regular-file identity.\n\nReceipt publication by the CLI is supplied as the acquisition transaction finalizer. Therefore a late custody/provenance reconciliation error or receipt-output write failure occurs while the destination descriptor remains open and triggers the same descriptor-relative model-file rollback. No path-based post-return snapshot rollback is trusted.\n\nIf any later file, metadata refresh, remote-content check, SafeTensors custody verification, provenance reconciliation, destination-identity check, or transaction finalizer fails, rollback removes each published model file only while its name still resolves to the exact transaction-owned regular-file identity captured at publication. A name that has been replaced or rebound by another actor is preserved rather than deleted. Transaction partials are likewise removed only while their captured identity still matches. The core executor does not delete arbitrary entries merely because they appeared during a finalizer; finalizer-owned outputs must use their own ownership-bound cleanup, as the CLI receipt publisher already does. A cleanup race therefore remains `BLOCKED` and may require operator inspection; it never converts into success. No resume, mutable overwrite, or partial-snapshot acceptance exists in V1.\n",
    "The executor requires no-follow directory-descriptor support and opens the destination once. The opened device/inode identity is bound for the transaction. Authorized V1 file paths are one canonical POSIX basename each. Public namespace mutation is intentionally limited to atomic descriptor publication; the executor performs no automatic public-entry unlink cleanup or rollback.\n\nThe executor never overwrites existing asset files. Every file is streamed into an unnamed same-filesystem `O_TMPFILE` opened through the bound destination descriptor, fully hashed and size-checked, then atomically published from that still-open file descriptor with `linkat(..., AT_EMPTY_PATH)`. If the primitive or filesystem support is unavailable, acquisition fails closed. If a racing target appears, the atomic link fails without modifying that target. Before publication, failure cleanup is descriptor close only because the temporary file has no directory entry.\n\nBefore and after the path-based canonical SafeTensors custody handoff, the destination pathname must still resolve to the exact opened device/inode. If the pathname is concurrently removed, replaced, redirected, or changed to another directory, the transaction fails. Published model files retain an internal transaction identity for verification, but that identity is never used to justify a non-atomic `stat`-then-`unlink` sequence.\n\nReceipt publication by the CLI is supplied as the acquisition transaction finalizer and uses the same unnamed-file pattern in each pre-bound external receipt parent. Receipt bytes are written and fsynced before one atomic descriptor publication to the final name. The CLI performs no automatic receipt unlink cleanup.\n\nIf any later file, metadata refresh, remote-content check, SafeTensors custody verification, provenance reconciliation, destination-identity check, or transaction finalizer fails after a public name has been published, the transaction remains `BLOCKED` and the published residue is retained for operator inspection. Automatic deletion is prohibited because a separate identity check followed by namespace unlink cannot make ownership and removal atomic. A failed attempt never becomes success, and no resume, mutable overwrite, automatic repair, or partial-snapshot acceptance exists in V1. A subsequent attempt must begin from a separately inspected and restored empty destination and unused receipt names.\n",
)

publish_test = Path("tests/test_mesc_mrl_0801_hf_publish_v1.py")
publish_test.write_text(r'''"""Atomic publication regression tests for MRL-0801 acquisition."""

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
''', encoding="utf-8")

cli_test = Path("tests/test_mesc_mrl_0801_hf_acquire_cli.py")
replace_once(
    cli_test,
    '''def test_receipt_output_is_written_and_cleaned_descriptor_relative(tmp_path: Path) -> None:
''',
    '''def test_receipt_output_is_published_descriptor_relative(tmp_path: Path) -> None:
''',
)
replace_once(
    cli_test,
    '''        cli._write_exact_new(output, b"{}")
        assert receipt.read_bytes() == b"{}"
        cli._unlink_bound_output(output)
        assert not receipt.exists()
''',
    '''        cli._write_exact_new(output, b"{}")
        assert receipt.read_bytes() == b"{}"
''',
)
replace_once(
    cli_test,
    '''        with pytest.raises(cli.AcquisitionEntrypointError, match="could not be created"):
            cli._write_exact_new(output, b"ours")
        cli._unlink_bound_output(output)
        assert receipt.read_bytes() == b"foreign"
''',
    '''        with pytest.raises(cli.AcquisitionEntrypointError, match="must not already exist"):
            cli._write_exact_new(output, b"ours")
        assert receipt.read_bytes() == b"foreign"
''',
)
regex_once(
    cli_test,
    r"def test_receipt_replacement_during_write_preserves_foreign_entry\([\s\S]*?\n\ndef test_any_preloaded_medscale_module_is_rejected",
    r'''def test_receipt_publication_race_preserves_foreign_entry(
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


def test_any_preloaded_medscale_module_is_rejected''',
)

print("MRL-0801 atomic publication patch applied")
