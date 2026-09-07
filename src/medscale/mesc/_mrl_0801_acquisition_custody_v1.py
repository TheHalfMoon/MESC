"""MRL-0801 bounded acquisition authorization and local custody receipts.

This module validates one exact Founder/operator acquisition/custody authorization
for the frozen Experiment-0 candidate set and defines a deterministic local-only
custody receipt. It performs no network access, model/tokenizer loading, inference,
GPU work, or training.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

from medscale.mesc._canonical_json_v1 import (
    CanonicalContractError,
    canonical_json_bytes,
)
from medscale.mesc._training_hf_safetensors_identity_v1 import (
    HfArtifactFileIdentity,
    HfArtifactFileKind,
    HfSafeTensorsArtifactIdentity,
    HfWeightLayout,
    TrainingModelArtifactIdentityError,
    identify_hf_safetensors_artifact,
)

_SCHEMA_VERSION: Final = "MESC-MRL-0801-ACQUISITION-CUSTODY-AUTHORIZATION-V1"
_AUTHORIZATION_ID: Final = "MESC-MRL-0801-ACQUISITION-CUSTODY-20260907-V1"
_SCOPE: Final = "MRL-0801_ACQUISITION_CUSTODY_ONLY"
_CUSTODY_SCHEMA_VERSION: Final = "MESC-MRL-0801-ASSET-CUSTODY-RECEIPT-V1"
_CUSTODY_VERIFICATION_METHOD: Final = "MESC_HF_SAFETENSORS_FULL_LOCAL_BYTE_VERIFICATION_V1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_MIN_EXTRA_FREE_BYTES: Final = 10 * 1024 * 1024 * 1024
_MIN_EXTRA_FREE_BASIS_POINTS: Final = 1000

_QWEN_MODEL_ID: Final = "Qwen/Qwen3.8-27B"
_QWEN_REVISION: Final = "1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0"
_QWEN_ROLE: Final = "PREFERRED_FOUNDATION_CANDIDATE"
_QWEN_FILES: Final = (
    "model.safetensors.index.json",
    "model-00001-of-00018.safetensors",
    "model-00002-of-00018.safetensors",
    "model-00003-of-00018.safetensors",
    "model-00004-of-00018.safetensors",
    "model-00005-of-00018.safetensors",
    "model-00006-of-00018.safetensors",
    "model-00007-of-00018.safetensors",
    "model-00008-of-00018.safetensors",
    "model-00009-of-00018.safetensors",
    "model-00010-of-00018.safetensors",
    "model-00011-of-00018.safetensors",
    "model-00012-of-00018.safetensors",
    "model-00013-of-00018.safetensors",
    "model-00014-of-00018.safetensors",
    "model-00015-of-00018.safetensors",
    "model-00016-of-00018.safetensors",
    "model-00017-of-00018.safetensors",
    "model-00018-of-00018.safetensors",
)
_GEMMA_MODEL_ID: Final = "google/gemma-4-31B-it"
_GEMMA_REVISION: Final = "842da3794eaa0b77d5f08bae87a17459d91ff475"
_GEMMA_ROLE: Final = "PRIMARY_CHALLENGER"
_GEMMA_FILES: Final = (
    "model.safetensors.index.json",
    "model-00001-of-00002.safetensors",
    "model-00002-of-00002.safetensors",
)
_ROSTER_PATH: Final = "specs/mesc-experiment-0/candidate-roster-v1.json"
_ROSTER_SHA256: Final = "2968f2c71fd0de4a9ef9b5f6e5d4d58d75ce0f2cf5af8a56840031d85f694489"
_AUTHORIZED_BASE_SHA: Final = "07b98baded530b7914dc0d1d89534cfcf6ee568a"
_AUTHORIZED_BASE_TREE: Final = "339125e96fa38c2cdab4b2f93c0a634f333f2587"
_POST_MERGE_CI_RUN: Final = 34139543250
_ISSUE_NUMBER: Final = 387


class MRL0801AcquisitionCustodyError(ValueError):
    """Raised when acquisition authorization or custody evidence fails closed."""


@dataclass(frozen=True, slots=True)
class AuthorizedModelAcquisition:
    """One exact authorized model/revision and weight-file allowlist."""

    model_id: str
    revision: str
    role: str
    allowed_files: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MRL0801AcquisitionAuthorization:
    """Validated exact canonical acquisition/custody authorization bytes."""

    canonical_bytes: bytes = field(repr=False)
    authorization_sha256: str = field(init=False)
    candidates: tuple[AuthorizedModelAcquisition, ...] = field(init=False)

    def __post_init__(self) -> None:
        _parse_canonical_object(
            self.canonical_bytes,
            label="MRL-0801 acquisition authorization",
        )
        if self.canonical_bytes != canonical_mrl_0801_acquisition_authorization_bytes():
            raise MRL0801AcquisitionCustodyError(
                "MRL-0801 acquisition authorization does not match the exact authorized scope"
            )
        object.__setattr__(
            self,
            "authorization_sha256",
            hashlib.sha256(self.canonical_bytes).hexdigest(),
        )
        object.__setattr__(self, "candidates", _authorized_candidates())

    def require_candidate(
        self,
        *,
        model_id: str,
        revision: str,
    ) -> AuthorizedModelAcquisition:
        """Return the exact authorized candidate or fail closed."""
        for candidate in self.candidates:
            if candidate.model_id == model_id and candidate.revision == revision:
                return candidate
        raise MRL0801AcquisitionCustodyError(
            "model_id/revision is outside the MRL-0801 acquisition authorization"
        )


@dataclass(frozen=True, slots=True)
class MRL0801AssetCustodyReceipt:
    """Deterministic semantic receipt for one successful full local byte verification."""

    canonical_bytes: bytes = field(repr=False)
    asset_custody_sha256: str = field(init=False)
    model_id: str = field(init=False)
    revision: str = field(init=False)
    access_authorization_sha256: str = field(init=False)
    artifact_identity_sha256: str = field(init=False)
    weights_sha256: str = field(init=False)
    files: tuple[HfArtifactFileIdentity, ...] = field(init=False)

    def __post_init__(self) -> None:
        document = _parse_canonical_object(
            self.canonical_bytes,
            label="MRL-0801 asset custody receipt",
        )
        _validate_exact_keys(
            document,
            {
                "access_authorization_sha256",
                "artifact_identity_sha256",
                "asset_present",
                "candidate_roster_sha256",
                "credentials_included",
                "files",
                "layout",
                "local_only",
                "model_id",
                "network_accessed",
                "path_included",
                "remote_code_allowed",
                "revision",
                "schema_version",
                "total_byte_count",
                "verification_method",
                "weights_sha256",
            },
            label="MRL-0801 asset custody receipt",
        )
        if document["schema_version"] != _CUSTODY_SCHEMA_VERSION:
            raise MRL0801AcquisitionCustodyError("custody receipt schema_version is invalid")
        if document["verification_method"] != _CUSTODY_VERIFICATION_METHOD:
            raise MRL0801AcquisitionCustodyError("custody verification method is invalid")
        if document["asset_present"] is not True:
            raise MRL0801AcquisitionCustodyError("custody receipt requires asset_present=true")
        if document["local_only"] is not True:
            raise MRL0801AcquisitionCustodyError("custody receipt requires local_only=true")
        if document["network_accessed"] is not False:
            raise MRL0801AcquisitionCustodyError("custody generation must be network-free")
        if document["remote_code_allowed"] is not False:
            raise MRL0801AcquisitionCustodyError("custody receipt must prohibit remote code")
        if document["path_included"] is not False:
            raise MRL0801AcquisitionCustodyError("custody receipt must not contain local paths")
        if document["credentials_included"] is not False:
            raise MRL0801AcquisitionCustodyError("custody receipt must not contain credentials")

        model_id = _require_text(document["model_id"], field_name="model_id")
        revision = _require_git_sha(document["revision"], field_name="revision")
        roster_sha256 = _require_sha256(
            document["candidate_roster_sha256"],
            field_name="candidate_roster_sha256",
        )
        if roster_sha256 != _ROSTER_SHA256:
            raise MRL0801AcquisitionCustodyError(
                "custody receipt candidate roster digest is not canonical"
            )
        access_sha256 = _require_sha256(
            document["access_authorization_sha256"],
            field_name="access_authorization_sha256",
        )
        weights_sha256 = _require_sha256(
            document["weights_sha256"],
            field_name="weights_sha256",
        )
        artifact_sha256 = _require_sha256(
            document["artifact_identity_sha256"],
            field_name="artifact_identity_sha256",
        )
        layout = _require_layout(document["layout"])
        files = _parse_artifact_files(document["files"])
        total_byte_count = _require_positive_int(
            document["total_byte_count"],
            field_name="total_byte_count",
        )
        if total_byte_count != sum(item.byte_count for item in files):
            raise MRL0801AcquisitionCustodyError(
                "custody total_byte_count does not match the exact file manifest"
            )

        try:
            identity = HfSafeTensorsArtifactIdentity(
                model_id=model_id,
                revision=revision,
                layout=layout,
                files=files,
            )
        except TrainingModelArtifactIdentityError as exc:
            raise MRL0801AcquisitionCustodyError(
                "custody receipt SafeTensors identity is invalid"
            ) from exc
        if identity.weights_sha256 != weights_sha256:
            raise MRL0801AcquisitionCustodyError(
                "custody receipt weights_sha256 does not match the exact file manifest"
            )
        if identity.verifier_receipt_sha256 != artifact_sha256:
            raise MRL0801AcquisitionCustodyError(
                "custody artifact_identity_sha256 does not match the canonical verifier receipt"
            )

        object.__setattr__(
            self,
            "asset_custody_sha256",
            hashlib.sha256(self.canonical_bytes).hexdigest(),
        )
        object.__setattr__(self, "model_id", model_id)
        object.__setattr__(self, "revision", revision)
        object.__setattr__(self, "access_authorization_sha256", access_sha256)
        object.__setattr__(self, "artifact_identity_sha256", artifact_sha256)
        object.__setattr__(self, "weights_sha256", weights_sha256)
        object.__setattr__(self, "files", files)


def canonical_mrl_0801_acquisition_authorization_bytes() -> bytes:
    """Return the exact Founder/operator authorization bytes for Issue #387."""
    return canonical_json_bytes(_expected_authorization_document())


def parse_mrl_0801_acquisition_authorization(
    raw: bytes,
) -> MRL0801AcquisitionAuthorization:
    """Parse the exact canonical MRL-0801 acquisition/custody authorization."""
    return MRL0801AcquisitionAuthorization(raw)


def required_mrl_0801_free_bytes(exact_allowlist_bytes: int) -> int:
    """Return the fail-closed free-space threshold for one planned acquisition."""
    exact_bytes = _require_positive_int(
        exact_allowlist_bytes,
        field_name="exact_allowlist_bytes",
    )
    ratio_margin = (exact_bytes * _MIN_EXTRA_FREE_BASIS_POINTS + 9999) // 10000
    return exact_bytes + max(_MIN_EXTRA_FREE_BYTES, ratio_margin)


def require_mrl_0801_storage_capacity(
    *,
    exact_allowlist_bytes: int,
    available_bytes: int,
) -> int:
    """Require enough free bytes before any authorized acquisition starts."""
    available = _require_nonnegative_int(
        available_bytes,
        field_name="available_bytes",
    )
    required = required_mrl_0801_free_bytes(exact_allowlist_bytes)
    if available < required:
        raise MRL0801AcquisitionCustodyError(
            "available storage is below the authorized MRL-0801 preflight threshold"
        )
    return required


def generate_mrl_0801_asset_custody_receipt(
    *,
    model_root: Path,
    authorization: MRL0801AcquisitionAuthorization,
    model_id: str,
    revision: str,
) -> MRL0801AssetCustodyReceipt:
    """Hash every authorized local weight file and emit one path-free custody receipt."""
    if type(authorization) is not MRL0801AcquisitionAuthorization:
        raise MRL0801AcquisitionCustodyError(
            "authorization must be an exact MRL0801AcquisitionAuthorization"
        )
    candidate = authorization.require_candidate(model_id=model_id, revision=revision)
    try:
        identity = identify_hf_safetensors_artifact(
            model_root=model_root,
            model_id=model_id,
            revision=revision,
        )
    except TrainingModelArtifactIdentityError as exc:
        raise MRL0801AcquisitionCustodyError(
            "authorized local SafeTensors custody verification failed"
        ) from exc

    observed_files = tuple(item.path for item in identity.files)
    if observed_files != candidate.allowed_files:
        raise MRL0801AcquisitionCustodyError(
            "local SafeTensors manifest does not match the exact authorized allowlist"
        )

    payload: dict[str, object] = {
        "access_authorization_sha256": authorization.authorization_sha256,
        "artifact_identity_sha256": identity.verifier_receipt_sha256,
        "asset_present": True,
        "candidate_roster_sha256": _ROSTER_SHA256,
        "credentials_included": False,
        "files": [item.to_dict() for item in identity.files],
        "layout": identity.layout,
        "local_only": True,
        "model_id": identity.model_id,
        "network_accessed": False,
        "path_included": False,
        "remote_code_allowed": False,
        "revision": identity.revision,
        "schema_version": _CUSTODY_SCHEMA_VERSION,
        "total_byte_count": sum(item.byte_count for item in identity.files),
        "verification_method": _CUSTODY_VERIFICATION_METHOD,
        "weights_sha256": identity.weights_sha256,
    }
    receipt = MRL0801AssetCustodyReceipt(canonical_json_bytes(payload))
    _validate_mrl_0801_custody_receipt_against_identity(
        receipt=receipt,
        authorization=authorization,
        identity=identity,
    )
    return receipt


def validate_mrl_0801_custody_receipt_authorization(
    *,
    receipt: MRL0801AssetCustodyReceipt,
    authorization: MRL0801AcquisitionAuthorization,
    model_root: Path,
) -> None:
    """Reverify local bytes and bind a parsed custody receipt to current authorization."""
    if type(receipt) is not MRL0801AssetCustodyReceipt:
        raise MRL0801AcquisitionCustodyError("receipt must be an exact MRL0801AssetCustodyReceipt")
    if type(authorization) is not MRL0801AcquisitionAuthorization:
        raise MRL0801AcquisitionCustodyError(
            "authorization must be an exact MRL0801AcquisitionAuthorization"
        )
    authorization.require_candidate(
        model_id=receipt.model_id,
        revision=receipt.revision,
    )
    try:
        identity = identify_hf_safetensors_artifact(
            model_root=model_root,
            model_id=receipt.model_id,
            revision=receipt.revision,
        )
    except TrainingModelArtifactIdentityError as exc:
        raise MRL0801AcquisitionCustodyError(
            "custody receipt local SafeTensors reverification failed"
        ) from exc
    _validate_mrl_0801_custody_receipt_against_identity(
        receipt=receipt,
        authorization=authorization,
        identity=identity,
    )


def _validate_mrl_0801_custody_receipt_against_identity(
    *,
    receipt: MRL0801AssetCustodyReceipt,
    authorization: MRL0801AcquisitionAuthorization,
    identity: HfSafeTensorsArtifactIdentity,
) -> None:
    """Require receipt, authorization, and one verified local identity to match exactly."""
    candidate = authorization.require_candidate(
        model_id=receipt.model_id,
        revision=receipt.revision,
    )
    if identity.model_id != receipt.model_id or identity.revision != receipt.revision:
        raise MRL0801AcquisitionCustodyError(
            "verified local identity does not match the custody receipt subject"
        )
    if receipt.access_authorization_sha256 != authorization.authorization_sha256:
        raise MRL0801AcquisitionCustodyError(
            "custody receipt is bound to a different acquisition authorization"
        )
    if tuple(item.path for item in receipt.files) != candidate.allowed_files:
        raise MRL0801AcquisitionCustodyError(
            "custody receipt file manifest is outside the exact authorized allowlist"
        )
    if identity.files != receipt.files:
        raise MRL0801AcquisitionCustodyError(
            "custody receipt file identities do not match the current local bytes"
        )
    if identity.weights_sha256 != receipt.weights_sha256:
        raise MRL0801AcquisitionCustodyError(
            "custody receipt weights_sha256 does not match the current local bytes"
        )
    if identity.verifier_receipt_sha256 != receipt.artifact_identity_sha256:
        raise MRL0801AcquisitionCustodyError(
            "custody receipt artifact identity does not match the current local bytes"
        )


def _authorized_candidates() -> tuple[AuthorizedModelAcquisition, ...]:
    return (
        AuthorizedModelAcquisition(
            model_id=_QWEN_MODEL_ID,
            revision=_QWEN_REVISION,
            role=_QWEN_ROLE,
            allowed_files=_QWEN_FILES,
        ),
        AuthorizedModelAcquisition(
            model_id=_GEMMA_MODEL_ID,
            revision=_GEMMA_REVISION,
            role=_GEMMA_ROLE,
            allowed_files=_GEMMA_FILES,
        ),
    )


def _expected_authorization_document() -> dict[str, object]:
    return {
        "acquisition_policy": {
            "allowlist_only": True,
            "credential_use_authorized": False,
            "experiment_0_execution_authorized": False,
            "gpu_execution_authorized": False,
            "inference_authorized": False,
            "model_loading_authorized": False,
            "mrl_0801_population_authorized": False,
            "production_trust_registry_mutation_authorized": False,
            "raw_snapshots_outside_git_required": True,
            "remote_code_authorized": False,
            "terms_acceptance_authorized": False,
            "tokenizer_loading_authorized": False,
            "tracked_repository_paths_prohibited": True,
            "training_authorized": False,
            "weight_mutation_authorized": False,
        },
        "authorization_id": _AUTHORIZATION_ID,
        "authorization_state": "AUTHORIZED",
        "authorized_base": {
            "main_sha": _AUTHORIZED_BASE_SHA,
            "main_tree": _AUTHORIZED_BASE_TREE,
            "post_merge_ci_run": _POST_MERGE_CI_RUN,
            "post_merge_ci_success": True,
        },
        "candidate_roster": {
            "path": _ROSTER_PATH,
            "sha256": _ROSTER_SHA256,
        },
        "candidates": [
            {
                "allowed_files": list(_QWEN_FILES),
                "model_id": _QWEN_MODEL_ID,
                "revision": _QWEN_REVISION,
                "role": _QWEN_ROLE,
            },
            {
                "allowed_files": list(_GEMMA_FILES),
                "model_id": _GEMMA_MODEL_ID,
                "revision": _GEMMA_REVISION,
                "role": _GEMMA_ROLE,
            },
        ],
        "issue_number": _ISSUE_NUMBER,
        "schema_version": _SCHEMA_VERSION,
        "scope": _SCOPE,
        "storage_capacity_preflight": {
            "authoritative_exact_file_sizes_required": True,
            "minimum_extra_free_basis_points": _MIN_EXTRA_FREE_BASIS_POINTS,
            "minimum_extra_free_bytes": _MIN_EXTRA_FREE_BYTES,
            "preflight_required": True,
            "rule": "AVAILABLE_BYTES_GTE_ALLOWLIST_BYTES_PLUS_MAX_MARGIN",
        },
    }


def _parse_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise MRL0801AcquisitionCustodyError(f"{label} must be non-empty exact bytes")
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonstandard_json_constant,
        )
        if type(parsed) is not dict:
            raise MRL0801AcquisitionCustodyError(f"{label} must be a JSON object")
        document = cast(dict[str, object], parsed)
        canonical = canonical_json_bytes(document)
    except MRL0801AcquisitionCustodyError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError, CanonicalContractError) as exc:
        raise MRL0801AcquisitionCustodyError(f"{label} must be valid canonical UTF-8 JSON") from exc
    if canonical != raw:
        raise MRL0801AcquisitionCustodyError(f"{label} bytes are not canonical JSON")
    return document


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise MRL0801AcquisitionCustodyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_nonstandard_json_constant(value: str) -> object:
    raise MRL0801AcquisitionCustodyError(f"non-standard JSON constant is prohibited: {value}")


def _validate_exact_keys(
    value: dict[str, object],
    expected: set[str],
    *,
    label: str,
) -> None:
    if set(value) != expected:
        raise MRL0801AcquisitionCustodyError(f"{label} has an invalid field set")


def _require_text(value: object, *, field_name: str) -> str:
    if type(value) is not str or not value:
        raise MRL0801AcquisitionCustodyError(f"{field_name} must be a non-empty string")
    return value


def _require_sha256(value: object, *, field_name: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise MRL0801AcquisitionCustodyError(
            f"{field_name} must be exactly 64 lowercase hex characters"
        )
    return value


def _require_git_sha(value: object, *, field_name: str) -> str:
    if type(value) is not str or _GIT_SHA.fullmatch(value) is None:
        raise MRL0801AcquisitionCustodyError(
            f"{field_name} must be exactly 40 lowercase hex characters"
        )
    return value


def _require_positive_int(value: object, *, field_name: str) -> int:
    if type(value) is not int or value <= 0:
        raise MRL0801AcquisitionCustodyError(f"{field_name} must be a positive int")
    return value


def _require_nonnegative_int(value: object, *, field_name: str) -> int:
    if type(value) is not int or value < 0:
        raise MRL0801AcquisitionCustodyError(f"{field_name} must be a non-negative int")
    return value


def _require_layout(value: object) -> HfWeightLayout:
    if value not in ("single", "sharded"):
        raise MRL0801AcquisitionCustodyError("custody receipt layout is invalid")
    return value


def _require_file_kind(value: object) -> HfArtifactFileKind:
    if value not in ("index", "weight"):
        raise MRL0801AcquisitionCustodyError("custody receipt file kind is invalid")
    return value


def _parse_artifact_files(value: object) -> tuple[HfArtifactFileIdentity, ...]:
    if type(value) is not list or not value:
        raise MRL0801AcquisitionCustodyError("custody receipt files must be a non-empty array")
    files: list[HfArtifactFileIdentity] = []
    for raw_item in value:
        if type(raw_item) is not dict:
            raise MRL0801AcquisitionCustodyError("custody receipt file entry must be an object")
        item = cast(dict[str, object], raw_item)
        _validate_exact_keys(
            item,
            {"byte_count", "kind", "path", "sha256"},
            label="custody receipt file entry",
        )
        try:
            files.append(
                HfArtifactFileIdentity(
                    path=_require_text(item["path"], field_name="file path"),
                    kind=_require_file_kind(item["kind"]),
                    sha256=_require_sha256(item["sha256"], field_name="file sha256"),
                    byte_count=_require_positive_int(
                        item["byte_count"],
                        field_name="file byte_count",
                    ),
                )
            )
        except TrainingModelArtifactIdentityError as exc:
            raise MRL0801AcquisitionCustodyError(
                "custody receipt file identity is invalid"
            ) from exc
    return tuple(files)
