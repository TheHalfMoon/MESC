from pathlib import Path


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label} matched {count} times, expected exactly once")
    return text.replace(old, new, 1)


source = Path("src/medscale/mesc/_training_hf_local_sft_backend_v1.py")
text = source.read_text(encoding="utf-8")
text = replace_once(text, "import hashlib\n", "import ctypes\nimport errno\nimport hashlib\n", label="stdlib imports")
text = replace_once(
    text,
    '_O_NOFOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)\n',
    '_O_NOFOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)\n_RENAME_NOREPLACE: Final = 1\n',
    label="rename noreplace constant",
)
text = replace_once(
    text,
    '''            summary = {
                "backend_id": _BACKEND_ID,
                "backend_version": _BACKEND_VERSION,
                "execution_manifest_sha256": manifest.execution_manifest_sha256,
                "experiment_id": manifest.experiment_id,
                "model_id": manifest.model_id,
                "profile": self._profile.to_dict(),
                "recipe_id": manifest.recipe_id,
                "revision": manifest.revision,
                "role": manifest.role,
                "seed_runs": seed_observations,
                "training_dataset_sha256": manifest.training_dataset_sha256,
                "weights_sha256": manifest.weights_sha256,
            }
''',
    '''            finished_at = _utc_now()
            summary = {
                "backend_id": _BACKEND_ID,
                "backend_version": _BACKEND_VERSION,
                "disposition": "SUCCEEDED",
                "execution_manifest_sha256": manifest.execution_manifest_sha256,
                "experiment_id": manifest.experiment_id,
                "finished_at": finished_at,
                "model_id": manifest.model_id,
                "profile": self._profile.to_dict(),
                "recipe_id": manifest.recipe_id,
                "result_parent": final_parent_relative,
                "revision": manifest.revision,
                "role": manifest.role,
                "seed_runs": seed_observations,
                "started_at": started_at,
                "training_dataset_sha256": manifest.training_dataset_sha256,
                "weights_sha256": manifest.weights_sha256,
            }
''',
    label="completion-bound summary",
)
text = replace_once(
    text,
    '''            try:
                os.replace(
                    staging.name,
                    final_parent.name,
                    src_dir_fd=repository_fd,
                    dst_dir_fd=publication_fd,
                )
            except OSError as exc:
                raise HfLocalSftBackendError(
                    "staged experiment root could not be published atomically"
                ) from exc
            staging = None
''',
    '''            _rename_no_replace(
                source_name=staging.name,
                destination_name=final_parent.name,
                source_dir_fd=repository_fd,
                destination_dir_fd=publication_fd,
            )
            staging = None
''',
    label="atomic no-replace publication",
)
text = replace_once(
    text,
    '''                started_at=started_at,
                finished_at=_utc_now(),
                artifacts=staged_artifacts,
''',
    '''                started_at=started_at,
                finished_at=finished_at,
                artifacts=staged_artifacts,
''',
    label="successful result timestamp binding",
)
helper_marker = "\n\ndef _resolve_result_parent(\n"
helper = '''


def _rename_no_replace(
    *,
    source_name: str,
    destination_name: str,
    source_dir_fd: int,
    destination_dir_fd: int,
) -> None:
    """Atomically publish one directory without replacing an existing destination."""
    if os.name != "posix":
        raise HfLocalSftBackendError(
            "platform cannot enforce atomic no-replace publication"
        )
    try:
        libc: Any = ctypes.CDLL(None, use_errno=True)
        renameat2: Any = libc.renameat2
    except (AttributeError, OSError) as exc:
        raise HfLocalSftBackendError(
            "platform cannot enforce atomic no-replace publication"
        ) from exc

    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    ctypes.set_errno(0)
    result = renameat2(
        source_dir_fd,
        os.fsencode(source_name),
        destination_dir_fd,
        os.fsencode(destination_name),
        _RENAME_NOREPLACE,
    )
    if result == 0:
        return

    error_number = ctypes.get_errno()
    if error_number == errno.EEXIST:
        raise HfLocalSftBackendError(
            "planned experiment result root appeared during publication"
        )

    unsupported_errors = {errno.EINVAL, errno.ENOSYS}
    for name in ("ENOTSUP", "EOPNOTSUPP"):
        value = getattr(errno, name, None)
        if isinstance(value, int):
            unsupported_errors.add(value)
    if error_number in unsupported_errors:
        raise HfLocalSftBackendError(
            "filesystem cannot enforce atomic no-replace publication"
        )

    cause = OSError(error_number, os.strerror(error_number))
    raise HfLocalSftBackendError(
        "staged experiment root could not be published atomically"
    ) from cause
'''
text = replace_once(text, helper_marker, helper + helper_marker, label="no-replace helper insertion")
source.write_text(text, encoding="utf-8", newline="\n")


tests = Path("tests/test_mesc_training_hf_local_sft_backend_v1.py")
text = tests.read_text(encoding="utf-8")
text = replace_once(
    text,
    "import pytest\n\n",
    "import pytest\n\nimport medscale.mesc._training_hf_local_sft_backend_v1 as backend_module\n",
    label="backend module test import",
)
text = replace_once(
    text,
    '''    assert (final_root / "outputs").is_dir()
    assert (final_root / "results").is_dir()
    assert not tuple((tmp_path / "repo").glob(".mesc-t6-compact-sft.mesc-sft-*"))
''',
    '''    assert (final_root / "outputs").is_dir()
    assert (final_root / "results").is_dir()
    summary = json.loads((final_root / "results" / "training-summary.json").read_text())
    assert summary["disposition"] == "SUCCEEDED"
    assert summary["started_at"] == result.started_at
    assert summary["finished_at"] == result.finished_at
    assert summary["result_parent"] == "experiments/mesc-t6-compact-sft"
    assert not tuple((tmp_path / "repo").glob(".mesc-t6-compact-sft.mesc-sft-*"))
''',
    label="published completion summary assertions",
)
race_marker = "\n\ndef test_runtime_failure_returns_failed_without_canonical_artifacts(tmp_path: Path) -> None:\n"
race_test = '''


def test_publication_race_never_overwrites_existing_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _FakeRuntime()
    backend, manifest = _backend(tmp_path, runtime)
    final_root = tmp_path / "repo" / "experiments" / "mesc-t6-compact-sft"
    original_publish = backend_module._rename_no_replace

    def raced_publish(
        *,
        source_name: str,
        destination_name: str,
        source_dir_fd: int,
        destination_dir_fd: int,
    ) -> None:
        final_root.mkdir(parents=True)
        original_publish(
            source_name=source_name,
            destination_name=destination_name,
            source_dir_fd=source_dir_fd,
            destination_dir_fd=destination_dir_fd,
        )

    monkeypatch.setattr(backend_module, "_rename_no_replace", raced_publish)
    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == [17, 42]
    assert result.artifacts == ()
    assert "appeared during publication" in (result.failure_reason or "")
    assert final_root.is_dir()
    assert not tuple(final_root.iterdir())
    assert not tuple((tmp_path / "repo").glob(".mesc-t6-compact-sft.mesc-sft-*"))
'''
text = replace_once(text, race_marker, race_test + race_marker, label="publication race regression")
tests.write_text(text, encoding="utf-8", newline="\n")


spec = Path("specs/mesc-hf-local-sft-backend-v1/README.md")
text = spec.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''8. atomically renames the complete staged experiment root with pinned source and
   destination directory descriptors.
''',
    '''8. atomically renames the complete staged experiment root with pinned source and
   destination directory descriptors using an operating-system no-replace primitive; if
   the primitive or filesystem guarantee is unavailable, publication fails closed.
''',
    label="spec atomic publication primitive",
)
text = replace_once(
    text,
    '''The backend never overwrites a prior experiment result root.

## Timestamp and failure behavior
''',
    '''The backend never overwrites a prior experiment result root, including one that
appears after the final existence check but before the atomic rename.

The successful no-replace rename is the backend publication commit point. Before that
commit, `training-summary.json` already binds `disposition = SUCCEEDED`, the exact backend
start/finish timestamps, and the repository-relative result parent. If an asynchronous
interrupt is delivered after the commit but before the caller receives the returned
`TrainingBackendResult`, the complete backend-published root may remain with that
self-contained completion evidence, while the core `TrainingExecutionReceipt` can still
be absent. Such a root is a reconciliation state and must not be interpreted as complete
core-executor success without the separately constructed core receipt. The backend does
not attempt a racy post-commit rollback.

## Timestamp and failure behavior
''',
    label="spec publication commit semantics",
)
text = replace_once(
    text,
    '''- normalized runtime metrics; and
- observed runtime package versions.
''',
    '''- normalized runtime metrics;
- observed runtime package versions;
- backend success disposition and exact start/finish timestamps; and
- the repository-relative result parent committed by the backend.
''',
    label="spec summary completion fields",
)
text = replace_once(
    text,
    '''- no existing result overwrite;
- publication ancestors cannot redirect writes through symlinks or another filesystem;
''',
    '''- atomic no-replace publication prevents an existing or concurrently appearing
  result root from being overwritten and fails closed if the platform/filesystem cannot
  enforce that guarantee;
- publication ancestors cannot redirect writes through symlinks or another filesystem;
''',
    label="spec acceptance no replace",
)
spec.write_text(text, encoding="utf-8", newline="\n")
