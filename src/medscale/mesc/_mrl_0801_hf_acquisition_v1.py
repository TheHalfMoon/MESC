"""Public, revision-pinned Hugging Face acquisition for MRL-0801.

The executor is intentionally narrow: it can acquire only files already authorized by the
canonical MRL-0801 acquisition/custody artifact. It never reads credentials, accepts terms,
loads model/tokenizer objects, executes remote code, performs inference, uses a GPU, mutates
weights, trains, populates MRL-0801, or changes a trust registry.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Final, Protocol

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
        weights_sha256 = _require_sha256(
            document["weights_sha256"], field_name="weights_sha256"
        )
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
            file_document = raw_file
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
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> urllib.request.Request | None:
        return None


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
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
                    # Follow Hub-internal resolve-cache redirects, preserving the query string.
                    url = next_url
                    continue

                # On an external/CDN redirect, Content-Length describes the redirect body,
                # not the target object. Only authoritative linked metadata is admissible.
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
    model_id: str,
    revision: str,
) -> tuple[MRL0801AssetCustodyReceipt, MRL0801HfAcquisitionProvenanceReceipt]:
    """Acquire one exact authorized candidate and bind remote provenance to local custody."""
    if type(authorization) is not MRL0801AcquisitionAuthorization:
        raise MRL0801HfAcquisitionError(
            "authorization must be an exact MRL0801AcquisitionAuthorization"
        )
    execution_identity = _capture_repository_execution_identity(repository_root)
    candidate = authorization.require_candidate(model_id=model_id, revision=revision)
    root = _require_external_empty_destination(
        destination=destination,
        repository_root=repository_root,
    )
    metadata = _verify_remote_allowlist_metadata(
        transport=transport,
        model_id=model_id,
        revision=revision,
        allowed_files=candidate.allowed_files,
    )
    exact_allowlist_bytes = sum(item.byte_count for item in metadata)
    available_bytes = shutil.disk_usage(root).free
    storage_required_bytes = require_mrl_0801_storage_capacity(
        exact_allowlist_bytes=exact_allowlist_bytes,
        available_bytes=available_bytes,
    )

    acquired: list[HfAcquiredFileIdentity] = []
    try:
        for preflight_item in metadata:
            fresh_item = transport.metadata(
                model_id=model_id,
                revision=revision,
                path=preflight_item.path,
            )
            _require_same_remote_identity(preflight=preflight_item, fresh=fresh_item)
            acquired.append(_acquire_one_file(root=root, transport=transport, metadata=fresh_item))
        custody = generate_mrl_0801_asset_custody_receipt(
            model_root=root,
            authorization=authorization,
            model_id=model_id,
            revision=revision,
        )
    except BaseException:
        _rollback_created_files(root=root, acquired=tuple(acquired))
        raise

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
    return custody, receipt


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
    if type(authorization) is not MRL0801AcquisitionAuthorization:
        raise MRL0801HfAcquisitionError(
            "authorization must be an exact MRL0801AcquisitionAuthorization"
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
    document = json.loads(custody.canonical_bytes.decode("utf-8"))
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
    status = _run_git_bytes(root, "status", "--porcelain", "--untracked-files=no")
    if status:
        raise MRL0801HfAcquisitionError(
            "tracked repository bytes must be clean before acquisition"
        )
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
        raise MRL0801HfAcquisitionError(
            "executor source bytes differ from the exact Git commit"
        )
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
    # The acquisition commit must be in the ancestry of the repository state used for review.
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
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_json_constant,
        )
        if type(value) is not dict:
            raise MRL0801HfAcquisitionError("acquisition provenance must be a JSON object")
        document = value
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
        raise MRL0801HfAcquisitionError(
            "Hugging Face metadata exact size must be positive"
        )
    return HfRemoteFileMetadata(
        path=path,
        commit_sha=commit_sha,
        byte_count=byte_count,
        etag=_normalize_etag(etag_text),
        location=location,
    )


def _validate_relative_path(path: str) -> PurePosixPath:
    value = PurePosixPath(path)
    if not path or value.is_absolute() or any(part in {"", ".", ".."} for part in value.parts):
        raise MRL0801HfAcquisitionError("authorized file path must be normalized and relative")
    if str(value) != path:
        raise MRL0801HfAcquisitionError("authorized file path is not canonical")
    return value


def _is_descendant(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _require_external_empty_destination(*, destination: Path, repository_root: Path) -> Path:
    repo = repository_root.resolve(strict=True)
    raw = destination.expanduser().absolute()
    if raw == repo or _is_descendant(raw, repo):
        raise MRL0801HfAcquisitionError("raw model snapshot destination must be outside Git")
    _require_no_existing_symlink_components(raw, label="raw model snapshot destination")
    root = raw.resolve(strict=False)
    if root == repo or _is_descendant(root, repo):
        raise MRL0801HfAcquisitionError("raw model snapshot destination must be outside Git")
    for ancestor in (root, *root.parents):
        if (ancestor / ".git").exists():
            raise MRL0801HfAcquisitionError(
                "raw model snapshot destination is inside a Git work tree"
            )
    if root.exists():
        if not root.is_dir() or any(root.iterdir()):
            raise MRL0801HfAcquisitionError(
                "acquisition destination must be an empty real directory"
            )
    else:
        root.mkdir(parents=True, mode=0o700)
    return root


def _require_no_existing_symlink_components(path: Path, *, label: str) -> None:
    for component in (path, *path.parents):
        if component.is_symlink():
            raise MRL0801HfAcquisitionError(f"{label} must not traverse a symbolic link")


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
            )
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


def _acquire_one_file(
    *,
    root: Path,
    transport: HfPublicTransport,
    metadata: HfRemoteFileMetadata,
) -> HfAcquiredFileIdentity:
    relative = _validate_relative_path(metadata.path)
    target = root.joinpath(*relative.parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        raise MRL0801HfAcquisitionError("executor refuses to overwrite an existing asset file")
    partial = target.with_name(f".{target.name}.mrl-0801-partial")
    if partial.exists() or partial.is_symlink():
        raise MRL0801HfAcquisitionError("stale partial acquisition file exists")

    sha256 = hashlib.sha256()
    git_blob_sha1 = _new_git_blob_digest(metadata.byte_count)
    byte_count = 0
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(partial, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
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
            local_sha256
            if metadata.etag_algorithm == "sha256"
            else git_blob_sha1.hexdigest()
        )
        if remote_identity != metadata.etag:
            raise MRL0801HfAcquisitionError("download bytes differ from remote content identity")
        os.replace(partial, target)
        return HfAcquiredFileIdentity(
            path=metadata.path,
            byte_count=byte_count,
            remote_etag=metadata.etag,
            remote_etag_algorithm=metadata.etag_algorithm,
            local_sha256=local_sha256,
        )
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def _rollback_created_files(
    *,
    root: Path,
    acquired: tuple[HfAcquiredFileIdentity, ...],
) -> None:
    for item in reversed(acquired):
        relative = _validate_relative_path(item.path)
        target = root.joinpath(*relative.parts)
        if target.exists() or target.is_symlink():
            target.unlink(missing_ok=True)
    for path in root.rglob("*.mrl-0801-partial"):
        if path.is_symlink() or path.is_file():
            path.unlink(missing_ok=True)
