"""Fixture-only activation runtime-binding and identity validation primitives.

This module validates synthetic canonical bytes for the MESC Backbone Tournament
activation contract. It performs no filesystem traversal, GitHub access, provider
access, model access, network I/O, credential work, or execution.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Final

DECISION_ID: Final = "FD-MESC-BT-EXEC-1-ACTIVATION-1"
RECEIPT_VERSION: Final = "MESC-BT-EXEC-1-ACTIVATION-RECEIPT-V1"
GPU_MODEL_H100: Final = "NVIDIA H100 80GB HBM3"
PROVIDER_CLASS: Final = "RunPod Secure Cloud"
EXTERNAL_RUNTIME_PARENT_PATH: Final = "/workspace/mesc-bt-exec-1"
REPOSITORY_RESULT_PARENT: Final = "specs/mesc-backbone-tournament/execution-result-1"

_SHA40_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_OCI_DIGEST_RE: Final = re.compile(r"^sha256:[0-9a-f]{64}$")
_CHECKOUT_ROOT_RE: Final = re.compile(
    r"^/[a-z0-9][a-z0-9._-]{0,127}(?:/[a-z0-9][a-z0-9._-]{0,127})*$"
)

_RUNTIME_KEYS: Final = (
    "acceleration_runtime_identities",
    "base_container_oci_digest",
    "cuda_runtime_version",
    "dependency_lock_sha256",
    "external_runtime_parent_device_id",
    "external_runtime_parent_inode",
    "external_runtime_parent_mount_id",
    "external_runtime_parent_path",
    "gpu_count",
    "gpu_model",
    "gpu_uuid",
    "nvidia_driver_version",
    "provider_class",
    "provider_instance_or_pod_id",
    "provider_region",
    "python_version",
    "pytorch_version",
    "repository_checkout_root_device_id",
    "repository_checkout_root_inode",
    "repository_checkout_root_mount_id",
    "repository_checkout_root_path",
    "repository_checkout_sha",
    "repository_checkout_tree",
    "repository_result_parent_device_id",
    "repository_result_parent_inode",
    "repository_result_parent_mount_id",
    "sequential_single_gpu_execution",
    "transformers_identity",
)

_IDENTITY_KEYS: Final = (
    "apertus_access_attestation_sha256",
    "authorization_merge_sha",
    "authorization_merge_tree",
    "decision_id",
    "execution_code_sha",
    "execution_code_tree",
    "executor_allowlist_sha256",
    "founder_attestation_comment_id",
    "gated_access_decision_merge_sha",
    "gated_access_founder_attestation_comment_id",
    "medgemma_access_attestation_sha256",
    "phi_remote_code_manifest_sha256",
    "phi_remote_code_security_review_sha256",
    "phi_sandbox_qualification_sha256",
    "receipt_version",
    "runtime_binding_sha256",
    "telemetry_qualification_sha256",
)


class FixtureActivationError(ValueError):
    """Base class for fixture activation validation failures."""


class FixtureActivationBlockedError(FixtureActivationError):
    """A fail-closed condition that blocks fixture qualification."""


@dataclass(frozen=True, slots=True)
class IndependentActivationBindings:
    """Values independently recomputed outside this pure fixture primitive."""

    authorization_merge_sha: str
    authorization_merge_tree: str
    execution_code_sha: str
    execution_code_tree: str
    executor_allowlist_sha256: str
    founder_attestation_comment_id: int
    gated_access_decision_merge_sha: str
    gated_access_founder_attestation_comment_id: int
    apertus_access_attestation_sha256: str
    medgemma_access_attestation_sha256: str
    phi_remote_code_manifest_sha256: str
    phi_remote_code_security_review_sha256: str
    phi_sandbox_qualification_sha256: str
    telemetry_qualification_sha256: str
    repository_checkout_sha: str
    repository_checkout_tree: str


@dataclass(frozen=True, slots=True)
class FixtureActivationIdentityResult:
    """Deterministic result after exact fixture binding validation."""

    runtime_binding_sha256: str
    activation_id: str
    external_runtime_root: str
    repository_result_root: str


def qualify_fixture_activation_identity(
    runtime_binding_bytes: bytes,
    identity_preimage_bytes: bytes,
    independent: IndependentActivationBindings,
) -> FixtureActivationIdentityResult:
    """Validate exact canonical bytes and derive a fixture activation identity."""
    runtime = _parse_runtime_binding(runtime_binding_bytes)
    _validate_independent_bindings(independent)
    if runtime["repository_checkout_sha"] != independent.repository_checkout_sha:
        raise FixtureActivationBlockedError("repository checkout SHA binding mismatch")
    if runtime["repository_checkout_tree"] != independent.repository_checkout_tree:
        raise FixtureActivationBlockedError("repository checkout tree binding mismatch")

    runtime_binding_sha256 = hashlib.sha256(runtime_binding_bytes).hexdigest()
    identity = _parse_identity_preimage(identity_preimage_bytes)

    expected = {
        "apertus_access_attestation_sha256": (independent.apertus_access_attestation_sha256),
        "authorization_merge_sha": independent.authorization_merge_sha,
        "authorization_merge_tree": independent.authorization_merge_tree,
        "execution_code_sha": independent.execution_code_sha,
        "execution_code_tree": independent.execution_code_tree,
        "executor_allowlist_sha256": independent.executor_allowlist_sha256,
        "founder_attestation_comment_id": independent.founder_attestation_comment_id,
        "gated_access_decision_merge_sha": independent.gated_access_decision_merge_sha,
        "gated_access_founder_attestation_comment_id": (
            independent.gated_access_founder_attestation_comment_id
        ),
        "medgemma_access_attestation_sha256": (independent.medgemma_access_attestation_sha256),
        "phi_remote_code_manifest_sha256": independent.phi_remote_code_manifest_sha256,
        "phi_remote_code_security_review_sha256": (
            independent.phi_remote_code_security_review_sha256
        ),
        "phi_sandbox_qualification_sha256": (independent.phi_sandbox_qualification_sha256),
        "runtime_binding_sha256": runtime_binding_sha256,
        "telemetry_qualification_sha256": independent.telemetry_qualification_sha256,
    }
    for key, value in expected.items():
        if identity[key] != value:
            raise FixtureActivationBlockedError(f"identity binding mismatch: {key}")

    activation_id = hashlib.sha256(identity_preimage_bytes).hexdigest()
    if _SHA256_RE.fullmatch(activation_id) is None:
        raise FixtureActivationBlockedError("derived activation ID is invalid")

    return FixtureActivationIdentityResult(
        runtime_binding_sha256=runtime_binding_sha256,
        activation_id=activation_id,
        external_runtime_root=f"{EXTERNAL_RUNTIME_PARENT_PATH}/{activation_id}/",
        repository_result_root=f"{REPOSITORY_RESULT_PARENT}/{activation_id}/",
    )


def _parse_runtime_binding(raw: bytes) -> dict[str, object]:
    value = _parse_canonical_object(raw, field="RUNTIME_BINDING")
    if tuple(value) != _RUNTIME_KEYS:
        raise FixtureActivationBlockedError("RUNTIME_BINDING key set/order mismatch")

    identities = value["acceleration_runtime_identities"]
    if type(identities) is not list or not identities:
        raise FixtureActivationBlockedError(
            "acceleration_runtime_identities must be a non-empty array"
        )
    validated_identities = [
        _require_ascii_identity(item, field="acceleration_runtime_identities[]")
        for item in identities
    ]
    if len(set(validated_identities)) != len(validated_identities):
        raise FixtureActivationBlockedError("acceleration runtime identities must be unique")
    if validated_identities != sorted(
        validated_identities,
        key=lambda item: item.encode("ascii"),
    ):
        raise FixtureActivationBlockedError("acceleration runtime identities must be byte-sorted")

    _require_regex_string(
        value["base_container_oci_digest"],
        _OCI_DIGEST_RE,
        field="base_container_oci_digest",
    )
    for field in (
        "cuda_runtime_version",
        "gpu_uuid",
        "nvidia_driver_version",
        "provider_instance_or_pod_id",
        "provider_region",
        "python_version",
        "pytorch_version",
        "transformers_identity",
    ):
        _require_ascii_identity(value[field], field=field)

    _require_regex_string(
        value["dependency_lock_sha256"],
        _SHA256_RE,
        field="dependency_lock_sha256",
    )
    for field in (
        "external_runtime_parent_device_id",
        "external_runtime_parent_inode",
        "external_runtime_parent_mount_id",
        "repository_checkout_root_device_id",
        "repository_checkout_root_inode",
        "repository_checkout_root_mount_id",
        "repository_result_parent_device_id",
        "repository_result_parent_inode",
        "repository_result_parent_mount_id",
    ):
        _require_nonnegative_int(value[field], field=field)

    if value["external_runtime_parent_path"] != EXTERNAL_RUNTIME_PARENT_PATH:
        raise FixtureActivationBlockedError("external runtime parent path mismatch")
    if type(value["gpu_count"]) is not int or value["gpu_count"] != 1:
        raise FixtureActivationBlockedError("gpu_count must be exactly 1")
    if value["gpu_model"] != GPU_MODEL_H100:
        raise FixtureActivationBlockedError("gpu_model mismatch")
    if value["provider_class"] != PROVIDER_CLASS:
        raise FixtureActivationBlockedError("provider_class mismatch")
    if type(value["sequential_single_gpu_execution"]) is not bool:
        raise FixtureActivationBlockedError("sequential_single_gpu_execution must be boolean true")
    if value["sequential_single_gpu_execution"] is not True:
        raise FixtureActivationBlockedError("sequential_single_gpu_execution must be boolean true")

    _require_regex_string(
        value["repository_checkout_root_path"],
        _CHECKOUT_ROOT_RE,
        field="repository_checkout_root_path",
    )
    _require_sha40(value["repository_checkout_sha"], field="repository_checkout_sha")
    _require_sha40(value["repository_checkout_tree"], field="repository_checkout_tree")
    return value


def _parse_identity_preimage(raw: bytes) -> dict[str, object]:
    value = _parse_canonical_object(raw, field="identity_preimage")
    if tuple(value) != _IDENTITY_KEYS:
        raise FixtureActivationBlockedError("identity_preimage key set/order mismatch")

    for field in (
        "apertus_access_attestation_sha256",
        "executor_allowlist_sha256",
        "medgemma_access_attestation_sha256",
        "phi_remote_code_manifest_sha256",
        "phi_remote_code_security_review_sha256",
        "phi_sandbox_qualification_sha256",
        "runtime_binding_sha256",
        "telemetry_qualification_sha256",
    ):
        _require_regex_string(value[field], _SHA256_RE, field=field)

    for field in (
        "authorization_merge_sha",
        "authorization_merge_tree",
        "execution_code_sha",
        "execution_code_tree",
        "gated_access_decision_merge_sha",
    ):
        _require_sha40(value[field], field=field)

    if value["decision_id"] != DECISION_ID:
        raise FixtureActivationBlockedError("decision_id mismatch")
    if value["receipt_version"] != RECEIPT_VERSION:
        raise FixtureActivationBlockedError("receipt_version mismatch")
    _require_positive_int(
        value["founder_attestation_comment_id"],
        field="founder_attestation_comment_id",
    )
    _require_positive_int(
        value["gated_access_founder_attestation_comment_id"],
        field="gated_access_founder_attestation_comment_id",
    )
    return value


def _parse_canonical_object(raw: bytes, *, field: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise FixtureActivationBlockedError(f"{field} must be non-empty bytes")
    if raw.startswith(b"\xef\xbb\xbf"):
        raise FixtureActivationBlockedError(f"{field} must not contain a BOM")
    if raw.endswith(b"\n") or raw.endswith(b"\r"):
        raise FixtureActivationBlockedError(f"{field} must not have a trailing newline")
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise FixtureActivationBlockedError(f"{field} must be ASCII JSON") from error

    try:
        parsed = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_members,
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, FixtureActivationBlockedError) as error:
        if isinstance(error, FixtureActivationBlockedError):
            raise
        raise FixtureActivationBlockedError(f"{field} is not valid JSON") from error
    if type(parsed) is not dict:
        raise FixtureActivationBlockedError(f"{field} must be a JSON object")

    try:
        canonical = json.dumps(
            parsed,
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, ValueError) as error:
        raise FixtureActivationBlockedError(f"{field} cannot be canonically serialized") from error
    if canonical != raw:
        raise FixtureActivationBlockedError(f"{field} is not canonical JSON")
    return parsed


def _reject_json_constant(token: str) -> object:
    raise FixtureActivationBlockedError(f"non-finite JSON token prohibited: {token}")


def _reject_duplicate_members(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise FixtureActivationBlockedError(f"duplicate JSON member: {key}")
        result[key] = value
    return result


def _validate_independent_bindings(independent: IndependentActivationBindings) -> None:
    for field in (
        "authorization_merge_sha",
        "authorization_merge_tree",
        "execution_code_sha",
        "execution_code_tree",
        "gated_access_decision_merge_sha",
        "repository_checkout_sha",
        "repository_checkout_tree",
    ):
        _require_sha40(getattr(independent, field), field=f"independent.{field}")
    for field in (
        "executor_allowlist_sha256",
        "apertus_access_attestation_sha256",
        "medgemma_access_attestation_sha256",
        "phi_remote_code_manifest_sha256",
        "phi_remote_code_security_review_sha256",
        "phi_sandbox_qualification_sha256",
        "telemetry_qualification_sha256",
    ):
        _require_regex_string(
            getattr(independent, field),
            _SHA256_RE,
            field=f"independent.{field}",
        )
    _require_positive_int(
        independent.founder_attestation_comment_id,
        field="independent.founder_attestation_comment_id",
    )
    _require_positive_int(
        independent.gated_access_founder_attestation_comment_id,
        field="independent.gated_access_founder_attestation_comment_id",
    )


def _require_ascii_identity(value: object, *, field: str) -> str:
    if type(value) is not str or not value:
        raise FixtureActivationBlockedError(f"{field} must be a non-empty string")
    try:
        encoded = value.encode("ascii")
    except UnicodeEncodeError as error:
        raise FixtureActivationBlockedError(f"{field} must be ASCII") from error
    if any(byte < 0x20 or byte > 0x7E or byte in {0x22, 0x5C} for byte in encoded):
        raise FixtureActivationBlockedError(f"{field} contains a prohibited ASCII byte")
    return value


def _require_regex_string(
    value: object,
    pattern: re.Pattern[str],
    *,
    field: str,
) -> str:
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise FixtureActivationBlockedError(f"{field} has invalid string form")
    return value


def _require_sha40(value: object, *, field: str) -> str:
    return _require_regex_string(value, _SHA40_RE, field=field)


def _require_nonnegative_int(value: object, *, field: str) -> int:
    if type(value) is not int or value < 0:
        raise FixtureActivationBlockedError(f"{field} must be an integer >= 0")
    return value


def _require_positive_int(value: object, *, field: str) -> int:
    if type(value) is not int or value < 1:
        raise FixtureActivationBlockedError(f"{field} must be an integer >= 1")
    return value
