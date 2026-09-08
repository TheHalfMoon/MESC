from __future__ import annotations

import re
from pathlib import Path


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def replace_between(text: str, start: str, end: str, new: str, *, label: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise SystemExit(f"{label}: start marker not found")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise SystemExit(f"{label}: end marker not found")
    return text[:start_index] + new.rstrip() + "\n\n\n" + text[end_index:]


SOURCE = Path("src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py")
SCRIPT = Path("scripts/mesc_mrl_0801_hf_acquire.py")
ACQ_TEST = Path("tests/test_mesc_mrl_0801_hf_acquisition_v1.py")
CLI_TEST = Path("tests/test_mesc_mrl_0801_hf_acquire_cli.py")
WITNESS_TEST = Path("tests/test_mesc_mrl_0801_hf_witness_v1.py")
SPEC = Path("specs/mesc-experiment-0/mrl-0801-hf-acquisition-provenance-v1.md")

source = SOURCE.read_text(encoding="utf-8")
script = SCRIPT.read_text(encoding="utf-8")
acq_test = ACQ_TEST.read_text(encoding="utf-8")
cli_test = CLI_TEST.read_text(encoding="utf-8")
spec = SPEC.read_text(encoding="utf-8")

source = replace_once(
    source,
    '''@dataclass(frozen=True, slots=True)\nclass _DestinationDirectory:\n    """Opened destination directory identity used for descriptor-relative mutation."""\n\n    path: Path\n    descriptor: int\n    device: int\n    inode: int\n\n\nclass _Digest(Protocol):''',
    '''@dataclass(frozen=True, slots=True)\nclass _DestinationDirectory:\n    """Opened destination directory identity used for descriptor-relative mutation."""\n\n    path: Path\n    descriptor: int\n    device: int\n    inode: int\n\n\n@dataclass(frozen=True, slots=True)\nclass _WitnessDirectory:\n    """Opened external capability-witness directory bound for one transaction."""\n\n    path: Path\n    descriptor: int\n    device: int\n    inode: int\n\n\nclass _Digest(Protocol):''',
    label="insert witness directory type",
)

new_acquire = r'''def acquire_mrl_0801_hf_candidate(
    *,
    authorization: MRL0801AcquisitionAuthorization,
    transport: HfPublicTransport,
    repository_root: Path,
    destination: Path,
    witness_root: Path,
    model_id: str,
    revision: str,
    finalizer: Callable[
        [MRL0801AssetCustodyReceipt, MRL0801HfAcquisitionProvenanceReceipt], None
    ]
    | None = None,
) -> tuple[MRL0801AssetCustodyReceipt, MRL0801HfAcquisitionProvenanceReceipt]:
    """Acquire one exact authorized candidate and bind remote provenance to local custody."""
    if type(authorization) is not MRL0801AcquisitionAuthorization:
        raise MRL0801HfAcquisitionError(
            "authorization must be an exact MRL0801AcquisitionAuthorization"
        )
    execution_identity = _capture_repository_execution_identity(repository_root)
    candidate = authorization.require_candidate(model_id=model_id, revision=revision)
    destination_root = _require_external_empty_destination(
        destination=destination,
        repository_root=repository_root,
    )
    witness: _WitnessDirectory | None = None
    acquired: list[HfAcquiredFileIdentity] = []
    pre_finalizer_entries: frozenset[str] | None = None
    try:
        witness = _require_external_witness_root(
            witness_root=witness_root,
            repository_root=repository_root,
            transaction_root=destination_root,
        )
        _probe_atomic_descriptor_publication(
            source_root_fd=destination_root.descriptor,
            witness_root=witness,
        )
        _require_witness_path_identity(witness)
        _require_destination_path_identity(destination_root)
        if _descriptor_entries(root_fd=destination_root.descriptor):
            raise MRL0801HfAcquisitionError(
                "acquisition destination changed during atomic publication preflight"
            )

        metadata = _verify_remote_allowlist_metadata(
            transport=transport,
            model_id=model_id,
            revision=revision,
            allowed_files=candidate.allowed_files,
        )
        exact_allowlist_bytes = sum(item.byte_count for item in metadata)
        available_bytes = _available_bytes(destination_root)
        storage_required_bytes = require_mrl_0801_storage_capacity(
            exact_allowlist_bytes=exact_allowlist_bytes,
            available_bytes=available_bytes,
        )

        for preflight_item in metadata:
            fresh_item = transport.metadata(
                model_id=model_id,
                revision=revision,
                path=preflight_item.path,
            )
            _require_same_remote_identity(preflight=preflight_item, fresh=fresh_item)
            acquired.append(
                _acquire_one_file(
                    root_fd=destination_root.descriptor,
                    transport=transport,
                    metadata=fresh_item,
                )
            )

        _require_destination_path_identity(destination_root)
        custody = generate_mrl_0801_asset_custody_receipt(
            model_root=destination_root.path,
            authorization=authorization,
            model_id=model_id,
            revision=revision,
        )
        _require_destination_path_identity(destination_root)
        payload: dict[str, object] = {
            "access_authorization_sha256": authorization.authorization_sha256,
            "artifact_identity_sha256": custody.artifact_identity_sha256,
            "asset_custody_sha256": custody.asset_custody_sha256,
            "candidate_roster_sha256": _candidate_roster_sha256(custody),
            "credentials_used": False,
            "executor_code_commit": execution_identity.commit_sha,
            "executor_code_tree": execution_identity.tree_sha,
            "executor_source_sha256": execution_identity.source_sha256,
            "files": [item.to_dict() for item in acquired],
            "gpu_execution_performed": False,
            "inference_performed": False,
            "model_id": model_id,
            "model_loading_performed": False,
            "mrl_0801_population_performed": False,
            "network_accessed": True,
            "public_unauthenticated": True,
            "remote_code_allowed": False,
            "revision": revision,
            "schema_version": _SCHEMA_VERSION,
            "source": _SOURCE,
            "storage_available_bytes_at_preflight": available_bytes,
            "storage_required_bytes": storage_required_bytes,
            "terms_accepted": False,
            "tokenizer_loading_performed": False,
            "total_byte_count": exact_allowlist_bytes,
            "training_performed": False,
            "trust_registry_mutation_performed": False,
            "weight_mutation_performed": False,
            "weights_sha256": custody.weights_sha256,
        }
        receipt = MRL0801HfAcquisitionProvenanceReceipt(canonical_json_bytes(payload))
        _require_receipt_matches_custody(
            receipt=receipt,
            custody=custody,
            authorization=authorization,
            expected_files=candidate.allowed_files,
        )
        _require_destination_path_identity(destination_root)
        if finalizer is not None:
            pre_finalizer_entries = _descriptor_entries(root_fd=destination_root.descriptor)
            if pre_finalizer_entries != frozenset(candidate.allowed_files):
                raise MRL0801HfAcquisitionError(
                    "acquisition destination manifest differs from the authorized allowlist"
                )
            finalizer(custody, receipt)
            _require_destination_path_identity(destination_root)
            if _descriptor_entries(root_fd=destination_root.descriptor) != pre_finalizer_entries:
                raise MRL0801HfAcquisitionError(
                    "acquisition destination manifest changed during finalization"
                )
            post_finalizer_custody = generate_mrl_0801_asset_custody_receipt(
                model_root=destination_root.path,
                authorization=authorization,
                model_id=model_id,
                revision=revision,
            )
            _require_destination_path_identity(destination_root)
            if post_finalizer_custody.canonical_bytes != custody.canonical_bytes:
                raise MRL0801HfAcquisitionError(
                    "acquisition destination custody changed during finalization"
                )
            _require_receipt_matches_custody(
                receipt=receipt,
                custody=post_finalizer_custody,
                authorization=authorization,
                expected_files=candidate.allowed_files,
            )
            custody = post_finalizer_custody
        _require_destination_path_identity(destination_root)
        _require_witness_path_identity(witness)
        return custody, receipt
    except BaseException:
        _rollback_created_files(
            root_fd=destination_root.descriptor,
            acquired=tuple(acquired),
            pre_finalizer_entries=pre_finalizer_entries,
        )
        raise
    finally:
        if witness is not None:
            os.close(witness.descriptor)
        os.close(destination_root.descriptor)'''
source = replace_between(
    source,
    "def acquire_mrl_0801_hf_candidate(\n",
    "def validate_mrl_0801_hf_acquisition_provenance(\n",
    new_acquire,
    label="replace operational acquire function",
)

new_destination = r'''def _require_external_empty_destination(
    *, destination: Path, repository_root: Path
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
        return _DestinationDirectory(
            path=root,
            descriptor=descriptor,
            device=opened.st_dev,
            inode=opened.st_ino,
        )
    except BaseException:
        os.close(descriptor)
        raise


def _require_external_witness_root(
    *,
    witness_root: Path,
    repository_root: Path,
    transaction_root: _DestinationDirectory,
) -> _WitnessDirectory:
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
    if (
        root == transaction_root.path
        or _is_descendant(root, transaction_root.path)
        or _is_descendant(transaction_root.path, root)
    ):
        raise MRL0801HfAcquisitionError(
            "capability witness root must be a dedicated directory outside the transaction root"
        )
    for ancestor in (root, *root.parents):
        if (ancestor / ".git").exists():
            raise MRL0801HfAcquisitionError("capability witness root is inside a Git work tree")
    flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
    try:
        descriptor = os.open(root, flags)
    except OSError:
        raise MRL0801HfAcquisitionError(
            "capability witness root must be an existing non-symlink directory"
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
                "capability witness root changed while it was being opened"
            )
        if opened.st_dev != transaction_root.device:
            raise MRL0801HfAcquisitionError(
                "capability witness root must be on the transaction filesystem"
            )
        return _WitnessDirectory(
            path=root,
            descriptor=descriptor,
            device=opened.st_dev,
            inode=opened.st_ino,
        )
    except BaseException:
        os.close(descriptor)
        raise


def _require_witness_path_identity(witness: _WitnessDirectory) -> None:
    try:
        opened = os.fstat(witness.descriptor)
        current = witness.path.stat(follow_symlinks=False)
    except OSError:
        raise MRL0801HfAcquisitionError(
            "capability witness root changed during the transaction"
        ) from None
    expected = (witness.device, witness.inode)
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(current.st_mode)
        or _stat_descriptor_identity(opened) != expected
        or _stat_descriptor_identity(current) != expected
    ):
        raise MRL0801HfAcquisitionError(
            "capability witness root changed during the transaction"
        )'''
source = replace_between(
    source,
    "def _require_external_empty_destination(\n",
    "def _require_no_existing_symlink_components(\n",
    new_destination,
    label="replace destination and witness binding",
)

new_probe = r'''def _probe_atomic_descriptor_publication(
    *,
    source_root_fd: int,
    witness_root: _WitnessDirectory,
) -> str:
    """Prove same-filesystem atomic publication into a retained external witness root."""
    _require_witness_path_identity(witness_root)
    source_fd: int | None = None
    try:
        source_fd = _open_unnamed_temp_file(root_fd=source_root_fd)
        source = os.fstat(source_fd)
        if not stat.S_ISREG(source.st_mode):
            raise MRL0801HfAcquisitionError(
                "atomic publication witness did not create a regular file"
            )
        if source.st_dev != witness_root.device:
            raise MRL0801HfAcquisitionError(
                "capability witness root must be on the transaction filesystem"
            )
        witness_name = f".mrl-0801-publication-witness-{secrets.token_hex(16)}"
        _publish_open_descriptor_no_replace(
            source_fd=source_fd,
            root_fd=witness_root.descriptor,
            target_name=witness_name,
        )
        linked = _descriptor_entry_stat(root_fd=witness_root.descriptor, name=witness_name)
        if (
            linked is None
            or not stat.S_ISREG(linked.st_mode)
            or _stat_descriptor_identity(linked) != _stat_descriptor_identity(source)
        ):
            raise MRL0801HfAcquisitionError(
                "atomic publication witness produced an invalid identity"
            )
        _require_witness_path_identity(witness_root)
        return witness_name
    except MRL0801HfAcquisitionError:
        raise
    except OSError:
        raise MRL0801HfAcquisitionError(
            "atomic descriptor publication capability witness failed safely"
        ) from None
    finally:
        if source_fd is not None:
            os.close(source_fd)'''
source = replace_between(
    source,
    "def _probe_atomic_descriptor_publication(\n",
    "def _acquire_one_file(\n",
    new_probe,
    label="replace model publication probe",
)

script = replace_once(
    script,
    '    parser.add_argument("--destination", type=Path, required=True)\n',
    '    parser.add_argument("--destination", type=Path, required=True)\n'
    '    parser.add_argument("--model-witness-root", type=Path, required=True)\n'
    '    parser.add_argument("--receipt-witness-root", type=Path, required=True)\n',
    label="add witness CLI arguments",
)

script = replace_once(
    script,
    '''class _BoundReceiptOutput:\n    """Descriptor-bound receipt output with transaction-created file identity."""''',
    '''class _BoundWitnessRoot:\n    """Descriptor-bound external capability-witness root."""\n\n    __slots__ = ("descriptor", "device", "inode", "path")\n\n    descriptor: int\n    device: int\n    inode: int\n    path: Path\n\n    def __init__(self, *, path: Path, descriptor: int, device: int, inode: int) -> None:\n        self.path = path\n        self.descriptor = descriptor\n        self.device = device\n        self.inode = inode\n\n\nclass _BoundReceiptOutput:\n    """Descriptor-bound receipt output with transaction-created file identity."""''',
    label="insert CLI witness type",
)

new_output_binding = r'''def _require_external_new_output(
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
        return output
    except BaseException:
        os.close(descriptor)
        raise


def _require_external_witness_root(
    *,
    path: Path,
    repository_root: Path,
    snapshot_root: Path,
) -> _BoundWitnessRoot:
    repo = repository_root.resolve(strict=True)
    snapshot = snapshot_root.expanduser().absolute().resolve(strict=False)
    raw = path.expanduser().absolute()
    if raw == repo or _is_descendant(raw, repo):
        raise AcquisitionEntrypointError("receipt witness root must be outside the repository")
    if raw == snapshot or _is_descendant(raw, snapshot):
        raise AcquisitionEntrypointError("receipt witness root must be outside the raw snapshot root")
    _require_no_existing_symlink_components(raw, label="receipt witness root")
    try:
        root = raw.resolve(strict=True)
    except OSError:
        raise AcquisitionEntrypointError(
            "receipt witness root must already exist as a real directory"
        ) from None
    if root == repo or _is_descendant(root, repo):
        raise AcquisitionEntrypointError("receipt witness root must be outside the repository")
    if root == snapshot or _is_descendant(root, snapshot):
        raise AcquisitionEntrypointError("receipt witness root must be outside the raw snapshot root")
    flags = os.O_RDONLY | _O_DIRECTORY | _O_NOFOLLOW | _O_CLOEXEC
    try:
        descriptor = os.open(root, flags)
    except OSError:
        raise AcquisitionEntrypointError("receipt witness root could not be opened safely") from None
    try:
        opened = os.fstat(descriptor)
        current = root.stat(follow_symlinks=False)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or not stat.S_ISDIR(current.st_mode)
            or _stat_identity(opened) != _stat_identity(current)
        ):
            raise AcquisitionEntrypointError(
                "receipt witness root changed while it was being bound"
            )
        return _BoundWitnessRoot(
            path=root,
            descriptor=descriptor,
            device=opened.st_dev,
            inode=opened.st_ino,
        )
    except BaseException:
        os.close(descriptor)
        raise


def _require_bound_witness_root_identity(witness: _BoundWitnessRoot) -> None:
    try:
        opened = os.fstat(witness.descriptor)
        current = witness.path.stat(follow_symlinks=False)
    except OSError:
        raise AcquisitionEntrypointError("receipt witness root changed during acquisition") from None
    expected = (witness.device, witness.inode)
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(current.st_mode)
        or _stat_identity(opened) != expected
        or _stat_identity(current) != expected
    ):
        raise AcquisitionEntrypointError("receipt witness root changed during acquisition")'''
script = replace_between(
    script,
    "def _require_external_new_output(\n",
    "def _load_posix_symbol(\n",
    new_output_binding,
    label="replace receipt output and witness binding",
)

new_receipt_probe = r'''def _probe_receipt_atomic_publication(
    output: _BoundReceiptOutput,
    witness_root: _BoundWitnessRoot,
) -> str:
    """Prove receipt-parent publication through a retained same-filesystem witness."""
    _require_bound_output_parent_identity(output)
    _require_bound_witness_root_identity(witness_root)
    if (
        witness_root.path == output.parent_path
        or _is_descendant(witness_root.path, output.parent_path)
        or _is_descendant(output.parent_path, witness_root.path)
    ):
        raise AcquisitionEntrypointError(
            "receipt witness root must be a dedicated directory outside receipt outputs"
        )
    source_fd: int | None = None
    try:
        try:
            source_fd = os.open(
                ".",
                os.O_WRONLY | _O_TMPFILE | _O_CLOEXEC,
                0o600,
                dir_fd=output.descriptor,
            )
        except OSError:
            raise AcquisitionEntrypointError(
                "unnamed receipt publication is unsupported on this filesystem"
            ) from None
        source = os.fstat(source_fd)
        if not stat.S_ISREG(source.st_mode):
            raise AcquisitionEntrypointError(
                "atomic receipt publication witness did not create a regular file"
            )
        if source.st_dev != witness_root.device:
            raise AcquisitionEntrypointError(
                "receipt witness root must be on the receipt-output filesystem"
            )
        witness_name = f".mrl-0801-receipt-witness-{secrets.token_hex(16)}"
        witness_output = _BoundReceiptOutput(
            path=witness_root.path / witness_name,
            parent_path=witness_root.path,
            descriptor=witness_root.descriptor,
            device=witness_root.device,
            inode=witness_root.inode,
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
        _require_bound_output_parent_identity(output)
        _require_bound_witness_root_identity(witness_root)
        if _descriptor_output_stat(output) is not None:
            raise AcquisitionEntrypointError(
                "receipt output appeared during atomic publication preflight"
            )
        return witness_name
    except AcquisitionEntrypointError:
        raise
    except OSError:
        raise AcquisitionEntrypointError(
            "atomic receipt publication capability witness failed safely"
        ) from None
    finally:
        if source_fd is not None:
            os.close(source_fd)'''
script = replace_between(
    script,
    "def _probe_receipt_atomic_publication(\n",
    "def _write_exact_new(\n",
    new_receipt_probe,
    label="replace receipt publication probe",
)

new_main = r'''def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    custody_output: _BoundReceiptOutput | None = None
    provenance_output: _BoundReceiptOutput | None = None
    receipt_witness: _BoundWitnessRoot | None = None
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

        receipt_witness = _require_external_witness_root(
            path=args.receipt_witness_root,
            repository_root=repository_root,
            snapshot_root=args.destination,
        )
        _probe_receipt_atomic_publication(custody_output_path, receipt_witness)
        _probe_receipt_atomic_publication(provenance_output_path, receipt_witness)
        _require_bound_output_parent_identity(custody_output_path)
        _require_bound_output_parent_identity(provenance_output_path)
        _require_bound_witness_root_identity(receipt_witness)

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
            witness_root=args.model_witness_root,
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
        if receipt_witness is not None:
            with contextlib.suppress(OSError):
                os.close(receipt_witness.descriptor)
        for output in (custody_output, provenance_output):
            if output is not None:
                with contextlib.suppress(OSError):
                    os.close(output.descriptor)'''
script = replace_between(
    script,
    "def main(argv: list[str] | None = None) -> int:\n",
    'if __name__ == "__main__":\n',
    new_main,
    label="replace CLI main",
)

acq_test = replace_once(
    acq_test,
    '''def patch_environment(monkeypatch: pytest.MonkeyPatch) -> None:\n    monkeypatch.setattr(subject, "_capture_repository_execution_identity", lambda _: IDENTITY)''',
    '''def witness_root_for(destination: Path) -> Path:\n    root = destination.parent / f"{destination.name}-witnesses"\n    root.mkdir(parents=True, exist_ok=True)\n    return root\n\n\ndef patch_environment(monkeypatch: pytest.MonkeyPatch) -> None:\n    monkeypatch.setattr(subject, "_capture_repository_execution_identity", lambda _: IDENTITY)''',
    label="add acquisition-test witness helper",
)

pattern = re.compile(r'(?m)^(?P<indent>\s*)destination=(?P<expr>[^\n,]+),\n(?P=indent)model_id=')
def inject_witness(match: re.Match[str]) -> str:
    indent = match.group("indent")
    expr = match.group("expr")
    return (
        f"{indent}destination={expr},\n"
        f"{indent}witness_root=witness_root_for({expr}),\n"
        f"{indent}model_id="
    )
acq_test, inject_count = pattern.subn(inject_witness, acq_test)
if inject_count < 10:
    raise SystemExit(f"acquisition-test witness injection count too small: {inject_count}")

acq_test = replace_once(
    acq_test,
    'def test_metadata_drift_and_corrupt_bytes_roll_back(\n',
    'def test_metadata_drift_and_corrupt_bytes_retain_published_residue(\n',
    label="rename retained residue test",
)
acq_test = replace_once(
    acq_test,
    '        assert list(destination.iterdir()) == []\n\n\ndef test_storage_failure_occurs_before_model_bytes',
    '        assert {item.name for item in destination.iterdir()} == {FILES[0]}\n\n\ndef test_storage_failure_occurs_before_model_bytes',
    label="assert retained published residue",
)
acq_test = replace_once(
    acq_test,
    '    def race(*, root_fd: int) -> None:\n        descriptor = os.open(\n            "foreign.txt",\n            os.O_WRONLY | os.O_CREAT | os.O_EXCL,\n            0o600,\n            dir_fd=root_fd,\n        )',
    '    def race(*, source_root_fd: int, witness_root: object) -> str:\n        del witness_root\n        descriptor = os.open(\n            "foreign.txt",\n            os.O_WRONLY | os.O_CREAT | os.O_EXCL,\n            0o600,\n            dir_fd=source_root_fd,\n        )',
    label="adapt destination-race probe signature",
)
acq_test = replace_once(
    acq_test,
    '        os.close(descriptor)\n\n    monkeypatch.setattr(subject, "_probe_atomic_descriptor_publication", race)',
    '        os.close(descriptor)\n        return "synthetic-witness"\n\n    monkeypatch.setattr(subject, "_probe_atomic_descriptor_publication", race)',
    label="return synthetic witness",
)

# The two CLI tests that assumed binding itself performed the old blocking probe are replaced.
cli_test = replace_between(
    cli_test,
    "def test_receipt_atomic_publication_capability_is_verified_before_binding(\n",
    "def test_receipt_output_is_published_descriptor_relative(\n",
    r'''def test_receipt_atomic_publication_capability_is_verified_before_use(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    receipt = tmp_path / "receipts/receipt.json"
    receipt.parent.mkdir()
    witness_dir = tmp_path / "receipt-witnesses"
    witness_dir.mkdir()
    output = cli._require_external_new_output(
        path=receipt,
        repository_root=root,
        snapshot_root=snapshot,
    )
    witness = cli._require_external_witness_root(
        path=witness_dir,
        repository_root=root,
        snapshot_root=snapshot,
    )

    def unsupported_publication(**_: object) -> None:
        raise cli.AcquisitionEntrypointError(
            "atomic receipt publication is unsupported on this filesystem"
        )

    monkeypatch.setattr(cli, "_publish_open_descriptor_no_replace", unsupported_publication)
    try:
        with pytest.raises(cli.AcquisitionEntrypointError, match="atomic receipt publication"):
            cli._probe_receipt_atomic_publication(output, witness)
        assert not receipt.exists()
        assert list(witness_dir.iterdir()) == []
    finally:
        os.close(witness.descriptor)
        os.close(output.descriptor)


def test_receipt_target_race_after_capability_probe_is_rejected(
    tmp_path: Path,
) -> None:
    cli = load_cli()
    root = repo(tmp_path)
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    receipt = tmp_path / "receipts/receipt.json"
    receipt.parent.mkdir()
    witness_dir = tmp_path / "receipt-witnesses"
    witness_dir.mkdir()
    output = cli._require_external_new_output(
        path=receipt,
        repository_root=root,
        snapshot_root=snapshot,
    )
    witness = cli._require_external_witness_root(
        path=witness_dir,
        repository_root=root,
        snapshot_root=snapshot,
    )
    try:
        cli._probe_receipt_atomic_publication(output, witness)
        receipt.write_bytes(b"foreign")
        with pytest.raises(cli.AcquisitionEntrypointError, match="must not already exist"):
            cli._write_exact_new(output, b"ours")
        assert receipt.read_bytes() == b"foreign"
        assert len(tuple(witness_dir.glob(".mrl-0801-receipt-witness-*"))) == 1
    finally:
        os.close(witness.descriptor)
        os.close(output.descriptor)''',
    label="replace obsolete receipt capability tests",
)

WITNESS_TEST.write_text(r'''"""ADR-0037 regressions for external retained publication witnesses."""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from medscale.mesc import _mrl_0801_hf_acquisition_v1 as subject
from medscale.mesc._mrl_0801_acquisition_custody_v1 import parse_mrl_0801_acquisition_authorization

ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/mesc_mrl_0801_hf_acquire.py"
AUTH = ROOT / "specs/mesc-experiment-0/mrl-0801-acquisition-custody-authorization-v1.json"
MODEL = "google/gemma-4-31B-it"
REVISION = "842da3794eaa0b77d5f08bae87a17459d91ff475"
IDENTITY = subject.RepositoryExecutionIdentity("9" * 40, "8" * 40, "7" * 64)
_O_DIRECTORY = os.__dict__.get("O_DIRECTORY", 0)
_O_CLOEXEC = os.__dict__.get("O_CLOEXEC", 0)
_O_TMPFILE = os.__dict__.get("O_TMPFILE", 0)

pytestmark = pytest.mark.skipif(
    sys.platform != "linux" or _O_TMPFILE == 0 or _O_DIRECTORY == 0,
    reason="requires Linux O_TMPFILE and descriptor-relative directory support",
)


def load_cli() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mesc_mrl_0801_hf_witness_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fake_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir(parents=True)
    (root / ".git").mkdir()
    return root


class MarkerTransport:
    def __init__(self) -> None:
        self.metadata_calls = 0
        self.download_calls = 0

    def metadata(
        self,
        *,
        model_id: str,
        revision: str,
        path: str,
    ) -> subject.HfRemoteFileMetadata:
        self.metadata_calls += 1
        raise RuntimeError(f"metadata-reached:{model_id}@{revision}:{path}")

    def iter_bytes(self, *, metadata: subject.HfRemoteFileMetadata) -> Iterator[bytes]:
        self.download_calls += 1
        yield b"unexpected"


def test_model_capability_witness_is_external_retained_and_destination_stays_empty(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "assets"
    destination.mkdir()
    witness_dir = tmp_path / "witnesses"
    witness_dir.mkdir()
    repository = fake_repo(tmp_path)
    destination_root = subject._require_external_empty_destination(
        destination=destination,
        repository_root=repository,
    )
    witness = subject._require_external_witness_root(
        witness_root=witness_dir,
        repository_root=repository,
        transaction_root=destination_root,
    )
    try:
        name = subject._probe_atomic_descriptor_publication(
            source_root_fd=destination_root.descriptor,
            witness_root=witness,
        )
        assert name.startswith(".mrl-0801-publication-witness-")
        assert list(destination.iterdir()) == []
        assert (witness_dir / name).read_bytes() == b""
    finally:
        os.close(witness.descriptor)
        os.close(destination_root.descriptor)


def test_successful_model_capability_proof_permits_metadata_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "assets"
    destination.mkdir()
    witness_dir = tmp_path / "witnesses"
    witness_dir.mkdir()
    repository = fake_repo(tmp_path)
    transport = MarkerTransport()
    authorization = parse_mrl_0801_acquisition_authorization(AUTH.read_bytes())
    monkeypatch.setattr(subject, "_capture_repository_execution_identity", lambda _: IDENTITY)

    with pytest.raises(RuntimeError, match="metadata-reached"):
        subject.acquire_mrl_0801_hf_candidate(
            authorization=authorization,
            transport=transport,
            repository_root=repository,
            destination=destination,
            witness_root=witness_dir,
            model_id=MODEL,
            revision=REVISION,
        )

    assert transport.metadata_calls == 1
    assert transport.download_calls == 0
    assert list(destination.iterdir()) == []
    assert len(tuple(witness_dir.glob(".mrl-0801-publication-witness-*"))) == 1


def test_model_witness_root_device_mismatch_is_rejected_before_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "assets"
    destination.mkdir()
    witness_dir = tmp_path / "witnesses"
    witness_dir.mkdir()
    repository = fake_repo(tmp_path)
    destination_root = subject._require_external_empty_destination(
        destination=destination,
        repository_root=repository,
    )
    real_fstat = os.fstat

    def mismatched(fd: int) -> os.stat_result:
        observed = real_fstat(fd)
        if fd == destination_root.descriptor:
            return observed
        values = list(observed)
        values[2] = observed.st_dev + 1
        return os.stat_result(values)

    monkeypatch.setattr(subject.os, "fstat", mismatched)
    try:
        with pytest.raises(subject.MRL0801HfAcquisitionError, match="transaction filesystem"):
            subject._require_external_witness_root(
                witness_root=witness_dir,
                repository_root=repository,
                transaction_root=destination_root,
            )
    finally:
        os.close(destination_root.descriptor)


def test_model_witness_foreign_replacement_is_never_deleted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path / "assets"
    destination.mkdir()
    witness_dir = tmp_path / "witnesses"
    witness_dir.mkdir()
    repository = fake_repo(tmp_path)
    destination_root = subject._require_external_empty_destination(
        destination=destination,
        repository_root=repository,
    )
    witness = subject._require_external_witness_root(
        witness_root=witness_dir,
        repository_root=repository,
        transaction_root=destination_root,
    )
    original_stat = subject._descriptor_entry_stat
    raced: dict[str, str] = {}

    def replace_after_identity(*, root_fd: int, name: str) -> os.stat_result | None:
        observed = original_stat(root_fd=root_fd, name=name)
        if observed is not None and name.startswith(".mrl-0801-publication-witness-") and not raced:
            owned_name = f"{name}.owned"
            os.rename(name, owned_name, src_dir_fd=root_fd, dst_dir_fd=root_fd)  # noqa: PTH104
            foreign_fd = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o600,
                dir_fd=root_fd,
            )
            try:
                os.write(foreign_fd, b"foreign")
            finally:
                os.close(foreign_fd)
            raced["name"] = name
            raced["owned"] = owned_name
        return observed

    monkeypatch.setattr(subject, "_descriptor_entry_stat", replace_after_identity)
    try:
        subject._probe_atomic_descriptor_publication(
            source_root_fd=destination_root.descriptor,
            witness_root=witness,
        )
    finally:
        os.close(witness.descriptor)
        os.close(destination_root.descriptor)

    assert (witness_dir / raced["name"]).read_bytes() == b"foreign"
    assert (witness_dir / raced["owned"]).read_bytes() == b""
    assert list(destination.iterdir()) == []


def test_receipt_capability_witness_is_external_and_retained(tmp_path: Path) -> None:
    cli = load_cli()
    repository = tmp_path / "repo"
    repository.mkdir()
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    receipt_parent = tmp_path / "receipts"
    receipt_parent.mkdir()
    witness_dir = tmp_path / "receipt-witnesses"
    witness_dir.mkdir()
    output = cli._require_external_new_output(
        path=receipt_parent / "receipt.json",
        repository_root=repository,
        snapshot_root=snapshot,
    )
    witness = cli._require_external_witness_root(
        path=witness_dir,
        repository_root=repository,
        snapshot_root=snapshot,
    )
    try:
        name = cli._probe_receipt_atomic_publication(output, witness)
        assert not (receipt_parent / "receipt.json").exists()
        assert list(receipt_parent.iterdir()) == []
        assert (witness_dir / name).read_bytes() == b""
    finally:
        os.close(witness.descriptor)
        os.close(output.descriptor)
''', encoding="utf-8")

spec = replace_once(
    spec,
    "Before any remote metadata request or model byte download, the executor must first prove that unnamed-file atomic publication actually works on the bound destination filesystem. The CLI performs the same proof for each bound receipt-parent filesystem before acquisition begins. A successful `O_TMPFILE` open or an exported `linkat` symbol alone is insufficient. The capability check publishes an unnamed file with `linkat(..., AT_EMPTY_PATH)` directly into the already-bound transaction directory and verifies the linked identity. Because V1 has no kernel primitive that atomically binds a prior inode observation to namespace removal, the zero-byte hidden capability witness is intentionally retained and the operation then fails closed before remote metadata access or acquisition.\n\n**Current V1 stops at that retained-witness boundary.** The following two-pass metadata sequence documents the already-implemented future operational path only. It is unreachable in V1 after a successful capability proof and requires a separate canonical design/authority change before activation:\n",
    "Before any remote metadata request or model byte download, the executor must first prove that unnamed-file atomic publication actually works on the bound destination filesystem. Under accepted ADR-0037, the operator supplies a dedicated pre-existing external capability-witness root on the same filesystem device. The executor opens the unnamed witness from the bound transaction directory, atomically links it into that dedicated witness root with `linkat(..., AT_EMPTY_PATH)`, verifies the linked inode identity, and retains the zero-byte witness permanently. The model destination therefore remains empty and unchanged by capability proof. The CLI performs the same source-filesystem proof for each bound receipt-output parent using a dedicated receipt witness root. A successful `O_TMPFILE` open or exported `linkat` symbol alone is insufficient.\n\nAfter successful retained-witness proof, the operational two-pass metadata sequence is authorized:\n",
    label="activate metadata rule",
)
spec = replace_once(
    spec,
    "In that future operational path, metadata would be retrieved again immediately before each file download. Its `(path, commit_sha, byte_count, etag, etag_algorithm)` identity must exactly equal the preflight record. Only the ephemeral download location may change.\n\nThis dormant rule is retained so any future activation cannot weaken immutable remote identity binding or signed-location handling.",
    "Metadata is retrieved again immediately before each file download. Its `(path, commit_sha, byte_count, etag, etag_algorithm)` identity must exactly equal the preflight record. Only the ephemeral download location may change. This rule prevents expired signed locations from weakening immutable remote identity binding.",
    label="activate metadata refresh",
)
spec = replace_once(
    spec,
    "The executor never overwrites existing asset files. Before any remote metadata request, it creates an unnamed `O_TMPFILE` through the already-bound destination descriptor, publishes a random hidden zero-byte witness with `linkat(..., AT_EMPTY_PATH)`, verifies the linked inode identity, retains the witness, and returns `BLOCKED` before network access because safe atomic witness cleanup is unavailable in V1. This proves the required publication primitive without performing a racy namespace deletion. The model-byte streaming path remains implemented for a future separately qualified execution boundary, but V1 does not reach it after successful capability proof.\n\nBefore and after any future path-based canonical SafeTensors custody handoff, the destination pathname must still resolve to the exact opened device/inode. If the pathname is concurrently removed, replaced, redirected, or changed to another directory, the transaction fails. Published model files may retain an internal transaction identity for verification, but that identity is never used to justify a non-atomic `stat`-then-`unlink` sequence.\n\nReceipt publication by the CLI follows the same fail-closed V1 rule. The already-bound receipt-parent descriptor publishes and verifies its own hidden zero-byte witness, retains it, and returns `BLOCKED`; no receipt bytes, model bytes, or remote metadata are reached through current V1 after a successful proof. No capability-witness cleanup is automatic because a later name deletion cannot be proven to remove the previously verified inode atomically.\n\nIf a future separately authorized operational path publishes any public model or receipt name and then encounters a later failure, the public residue must be treated as `BLOCKED` evidence for operator inspection. Current V1 does not authorize automatic deletion based on a separate identity observation followed by namespace unlink. Any future activation must independently qualify its residue lifecycle and cannot rely on the older identity-check-then-unlink cleanup claim.",
    "The executor never overwrites existing asset files. Capability proof opens an unnamed `O_TMPFILE` through the already-bound destination descriptor but publishes the random hidden zero-byte witness only into the separately bound same-filesystem witness root. The witness is verified and retained; the destination is rechecked as empty before remote metadata begins. Each authorized model file is then streamed into a same-filesystem unnamed file, byte-counted and content-verified, and atomically linked no-replace to its final authorized basename.\n\nBefore and after the canonical SafeTensors custody handoff, the destination pathname must still resolve to the exact opened device/inode. If the pathname is concurrently removed, replaced, redirected, or changed to another directory, the transaction fails. Published model files may retain an internal transaction identity for verification, but that identity is never used to justify a non-atomic `stat`-then-`unlink` sequence.\n\nReceipt publication follows the same ADR-0037 rule. Each already-bound receipt-output parent proves its source-filesystem publication capability by creating an unnamed file there and atomically linking the witness into the dedicated same-filesystem receipt witness root. The receipt target remains unused during proof. Receipt bytes are later published atomically no-replace.\n\nOnce any model or receipt name is publicly published, automatic deletion, replacement, exchange, repair, resume, or reuse is prohibited. Any later failure remains `BLOCKED`; already-published transaction residue is retained for operator inspection and no success receipt is returned. A subsequent attempt requires a separately inspected empty model destination and unused receipt names.",
    label="activate destination transaction semantics",
)
spec = replace_once(
    spec,
    "The storage-preflight implementation is retained for the future operational path and is not reached by current V1 after successful capability proof. When separately activated, the exact byte count is the sum of authoritative metadata for every authorized file, and available storage is read from the opened destination directory descriptor rather than by re-resolving its pathname. The canonical condition remains:",
    "The exact byte count is the sum of authoritative metadata for every authorized file, and available storage is read from the opened destination directory descriptor rather than by re-resolving its pathname. The canonical condition is:",
    label="activate storage preflight",
)
spec = replace_once(
    spec,
    "The custody handoff implementation is retained but unreachable in current V1 after successful capability proof. In a future separately qualified operational path, after every authorized remote file is verified and atomically present, the executor calls:",
    "After every authorized remote file is verified and atomically present, the executor calls:",
    label="activate custody handoff",
)
spec = replace_once(
    spec,
    "Any future supporting acquisition file identities must be reconciled against the custody receipt's exact local SHA-256 and byte-count manifest before success can be returned.",
    "Supporting acquisition file identities must be reconciled against the custody receipt's exact local SHA-256 and byte-count manifest before success can be returned.",
    label="activate custody reconciliation",
)
spec = replace_once(
    spec,
    "Current V1 cannot emit a successful acquisition-provenance receipt because it blocks before remote metadata or model bytes. The dormant operational path is designed so that a future separately authorized successful execution would emit one deterministic canonical supporting receipt binding remote identities, storage preflight, exact executor code identity, and resulting local custody identities. It must contain no local path, hostname, signed URL, or query string.\n\nThat future receipt contract records:",
    "A successful operational execution emits one deterministic canonical supporting receipt binding remote identities, storage preflight, exact executor code identity, and resulting local custody identities. It contains no local path, hostname, signed URL, or query string.\n\nThe receipt contract records:",
    label="activate provenance receipt",
)
spec = replace_once(
    spec,
    "Such a receipt is not `mesc.mrl.real_preflight.model_weights_set.v1`; it is only an input to later independent verification of that envelope.",
    "This receipt is not `mesc.mrl.real_preflight.model_weights_set.v1`; it is only an input to later independent verification of that envelope.",
    label="activate provenance nontrust",
)
spec = replace_once(
    spec,
    "If a future operational acquisition-provenance receipt exists, `validate_mrl_0801_hf_acquisition_provenance(...)` must, without downloading weights again:",
    "`validate_mrl_0801_hf_acquisition_provenance(...)` must, without downloading weights again:",
    label="activate independent revalidation",
)
spec = replace_once(
    spec,
    "Each receipt output parent directory must already exist as a real directory; the CLI never creates missing receipt-output directories. The parent is resolved, opened once with no-follow directory flags, and bound to its exact device/inode identity. Current V1 uses that bound descriptor only to perform the retained capability-witness proof and then blocks before receipt creation.\n\nThe descriptor-bound exclusive receipt publication and receipt-identity verification implementation remains present for a future separately qualified operational boundary. Current V1 never reaches receipt publication after a successful capability proof and therefore creates no receipt output. Automatic deletion of a published receipt name is not authorized in V1 because an identity check followed by `unlink` cannot atomically prove that the removed name still denotes the transaction-created inode.\n\nUser-visible V1 failure emits a generic blocked message and must not print signed URLs, local paths, credentials, or provider error bodies. Any future success output remains constrained to stable subject/digest fields only.",
    "Each receipt output parent directory must already exist as a real directory; the CLI never creates missing receipt-output directories. The parent is resolved, opened once with no-follow directory flags, and bound to its exact device/inode identity. A separately supplied pre-existing receipt witness root is bound outside the repository and raw snapshot. Each receipt-output parent proves same-filesystem `O_TMPFILE` publication by linking a retained witness into that dedicated witness root before model acquisition begins.\n\nReceipt outputs are created and published exclusively through their bound parent descriptors. Automatic deletion of a published receipt name is prohibited because an identity check followed by `unlink` cannot atomically prove that the removed name still denotes the transaction-created inode. Late receipt/finalizer failure retains published receipt and model residue and returns `BLOCKED`.\n\nUser-visible failure emits a generic blocked message and must not print signed URLs, local paths, credentials, or provider error bodies. Success output is constrained to stable subject/digest fields only.",
    label="activate CLI boundary",
)
spec = replace_once(
    spec,
    "Repository tests inject fake Hub transports. CI must never download model weights or depend on live Hub availability. Transport tests synthesize redirect/metadata responses, including the external-redirect `Content-Length` ambiguity case. Security tests cover exact runtime receipt types, preloaded transitive module rejection, untracked-work-tree rejection, descriptor-relative publication, concurrent destination replacement, missing receipt-parent no-mutation, receipt-output parent replacement, foreign receipt-entry preservation, retained model/receipt capability witnesses, foreign witness replacement preservation, and proof that successful capability publication causes zero remote metadata calls and zero model-byte downloads in current V1.",
    "Repository tests inject fake Hub transports. CI must never download model weights or depend on live Hub availability. Transport tests synthesize redirect/metadata responses, including the external-redirect `Content-Length` ambiguity case. Security tests cover exact runtime receipt types, preloaded transitive module rejection, untracked-work-tree rejection, descriptor-relative publication, concurrent destination replacement, missing receipt-parent no-mutation, receipt-output parent replacement, foreign receipt-entry preservation, dedicated same-filesystem retained model/receipt witnesses, foreign witness replacement preservation, successful proof reaching the metadata phase, racing target preservation, late-failure retained residue, and retry rejection against non-empty failed destinations.",
    label="update CI boundary",
)
spec = replace_once(
    spec,
    "Current V1 emits no successful acquisition receipt and no real asset evidence. The production real-preflight trust registry remains unchanged until a separately reviewed genuine-evidence admission mutation occurs.",
    "Repository qualification emits no real asset evidence. A later genuine operational acquisition may emit a supporting receipt only after canonical merge and post-merge qualification. The production real-preflight trust registry remains unchanged until a separately reviewed genuine-evidence admission mutation occurs.",
    label="update nonauthority ending",
)

SOURCE.write_text(source, encoding="utf-8")
SCRIPT.write_text(script, encoding="utf-8")
ACQ_TEST.write_text(acq_test, encoding="utf-8")
CLI_TEST.write_text(cli_test, encoding="utf-8")
SPEC.write_text(spec, encoding="utf-8")

for path in (SOURCE, SCRIPT, ACQ_TEST, CLI_TEST, WITNESS_TEST, SPEC):
    if not path.read_text(encoding="utf-8").endswith("\n"):
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
