from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from medscale.mesc._bt_activation_identity_fixture_v1 import (
    DECISION_ID,
    EXTERNAL_RUNTIME_PARENT_PATH,
    GPU_MODEL_H100,
    PROVIDER_CLASS,
    RECEIPT_VERSION,
    FixtureActivationBlockedError,
    IndependentActivationBindings,
    qualify_fixture_activation_identity,
)

SHA_A = "a" * 40
SHA_B = "b" * 40
SHA_C = "c" * 40
SHA_D = "d" * 40
SHA_E = "e" * 40
H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
H4 = "4" * 64
H5 = "5" * 64
H6 = "6" * 64
H7 = "7" * 64


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
        "repository_checkout_sha": SHA_A,
        "repository_checkout_tree": SHA_B,
        "repository_result_parent_device_id": 7,
        "repository_result_parent_inode": 8,
        "repository_result_parent_mount_id": 9,
        "sequential_single_gpu_execution": True,
        "transformers_identity": "transformers==4.57.0",
    }


def _independent() -> IndependentActivationBindings:
    return IndependentActivationBindings(
        authorization_merge_sha=SHA_C,
        authorization_merge_tree=SHA_D,
        execution_code_sha=SHA_E,
        execution_code_tree=SHA_A,
        executor_allowlist_sha256=H1,
        founder_attestation_comment_id=101,
        gated_access_decision_merge_sha=SHA_B,
        gated_access_founder_attestation_comment_id=202,
        apertus_access_attestation_sha256=H2,
        medgemma_access_attestation_sha256=H3,
        phi_remote_code_manifest_sha256=H4,
        phi_remote_code_security_review_sha256=H5,
        phi_sandbox_qualification_sha256=H6,
        telemetry_qualification_sha256=H7,
        repository_checkout_sha=SHA_A,
        repository_checkout_tree=SHA_B,
    )


def _identity(runtime_digest: str) -> dict[str, object]:
    independent = _independent()
    return {
        "apertus_access_attestation_sha256": (independent.apertus_access_attestation_sha256),
        "authorization_merge_sha": independent.authorization_merge_sha,
        "authorization_merge_tree": independent.authorization_merge_tree,
        "decision_id": DECISION_ID,
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
        "receipt_version": RECEIPT_VERSION,
        "runtime_binding_sha256": runtime_digest,
        "telemetry_qualification_sha256": independent.telemetry_qualification_sha256,
    }


def _qualified_inputs() -> tuple[bytes, bytes, IndependentActivationBindings]:
    runtime_bytes = _canonical(_runtime())
    runtime_digest = hashlib.sha256(runtime_bytes).hexdigest()
    identity_bytes = _canonical(_identity(runtime_digest))
    return runtime_bytes, identity_bytes, _independent()


def test_valid_fixture_derives_activation_id_and_roots() -> None:
    runtime_bytes, identity_bytes, independent = _qualified_inputs()
    result = qualify_fixture_activation_identity(
        runtime_bytes,
        identity_bytes,
        independent,
    )
    expected_activation_id = hashlib.sha256(identity_bytes).hexdigest()
    assert result.runtime_binding_sha256 == hashlib.sha256(runtime_bytes).hexdigest()
    assert result.activation_id == expected_activation_id
    assert result.external_runtime_root == (f"/workspace/mesc-bt-exec-1/{expected_activation_id}/")
    assert result.repository_result_root == (
        f"specs/mesc-backbone-tournament/execution-result-1/{expected_activation_id}/"
    )


def test_activation_identity_is_deterministic() -> None:
    runtime_bytes, identity_bytes, independent = _qualified_inputs()
    first = qualify_fixture_activation_identity(
        runtime_bytes,
        identity_bytes,
        independent,
    )
    second = qualify_fixture_activation_identity(
        runtime_bytes,
        identity_bytes,
        independent,
    )
    assert first == second


@pytest.mark.parametrize("raw", [b"", b"\xef\xbb\xbf{}", b"{}\n", b"{}\r\n"])
def test_runtime_envelope_invalid_bytes_block(raw: bytes) -> None:
    _, identity_bytes, independent = _qualified_inputs()
    with pytest.raises(FixtureActivationBlockedError):
        qualify_fixture_activation_identity(raw, identity_bytes, independent)


def test_runtime_duplicate_member_blocks() -> None:
    runtime_bytes, identity_bytes, independent = _qualified_inputs()
    text = runtime_bytes.decode("ascii")
    injected = text[:-1] + ',"gpu_count":1}'
    with pytest.raises(FixtureActivationBlockedError, match="duplicate JSON member"):
        qualify_fixture_activation_identity(
            injected.encode("ascii"),
            identity_bytes,
            independent,
        )


def test_identity_duplicate_member_blocks() -> None:
    runtime_bytes, identity_bytes, independent = _qualified_inputs()
    text = identity_bytes.decode("ascii")
    injected = text[:-1] + f',"decision_id":"{DECISION_ID}"}}'
    with pytest.raises(FixtureActivationBlockedError, match="duplicate JSON member"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            injected.encode("ascii"),
            independent,
        )


def test_runtime_noncanonical_whitespace_blocks() -> None:
    runtime_bytes, identity_bytes, independent = _qualified_inputs()
    modified = runtime_bytes.replace(b'":', b'": ', 1)
    with pytest.raises(FixtureActivationBlockedError, match="not canonical JSON"):
        qualify_fixture_activation_identity(modified, identity_bytes, independent)


def test_identity_noncanonical_escape_blocks() -> None:
    runtime_bytes, identity_bytes, independent = _qualified_inputs()
    modified = identity_bytes.replace(b"FD-MESC", b"FD\\u002dMESC", 1)
    with pytest.raises(FixtureActivationBlockedError, match="not canonical JSON"):
        qualify_fixture_activation_identity(runtime_bytes, modified, independent)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("gpu_count", 2, "gpu_count"),
        ("gpu_model", "NVIDIA H100", "gpu_model"),
        ("provider_class", "Other Cloud", "provider_class"),
        ("sequential_single_gpu_execution", False, "sequential_single_gpu_execution"),
        ("external_runtime_parent_path", "/workspace/other", "external runtime parent"),
    ],
)
def test_runtime_exact_invariants_block(
    field: str,
    value: object,
    message: str,
) -> None:
    runtime = _runtime()
    runtime[field] = value
    runtime_bytes = _canonical(runtime)
    identity_bytes = _canonical(_identity(hashlib.sha256(runtime_bytes).hexdigest()))
    with pytest.raises(FixtureActivationBlockedError, match=message):
        qualify_fixture_activation_identity(
            runtime_bytes,
            identity_bytes,
            _independent(),
        )


@pytest.mark.parametrize(
    "path",
    [
        "/Workspace/mesc",
        "/workspace//mesc",
        "/workspace/../mesc",
        "/workspace/.hidden",
        "/workspace/mesc/",
        r"C:\workspace\mesc",
        "/workspace/mésc",
    ],
)
def test_checkout_root_path_grammar_blocks(path: str) -> None:
    runtime = _runtime()
    runtime["repository_checkout_root_path"] = path
    runtime_bytes = _canonical(runtime)
    identity_bytes = _canonical(_identity(hashlib.sha256(runtime_bytes).hexdigest()))
    with pytest.raises(
        FixtureActivationBlockedError,
        match="repository_checkout_root_path",
    ):
        qualify_fixture_activation_identity(
            runtime_bytes,
            identity_bytes,
            _independent(),
        )


def test_runtime_identity_order_blocks() -> None:
    runtime = _runtime()
    runtime["acceleration_runtime_identities"] = ["torch:2.9", "cuda:13.0"]
    runtime_bytes = _canonical(runtime)
    identity_bytes = _canonical(_identity(hashlib.sha256(runtime_bytes).hexdigest()))
    with pytest.raises(FixtureActivationBlockedError, match="byte-sorted"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            identity_bytes,
            _independent(),
        )


def test_runtime_identity_duplicate_blocks() -> None:
    runtime = _runtime()
    runtime["acceleration_runtime_identities"] = ["cuda:13.0", "cuda:13.0"]
    runtime_bytes = _canonical(runtime)
    identity_bytes = _canonical(_identity(hashlib.sha256(runtime_bytes).hexdigest()))
    with pytest.raises(FixtureActivationBlockedError, match="unique"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            identity_bytes,
            _independent(),
        )


def test_runtime_identity_prohibited_ascii_blocks() -> None:
    runtime = _runtime()
    runtime["gpu_uuid"] = "GPU\\fixture"
    runtime_bytes = _canonical(runtime)
    identity_bytes = _canonical(_identity(hashlib.sha256(runtime_bytes).hexdigest()))
    with pytest.raises(FixtureActivationBlockedError, match="prohibited ASCII byte"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            identity_bytes,
            _independent(),
        )


def test_boolean_integer_field_blocks() -> None:
    runtime = _runtime()
    runtime["repository_checkout_root_inode"] = True
    runtime_bytes = _canonical(runtime)
    identity_bytes = _canonical(_identity(hashlib.sha256(runtime_bytes).hexdigest()))
    with pytest.raises(FixtureActivationBlockedError, match="integer >= 0"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            identity_bytes,
            _independent(),
        )


def test_runtime_checkout_sha_binding_mismatch_blocks() -> None:
    runtime_bytes, identity_bytes, independent = _qualified_inputs()
    with pytest.raises(FixtureActivationBlockedError, match="checkout SHA"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            identity_bytes,
            replace(independent, repository_checkout_sha=SHA_C),
        )


def test_runtime_checkout_tree_binding_mismatch_blocks() -> None:
    runtime_bytes, identity_bytes, independent = _qualified_inputs()
    with pytest.raises(FixtureActivationBlockedError, match="checkout tree"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            identity_bytes,
            replace(independent, repository_checkout_tree=SHA_C),
        )


@pytest.mark.parametrize(
    "changed",
    [
        replace(_independent(), authorization_merge_sha=SHA_A),
        replace(_independent(), authorization_merge_tree=SHA_A),
        replace(_independent(), execution_code_sha=SHA_A),
        replace(_independent(), execution_code_tree=SHA_B),
        replace(_independent(), executor_allowlist_sha256=H2),
        replace(_independent(), founder_attestation_comment_id=999),
        replace(_independent(), gated_access_decision_merge_sha=SHA_A),
        replace(_independent(), gated_access_founder_attestation_comment_id=999),
        replace(_independent(), apertus_access_attestation_sha256=H3),
        replace(_independent(), medgemma_access_attestation_sha256=H4),
        replace(_independent(), phi_remote_code_manifest_sha256=H5),
        replace(_independent(), phi_remote_code_security_review_sha256=H6),
        replace(_independent(), phi_sandbox_qualification_sha256=H7),
        replace(_independent(), telemetry_qualification_sha256=H1),
    ],
)
def test_independent_identity_binding_mismatch_blocks(
    changed: IndependentActivationBindings,
) -> None:
    runtime_bytes, identity_bytes, _ = _qualified_inputs()
    with pytest.raises(
        FixtureActivationBlockedError,
        match="identity binding mismatch",
    ):
        qualify_fixture_activation_identity(
            runtime_bytes,
            identity_bytes,
            changed,
        )


def test_runtime_digest_binding_mismatch_blocks() -> None:
    runtime_bytes, _, independent = _qualified_inputs()
    identity_bytes = _canonical(_identity("f" * 64))
    with pytest.raises(
        FixtureActivationBlockedError,
        match="runtime_binding_sha256",
    ):
        qualify_fixture_activation_identity(
            runtime_bytes,
            identity_bytes,
            independent,
        )


def test_wrong_decision_id_blocks() -> None:
    runtime_bytes, _, independent = _qualified_inputs()
    runtime_digest = hashlib.sha256(runtime_bytes).hexdigest()
    identity = _identity(runtime_digest)
    identity["decision_id"] = "FD-MESC-BT-EXEC-1-ACTIVATION-X"
    with pytest.raises(FixtureActivationBlockedError, match="decision_id"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            _canonical(identity),
            independent,
        )


def test_wrong_receipt_version_blocks() -> None:
    runtime_bytes, _, independent = _qualified_inputs()
    runtime_digest = hashlib.sha256(runtime_bytes).hexdigest()
    identity = _identity(runtime_digest)
    identity["receipt_version"] = "MESC-BT-EXEC-1-ACTIVATION-RECEIPT-V2"
    with pytest.raises(FixtureActivationBlockedError, match="receipt_version"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            _canonical(identity),
            independent,
        )


def test_boolean_comment_id_blocks() -> None:
    runtime_bytes, _, independent = _qualified_inputs()
    runtime_digest = hashlib.sha256(runtime_bytes).hexdigest()
    identity = _identity(runtime_digest)
    identity["founder_attestation_comment_id"] = True
    with pytest.raises(FixtureActivationBlockedError, match="integer >= 1"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            _canonical(identity),
            independent,
        )


def test_extra_identity_member_blocks() -> None:
    runtime_bytes, _, independent = _qualified_inputs()
    runtime_digest = hashlib.sha256(runtime_bytes).hexdigest()
    identity = _identity(runtime_digest)
    identity["unexpected"] = H1
    with pytest.raises(FixtureActivationBlockedError, match="key set/order"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            _canonical(identity),
            independent,
        )


def test_missing_runtime_member_blocks() -> None:
    runtime = _runtime()
    runtime.pop("provider_region")
    runtime_bytes = _canonical(runtime)
    identity_bytes = _canonical(_identity(hashlib.sha256(runtime_bytes).hexdigest()))
    with pytest.raises(FixtureActivationBlockedError, match="key set/order"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            identity_bytes,
            _independent(),
        )


def test_invalid_independent_hash_blocks_before_comparison() -> None:
    runtime_bytes, identity_bytes, independent = _qualified_inputs()
    with pytest.raises(FixtureActivationBlockedError, match="invalid string form"):
        qualify_fixture_activation_identity(
            runtime_bytes,
            identity_bytes,
            replace(independent, executor_allowlist_sha256="ABC"),
        )
