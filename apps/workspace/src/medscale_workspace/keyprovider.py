"""Platform key-provider abstraction for CW-002.

ADR-0039 decision 4 and amendment A1.7 require an abstraction that declares its
explicit capabilities, no weak cross-platform adapter created merely to claim
platform support, and fail-closed behaviour when protected secret storage is
unsupported or unavailable.

CW-002 implements no platform protected-secret-storage binding: on Windows that
would require ``ctypes``/DPAPI, which the CW-001/CW-002 boundary guard prohibits,
and inventing a weaker cross-platform substitute is exactly what A1.7 forbids. The
production resolver therefore returns an explicitly unavailable provider, and the
store refuses to open rather than persisting key material in plaintext or a weakly
protected file.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from uuid import UUID

from medscale_workspace.errors import (
    KeyMaterialUnavailableError,
    KeyProviderUnavailableError,
)
from medscale_workspace.keyderive import (
    DERIVED_KEY_SIZE_BYTES,
    ROOT_SECRET_MINIMUM_BYTES,
    SALT_SIZE_BYTES,
    derive_workspace_key,
)

ROOT_SECRET_SIZE_BYTES = ROOT_SECRET_MINIMUM_BYTES


@dataclass(frozen=True, slots=True)
class KeyProviderCapabilities:
    """The capabilities a key provider declares about itself."""

    identifier: str
    protected_secret_storage: bool
    available: bool
    derivable_key_material: bool
    persistent: bool
    production_selectable: bool
    notes: str


class KeyProvider:
    """Base class: every capability is declared, and every default fails closed."""

    capabilities: KeyProviderCapabilities

    def require_available(self) -> None:
        """Raise when this provider cannot supply key material at all."""

        raise KeyProviderUnavailableError(
            f"key provider {self.capabilities.identifier!r} is not available"
        )

    def key_for_version(self, *, workspace_id: UUID, key_version: int, salt: bytes) -> bytes:
        """Return the data-encryption key for one workspace and key version."""

        raise KeyMaterialUnavailableError(
            f"key provider {self.capabilities.identifier!r} cannot derive key version {key_version}"
        )


class InMemoryTestKeyProvider(KeyProvider):
    """Derivation-capable test provider that never touches disk or a secret store.

    It is constructed only by explicit import. It cannot be selected by
    configuration: the production resolver below cannot reach it, and the CW-002
    boundary guard rejects any reference to this class from that resolver.
    """

    capabilities = KeyProviderCapabilities(
        identifier="cw-002-in-memory-test",
        protected_secret_storage=False,
        available=True,
        derivable_key_material=True,
        persistent=False,
        production_selectable=False,
        notes="synthetic test root secret held in process memory only",
    )

    def __init__(self, root_secret: bytes) -> None:
        if not isinstance(root_secret, bytes) or len(root_secret) < ROOT_SECRET_MINIMUM_BYTES:
            raise ValueError("test root secret must be at least 32 bytes")
        self._root_secret = root_secret

    def require_available(self) -> None:
        return None

    def key_for_version(self, *, workspace_id: UUID, key_version: int, salt: bytes) -> bytes:
        derived = derive_workspace_key(
            root_secret=self._root_secret,
            workspace_id=workspace_id,
            salt=salt,
            key_version=key_version,
        )
        if len(derived) != DERIVED_KEY_SIZE_BYTES:
            raise KeyMaterialUnavailableError("derived key size is not the admitted size")
        return derived


class UnavailablePlatformKeyProvider(KeyProvider):
    """The production provider while no platform protected storage is implemented."""

    capabilities = KeyProviderCapabilities(
        identifier="cw-002-platform-unavailable",
        protected_secret_storage=False,
        available=False,
        derivable_key_material=False,
        persistent=False,
        production_selectable=True,
        notes=(
            "no platform protected-secret-storage binding is implemented in CW-002; "
            "unsupported protected storage fails closed"
        ),
    )


def resolve_platform_key_provider() -> KeyProvider:
    """Return the provider the production path must use.

    CW-002 has no platform protected-secret-storage implementation, so this
    resolver returns an unavailable provider and the store fails closed. The
    in-memory test provider is unreachable from here by design.
    """

    return UnavailablePlatformKeyProvider()


def new_root_secret() -> bytes:
    """Return a fresh high-entropy root secret (never persisted by the store)."""

    return secrets.token_bytes(ROOT_SECRET_SIZE_BYTES)


def new_salt() -> bytes:
    """Return a fresh per-key-version random salt."""

    return secrets.token_bytes(SALT_SIZE_BYTES)
