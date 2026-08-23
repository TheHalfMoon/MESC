"""Fail-closed fixture validation for Phi sandbox-control evidence.

This module validates only caller-supplied evidence for the frozen
``FD-MESC-BT-EXEC-1`` Section C.3 Phi model-process isolation predicates. It
performs no sandbox construction, process launch, filesystem or network access,
credential handling, remote-code import or execution, model access, prompt
dispatch, inference, ranking, winner selection, or training.
"""

from __future__ import annotations

from dataclasses import dataclass


class PhiSandboxEvidenceError(ValueError):
    """Caller-supplied sandbox-control evidence is malformed or incomplete."""


@dataclass(frozen=True, slots=True)
class PhiSandboxControlEvidence:
    """Injected evidence for the frozen Phi model-process isolation controls."""

    dedicated_model_process: bool
    controls_active_before_remote_code_import: bool
    controls_active_before_model_load: bool
    network_egress: str
    network_ingress: str
    dns: str
    credential_environment: str
    cloud_metadata_access: str
    host_or_container_control_sockets: str
    model_and_runtime_input_mounts: str
    frozen_gold_scoring_inputs_visible_to_model_process: str
    writable_paths: str
    remote_fetch_during_model_process: str


def verify_phi_sandbox_control_evidence(evidence: PhiSandboxControlEvidence) -> None:
    """Verify injected evidence against the exact frozen sandbox-control values."""
    if type(evidence) is not PhiSandboxControlEvidence:
        raise PhiSandboxEvidenceError("sandbox-control evidence has invalid type")

    _require_true(evidence.dedicated_model_process, field="dedicated_model_process")
    _require_true(
        evidence.controls_active_before_remote_code_import,
        field="controls_active_before_remote_code_import",
    )
    _require_true(
        evidence.controls_active_before_model_load,
        field="controls_active_before_model_load",
    )

    _require_control(evidence.network_egress, "DENY_ALL", field="network_egress")
    _require_control(evidence.network_ingress, "DENY_ALL", field="network_ingress")
    _require_control(evidence.dns, "UNAVAILABLE_TO_MODEL_PROCESS", field="dns")
    _require_control(
        evidence.credential_environment,
        "EMPTY",
        field="credential_environment",
    )
    _require_control(
        evidence.cloud_metadata_access,
        "DENIED",
        field="cloud_metadata_access",
    )
    _require_control(
        evidence.host_or_container_control_sockets,
        "NONE",
        field="host_or_container_control_sockets",
    )
    _require_control(
        evidence.model_and_runtime_input_mounts,
        "READ_ONLY_ALLOWLIST_ONLY",
        field="model_and_runtime_input_mounts",
    )
    _require_control(
        evidence.frozen_gold_scoring_inputs_visible_to_model_process,
        "NO",
        field="frozen_gold_scoring_inputs_visible_to_model_process",
    )
    _require_control(
        evidence.writable_paths,
        "ACTIVATION_SCOPED_SCRATCH_AND_OUTPUT_ONLY",
        field="writable_paths",
    )
    _require_control(
        evidence.remote_fetch_during_model_process,
        "PROHIBITED",
        field="remote_fetch_during_model_process",
    )


def _require_true(value: object, *, field: str) -> None:
    if type(value) is not bool or value is not True:
        raise PhiSandboxEvidenceError(f"{field} must be exact boolean true")


def _require_control(value: object, expected: str, *, field: str) -> None:
    if type(value) is not str:
        raise PhiSandboxEvidenceError(f"{field} must be an exact string")
    if value != expected:
        raise PhiSandboxEvidenceError(f"{field} must equal {expected}")
