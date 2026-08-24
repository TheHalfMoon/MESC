"""Fixture-only qualification for Phi sandbox-qualification artifact conformance."""

from __future__ import annotations

import hashlib
import json
from typing import cast

import pytest

from medscale.mesc._bt_activation_identity_fixture_v1 import (
    EXTERNAL_RUNTIME_PARENT_PATH,
    GPU_MODEL_H100,
    PROVIDER_CLASS,
)
from medscale.mesc._bt_phi_sandbox_qualification_artifact_fixture_v1 import (
    PhiSandboxQualificationArtifact,
    PhiSandboxQualificationArtifactFixtureError,
    verify_phi_sandbox_qualification_artifact_fixture,
)

_SHA_A = "a" * 40
_SHA_B = "b" * 40
_CHALLENGE = "c" * 64
_OVERSIZED_INTEGER_JSON = b'{"x":' + b"1" * 5000 + b"}"
_DEEPLY_NESTED_JSON = b"[" * 1100 + b"0" + b"]" * 1100


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _runtime() -> dict[str, object]:
    return {
        "acceleration_runtime_identities": ["cuda:13.0", "torch:2.9"],
        "base_container_oci_digest": f"sha256:{'0' * 64}",
        "cuda_runtime_version": "13.0",
        "dependency_lock_sha256": "8" * 64,
        "external_runtime_parent_device_id": 1,
        "external_runtime_parent_inode": 2,
        "external_runtime_parent_mount_id": 3,
        "external_runtime_parent_path": EXTERNAL_RUNTIME_PARENT_PATH,
        "gpu_count": 1,
        "gpu_model": GPU_MODEL_H100,
        "gpu_uuid": "GPU-fixture-001",
        "nvidia_driver_version": "590.00",
        "provider_class": PROVIDER_CLASS,
        "provider_instance_or_pod_id": "fixture-pod",
        "provider_region": "fixture-region",
        "python_version": "3.12.14",
        "pytorch_version": "2.9.0",
        "repository_checkout_root_device_id": 4,
        "repository_checkout_root_inode": 5,
        "repository_checkout_root_mount_id": 6,
        "repository_checkout_root_path": "/workspace/mesc-checkout",
        "repository_checkout_sha": _SHA_A,
        "repository_checkout_tree": _SHA_B,
        "repository_result_parent_device_id": 7,
        "repository_result_parent_inode": 8,
        "repository_result_parent_mount_id": 9,
        "sequential_single_gpu_execution": True,
        "transformers_identity": "transformers==4.57.0",
    }


def _controls() -> dict[str, str]:
    return {
        "cloud_metadata_access": "DENIED",
        "credential_environment": "EMPTY",
        "dns": "UNAVAILABLE_TO_MODEL_PROCESS",
        "frozen_gold_scoring_inputs_visible_to_model_process": "NO",
        "host_or_container_control_sockets": "NONE",
        "model_and_runtime_input_mounts": "READ_ONLY_ALLOWLIST_ONLY",
        "network_egress": "DENY_ALL",
        "network_ingress": "DENY_ALL",
        "remote_fetch_during_model_process": "PROHIBITED",
        "writable_paths": "ACTIVATION_SCOPED_SCRATCH_AND_OUTPUT_ONLY",
    }


def _document(runtime_bytes: bytes) -> dict[str, object]:
    return {
        "artifact_version": "MESC-BT-PHI-SANDBOX-QUALIFICATION-ARTIFACT-V1",
        "controls": _controls(),
        "controls_active_before_model_load": True,
        "controls_active_before_remote_code_import": True,
        "dedicated_model_process": True,
        "producer_identity": "fixture-producer-1",
        "qualification_challenge": _CHALLENGE,
        "qualification_disposition": "PASS",
        "runtime_binding_sha256": hashlib.sha256(runtime_bytes).hexdigest(),
    }


def _fixture() -> tuple[bytes, dict[str, object]]:
    runtime_bytes = _canonical(_runtime())
    return runtime_bytes, _document(runtime_bytes)


def _verify(
    payload: bytes,
    runtime_bytes: bytes,
) -> PhiSandboxQualificationArtifact:
    return verify_phi_sandbox_qualification_artifact_fixture(payload, runtime_bytes)


def test_valid_artifact_is_canonical_digest_and_runtime_bound() -> None:
    runtime_bytes, document = _fixture()
    payload = _canonical(document)

    artifact = _verify(payload, runtime_bytes)

    assert artifact.canonical_bytes == payload
    assert artifact.sha256 == hashlib.sha256(payload).hexdigest()
    assert artifact.runtime_binding_sha256 == hashlib.sha256(runtime_bytes).hexdigest()
    assert artifact.qualification_challenge == _CHALLENGE
    assert artifact.producer_identity == "fixture-producer-1"


@pytest.mark.parametrize(
    ("payload", "match"),
    [
        (b"{", "not valid JSON"),
        (b"[]", "top level"),
        (b'{"x":NaN}', "non-standard JSON constant"),
        (_OVERSIZED_INTEGER_JSON, "not valid JSON"),
        (_DEEPLY_NESTED_JSON, "not valid JSON"),
    ],
)
def test_json_envelope_is_fail_closed(payload: bytes, match: str) -> None:
    runtime_bytes, _ = _fixture()

    with pytest.raises(PhiSandboxQualificationArtifactFixtureError, match=match):
        _verify(payload, runtime_bytes)


def test_bom_trailing_newline_whitespace_and_escaped_ascii_are_noncanonical() -> None:
    runtime_bytes, document = _fixture()
    payload = _canonical(document)
    variants = (
        b"\xef\xbb\xbf" + payload,
        payload + b"\n",
        payload.replace(b"{", b"{ ", 1),
        payload.replace(b"fixture-producer-1", b"fixture-producer\\u002d1"),
    )

    for variant in variants:
        with pytest.raises(PhiSandboxQualificationArtifactFixtureError):
            _verify(variant, runtime_bytes)


def test_duplicate_members_are_rejected_at_any_depth() -> None:
    runtime_bytes, _ = _fixture()
    payloads = (
        b'{"artifact_version":"x","artifact_version":"x"}',
        b'{"controls":{"dns":"x","dns":"x"}}',
    )

    for payload in payloads:
        with pytest.raises(
            PhiSandboxQualificationArtifactFixtureError,
            match="duplicate JSON member",
        ):
            _verify(payload, runtime_bytes)


def test_top_level_member_set_is_exact() -> None:
    runtime_bytes, document = _fixture()

    missing = dict(document)
    missing.pop("producer_identity")
    extra = dict(document)
    extra["activation_id"] = "0" * 64

    for candidate in (missing, extra):
        with pytest.raises(
            PhiSandboxQualificationArtifactFixtureError,
            match="top-level member set/order",
        ):
            _verify(_canonical(candidate), runtime_bytes)


def test_controls_member_set_is_exact() -> None:
    runtime_bytes, document = _fixture()
    controls = cast(dict[str, str], document["controls"])

    missing = dict(document)
    missing_controls = dict(controls)
    missing_controls.pop("dns")
    missing["controls"] = missing_controls

    extra = dict(document)
    extra_controls = dict(controls)
    extra_controls["process_uid"] = "1234"
    extra["controls"] = extra_controls

    for candidate in (missing, extra):
        with pytest.raises(
            PhiSandboxQualificationArtifactFixtureError,
            match="controls member set/order",
        ):
            _verify(_canonical(candidate), runtime_bytes)


def test_noncanonical_key_order_is_rejected() -> None:
    runtime_bytes, document = _fixture()
    items = list(document.items())
    reordered = dict([items[1], items[0], *items[2:]])
    payload = json.dumps(
        reordered,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=False,
    ).encode("ascii")

    with pytest.raises(
        PhiSandboxQualificationArtifactFixtureError,
        match=r"top-level member set/order|canonical",
    ):
        _verify(payload, runtime_bytes)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("artifact_version", "OTHER", "artifact_version"),
        ("controls_active_before_model_load", False, "controls_active_before_model_load"),
        ("controls_active_before_model_load", 1, "controls_active_before_model_load"),
        (
            "controls_active_before_remote_code_import",
            False,
            "controls_active_before_remote_code_import",
        ),
        ("dedicated_model_process", False, "dedicated_model_process"),
        ("qualification_disposition", "FAIL", "qualification_disposition"),
    ],
)
def test_frozen_top_level_controls_are_exact(field: str, value: object, match: str) -> None:
    runtime_bytes, document = _fixture()
    document[field] = value

    with pytest.raises(PhiSandboxQualificationArtifactFixtureError, match=match):
        _verify(_canonical(document), runtime_bytes)


@pytest.mark.parametrize("producer", ["", " bad", "producer name", "x" * 257, 7])
def test_producer_identity_grammar_is_fail_closed(producer: object) -> None:
    runtime_bytes, document = _fixture()
    document["producer_identity"] = producer

    with pytest.raises(
        PhiSandboxQualificationArtifactFixtureError,
        match="producer_identity",
    ):
        _verify(_canonical(document), runtime_bytes)


@pytest.mark.parametrize("challenge", ["bad", "A" * 64, 7])
def test_qualification_challenge_grammar_is_fail_closed(challenge: object) -> None:
    runtime_bytes, document = _fixture()
    document["qualification_challenge"] = challenge

    with pytest.raises(
        PhiSandboxQualificationArtifactFixtureError,
        match="qualification_challenge",
    ):
        _verify(_canonical(document), runtime_bytes)


@pytest.mark.parametrize("control", list(_controls()))
def test_every_frozen_isolation_control_value_is_exact(control: str) -> None:
    runtime_bytes, document = _fixture()
    controls = cast(dict[str, str], document["controls"])
    controls[control] = "WRONG"

    with pytest.raises(
        PhiSandboxQualificationArtifactFixtureError,
        match=f"control value mismatch: {control}",
    ):
        _verify(_canonical(document), runtime_bytes)


@pytest.mark.parametrize(
    "bad_runtime",
    [
        b"",
        b"{}",
        b"{}\n",
        b"\xef\xbb\xbf{}",
        _OVERSIZED_INTEGER_JSON,
        _DEEPLY_NESTED_JSON,
    ],
)
def test_runtime_binding_must_pass_canonical_activation_validator(bad_runtime: bytes) -> None:
    _, document = _fixture()

    with pytest.raises(
        PhiSandboxQualificationArtifactFixtureError,
        match="runtime binding is not canonical",
    ):
        _verify(_canonical(document), bad_runtime)


def test_runtime_binding_digest_is_recomputed_from_exact_validated_bytes() -> None:
    runtime_bytes, document = _fixture()
    changed_runtime = _runtime()
    changed_runtime["provider_instance_or_pod_id"] = "fixture-pod-2"
    changed_runtime_bytes = _canonical(changed_runtime)

    assert changed_runtime_bytes != runtime_bytes
    with pytest.raises(
        PhiSandboxQualificationArtifactFixtureError,
        match="runtime_binding_sha256 does not reproduce",
    ):
        _verify(_canonical(document), changed_runtime_bytes)


@pytest.mark.parametrize("runtime_digest", ["bad", "A" * 64, 7])
def test_runtime_binding_digest_grammar_is_fail_closed(runtime_digest: object) -> None:
    runtime_bytes, document = _fixture()
    document["runtime_binding_sha256"] = runtime_digest

    with pytest.raises(
        PhiSandboxQualificationArtifactFixtureError,
        match="runtime_binding_sha256",
    ):
        _verify(_canonical(document), runtime_bytes)
