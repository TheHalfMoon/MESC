"""Fail-closed MESC training-authorization receipt validator.

Canonicalizes an already-supplied founder/operator authorization artifact into
``training_authorization_receipt_sha256``. This module never mints authorization from
empty defaults and never executes training.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from medscale.reproducibility import content_hash

TrainingAuthorizationDisposition = Literal["BLOCKED", "AUTHORIZED"]
AuthorizationScope = Literal["TRAINING_EXECUTION"]

_PROGRAM_VERSION: Final = "MESC-TRAINING-AUTHORIZATION-RECEIPT-V1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_SCOPE: Final = "TRAINING_EXECUTION"


class TrainingAuthorizationReceiptError(ValueError):
    """Raised when an authorization receipt cannot be constructed fail-closed."""


@dataclass(frozen=True, slots=True)
class TrainingAuthorizationReceipt:
    """Content-addressed explicit training-authorization evidence."""

    disposition: TrainingAuthorizationDisposition
    authorization_scope: AuthorizationScope
    authorizer_id: str
    subject_readiness_manifest_sha256: str
    runtime_qualification_sha256: str
    corpus_binding_sha256: str
    local_asset_attestation_sha256: str
    authorization_statement: str
    real_training_authorized: bool
    blockers: tuple[str, ...]
    program_version: str = _PROGRAM_VERSION

    def __post_init__(self) -> None:
        if self.program_version != _PROGRAM_VERSION:
            raise TrainingAuthorizationReceiptError(
                f"program_version must be exactly {_PROGRAM_VERSION}"
            )
        if self.disposition not in ("BLOCKED", "AUTHORIZED"):
            raise TrainingAuthorizationReceiptError("disposition is invalid")
        if self.authorization_scope != _SCOPE:
            raise TrainingAuthorizationReceiptError(
                "authorization_scope must be exactly TRAINING_EXECUTION"
            )
        if not isinstance(self.authorizer_id, str) or not self.authorizer_id.strip():
            raise TrainingAuthorizationReceiptError("authorizer_id must be a non-empty string")
        if (
            not isinstance(self.authorization_statement, str)
            or not self.authorization_statement.strip()
        ):
            raise TrainingAuthorizationReceiptError(
                "authorization_statement must be a non-empty string"
            )
        for field, value in (
            ("subject_readiness_manifest_sha256", self.subject_readiness_manifest_sha256),
            ("runtime_qualification_sha256", self.runtime_qualification_sha256),
            ("corpus_binding_sha256", self.corpus_binding_sha256),
            ("local_asset_attestation_sha256", self.local_asset_attestation_sha256),
        ):
            _require_sha256(value, field=field)
        if type(self.real_training_authorized) is not bool:
            raise TrainingAuthorizationReceiptError("real_training_authorized must be a bool")
        if self.disposition == "AUTHORIZED":
            if self.blockers:
                raise TrainingAuthorizationReceiptError(
                    "AUTHORIZED receipts cannot retain blockers"
                )
            if not self.real_training_authorized:
                raise TrainingAuthorizationReceiptError(
                    "AUTHORIZED receipts require real_training_authorized=true"
                )
        if self.disposition == "BLOCKED":
            if not self.blockers:
                raise TrainingAuthorizationReceiptError("BLOCKED receipts must record blockers")
            if self.real_training_authorized:
                raise TrainingAuthorizationReceiptError(
                    "BLOCKED receipts forbid real_training_authorized=true"
                )

    @property
    def receipt_sha256(self) -> str:
        """Return the opaque digest bound into readiness/launch plans."""
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "authorization_scope": self.authorization_scope,
            "authorization_statement": self.authorization_statement,
            "authorizer_id": self.authorizer_id,
            "blockers": list(self.blockers),
            "corpus_binding_sha256": self.corpus_binding_sha256,
            "disposition": self.disposition,
            "local_asset_attestation_sha256": self.local_asset_attestation_sha256,
            "program_version": self.program_version,
            "real_training_authorized": self.real_training_authorized,
            "runtime_qualification_sha256": self.runtime_qualification_sha256,
            "subject_readiness_manifest_sha256": self.subject_readiness_manifest_sha256,
        }


def build_training_authorization_receipt(
    *,
    authorizer_id: str,
    subject_readiness_manifest_sha256: str,
    runtime_qualification_sha256: str,
    corpus_binding_sha256: str,
    local_asset_attestation_sha256: str,
    authorization_statement: str,
    authorization_scope: AuthorizationScope = _SCOPE,
    authorize: bool,
) -> TrainingAuthorizationReceipt:
    """Validate supplied authorization material into a content-addressed receipt.

    ``authorize=True`` is required to emit ``AUTHORIZED``. The builder never defaults to
    authorization and never invents missing identity digests.
    """
    if not isinstance(authorizer_id, str) or not authorizer_id.strip():
        raise TrainingAuthorizationReceiptError("authorizer_id must be a non-empty string")
    if not isinstance(authorization_statement, str) or not authorization_statement.strip():
        raise TrainingAuthorizationReceiptError(
            "authorization_statement must be a non-empty string"
        )
    if authorization_scope != _SCOPE:
        raise TrainingAuthorizationReceiptError(
            "authorization_scope must be exactly TRAINING_EXECUTION"
        )
    _require_sha256(
        subject_readiness_manifest_sha256,
        field="subject_readiness_manifest_sha256",
    )
    _require_sha256(runtime_qualification_sha256, field="runtime_qualification_sha256")
    _require_sha256(corpus_binding_sha256, field="corpus_binding_sha256")
    _require_sha256(local_asset_attestation_sha256, field="local_asset_attestation_sha256")
    if type(authorize) is not bool:
        raise TrainingAuthorizationReceiptError("authorize must be a bool")

    blockers: list[str] = []
    if not authorize:
        blockers.append("explicit authorize=true was not supplied")

    disposition: TrainingAuthorizationDisposition = "BLOCKED" if blockers else "AUTHORIZED"
    return TrainingAuthorizationReceipt(
        disposition=disposition,
        authorization_scope=authorization_scope,
        authorizer_id=authorizer_id.strip(),
        subject_readiness_manifest_sha256=subject_readiness_manifest_sha256,
        runtime_qualification_sha256=runtime_qualification_sha256,
        corpus_binding_sha256=corpus_binding_sha256,
        local_asset_attestation_sha256=local_asset_attestation_sha256,
        authorization_statement=authorization_statement.strip(),
        real_training_authorized=disposition == "AUTHORIZED",
        blockers=tuple(blockers),
    )


def _require_sha256(value: str, *, field: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise TrainingAuthorizationReceiptError(
            f"{field} must be exactly 64 lowercase hex characters"
        )


__all__ = [
    "AuthorizationScope",
    "TrainingAuthorizationDisposition",
    "TrainingAuthorizationReceipt",
    "TrainingAuthorizationReceiptError",
    "build_training_authorization_receipt",
]
