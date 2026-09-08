from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise RuntimeError(f"{path}: replacement count mismatch")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


module = Path("src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py")
replace_once(
    module,
    '''def _require_descriptor_relative_support() -> None:
    if _O_DIRECTORY == 0 or _O_NOFOLLOW == 0:
        raise MRL0801HfAcquisitionError(
            "platform lacks required no-follow directory descriptor support"
        )
    required_dir_fd = (os.open, os.stat, os.unlink, os.link)
    if any(operation not in os.supports_dir_fd for operation in required_dir_fd):
        raise MRL0801HfAcquisitionError(
            "platform lacks required descriptor-relative filesystem operations"
        )
    if os.listdir not in os.supports_fd or os.link not in os.supports_follow_symlinks:
        raise MRL0801HfAcquisitionError(
            "platform lacks required descriptor-safe listing or linking support"
        )
    if not hasattr(os, "fstatvfs"):
        raise MRL0801HfAcquisitionError(
            "platform lacks descriptor-relative storage-capacity inspection"
        )
''',
    '''def _require_descriptor_relative_support() -> None:
    if _O_DIRECTORY == 0 or _O_NOFOLLOW == 0 or _O_TMPFILE == 0:
        raise MRL0801HfAcquisitionError(
            "platform lacks required no-follow or unnamed-file descriptor support"
        )
    required_dir_fd = (os.open, os.stat)
    if any(operation not in os.supports_dir_fd for operation in required_dir_fd):
        raise MRL0801HfAcquisitionError(
            "platform lacks required descriptor-relative filesystem operations"
        )
    if os.listdir not in os.supports_fd:
        raise MRL0801HfAcquisitionError(
            "platform lacks required descriptor-safe directory listing"
        )
    if _load_posix_symbol("linkat") is None:
        raise MRL0801HfAcquisitionError(
            "platform lacks required atomic descriptor publication support"
        )
    if not hasattr(os, "fstatvfs"):
        raise MRL0801HfAcquisitionError(
            "platform lacks descriptor-relative storage-capacity inspection"
        )
''',
)
replace_once(
    module,
    '''        if os.listdir(descriptor):  # noqa: PTH208 -- descriptor-relative listing is required
            raise MRL0801HfAcquisitionError(
                "acquisition destination must be an empty real directory"
            )
        return _DestinationDirectory(
''',
    '''        if os.listdir(descriptor):  # noqa: PTH208 -- descriptor-relative listing is required
            raise MRL0801HfAcquisitionError(
                "acquisition destination must be an empty real directory"
            )
        probe = _open_unnamed_temp_file(root_fd=descriptor)
        os.close(probe)
        return _DestinationDirectory(
''',
)

cli = Path("scripts/mesc_mrl_0801_hf_acquire.py")
replace_once(
    cli,
    '''def _require_receipt_output_descriptor_support() -> None:
    if _O_DIRECTORY == 0 or _O_NOFOLLOW == 0:
        raise AcquisitionEntrypointError(
            "platform lacks required no-follow receipt-output descriptor support"
        )
    required_dir_fd = (os.open, os.stat, os.unlink)
    if any(operation not in os.supports_dir_fd for operation in required_dir_fd):
        raise AcquisitionEntrypointError(
            "platform lacks required descriptor-relative receipt-output operations"
        )
''',
    '''def _require_receipt_output_descriptor_support() -> None:
    if _O_DIRECTORY == 0 or _O_NOFOLLOW == 0 or _O_TMPFILE == 0:
        raise AcquisitionEntrypointError(
            "platform lacks required no-follow or unnamed-file receipt support"
        )
    required_dir_fd = (os.open, os.stat)
    if any(operation not in os.supports_dir_fd for operation in required_dir_fd):
        raise AcquisitionEntrypointError(
            "platform lacks required descriptor-relative receipt-output operations"
        )
    if _load_posix_symbol("linkat") is None:
        raise AcquisitionEntrypointError(
            "platform lacks required atomic receipt publication support"
        )
''',
)
replace_once(
    cli,
    '''        if _descriptor_output_stat(output) is not None:
            raise AcquisitionEntrypointError("receipt output must not already exist")
        return output
''',
    '''        if _descriptor_output_stat(output) is not None:
            raise AcquisitionEntrypointError("receipt output must not already exist")
        try:
            probe = os.open(
                ".",
                os.O_WRONLY | _O_TMPFILE | _O_CLOEXEC,
                0o600,
                dir_fd=output.descriptor,
            )
        except OSError:
            raise AcquisitionEntrypointError(
                "unnamed receipt publication is unsupported on this filesystem"
            ) from None
        os.close(probe)
        return output
''',
)

print("atomic publication capability checks updated")
