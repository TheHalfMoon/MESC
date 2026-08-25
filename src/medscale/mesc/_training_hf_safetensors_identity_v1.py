"""Canonical local Hugging Face SafeTensors model-artifact identity for MESC training.

This module defines the first repository-wide meaning of ``weights_sha256`` for
training-ready Hugging Face model assets. It performs local filesystem inspection
only: no Hub access, authentication, model loading, remote code, inference, GPU
work, or training.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, Literal

from medscale.mesc._training_launch_plan_v1 import TrainingRole, TrainingRunPlan
from medscale.mesc._training_local_asset_attestation_v1 import LocalModelAssetObservation
from medscale.reproducibility import content_hash

HfWeightLayout = Literal["single", "sharded"]
HfArtifactFileKind = Literal["index", "weight"]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_SHARD: Final = re.compile(
    r"^model-([0-9]{5})-of-([0-9]{5})\.safetensors$",
    flags=re.ASCII,
)
_IDENTITY_VERSION: Final = "MESC-HF-SAFETENSORS-WEIGHT-IDENTITY-V1"
_VERIFIER_ID: Final = "mesc-hf-safetensors-local-verifier"
_VERIFIER_VERSION: Final = "v1"
_SINGLE_WEIGHT: Final = "model.safetensors"
_INDEX: Final = "model.safetensors.index.json"
_UNSAFE_WEIGHT_SUFFIXES: Final = (".bin", ".pt", ".pth")
_CHUNK_SIZE: Final = 1024 * 1024
_MAX_INDEX_BYTES: Final = 16 * 1024 * 1024
_O_BINARY: Final = getattr(os, "O_BINARY", 0)
_O_NOFOLLOW: Final = getattr(os, "O_NOFOLLOW", 0)


class TrainingModelArtifactIdentityError(ValueError):
    """Raised when a local model artifact cannot satisfy the canonical V1 contract."""


@dataclass(frozen=True, slots=True)
class HfArtifactFileIdentity:
    """One canonical file entry participating in ``weights_sha256``."""

    path: str
    kind: HfArtifactFileKind
    sha256: str
    byte_count: int

    def __post_init__(self) -> None:
        _require_relative_basename(self.path, field="artifact file path")
        if self.kind not in ("index", "weight"):
            raise TrainingModelArtifactIdentityError("artifact file kind is invalid")
        _require_sha256(self.sha256, field="artifact file sha256")
        if type(self.byte_count) is not int or self.byte_count <= 0:
            raise TrainingModelArtifactIdentityError(
                "artifact file byte_count must be a positive int"
            )

    def to_dict(self) -> dict[str, object]:
        """Return the canonical file payload."""
        return {
            "byte_count": self.byte_count,
            "kind": self.kind,
            "path": self.path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class HfSafeTensorsArtifactIdentity:
    """Content-addressed identity of one already-local SafeTensors weight payload."""

    model_id: str
    revision: str
    layout: HfWeightLayout
    files: tuple[HfArtifactFileIdentity, ...]
    identity_version: str = _IDENTITY_VERSION

    def __post_init__(self) -> None:
        if self.identity_version != _IDENTITY_VERSION:
            raise TrainingModelArtifactIdentityError(
                f"identity_version must be exactly {_IDENTITY_VERSION}"
            )
        _require_text(self.model_id, field="model_id")
        if not isinstance(self.revision, str) or _GIT_SHA.fullmatch(self.revision) is None:
            raise TrainingModelArtifactIdentityError(
                "revision must be exactly 40 lowercase hex characters"
            )
        if self.layout not in ("single", "sharded"):
            raise TrainingModelArtifactIdentityError("layout must be single or sharded")
        if not isinstance(self.files, tuple) or not self.files:
            raise TrainingModelArtifactIdentityError("files must be a non-empty immutable tuple")
        if any(type(item) is not HfArtifactFileIdentity for item in self.files):
            raise TrainingModelArtifactIdentityError(
                "files must contain exact HfArtifactFileIdentity values"
            )
        paths = tuple(item.path for item in self.files)
        if len(set(paths)) != len(paths):
            raise TrainingModelArtifactIdentityError("artifact file paths must be unique")

        kinds = tuple(item.kind for item in self.files)
        if self.layout == "single":
            if paths != (_SINGLE_WEIGHT,) or kinds != ("weight",):
                raise TrainingModelArtifactIdentityError(
                    "single layout must contain only model.safetensors"
                )
            return

        if paths[0] != _INDEX or kinds[0] != "index":
            raise TrainingModelArtifactIdentityError(
                "sharded layout must begin with the canonical index"
            )
        if len(self.files) < 2 or any(kind != "weight" for kind in kinds[1:]):
            raise TrainingModelArtifactIdentityError(
                "sharded layout requires one or more weight shards"
            )
        if paths[1:] != tuple(sorted(paths[1:])):
            raise TrainingModelArtifactIdentityError(
                "sharded weight files must use canonical path ordering"
            )
        _require_complete_shard_sequence(paths[1:])

    @property
    def weights_sha256(self) -> str:
        """Return the canonical, root-independent V1 weight identity."""
        return content_hash(
            {
                "files": [item.to_dict() for item in self.files],
                "identity_version": self.identity_version,
                "layout": self.layout,
            }
        )

    @property
    def verifier_receipt_sha256(self) -> str:
        """Bind weight identity to the exact model id and immutable revision."""
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """Return the canonical model-artifact receipt payload."""
        return {
            "files": [item.to_dict() for item in self.files],
            "identity_version": self.identity_version,
            "layout": self.layout,
            "model_id": self.model_id,
            "revision": self.revision,
            "weights_sha256": self.weights_sha256,
        }


def identify_hf_safetensors_artifact(
    *,
    model_root: Path,
    model_id: str,
    revision: str,
) -> HfSafeTensorsArtifactIdentity:
    """Inspect an already-local root and derive the canonical V1 weight identity."""
    _require_text(model_id, field="model_id")
    if not isinstance(revision, str) or _GIT_SHA.fullmatch(revision) is None:
        raise TrainingModelArtifactIdentityError(
            "revision must be exactly 40 lowercase hex characters"
        )
    root = _require_model_root(model_root)
    _reject_unsafe_weight_files(root)

    single_path = root / _SINGLE_WEIGHT
    index_path = root / _INDEX
    single_exists = _lexists(single_path)
    index_exists = _lexists(index_path)

    if single_exists and index_exists:
        raise TrainingModelArtifactIdentityError(
            "model root is ambiguous: both single and sharded SafeTensors layouts exist"
        )
    if single_exists:
        extra = _root_safetensors_names(root) - {_SINGLE_WEIGHT}
        if extra:
            raise TrainingModelArtifactIdentityError(
                "single SafeTensors layout contains unexpected additional weight files"
            )
        file_identity = _hash_file_identity(
            single_path,
            relative_name=_SINGLE_WEIGHT,
            kind="weight",
        )
        return HfSafeTensorsArtifactIdentity(
            model_id=model_id,
            revision=revision,
            layout="single",
            files=(file_identity,),
        )
    if index_exists:
        index_raw, index_sha256, index_byte_count = _read_regular_file(
            index_path,
            max_bytes=_MAX_INDEX_BYTES,
        )
        shard_names = _parse_index(index_raw)
        unexpected = _root_safetensors_names(root) - set(shard_names)
        if unexpected:
            raise TrainingModelArtifactIdentityError(
                "sharded SafeTensors layout contains unreferenced weight files"
            )
        index_identity = HfArtifactFileIdentity(
            path=_INDEX,
            kind="index",
            sha256=index_sha256,
            byte_count=index_byte_count,
        )
        shard_identities = tuple(
            _hash_file_identity(
                root / shard_name,
                relative_name=shard_name,
                kind="weight",
            )
            for shard_name in shard_names
        )
        return HfSafeTensorsArtifactIdentity(
            model_id=model_id,
            revision=revision,
            layout="sharded",
            files=(index_identity, *shard_identities),
        )

    raise TrainingModelArtifactIdentityError(
        "model root does not contain a canonical SafeTensors weight layout"
    )


class HfSafeTensorsLocalModelVerifier:
    """Concrete local-only verifier compatible with the canonical attestation protocol."""

    def verify(
        self,
        *,
        role: TrainingRole,
        model_root: Path,
        run_plan: TrainingRunPlan,
    ) -> LocalModelAssetObservation:
        if type(run_plan) is not TrainingRunPlan:
            raise TrainingModelArtifactIdentityError(
                "run_plan must use the exact canonical TrainingRunPlan type"
            )
        if role not in ("compact", "reasoner") or run_plan.role != role:
            raise TrainingModelArtifactIdentityError(
                "role must match the exact selected training run"
            )

        identity = identify_hf_safetensors_artifact(
            model_root=model_root,
            model_id=run_plan.model_id,
            revision=run_plan.revision,
        )
        return LocalModelAssetObservation(
            role=role,
            model_id=identity.model_id,
            revision=identity.revision,
            weights_sha256=identity.weights_sha256,
            verifier_id=_VERIFIER_ID,
            verifier_version=_VERIFIER_VERSION,
            verifier_receipt_sha256=identity.verifier_receipt_sha256,
            network_accessed=False,
            remote_code_allowed=False,
            gated_terms_accepted=False,
        )


def _parse_index(raw: bytes) -> tuple[str, ...]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TrainingModelArtifactIdentityError(
            "SafeTensors index must be valid UTF-8 JSON"
        ) from exc
    if not isinstance(payload, dict) or set(payload) - {"metadata", "weight_map"}:
        raise TrainingModelArtifactIdentityError(
            "SafeTensors index must contain only metadata and weight_map"
        )
    if "metadata" in payload and not isinstance(payload["metadata"], dict):
        raise TrainingModelArtifactIdentityError("SafeTensors index metadata must be an object")
    weight_map = payload.get("weight_map")
    if not isinstance(weight_map, dict) or not weight_map:
        raise TrainingModelArtifactIdentityError(
            "SafeTensors index weight_map must be a non-empty object"
        )

    shard_names: set[str] = set()
    for tensor_name, shard_name in weight_map.items():
        if not isinstance(tensor_name, str) or not tensor_name.strip() or "\x00" in tensor_name:
            raise TrainingModelArtifactIdentityError(
                "SafeTensors weight_map keys must be non-empty NUL-free strings"
            )
        if not isinstance(shard_name, str):
            raise TrainingModelArtifactIdentityError(
                "SafeTensors weight_map values must be shard filenames"
            )
        _require_relative_basename(shard_name, field="SafeTensors shard filename")
        if _SHARD.fullmatch(shard_name) is None:
            raise TrainingModelArtifactIdentityError(
                "SafeTensors shard filenames must use "
                "model-NNNNN-of-NNNNN.safetensors"
            )
        shard_names.add(shard_name)

    ordered = tuple(sorted(shard_names))
    _require_complete_shard_sequence(ordered)
    return ordered


def _require_complete_shard_sequence(names: tuple[str, ...]) -> None:
    if not names:
        raise TrainingModelArtifactIdentityError("sharded layout requires at least one shard")
    parsed: list[tuple[int, int]] = []
    for name in names:
        match = _SHARD.fullmatch(name)
        if match is None:
            raise TrainingModelArtifactIdentityError("invalid canonical shard filename")
        parsed.append((int(match.group(1)), int(match.group(2))))
    totals = {total for _, total in parsed}
    if len(totals) != 1:
        raise TrainingModelArtifactIdentityError("all shards must declare the same shard count")
    total = next(iter(totals))
    expected = tuple(range(1, total + 1))
    if total != len(parsed) or tuple(index for index, _ in parsed) != expected:
        raise TrainingModelArtifactIdentityError(
            "SafeTensors shards must form one complete contiguous sequence"
        )


def _require_model_root(model_root: Path) -> Path:
    if not isinstance(model_root, Path):
        raise TrainingModelArtifactIdentityError("model_root must be a pathlib.Path")
    if model_root.is_symlink():
        raise TrainingModelArtifactIdentityError("model_root must not be a symlink")
    try:
        if not model_root.is_dir():
            raise TrainingModelArtifactIdentityError("model_root must be an existing directory")
    except OSError as exc:
        raise TrainingModelArtifactIdentityError("model_root could not be inspected") from exc
    return model_root


def _reject_unsafe_weight_files(root: Path) -> None:
    try:
        names = tuple(entry.name for entry in os.scandir(root))
    except OSError as exc:
        raise TrainingModelArtifactIdentityError("model_root could not be enumerated") from exc
    for name in names:
        if name.lower().endswith(_UNSAFE_WEIGHT_SUFFIXES):
            raise TrainingModelArtifactIdentityError(
                "pickle-compatible weight files are forbidden by the "
                "V1 SafeTensors contract"
            )


def _root_safetensors_names(root: Path) -> set[str]:
    try:
        return {entry.name for entry in os.scandir(root) if entry.name.endswith(".safetensors")}
    except OSError as exc:
        raise TrainingModelArtifactIdentityError("model_root could not be enumerated") from exc


def _hash_file_identity(
    path: Path,
    *,
    relative_name: str,
    kind: HfArtifactFileKind,
) -> HfArtifactFileIdentity:
    _, digest, byte_count = _read_regular_file(path)
    return HfArtifactFileIdentity(
        path=relative_name,
        kind=kind,
        sha256=digest,
        byte_count=byte_count,
    )


def _read_regular_file(
    path: Path,
    *,
    max_bytes: int | None = None,
) -> tuple[bytes, str, int]:
    try:
        before = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise TrainingModelArtifactIdentityError(
            f"artifact file could not be statted: {path.name}"
        ) from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise TrainingModelArtifactIdentityError(
            f"artifact file must be a non-symlink regular file: {path.name}"
        )
    if before.st_size <= 0:
        raise TrainingModelArtifactIdentityError(
            f"artifact file must be non-empty: {path.name}"
        )
    if max_bytes is not None and before.st_size > max_bytes:
        raise TrainingModelArtifactIdentityError(
            f"artifact file exceeds the bounded read limit: {path.name}"
        )

    flags = os.O_RDONLY | _O_BINARY | _O_NOFOLLOW
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise TrainingModelArtifactIdentityError(
            f"artifact file could not be opened safely: {path.name}"
        ) from exc

    digest = hashlib.sha256()
    chunks: list[bytes] = []
    byte_count = 0
    try:
        opened = os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode):
            raise TrainingModelArtifactIdentityError(
                f"opened artifact is not a regular file: {path.name}"
            )
        while True:
            chunk = os.read(fd, _CHUNK_SIZE)
            if not chunk:
                break
            byte_count += len(chunk)
            if max_bytes is not None and byte_count > max_bytes:
                raise TrainingModelArtifactIdentityError(
                    f"artifact file exceeds the bounded read limit: {path.name}"
                )
            digest.update(chunk)
            if max_bytes is not None:
                chunks.append(chunk)
        finished = os.fstat(fd)
    finally:
        os.close(fd)

    try:
        after = path.stat(follow_symlinks=False)
    except OSError as exc:
        raise TrainingModelArtifactIdentityError(
            f"artifact file changed during verification: {path.name}"
        ) from exc

    expected_identity = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    )
    opened_identity = (
        opened.st_dev,
        opened.st_ino,
        opened.st_size,
        opened.st_mtime_ns,
    )
    finished_identity = (
        finished.st_dev,
        finished.st_ino,
        finished.st_size,
        finished.st_mtime_ns,
    )
    after_identity = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    )
    if not (expected_identity == opened_identity == finished_identity == after_identity):
        raise TrainingModelArtifactIdentityError(
            f"artifact file changed during verification: {path.name}"
        )
    if byte_count != before.st_size:
        raise TrainingModelArtifactIdentityError(
            f"artifact byte count changed during verification: {path.name}"
        )
    return b"".join(chunks), digest.hexdigest(), byte_count


def _lexists(path: Path) -> bool:
    try:
        os.lstat(path)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise TrainingModelArtifactIdentityError(
            f"artifact path could not be inspected: {path.name}"
        ) from exc
    return True


def _require_relative_basename(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise TrainingModelArtifactIdentityError(f"{field} must be one non-empty POSIX basename")
    path = PurePosixPath(value)
    if path.is_absolute() or len(path.parts) != 1 or str(path) != value or value in (".", ".."):
        raise TrainingModelArtifactIdentityError(f"{field} must be one canonical POSIX basename")
    return value


def _require_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise TrainingModelArtifactIdentityError(
            f"{field} must be exactly 64 lowercase hex characters"
        )
    return value


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise TrainingModelArtifactIdentityError(f"{field} must be non-empty NUL-free text")
    return value
