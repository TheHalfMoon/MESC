"""Immutable repository-controlled trust root for MRL research-input permissions.

A caller cannot create research-input authority by constructing well-formed permission
semantics. Public admission gates consult one immutable trust snapshot captured from
canonical repository code at import time. The canonical registry intentionally starts
empty, so this module grants no research-input, model, dataset, network, training,
promotion, deployment, or clinical authority.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

TRUST_REGISTRY_VERSION: Final = "MRL-RESEARCH-INPUT-SOURCE-PERMISSION-TRUST-V1"

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_REGISTRY_KIND: Final = "mesc.mrl.research_input_source_permission.trust_registry.v1"


class ResearchInputPermissionTrustError(RuntimeError):
    """Raised when canonical research-input source-permission trust is invalid."""


@dataclass(frozen=True, slots=True)
class ResearchInputPermissionTrustSnapshot:
    """One immutable canonical source-permission trust snapshot."""

    registry_version: str
    trusted_source_permission_sha256: frozenset[str]
    registry_sha256: str

    def admits(self, value: str) -> bool:
        """Return whether this exact snapshot admits one source-permission digest."""
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            return False
        return value in self.trusted_source_permission_sha256


def _validated_registry_snapshot(
    registry: frozenset[str],
) -> ResearchInputPermissionTrustSnapshot:
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
    return ResearchInputPermissionTrustSnapshot(
        registry_version=TRUST_REGISTRY_VERSION,
        trusted_source_permission_sha256=registry,
        registry_sha256=hashlib.sha256(canonical_json_bytes(payload)).hexdigest(),
    )


def _build_canonical_trust_api(
    registry: frozenset[str],
) -> tuple[
    Callable[[], ResearchInputPermissionTrustSnapshot],
    Callable[[str], ResearchInputPermissionTrustSnapshot],
]:
    """Bind public trust operations to one immutable registry snapshot."""
    canonical_snapshot = _validated_registry_snapshot(registry)

    def snapshot() -> ResearchInputPermissionTrustSnapshot:
        return canonical_snapshot

    def validate(permission_sha256: str) -> ResearchInputPermissionTrustSnapshot:
        if type(permission_sha256) is not str or _SHA256.fullmatch(permission_sha256) is None:
            raise ResearchInputPermissionTrustError(
                "source permission identity must be 64 lowercase hex characters"
            )
        if not canonical_snapshot.admits(permission_sha256):
            raise ResearchInputPermissionTrustError(
                "source permission is not trusted by the canonical registry"
            )
        return canonical_snapshot

    return snapshot, validate


(
    research_input_permission_trust_snapshot,
    validate_research_input_source_permission_trust,
) = _build_canonical_trust_api(frozenset())
del _build_canonical_trust_api


__all__ = [
    "TRUST_REGISTRY_VERSION",
    "ResearchInputPermissionTrustError",
    "ResearchInputPermissionTrustSnapshot",
    "research_input_permission_trust_snapshot",
    "validate_research_input_source_permission_trust",
]
