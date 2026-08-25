from pathlib import Path


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label} matched {count} times, expected exactly once")
    return text.replace(old, new, 1)


source = Path("src/medscale/mesc/_training_hf_local_sft_backend_v1.py")
text = source.read_text(encoding="utf-8")

text = replace_once(
    text,
    '_SHA256_CHUNK: Final = 1024 * 1024\n_REQUIRED_RUNTIME_MODULES: Final = (\n',
    '_SHA256_CHUNK: Final = 1024 * 1024\n'
    '_O_BINARY: Final = getattr(os, "O_BINARY", 0)\n'
    '_O_DIRECTORY: Final = getattr(os, "O_DIRECTORY", 0)\n'
    '_O_NOFOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)\n'
    '_REQUIRED_RUNTIME_MODULES: Final = (\n',
    label="safe-open constants",
)

text = replace_once(
    text,
    '''        started_at = _utc_now()
        staging: Path | None = None
        try:
''',
    '''        started_at = _utc_now()
        staging: Path | None = None
        repository_fd: int | None = None
        publication_fd: int | None = None
        try:
''',
    label="execute fd state",
)

text = replace_once(
    text,
    '''            if final_parent.exists() or final_parent.is_symlink():
                raise HfLocalSftBackendError("planned experiment result root already exists")
            final_parent.parent.mkdir(parents=True, exist_ok=True)
            staging = Path(
                tempfile.mkdtemp(
                    prefix=f".{manifest.experiment_id}.mesc-sft-",
                    dir=final_parent.parent,
                )
            )
''',
    '''            if _path_exists_no_follow(final_parent):
                raise HfLocalSftBackendError("planned experiment result root already exists")
            publication_parent = _prepare_publication_parent(
                final_parent.parent,
                repository_root=self._repository_root,
            )
            repository_fd = _open_directory_fd(
                self._repository_root,
                field="repository_root",
            )
            publication_fd = _open_directory_fd(
                publication_parent,
                field="publication_parent",
            )
            staging = Path(
                tempfile.mkdtemp(
                    prefix=f".{manifest.experiment_id}.mesc-sft-",
                    dir=self._repository_root,
                )
            )
''',
    label="initial publication block",
)

text = replace_once(
    text,
    '''            if final_parent.exists() or final_parent.is_symlink():
                raise HfLocalSftBackendError(
                    "planned experiment result root appeared during training"
                )
            staging.replace(final_parent)
            staging = None
''',
    '''            if publication_fd is None or repository_fd is None:
                raise HfLocalSftBackendError("publication descriptors are unavailable")
            _require_publication_parent_safe(
                publication_parent,
                repository_root=self._repository_root,
            )
            _require_directory_fd_matches_path(
                repository_fd,
                self._repository_root,
                field="repository_root",
            )
            _require_directory_fd_matches_path(
                publication_fd,
                publication_parent,
                field="publication_parent",
            )
            if _path_exists_no_follow(final_parent):
                raise HfLocalSftBackendError(
                    "planned experiment result root appeared during training"
                )
            try:
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
    label="final publication block",
)

text = replace_once(
    text,
    '''        except Exception as exc:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
            return TrainingBackendResult(
                disposition="FAILED",
                backend_id=_BACKEND_ID,
                backend_version=_BACKEND_VERSION,
                started_at=started_at,
                finished_at=_utc_now(),
                artifacts=(),
                failure_reason=_failure_reason(exc),
            )

    def _identify_model(
''',
    '''        except Exception as exc:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
            return TrainingBackendResult(
                disposition="FAILED",
                backend_id=_BACKEND_ID,
                backend_version=_BACKEND_VERSION,
                started_at=started_at,
                finished_at=_utc_now(),
                artifacts=(),
                failure_reason=_failure_reason(exc),
            )
        except BaseException:
            if staging is not None:
                shutil.rmtree(staging, ignore_errors=True)
            raise
        finally:
            if publication_fd is not None:
                os.close(publication_fd)
            if repository_fd is not None:
                os.close(repository_fd)

    def _identify_model(
''',
    label="baseexception cleanup",
)

helpers = '''


def _path_exists_no_follow(path: Path) -> bool:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise HfLocalSftBackendError("publication path could not be inspected safely") from exc
    return True


def _open_directory_fd(path: Path, *, field: str) -> int:
    if _O_DIRECTORY == 0 or _O_NOFOLLOW == 0:
        raise HfLocalSftBackendError(
            "platform cannot enforce descriptor-pinned publication directories"
        )
    flags = os.O_RDONLY | _O_BINARY | _O_DIRECTORY | _O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise HfLocalSftBackendError(f"{field} could not be opened safely") from exc
    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode):
            raise HfLocalSftBackendError(f"{field} descriptor must reference a directory")
    except BaseException:
        os.close(fd)
        raise
    return fd


def _require_directory_fd_matches_path(fd: int, path: Path, *, field: str) -> None:
    try:
        descriptor_info = os.fstat(fd)
        path_info = os.lstat(path)
    except OSError as exc:
        raise HfLocalSftBackendError(f"{field} changed during execution") from exc
    if stat.S_ISLNK(path_info.st_mode) or not stat.S_ISDIR(path_info.st_mode):
        raise HfLocalSftBackendError(f"{field} must remain a non-symlink directory")
    if (descriptor_info.st_dev, descriptor_info.st_ino) != (path_info.st_dev, path_info.st_ino):
        raise HfLocalSftBackendError(f"{field} changed during execution")


def _prepare_publication_parent(
    publication_parent: Path,
    *,
    repository_root: Path,
) -> Path:
    return _walk_publication_parent(
        publication_parent,
        repository_root=repository_root,
        create_missing=True,
    )


def _require_publication_parent_safe(
    publication_parent: Path,
    *,
    repository_root: Path,
) -> None:
    _walk_publication_parent(
        publication_parent,
        repository_root=repository_root,
        create_missing=False,
    )


def _walk_publication_parent(
    publication_parent: Path,
    *,
    repository_root: Path,
    create_missing: bool,
) -> Path:
    try:
        root_info = os.lstat(repository_root)
    except OSError as exc:
        raise HfLocalSftBackendError("repository_root could not be inspected safely") from exc
    if stat.S_ISLNK(root_info.st_mode) or not stat.S_ISDIR(root_info.st_mode):
        raise HfLocalSftBackendError("repository_root must be an existing non-symlink directory")
    try:
        relative = publication_parent.relative_to(repository_root)
    except ValueError as exc:
        raise HfLocalSftBackendError("publication parent must remain inside repository_root") from exc

    current = repository_root
    for part in relative.parts:
        current = current / part
        try:
            info = os.lstat(current)
        except FileNotFoundError:
            if not create_missing:
                raise HfLocalSftBackendError("publication parent disappeared during execution")
            try:
                current.mkdir()
                info = os.lstat(current)
            except OSError as exc:
                raise HfLocalSftBackendError(
                    "publication parent could not be created safely"
                ) from exc
        except OSError as exc:
            raise HfLocalSftBackendError("publication parent could not be inspected safely") from exc
        if stat.S_ISLNK(info.st_mode):
            raise HfLocalSftBackendError("publication parent ancestors must not be symlinks")
        if not stat.S_ISDIR(info.st_mode):
            raise HfLocalSftBackendError("publication parent ancestors must be directories")
        if info.st_dev != root_info.st_dev:
            raise HfLocalSftBackendError(
                "publication parent must remain on the repository filesystem"
            )

    try:
        root_resolved = repository_root.resolve(strict=True)
        current_resolved = current.resolve(strict=True)
    except OSError as exc:
        raise HfLocalSftBackendError("publication parent could not be resolved safely") from exc
    if current_resolved != root_resolved and root_resolved not in current_resolved.parents:
        raise HfLocalSftBackendError("publication parent resolved outside repository_root")
    return current
'''

text = replace_once(
    text,
    '\n\ndef _read_attested_file(path: Path) -> bytes:\n',
    helpers + '\n\ndef _read_attested_file(path: Path) -> bytes:\n',
    label="publication helpers insertion",
)

text = replace_once(
    text,
    '''        if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
            raise HfLocalSftBackendError("runtime output must contain non-empty regular files only")
''',
    '''        if not stat.S_ISREG(info.st_mode) or info.st_size <= 0:
            raise HfLocalSftBackendError("runtime output must contain non-empty regular files only")
        if info.st_nlink != 1:
            raise HfLocalSftBackendError("runtime output files must have exactly one hard link")
''',
    label="collector hardlink check",
)

text = replace_once(
    text,
    '''def _hash_regular_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    byte_count = 0
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(_SHA256_CHUNK)
            if not chunk:
                break
            byte_count += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), byte_count
''',
    '''def _hash_regular_file(path: Path) -> tuple[str, int]:
    if _O_NOFOLLOW == 0:
        raise HfLocalSftBackendError("platform cannot enforce no-follow runtime output hashing")
    flags = os.O_RDONLY | _O_BINARY | _O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise HfLocalSftBackendError("runtime output could not be opened safely") from exc

    digest = hashlib.sha256()
    byte_count = 0
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
            raise HfLocalSftBackendError(
                "runtime output must contain non-empty regular files only"
            )
        if before.st_nlink != 1:
            raise HfLocalSftBackendError("runtime output files must have exactly one hard link")
        while True:
            chunk = os.read(fd, _SHA256_CHUNK)
            if not chunk:
                break
            byte_count += len(chunk)
            digest.update(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)

    if _stat_identity(before) != _stat_identity(after):
        raise HfLocalSftBackendError("runtime output changed while being hashed")
    if byte_count != before.st_size:
        raise HfLocalSftBackendError("runtime output byte count changed while being hashed")
    try:
        current = os.lstat(path)
    except OSError as exc:
        raise HfLocalSftBackendError("runtime output changed after hashing") from exc
    if stat.S_ISLNK(current.st_mode) or not stat.S_ISREG(current.st_mode):
        raise HfLocalSftBackendError("runtime output path changed after hashing")
    if current.st_nlink != 1:
        raise HfLocalSftBackendError("runtime output files must have exactly one hard link")
    if _stat_identity(after) != _stat_identity(current):
        raise HfLocalSftBackendError("runtime output changed after hashing")
    return digest.hexdigest(), byte_count
''',
    label="fd hashing",
)
source.write_text(text, encoding="utf-8", newline="\n")


tests = Path("tests/test_mesc_training_hf_local_sft_backend_v1.py")
text = tests.read_text(encoding="utf-8")

runtime_classes = '''


class _InterruptRuntime(_FakeRuntime):
    def train_seed(
        self,
        *,
        model_root: Path,
        records: tuple[dict[str, object], ...],
        recipe: TrainingRecipe,
        seed: int,
        output_dir: Path,
        profile: HfLocalSftExecutionProfile,
    ) -> HfSftRuntimeResult:
        result = super().train_seed(
            model_root=model_root,
            records=records,
            recipe=recipe,
            seed=seed,
            output_dir=output_dir,
            profile=profile,
        )
        del result
        raise KeyboardInterrupt("fixture interrupt")


class _HardlinkRuntime(_FakeRuntime):
    def __init__(self, source: Path) -> None:
        super().__init__()
        self.source = source

    def train_seed(
        self,
        *,
        model_root: Path,
        records: tuple[dict[str, object], ...],
        recipe: TrainingRecipe,
        seed: int,
        output_dir: Path,
        profile: HfLocalSftExecutionProfile,
    ) -> HfSftRuntimeResult:
        assert model_root.is_dir()
        assert records
        assert recipe.recipe_id
        assert profile.max_length == 2048
        self.calls.append(seed)
        (output_dir / "adapter_model.safetensors").hardlink_to(self.source)
        (output_dir / "adapter_config.json").write_text(
            '{"peft_type":"LORA"}\n',
            encoding="utf-8",
        )
        return HfSftRuntimeResult(
            metrics=(("train_loss", float(seed) / 100.0),),
            packages=(("trl", "fixture"),),
        )
'''

text = replace_once(
    text,
    '\n\ndef _recipe(*, model_id: str = "example/model") -> TrainingRecipe:\n',
    runtime_classes + '\n\ndef _recipe(*, model_id: str = "example/model") -> TrainingRecipe:\n',
    label="regression runtime classes",
)

security_tests = '''


def test_interrupt_cleans_staging_and_reraises(tmp_path: Path) -> None:
    runtime = _InterruptRuntime()
    backend, manifest = _backend(tmp_path, runtime)

    with pytest.raises(KeyboardInterrupt, match="fixture interrupt"):
        backend.execute(manifest=manifest)

    repository_root = tmp_path / "repo"
    assert runtime.calls == [17]
    assert not (repository_root / "experiments" / "mesc-t6-compact-sft").exists()
    assert not tuple(repository_root.glob(".mesc-t6-compact-sft.mesc-sft-*"))


def test_symlinked_publication_ancestor_fails_before_runtime(tmp_path: Path) -> None:
    runtime = _FakeRuntime()
    backend, manifest = _backend(tmp_path, runtime)
    repository_root = tmp_path / "repo"
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (repository_root / "experiments").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable on this platform")

    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == []
    assert "symlink" in (result.failure_reason or "")
    assert not (outside / "mesc-t6-compact-sft").exists()


def test_hardlinked_runtime_output_fails_closed(tmp_path: Path) -> None:
    external = tmp_path / "external-adapter.safetensors"
    external.write_bytes(b"external-adapter")
    runtime = _HardlinkRuntime(external)
    backend, manifest = _backend(tmp_path, runtime)

    result = backend.execute(manifest=manifest)

    assert result.disposition == "FAILED"
    assert runtime.calls == [17, 42]
    assert result.artifacts == ()
    assert "hard link" in (result.failure_reason or "")
    assert external.read_bytes() == b"external-adapter"
    repository_root = tmp_path / "repo"
    assert not (repository_root / "experiments" / "mesc-t6-compact-sft").exists()
    assert not tuple(repository_root.glob(".mesc-t6-compact-sft.mesc-sft-*"))
'''

text = replace_once(
    text,
    '\n\ndef test_model_weight_mismatch_fails_before_runtime(tmp_path: Path) -> None:\n',
    security_tests + '\n\ndef test_model_weight_mismatch_fails_before_runtime(tmp_path: Path) -> None:\n',
    label="security regression tests",
)

text = replace_once(
    text,
    '    assert not tuple((tmp_path / "repo" / "experiments").glob(".*.mesc-sft-*"))\n',
    '    assert not tuple((tmp_path / "repo").glob(".mesc-t6-compact-sft.mesc-sft-*"))\n',
    label="success staging assertion",
)
tests.write_text(text, encoding="utf-8", newline="\n")


spec = Path("specs/mesc-hf-local-sft-backend-v1/README.md")
text = spec.read_text(encoding="utf-8")
text = replace_once(
    text,
    '''The backend:

1. creates a private staging directory beside the final experiment root on the same
   filesystem;
2. trains every seed only into staging;
3. writes the summary only into staging;
4. rejects symlink, empty, non-regular, or namespace-escaping outputs;
5. hashes every final file into canonical `TrainingResultArtifact` values;
6. rechecks that the final result root still does not exist; and
7. atomically renames the complete staged experiment root into its final location.

Any exception before publication deletes staging and returns a canonical `FAILED`
`TrainingBackendResult` with no result artifacts.
''',
    '''The backend:

1. validates every existing publication-path ancestor below `repository_root` as a real
   non-symlink directory, creates missing ancestors one at a time, requires the resolved
   parent to remain inside the repository and on the same filesystem, and pins repository
   and publication directories with no-follow descriptors;
2. creates a private staging directory directly beneath the validated repository root;
3. trains every seed only into staging;
4. writes the summary only into staging;
5. rejects symlink, empty, non-regular, namespace-escaping, or multi-link outputs;
6. hashes every final file through a no-follow file descriptor, requiring stable
   descriptor identity and a single hard link before and after hashing;
7. revalidates publication ancestors and pinned directory identities and rechecks that the
   final result root still does not exist; and
8. atomically renames the complete staged experiment root with pinned source and
   destination directory descriptors.

Any ordinary exception before publication deletes staging and returns a canonical
`FAILED` `TrainingBackendResult` with no result artifacts. `KeyboardInterrupt`,
`SystemExit`, and other `BaseException` subclasses also delete staging, but are re-raised
instead of being converted into canonical failure results.
''',
    label="atomic publication spec",
)
text = replace_once(
    text,
    '- runtime failure cleanup;\n- no result overwrite;\n- namespace confinement;\n',
    '- runtime failure and interrupt cleanup;\n- no result overwrite;\n'
    '- symlinked publication-ancestor rejection;\n- namespace confinement;\n'
    '- hardlink rejection and descriptor-based no-follow artifact hashing;\n',
    label="default CI spec bullets",
)
text = replace_once(
    text,
    '- no existing result overwrite;\n- failed execution publishes no canonical artifacts;\n'
    '- successful execution atomically publishes both planned namespaces; and\n'
    '- returned artifact hashes and byte counts describe the published files.\n',
    '- no existing result overwrite;\n'
    '- publication ancestors cannot redirect writes through symlinks or another filesystem;\n'
    '- runtime artifact hashing is no-follow, single-link, and descriptor-stable;\n'
    '- failed or interrupted execution leaves no staged canonical artifacts;\n'
    '- successful execution atomically publishes both planned namespaces; and\n'
    '- returned artifact hashes and byte counts describe the published files.\n',
    label="acceptance spec bullets",
)
spec.write_text(text, encoding="utf-8", newline="\n")
