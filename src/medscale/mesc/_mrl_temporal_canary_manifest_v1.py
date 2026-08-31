"""R2-compatible temporal-canary manifest contract for MRL V1.

MRL-0605 defines metadata for synthetic or hand-authored temporal canaries created after
one frozen temporal boundary. It contains only immutable identities and timestamps; it does
not create canary content, access corpora, execute evaluators, or authorize training.
"""

from __future__ import annotations

import enum
import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.provenance import validate_timestamp

__all__ = [
    "TemporalCanaryManifest",
    "TemporalCanaryManifestError",
    "TemporalCanarySourceKind",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")


class TemporalCanaryManifestError(ValueError):
    """Fail-closed validation error for one MRL temporal-canary manifest."""


class TemporalCanarySourceKind(enum.Enum):
    SYNTHETIC = "SYNTHETIC"
    HAND_AUTHORED_FIXTURE = "HAND_AUTHORED_FIXTURE"


def _make_manifest_identity_registry() -> tuple[
    Callable[[TemporalCanaryManifest, str], None],
    Callable[[TemporalCanaryManifest], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: TemporalCanaryManifest, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise TemporalCanaryManifestError(
                "temporal canary construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: TemporalCanaryManifest) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise TemporalCanaryManifestError(
                "temporal canary construction identity is missing"
            )
        return identity

    return store, load


_store_manifest_identity, _load_manifest_identity = _make_manifest_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class TemporalCanaryManifest:
    """Immutable sealed canary identity created strictly after a frozen time boundary."""

    canary_id: str
    source_kind: TemporalCanarySourceKind
    canary_artifact_sha256: str
    temporal_boundary_at: str
    created_at: str
    evaluator_artifact_sha256: str
    topic_tags: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_token(self.canary_id, "canary_id")
        if type(self.source_kind) is not TemporalCanarySourceKind:
            raise TemporalCanaryManifestError(
                "source_kind must be an exact TemporalCanarySourceKind"
            )
        _require_sha256(self.canary_artifact_sha256, "canary_artifact_sha256")
        boundary = _timestamp(self.temporal_boundary_at, "temporal_boundary_at")
        created = _timestamp(self.created_at, "created_at")
        if created <= boundary:
            raise TemporalCanaryManifestError(
                "temporal canary must be created strictly after its frozen boundary"
            )
        _require_sha256(self.evaluator_artifact_sha256, "evaluator_artifact_sha256")
        if type(self.topic_tags) is not tuple or not self.topic_tags:
            raise TemporalCanaryManifestError("topic_tags must be a non-empty exact tuple")
        for tag in self.topic_tags:
            _require_token(tag, "topic_tags member")
        if self.topic_tags != tuple(sorted(set(self.topic_tags))):
            raise TemporalCanaryManifestError("topic_tags must be sorted and unique")
        _store_manifest_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> TemporalCanaryManifest:
        if type(self) is not TemporalCanaryManifest:
            raise TemporalCanaryManifestError(
                "manifest must be an exact TemporalCanaryManifest"
            )
        bound_content_sha256 = _load_manifest_identity(self)
        _require_sha256(bound_content_sha256, "bound manifest content_sha256")
        snapshot = TemporalCanaryManifest(
            canary_id=self.canary_id,
            source_kind=self.source_kind,
            canary_artifact_sha256=self.canary_artifact_sha256,
            temporal_boundary_at=self.temporal_boundary_at,
            created_at=self.created_at,
            evaluator_artifact_sha256=self.evaluator_artifact_sha256,
            topic_tags=self.topic_tags,
        )
        current_content_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
        if current_content_sha256 != bound_content_sha256:
            raise TemporalCanaryManifestError(
                "temporal canary identity changed after construction"
            )
        return snapshot

    @property
    def can_enter_training(self) -> bool:
        return False

    @property
    def can_enter_search(self) -> bool:
        return False

    @property
    def can_authorize(self) -> bool:
        return False

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "can_authorize": False,
            "can_enter_search": False,
            "can_enter_training": False,
            "canary_artifact_sha256": self.canary_artifact_sha256,
            "canary_id": self.canary_id,
            "created_at": self.created_at,
            "evaluator_artifact_sha256": self.evaluator_artifact_sha256,
            "format": "MRL-TEMPORAL-CANARY-MANIFEST-V1",
            "sealed": True,
            "source_kind": self.source_kind.value,
            "temporal_boundary_at": self.temporal_boundary_at,
            "topic_tags": list(self.topic_tags),
        }

    def semantic_dict(self) -> dict[str, object]:
        snapshot = TemporalCanaryManifest._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def _timestamp(value: object, label: str) -> datetime:
    if type(value) is not str:
        raise TemporalCanaryManifestError(f"{label} must be timestamp text")
    try:
        validate_timestamp(value, label)
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise TemporalCanaryManifestError(f"{label} must be a valid UTC timestamp") from exc


def _require_token(value: object, label: str) -> None:
    if type(value) is not str or _TOKEN.fullmatch(value) is None:
        raise TemporalCanaryManifestError(f"{label} must be canonical token text")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise TemporalCanaryManifestError(f"{label} must be 64 lowercase hex")
