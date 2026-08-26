"""Test-only lifetime support for synthetic training-authorization trust."""

from __future__ import annotations

import hashlib

from medscale.mesc import _training_authorization_trust_v1 as authorization_trust

_TRUST_CLEANUPS: list[frozenset[str]] = []


def install_training_authorization_test_trust(artifact: bytes) -> None:
    """Trust one synthetic artifact until the current pytest test finishes."""
    digest = hashlib.sha256(artifact).hexdigest()
    trusted = authorization_trust.TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256 | frozenset(
        {digest}
    )
    previous = authorization_trust._replace_training_authorization_trust_registry_for_tests(trusted)
    _TRUST_CLEANUPS.append(previous)


def restore_training_authorization_test_trust() -> None:
    """Restore all temporary registry replacements in reverse installation order."""
    while _TRUST_CLEANUPS:
        previous = _TRUST_CLEANUPS.pop()
        authorization_trust._replace_training_authorization_trust_registry_for_tests(previous)
