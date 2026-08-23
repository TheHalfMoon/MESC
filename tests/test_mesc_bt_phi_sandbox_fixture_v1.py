from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._bt_phi_sandbox_fixture_v1 import (
    PhiSandboxControlEvidence,
    PhiSandboxEvidenceError,
    verify_phi_sandbox_control_evidence,
)


class _StringSubclass(str):
    pass


class _EqualToDenyAll:
    def __eq__(self, other: object) -> bool:
        return other == "DENY_ALL"


class _EvidenceSubclass(PhiSandboxControlEvidence):
    pass


def _valid_evidence() -> PhiSandboxControlEvidence:
    return PhiSandboxControlEvidence(
        dedicated_model_process=True,
        controls_active_before_remote_code_import=True,
        controls_active_before_model_load=True,
        network_egress="DENY_ALL",
        network_ingress="DENY_ALL",
        dns="UNAVAILABLE_TO_MODEL_PROCESS",
        credential_environment="EMPTY",
        cloud_metadata_access="DENIED",
        host_or_container_control_sockets="NONE",
        model_and_runtime_input_mounts="READ_ONLY_ALLOWLIST_ONLY",
        frozen_gold_scoring_inputs_visible_to_model_process="NO",
        writable_paths="ACTIVATION_SCOPED_SCRATCH_AND_OUTPUT_ONLY",
        remote_fetch_during_model_process="PROHIBITED",
    )


def test_accepts_exact_frozen_sandbox_control_evidence() -> None:
    verify_phi_sandbox_control_evidence(_valid_evidence())


def test_rejects_evidence_subclass() -> None:
    valid = _valid_evidence()
    forged = _EvidenceSubclass(
        dedicated_model_process=valid.dedicated_model_process,
        controls_active_before_remote_code_import=valid.controls_active_before_remote_code_import,
        controls_active_before_model_load=valid.controls_active_before_model_load,
        network_egress=valid.network_egress,
        network_ingress=valid.network_ingress,
        dns=valid.dns,
        credential_environment=valid.credential_environment,
        cloud_metadata_access=valid.cloud_metadata_access,
        host_or_container_control_sockets=valid.host_or_container_control_sockets,
        model_and_runtime_input_mounts=valid.model_and_runtime_input_mounts,
        frozen_gold_scoring_inputs_visible_to_model_process=(
            valid.frozen_gold_scoring_inputs_visible_to_model_process
        ),
        writable_paths=valid.writable_paths,
        remote_fetch_during_model_process=valid.remote_fetch_during_model_process,
    )

    with pytest.raises(PhiSandboxEvidenceError, match="invalid type"):
        verify_phi_sandbox_control_evidence(forged)


@pytest.mark.parametrize(
    "field",
    [
        "dedicated_model_process",
        "controls_active_before_remote_code_import",
        "controls_active_before_model_load",
    ],
)
def test_rejects_false_process_or_timing_predicate(field: str) -> None:
    evidence = replace(_valid_evidence(), **{field: False})

    with pytest.raises(PhiSandboxEvidenceError, match="exact boolean true"):
        verify_phi_sandbox_control_evidence(evidence)


@pytest.mark.parametrize(
    "field",
    [
        "dedicated_model_process",
        "controls_active_before_remote_code_import",
        "controls_active_before_model_load",
    ],
)
def test_rejects_integer_for_boolean_predicate(field: str) -> None:
    evidence = replace(_valid_evidence(), **{field: cast(bool, 1)})

    with pytest.raises(PhiSandboxEvidenceError, match="exact boolean true"):
        verify_phi_sandbox_control_evidence(evidence)


@pytest.mark.parametrize(
    ("field", "wrong_value"),
    [
        ("network_egress", "ALLOW"),
        ("network_ingress", "ALLOW"),
        ("dns", "AVAILABLE"),
        ("credential_environment", "NONEMPTY"),
        ("cloud_metadata_access", "ALLOWED"),
        ("host_or_container_control_sockets", "PRESENT"),
        ("model_and_runtime_input_mounts", "READ_WRITE"),
        ("frozen_gold_scoring_inputs_visible_to_model_process", "YES"),
        ("writable_paths", "UNRESTRICTED"),
        ("remote_fetch_during_model_process", "ALLOWED"),
    ],
)
def test_rejects_wrong_frozen_control_value(field: str, wrong_value: str) -> None:
    evidence = replace(_valid_evidence(), **{field: wrong_value})

    with pytest.raises(PhiSandboxEvidenceError, match=field):
        verify_phi_sandbox_control_evidence(evidence)


@pytest.mark.parametrize(
    "field",
    [
        "network_egress",
        "network_ingress",
        "dns",
        "credential_environment",
        "cloud_metadata_access",
        "host_or_container_control_sockets",
        "model_and_runtime_input_mounts",
        "frozen_gold_scoring_inputs_visible_to_model_process",
        "writable_paths",
        "remote_fetch_during_model_process",
    ],
)
def test_rejects_string_subclass_for_control(field: str) -> None:
    valid = _valid_evidence()
    evidence = replace(valid, **{field: _StringSubclass(getattr(valid, field))})

    with pytest.raises(PhiSandboxEvidenceError, match="exact string"):
        verify_phi_sandbox_control_evidence(evidence)


def test_rejects_non_string_equality_spoof() -> None:
    evidence = replace(
        _valid_evidence(),
        network_egress=cast(str, _EqualToDenyAll()),
    )
    assert evidence.network_egress == "DENY_ALL"

    with pytest.raises(PhiSandboxEvidenceError, match="exact string"):
        verify_phi_sandbox_control_evidence(evidence)
