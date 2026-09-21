"""HKDF-SHA-256 key derivation for CW-002 (RFC 5869, reviewed local code).

ADR-0039 decision 5 keeps key derivation inside our own reviewed code, and
amendment A1.1 fixes the derivation function as HKDF-SHA-256 over a high-entropy
root secret. Amendment A1.2 reserves the memory-hard password-hashing family for a
future password/passphrase-derived root-key path; CW-002 implements no such path.

The workspace flag is bound into the derivation inputs together with an explicit
per-key-version random salt, so two workspaces and two key versions never share key
material.
"""

from __future__ import annotations

import hashlib
import hmac
from uuid import UUID

DERIVED_KEY_SIZE_BYTES = 32
ROOT_SECRET_MINIMUM_BYTES = 32
SALT_SIZE_BYTES = 16
KEY_DERIVATION_LABEL = "mesc-clinical-workspace-dek-hkdf-sha256/1"
_HASH = hashlib.sha256
_HASH_SIZE_BYTES = 32
_MAXIMUM_EXPAND_BLOCKS = 255


def hkdf_sha256_extract(*, salt: bytes, input_key_material: bytes) -> bytes:
    """RFC 5869 section 2.2 extract step.

    An empty salt is the RFC 5869 "salt not provided" case and expands to ``HashLen``
    zero bytes. CW-002's workspace derivation never uses an empty salt: the salt is
    the recorded per-key-version 16-byte random value.
    """

    if not input_key_material:
        raise ValueError("HKDF input key material must be non-empty")
    admitted_salt = salt if salt else b"\x00" * _HASH_SIZE_BYTES
    return hmac.new(admitted_salt, input_key_material, _HASH).digest()


def hkdf_sha256_expand(*, pseudorandom_key: bytes, info: bytes, length: int) -> bytes:
    """RFC 5869 section 2.3 expand step."""

    if len(pseudorandom_key) != _HASH_SIZE_BYTES:
        raise ValueError("HKDF pseudorandom key must be one SHA-256 output")
    if length <= 0 or length > _MAXIMUM_EXPAND_BLOCKS * _HASH_SIZE_BYTES:
        raise ValueError("HKDF output length is outside the RFC 5869 range")
    output = bytearray()
    previous_block = b""
    counter = 1
    while len(output) < length:
        previous_block = hmac.new(
            pseudorandom_key,
            previous_block + info + counter.to_bytes(1, "big"),
            _HASH,
        ).digest()
        output.extend(previous_block)
        counter += 1
    return bytes(output[:length])


def hkdf_sha256(*, salt: bytes, input_key_material: bytes, info: bytes, length: int) -> bytes:
    """Full RFC 5869 HKDF-SHA-256."""

    pseudorandom_key = hkdf_sha256_extract(
        salt=salt,
        input_key_material=input_key_material,
    )
    return hkdf_sha256_expand(
        pseudorandom_key=pseudorandom_key,
        info=info,
        length=length,
    )


def derive_workspace_key(
    *,
    root_secret: bytes,
    workspace_id: UUID,
    salt: bytes,
    key_version: int,
) -> bytes:
    """Derive the CW-002 data-encryption key for one workspace and key version."""

    if not isinstance(root_secret, bytes) or len(root_secret) < ROOT_SECRET_MINIMUM_BYTES:
        raise ValueError("root secret must be at least 32 high-entropy bytes")
    if not isinstance(salt, bytes) or len(salt) != SALT_SIZE_BYTES:
        raise ValueError("per-workspace salt must be exactly 16 bytes")
    if not isinstance(key_version, int) or key_version < 1:
        raise ValueError("key version must be a positive integer")
    if not isinstance(workspace_id, UUID):
        raise ValueError("workspace id must be a UUID value")
    info = (f"{KEY_DERIVATION_LABEL}|workspace={workspace_id}|key_version={key_version}").encode(
        "ascii"
    )
    return hkdf_sha256(
        salt=salt,
        input_key_material=root_secret,
        info=info,
        length=DERIVED_KEY_SIZE_BYTES,
    )
