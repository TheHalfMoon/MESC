"""AES-256-GCM envelope encryption for CW-002.

This is the only Workspace module permitted to import the ``cryptography``
dependency, and it uses that dependency for the AEAD primitive only. Envelope
layout, header validation, nonce handling and associated-data construction remain
reviewed code in this package.

Nonce contract (ADR-0039 amendment A1.3): 96-bit, cryptographically random for
every encryption operation, never reused with the same key, and stored as part of
the envelope.

Envelope layout (format version 1):

```text
0   .. 8    magic            b"MSWSENV1"
8   .. 9    format version   1 byte
9   .. 13   key version      4 bytes, big-endian
13  .. 25   nonce            12 bytes
25  .. end  ciphertext       payload plus 16-byte GCM tag
```

AES-256-GCM authenticates objects. It does not, by itself, defeat a valid
historical whole-store rollback performed with a still-valid key; CW-002
implements no rollback detector and claims none (amendment A1.5).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from medscale_workspace.errors import (
    EnvelopeAuthenticationError,
    EnvelopeFormatError,
)
from medscale_workspace.versions import ENCRYPTION_FORMAT_VERSION

ENVELOPE_MAGIC = b"MSWSENV1"
NONCE_SIZE_BYTES = 12
TAG_SIZE_BYTES = 16
KEY_SIZE_BYTES = 32
SUPPORTED_ENCRYPTION_FORMAT_VERSIONS = (ENCRYPTION_FORMAT_VERSION,)

_MAGIC_SIZE_BYTES = len(ENVELOPE_MAGIC)
_FORMAT_VERSION_SIZE_BYTES = 1
_KEY_VERSION_SIZE_BYTES = 4
HEADER_SIZE_BYTES = (
    _MAGIC_SIZE_BYTES + _FORMAT_VERSION_SIZE_BYTES + _KEY_VERSION_SIZE_BYTES + NONCE_SIZE_BYTES
)
MINIMUM_ENVELOPE_SIZE_BYTES = HEADER_SIZE_BYTES + TAG_SIZE_BYTES


@dataclass(frozen=True, slots=True)
class EnvelopeHeader:
    """The visible, pre-decryption header of a CW-002 envelope."""

    encryption_format_version: int
    key_version: int
    nonce: bytes


def _admit_key(key: bytes) -> bytes:
    if not isinstance(key, bytes) or len(key) != KEY_SIZE_BYTES:
        raise EnvelopeFormatError("AEAD key must be exactly 32 bytes")
    return key


def new_nonce() -> bytes:
    """Return a fresh 96-bit cryptographically random nonce (A1.3)."""

    return secrets.token_bytes(NONCE_SIZE_BYTES)


def parse_envelope_header(envelope: bytes) -> EnvelopeHeader:
    """Validate and decode the visible envelope header without decrypting."""

    if not isinstance(envelope, bytes):
        raise EnvelopeFormatError("envelope must be bytes")
    if len(envelope) < MINIMUM_ENVELOPE_SIZE_BYTES:
        raise EnvelopeFormatError("envelope is shorter than the minimum admitted envelope")
    if envelope[:_MAGIC_SIZE_BYTES] != ENVELOPE_MAGIC:
        raise EnvelopeFormatError("envelope magic is not a CW-002 envelope")
    format_offset = _MAGIC_SIZE_BYTES
    format_version = envelope[format_offset]
    if format_version not in SUPPORTED_ENCRYPTION_FORMAT_VERSIONS:
        raise EnvelopeFormatError("envelope encryption format version is not supported")
    key_offset = format_offset + _FORMAT_VERSION_SIZE_BYTES
    key_version = int.from_bytes(envelope[key_offset : key_offset + _KEY_VERSION_SIZE_BYTES], "big")
    if key_version < 1:
        raise EnvelopeFormatError("envelope key version is not a positive integer")
    nonce_offset = key_offset + _KEY_VERSION_SIZE_BYTES
    nonce = envelope[nonce_offset : nonce_offset + NONCE_SIZE_BYTES]
    if len(nonce) != NONCE_SIZE_BYTES:
        raise EnvelopeFormatError("envelope nonce is not 96 bits")
    return EnvelopeHeader(
        encryption_format_version=format_version,
        key_version=key_version,
        nonce=nonce,
    )


def encrypt_payload(
    *,
    key: bytes,
    plaintext: bytes,
    associated_data: bytes,
    key_version: int,
) -> bytes:
    """Encrypt one payload into a CW-002 envelope under the given key version."""

    admitted_key = _admit_key(key)
    if not isinstance(plaintext, bytes):
        raise EnvelopeFormatError("plaintext must be bytes")
    if not isinstance(associated_data, bytes) or not associated_data:
        raise EnvelopeFormatError("associated data must be non-empty bytes")
    if not isinstance(key_version, int) or key_version < 1:
        raise EnvelopeFormatError("key version must be a positive integer")
    nonce = new_nonce()
    header = (
        ENVELOPE_MAGIC
        + bytes([ENCRYPTION_FORMAT_VERSION])
        + key_version.to_bytes(_KEY_VERSION_SIZE_BYTES, "big")
        + nonce
    )
    ciphertext = AESGCM(admitted_key).encrypt(nonce, plaintext, associated_data)
    return header + ciphertext


def decrypt_payload(
    *,
    envelope: bytes,
    key: bytes,
    associated_data: bytes,
) -> bytes:
    """Decrypt one CW-002 envelope, failing closed on any authentication failure."""

    admitted_key = _admit_key(key)
    if not isinstance(associated_data, bytes) or not associated_data:
        raise EnvelopeFormatError("associated data must be non-empty bytes")
    header = parse_envelope_header(envelope)
    ciphertext = envelope[HEADER_SIZE_BYTES:]
    try:
        plaintext = AESGCM(admitted_key).decrypt(header.nonce, ciphertext, associated_data)
    except Exception as error:
        raise EnvelopeAuthenticationError(
            "envelope authentication failed; the payload, its nonce or its binding changed"
        ) from error
    return plaintext
