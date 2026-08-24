"""Qualification tests for the fixture-only Phi sandbox challenge lifecycle."""

from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import cast

import pytest

from medscale.mesc import _bt_phi_sandbox_challenge_verifier_fixture_v1 as challenge_fixture
from medscale.mesc._bt_activation_identity_fixture_v1 import (
    EXTERNAL_RUNTIME_PARENT_PATH,
    GPU_MODEL_H100,
    PROVIDER_CLASS,
)
from medscale.mesc._bt_phi_sandbox_challenge_verifier_fixture_v1 import (
    PhiSandboxChallengeFixtureError,
    PhiSandboxChallengeVerifierFixture,
    PhiSandboxProducerInvocationFixture,
)

_SHA_A = "a" * 40
_SHA_B = "b" * 40
_TOKEN_BYTES_TARGET = (
    "medscale.mesc._bt_phi_sandbox_challenge_verifier_fixture_v1.secrets.token_bytes"
)


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")


def _runtime(*, pod: str = "fixture-pod") -> bytes:
    return _canonical(
        {
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
            "provider_instance_or_pod_id": pod,
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
    )


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


def _artifact(
    *,
    runtime_bytes: bytes,
    challenge: str,
    producer_identity: str = "fixture-producer-1",
) -> bytes:
    return _canonical(
        {
            "artifact_version": "MESC-BT-PHI-SANDBOX-QUALIFICATION-ARTIFACT-V1",
            "controls": _controls(),
            "controls_active_before_model_load": True,
            "controls_active_before_remote_code_import": True,
            "dedicated_model_process": True,
            "producer_identity": producer_identity,
            "qualification_challenge": challenge,
            "qualification_disposition": "PASS",
            "runtime_binding_sha256": hashlib.sha256(runtime_bytes).hexdigest(),
        }
    )


def _fixed_csprng(monkeypatch: pytest.MonkeyPatch, byte: int) -> str:
    raw = bytes([byte]) * 32
    monkeypatch.setattr(_TOKEN_BYTES_TARGET, lambda size: raw)
    return raw.hex()


def _issue(
    verifier: PhiSandboxChallengeVerifierFixture,
    invocation: PhiSandboxProducerInvocationFixture,
    runtime_bytes: bytes,
) -> str:
    return verifier.issue(
        runtime_binding_sha256=hashlib.sha256(runtime_bytes).hexdigest(),
        producer_identity="fixture-producer-1",
        producer_invocation=invocation,
    )


def test_issue_consume_is_one_shot_and_replay_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_challenge = _fixed_csprng(monkeypatch, 0xA1)
    verifier = PhiSandboxChallengeVerifierFixture()
    invocation = PhiSandboxProducerInvocationFixture()
    runtime_bytes = _runtime()

    challenge = _issue(verifier, invocation, runtime_bytes)
    assert challenge == expected_challenge
    assert verifier.status(challenge) == "ISSUED"

    payload = _artifact(runtime_bytes=runtime_bytes, challenge=challenge)
    artifact = verifier.consume(
        artifact_payload=payload,
        runtime_binding_bytes=runtime_bytes,
        producer_invocation=invocation,
    )

    assert artifact.canonical_bytes == payload
    assert artifact.qualification_challenge == challenge
    assert verifier.status(challenge) == "CONSUMED"

    with pytest.raises(PhiSandboxChallengeFixtureError, match="not ISSUED"):
        verifier.consume(
            artifact_payload=payload,
            runtime_binding_bytes=runtime_bytes,
            producer_invocation=invocation,
        )


def test_concurrent_consume_allows_exactly_one_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_challenge = _fixed_csprng(monkeypatch, 0xB0)
    verifier = PhiSandboxChallengeVerifierFixture()
    invocation = PhiSandboxProducerInvocationFixture()
    runtime_bytes = _runtime()
    challenge = _issue(verifier, invocation, runtime_bytes)
    assert challenge == expected_challenge
    payload = _artifact(runtime_bytes=runtime_bytes, challenge=challenge)

    barrier = Barrier(2)
    original_verify = challenge_fixture.verify_phi_sandbox_qualification_artifact_fixture

    def synchronized_verify(artifact_payload: bytes, runtime_binding_bytes: bytes) -> object:
        artifact = original_verify(artifact_payload, runtime_binding_bytes)
        barrier.wait()
        return artifact

    monkeypatch.setattr(
        challenge_fixture,
        "verify_phi_sandbox_qualification_artifact_fixture",
        synchronized_verify,
    )

    def consume_once() -> str:
        try:
            verifier.consume(
                artifact_payload=payload,
                runtime_binding_bytes=runtime_bytes,
                producer_invocation=invocation,
            )
        except PhiSandboxChallengeFixtureError as error:
            return str(error)
        return "PASS"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(consume_once) for _ in range(2)]
        outcomes = [future.result() for future in futures]

    assert outcomes.count("PASS") == 1
    failures = [outcome for outcome in outcomes if outcome != "PASS"]
    assert len(failures) == 1
    assert "no longer the same current ISSUED record" in failures[0]
    assert verifier.status(challenge) == "CONSUMED"


def test_issue_requires_exact_frozen_runtime_digest_and_producer_grammar(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_csprng(monkeypatch, 0xA2)
    verifier = PhiSandboxChallengeVerifierFixture()
    invocation = PhiSandboxProducerInvocationFixture()

    with pytest.raises(PhiSandboxChallengeFixtureError, match="runtime_binding_sha256"):
        verifier.issue(
            runtime_binding_sha256="A" * 64,
            producer_identity="fixture-producer-1",
            producer_invocation=invocation,
        )
    with pytest.raises(PhiSandboxChallengeFixtureError, match="producer_identity"):
        verifier.issue(
            runtime_binding_sha256="a" * 64,
            producer_identity="bad producer",
            producer_invocation=invocation,
        )


@pytest.mark.parametrize("raw", [b"", b"x" * 31, b"x" * 33])
def test_csprng_must_return_exactly_32_bytes(
    monkeypatch: pytest.MonkeyPatch,
    raw: bytes,
) -> None:
    monkeypatch.setattr(_TOKEN_BYTES_TARGET, lambda size: raw)
    verifier = PhiSandboxChallengeVerifierFixture()

    with pytest.raises(PhiSandboxChallengeFixtureError, match="exactly 32"):
        verifier.issue(
            runtime_binding_sha256="a" * 64,
            producer_identity="fixture-producer-1",
            producer_invocation=PhiSandboxProducerInvocationFixture(),
        )


def test_non_bytes_csprng_result_is_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def bad_token_bytes(size: int) -> bytes:
        del size
        return cast(bytes, bytearray(b"x" * 32))

    monkeypatch.setattr(_TOKEN_BYTES_TARGET, bad_token_bytes)
    verifier = PhiSandboxChallengeVerifierFixture()

    with pytest.raises(PhiSandboxChallengeFixtureError, match="built-in bytes"):
        verifier.issue(
            runtime_binding_sha256="a" * 64,
            producer_identity="fixture-producer-1",
            producer_invocation=PhiSandboxProducerInvocationFixture(),
        )


def test_csprng_collision_is_blocked_across_current_process_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_csprng(monkeypatch, 0xA3)
    verifier = PhiSandboxChallengeVerifierFixture()
    first = PhiSandboxProducerInvocationFixture()
    second = PhiSandboxProducerInvocationFixture()

    verifier.issue(
        runtime_binding_sha256="a" * 64,
        producer_identity="fixture-producer-1",
        producer_invocation=first,
    )
    with pytest.raises(PhiSandboxChallengeFixtureError, match="collides"):
        verifier.issue(
            runtime_binding_sha256="a" * 64,
            producer_identity="fixture-producer-1",
            producer_invocation=second,
        )


def test_invocation_history_cannot_be_reissued_after_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_csprng(monkeypatch, 0xA4)
    verifier = PhiSandboxChallengeVerifierFixture()
    invocation = PhiSandboxProducerInvocationFixture()
    challenge = verifier.issue(
        runtime_binding_sha256="a" * 64,
        producer_identity="fixture-producer-1",
        producer_invocation=invocation,
    )
    verifier.cancel(invocation)
    assert verifier.status(challenge) == "CANCELLED"

    with pytest.raises(PhiSandboxChallengeFixtureError, match="history"):
        verifier.issue(
            runtime_binding_sha256="a" * 64,
            producer_identity="fixture-producer-1",
            producer_invocation=invocation,
        )


def test_wrong_fixture_invocation_is_blocked_without_consuming_legitimate_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_csprng(monkeypatch, 0xA5)
    verifier = PhiSandboxChallengeVerifierFixture()
    issued_invocation = PhiSandboxProducerInvocationFixture()
    wrong_invocation = PhiSandboxProducerInvocationFixture()
    runtime_bytes = _runtime()
    challenge = _issue(verifier, issued_invocation, runtime_bytes)
    payload = _artifact(runtime_bytes=runtime_bytes, challenge=challenge)

    with pytest.raises(PhiSandboxChallengeFixtureError, match="no current-process ISSUED"):
        verifier.consume(
            artifact_payload=payload,
            runtime_binding_bytes=runtime_bytes,
            producer_invocation=wrong_invocation,
        )
    assert verifier.status(challenge) == "ISSUED"


def test_wrong_challenge_cancels_the_bound_issued_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_csprng(monkeypatch, 0xA6)
    verifier = PhiSandboxChallengeVerifierFixture()
    invocation = PhiSandboxProducerInvocationFixture()
    runtime_bytes = _runtime()
    challenge = _issue(verifier, invocation, runtime_bytes)
    payload = _artifact(runtime_bytes=runtime_bytes, challenge="b" * 64)

    with pytest.raises(PhiSandboxChallengeFixtureError, match="qualification_challenge"):
        verifier.consume(
            artifact_payload=payload,
            runtime_binding_bytes=runtime_bytes,
            producer_invocation=invocation,
        )
    assert verifier.status(challenge) == "CANCELLED"


def test_wrong_runtime_cancels_the_bound_issued_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_csprng(monkeypatch, 0xA7)
    verifier = PhiSandboxChallengeVerifierFixture()
    invocation = PhiSandboxProducerInvocationFixture()
    issued_runtime = _runtime(pod="fixture-pod-a")
    presented_runtime = _runtime(pod="fixture-pod-b")
    challenge = _issue(verifier, invocation, issued_runtime)
    payload = _artifact(runtime_bytes=presented_runtime, challenge=challenge)

    with pytest.raises(PhiSandboxChallengeFixtureError, match="runtime binding"):
        verifier.consume(
            artifact_payload=payload,
            runtime_binding_bytes=presented_runtime,
            producer_invocation=invocation,
        )
    assert verifier.status(challenge) == "CANCELLED"


def test_wrong_producer_identity_cancels_the_bound_issued_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_csprng(monkeypatch, 0xA8)
    verifier = PhiSandboxChallengeVerifierFixture()
    invocation = PhiSandboxProducerInvocationFixture()
    runtime_bytes = _runtime()
    challenge = _issue(verifier, invocation, runtime_bytes)
    payload = _artifact(
        runtime_bytes=runtime_bytes,
        challenge=challenge,
        producer_identity="fixture-producer-2",
    )

    with pytest.raises(PhiSandboxChallengeFixtureError, match="producer identity"):
        verifier.consume(
            artifact_payload=payload,
            runtime_binding_bytes=runtime_bytes,
            producer_invocation=invocation,
        )
    assert verifier.status(challenge) == "CANCELLED"


def test_artifact_rejection_cancels_the_bound_issued_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_csprng(monkeypatch, 0xA9)
    verifier = PhiSandboxChallengeVerifierFixture()
    invocation = PhiSandboxProducerInvocationFixture()
    runtime_bytes = _runtime()
    challenge = _issue(verifier, invocation, runtime_bytes)

    with pytest.raises(PhiSandboxChallengeFixtureError, match="conformance failed"):
        verifier.consume(
            artifact_payload=b"{",
            runtime_binding_bytes=runtime_bytes,
            producer_invocation=invocation,
        )
    assert verifier.status(challenge) == "CANCELLED"


def test_explicit_cancellation_blocks_late_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_csprng(monkeypatch, 0xAA)
    verifier = PhiSandboxChallengeVerifierFixture()
    invocation = PhiSandboxProducerInvocationFixture()
    runtime_bytes = _runtime()
    challenge = _issue(verifier, invocation, runtime_bytes)
    payload = _artifact(runtime_bytes=runtime_bytes, challenge=challenge)

    assert verifier.cancel(invocation) == challenge
    with pytest.raises(PhiSandboxChallengeFixtureError, match="CANCELLED"):
        verifier.consume(
            artifact_payload=payload,
            runtime_binding_bytes=runtime_bytes,
            producer_invocation=invocation,
        )


def test_prior_verifier_process_state_is_not_reconstructed_from_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_csprng(monkeypatch, 0xAB)
    prior_verifier = PhiSandboxChallengeVerifierFixture()
    invocation = PhiSandboxProducerInvocationFixture()
    runtime_bytes = _runtime()
    challenge = _issue(prior_verifier, invocation, runtime_bytes)
    payload = _artifact(runtime_bytes=runtime_bytes, challenge=challenge)

    restarted_verifier = PhiSandboxChallengeVerifierFixture()
    assert restarted_verifier.status(challenge) is None
    with pytest.raises(PhiSandboxChallengeFixtureError, match="no current-process ISSUED"):
        restarted_verifier.consume(
            artifact_payload=payload,
            runtime_binding_bytes=runtime_bytes,
            producer_invocation=invocation,
        )
    assert prior_verifier.status(challenge) == "ISSUED"


def test_detached_prior_artifact_is_blocked_even_when_runtime_digest_repeats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_bytes = _runtime()

    old_challenge = _fixed_csprng(monkeypatch, 0xAC)
    old_verifier = PhiSandboxChallengeVerifierFixture()
    old_invocation = PhiSandboxProducerInvocationFixture()
    assert _issue(old_verifier, old_invocation, runtime_bytes) == old_challenge
    detached_payload = _artifact(runtime_bytes=runtime_bytes, challenge=old_challenge)

    new_challenge = _fixed_csprng(monkeypatch, 0xAD)
    new_verifier = PhiSandboxChallengeVerifierFixture()
    new_invocation = PhiSandboxProducerInvocationFixture()
    assert _issue(new_verifier, new_invocation, runtime_bytes) == new_challenge

    with pytest.raises(PhiSandboxChallengeFixtureError, match="qualification_challenge"):
        new_verifier.consume(
            artifact_payload=detached_payload,
            runtime_binding_bytes=runtime_bytes,
            producer_invocation=new_invocation,
        )
    assert new_verifier.status(new_challenge) == "CANCELLED"


def test_status_rejects_noncanonical_challenge_and_returns_none_for_unknown() -> None:
    verifier = PhiSandboxChallengeVerifierFixture()
    assert verifier.status("f" * 64) is None

    with pytest.raises(PhiSandboxChallengeFixtureError, match="qualification_challenge"):
        verifier.status("F" * 64)


def test_cancel_is_one_shot_and_consumed_record_cannot_be_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fixed_csprng(monkeypatch, 0xAE)
    verifier = PhiSandboxChallengeVerifierFixture()
    invocation = PhiSandboxProducerInvocationFixture()
    runtime_bytes = _runtime()
    challenge = _issue(verifier, invocation, runtime_bytes)
    payload = _artifact(runtime_bytes=runtime_bytes, challenge=challenge)

    verifier.consume(
        artifact_payload=payload,
        runtime_binding_bytes=runtime_bytes,
        producer_invocation=invocation,
    )
    with pytest.raises(PhiSandboxChallengeFixtureError, match="CONSUMED"):
        verifier.cancel(invocation)


def test_invocation_token_requires_exact_fixture_type(monkeypatch: pytest.MonkeyPatch) -> None:
    _fixed_csprng(monkeypatch, 0xAF)
    verifier = PhiSandboxChallengeVerifierFixture()

    with pytest.raises(PhiSandboxChallengeFixtureError, match="opaque fixture invocation token"):
        verifier.issue(
            runtime_binding_sha256="a" * 64,
            producer_identity="fixture-producer-1",
            producer_invocation=cast(PhiSandboxProducerInvocationFixture, object()),
        )
