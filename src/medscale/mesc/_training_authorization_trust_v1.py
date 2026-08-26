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
from typing import Final

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

TRUST_REGISTRY_VERSION: Final = "MESC-TRAINING-AUTHORIZATION-TRUST-REGISTRY-V1"

# Production trust root. Keep empty until a separately reviewed, founder-authenticated
# canonical governance change provisions an exact authorization artifact digest.
TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256: Final[frozenset[str]] = frozenset()

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_REGISTRY_KIND: Final = "mesc.training_authorization.trust_registry.v1"


def is_trusted_training_authorization_artifact_sha256(value: str) -> bool:
    """Return whether an exact artifact digest is present in the canonical trust registry."""
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        return False
    return value in _validated_registry()


def training_authorization_trust_registry_sha256() -> str:
    """Return a deterministic identity for the exact repository-controlled trust registry."""
    payload = {
        "kind": _REGISTRY_KIND,
        "registry_version": TRUST_REGISTRY_VERSION,
        "trusted_authorization_artifact_sha256": sorted(_validated_registry()),
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _validated_registry() -> frozenset[str]:
    registry = TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256
    if type(registry) is not frozenset:
        raise RuntimeError("training authorization trust registry must be an exact frozenset")
    for value in registry:
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            raise RuntimeError(
                "training authorization trust registry entries must be 64 lowercase hex characters"
            )
    return registry


__all__ = [
    "TRUST_REGISTRY_VERSION",
    "is_trusted_training_authorization_artifact_sha256",
    "training_authorization_trust_registry_sha256",
]
