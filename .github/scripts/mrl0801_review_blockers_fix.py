from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1])


def replace_exact(path: str, old: str, new: str, *, expected: int = 1) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{path}: expected {expected} exact match(es), found {count}")
    target.write_text(text.replace(old, new), encoding="utf-8")


core = "src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py"

replace_exact(
    core,
    '''class _Digest(Protocol):
    def update(self, data: bytes, /) -> None: ...

    def hexdigest(self) -> str: ...


@dataclass(frozen=True, slots=True)
class HfRemoteFileMetadata:
''',
    '''class _Digest(Protocol):
    def update(self, data: bytes, /) -> None: ...

    def hexdigest(self) -> str: ...


class _StatVfsResult(Protocol):
    f_bavail: int
    f_frsize: int


class _FstatVfs(Protocol):
    def __call__(self, descriptor: int, /) -> _StatVfsResult: ...


@dataclass(frozen=True, slots=True)
class HfRemoteFileMetadata:
''',
)

replace_exact(
    core,
    '''    normalized = value.strip()
    if normalized.startswith("W/"):
        normalized = normalized[2:].strip()
    normalized = normalized.strip('"')
''',
    '''    normalized = value.strip()
    if normalized.startswith("W/"):
        raise MRL0801HfAcquisitionError(
            "Hugging Face content etag must not use a weak validator"
        )
    normalized = normalized.strip('"')
''',
)

replace_exact(
    core,
    '''    for recorded in receipt.files:
        remote = transport.metadata(
''',
    '''    for recorded in receipt.files:
        _require_git_blob_identity_matches_local_bytes(
            model_root=model_root,
            recorded=recorded,
        )
        remote = transport.metadata(
''',
)

replace_exact(
    core,
    '''

def _require_receipt_matches_custody(
''',
    '''

def _require_git_blob_identity_matches_local_bytes(
    *,
    model_root: Path,
    recorded: HfAcquiredFileIdentity,
) -> None:
    """Bind a recorded Git-blob remote identity to the locally revalidated bytes."""
    if recorded.remote_etag_algorithm != "git_blob_sha1":
        return
    _validate_relative_path(recorded.path)
    local_sha256 = hashlib.sha256()
    git_blob_sha1 = _new_git_blob_digest(recorded.byte_count)
    observed_bytes = 0
    try:
        with (model_root / recorded.path).open("rb") as stream:
            while True:
                chunk = stream.read(_CHUNK_BYTES)
                if not chunk:
                    break
                observed_bytes += len(chunk)
                local_sha256.update(chunk)
                git_blob_sha1.update(chunk)
    except OSError:
        raise MRL0801HfAcquisitionError(
            "local bytes could not be reread for Git-blob identity verification"
        ) from None
    if (
        observed_bytes != recorded.byte_count
        or local_sha256.hexdigest() != recorded.local_sha256
    ):
        raise MRL0801HfAcquisitionError(
            "local bytes changed during Git-blob identity verification"
        )
    if git_blob_sha1.hexdigest() != recorded.remote_etag:
        raise MRL0801HfAcquisitionError(
            "local Git-blob identity does not match acquisition provenance"
        )


def _require_receipt_matches_custody(
''',
)

replace_exact(
    core,
    '''def _available_bytes(destination: _DestinationDirectory) -> int:
    try:
        observation = os.fstatvfs(destination.descriptor)
    except OSError:
        raise MRL0801HfAcquisitionError(
            "acquisition destination storage capacity could not be inspected"
        ) from None
''',
    '''def _available_bytes(destination: _DestinationDirectory) -> int:
    fstatvfs = cast(_FstatVfs | None, getattr(os, "fstatvfs", None))
    if fstatvfs is None:
        raise MRL0801HfAcquisitionError(
            "platform lacks descriptor-relative storage-capacity inspection"
        )
    try:
        observation = fstatvfs(destination.descriptor)
    except OSError:
        raise MRL0801HfAcquisitionError(
            "acquisition destination storage capacity could not be inspected"
        ) from None
''',
)

replace_exact(
    "pyproject.toml",
    '''# Windows typeshed intentionally omits POSIX-only os.fstatvfs. The executor checks the full
# descriptor capability set at runtime and fails closed before that call on unsupported hosts.
# Keep the exception isolated to this module; all other strict mypy diagnostics remain active.
[[tool.mypy.overrides]]
module = ["medscale.mesc._mrl_0801_hf_acquisition_v1"]
disable_error_code = ["attr-defined", "no-any-return"]

''',
    "",
)

replace_exact(
    "tests/test_mesc_mrl_0801_hf_transport_v1.py",
    '''        ("123", "mutable-etag", "content etag is not immutable"),
''',
    '''        ("123", "mutable-etag", "content etag is not immutable"),
        ("123", f'W/"{ETAG}"', "must not use a weak validator"),
''',
)

replace_exact(
    "tests/test_mesc_mrl_0801_hf_acquisition_v1.py",
    '''class ReplacingTransport(FakeTransport):
''',
    '''class RevalidationGitBlobMismatchTransport(FakeTransport):
    def metadata(
        self,
        *,
        model_id: str,
        revision: str,
        path: str,
    ) -> subject.HfRemoteFileMetadata:
        item = super().metadata(model_id=model_id, revision=revision, path=path)
        if path != FILES[0]:
            return item
        return subject.HfRemoteFileMetadata(
            path=item.path,
            commit_sha=item.commit_sha,
            byte_count=item.byte_count,
            etag="f" * 40,
            location=item.location,
        )


class ReplacingTransport(FakeTransport):
''',
)

replace_exact(
    "tests/test_mesc_mrl_0801_hf_acquisition_v1.py",
    '''
def test_spoofed_authorization_fails_before_transport(
''',
    '''
def test_revalidation_binds_git_blob_etag_to_current_local_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination, custody, receipt = acquire(tmp_path, monkeypatch, FakeTransport())
    document = cast(dict[str, object], json.loads(receipt.canonical_bytes))
    raw_files = cast(list[dict[str, object]], document["files"])
    raw_files[0]["remote_etag"] = "f" * 40
    mismatched_receipt = subject.MRL0801HfAcquisitionProvenanceReceipt(
        canonical_json_bytes(document)
    )

    with pytest.raises(subject.MRL0801HfAcquisitionError, match="local Git-blob identity"):
        subject.validate_mrl_0801_hf_acquisition_provenance(
            receipt=mismatched_receipt,
            custody=custody,
            authorization=authorization(),
            model_root=destination,
            transport=RevalidationGitBlobMismatchTransport(),
            repository_root=fake_repo(tmp_path / "review-git-blob"),
        )


def test_spoofed_authorization_fails_before_transport(
''',
)
