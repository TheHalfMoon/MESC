"""Fail-closed MESC training-authorization receipt validator.

Validates an explicitly supplied founder/operator authorization artifact into a
content-addressed receipt bound to a pre-authorization readiness subject, validated
runtime qualification, and canonical corpus binding. The receipt deliberately does not
bind post-launch local-asset attestation, avoiding circular authority dependencies. This
module never executes training and never mints authorization from scalar arguments alone.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Final, Literal

from medscale.mesc import _training_authorization_trust_v1 as authorization_trust
from medscale.mesc._canonical_json_v1 import CanonicalContractError, canonical_json_bytes
from medscale.reproducibility import content_hash

TrainingAuthorizationDisposition = Literal["BLOCKED", "AUTHORIZED"]
AuthorizationScope = Literal["TRAINING_EXECUTION"]

_PROGRAM_VERSION: Final = "MESC-TRAINING-AUTHORIZATION-RECEIPT-V1"
_ARTIFACT_KIND: Final = "mesc.training_authorization.v1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_SCOPE: Final[AuthorizationScope] = "TRAINING_EXECUTION"
_ARTIFACT_KEYS: Final = frozenset(
    {
        "authorization_scope",
        "authorization_statement",
        "authorization_subject_sha256",
        "authorize",
        "authorizer_id",
        "corpus_binding_sha256",
        "kind",
        "runtime_qualification_sha256",
    }
)


class TrainingAuthorizationReceiptError(ValueError):
    """Raised when authorization evidence or a receipt cannot be validated fail-closed."""


@dataclass(frozen=True, slots=True)
class TrainingAuthorizationArtifact:
    """Canonical authorization bytes supplied out-of-band by a founder/operator."""

    canonical_bytes: bytes = field(repr=False)
    authorization_scope: AuthorizationScope = field(init=False)
    authorizer_id: str = field(init=False)
    authorization_subject_sha256: str = field(init=False)
    runtime_qualification_sha256: str = field(init=False)
    corpus_binding_sha256: str = field(init=False)
    authorization_statement: str = field(init=False)
    authorize: bool = field(init=False)

    def __post_init__(self) -> None:
        if type(self.canonical_bytes) is not bytes or not self.canonical_bytes:
            raise TrainingAuthorizationReceiptError(
                "authorization artifact must be non-empty exact bytes"
            )
        payload = _parse_authorization_payload(self.canonical_bytes)
        if payload["kind"] != _ARTIFACT_KIND:
            raise TrainingAuthorizationReceiptError(
                f"authorization artifact kind must be exactly {_ARTIFACT_KIND}"
            )
        scope = _require_scope(payload["authorization_scope"])
        authorizer_id = _require_artifact_text(payload["authorizer_id"], field="authorizer_id")
        statement = _require_artifact_text(
            payload["authorization_statement"], field="authorization_statement"
        )
        subject = _require_sha256(
            payload["authorization_subject_sha256"], field="authorization_subject_sha256"
        )
        runtime = _require_sha256(
            payload["runtime_qualification_sha256"], field="runtime_qualification_sha256"
        )
        corpus = _require_sha256(payload["corpus_binding_sha256"], field="corpus_binding_sha256")
        authorize = payload["authorize"]
        if type(authorize) is not bool:
            raise TrainingAuthorizationReceiptError(
                "authorization artifact authorize must be an exact bool"
            )

        object.__setattr__(self, "authorization_scope", scope)
        object.__setattr__(self, "authorizer_id", authorizer_id)
        object.__setattr__(self, "authorization_subject_sha256", subject)
        object.__setattr__(self, "runtime_qualification_sha256", runtime)
        object.__setattr__(self, "corpus_binding_sha256", corpus)
        object.__setattr__(self, "authorization_statement", statement)
        object.__setattr__(self, "authorize", authorize)

    @property
    def artifact_sha256(self) -> str:
        """Return SHA-256 over the exact validated artifact bytes."""
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def to_dict(self) -> dict[str, object]:
        """Return the validated semantic authorization payload."""
        return {
            "authorization_scope": self.authorization_scope,
            "authorization_statement": self.authorization_statement,
            "authorization_subject_sha256": self.authorization_subject_sha256,
            "authorize": self.authorize,
            "authorizer_id": self.authorizer_id,
            "corpus_binding_sha256": self.corpus_binding_sha256,
            "kind": _ARTIFACT_KIND,
            "runtime_qualification_sha256": self.runtime_qualification_sha256,
        }


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
    authorization_trust_registry_sha256: str | None = None
    authorization_artifact: TrainingAuthorizationArtifact | None = None
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
        if self.authorization_trust_registry_sha256 is not None:
            _require_sha256(
                self.authorization_trust_registry_sha256,
                field="authorization_trust_registry_sha256",
            )
        if self.authorization_artifact is not None and (
            type(self.authorization_artifact) is not TrainingAuthorizationArtifact
        ):
            raise TrainingAuthorizationReceiptError(
                "authorization_artifact must be an exact TrainingAuthorizationArtifact"
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
            if self.authorization_artifact is None:
                raise TrainingAuthorizationReceiptError(
                    "AUTHORIZED receipts require validated authorization artifact bytes"
                )
            _require_artifact_matches_receipt(self.authorization_artifact, self)
            if not self.authorization_artifact.authorize:
                raise TrainingAuthorizationReceiptError(
                    "AUTHORIZED receipt artifact must carry authorize=true"
                )
            expected_registry_sha256 = (
                authorization_trust.training_authorization_trust_registry_sha256()
            )
            if self.authorization_trust_registry_sha256 != expected_registry_sha256:
                raise TrainingAuthorizationReceiptError(
                    "AUTHORIZED receipt does not bind the canonical authorization trust registry"
                )
            if not authorization_trust.is_trusted_training_authorization_artifact_sha256(
                self.authorization_artifact.artifact_sha256
            ):
                raise TrainingAuthorizationReceiptError(
                    "AUTHORIZED receipt artifact is not present in the canonical trust registry"
                )
        else:
            if not self.blockers:
                raise TrainingAuthorizationReceiptError("BLOCKED receipts must record blockers")
            if self.real_training_authorized:
                raise TrainingAuthorizationReceiptError(
                    "BLOCKED receipts forbid real_training_authorized=true"
                )
            if self.authorization_trust_registry_sha256 is not None:
                raise TrainingAuthorizationReceiptError(
                    "BLOCKED receipts cannot claim an authorization trust registry"
                )
            if self.authorization_artifact is not None:
                _require_artifact_matches_receipt(self.authorization_artifact, self)
                if self.authorization_artifact.authorize:
                    raise TrainingAuthorizationReceiptError(
                        "BLOCKED receipt cannot bind an authorize=true artifact"
                    )

    def validate_current_trust(self) -> None:
        """Require this AUTHORIZED receipt to remain trusted by the current registry."""
        if self.disposition != "AUTHORIZED" or not self.real_training_authorized:
            raise TrainingAuthorizationReceiptError(
                "current-trust validation requires an AUTHORIZED receipt"
            )
        artifact = self.authorization_artifact
        if artifact is None:
            raise TrainingAuthorizationReceiptError(
                "AUTHORIZED receipt lacks validated authorization artifact bytes"
            )
        current_registry_sha256 = authorization_trust.training_authorization_trust_registry_sha256()
        if self.authorization_trust_registry_sha256 != current_registry_sha256:
            raise TrainingAuthorizationReceiptError(
                "authorization trust registry changed after receipt admission"
            )
        if not authorization_trust.is_trusted_training_authorization_artifact_sha256(
            artifact.artifact_sha256
        ):
            raise TrainingAuthorizationReceiptError(
                "authorization artifact is no longer trusted by the canonical registry"
            )

    @property
    def authorization_artifact_sha256(self) -> str | None:
        if self.authorization_artifact is None:
            return None
        return self.authorization_artifact.artifact_sha256

    @property
    def receipt_sha256(self) -> str:
        """Return the opaque digest bound into the final readiness manifest."""
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "authorization_artifact_sha256": self.authorization_artifact_sha256,
            "authorization_scope": self.authorization_scope,
            "authorization_statement": self.authorization_statement,
            "authorization_subject_sha256": self.authorization_subject_sha256,
            "authorization_trust_registry_sha256": (self.authorization_trust_registry_sha256),
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
    authorization_artifact: bytes | None = None,
) -> TrainingAuthorizationReceipt:
    """Validate supplied authorization material into a content-addressed receipt.

    ``authorize=True`` never creates authority by itself. An AUTHORIZED receipt requires
    separately supplied canonical ``authorization_artifact`` bytes whose exact semantic
    fields match every scalar binding and whose SHA-256 was independently provisioned in
    the repository-controlled trust registry. ``authorize=False`` remains fail-closed.
    """
    normalized_authorizer = _require_text(authorizer_id, field="authorizer_id")
    normalized_statement = _require_text(authorization_statement, field="authorization_statement")
    scope = _require_scope(authorization_scope)
    subject = _require_sha256(
        authorization_subject_sha256,
        field="authorization_subject_sha256",
    )
    runtime = _require_sha256(runtime_qualification_sha256, field="runtime_qualification_sha256")
    corpus = _require_sha256(corpus_binding_sha256, field="corpus_binding_sha256")
    if type(authorize) is not bool:
        raise TrainingAuthorizationReceiptError("authorize must be an exact bool")

    artifact: TrainingAuthorizationArtifact | None = None
    if authorization_artifact is not None:
        if type(authorization_artifact) is not bytes:
            raise TrainingAuthorizationReceiptError(
                "authorization_artifact must be exact bytes when supplied"
            )
        artifact = TrainingAuthorizationArtifact(authorization_artifact)
        expected = (
            ("authorization_scope", artifact.authorization_scope, scope),
            ("authorizer_id", artifact.authorizer_id, normalized_authorizer),
            (
                "authorization_subject_sha256",
                artifact.authorization_subject_sha256,
                subject,
            ),
            (
                "runtime_qualification_sha256",
                artifact.runtime_qualification_sha256,
                runtime,
            ),
            ("corpus_binding_sha256", artifact.corpus_binding_sha256, corpus),
            (
                "authorization_statement",
                artifact.authorization_statement,
                normalized_statement,
            ),
            ("authorize", artifact.authorize, authorize),
        )
        for field_name, observed, required in expected:
            if observed != required:
                raise TrainingAuthorizationReceiptError(
                    f"authorization artifact {field_name} does not match supplied binding"
                )

    if authorize and artifact is None:
        raise TrainingAuthorizationReceiptError(
            "authorize=true requires validated authorization_artifact bytes"
        )
    if (
        authorize
        and artifact is not None
        and not authorization_trust.is_trusted_training_authorization_artifact_sha256(
            artifact.artifact_sha256
        )
    ):
        raise TrainingAuthorizationReceiptError(
            "authorization artifact is not present in the canonical trusted authorization registry"
        )

    blockers: list[str] = []
    if not authorize:
        blockers.append("explicit authorize=true was not supplied")

    disposition: TrainingAuthorizationDisposition = "BLOCKED" if blockers else "AUTHORIZED"
    return TrainingAuthorizationReceipt(
        disposition=disposition,
        authorization_scope=scope,
        authorizer_id=normalized_authorizer,
        authorization_subject_sha256=subject,
        runtime_qualification_sha256=runtime,
        corpus_binding_sha256=corpus,
        authorization_statement=normalized_statement,
        real_training_authorized=disposition == "AUTHORIZED",
        blockers=tuple(blockers),
        authorization_trust_registry_sha256=(
            authorization_trust.training_authorization_trust_registry_sha256()
            if disposition == "AUTHORIZED"
            else None
        ),
        authorization_artifact=artifact,
    )


def _parse_authorization_payload(payload_bytes: bytes) -> dict[str, object]:
    try:
        text = payload_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise TrainingAuthorizationReceiptError(
            "authorization artifact is not valid UTF-8"
        ) from exc
    try:
        value = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_nonfinite_constant,
        )
    except TrainingAuthorizationReceiptError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError, RecursionError) as exc:
        raise TrainingAuthorizationReceiptError("authorization artifact is not valid JSON") from exc
    if type(value) is not dict:
        raise TrainingAuthorizationReceiptError("authorization artifact must be one JSON object")
    if set(value) != _ARTIFACT_KEYS:
        raise TrainingAuthorizationReceiptError(
            "authorization artifact must contain exactly the canonical field set"
        )
    try:
        canonical = canonical_json_bytes(value)
    except (CanonicalContractError, TypeError, ValueError, RecursionError) as exc:
        raise TrainingAuthorizationReceiptError(
            "authorization artifact cannot be canonicalized"
        ) from exc
    if canonical != payload_bytes:
        raise TrainingAuthorizationReceiptError(
            "authorization artifact bytes are not canonical JSON"
        )
    return value


def _reject_duplicate_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise TrainingAuthorizationReceiptError(
                f"authorization artifact contains duplicate key: {key}"
            )
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str) -> object:
    raise TrainingAuthorizationReceiptError(
        f"authorization artifact contains non-standard JSON constant: {value}"
    )


def _require_artifact_matches_receipt(
    artifact: TrainingAuthorizationArtifact,
    receipt: TrainingAuthorizationReceipt,
) -> None:
    comparisons = (
        (artifact.authorization_scope, receipt.authorization_scope),
        (artifact.authorizer_id, receipt.authorizer_id),
        (artifact.authorization_subject_sha256, receipt.authorization_subject_sha256),
        (artifact.runtime_qualification_sha256, receipt.runtime_qualification_sha256),
        (artifact.corpus_binding_sha256, receipt.corpus_binding_sha256),
        (artifact.authorization_statement, receipt.authorization_statement),
    )
    if any(observed != required for observed, required in comparisons):
        raise TrainingAuthorizationReceiptError(
            "authorization artifact does not match receipt bindings"
        )


def _require_scope(value: object) -> AuthorizationScope:
    if value != _SCOPE:
        raise TrainingAuthorizationReceiptError(
            "authorization_scope must be exactly TRAINING_EXECUTION"
        )
    return _SCOPE


def _require_artifact_text(value: object, *, field: str) -> str:
    normalized = _require_text(value, field=field)
    if value != normalized:
        raise TrainingAuthorizationReceiptError(
            f"authorization artifact {field} must not contain surrounding whitespace"
        )
    return normalized


def _require_text(value: object, *, field: str) -> str:
    if type(value) is not str or not value.strip() or "\x00" in value:
        raise TrainingAuthorizationReceiptError(f"{field} must be exact non-empty NUL-free text")
    return value.strip()


def _require_sha256(value: object, *, field: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise TrainingAuthorizationReceiptError(
            f"{field} must be exactly 64 lowercase hex characters"
        )
    return value


__all__ = [
    "AuthorizationScope",
    "TrainingAuthorizationArtifact",
    "TrainingAuthorizationDisposition",
    "TrainingAuthorizationReceipt",
    "TrainingAuthorizationReceiptError",
    "build_training_authorization_receipt",
]
