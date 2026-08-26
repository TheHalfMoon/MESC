"""Fail-closed MESC training-authorization receipt validator.

Validates explicitly supplied founder/operator authorization material into a
content-addressed receipt bound to a pre-authorization readiness subject, validated
runtime qualification, and canonical corpus binding. The receipt deliberately does not
bind post-launch local-asset attestation, avoiding circular authority dependencies. This
module never executes training.
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
    authorization_subject_sha256: str
    runtime_qualification_sha256: str
    corpus_binding_sha256: str
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
        _require_text(self.authorizer_id, field="authorizer_id")
        _require_text(self.authorization_statement, field="authorization_statement")
        for field_name, value in (
            ("authorization_subject_sha256", self.authorization_subject_sha256),
            ("runtime_qualification_sha256", self.runtime_qualification_sha256),
            ("corpus_binding_sha256", self.corpus_binding_sha256),
        ):
            _require_sha256(value, field=field_name)
        if type(self.real_training_authorized) is not bool:
            raise TrainingAuthorizationReceiptError(
                "real_training_authorized must be an exact bool"
            )
        if type(self.blockers) is not tuple:
            raise TrainingAuthorizationReceiptError("blockers must be an exact tuple")
        if any(type(item) is not str or not item for item in self.blockers):
            raise TrainingAuthorizationReceiptError(
                "blockers must contain exact non-empty strings only"
            )

        if self.disposition == "AUTHORIZED":
            if self.blockers:
                raise TrainingAuthorizationReceiptError(
                    "AUTHORIZED receipts cannot retain blockers"
                )
            if not self.real_training_authorized:
                raise TrainingAuthorizationReceiptError(
                    "AUTHORIZED receipts require real_training_authorized=true"
                )
        else:
            if not self.blockers:
                raise TrainingAuthorizationReceiptError(
                    "BLOCKED receipts must record blockers"
                )
            if self.real_training_authorized:
                raise TrainingAuthorizationReceiptError(
                    "BLOCKED receipts forbid real_training_authorized=true"
                )

    @property
    def receipt_sha256(self) -> str:
        """Return the opaque digest bound into the final readiness manifest."""
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "authorization_scope": self.authorization_scope,
            "authorization_statement": self.authorization_statement,
            "authorization_subject_sha256": self.authorization_subject_sha256,
            "authorizer_id": self.authorizer_id,
            "blockers": list(self.blockers),
            "corpus_binding_sha256": self.corpus_binding_sha256,
            "disposition": self.disposition,
            "program_version": self.program_version,
            "real_training_authorized": self.real_training_authorized,
            "runtime_qualification_sha256": self.runtime_qualification_sha256,
        }


def build_training_authorization_receipt(
    *,
    authorizer_id: str,
    authorization_subject_sha256: str,
    runtime_qualification_sha256: str,
    corpus_binding_sha256: str,
    authorization_statement: str,
    authorization_scope: AuthorizationScope = _SCOPE,
    authorize: bool,
) -> TrainingAuthorizationReceipt:
    """Validate explicit authorization material into a content-addressed receipt.

    ``authorize=True`` is an explicit input and never defaults on. Calling this builder is
    not itself proof that an operator was authorized to supply that input; downstream
    readiness still validates the receipt against the exact readiness subject, runtime
    qualification, and corpus binding before launch can be admitted.
    """
    _require_text(authorizer_id, field="authorizer_id")
    _require_text(authorization_statement, field="authorization_statement")
    if authorization_scope != _SCOPE:
        raise TrainingAuthorizationReceiptError(
            "authorization_scope must be exactly TRAINING_EXECUTION"
        )
    _require_sha256(
        authorization_subject_sha256,
        field="authorization_subject_sha256",
    )
    _require_sha256(runtime_qualification_sha256, field="runtime_qualification_sha256")
    _require_sha256(corpus_binding_sha256, field="corpus_binding_sha256")
    if type(authorize) is not bool:
        raise TrainingAuthorizationReceiptError("authorize must be an exact bool")

    blockers: list[str] = []
    if not authorize:
        blockers.append("explicit authorize=true was not supplied")

    disposition: TrainingAuthorizationDisposition = "BLOCKED" if blockers else "AUTHORIZED"
    return TrainingAuthorizationReceipt(
        disposition=disposition,
        authorization_scope=authorization_scope,
        authorizer_id=authorizer_id.strip(),
        authorization_subject_sha256=authorization_subject_sha256,
        runtime_qualification_sha256=runtime_qualification_sha256,
        corpus_binding_sha256=corpus_binding_sha256,
        authorization_statement=authorization_statement.strip(),
        real_training_authorized=disposition == "AUTHORIZED",
        blockers=tuple(blockers),
    )


def _require_text(value: object, *, field: str) -> str:
    if type(value) is not str or not value.strip() or "\x00" in value:
        raise TrainingAuthorizationReceiptError(
            f"{field} must be exact non-empty NUL-free text"
        )
    return value.strip()


def _require_sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise TrainingAuthorizationReceiptError(
            f"{field} must be exactly 64 lowercase hex characters"
        )
    return value


__all__ = [
    "AuthorizationScope",
    "TrainingAuthorizationDisposition",
    "TrainingAuthorizationReceipt",
    "TrainingAuthorizationReceiptError",
    "build_training_authorization_receipt",
]
