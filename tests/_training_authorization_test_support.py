"""Test-only lifetime support for synthetic training-authorization trust."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from unittest.mock import patch

from medscale.mesc import _training_authorization_trust_v1 as authorization_trust

_TRUST_CLEANUPS: list[Callable[[], object]] = []


def install_training_authorization_test_trust(artifact: bytes) -> None:
    """Trust one synthetic artifact until the current pytest test finishes."""
    digest = hashlib.sha256(artifact).hexdigest()
    trusted = authorization_trust.TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256 | frozenset(
        {digest}
    )
    patcher = patch.object(
        authorization_trust,
        "TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256",
        trusted,
    )
    patcher.start()
    _TRUST_CLEANUPS.append(patcher.stop)


def restore_training_authorization_test_trust() -> None:
    """Restore all temporary registry patches in reverse installation order."""
    while _TRUST_CLEANUPS:
        _TRUST_CLEANUPS.pop()()
