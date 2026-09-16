"""Deterministic MRL-0808 sandbox qualification prototype.

The module validates frozen sandbox policies plus caller-supplied hosted observation and
independent runtime/control-plane attestation bytes. The attestation is not self-trusting:
its exact digest must already exist in the separately controlled trust root before this
module can emit an untrusted MRL-0808 real-preflight evidence candidate.

This prototype performs no network access, provider scheduling, model/tokenizer loading,
scientific evaluation, training, weight mutation, promotion, release, or clinical action.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Final, Never, cast

from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_OBSERVATION_SCHEMA: Final = "MESC-MRL-0808-RUNTIME-SANDBOX-OBSERVATION-V1"
_ATTESTATION_SCHEMA: Final = "MESC-MRL-0808-RUNTIME-SANDBOX-ATTESTATION-V1"
_CHALLENGE_RECEIPT_SCHEMA: Final = "MESC-MRL-0808-SANDBOX-CHALLENGE-RECEIPT-V1"
_RUNTIME_CONTEXT_SCHEMA: Final = "MESC-MRL-0808-RUNTIME-CONTEXT-V1"
_CLEANUP_RECEIPT_SCHEMA: Final = "MESC-MRL-0808-SANDBOX-CLEANUP-RECEIPT-V1"
_CONTROL_EVIDENCE_SCHEMA: Final = "MESC-MRL-0808-SANDBOX-CONTROL-EVIDENCE-V1"
_RECEIPT_SCHEMA: Final = "MESC-MRL-0808-SANDBOX-QUALIFICATION-RECEIPT-V1"
_EVIDENCE_SCHEMA: Final = "MRL-REAL-PREFLIGHT-EVIDENCE-V1"
_EVIDENCE_KIND: Final = "mesc.mrl.real_preflight.sandbox.v1"
_TASK: Final = "MRL-0808"
_EXPECTED_AUTHORIZATION: Final = "838c7ed0b8aafd9f85a89d96846486660d0f54ba0e50c0ebec1a415a6b328575"
_EXPECTED_RUNTIME_EVIDENCE: Final = (
    "f630a852319ca1ce6bd66b3203ce80c092e0695cabec3bb8456e29a94f8cd3f0"
)
_EXPECTED_RUNTIME_IDENTITY: Final = (
    "05b19593f7c9c1f03df39a100189da653695bad1b13d24c921dd1fecd7fe0b45"
)
_EXPECTED_0806_EVIDENCE: Final = "27ed7a990b6408b8972980d576da3692801dfdb3f7bd444beda1b0135f7d7de2"
_EXPECTED_NETWORK_POLICY: Final = "4ba5dc099d7e5ad648bbd473a73a1e91693fe6b139286f26b0e80831b0e0732f"
_EXPECTED_MUTATION_POLICY: Final = (
    "044c61563880e630e079fad1e762aa5c9d3af505099a801070ef57d750633691"
)
_EXPECTED_OUTPUT_POLICY: Final = "2b6c79b5662d3e91f107bf24d00155b8df0b4a1c96b0ad48284451afd0cbb8ea"
_EXPECTED_STOP_POLICY: Final = "607720d456b0dfdc26b6058bfc3bd71f18bdd539e52fab1c0b32780c4c1b6194"
_EXPECTED_SANDBOX_POLICY: Final = "169255451b232a530875e221f39096fd103f3429b5d5125f54229f1b347c8316"

# Offline prototype trust root: intentionally empty. A later separately reviewed
# canonical mutation may admit exactly one independently verified attestation digest.
TRUSTED_MRL0808_RUNTIME_SANDBOX_ATTESTATION_SHA256: frozenset[str] = frozenset()


class MRL0808SandboxError(ValueError):
    """Fail-closed MRL-0808 sandbox qualification error."""


@dataclass(frozen=True, slots=True)
class SandboxQualification:
    """Derived qualification receipt plus untrusted MRL-0808 evidence candidate."""

    runtime_sandbox_evidence_bytes: bytes = field(repr=False)
    receipt_bytes: bytes = field(repr=False)
    evidence_bytes: bytes = field(repr=False)
    attestation_sha256: str
    observation_sha256: str
    runtime_context_sha256: str
    cleanup_receipt_sha256: str
    sandbox_control_evidence_sha256: str
    runtime_sandbox_evidence_sha256: str
    receipt_sha256: str
    evidence_sha256: str


def _reject_constant(token: str) -> Never:
    raise MRL0808SandboxError(f"non-standard JSON constant prohibited: {token}")


def _reject_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    out: dict[str, object] = {}
    for key, value in pairs:
        if key in out:
            raise MRL0808SandboxError(f"duplicate JSON member: {key}")
        out[key] = value
    return out


def _canonical(value: object) -> bytes:
    try:
        return canonical_json_bytes(value)
    except CanonicalContractError as exc:
        raise MRL0808SandboxError("value cannot be canonically serialized") from exc


def _document(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise MRL0808SandboxError(f"{label} must be non-empty built-in bytes")
    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text, object_pairs_hook=_reject_duplicates, parse_constant=_reject_constant
        )
    except MRL0808SandboxError:
        raise
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise MRL0808SandboxError(f"{label} is not canonical JSON") from exc
    if type(value) is not dict:
        raise MRL0808SandboxError(f"{label} top level must be one object")
    document = cast(dict[str, object], value)
    if _canonical(document) != raw:
        raise MRL0808SandboxError(f"{label} is not exact canonical JSON")
    return document


def _keys(document: dict[str, object], expected: set[str], *, label: str) -> None:
    if set(document) != expected:
        raise MRL0808SandboxError(f"{label} exact key set mismatch")


def _text(value: object, *, field: str) -> str:
    if type(value) is not str or not value or value != value.strip() or "\x00" in value:
        raise MRL0808SandboxError(f"{field} must be non-empty canonical text")
    return value


def _sha(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _SHA256.fullmatch(text) is None:
        raise MRL0808SandboxError(f"{field} must be 64 lowercase hex")
    return text


def _git_sha(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if _GIT_SHA.fullmatch(text) is None:
        raise MRL0808SandboxError(f"{field} must be 40 lowercase hex")
    return text


def _false(value: object, *, field: str) -> None:
    if type(value) is not bool or value is not False:
        raise MRL0808SandboxError(f"{field} must be false")


def _true(value: object, *, field: str) -> None:
    if type(value) is not bool or value is not True:
        raise MRL0808SandboxError(f"{field} must be true")


def _zero(value: object, *, field: str) -> None:
    if type(value) is not int or value != 0:
        raise MRL0808SandboxError(f"{field} must be integer zero")


def _parse_policy(raw: bytes, expected_sha: str, *, label: str) -> dict[str, object]:
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise MRL0808SandboxError(f"{label} digest drifted")
    return _document(raw, label=label)


def _parse_runtime_context(
    raw: bytes, *, repository_sha: str, repository_tree: str
) -> dict[str, object]:
    document = _document(raw, label="runtime context")
    _keys(
        document,
        {
            "bubblewrap_binary_sha256",
            "bubblewrap_version",
            "colab_release_tag",
            "direct_host_root_bind",
            "gpu_observation",
            "kernel_release",
            "model_weights_directory_empty",
            "nvidia_device_nodes",
            "output_tmpfs_maximum_bytes",
            "provider",
            "provider_execution_id",
            "provider_flavor",
            "provider_owner",
            "python_version",
            "repository_sha",
            "repository_tree",
            "runtime_support_read_only_roots",
            "runtime_support_symlinks",
            "schema_version",
            "scratch_tmpfs_maximum_bytes",
            "synthetic_input_sha256",
        },
        label="runtime context",
    )
    if document["schema_version"] != _RUNTIME_CONTEXT_SCHEMA:
        raise MRL0808SandboxError("runtime context schema drifted")
    if (
        document["provider"] != "GOOGLE_COLAB"
        or document["provider_flavor"] != "DYNAMIC_ASSIGNED"
        or document["provider_owner"] != "GOOGLE"
    ):
        raise MRL0808SandboxError("runtime context is not the qualified Google Colab class")
    if document["direct_host_root_bind"] is not False:
        raise MRL0808SandboxError("runtime context must deny direct host-root binding")
    if document["model_weights_directory_empty"] is not True:
        raise MRL0808SandboxError("sandbox qualification must expose no model weights")
    if _git_sha(document["repository_sha"], field="repository_sha") != repository_sha:
        raise MRL0808SandboxError("runtime context repository SHA drifted")
    if _git_sha(document["repository_tree"], field="repository_tree") != repository_tree:
        raise MRL0808SandboxError("runtime context repository tree drifted")
    _sha(document["bubblewrap_binary_sha256"], field="bubblewrap_binary_sha256")
    for field_name in (
        "bubblewrap_version",
        "colab_release_tag",
        "gpu_observation",
        "kernel_release",
        "provider_execution_id",
        "python_version",
    ):
        _text(document[field_name], field=field_name)
    if document["output_tmpfs_maximum_bytes"] != 67_108_864:
        raise MRL0808SandboxError("runtime context output tmpfs budget drifted")
    if document["scratch_tmpfs_maximum_bytes"] != 268_435_456:
        raise MRL0808SandboxError("runtime context scratch tmpfs budget drifted")
    expected_synthetic_input = hashlib.sha256(
        b"MESC-MRL-0808-SYNTHETIC-READ-PROBE-V1\n"
    ).hexdigest()
    if (
        _sha(document["synthetic_input_sha256"], field="synthetic_input_sha256")
        != expected_synthetic_input
    ):
        raise MRL0808SandboxError("runtime context synthetic-input identity drifted")
    if document["runtime_support_read_only_roots"] != ["/etc/ld.so.cache", "/sys", "/usr"]:
        raise MRL0808SandboxError("runtime support root allowlist drifted")
    nodes = document["nvidia_device_nodes"]
    if type(nodes) is not list or not nodes:
        raise MRL0808SandboxError("runtime context must bind explicit NVIDIA device nodes")
    for index, node in enumerate(nodes):
        text = _text(node, field=f"nvidia_device_nodes[{index}]")
        if not text.startswith("/dev/nvidia"):
            raise MRL0808SandboxError("runtime context contains non-NVIDIA device node")
    symlinks = document["runtime_support_symlinks"]
    if type(symlinks) is not dict:
        raise MRL0808SandboxError("runtime support symlinks must be one object")
    for link_path, target in cast(dict[str, object], symlinks).items():
        path_text = _text(link_path, field="runtime_support_symlink_path")
        target_text = _text(target, field=f"runtime_support_symlinks[{path_text}]")
        if path_text not in {"/bin", "/sbin", "/lib", "/lib64"}:
            raise MRL0808SandboxError("runtime support symlink path escaped frozen allowlist")
        if target_text.startswith("/") and target_text != "DIRECT_READ_ONLY_BIND":
            raise MRL0808SandboxError("runtime support symlink target must remain relative")
    return document


def _parse_cleanup_receipt(
    raw: bytes,
    observation: dict[str, object],
    observation_sha: str,
    runtime_context_sha: str,
    control_evidence_sha: str,
    *,
    repository_sha: str,
    repository_tree: str,
) -> dict[str, object]:
    document = _document(raw, label="cleanup receipt")
    _keys(
        document,
        {
            "challenge",
            "collected_bytes_before_cleanup",
            "forbidden_repository_write_absent",
            "minimal_runtime_root_enforced",
            "normal_probe_exit_code",
            "observation_sha256",
            "output_budget_challenge_blocked",
            "output_tmpfs_destroyed_after_namespace_exit",
            "repository_sha",
            "repository_tree",
            "runtime_context_sha256",
            "sandbox_control_evidence_sha256",
            "sandbox_policy_sha256",
            "schema_version",
            "scratch_tmpfs_destroyed_after_namespace_exit",
            "state",
            "undeclared_output_challenge_blocked",
            "violation_probe_stopped",
        },
        label="cleanup receipt",
    )
    if document["schema_version"] != _CLEANUP_RECEIPT_SCHEMA or document["state"] != "COMPLETED":
        raise MRL0808SandboxError("cleanup receipt state/schema invalid")
    if _sha(document["challenge"], field="challenge") != cast(str, observation["challenge"]):
        raise MRL0808SandboxError("cleanup receipt challenge mismatch")
    if _sha(document["observation_sha256"], field="observation_sha256") != observation_sha:
        raise MRL0808SandboxError("cleanup receipt observation mismatch")
    if (
        _sha(document["runtime_context_sha256"], field="runtime_context_sha256")
        != runtime_context_sha
    ):
        raise MRL0808SandboxError("cleanup receipt runtime context mismatch")
    if (
        _sha(document["sandbox_control_evidence_sha256"], field="sandbox_control_evidence_sha256")
        != control_evidence_sha
    ):
        raise MRL0808SandboxError("cleanup receipt sandbox-control evidence mismatch")
    if _git_sha(document["repository_sha"], field="repository_sha") != repository_sha:
        raise MRL0808SandboxError("cleanup receipt repository SHA drifted")
    if _git_sha(document["repository_tree"], field="repository_tree") != repository_tree:
        raise MRL0808SandboxError("cleanup receipt repository tree drifted")
    if (
        _sha(document["sandbox_policy_sha256"], field="sandbox_policy_sha256")
        != _EXPECTED_SANDBOX_POLICY
    ):
        raise MRL0808SandboxError("cleanup receipt sandbox policy drifted")
    _zero(document["normal_probe_exit_code"], field="normal_probe_exit_code")
    collected = document["collected_bytes_before_cleanup"]
    if type(collected) is not int or collected <= 0 or collected > 67_108_864:
        raise MRL0808SandboxError("cleanup receipt collected-byte budget invalid")
    for field_name in (
        "forbidden_repository_write_absent",
        "minimal_runtime_root_enforced",
        "output_budget_challenge_blocked",
        "output_tmpfs_destroyed_after_namespace_exit",
        "scratch_tmpfs_destroyed_after_namespace_exit",
        "undeclared_output_challenge_blocked",
        "violation_probe_stopped",
    ):
        _true(document[field_name], field=field_name)
    return document


def _parse_observation(raw: bytes) -> dict[str, object]:
    document = _document(raw, label="sandbox observation")
    _keys(
        document,
        {
            "challenge",
            "controls",
            "monetary_cost_microunits",
            "model_loaded",
            "mutation_paths_sha256",
            "network_policy_sha256",
            "output_destinations_sha256",
            "predecessor_runtime_evidence_sha256",
            "predecessor_runtime_identity_sha256",
            "runtime_context_sha256",
            "sandbox_policy_sha256",
            "schema_version",
            "sealed_tier3_item_content_accessed",
            "stop_conditions_sha256",
            "tokenizer_loaded",
            "training_performed",
            "weight_mutation_performed",
        },
        label="sandbox observation",
    )
    if document["schema_version"] != _OBSERVATION_SCHEMA:
        raise MRL0808SandboxError("sandbox observation schema drifted")
    _sha(document["challenge"], field="challenge")
    expected = {
        "mutation_paths_sha256": _EXPECTED_MUTATION_POLICY,
        "network_policy_sha256": _EXPECTED_NETWORK_POLICY,
        "output_destinations_sha256": _EXPECTED_OUTPUT_POLICY,
        "predecessor_runtime_evidence_sha256": _EXPECTED_RUNTIME_EVIDENCE,
        "predecessor_runtime_identity_sha256": _EXPECTED_RUNTIME_IDENTITY,
        "sandbox_policy_sha256": _EXPECTED_SANDBOX_POLICY,
        "stop_conditions_sha256": _EXPECTED_STOP_POLICY,
    }
    for field_name, expected_value in expected.items():
        if _sha(document[field_name], field=field_name) != expected_value:
            raise MRL0808SandboxError(f"{field_name} does not match frozen policy/predecessor")
    _sha(document["runtime_context_sha256"], field="runtime_context_sha256")
    controls = document["controls"]
    if type(controls) is not dict:
        raise MRL0808SandboxError("controls must be one object")
    expected_controls = {
        "cloud_metadata_access_denied",
        "control_sockets_absent",
        "credential_environment_empty",
        "dns_unavailable",
        "home_write_denied",
        "inputs_read_only_enforced",
        "model_weights_read_only_enforced",
        "network_egress_denied",
        "output_write_allowed",
        "repository_read_only_enforced",
        "root_write_denied",
        "scratch_write_allowed",
        "synthetic_input_read_allowed",
        "tmp_write_denied",
    }
    _keys(cast(dict[str, object], controls), expected_controls, label="controls")
    for key in expected_controls:
        _true(cast(dict[str, object], controls)[key], field=f"controls.{key}")
    _zero(document["monetary_cost_microunits"], field="monetary_cost_microunits")
    for field_name in (
        "model_loaded",
        "sealed_tier3_item_content_accessed",
        "tokenizer_loaded",
        "training_performed",
        "weight_mutation_performed",
    ):
        _false(document[field_name], field=field_name)
    return document


def _parse_control_evidence(
    raw: bytes,
    observation: dict[str, object],
    *,
    runtime_context_sha: str,
    expected_gpu: str,
) -> dict[str, object]:
    document = _document(raw, label="sandbox control evidence")
    _keys(
        document,
        {
            "allowed_artifact_names",
            "challenge",
            "dev_directory_write_denied",
            "forbidden_host_data_roots_absent",
            "gpu_observation",
            "gpu_visible_inside_sandbox",
            "maximum_total_bytes",
            "output_filesystem_type",
            "output_mount_capacity_bytes",
            "output_root",
            "output_root_capacity_enforced",
            "proc_write_denied",
            "runtime_context_sha256",
            "runtime_support_roots_present",
            "schema_version",
            "undeclared_artifact_present",
        },
        label="sandbox control evidence",
    )
    if document["schema_version"] != _CONTROL_EVIDENCE_SCHEMA:
        raise MRL0808SandboxError("sandbox control evidence schema drifted")
    if _sha(document["challenge"], field="challenge") != cast(str, observation["challenge"]):
        raise MRL0808SandboxError("sandbox control evidence challenge mismatch")
    if (
        _sha(document["runtime_context_sha256"], field="runtime_context_sha256")
        != runtime_context_sha
    ):
        raise MRL0808SandboxError("sandbox control evidence runtime context mismatch")
    if _text(document["gpu_observation"], field="gpu_observation") != expected_gpu:
        raise MRL0808SandboxError("sandbox control evidence GPU identity drifted")
    if document["allowed_artifact_names"] != [
        "sandbox-observation.json",
        "sandbox-control-evidence.json",
    ]:
        raise MRL0808SandboxError("sandbox control evidence allowed-artifact set drifted")
    if document["maximum_total_bytes"] != 67_108_864:
        raise MRL0808SandboxError("sandbox control evidence output budget drifted")
    if (
        document["output_filesystem_type"] != "tmpfs"
        or document["output_root"] != "/mesc-run/output"
    ):
        raise MRL0808SandboxError("sandbox control evidence output mount identity drifted")
    capacity = document["output_mount_capacity_bytes"]
    if type(capacity) is not int or capacity <= 0 or capacity > 67_108_864:
        raise MRL0808SandboxError("sandbox control evidence output mount capacity invalid")
    for field_name in (
        "dev_directory_write_denied",
        "forbidden_host_data_roots_absent",
        "gpu_visible_inside_sandbox",
        "output_root_capacity_enforced",
        "proc_write_denied",
        "runtime_support_roots_present",
    ):
        _true(document[field_name], field=field_name)
    _false(document["undeclared_artifact_present"], field="undeclared_artifact_present")
    return document


def _parse_challenge_receipt(
    raw: bytes,
    observation: dict[str, object],
    observation_sha: str,
    runtime_context_sha: str,
    cleanup_receipt_sha: str,
    control_evidence_sha: str,
    *,
    repository_sha: str,
    repository_tree: str,
) -> dict[str, object]:
    document = _document(raw, label="challenge receipt")
    _keys(
        document,
        {
            "challenge",
            "cleanup_receipt_sha256",
            "observation_sha256",
            "sandbox_control_evidence_sha256",
            "predecessor_runtime_evidence_sha256",
            "predecessor_runtime_identity_sha256",
            "provider_execution_id",
            "repository_sha",
            "repository_tree",
            "runtime_context_sha256",
            "sandbox_policy_sha256",
            "schema_version",
            "state",
            "task_id",
        },
        label="challenge receipt",
    )
    if document["schema_version"] != _CHALLENGE_RECEIPT_SCHEMA:
        raise MRL0808SandboxError("challenge receipt schema drifted")
    if document["state"] != "CONSUMED" or document["task_id"] != _TASK:
        raise MRL0808SandboxError("challenge receipt is not one consumed MRL-0808 challenge")
    if _sha(document["challenge"], field="challenge") != cast(str, observation["challenge"]):
        raise MRL0808SandboxError("challenge receipt does not bind observation challenge")
    if _sha(document["observation_sha256"], field="observation_sha256") != observation_sha:
        raise MRL0808SandboxError("challenge receipt does not bind exact observation")
    if (
        _sha(document["runtime_context_sha256"], field="runtime_context_sha256")
        != runtime_context_sha
    ):
        raise MRL0808SandboxError("challenge receipt does not bind exact runtime context")
    if (
        _sha(document["cleanup_receipt_sha256"], field="cleanup_receipt_sha256")
        != cleanup_receipt_sha
    ):
        raise MRL0808SandboxError("challenge receipt does not bind exact cleanup receipt")
    if (
        _sha(document["sandbox_control_evidence_sha256"], field="sandbox_control_evidence_sha256")
        != control_evidence_sha
    ):
        raise MRL0808SandboxError("challenge receipt does not bind exact sandbox-control evidence")
    if _git_sha(document["repository_sha"], field="repository_sha") != repository_sha:
        raise MRL0808SandboxError("challenge receipt repository SHA drifted")
    if _git_sha(document["repository_tree"], field="repository_tree") != repository_tree:
        raise MRL0808SandboxError("challenge receipt repository tree drifted")
    if (
        _sha(document["sandbox_policy_sha256"], field="sandbox_policy_sha256")
        != _EXPECTED_SANDBOX_POLICY
    ):
        raise MRL0808SandboxError("challenge receipt sandbox policy drifted")
    if (
        _sha(
            document["predecessor_runtime_evidence_sha256"],
            field="predecessor_runtime_evidence_sha256",
        )
        != _EXPECTED_RUNTIME_EVIDENCE
    ):
        raise MRL0808SandboxError("challenge receipt predecessor runtime evidence drifted")
    if (
        _sha(
            document["predecessor_runtime_identity_sha256"],
            field="predecessor_runtime_identity_sha256",
        )
        != _EXPECTED_RUNTIME_IDENTITY
    ):
        raise MRL0808SandboxError("challenge receipt predecessor runtime identity drifted")
    _text(document["provider_execution_id"], field="provider_execution_id")
    return document


def _parse_attestation(
    raw: bytes,
    observation: dict[str, object],
    observation_sha: str,
    challenge_receipt: dict[str, object],
    challenge_receipt_sha: str,
    runtime_context: dict[str, object],
    cleanup_receipt_sha: str,
    control_evidence_sha: str,
) -> dict[str, object]:
    document = _document(raw, label="runtime-sandbox attestation")
    _keys(
        document,
        {
            "attestation_state",
            "challenge",
            "challenge_receipt_sha256",
            "challenge_state",
            "cleanup_receipt_sha256",
            "sandbox_control_evidence_sha256",
            "independent_verification_method",
            "independent_verification_reference",
            "monetary_cost_microunits",
            "observation_sha256",
            "policy_sha256",
            "provider",
            "provider_execution_id",
            "provider_flavor",
            "provider_owner",
            "repository_sha",
            "repository_tree",
            "runtime_context_sha256",
            "schema_version",
        },
        label="runtime-sandbox attestation",
    )
    if (
        document["schema_version"] != _ATTESTATION_SCHEMA
        or document["attestation_state"] != "COMPLETED"
        or document["challenge_state"] != "CONSUMED"
    ):
        raise MRL0808SandboxError("runtime-sandbox attestation state/schema invalid")
    if (
        document["provider"] != "GOOGLE_COLAB"
        or document["provider_flavor"] != "DYNAMIC_ASSIGNED"
        or document["provider_owner"] != "GOOGLE"
    ):
        raise MRL0808SandboxError(
            "runtime-sandbox attestation is not the qualified Google Colab class"
        )
    _text(document["provider_execution_id"], field="provider_execution_id")
    _git_sha(document["repository_sha"], field="repository_sha")
    _git_sha(document["repository_tree"], field="repository_tree")
    _text(
        document["independent_verification_method"],
        field="independent_verification_method",
    )
    _text(
        document["independent_verification_reference"],
        field="independent_verification_reference",
    )
    _zero(document["monetary_cost_microunits"], field="monetary_cost_microunits")
    if _sha(document["observation_sha256"], field="observation_sha256") != observation_sha:
        raise MRL0808SandboxError("attestation does not bind the exact observation")
    if (
        _sha(document["challenge_receipt_sha256"], field="challenge_receipt_sha256")
        != challenge_receipt_sha
    ):
        raise MRL0808SandboxError("attestation does not bind exact consumed challenge receipt")
    if (
        _sha(document["cleanup_receipt_sha256"], field="cleanup_receipt_sha256")
        != cleanup_receipt_sha
    ):
        raise MRL0808SandboxError("attestation does not bind exact cleanup receipt")
    if (
        _sha(document["sandbox_control_evidence_sha256"], field="sandbox_control_evidence_sha256")
        != control_evidence_sha
    ):
        raise MRL0808SandboxError("attestation does not bind exact sandbox-control evidence")
    if document["provider_execution_id"] != challenge_receipt["provider_execution_id"]:
        raise MRL0808SandboxError(
            "attestation provider execution identity does not match challenge receipt"
        )
    if document["provider_execution_id"] != runtime_context["provider_execution_id"]:
        raise MRL0808SandboxError(
            "attestation provider execution identity does not match runtime context"
        )
    if _sha(document["challenge"], field="challenge") != cast(str, observation["challenge"]):
        raise MRL0808SandboxError("attestation challenge does not match observation")
    if _sha(document["runtime_context_sha256"], field="runtime_context_sha256") != cast(
        str, observation["runtime_context_sha256"]
    ):
        raise MRL0808SandboxError("attestation runtime context does not match observation")
    if _sha(document["policy_sha256"], field="policy_sha256") != _EXPECTED_SANDBOX_POLICY:
        raise MRL0808SandboxError("attestation sandbox policy identity drifted")
    return document


def qualify_mrl_0808_sandbox(
    *,
    authorization_bytes: bytes,
    network_policy_bytes: bytes,
    mutation_policy_bytes: bytes,
    output_policy_bytes: bytes,
    stop_policy_bytes: bytes,
    sandbox_policy_bytes: bytes,
    observation_bytes: bytes,
    runtime_context_bytes: bytes,
    sandbox_control_evidence_bytes: bytes,
    cleanup_receipt_bytes: bytes,
    challenge_receipt_bytes: bytes,
    runtime_attestation_bytes: bytes,
    repository_sha: str,
    repository_tree: str,
) -> SandboxQualification:
    """Validate exact frozen policies and one trusted hosted sandbox observation."""
    _parse_policy(authorization_bytes, _EXPECTED_AUTHORIZATION, label="MRL-0808 authorization")
    _parse_policy(network_policy_bytes, _EXPECTED_NETWORK_POLICY, label="network policy")
    _parse_policy(mutation_policy_bytes, _EXPECTED_MUTATION_POLICY, label="mutation policy")
    _parse_policy(output_policy_bytes, _EXPECTED_OUTPUT_POLICY, label="output policy")
    _parse_policy(stop_policy_bytes, _EXPECTED_STOP_POLICY, label="stop policy")
    _parse_policy(sandbox_policy_bytes, _EXPECTED_SANDBOX_POLICY, label="sandbox policy")
    repo_sha = _git_sha(repository_sha, field="repository_sha")
    repo_tree = _git_sha(repository_tree, field="repository_tree")
    runtime_context = _parse_runtime_context(
        runtime_context_bytes, repository_sha=repo_sha, repository_tree=repo_tree
    )
    runtime_context_sha = hashlib.sha256(runtime_context_bytes).hexdigest()
    observation = _parse_observation(observation_bytes)
    observation_sha = hashlib.sha256(observation_bytes).hexdigest()
    if (
        _sha(observation["runtime_context_sha256"], field="runtime_context_sha256")
        != runtime_context_sha
    ):
        raise MRL0808SandboxError("observation does not bind exact runtime context")
    _parse_control_evidence(
        sandbox_control_evidence_bytes,
        observation,
        runtime_context_sha=runtime_context_sha,
        expected_gpu=cast(str, runtime_context["gpu_observation"]),
    )
    control_evidence_sha = hashlib.sha256(sandbox_control_evidence_bytes).hexdigest()
    _parse_cleanup_receipt(
        cleanup_receipt_bytes,
        observation,
        observation_sha,
        runtime_context_sha,
        control_evidence_sha,
        repository_sha=repo_sha,
        repository_tree=repo_tree,
    )
    cleanup_receipt_sha = hashlib.sha256(cleanup_receipt_bytes).hexdigest()
    challenge_receipt = _parse_challenge_receipt(
        challenge_receipt_bytes,
        observation,
        observation_sha,
        runtime_context_sha,
        cleanup_receipt_sha,
        control_evidence_sha,
        repository_sha=repo_sha,
        repository_tree=repo_tree,
    )
    challenge_receipt_sha = hashlib.sha256(challenge_receipt_bytes).hexdigest()
    attestation = _parse_attestation(
        runtime_attestation_bytes,
        observation,
        observation_sha,
        challenge_receipt,
        challenge_receipt_sha,
        runtime_context,
        cleanup_receipt_sha,
        control_evidence_sha,
    )
    if attestation["repository_sha"] != repo_sha or attestation["repository_tree"] != repo_tree:
        raise MRL0808SandboxError("runtime-sandbox attestation repository identity drifted")
    attestation_sha = hashlib.sha256(runtime_attestation_bytes).hexdigest()
    if attestation_sha not in TRUSTED_MRL0808_RUNTIME_SANDBOX_ATTESTATION_SHA256:
        raise MRL0808SandboxError("runtime-sandbox attestation is not admitted by canonical trust")

    runtime_sandbox = {
        "attestation_sha256": attestation_sha,
        "challenge": observation["challenge"],
        "challenge_receipt_sha256": challenge_receipt_sha,
        "cleanup_receipt_sha256": cleanup_receipt_sha,
        "sandbox_control_evidence_sha256": control_evidence_sha,
        "observation_sha256": observation_sha,
        "runtime_context_sha256": runtime_context_sha,
        "policy_sha256": _EXPECTED_SANDBOX_POLICY,
        "provider_execution_id": attestation["provider_execution_id"],
        "repository_sha": repo_sha,
        "repository_tree": repo_tree,
        "schema_version": "MESC-MRL-0808-RUNTIME-SANDBOX-EVIDENCE-V1",
    }
    runtime_sandbox_bytes = _canonical(runtime_sandbox)
    runtime_sandbox_sha = hashlib.sha256(runtime_sandbox_bytes).hexdigest()
    receipt = {
        "allowed_mutation_paths_sha256": _EXPECTED_MUTATION_POLICY,
        "challenge_receipt_sha256": challenge_receipt_sha,
        "cleanup_receipt_sha256": cleanup_receipt_sha,
        "sandbox_control_evidence_sha256": control_evidence_sha,
        "network_policy_sha256": _EXPECTED_NETWORK_POLICY,
        "output_destinations_sha256": _EXPECTED_OUTPUT_POLICY,
        "predecessor_mrl_0804_evidence_sha256": _EXPECTED_RUNTIME_EVIDENCE,
        "predecessor_mrl_0806_evidence_sha256": _EXPECTED_0806_EVIDENCE,
        "repository_sha": repo_sha,
        "repository_tree": repo_tree,
        "runtime_context_sha256": runtime_context_sha,
        "runtime_sandbox_evidence_sha256": runtime_sandbox_sha,
        "sandbox_policy_sha256": _EXPECTED_SANDBOX_POLICY,
        "schema_version": _RECEIPT_SCHEMA,
        "stop_conditions_sha256": _EXPECTED_STOP_POLICY,
    }
    receipt_bytes = _canonical(receipt)
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    evidence = {
        "disposition": "PASS",
        "kind": _EVIDENCE_KIND,
        "payload": {
            "allowed_mutation_paths_sha256": _EXPECTED_MUTATION_POLICY,
            "mutation_paths_frozen": True,
            "network_policy_enforced": True,
            "network_policy_sha256": _EXPECTED_NETWORK_POLICY,
            "output_destinations_frozen": True,
            "output_destinations_sha256": _EXPECTED_OUTPUT_POLICY,
            "runtime_sandbox_evidence_sha256": runtime_sandbox_sha,
            "sandbox_policy_sha256": _EXPECTED_SANDBOX_POLICY,
            "sandbox_qualified": True,
            "stop_conditions_frozen": True,
            "stop_conditions_sha256": _EXPECTED_STOP_POLICY,
        },
        "schema_version": _EVIDENCE_SCHEMA,
        "subject_sha256": receipt_sha,
        "task_id": _TASK,
    }
    evidence_bytes = _canonical(evidence)
    return SandboxQualification(
        runtime_sandbox_evidence_bytes=runtime_sandbox_bytes,
        receipt_bytes=receipt_bytes,
        evidence_bytes=evidence_bytes,
        attestation_sha256=attestation_sha,
        observation_sha256=observation_sha,
        runtime_context_sha256=runtime_context_sha,
        cleanup_receipt_sha256=cleanup_receipt_sha,
        sandbox_control_evidence_sha256=control_evidence_sha,
        runtime_sandbox_evidence_sha256=runtime_sandbox_sha,
        receipt_sha256=receipt_sha,
        evidence_sha256=hashlib.sha256(evidence_bytes).hexdigest(),
    )
