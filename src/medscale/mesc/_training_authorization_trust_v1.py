"""Repository-controlled trust roots for MESC training authorization.

Authorization artifacts are not trusted because a caller supplies well-formed bytes. A
positive training authorization must additionally match an artifact digest provisioned in
this registry by a separate canonical repository-governance change. The production
registry intentionally starts empty: repository code alone grants no real training
authority.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Final

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

TRUST_REGISTRY_VERSION: Final = "MESC-TRAINING-AUTHORIZATION-TRUST-REGISTRY-V1"

# Production trust root. Keep empty until a separately reviewed, founder-authenticated
# canonical governance change provisions an exact authorization artifact digest. Tests
# may replace this exact frozenset only through the private lock-aware helper below.
TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256: frozenset[str] = frozenset()

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_REGISTRY_KIND: Final = "mesc.training_authorization.trust_registry.v1"
_REGISTRY_LOCK: Final = Lock()


class TrainingAuthorizationTrustError(RuntimeError):
    """Raised when canonical training-authorization trust cannot be validated."""


@dataclass(frozen=True, slots=True)
class TrainingAuthorizationTrustSnapshot:
    """One immutable, self-consistent view of the canonical authorization registry."""

    registry_version: str
    trusted_authorization_artifact_sha256: frozenset[str]
    registry_sha256: str

    def admits(self, value: str) -> bool:
        """Return whether this exact snapshot admits one artifact digest."""
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            return False
        return value in self.trusted_authorization_artifact_sha256


def training_authorization_trust_snapshot() -> TrainingAuthorizationTrustSnapshot:
    """Capture one validated immutable registry snapshot under the registry lock."""
    with _REGISTRY_LOCK:
        return _validated_registry_snapshot_unlocked()


def is_trusted_training_authorization_artifact_sha256(value: str) -> bool:
    """Return whether an exact artifact digest is present in one canonical snapshot."""
    return training_authorization_trust_snapshot().admits(value)


def training_authorization_trust_registry_sha256() -> str:
    """Return a deterministic identity for one exact canonical trust snapshot."""
    return training_authorization_trust_snapshot().registry_sha256


def validate_training_authorization_trust(
    *,
    expected_registry_sha256: str,
    artifact_sha256: str,
) -> TrainingAuthorizationTrustSnapshot:
    """Validate registry identity and artifact membership against one snapshot."""
    snapshot = training_authorization_trust_snapshot()
    _require_snapshot_admission(
        snapshot,
        expected_registry_sha256=expected_registry_sha256,
        artifact_sha256=artifact_sha256,
    )
    return snapshot


@contextmanager
def hold_training_authorization_trust(
    *,
    expected_registry_sha256: str,
    artifact_sha256: str,
) -> Iterator[TrainingAuthorizationTrustSnapshot]:
    """Hold one valid admission snapshot stable across a backend admission boundary.

    Canonical runtime code does not mutate trust in process. The lock additionally makes
    the repository-supported test mutation path serialize with the final executor guard,
    so a revocation cannot interleave between the last trust check and backend invocation.
    """
    with _REGISTRY_LOCK:
        snapshot = _validated_registry_snapshot_unlocked()
        _require_snapshot_admission(
            snapshot,
            expected_registry_sha256=expected_registry_sha256,
            artifact_sha256=artifact_sha256,
        )
        yield snapshot


def _require_snapshot_admission(
    snapshot: TrainingAuthorizationTrustSnapshot,
    *,
    expected_registry_sha256: str,
    artifact_sha256: str,
) -> None:
    if type(expected_registry_sha256) is not str or _SHA256.fullmatch(expected_registry_sha256) is None:
        raise TrainingAuthorizationTrustError(
            "expected authorization trust registry identity must be 64 lowercase hex characters"
        )
    if type(artifact_sha256) is not str or _SHA256.fullmatch(artifact_sha256) is None:
        raise TrainingAuthorizationTrustError(
            "authorization artifact identity must be 64 lowercase hex characters"
        )
    if snapshot.registry_sha256 != expected_registry_sha256:
        raise TrainingAuthorizationTrustError(
            "authorization trust registry changed after receipt admission"
        )
    if not snapshot.admits(artifact_sha256):
        raise TrainingAuthorizationTrustError(
            "authorization artifact is no longer trusted by the canonical registry"
        )


def _validated_registry_snapshot_unlocked() -> TrainingAuthorizationTrustSnapshot:
    registry = TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256
    if type(registry) is not frozenset:
        raise TrainingAuthorizationTrustError(
            "training authorization trust registry must be an exact frozenset"
        )
    for value in registry:
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            raise TrainingAuthorizationTrustError(
                "training authorization trust registry entries must be 64 lowercase hex characters"
            )
    payload = {
        "kind": _REGISTRY_KIND,
        "registry_version": TRUST_REGISTRY_VERSION,
        "trusted_authorization_artifact_sha256": sorted(registry),
    }
    registry_sha256 = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return TrainingAuthorizationTrustSnapshot(
        registry_version=TRUST_REGISTRY_VERSION,
        trusted_authorization_artifact_sha256=registry,
        registry_sha256=registry_sha256,
    )


def _replace_training_authorization_trust_registry_for_tests(
    registry: frozenset[str],
) -> frozenset[str]:
    """Replace test trust under the same lock used by final backend admission."""
    if type(registry) is not frozenset:
        raise TypeError("test training authorization trust registry must be an exact frozenset")
    for value in registry:
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            raise ValueError(
                "test training authorization trust registry entries must be 64 lowercase hex characters"
            )
    with _REGISTRY_LOCK:
        previous = TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256
        globals()["TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256"] = registry
        return previous


__all__ = [
    "TRUST_REGISTRY_VERSION",
    "TrainingAuthorizationTrustError",
    "TrainingAuthorizationTrustSnapshot",
    "hold_training_authorization_trust",
    "is_trusted_training_authorization_artifact_sha256",
    "training_authorization_trust_registry_sha256",
    "training_authorization_trust_snapshot",
    "validate_training_authorization_trust",
]
