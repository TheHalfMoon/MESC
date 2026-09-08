"""Public, revision-pinned Hugging Face acquisition for MRL-0801.

The executor is intentionally narrow: it can acquire only files already authorized by the
canonical MRL-0801 acquisition/custody artifact. It never reads credentials, accepts terms,
loads model/tokenizer objects, executes remote code, performs inference, uses a GPU, mutates
weights, trains, populates MRL-0801, or changes a trust registry.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import ipaddress
import json
import os
import re
import secrets
import stat
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from http.client import HTTPMessage
from pathlib import Path, PurePosixPath
from typing import IO, Any, Final, Protocol, cast

from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes
from medscale.mesc._mrl_0801_acquisition_custody_v1 import (
    MRL0801AcquisitionAuthorization,
    MRL0801AssetCustodyReceipt,
    generate_mrl_0801_asset_custody_receipt,
    require_mrl_0801_storage_capacity,
    required_mrl_0801_free_bytes,
    validate_mrl_0801_custody_receipt_authorization,
)

_SCHEMA_VERSION: Final = "MESC-MRL-0801-HF-ACQUISITION-PROVENANCE-RECEIPT-V1"
_SOURCE: Final = "huggingface.co"
_USER_AGENT: Final = "MedScale-MESC-MRL-0801-acquisition/1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_SHA1: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_GIT_SHA: Final = _SHA1
_CHUNK_BYTES: Final = 8 * 1024 * 1024
_MODULE_RELATIVE_PATH: Final = Path("src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py")
_ALLOWED_REMOTE_HOST_SUFFIXES: Final = (".huggingface.co", ".hf.co")
_O_NOFOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)
_O_DIRECTORY: Final = getattr(os, "O_DIRECTORY", 0)
_O_CLOEXEC: Final = getattr(os, "O_CLOEXEC", 0)
_O_TMPFILE: Final = getattr(os, "O_TMPFILE", 0)
_AT_EMPTY_PATH: Final = 0x1000
_UNSUPPORTED_LINKAT_ERRNOS: Final = frozenset(
    {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP, getattr(errno, "EOPNOTSUPP", errno.ENOTSUP)}
)
_RECEIPT_KEYS: Final = frozenset(
    {
        "access_authorization_sha256",
        "artifact_identity_sha256",
        "asset_custody_sha256",
        "candidate_roster_sha256",
        "credentials_used",
        "executor_code_commit",
        "executor_code_tree",
        "executor_source_sha256",
        "files",
        "gpu_execution_performed",
        "inference_performed",
        "model_id",
        "model_loading_performed",
        "mrl_0801_population_performed",
        "network_accessed",
        "public_unauthenticated",
        "remote_code_allowed",
        "revision",
        "schema_version",
        "source",
        "storage_available_bytes_at_preflight",
        "storage_required_bytes",
        "terms_accepted",
        "tokenizer_loading_performed",
        "total_byte_count",
        "training_performed",
        "trust_registry_mutation_performed",
        "weight_mutation_performed",
        "weights_sha256",
    }
)
_FILE_KEYS: Final = frozenset(
    {"byte_count", "local_sha256", "path", "remote_etag", "remote_etag_algorithm"}
)


class MRL0801HfAcquisitionError(RuntimeError):
    """Raised when public Hugging Face acquisition cannot be proven safely."""


@dataclass(frozen=True, slots=True)
class RepositoryExecutionIdentity:
    """Exact clean Git identity of the executor bytes used for acquisition."""

    commit_sha: str
    tree_sha: str
    source_sha256: str


@dataclass(frozen=True, slots=True)
class _DestinationDirectory:
    """Opened destination directory identity used for descriptor-relative mutation."""

    path: Path
    descriptor: int
    device: int
    inode: int


@dataclass(frozen=True, slots=True)
class _WitnessDirectory:
    """Opened external capability-witness directory bound for one transaction."""

    path: Path
    descriptor: int
    device: int
    inode: int


class _Digest(Protocol):
    def update(self, data: bytes, /) -> None: ...

    def hexdigest(self) -> str: ...


@dataclass(frozen=True, slots=True)
class HfRemoteFileMetadata:
    """Immutable remote identity for one authorized file at one pinned revision."""

    path: str
    commit_sha: str
    byte_count: int
    etag: str
    location: str = field(repr=False)

    @property
    def etag_algorithm(self) -> str:
        """Return the only supported immutable Hub content-identity algorithm."""
        if _SHA256.fullmatch(self.etag):
            return "sha256"
        if _SHA1.fullmatch(self.etag):
            return "git_blob_sha1"
        raise MRL0801HfAcquisitionError(
            "remote file etag is not a supported immutable content identity"
        )


@dataclass(frozen=True, slots=True)
class HfAcquiredFileIdentity:
    """Remote-to-local byte binding for one acquired file."""

    path: str
    byte_count: int
    remote_etag: str
    remote_etag_algorithm: str
    local_sha256: str
    owned_device: int | None = field(default=None, repr=False, compare=False)
    owned_inode: int | None = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict[str, object]:
        """Return deterministic public provenance fields with no local path or URL."""
        return {
            "byte_count": self.byte_count,
            "local_sha256": self.local_sha256,
            "path": self.path,
            "remote_etag": self.remote_etag,
            "remote_etag_algorithm": self.remote_etag_algorithm,
        }


@dataclass(frozen=True, slots=True)
class MRL0801HfAcquisitionProvenanceReceipt:
    """Canonical path-free remote-provenance receipt for one acquired candidate."""

    canonical_bytes: bytes = field(repr=False)
    receipt_sha256: str = field(init=False)
    model_id: str = field(init=False)
    revision: str = field(init=False)
    access_authorization_sha256: str = field(init=False)
    candidate_roster_sha256: str = field(init=False)
    artifact_identity_sha256: str = field(init=False)
    weights_sha256: str = field(init=False)
    asset_custody_sha256: str = field(init=False)
    executor_code_commit: str = field(init=False)
    executor_code_tree: str = field(init=False)
    executor_source_sha256: str = field(init=False)
    files: tuple[HfAcquiredFileIdentity, ...] = field(init=False)
    total_byte_count: int = field(init=False)
    storage_required_bytes: int = field(init=False)
    storage_available_bytes_at_preflight: int = field(init=False)

    def __post_init__(self) -> None:
        document = _parse_canonical_object(self.canonical_bytes)
        if frozenset(document) != _RECEIPT_KEYS:
            raise MRL0801HfAcquisitionError(
                "acquisition provenance receipt has an invalid top-level key set"
            )
        if document["schema_version"] != _SCHEMA_VERSION or document["source"] != _SOURCE:
            raise MRL0801HfAcquisitionError("acquisition provenance receipt identity is invalid")
        _require_exact_bool(
            document["network_accessed"], expected=True, field_name="network_accessed"
        )
        _require_exact_bool(
            document["public_unauthenticated"],
            expected=True,
            field_name="public_unauthenticated",
        )
        for field_name in (
            "credentials_used",
            "gpu_execution_performed",
            "inference_performed",
            "model_loading_performed",
            "mrl_0801_population_performed",
            "remote_code_allowed",
            "terms_accepted",
            "tokenizer_loading_performed",
            "training_performed",
            "trust_registry_mutation_performed",
            "weight_mutation_performed",
        ):
            _require_exact_bool(document[field_name], expected=False, field_name=field_name)

        model_id = _require_text(document["model_id"], field_name="model_id")
        revision = _require_git_sha(document["revision"], field_name="revision")
        access_sha256 = _require_sha256(
            document["access_authorization_sha256"], field_name="access_authorization_sha256"
        )
        roster_sha256 = _require_sha256(
            document["candidate_roster_sha256"], field_name="candidate_roster_sha256"
        )
        artifact_sha256 = _require_sha256(
            document["artifact_identity_sha256"], field_name="artifact_identity_sha256"
        )
        weights_sha256 = _require_sha256(document["weights_sha256"], field_name="weights_sha256")
        custody_sha256 = _require_sha256(
            document["asset_custody_sha256"], field_name="asset_custody_sha256"
        )
        executor_commit = _require_git_sha(
            document["executor_code_commit"], field_name="executor_code_commit"
        )
        executor_tree = _require_git_sha(
            document["executor_code_tree"], field_name="executor_code_tree"
        )
        executor_source = _require_sha256(
            document["executor_source_sha256"], field_name="executor_source_sha256"
        )
        raw_files = document["files"]
        if type(raw_files) is not list or not raw_files:
            raise MRL0801HfAcquisitionError("acquisition provenance files must be non-empty")
        parsed_files: list[HfAcquiredFileIdentity] = []
        for index, raw_file in enumerate(raw_files):
            if type(raw_file) is not dict:
                raise MRL0801HfAcquisitionError(f"files[{index}] must be an object")
            file_document = cast(dict[str, object], raw_file)
            if frozenset(file_document) != _FILE_KEYS:
                raise MRL0801HfAcquisitionError(f"files[{index}] has an invalid key set")
            path = _require_text(file_document["path"], field_name=f"files[{index}].path")
            _validate_relative_path(path)
            byte_count = _require_positive_int(
                file_document["byte_count"], field_name=f"files[{index}].byte_count"
            )
            remote_etag = _require_text(
                file_document["remote_etag"], field_name=f"files[{index}].remote_etag"
            )
            remote_algorithm = _require_text(
                file_document["remote_etag_algorithm"],
                field_name=f"files[{index}].remote_etag_algorithm",
            )
            if remote_algorithm == "sha256":
                _require_sha256(remote_etag, field_name=f"files[{index}].remote_etag")
            elif remote_algorithm == "git_blob_sha1":
                _require_git_sha(remote_etag, field_name=f"files[{index}].remote_etag")
            else:
                raise MRL0801HfAcquisitionError(
                    f"files[{index}].remote_etag_algorithm is unsupported"
                )
            local_sha256 = _require_sha256(
                file_document["local_sha256"], field_name=f"files[{index}].local_sha256"
            )
            if remote_algorithm == "sha256" and local_sha256 != remote_etag:
                raise MRL0801HfAcquisitionError(
                    f"files[{index}] local SHA-256 does not match remote SHA-256 identity"
                )
            parsed_files.append(
                HfAcquiredFileIdentity(
                    path=path,
                    byte_count=byte_count,
                    remote_etag=remote_etag,
                    remote_etag_algorithm=remote_algorithm,
                    local_sha256=local_sha256,
                )
            )
        paths = tuple(item.path for item in parsed_files)
        if len(paths) != len(set(paths)):
            raise MRL0801HfAcquisitionError("acquisition provenance file paths must be unique")
        total_byte_count = _require_positive_int(
            document["total_byte_count"], field_name="total_byte_count"
        )
        if total_byte_count != sum(item.byte_count for item in parsed_files):
            raise MRL0801HfAcquisitionError(
                "acquisition provenance total_byte_count does not match files"
            )
        storage_required = _require_positive_int(
            document["storage_required_bytes"], field_name="storage_required_bytes"
        )
        expected_required = required_mrl_0801_free_bytes(total_byte_count)
        if storage_required != expected_required:
            raise MRL0801HfAcquisitionError(
                "acquisition provenance storage threshold is not canonical"
            )
        storage_available = _require_positive_int(
            document["storage_available_bytes_at_preflight"],
            field_name="storage_available_bytes_at_preflight",
        )
        if storage_available < storage_required:
            raise MRL0801HfAcquisitionError(
                "acquisition provenance claims a failed storage preflight"
            )

        object.__setattr__(self, "receipt_sha256", hashlib.sha256(self.canonical_bytes).hexdigest())
        object.__setattr__(self, "model_id", model_id)
        object.__setattr__(self, "revision", revision)
        object.__setattr__(self, "access_authorization_sha256", access_sha256)
        object.__setattr__(self, "candidate_roster_sha256", roster_sha256)
        object.__setattr__(self, "artifact_identity_sha256", artifact_sha256)
        object.__setattr__(self, "weights_sha256", weights_sha256)
        object.__setattr__(self, "asset_custody_sha256", custody_sha256)
        object.__setattr__(self, "executor_code_commit", executor_commit)
        object.__setattr__(self, "executor_code_tree", executor_tree)
        object.__setattr__(self, "executor_source_sha256", executor_source)
        object.__setattr__(self, "files", tuple(parsed_files))
        object.__setattr__(self, "total_byte_count", total_byte_count)
        object.__setattr__(self, "storage_required_bytes", storage_required)
        object.__setattr__(self, "storage_available_bytes_at_preflight", storage_available)


class HfPublicTransport(Protocol):
    """Credential-free transport contract used by the bounded executor."""

    def metadata(
        self,
        *,
        model_id: str,
        revision: str,
        path: str,
    ) -> HfRemoteFileMetadata: ...

    def iter_bytes(self, *, metadata: HfRemoteFileMetadata) -> Iterator[bytes]: ...


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        return None


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        _require_safe_remote_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibHfPublicTransport:
    """Minimal HTTPS-only Hub transport that never reads or sends credentials."""

    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._timeout = timeout_seconds
        self._metadata_opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _NoRedirect(),
        )
        self._download_opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            _SafeRedirect(),
        )

    def metadata(
        self,
        *,
        model_id: str,
        revision: str,
        path: str,
    ) -> HfRemoteFileMetadata:
        url = _hf_resolve_url(model_id=model_id, revision=revision, path=path)
        for _ in range(8):
            request = urllib.request.Request(
                url,
                headers={"User-Agent": _USER_AGENT},
                method="HEAD",
            )
            try:
                response = self._metadata_opener.open(request, timeout=self._timeout)
            except urllib.error.HTTPError as exc:
                if exc.code in {301, 302, 303, 307, 308}:
                    headers = exc.headers
                    status = exc.code
                elif exc.code in {401, 403}:
                    raise MRL0801HfAcquisitionError(
                        "authorized file is not available through public unauthenticated access"
                    ) from None
                else:
                    raise MRL0801HfAcquisitionError(
                        "Hugging Face metadata request failed for an authorized file"
                    ) from None
            except (urllib.error.URLError, OSError):
                raise MRL0801HfAcquisitionError(
                    "Hugging Face metadata transport failed for an authorized file"
                ) from None
            else:
                with response:
                    headers = response.headers
                    status = response.status

            if status in {301, 302, 303, 307, 308}:
                raw_location = headers.get("Location")
                if raw_location is None:
                    raise MRL0801HfAcquisitionError(
                        "Hugging Face metadata redirect is missing a location"
                    )
                next_url = urllib.parse.urljoin(url, raw_location)
                _require_safe_remote_url(next_url)
                next_host = urllib.parse.urlparse(next_url).hostname
                if next_host is not None and next_host.rstrip(".").lower() == "huggingface.co":
                    url = next_url
                    continue

                commit_sha = headers.get("X-Repo-Commit")
                size_text = headers.get("X-Linked-Size")
                etag_text = headers.get("X-Linked-Etag")
                if commit_sha is None or size_text is None or etag_text is None:
                    raise MRL0801HfAcquisitionError(
                        "Hugging Face external redirect lacks authoritative linked metadata"
                    )
                return _build_remote_metadata(
                    path=path,
                    commit_sha=commit_sha,
                    size_text=size_text,
                    etag_text=etag_text,
                    location=next_url,
                )

            if status != 200:
                raise MRL0801HfAcquisitionError(
                    "Hugging Face metadata transport returned an unsupported status"
                )
            commit_sha = headers.get("X-Repo-Commit")
            size_text = headers.get("Content-Length")
            etag_text = headers.get("X-Linked-Etag") or headers.get("ETag")
            if commit_sha is None or size_text is None or etag_text is None:
                raise MRL0801HfAcquisitionError(
                    "Hugging Face final metadata is missing revision, size, or etag"
                )
            return _build_remote_metadata(
                path=path,
                commit_sha=commit_sha,
                size_text=size_text,
                etag_text=etag_text,
                location=url,
            )
        raise MRL0801HfAcquisitionError("Hugging Face metadata exceeded the redirect limit")

    def iter_bytes(self, *, metadata: HfRemoteFileMetadata) -> Iterator[bytes]:
        _require_safe_remote_url(metadata.location)
        request = urllib.request.Request(
            metadata.location,
            headers={"User-Agent": _USER_AGENT},
            method="GET",
        )
        try:
            response = self._download_opener.open(request, timeout=self._timeout)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            raise MRL0801HfAcquisitionError(
                "Hugging Face byte transport failed for an authorized file"
            ) from None
        with response:
            _require_safe_remote_url(response.geturl())
            if response.status != 200:
                raise MRL0801HfAcquisitionError(
                    "Hugging Face byte transport returned a non-success status"
                )
            while True:
                chunk = response.read(_CHUNK_BYTES)
                if not chunk:
                    return
                yield chunk


def acquire_mrl_0801_hf_candidate(
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
        os.close(destination_root.descriptor)


def validate_mrl_0801_hf_acquisition_provenance(
    *,
    receipt: MRL0801HfAcquisitionProvenanceReceipt,
    custody: MRL0801AssetCustodyReceipt,
    authorization: MRL0801AcquisitionAuthorization,
    model_root: Path,
    transport: HfPublicTransport,
    repository_root: Path,
) -> None:
    """Reverify remote identities, historical executor bytes, and current local custody."""
    if type(receipt) is not MRL0801HfAcquisitionProvenanceReceipt:
        raise MRL0801HfAcquisitionError(
            "receipt must use the exact canonical MRL0801HfAcquisitionProvenanceReceipt type"
        )
    if type(custody) is not MRL0801AssetCustodyReceipt:
        raise MRL0801HfAcquisitionError(
            "custody must use the exact canonical MRL0801AssetCustodyReceipt type"
        )
    if type(authorization) is not MRL0801AcquisitionAuthorization:
        raise MRL0801HfAcquisitionError(
            "authorization must use the exact canonical MRL0801AcquisitionAuthorization type"
        )
    candidate = authorization.require_candidate(
        model_id=receipt.model_id,
        revision=receipt.revision,
    )
    _validate_recorded_repository_execution_identity(
        repository_root=repository_root,
        receipt=receipt,
    )
    validate_mrl_0801_custody_receipt_authorization(
        receipt=custody,
        authorization=authorization,
        model_root=model_root,
    )
    _require_receipt_matches_custody(
        receipt=receipt,
        custody=custody,
        authorization=authorization,
        expected_files=candidate.allowed_files,
    )
    for recorded in receipt.files:
        remote = transport.metadata(
            model_id=receipt.model_id,
            revision=receipt.revision,
            path=recorded.path,
        )
        _require_safe_remote_url(remote.location)
        if (
            remote.path != recorded.path
            or remote.commit_sha != receipt.revision
            or remote.byte_count != recorded.byte_count
            or remote.etag != recorded.remote_etag
            or remote.etag_algorithm != recorded.remote_etag_algorithm
        ):
            raise MRL0801HfAcquisitionError(
                "current pinned Hugging Face metadata does not match acquisition provenance"
            )


def _require_receipt_matches_custody(
    *,
    receipt: MRL0801HfAcquisitionProvenanceReceipt,
    custody: MRL0801AssetCustodyReceipt,
    authorization: MRL0801AcquisitionAuthorization,
    expected_files: tuple[str, ...],
) -> None:
    if type(receipt) is not MRL0801HfAcquisitionProvenanceReceipt:
        raise MRL0801HfAcquisitionError("acquisition provenance receipt type is not canonical")
    if type(custody) is not MRL0801AssetCustodyReceipt:
        raise MRL0801HfAcquisitionError("custody receipt type is not canonical")
    if type(authorization) is not MRL0801AcquisitionAuthorization:
        raise MRL0801HfAcquisitionError("acquisition authorization type is not canonical")
    if receipt.model_id != custody.model_id or receipt.revision != custody.revision:
        raise MRL0801HfAcquisitionError("acquisition and custody subject identities differ")
    if receipt.access_authorization_sha256 != authorization.authorization_sha256:
        raise MRL0801HfAcquisitionError("acquisition provenance binds a different authorization")
    if receipt.candidate_roster_sha256 != _candidate_roster_sha256(custody):
        raise MRL0801HfAcquisitionError("acquisition provenance binds a different roster")
    if receipt.artifact_identity_sha256 != custody.artifact_identity_sha256:
        raise MRL0801HfAcquisitionError("acquisition and custody artifact identities differ")
    if receipt.weights_sha256 != custody.weights_sha256:
        raise MRL0801HfAcquisitionError("acquisition and custody weight identities differ")
    if receipt.asset_custody_sha256 != custody.asset_custody_sha256:
        raise MRL0801HfAcquisitionError("acquisition provenance binds a different custody receipt")
    if tuple(item.path for item in receipt.files) != expected_files:
        raise MRL0801HfAcquisitionError(
            "acquisition provenance does not equal the authorized allowlist"
        )
    custody_by_path = {item.path: item for item in custody.files}
    if tuple(custody_by_path) != expected_files:
        raise MRL0801HfAcquisitionError("custody receipt does not equal the authorized allowlist")
    for item in receipt.files:
        local = custody_by_path[item.path]
        if local.byte_count != item.byte_count or local.sha256 != item.local_sha256:
            raise MRL0801HfAcquisitionError(
                "acquisition provenance local file identity differs from verified custody"
            )


def _candidate_roster_sha256(custody: MRL0801AssetCustodyReceipt) -> str:
    loaded: object = json.loads(custody.canonical_bytes.decode("utf-8"))
    if type(loaded) is not dict:
        raise MRL0801HfAcquisitionError("custody receipt must be a JSON object")
    document = cast(dict[str, object], loaded)
    value = document.get("candidate_roster_sha256")
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise MRL0801HfAcquisitionError("custody receipt has no canonical roster identity")
    return value


def _run_git_bytes(repository_root: Path, *arguments: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repository_root), *arguments],
            check=False,
            capture_output=True,
        )
    except OSError:
        raise MRL0801HfAcquisitionError("Git execution is unavailable") from None
    if completed.returncode != 0:
        raise MRL0801HfAcquisitionError("repository Git identity cannot be resolved")
    return completed.stdout


def _run_git_text(repository_root: Path, *arguments: str) -> str:
    try:
        return _run_git_bytes(repository_root, *arguments).decode("utf-8").strip()
    except UnicodeDecodeError:
        raise MRL0801HfAcquisitionError("repository Git text output is not UTF-8") from None


def _capture_repository_execution_identity(repository_root: Path) -> RepositoryExecutionIdentity:
    root = repository_root.resolve(strict=True)
    if not (root / ".git").exists():
        raise MRL0801HfAcquisitionError("repository_root is not a Git work tree")
    top_level = Path(_run_git_text(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if top_level != root:
        raise MRL0801HfAcquisitionError("repository_root is not the exact Git work-tree root")
    status = _run_git_bytes(root, "status", "--porcelain", "--untracked-files=all")
    if status:
        raise MRL0801HfAcquisitionError("repository work tree must be clean before acquisition")
    commit_sha = _require_git_sha(
        _run_git_text(root, "rev-parse", "HEAD"), field_name="executor_code_commit"
    )
    tree_sha = _require_git_sha(
        _run_git_text(root, "rev-parse", "HEAD^{tree}"), field_name="executor_code_tree"
    )
    expected_source = (root / _MODULE_RELATIVE_PATH).resolve(strict=True)
    actual_source = Path(__file__).resolve(strict=True)
    if actual_source != expected_source:
        raise MRL0801HfAcquisitionError(
            "executor must run from the exact checked-out repository source"
        )
    current_bytes = expected_source.read_bytes()
    committed_bytes = _run_git_bytes(root, "show", f"HEAD:{_MODULE_RELATIVE_PATH.as_posix()}")
    if current_bytes != committed_bytes:
        raise MRL0801HfAcquisitionError("executor source bytes differ from the exact Git commit")
    return RepositoryExecutionIdentity(
        commit_sha=commit_sha,
        tree_sha=tree_sha,
        source_sha256=hashlib.sha256(current_bytes).hexdigest(),
    )


def _validate_recorded_repository_execution_identity(
    *,
    repository_root: Path,
    receipt: MRL0801HfAcquisitionProvenanceReceipt,
) -> None:
    root = repository_root.resolve(strict=True)
    if not (root / ".git").exists():
        raise MRL0801HfAcquisitionError("repository_root is not a Git work tree")
    top_level = Path(_run_git_text(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
    if top_level != root:
        raise MRL0801HfAcquisitionError("repository_root is not the exact Git work-tree root")
    recorded_tree = _require_git_sha(
        _run_git_text(root, "rev-parse", f"{receipt.executor_code_commit}^{{tree}}"),
        field_name="recorded executor tree",
    )
    if recorded_tree != receipt.executor_code_tree:
        raise MRL0801HfAcquisitionError(
            "recorded executor commit does not resolve to the receipt tree"
        )
    try:
        ancestry = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "merge-base",
                "--is-ancestor",
                receipt.executor_code_commit,
                "HEAD",
            ],
            check=False,
            capture_output=True,
        )
    except OSError:
        raise MRL0801HfAcquisitionError("Git execution is unavailable") from None
    if ancestry.returncode != 0:
        raise MRL0801HfAcquisitionError(
            "recorded executor commit is not an ancestor of the review repository state"
        )
    committed_source = _run_git_bytes(
        root,
        "show",
        f"{receipt.executor_code_commit}:{_MODULE_RELATIVE_PATH.as_posix()}",
    )
    if hashlib.sha256(committed_source).hexdigest() != receipt.executor_source_sha256:
        raise MRL0801HfAcquisitionError(
            "recorded executor source identity does not match Git history"
        )


def _parse_canonical_object(raw: bytes) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise MRL0801HfAcquisitionError("acquisition provenance must be non-empty exact bytes")
    try:
        loaded: object = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
        if type(loaded) is not dict:
            raise MRL0801HfAcquisitionError("acquisition provenance must be a JSON object")
        document = cast(dict[str, object], loaded)
        canonical = canonical_json_bytes(document)
    except MRL0801HfAcquisitionError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError, CanonicalContractError) as exc:
        raise MRL0801HfAcquisitionError(
            "acquisition provenance must be valid canonical UTF-8 JSON"
        ) from exc
    if canonical != raw:
        raise MRL0801HfAcquisitionError("acquisition provenance bytes are not canonical JSON")
    return document


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MRL0801HfAcquisitionError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise MRL0801HfAcquisitionError(f"non-standard JSON constant is prohibited: {value}")


def _require_text(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value.strip():
        raise MRL0801HfAcquisitionError(f"{field_name} must be a non-blank string")
    return value


def _require_sha256(value: object, *, field_name: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise MRL0801HfAcquisitionError(f"{field_name} must be 64 lowercase hex characters")
    return value


def _require_git_sha(value: object, *, field_name: str) -> str:
    if type(value) is not str or _GIT_SHA.fullmatch(value) is None:
        raise MRL0801HfAcquisitionError(f"{field_name} must be 40 lowercase hex characters")
    return value


def _require_positive_int(value: object, *, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        raise MRL0801HfAcquisitionError(f"{field_name} must be a positive integer")
    return value


def _require_exact_bool(value: object, *, expected: bool, field_name: str) -> None:
    if type(value) is not bool or value is not expected:
        expected_text = "true" if expected else "false"
        raise MRL0801HfAcquisitionError(f"{field_name} must be exactly {expected_text}")


def _hf_resolve_url(*, model_id: str, revision: str, path: str) -> str:
    if _GIT_SHA.fullmatch(revision) is None:
        raise MRL0801HfAcquisitionError("revision must be an immutable lowercase commit SHA")
    _validate_relative_path(path)
    encoded_model = urllib.parse.quote(model_id, safe="/")
    encoded_path = urllib.parse.quote(path, safe="/")
    return f"https://huggingface.co/{encoded_model}/resolve/{revision}/{encoded_path}"


def _normalize_etag(value: str | None) -> str:
    if value is None:
        raise MRL0801HfAcquisitionError("Hugging Face metadata is missing a content etag")
    normalized = value.strip()
    if normalized.startswith("W/"):
        normalized = normalized[2:].strip()
    normalized = normalized.strip('"')
    if _SHA256.fullmatch(normalized) is None and _SHA1.fullmatch(normalized) is None:
        raise MRL0801HfAcquisitionError("Hugging Face content etag is not immutable")
    return normalized


def _build_remote_metadata(
    *,
    path: str,
    commit_sha: str,
    size_text: str,
    etag_text: str,
    location: str,
) -> HfRemoteFileMetadata:
    try:
        byte_count = int(size_text)
    except ValueError:
        raise MRL0801HfAcquisitionError(
            "Hugging Face metadata contains an invalid exact size"
        ) from None
    if byte_count <= 0:
        raise MRL0801HfAcquisitionError("Hugging Face metadata exact size must be positive")
    return HfRemoteFileMetadata(
        path=path,
        commit_sha=commit_sha,
        byte_count=byte_count,
        etag=_normalize_etag(etag_text),
        location=location,
    )


def _validate_relative_path(path: str) -> PurePosixPath:
    value = PurePosixPath(path)
    if (
        not path
        or "\\" in path
        or "\x00" in path
        or value.is_absolute()
        or len(value.parts) != 1
        or any(part in {"", ".", ".."} for part in value.parts)
    ):
        raise MRL0801HfAcquisitionError(
            "authorized file path must be one normalized relative basename"
        )
    if str(value) != path:
        raise MRL0801HfAcquisitionError("authorized file path is not canonical")
    return value


def _is_descendant(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _require_descriptor_relative_support() -> None:
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


def _stat_descriptor_identity(observation: os.stat_result) -> tuple[int, int]:
    return observation.st_dev, observation.st_ino


def _require_external_empty_destination(
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
        )


def _require_no_existing_symlink_components(path: Path, *, label: str) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            raise MRL0801HfAcquisitionError(f"{label} must not traverse a symbolic link")


def _require_destination_path_identity(destination: _DestinationDirectory) -> None:
    try:
        opened = os.fstat(destination.descriptor)
        current = destination.path.stat(follow_symlinks=False)
    except OSError:
        raise MRL0801HfAcquisitionError(
            "acquisition destination path changed during the transaction"
        ) from None
    expected = (destination.device, destination.inode)
    if (
        not stat.S_ISDIR(opened.st_mode)
        or not stat.S_ISDIR(current.st_mode)
        or _stat_descriptor_identity(opened) != expected
        or _stat_descriptor_identity(current) != expected
    ):
        raise MRL0801HfAcquisitionError(
            "acquisition destination path changed during the transaction"
        )


def _available_bytes(destination: _DestinationDirectory) -> int:
    try:
        observation = os.fstatvfs(destination.descriptor)
    except OSError:
        raise MRL0801HfAcquisitionError(
            "acquisition destination storage capacity could not be inspected"
        ) from None
    available = observation.f_bavail * observation.f_frsize
    if available <= 0:
        raise MRL0801HfAcquisitionError(
            "acquisition destination reports no available storage capacity"
        )
    return available


def _descriptor_entries(*, root_fd: int) -> frozenset[str]:
    try:
        return frozenset(
            os.listdir(root_fd)  # noqa: PTH208 -- descriptor-relative listing is required
        )
    except OSError:
        raise MRL0801HfAcquisitionError(
            "acquisition destination could not be enumerated safely"
        ) from None


def _require_safe_remote_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise MRL0801HfAcquisitionError("remote location must be credential-free HTTPS")
    host = parsed.hostname.rstrip(".").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise MRL0801HfAcquisitionError("remote location uses a prohibited local hostname")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if host != "huggingface.co" and not host.endswith(_ALLOWED_REMOTE_HOST_SUFFIXES):
            raise MRL0801HfAcquisitionError(
                "remote location is outside the bounded Hugging Face transport domains"
            ) from None
        return
    if not address.is_global:
        raise MRL0801HfAcquisitionError("remote location uses a non-global IP address")
    raise MRL0801HfAcquisitionError(
        "literal IP download locations are outside the bounded Hugging Face transport domains"
    )


def _verify_remote_allowlist_metadata(
    *,
    transport: HfPublicTransport,
    model_id: str,
    revision: str,
    allowed_files: tuple[str, ...],
) -> tuple[HfRemoteFileMetadata, ...]:
    if _GIT_SHA.fullmatch(revision) is None:
        raise MRL0801HfAcquisitionError("revision must be an immutable lowercase commit SHA")
    if not allowed_files or len(set(allowed_files)) != len(allowed_files):
        raise MRL0801HfAcquisitionError("authorized allowlist must be non-empty and unique")
    result: list[HfRemoteFileMetadata] = []
    for path in allowed_files:
        _validate_relative_path(path)
        item = transport.metadata(model_id=model_id, revision=revision, path=path)
        if item.path != path:
            raise MRL0801HfAcquisitionError("remote metadata path escaped the authorized allowlist")
        if item.commit_sha != revision:
            raise MRL0801HfAcquisitionError(
                "remote metadata did not resolve to the authorized revision"
            )
        if type(item.byte_count) is not int or item.byte_count <= 0:
            raise MRL0801HfAcquisitionError("remote metadata lacks a positive exact byte count")
        _ = item.etag_algorithm
        _require_safe_remote_url(item.location)
        result.append(item)
    return tuple(result)


def _require_same_remote_identity(
    *,
    preflight: HfRemoteFileMetadata,
    fresh: HfRemoteFileMetadata,
) -> None:
    if (
        fresh.path != preflight.path
        or fresh.commit_sha != preflight.commit_sha
        or fresh.byte_count != preflight.byte_count
        or fresh.etag != preflight.etag
        or fresh.etag_algorithm != preflight.etag_algorithm
    ):
        raise MRL0801HfAcquisitionError(
            "remote file identity changed between storage preflight and byte acquisition"
        )
    _require_safe_remote_url(fresh.location)


def _new_git_blob_digest(byte_count: int) -> _Digest:
    digest = hashlib.sha1(usedforsecurity=False)
    digest.update(f"blob {byte_count}\0".encode("ascii"))
    return digest


def _descriptor_entry_exists(*, root_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=root_fd, follow_symlinks=False)
    except FileNotFoundError:
        return False
    except OSError:
        raise MRL0801HfAcquisitionError(
            "acquisition destination entry could not be inspected safely"
        ) from None
    return True


def _descriptor_entry_stat(*, root_fd: int, name: str) -> os.stat_result | None:
    try:
        return os.stat(name, dir_fd=root_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    except OSError:
        raise MRL0801HfAcquisitionError(
            "acquisition destination entry could not be inspected safely"
        ) from None


def _load_posix_symbol(name: str) -> Any:
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


def _probe_atomic_descriptor_publication(
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
            os.close(source_fd)


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
