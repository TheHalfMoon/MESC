"""Run one authorized MRL-0801 public Hugging Face acquisition transaction."""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import errno
import importlib
import json
import os
import secrets
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_MODULE_RELATIVE_PATH = Path("src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py")
_AUTHORIZATION_RELATIVE_PATH = Path(
    "specs/mesc-experiment-0/mrl-0801-acquisition-custody-authorization-v1.json"
)
_O_NOFOLLOW: int = getattr(os, "O_NOFOLLOW", 0)
_O_DIRECTORY: int = getattr(os, "O_DIRECTORY", 0)
_O_CLOEXEC: int = getattr(os, "O_CLOEXEC", 0)
_O_TMPFILE: int = getattr(os, "O_TMPFILE", 0)
_AT_EMPTY_PATH = 0x1000
_UNSUPPORTED_LINKAT_ERRNOS = frozenset(
    {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)}
)


class AcquisitionEntrypointError(RuntimeError):
    """Raised before importing repository code when execution identity is invalid."""


class _BoundReceiptOutput:
    """Descriptor-bound receipt output with transaction-created file identity."""

    __slots__ = (
        "created_device",
        "created_inode",
        "descriptor",
        "device",
        "inode",
        "name",
        "parent_path",
        "path",
    )

    created_device: int | None
    created_inode: int | None
    descriptor: int
    device: int
    inode: int
    name: str
    parent_path: Path
    path: Path

    def __init__(
        self,
        *,
        path: Path,
        parent_path: Path,
        descriptor: int,
        device: int,
        inode: int,
        name: str,
    ) -> None:
        self.path = path
        self.parent_path = parent_path
        self.descriptor = descriptor
        self.device = device
        self.inode = inode
        self.name = name
        self.created_device = None
        self.created_inode = None


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Acquire one exact MRL-0801 authorized public Hugging Face candidate."
    )
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--custody-receipt-output", type=Path, required=True)
    parser.add_argument("--provenance-receipt-output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    return parser


def _git(repository_root: Path, *arguments: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        raise AcquisitionEntrypointError("Git execution is unavailable") from None
    if completed.returncode != 0:
        raise AcquisitionEntrypointError("repository Git identity cannot be resolved")
    return completed.stdout.strip()


def _git_bytes(repository_root: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=False,
            capture_output=True,
        )
    except OSError:
        raise AcquisitionEntrypointError("Git execution is unavailable") from None
    if completed.returncode != 0:
        raise AcquisitionEntrypointError("repository Git identity cannot be resolved")
    return completed.stdout


def _require_clean_repository_before_import(repository_root: Path) -> Path:
    root = repository_root.resolve(strict=True)
    if not (root / ".git").exists():
        raise AcquisitionEntrypointError("repository_root is not a Git work tree")
    top_level = Path(_git(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if top_level != root:
        raise AcquisitionEntrypointError("repository_root is not the exact Git work-tree root")
    if _git(root, "status", "--porcelain", "--untracked-files=all"):
        raise AcquisitionEntrypointError("repository work tree must be clean before acquisition")
    module_path = (root / _MODULE_RELATIVE_PATH).resolve(strict=True)
    if not module_path.is_file():
        raise AcquisitionEntrypointError("canonical acquisition executor source is missing")
    return root


def _require_module_file(module: ModuleType, expected: Path, *, label: str) -> None:
    module_file = getattr(module, "__file__", None)
    if type(module_file) is not str or Path(module_file).resolve(strict=True) != expected:
        raise AcquisitionEntrypointError(
            f"{label} must import from the exact checked-out repository source"
        )


def _require_no_preloaded_medscale_modules() -> None:
    preloaded = tuple(
        sorted(name for name in sys.modules if name == "medscale" or name.startswith("medscale."))
    )
    if preloaded:
        raise AcquisitionEntrypointError(
            "preloaded medscale modules are prohibited before exact-source acquisition import"
        )


def _prepend_exact_source_root(source_root: str) -> None:
    """Place the exact repository source root first even when it already exists later."""
    sys.path[:] = [entry for entry in sys.path if entry != source_root]
    sys.path.insert(0, source_root)


def _require_loaded_medscale_modules_match_head(
    *, repository_root: Path, source_root: Path
) -> None:
    for name, module in tuple(sys.modules.items()):
        if name != "medscale" and not name.startswith("medscale."):
            continue
        if module is None:
            raise AcquisitionEntrypointError("loaded medscale module identity is unavailable")
        module_file = getattr(module, "__file__", None)
        if type(module_file) is not str:
            raise AcquisitionEntrypointError("loaded medscale module has no exact source file")
        try:
            resolved = Path(module_file).resolve(strict=True)
            relative_source = resolved.relative_to(source_root)
        except (OSError, ValueError):
            raise AcquisitionEntrypointError(
                "loaded medscale module is outside the exact checked-out repository source"
            ) from None
        repository_relative = Path("src") / relative_source
        committed = _git_bytes(
            repository_root,
            "show",
            f"HEAD:{repository_relative.as_posix()}",
        )
        if resolved.read_bytes() != committed:
            raise AcquisitionEntrypointError(
                "loaded medscale module bytes differ from the exact Git commit"
            )


def _import_exact_repository_modules(repository_root: Path) -> tuple[ModuleType, ModuleType]:
    source_root_path = (repository_root / "src").resolve(strict=True)
    source_root = str(source_root_path)
    _require_no_preloaded_medscale_modules()
    _prepend_exact_source_root(source_root)
    try:
        custody = importlib.import_module("medscale.mesc._mrl_0801_acquisition_custody_v1")
        acquisition = importlib.import_module("medscale.mesc._mrl_0801_hf_acquisition_v1")
    except ImportError:
        raise AcquisitionEntrypointError(
            "repository acquisition modules could not be imported"
        ) from None
    expected_custody = (
        repository_root / "src/medscale/mesc/_mrl_0801_acquisition_custody_v1.py"
    ).resolve(strict=True)
    expected_acquisition = (repository_root / _MODULE_RELATIVE_PATH).resolve(strict=True)
    _require_module_file(custody, expected_custody, label="custody contract")
    _require_module_file(acquisition, expected_acquisition, label="acquisition executor")
    _require_loaded_medscale_modules_match_head(
        repository_root=repository_root,
        source_root=source_root_path,
    )
    return custody, acquisition


def _is_descendant(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _require_no_existing_symlink_components(path: Path, *, label: str) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            raise AcquisitionEntrypointError(f"{label} must not traverse a symbolic link")


def _require_receipt_output_descriptor_support() -> None:
    if _O_DIRECTORY == 0 or _O_NOFOLLOW == 0 or _O_TMPFILE == 0:
        raise AcquisitionEntrypointError(
            "platform lacks required no-follow or unnamed-file receipt support"
        )
    required_dir_fd = (os.mkdir, os.open, os.rmdir, os.stat, os.unlink)
    if any(operation not in os.supports_dir_fd for operation in required_dir_fd):
        raise AcquisitionEntrypointError(
            "platform lacks required descriptor-relative receipt-output operations"
        )
    if _load_posix_symbol("linkat") is None:
        raise AcquisitionEntrypointError(
            "platform lacks required atomic receipt publication support"
        )


def _stat_identity(observation: os.stat_result) -> tuple[int, int]:
    return observation.st_dev, observation.st_ino


def _require_bound_output_parent_identity(output: _BoundReceiptOutput) -> None:
    try:
        opened = os.fstat(output.descriptor)
        current = output.parent_path.stat(follow_symlinks=False)
    except OSError:
        raise AcquisitionEntrypointError(
            "receipt output parent changed during publication"
        ) from None
    expected = (output.device, output.inode)
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(current.st_mode)
        or _stat_identity(opened) != expected
        or _stat_identity(current) != expected
    ):
        raise AcquisitionEntrypointError("receipt output parent changed during publication")


def _descriptor_output_stat(output: _BoundReceiptOutput) -> os.stat_result | None:
    try:
        return os.stat(
            output.name,
            dir_fd=output.descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return None
    except OSError:
        raise AcquisitionEntrypointError(
            "receipt output entry could not be inspected safely"
        ) from None


def _require_owned_output_identity(output: _BoundReceiptOutput) -> None:
    if output.created_device is None or output.created_inode is None:
        raise AcquisitionEntrypointError("receipt output has no transaction-created identity")
    observed = _descriptor_output_stat(output)
    expected = (output.created_device, output.created_inode)
    if (
        observed is None
        or not stat.S_ISREG(observed.st_mode)
        or _stat_identity(observed) != expected
    ):
        raise AcquisitionEntrypointError("receipt output name changed during publication")


def _require_external_new_output(
    *,
    path: Path,
    repository_root: Path,
    snapshot_root: Path,
) -> _BoundReceiptOutput:
    repo = repository_root.resolve(strict=True)
    snapshot = snapshot_root.expanduser().absolute().resolve(strict=False)
    raw = path.expanduser().absolute()
    if not raw.name:
        raise AcquisitionEntrypointError("receipt output must name a file")
    if raw == repo or _is_descendant(raw, repo):
        raise AcquisitionEntrypointError("receipt output must be outside the repository")
    if raw == snapshot or _is_descendant(raw, snapshot):
        raise AcquisitionEntrypointError("receipt output must be outside the raw snapshot root")
    _require_no_existing_symlink_components(raw, label="receipt output")
    value = raw.resolve(strict=False)
    if value == repo or _is_descendant(value, repo):
        raise AcquisitionEntrypointError("receipt output must be outside the repository")
    if value == snapshot or _is_descendant(value, snapshot):
        raise AcquisitionEntrypointError("receipt output must be outside the raw snapshot root")
    if value.exists():
        raise AcquisitionEntrypointError("receipt output must not already exist")

    try:
        parent = raw.parent.resolve(strict=True)
    except OSError:
        raise AcquisitionEntrypointError(
            "receipt output parent must already exist as a real directory"
        ) from None
    _require_no_existing_symlink_components(raw, label="receipt output")
    value = parent / raw.name
    if value == repo or _is_descendant(value, repo):
        raise AcquisitionEntrypointError("receipt output must be outside the repository")
    if value == snapshot or _is_descendant(value, snapshot):
        raise AcquisitionEntrypointError("receipt output must be outside the raw snapshot root")
    if value.exists():
        raise AcquisitionEntrypointError("receipt output must not already exist")

    _require_receipt_output_descriptor_support()
    before_open = parent.stat(follow_symlinks=False)
    if not stat.S_ISDIR(before_open.st_mode):
        raise AcquisitionEntrypointError("receipt output parent must be a real directory")
    flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
    try:
        descriptor = os.open(parent, flags)
    except OSError:
        raise AcquisitionEntrypointError(
            "receipt output parent could not be opened safely"
        ) from None
    try:
        opened = os.fstat(descriptor)
        current = parent.stat(follow_symlinks=False)
        expected = _stat_identity(before_open)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(current.st_mode)
            or _stat_identity(opened) != expected
            or _stat_identity(current) != expected
        ):
            raise AcquisitionEntrypointError(
                "receipt output parent changed while it was being bound"
            )
        output = _BoundReceiptOutput(
            path=value,
            parent_path=parent,
            descriptor=descriptor,
            device=opened.st_dev,
            inode=opened.st_ino,
            name=value.name,
        )
        if _descriptor_output_stat(output) is not None:
            raise AcquisitionEntrypointError("receipt output must not already exist")
        _probe_receipt_atomic_publication(output)
        _require_bound_output_parent_identity(output)
        if _descriptor_output_stat(output) is not None:
            raise AcquisitionEntrypointError(
                "receipt output appeared during atomic publication preflight"
            )
        return output
    except BaseException:
        os.close(descriptor)
        raise


def _load_posix_symbol(name: str) -> Any:
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


def _probe_receipt_atomic_publication(output: _BoundReceiptOutput) -> None:
    """Prove receipt atomic publication on the bound filesystem before acquisition."""
    _require_bound_output_parent_identity(output)
    probe_dir_name = f".mrl-0801-receipt-probe-{secrets.token_hex(16)}"
    probe_fd: int | None = None
    source_fd: int | None = None
    created_dir = False
    published = False
    try:
        os.mkdir(probe_dir_name, 0o700, dir_fd=output.descriptor)
        created_dir = True
        probe_fd = os.open(
            probe_dir_name,
            os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC,
            dir_fd=output.descriptor,
        )
        probe_directory = os.fstat(probe_fd)
        if not stat.S_ISDIR(probe_directory.st_mode):
            raise AcquisitionEntrypointError(
                "atomic receipt publication probe did not bind a directory"
            )
        try:
            source_fd = os.open(
                ".",
                os.O_WRONLY | _O_TMPFILE | _O_CLOEXEC,
                0o600,
                dir_fd=probe_fd,
            )
        except OSError:
            raise AcquisitionEntrypointError(
                "unnamed receipt publication is unsupported on this filesystem"
            ) from None
        source = os.fstat(source_fd)
        if not stat.S_ISREG(source.st_mode):
            raise AcquisitionEntrypointError(
                "atomic receipt publication probe did not create a regular file"
            )
        probe_output = _BoundReceiptOutput(
            path=output.parent_path / probe_dir_name / "probe",
            parent_path=output.parent_path / probe_dir_name,
            descriptor=probe_fd,
            device=probe_directory.st_dev,
            inode=probe_directory.st_ino,
            name="probe",
        )
        _publish_open_descriptor_no_replace(source_fd=source_fd, output=probe_output)
        published = True
        linked = _descriptor_output_stat(probe_output)
        if (
            linked is None
            or not stat.S_ISREG(linked.st_mode)
            or _stat_identity(linked) != _stat_identity(source)
        ):
            raise AcquisitionEntrypointError(
                "atomic receipt publication probe produced an invalid identity"
            )
        os.unlink("probe", dir_fd=probe_fd)
        published = False
        os.close(source_fd)
        source_fd = None
        os.close(probe_fd)
        probe_fd = None
        os.rmdir(probe_dir_name, dir_fd=output.descriptor)
        created_dir = False
        _require_bound_output_parent_identity(output)
    except AcquisitionEntrypointError:
        raise
    except OSError:
        raise AcquisitionEntrypointError(
            "atomic receipt publication capability probe failed safely"
        ) from None
    finally:
        if source_fd is not None:
            with contextlib.suppress(OSError):
                os.close(source_fd)
        if probe_fd is not None:
            if published:
                with contextlib.suppress(OSError):
                    os.unlink("probe", dir_fd=probe_fd)
            with contextlib.suppress(OSError):
                os.close(probe_fd)
        if created_dir:
            with contextlib.suppress(OSError):
                os.rmdir(probe_dir_name, dir_fd=output.descriptor)


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


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    custody_output: _BoundReceiptOutput | None = None
    provenance_output: _BoundReceiptOutput | None = None
    try:
        repository_root = _require_clean_repository_before_import(args.repository_root)
        custody_module, acquisition_module = _import_exact_repository_modules(repository_root)
        authorization_path = (repository_root / _AUTHORIZATION_RELATIVE_PATH).resolve(strict=True)
        authorization = custody_module.parse_mrl_0801_acquisition_authorization(
            authorization_path.read_bytes()
        )
        custody_output = _require_external_new_output(
            path=args.custody_receipt_output,
            repository_root=repository_root,
            snapshot_root=args.destination,
        )
        custody_output_path = custody_output
        provenance_output = _require_external_new_output(
            path=args.provenance_receipt_output,
            repository_root=repository_root,
            snapshot_root=args.destination,
        )
        provenance_output_path = provenance_output
        if custody_output_path.path == provenance_output_path.path:
            raise AcquisitionEntrypointError("custody and provenance outputs must be distinct")

        def publish_receipts(custody_value: object, provenance_value: object) -> None:
            custody_bytes = getattr(custody_value, "canonical_bytes", None)
            provenance_bytes = getattr(provenance_value, "canonical_bytes", None)
            if type(custody_bytes) is not bytes or type(provenance_bytes) is not bytes:
                raise AcquisitionEntrypointError("executor returned non-canonical receipt values")
            _write_exact_new(custody_output_path, custody_bytes)
            _write_exact_new(provenance_output_path, provenance_bytes)
            _require_owned_output_identity(custody_output_path)
            _require_owned_output_identity(provenance_output_path)

        custody, provenance = acquisition_module.acquire_mrl_0801_hf_candidate(
            authorization=authorization,
            transport=acquisition_module.UrllibHfPublicTransport(
                timeout_seconds=args.timeout_seconds
            ),
            repository_root=repository_root,
            destination=args.destination,
            model_id=args.model_id,
            revision=args.revision,
            finalizer=publish_receipts,
        )
        print(
            json.dumps(
                {
                    "artifact_identity_sha256": custody.artifact_identity_sha256,
                    "asset_custody_sha256": custody.asset_custody_sha256,
                    "model_id": custody.model_id,
                    "provenance_receipt_sha256": provenance.receipt_sha256,
                    "revision": custody.revision,
                    "weights_sha256": custody.weights_sha256,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return 0
    except (AcquisitionEntrypointError, ImportError, OSError, RuntimeError, ValueError):
        print(
            "MRL-0801 acquisition blocked: bounded acquisition requirements were not met",
            file=sys.stderr,
        )
        return 2
    finally:
        for output in (custody_output, provenance_output):
            if output is not None:
                with contextlib.suppress(OSError):
                    os.close(output.descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
