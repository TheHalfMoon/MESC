from __future__ import annotations

import re
from pathlib import Path


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


def replace_regex_once(text: str, pattern: str, replacement: str, *, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one regex match, got {count}")
    return updated


root = Path('.')
core_path = root / 'src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py'
cli_path = root / 'scripts/mesc_mrl_0801_hf_acquire.py'
acq_test_path = root / 'tests/test_mesc_mrl_0801_hf_acquisition_v1.py'
witness_test_path = root / 'tests/test_mesc_mrl_0801_hf_witness_v1.py'
cli_test_path = root / 'tests/test_mesc_mrl_0801_hf_acquire_cli.py'
spec_path = root / 'specs/mesc-experiment-0/mrl-0801-hf-acquisition-provenance-v1.md'

core = core_path.read_text(encoding='utf-8')
core = replace_once(
    core,
    '    destination: Path,\n    model_id: str,\n    revision: str,\n    finalizer:',
    '    destination: Path,\n    model_id: str,\n    revision: str,\n    witness_root: Path | None = None,\n    finalizer:',
    label='core acquire witness parameter',
)
core = replace_once(
    core,
    '    destination_root = _require_external_empty_destination(\n        destination=destination,\n        repository_root=repository_root,\n    )',
    '    destination_root = _require_external_empty_destination(\n        destination=destination,\n        repository_root=repository_root,\n        witness_root=witness_root,\n    )',
    label='core acquire destination witness binding',
)
new_destination = '''def _require_external_witness_root(
    *,
    witness_root: Path,
    repository_root: Path,
    transaction_root: Path,
    expected_device: int,
) -> _DestinationDirectory:
    repo = repository_root.resolve(strict=True)
    raw = witness_root.expanduser().absolute()
    if raw == repo or _is_descendant(raw, repo):
        raise MRL0801HfAcquisitionError("capability witness root must be outside Git")
    _require_no_existing_symlink_components(raw, label="capability witness root")
    try:
        root = raw.resolve(strict=True)
    except OSError:
        raise MRL0801HfAcquisitionError(
            "capability witness root must be an existing real directory"
        ) from None
    if root == repo or _is_descendant(root, repo):
        raise MRL0801HfAcquisitionError("capability witness root must be outside Git")
    for ancestor in (root, *root.parents):
        if (ancestor / ".git").exists():
            raise MRL0801HfAcquisitionError("capability witness root is inside a Git work tree")
    if (
        root == transaction_root
        or _is_descendant(root, transaction_root)
        or _is_descendant(transaction_root, root)
    ):
        raise MRL0801HfAcquisitionError(
            "capability witness root must be separate from the transaction directory"
        )
    _require_descriptor_relative_support()
    flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
    try:
        descriptor = os.open(root, flags)
    except OSError:
        raise MRL0801HfAcquisitionError(
            "capability witness root could not be opened safely"
        ) from None
    try:
        opened = os.fstat(descriptor)
        current = root.stat(follow_symlinks=False)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(current.st_mode)
            or _stat_descriptor_identity(opened) != _stat_descriptor_identity(current)
        ):
            raise MRL0801HfAcquisitionError(
                "capability witness root changed while it was being bound"
            )
        if opened.st_dev != expected_device:
            raise MRL0801HfAcquisitionError(
                "capability witness root must be on the transaction filesystem"
            )
        return _DestinationDirectory(
            path=root,
            descriptor=descriptor,
            device=opened.st_dev,
            inode=opened.st_ino,
        )
    except BaseException:
        os.close(descriptor)
        raise


def _require_external_empty_destination(
    *,
    destination: Path,
    repository_root: Path,
    witness_root: Path | None = None,
) -> _DestinationDirectory:
    repo = repository_root.resolve(strict=True)
    raw = destination.expanduser().absolute()
    if raw == repo or _is_descendant(raw, repo):
        raise MRL0801HfAcquisitionError("raw model snapshot destination must be outside Git")
    _require_no_existing_symlink_components(raw, label="raw model snapshot destination")
    try:
        root = raw.resolve(strict=True)
    except OSError:
        raise MRL0801HfAcquisitionError(
            "acquisition destination must be an existing real empty directory"
        ) from None
    if root == repo or _is_descendant(root, repo):
        raise MRL0801HfAcquisitionError("raw model snapshot destination must be outside Git")
    for ancestor in (root, *root.parents):
        if (ancestor / ".git").exists():
            raise MRL0801HfAcquisitionError(
                "raw model snapshot destination is inside a Git work tree"
            )
    _require_descriptor_relative_support()
    flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
    try:
        descriptor = os.open(root, flags)
    except OSError:
        raise MRL0801HfAcquisitionError(
            "acquisition destination must be an existing non-symlink directory"
        ) from None
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode):
            raise MRL0801HfAcquisitionError(
                "acquisition destination descriptor must reference a directory"
            )
        path_observation = root.stat(follow_symlinks=False)
        if _stat_descriptor_identity(opened) != _stat_descriptor_identity(path_observation):
            raise MRL0801HfAcquisitionError(
                "acquisition destination changed while it was being opened"
            )
        if os.listdir(descriptor):  # noqa: PTH208 -- descriptor-relative listing is required
            raise MRL0801HfAcquisitionError(
                "acquisition destination must be an empty real directory"
            )
        if witness_root is None:
            raise MRL0801HfAcquisitionError("capability witness root is required")
        witness = _require_external_witness_root(
            witness_root=witness_root,
            repository_root=repository_root,
            transaction_root=root,
            expected_device=opened.st_dev,
        )
        try:
            _probe_atomic_descriptor_publication(root_fd=witness.descriptor)
            witness_current = witness.path.stat(follow_symlinks=False)
            if (
                not stat.S_ISDIR(witness_current.st_mode)
                or _stat_descriptor_identity(witness_current) != (witness.device, witness.inode)
            ):
                raise MRL0801HfAcquisitionError(
                    "capability witness root changed during publication proof"
                )
        finally:
            os.close(witness.descriptor)
        if os.listdir(descriptor):  # noqa: PTH208 -- descriptor-relative listing is required
            raise MRL0801HfAcquisitionError(
                "acquisition destination changed during atomic publication preflight"
            )
        return _DestinationDirectory(
            path=root,
            descriptor=descriptor,
            device=opened.st_dev,
            inode=opened.st_ino,
        )
    except BaseException:
        os.close(descriptor)
        raise
'''
core = replace_regex_once(
    core,
    r'def _require_external_empty_destination\(.*?\n\ndef _require_no_existing_symlink_components',
    new_destination + '\n\ndef _require_no_existing_symlink_components',
    label='core destination and witness root implementation',
)
core = replace_once(
    core,
    'def _probe_atomic_descriptor_publication(*, root_fd: int) -> None:\n    """Prove atomic publication, retain the witness, and block before remote access."""',
    'def _probe_atomic_descriptor_publication(*, root_fd: int) -> None:\n    """Prove atomic no-replace publication and retain the witness as evidence."""',
    label='core probe docstring',
)
core = replace_once(
    core,
    '        raise MRL0801HfAcquisitionError(\n            "atomic publication capability proven; witness retained because safe atomic "\n            "cleanup is unavailable, so remote access is blocked"\n        )',
    '        return',
    label='core probe operational continuation',
)
core_path.write_text(core, encoding='utf-8')

cli = cli_path.read_text(encoding='utf-8')
cli = replace_once(
    cli,
    '    parser.add_argument("--destination", type=Path, required=True)\n',
    '    parser.add_argument("--destination", type=Path, required=True)\n    parser.add_argument("--model-witness-root", type=Path, required=True)\n    parser.add_argument("--receipt-witness-root", type=Path, required=True)\n',
    label='cli witness args',
)
cli = replace_once(
    cli,
    '    snapshot_root: Path,\n) -> _BoundReceiptOutput:',
    '    snapshot_root: Path,\n    witness_root: Path | None = None,\n) -> _BoundReceiptOutput:',
    label='cli output witness parameter',
)
cli = replace_once(
    cli,
    '        _probe_receipt_atomic_publication(output)\n',
    '        if witness_root is None:\n            raise AcquisitionEntrypointError("receipt capability witness root is required")\n        _probe_receipt_atomic_publication(\n            output,\n            witness_root=witness_root,\n            repository_root=repository_root,\n            snapshot_root=snapshot_root,\n        )\n',
    label='cli output receipt witness binding',
)
new_probe = '''def _probe_receipt_atomic_publication(
    output: _BoundReceiptOutput,
    *,
    witness_root: Path,
    repository_root: Path,
    snapshot_root: Path,
) -> None:
    """Prove receipt publication through a retained external same-device witness."""
    _require_bound_output_parent_identity(output)
    repo = repository_root.resolve(strict=True)
    snapshot = snapshot_root.expanduser().absolute().resolve(strict=False)
    raw = witness_root.expanduser().absolute()
    if raw == repo or _is_descendant(raw, repo):
        raise AcquisitionEntrypointError("receipt witness root must be outside the repository")
    if raw == snapshot or _is_descendant(raw, snapshot):
        raise AcquisitionEntrypointError("receipt witness root must be outside the raw snapshot")
    _require_no_existing_symlink_components(raw, label="receipt witness root")
    try:
        witness_path = raw.resolve(strict=True)
    except OSError:
        raise AcquisitionEntrypointError(
            "receipt witness root must be an existing real directory"
        ) from None
    if (
        witness_path == output.parent_path
        or _is_descendant(witness_path, output.parent_path)
        or _is_descendant(output.parent_path, witness_path)
    ):
        raise AcquisitionEntrypointError(
            "receipt witness root must be separate from the receipt output parent"
        )
    for ancestor in (witness_path, *witness_path.parents):
        if (ancestor / ".git").exists():
            raise AcquisitionEntrypointError("receipt witness root is inside a Git work tree")
    flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
    try:
        witness_descriptor = os.open(witness_path, flags)
    except OSError:
        raise AcquisitionEntrypointError("receipt witness root could not be opened safely") from None
    source_fd: int | None = None
    try:
        witness_opened = os.fstat(witness_descriptor)
        witness_current = witness_path.stat(follow_symlinks=False)
        if (
            not stat.S_ISDIR(witness_opened.st_mode)
            or not stat.S_ISDIR(witness_current.st_mode)
            or _stat_identity(witness_opened) != _stat_identity(witness_current)
        ):
            raise AcquisitionEntrypointError(
                "receipt witness root changed while it was being bound"
            )
        if witness_opened.st_dev != output.device:
            raise AcquisitionEntrypointError(
                "receipt witness root must be on the receipt-output filesystem"
            )
        source_fd = os.open(
            ".",
            os.O_WRONLY | _O_TMPFILE | _O_CLOEXEC,
            0o600,
            dir_fd=witness_descriptor,
        )
        source = os.fstat(source_fd)
        if not stat.S_ISREG(source.st_mode):
            raise AcquisitionEntrypointError(
                "atomic receipt publication witness did not create a regular file"
            )
        witness_name = f".mrl-0801-receipt-witness-{secrets.token_hex(16)}"
        witness_output = _BoundReceiptOutput(
            path=witness_path / witness_name,
            parent_path=witness_path,
            descriptor=witness_descriptor,
            device=witness_opened.st_dev,
            inode=witness_opened.st_ino,
            name=witness_name,
        )
        _publish_open_descriptor_no_replace(source_fd=source_fd, output=witness_output)
        linked = _descriptor_output_stat(witness_output)
        if (
            linked is None
            or not stat.S_ISREG(linked.st_mode)
            or _stat_identity(linked) != _stat_identity(source)
        ):
            raise AcquisitionEntrypointError(
                "atomic receipt publication witness produced an invalid identity"
            )
        witness_after = witness_path.stat(follow_symlinks=False)
        if _stat_identity(witness_after) != _stat_identity(witness_opened):
            raise AcquisitionEntrypointError(
                "receipt witness root changed during publication proof"
            )
        _require_bound_output_parent_identity(output)
    except AcquisitionEntrypointError:
        raise
    except OSError:
        raise AcquisitionEntrypointError(
            "atomic receipt publication capability witness failed safely"
        ) from None
    finally:
        if source_fd is not None:
            os.close(source_fd)
        os.close(witness_descriptor)
'''
cli = replace_regex_once(
    cli,
    r'def _probe_receipt_atomic_publication\(.*?\n\ndef _write_exact_new',
    new_probe + '\n\ndef _write_exact_new',
    label='cli external receipt witness implementation',
)
cli = replace_once(
    cli,
    '            snapshot_root=args.destination,\n        )',
    '            snapshot_root=args.destination,\n            witness_root=args.receipt_witness_root,\n        )',
    label='cli custody receipt witness arg',
)
cli = replace_once(
    cli,
    '            snapshot_root=args.destination,\n        )',
    '            snapshot_root=args.destination,\n            witness_root=args.receipt_witness_root,\n        )',
    label='cli provenance receipt witness arg',
)
cli = replace_once(
    cli,
    '            destination=args.destination,\n            model_id=args.model_id,',
    '            destination=args.destination,\n            model_id=args.model_id,\n            witness_root=args.model_witness_root,',
    label='cli core model witness arg',
)
cli_path.write_text(cli, encoding='utf-8')

acq = acq_test_path.read_text(encoding='utf-8')
acq = replace_once(
    acq,
    'def patch_environment(monkeypatch: pytest.MonkeyPatch) -> None:\n',
    'def witness_root(base: Path) -> Path:\n    value = base / "witness-root"\n    value.mkdir(parents=True, exist_ok=True)\n    return value\n\n\ndef patch_environment(monkeypatch: pytest.MonkeyPatch) -> None:\n',
    label='acquisition test witness helper',
)
acq = acq.replace(
    '            destination=destination,\n',
    '            destination=destination,\n            witness_root=witness_root(destination.parent),\n',
)
acq = acq.replace(
    '        destination=destination,\n',
    '        destination=destination,\n        witness_root=witness_root(destination.parent),\n',
)
acq = replace_once(
    acq,
    '                destination=tmp_path / hashlib.sha256(revision.encode()).hexdigest(),\n                model_id=model_id,',
    '                destination=tmp_path / hashlib.sha256(revision.encode()).hexdigest(),\n                witness_root=tmp_path / "unused-witness",\n                model_id=model_id,',
    label='acquisition unauthorized direct destination witness',
)
acq = replace_once(
    acq,
    '            destination=tmp_path / "assets",\n            model_id=MODEL,',
    '            destination=tmp_path / "assets",\n            witness_root=tmp_path / "unused-witness",\n            model_id=MODEL,',
    label='acquisition spoof direct destination witness',
)
acq = replace_once(
    acq,
    '        assert list(destination.iterdir()) == []\n',
    '        assert {item.name for item in destination.iterdir()} == {FILES[0]}\n',
    label='acquisition retained residue after drift/corruption',
)
acq = replace_once(
    acq,
    '    assert list(original.iterdir()) == []\n',
    '    assert {item.name for item in original.iterdir()} == set(FILES)\n',
    label='acquisition destination replacement retained residue',
)
acq = replace_once(
    acq,
    '    def race(*, root_fd: int) -> None:\n        descriptor = os.open(\n            "foreign.txt",\n            os.O_WRONLY | os.O_CREAT | os.O_EXCL,\n            0o600,\n            dir_fd=root_fd,\n        )\n        os.close(descriptor)\n',
    '    def race(*, root_fd: int) -> None:\n        del root_fd\n        (destination / "foreign.txt").write_text("foreign", encoding="utf-8")\n',
    label='acquisition destination race after witness proof',
)
acq_test_path.write_text(acq, encoding='utf-8')

witness = witness_test_path.read_text(encoding='utf-8')
witness = witness.replace('test_model_capability_witness_is_retained_and_blocks', 'test_model_capability_witness_is_retained_and_allows_continuation')
witness = witness.replace('        with pytest.raises(subject.MRL0801HfAcquisitionError, match="witness retained"):\n            subject._probe_atomic_descriptor_publication(root_fd=root_fd)\n', '        subject._probe_atomic_descriptor_publication(root_fd=root_fd)\n')
witness = witness.replace('test_successful_model_capability_proof_blocks_before_remote_metadata', 'test_successful_model_capability_proof_reaches_remote_metadata')
witness = replace_regex_once(
    witness,
    r'def test_successful_model_capability_proof_reaches_remote_metadata\(.*?\n\n\ndef test_receipt_capability_witness_is_retained_and_blocks',
    '''def test_successful_model_capability_proof_reaches_remote_metadata(\n    tmp_path: Path, monkeypatch: pytest.MonkeyPatch\n) -> None:\n    destination = tmp_path / "assets"\n    destination.mkdir()\n    witness_root = tmp_path / "model-witness"\n    witness_root.mkdir()\n    repository = tmp_path / "repo"\n    repository.mkdir()\n    (repository / ".git").mkdir()\n    transport = NeverTransport()\n    authorization = parse_mrl_0801_acquisition_authorization(AUTH.read_bytes())\n    monkeypatch.setattr(subject, "_capture_repository_execution_identity", lambda _: IDENTITY)\n\n    with pytest.raises(AssertionError, match="unexpected remote metadata access"):\n        subject.acquire_mrl_0801_hf_candidate(\n            authorization=authorization,\n            transport=transport,\n            repository_root=repository,\n            destination=destination,\n            model_id=MODEL,\n            revision=REVISION,\n            witness_root=witness_root,\n        )\n\n    assert transport.metadata_calls == 1\n    assert transport.download_calls == 0\n    assert list(destination.iterdir()) == []\n    witnesses = tuple(witness_root.glob(".mrl-0801-publication-witness-*"))\n    assert len(witnesses) == 1\n    assert witnesses[0].read_bytes() == b""\n\n\ndef test_receipt_capability_witness_is_retained_and_blocks''',
    label='witness full model operational test',
)
witness = witness.replace('test_receipt_capability_witness_is_retained_and_blocks', 'test_receipt_capability_witness_is_retained_and_allows_continuation')
witness = replace_regex_once(
    witness,
    r'def test_receipt_capability_witness_is_retained_and_allows_continuation\(.*?\n\n\ndef test_receipt_capability_witness_foreign_replacement_is_never_deleted',
    '''def test_receipt_capability_witness_is_retained_and_allows_continuation(tmp_path: Path) -> None:\n    cli = load_cli()\n    receipt_parent = tmp_path / "receipts"\n    receipt_parent.mkdir()\n    witness_root = tmp_path / "receipt-witness"\n    witness_root.mkdir()\n    repository = tmp_path / "repo"\n    repository.mkdir()\n    snapshot = tmp_path / "snapshot"\n    snapshot.mkdir()\n    descriptor = _open_directory(receipt_parent)\n    opened = os.fstat(descriptor)\n    output = cli._BoundReceiptOutput(\n        path=receipt_parent / "receipt.json",\n        parent_path=receipt_parent,\n        descriptor=descriptor,\n        device=opened.st_dev,\n        inode=opened.st_ino,\n        name="receipt.json",\n    )\n    try:\n        cli._probe_receipt_atomic_publication(\n            output,\n            witness_root=witness_root,\n            repository_root=repository,\n            snapshot_root=snapshot,\n        )\n    finally:\n        os.close(descriptor)\n\n    witnesses = tuple(witness_root.glob(".mrl-0801-receipt-witness-*"))\n    assert len(witnesses) == 1\n    assert witnesses[0].is_file()\n    assert witnesses[0].read_bytes() == b""\n    assert list(receipt_parent.iterdir()) == []\n\n\ndef test_receipt_capability_witness_foreign_replacement_is_never_deleted''',
    label='witness receipt continuation test',
)
witness = replace_regex_once(
    witness,
    r'def test_receipt_capability_witness_foreign_replacement_is_never_deleted\(.*?\n\n\ndef test_receipt_binding_blocks_after_witness_without_creating_receipt',
    '''def test_receipt_capability_witness_foreign_replacement_is_never_deleted(\n    tmp_path: Path, monkeypatch: pytest.MonkeyPatch\n) -> None:\n    cli = load_cli()\n    receipt_parent = tmp_path / "receipts"\n    receipt_parent.mkdir()\n    witness_root = tmp_path / "receipt-witness"\n    witness_root.mkdir()\n    repository = tmp_path / "repo"\n    repository.mkdir()\n    snapshot = tmp_path / "snapshot"\n    snapshot.mkdir()\n    original_stat = cli._descriptor_output_stat\n    raced: dict[str, str] = {}\n\n    def replace_after_identity_check(output: Any) -> os.stat_result | None:\n        observed = cast(os.stat_result | None, original_stat(output))\n        name = output.name\n        descriptor = output.descriptor\n        if observed is not None and name.startswith(".mrl-0801-receipt-witness-") and not raced:\n            owned_name = f"{name}.owned"\n            os.rename(name, owned_name, src_dir_fd=descriptor, dst_dir_fd=descriptor)\n            foreign_fd = os.open(\n                name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=descriptor\n            )\n            try:\n                os.write(foreign_fd, b"foreign")\n            finally:\n                os.close(foreign_fd)\n            raced["name"] = name\n            raced["owned_name"] = owned_name\n        return observed\n\n    monkeypatch.setattr(cli, "_descriptor_output_stat", replace_after_identity_check)\n    descriptor = _open_directory(receipt_parent)\n    opened = os.fstat(descriptor)\n    output = cli._BoundReceiptOutput(\n        path=receipt_parent / "receipt.json",\n        parent_path=receipt_parent,\n        descriptor=descriptor,\n        device=opened.st_dev,\n        inode=opened.st_ino,\n        name="receipt.json",\n    )\n    try:\n        cli._probe_receipt_atomic_publication(\n            output,\n            witness_root=witness_root,\n            repository_root=repository,\n            snapshot_root=snapshot,\n        )\n    finally:\n        os.close(descriptor)\n\n    assert raced\n    assert (witness_root / raced["name"]).read_bytes() == b"foreign"\n    assert (witness_root / raced["owned_name"]).read_bytes() == b""\n    assert not (receipt_parent / "receipt.json").exists()\n\n\ndef test_receipt_binding_blocks_after_witness_without_creating_receipt''',
    label='witness receipt foreign replacement test',
)
witness = replace_regex_once(
    witness,
    r'def test_receipt_binding_blocks_after_witness_without_creating_receipt\(.*\Z',
    '''def test_receipt_binding_after_witness_keeps_receipt_parent_clean(tmp_path: Path) -> None:\n    cli = load_cli()\n    repository = tmp_path / "repo"\n    repository.mkdir()\n    snapshot = tmp_path / "snapshot"\n    snapshot.mkdir()\n    receipt_parent = tmp_path / "receipts"\n    receipt_parent.mkdir()\n    witness_root = tmp_path / "receipt-witness"\n    witness_root.mkdir()\n    receipt = receipt_parent / "receipt.json"\n\n    output = cli._require_external_new_output(\n        path=receipt,\n        repository_root=repository,\n        snapshot_root=snapshot,\n        witness_root=witness_root,\n    )\n    try:\n        assert not receipt.exists()\n        assert list(receipt_parent.iterdir()) == []\n        witnesses = tuple(witness_root.glob(".mrl-0801-receipt-witness-*"))\n        assert len(witnesses) == 1\n        assert witnesses[0].read_bytes() == b""\n    finally:\n        os.close(output.descriptor)\n''',
    label='witness receipt binding clean parent test',
)
witness_test_path.write_text(witness, encoding='utf-8')

cli_test = cli_test_path.read_text(encoding='utf-8')
cli_test = replace_once(
    cli_test,
    'def clear_medscale_modules(monkeypatch: pytest.MonkeyPatch) -> None:\n',
    'def witness_root(base: Path) -> Path:\n    value = base / "receipt-witness"\n    value.mkdir(parents=True, exist_ok=True)\n    return value\n\n\ndef clear_medscale_modules(monkeypatch: pytest.MonkeyPatch) -> None:\n',
    label='cli test witness helper',
)
cli_test = cli_test.replace(
    '            snapshot_root=snapshot,\n        )',
    '            snapshot_root=snapshot,\n            witness_root=witness_root(tmp_path),\n        )',
)
cli_test = cli_test.replace(
    '        snapshot_root=snapshot,\n    )',
    '        snapshot_root=snapshot,\n        witness_root=witness_root(tmp_path),\n    )',
)
cli_test = cli_test.replace('    def race(output: Any) -> None:\n', '    def race(output: Any, **_: object) -> None:\n')
cli_test_path.write_text(cli_test, encoding='utf-8')

spec = spec_path.read_text(encoding='utf-8')
spec = replace_once(
    spec,
    'Before any remote metadata request or model byte download, the executor must first prove that unnamed-file atomic publication actually works on the bound destination filesystem. The CLI performs the same proof for each bound receipt-parent filesystem before acquisition begins. A successful `O_TMPFILE` open or an exported `linkat` symbol alone is insufficient. The capability check publishes an unnamed file with `linkat(..., AT_EMPTY_PATH)` directly into the already-bound transaction directory and verifies the linked identity. Because V1 has no kernel primitive that atomically binds a prior inode observation to namespace removal, the zero-byte hidden capability witness is intentionally retained and the operation then fails closed before remote metadata access or acquisition.\n\n**Current V1 stops at that retained-witness boundary.** The following two-pass metadata sequence documents the already-implemented future operational path only. It is unreachable in V1 after a successful capability proof and requires a separate canonical design/authority change before activation:',
    'Before any remote metadata request or model byte download, the executor must first prove that unnamed-file atomic publication actually works on the transaction filesystem. The caller must provide an explicit pre-existing external capability-witness root on the same filesystem device as the model destination. The CLI likewise requires an explicit pre-existing external witness root on the same filesystem device as each receipt-output parent. A successful `O_TMPFILE` open or an exported `linkat` symbol alone is insufficient. The capability check publishes an unnamed zero-byte file with `linkat(..., AT_EMPTY_PATH)` into the separately bound witness root, verifies the linked inode identity, retains the witness as audit evidence, and leaves the model destination / receipt-output parent unchanged. After that proof succeeds, the authorized operational metadata path may begin.\n\nThe operational two-pass metadata sequence is:',
    label='spec operational two-pass metadata',
)
spec = spec.replace('In that future operational path, metadata would be retrieved again immediately before each file download.', 'Metadata is retrieved again immediately before each file download.')
spec = spec.replace('This dormant rule is retained so any future activation cannot weaken immutable remote identity binding or signed-location handling.', 'This rule prevents immutable remote identity binding or signed-location handling from weakening between preflight and byte acquisition.')
spec = replace_once(
    spec,
    'The executor never overwrites existing asset files. Before any remote metadata request, it creates an unnamed `O_TMPFILE` through the already-bound destination descriptor, publishes a random hidden zero-byte witness with `linkat(..., AT_EMPTY_PATH)`, verifies the linked inode identity, retains the witness, and returns `BLOCKED` before network access because safe atomic witness cleanup is unavailable in V1. This proves the required publication primitive without performing a racy namespace deletion. The model-byte streaming path remains implemented for a future separately qualified execution boundary, but V1 does not reach it after successful capability proof.',
    'The executor never overwrites existing asset files. Before any remote metadata request, it binds the caller-provided external witness root, requires that root to be a separate real no-follow directory outside Git and on the exact destination filesystem device, publishes a random hidden zero-byte witness there with `O_TMPFILE` plus `linkat(..., AT_EMPTY_PATH)`, verifies the linked inode identity, and retains the witness permanently. The model destination remains empty after proof. Successful proof permits the authorized metadata and model-byte path to continue.',
    label='spec operational destination witness',
)
spec = replace_once(
    spec,
    'Receipt publication by the CLI follows the same fail-closed V1 rule. The already-bound receipt-parent descriptor publishes and verifies its own hidden zero-byte witness, retains it, and returns `BLOCKED`; no receipt bytes, model bytes, or remote metadata are reached through current V1 after a successful proof. No capability-witness cleanup is automatic because a later name deletion cannot be proven to remove the previously verified inode atomically.',
    'Receipt publication by the CLI follows the same accepted ADR-0037 rule. Each receipt-output parent is bound once, while capability proof is performed in the explicit external same-device receipt witness root. The hidden zero-byte witness is retained there; the receipt-output parent remains unchanged by proof. Receipt bytes are later published from unnamed files with atomic no-replace semantics. No capability witness or published receipt is automatically deleted after publication.',
    label='spec operational receipt witness',
)
spec = spec.replace('The storage-preflight implementation is retained for the future operational path and is not reached by current V1 after successful capability proof. When separately activated,', 'After successful capability proof and metadata preflight,')
spec = spec.replace('The custody handoff implementation is retained but unreachable in current V1 after successful capability proof. In a future separately qualified operational path,', 'After every authorized remote file is verified and atomically present,')
spec = spec.replace('Current V1 cannot emit a successful acquisition-provenance receipt because it blocks before remote metadata or model bytes. The dormant operational path is designed so that a future separately authorized successful execution would emit one deterministic canonical supporting receipt', 'A successful operational execution emits one deterministic canonical supporting receipt')
spec = spec.replace('That future receipt contract records:', 'That receipt contract records:')
spec = spec.replace('If a future operational acquisition-provenance receipt exists,', 'For every operational acquisition-provenance receipt,')
spec = spec.replace('Current V1 uses that bound descriptor only to perform the retained capability-witness proof and then blocks before receipt creation.', 'The receipt-output parent remains unchanged during capability proof because the witness is published into the explicit external same-device receipt witness root.')
spec = spec.replace('The descriptor-bound exclusive receipt publication and receipt-identity verification implementation remains present for a future separately qualified operational boundary. Current V1 never reaches receipt publication after a successful capability proof and therefore creates no receipt output.', 'The descriptor-bound exclusive receipt publication and receipt-identity verification path is operational after capability proof and successful acquisition.')
spec = spec.replace('User-visible V1 failure emits a generic blocked message', 'User-visible failure emits a generic blocked message')
spec = spec.replace('proof that successful capability publication causes zero remote metadata calls and zero model-byte downloads in current V1.', 'proof that successful capability publication leaves the transaction directory unchanged and permits injected metadata access, while failed preconditions still cause zero remote access.')
spec = spec.replace('Current V1 emits no successful acquisition receipt and no real asset evidence.', 'This repository change itself emits no real asset evidence; successful external acquisition remains separately gated by post-merge qualification.')
spec_path.write_text(spec, encoding='utf-8')

for path in (core_path, cli_path, acq_test_path, witness_test_path, cli_test_path, spec_path):
    data = path.read_text(encoding='utf-8')
    if not data.endswith('\n'):
        path.write_text(data + '\n', encoding='utf-8')
