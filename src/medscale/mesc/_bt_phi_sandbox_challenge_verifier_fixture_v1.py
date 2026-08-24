"""Fixture-only Phi sandbox qualification challenge lifecycle verification.

This module models the verifier-owned ``ISSUED -> CONSUMED/CANCELLED`` freshness
state required by ``MESC-BT-PHI-SANDBOX-QUALIFICATION-ARTIFACT-V1``. It uses an
in-memory opaque fixture invocation identity and verifier-owned CSPRNG challenge
issuance, then reuses the canonical fixture artifact verifier before consuming a
record.

It does not start or observe a producer process, configure or inspect a sandbox,
prove challenge-to-live-process timing, access real Phi source or model weights,
import or execute remote code, serialize prompts, run inference, rank/select a
winner, execute the Backbone Tournament, train, fine-tune, or grant execution
authority.
"""

from __future__ import annotations

import re
import secrets
from dataclasses import dataclass, replace
from threading import Lock
from typing import Final, Literal

from medscale.mesc._bt_phi_sandbox_qualification_artifact_fixture_v1 import (
    PhiSandboxQualificationArtifact,
    PhiSandboxQualificationArtifactFixtureError,
    verify_phi_sandbox_qualification_artifact_fixture,
)

ChallengeStatus = Literal["ISSUED", "CONSUMED", "CANCELLED"]

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_PRODUCER: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@/-]{0,255}$")


class PhiSandboxChallengeFixtureError(ValueError):
    """Fail-closed fixture challenge lifecycle verification error."""


class PhiSandboxProducerInvocationFixture:
    """Opaque identity token standing in for one producer invocation in fixture tests."""

    __slots__ = ()


@dataclass(frozen=True, slots=True)
class _ChallengeRecord:
    challenge: str
    runtime_binding_sha256: str
    producer_identity: str
    producer_invocation: PhiSandboxProducerInvocationFixture
    status: ChallengeStatus


class PhiSandboxChallengeVerifierFixture:
    """Current-process-only fixture ledger for one-shot sandbox freshness challenges."""

    __slots__ = ("_by_invocation", "_lock", "_records")

    def __init__(self) -> None:
        self._lock = Lock()
        self._records: dict[str, _ChallengeRecord] = {}
        self._by_invocation: dict[PhiSandboxProducerInvocationFixture, str] = {}

    def issue(
        self,
        *,
        runtime_binding_sha256: str,
        producer_identity: str,
        producer_invocation: PhiSandboxProducerInvocationFixture,
    ) -> str:
        """Issue one verifier-owned 32-byte CSPRNG challenge for a fixture invocation.

        This fixture API accepts the already-fixed runtime-binding digest rather than
        producing or validating live runtime evidence. A separate activation/runtime
        producer remains required before any live activation reliance.
        """
        runtime_digest = _require_sha256(
            runtime_binding_sha256,
            field="runtime_binding_sha256",
        )
        producer = _require_producer_identity(producer_identity)
        _require_invocation(producer_invocation)

        challenge_bytes = secrets.token_bytes(32)
        if type(challenge_bytes) is not bytes or len(challenge_bytes) != 32:
            raise PhiSandboxChallengeFixtureError(
                "verifier CSPRNG must return exactly 32 built-in bytes"
            )
        challenge = challenge_bytes.hex()
        if _SHA256.fullmatch(challenge) is None:
            raise PhiSandboxChallengeFixtureError(
                "verifier CSPRNG challenge encoding is not exactly 64 lowercase hex characters"
            )

        with self._lock:
            if producer_invocation in self._by_invocation:
                raise PhiSandboxChallengeFixtureError(
                    "fixture producer invocation already has challenge history"
                )
            if challenge in self._records:
                raise PhiSandboxChallengeFixtureError(
                    "verifier CSPRNG challenge collides with existing current-process history"
                )
            record = _ChallengeRecord(
                challenge=challenge,
                runtime_binding_sha256=runtime_digest,
                producer_identity=producer,
                producer_invocation=producer_invocation,
                status="ISSUED",
            )
            self._records[challenge] = record
            self._by_invocation[producer_invocation] = challenge
        return challenge

    def consume(
        self,
        *,
        artifact_payload: bytes,
        runtime_binding_bytes: bytes,
        producer_invocation: PhiSandboxProducerInvocationFixture,
    ) -> PhiSandboxQualificationArtifact:
        """Validate and atomically consume the current fixture invocation challenge.

        Any artifact-conformance failure or bound-field mismatch cancels the still
        issued record before returning a fail-closed error. Replays cannot observe a
        second PASS because only an ``ISSUED`` record may transition to ``CONSUMED``.
        """
        _require_invocation(producer_invocation)
        challenge, initial_record = self._issued_record_for_invocation(producer_invocation)

        try:
            artifact = verify_phi_sandbox_qualification_artifact_fixture(
                artifact_payload,
                runtime_binding_bytes,
            )
        except PhiSandboxQualificationArtifactFixtureError as error:
            self._cancel_if_still_issued(challenge, initial_record)
            raise PhiSandboxChallengeFixtureError(
                "sandbox qualification artifact conformance failed; issued challenge cancelled"
            ) from error

        with self._lock:
            current = self._records.get(challenge)
            if current != initial_record or current.status != "ISSUED":
                raise PhiSandboxChallengeFixtureError(
                    "challenge is no longer the same current ISSUED record"
                )
            if current.producer_invocation is not producer_invocation:
                self._records[challenge] = replace(current, status="CANCELLED")
                raise PhiSandboxChallengeFixtureError(
                    "challenge is bound to a different fixture producer invocation"
                )
            if artifact.qualification_challenge != current.challenge:
                self._records[challenge] = replace(current, status="CANCELLED")
                raise PhiSandboxChallengeFixtureError(
                    "artifact qualification_challenge does not match the ISSUED record"
                )
            if artifact.runtime_binding_sha256 != current.runtime_binding_sha256:
                self._records[challenge] = replace(current, status="CANCELLED")
                raise PhiSandboxChallengeFixtureError(
                    "artifact runtime binding does not match the ISSUED record"
                )
            if artifact.producer_identity != current.producer_identity:
                self._records[challenge] = replace(current, status="CANCELLED")
                raise PhiSandboxChallengeFixtureError(
                    "artifact producer identity does not match the ISSUED record"
                )

            self._records[challenge] = replace(current, status="CONSUMED")
        return artifact

    def cancel(self, producer_invocation: PhiSandboxProducerInvocationFixture) -> str:
        """Atomically cancel the one still-issued challenge for a fixture invocation."""
        _require_invocation(producer_invocation)
        with self._lock:
            challenge = self._by_invocation.get(producer_invocation)
            if challenge is None:
                raise PhiSandboxChallengeFixtureError(
                    "fixture producer invocation has no current-process challenge record"
                )
            record = self._records[challenge]
            if record.status != "ISSUED":
                raise PhiSandboxChallengeFixtureError(
                    f"challenge cannot be cancelled from status {record.status}"
                )
            self._records[challenge] = replace(record, status="CANCELLED")
        return challenge

    def status(self, challenge: str) -> ChallengeStatus | None:
        """Return immutable fixture status for a canonical challenge, or ``None`` if unknown."""
        canonical_challenge = _require_sha256(challenge, field="qualification_challenge")
        with self._lock:
            record = self._records.get(canonical_challenge)
            if record is None:
                return None
            return record.status

    def _issued_record_for_invocation(
        self,
        producer_invocation: PhiSandboxProducerInvocationFixture,
    ) -> tuple[str, _ChallengeRecord]:
        with self._lock:
            challenge = self._by_invocation.get(producer_invocation)
            if challenge is None:
                raise PhiSandboxChallengeFixtureError(
                    "fixture producer invocation has no current-process ISSUED record"
                )
            record = self._records[challenge]
            if record.status != "ISSUED":
                raise PhiSandboxChallengeFixtureError(
                    f"challenge is not ISSUED; current status is {record.status}"
                )
            return challenge, record

    def _cancel_if_still_issued(
        self,
        challenge: str,
        expected_record: _ChallengeRecord,
    ) -> None:
        with self._lock:
            current = self._records.get(challenge)
            if current == expected_record and current.status == "ISSUED":
                self._records[challenge] = replace(current, status="CANCELLED")


def _require_invocation(value: object) -> None:
    if type(value) is not PhiSandboxProducerInvocationFixture:
        raise PhiSandboxChallengeFixtureError(
            "producer_invocation must be an exact opaque fixture invocation token"
        )


def _require_sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise PhiSandboxChallengeFixtureError(
            f"{field} must be exactly 64 lowercase hex characters"
        )
    return value


def _require_producer_identity(value: object) -> str:
    if type(value) is not str or _PRODUCER.fullmatch(value) is None:
        raise PhiSandboxChallengeFixtureError("producer_identity violates the frozen grammar")
    return value
