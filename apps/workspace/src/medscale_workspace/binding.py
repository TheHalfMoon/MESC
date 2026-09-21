"""Immutable object binding and canonical AEAD associated data for CW-002.

ADR-0039 decision 2, as amended by A1.4, binds at least the workspace id, object
id, object type, immutable object/revision identity, key version and
encryption-format version as associated data. The encoding below is the only
admitted encoding, so a ciphertext cannot be relocated to another workspace,
object, object type, revision, key version or format version undetected.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from medscale_workspace.errors import ObjectBindingError
from medscale_workspace.identity import WorkspaceObjectType

ASSOCIATED_DATA_DOMAIN = "mesc-clinical-workspace-object-aad/1"
MAXIMUM_REVISION_LENGTH = 128
MAXIMUM_REVISION_BYTES = 128


def _admit_revision(raw_revision: str) -> str:
    if not isinstance(raw_revision, str):
        raise ObjectBindingError("object revision must be a string")
    revision = raw_revision.strip()
    if not revision:
        raise ObjectBindingError("object revision must be non-empty")
    if len(revision) > MAXIMUM_REVISION_LENGTH:
        raise ObjectBindingError("object revision is longer than the admitted maximum")
    if not revision.isascii():
        raise ObjectBindingError("object revision must be ASCII")
    if len(revision.encode("ascii")) > MAXIMUM_REVISION_BYTES:
        raise ObjectBindingError("object revision exceeds the admitted byte length")
    for character in revision:
        if character.isspace() or not character.isprintable():
            raise ObjectBindingError("object revision must not contain whitespace or controls")
    return revision


@dataclass(frozen=True, slots=True)
class ObjectBinding:
    """The immutable identity an encrypted object payload is bound to."""

    workspace_id: UUID
    object_id: UUID
    object_type: WorkspaceObjectType
    object_revision: str

    def validated(self) -> ObjectBinding:
        """Return an equivalent binding after admitting every AAD component."""

        if not isinstance(self.workspace_id, UUID) or not isinstance(self.object_id, UUID):
            raise ObjectBindingError("workspace id and object id must be UUID values")
        if not isinstance(self.object_type, WorkspaceObjectType):
            raise ObjectBindingError("object type must be a WorkspaceObjectType member")
        return ObjectBinding(
            workspace_id=self.workspace_id,
            object_id=self.object_id,
            object_type=self.object_type,
            object_revision=_admit_revision(self.object_revision),
        )

    def canonical_associated_data(
        self,
        *,
        key_version: int,
        encryption_format_version: int,
    ) -> bytes:
        """Return the canonical associated data for this binding and key version."""

        if not isinstance(key_version, int) or key_version < 1:
            raise ObjectBindingError("key version must be a positive integer")
        if not isinstance(encryption_format_version, int) or encryption_format_version < 1:
            raise ObjectBindingError("encryption format version must be a positive integer")
        document = {
            "domain": ASSOCIATED_DATA_DOMAIN,
            "encryption_format_version": encryption_format_version,
            "key_version": key_version,
            "object_id": str(self.object_id),
            "object_revision": self.object_revision,
            "object_type": self.object_type.value,
            "workspace_id": str(self.workspace_id),
        }
        encoded = json.dumps(
            document,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return encoded.encode("ascii")
