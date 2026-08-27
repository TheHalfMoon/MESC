"""Repository-controlled trust roots for MRL research-input source permissions.

A source permission is not trusted merely because a caller can construct valid semantics.
Its exact content digest must also be provisioned by a separate canonical repository change.
The production registry intentionally starts empty, so this module alone grants no research
input, model, dataset, network, training, promotion, deployment, or clinical authority.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from threading import Lock
from typing import Final

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

TRUST_REGISTRY_VERSION: Final = "MRL-RESEARCH-INPUT-SOURCE-PERMISSION-TRUST-V1"
TRUSTED_RESEARCH_INPUT_SOURCE_PERMISSION_SHA256: frozenset[str] = frozenset()

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_REGISTRY_KIND: Final = "mesc.mrl.research_input_source_permission.trust_registry.v1"
_REGISTRY_LOCK: Final = Lock()


class ResearchInputPermissionTrustError(RuntimeError):
    """Raised when canonical research-input source-permission trust is invalid."""


@dataclass(frozen=True, slots=True)
class ResearchInputPermissionTrustSnapshot:
    """One validated immutable view of the canonical source-permission registry."""

    registry_version: str
    trusted_source_permission_sha256: frozenset[str]
    registry_sha256: str

    def admits(self, value: str) -> bool:
        """Return whether this exact snapshot admits one source-permission digest."""
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            return False
        return value in self.trusted_source_permission_sha256


def research_input_permission_trust_snapshot() -> ResearchInputPermissionTrustSnapshot:
    """Capture one validated immutable registry snapshot under the registry lock."""
    with _REGISTRY_LOCK:
        return _validated_registry_snapshot_unlocked()


def validate_research_input_source_permission_trust(
    permission_sha256: str,
) -> ResearchInputPermissionTrustSnapshot:
    """Require one exact source-permission digest in the current canonical registry."""
    if type(permission_sha256) is not str or _SHA256.fullmatch(permission_sha256) is None:
        raise ResearchInputPermissionTrustError(
            "source permission identity must be 64 lowercase hex characters"
        )
    snapshot = research_input_permission_trust_snapshot()
    if not snapshot.admits(permission_sha256):
        raise ResearchInputPermissionTrustError(
            "source permission is not trusted by the canonical registry"
        )
    return snapshot


def _validated_registry_snapshot_unlocked() -> ResearchInputPermissionTrustSnapshot:
    registry = TRUSTED_RESEARCH_INPUT_SOURCE_PERMISSION_SHA256
    if type(registry) is not frozenset:
        raise ResearchInputPermissionTrustError(
            "research-input source-permission trust registry must be an exact frozenset"
        )
    for value in registry:
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            raise ResearchInputPermissionTrustError(
                "research-input source-permission trust entries must be 64 lowercase hex characters"
            )
    payload = {
        "kind": _REGISTRY_KIND,
        "registry_version": TRUST_REGISTRY_VERSION,
        "trusted_source_permission_sha256": sorted(registry),
    }
    registry_sha256 = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return ResearchInputPermissionTrustSnapshot(
        registry_version=TRUST_REGISTRY_VERSION,
        trusted_source_permission_sha256=registry,
        registry_sha256=registry_sha256,
    )


def _replace_research_input_permission_trust_registry_for_tests(
    registry: frozenset[str],
) -> frozenset[str]:
    """Replace the test registry under the same lock used for production snapshots."""
    if type(registry) is not frozenset:
        raise TypeError("test source-permission trust registry must be an exact frozenset")
    for value in registry:
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            raise ValueError(
                "test source-permission trust entries must be 64 lowercase hex characters"
            )
    with _REGISTRY_LOCK:
        previous = TRUSTED_RESEARCH_INPUT_SOURCE_PERMISSION_SHA256
        globals()["TRUSTED_RESEARCH_INPUT_SOURCE_PERMISSION_SHA256"] = registry
        return previous


__all__ = [
    "TRUST_REGISTRY_VERSION",
    "ResearchInputPermissionTrustError",
    "ResearchInputPermissionTrustSnapshot",
    "research_input_permission_trust_snapshot",
    "validate_research_input_source_permission_trust",
]
