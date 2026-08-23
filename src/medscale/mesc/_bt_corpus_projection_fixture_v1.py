"""Fail-closed fixture validation for frozen corpus projection evidence.

This module validates only caller-supplied fixture evidence for the Backbone
Tournament pre-prompt corpus-projection boundary. It does not read corpus,
scoring-key, prompt, provider, model, filesystem, or network content and does
not serialize a prompt, run inference, rank candidates, select a winner, or
train.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

_FROZEN_CORPUS_SPEC_SHA256: Final = (
    "49f554d57e29da4b1d04223d43f1630731e5f8c9b72e7a1e15f959e38c00643b"
)
_FROZEN_MATERIALIZED_CORPUS_ITEM_COUNT: Final = 240
_FROZEN_MATERIALIZED_CORPUS_SHA256: Final = (
    "48fba9119f0170eb40775c75f12916e277cb3953abe22357e0b22497dadbbebd"
)
_FROZEN_MATERIALIZED_CORPUS_GZIP_SHA256: Final = (
    "667cd68e5ccc9356321eb5857c6e9203e1320ec33d866ccf514411c211ceb632"
)
_FROZEN_CORPUS_MANIFEST_SHA256: Final = (
    "201fa1351923a72097ff7e467b6dce2eb8bd0cfa1e88c73157788f77dd89e745"
)
_FROZEN_R2_PROVENANCE_AUDIT_SHA256: Final = (
    "a8f6fd8d9c9f60c5a1a2bedc0bbb49182e635772cf50dae1e9e9028a4eb09398"
)
_FROZEN_CORPUS_CONFORMANCE_AUDIT_SHA256: Final = (
    "842f2e0dbeaea59087223ddd94c8a95844c8f14822a16e1549e67c0c850c67f2"
)
_CANONICAL_AXES: Final = ("A", "B", "C", "D", "E", "F")
_CANONICAL_ITEM_IDS: Final = tuple(
    f"BT-{axis}-{index:03d}" for axis in _CANONICAL_AXES for index in range(1, 41)
)


class CorpusProjectionError(ValueError):
    """Base class for fail-closed corpus-projection fixture violations."""


class CorpusProjectionIdentityError(CorpusProjectionError):
    """Frozen corpus or audit identity evidence is invalid."""


class CorpusProjectionObservationError(CorpusProjectionError):
    """Projected item-set or visibility evidence is invalid."""


@dataclass(frozen=True, slots=True)
class CorpusProjectionIdentityEvidence:
    """Injected identity and audit facts required before corpus projection."""

    corpus_spec_sha256: str
    materialized_corpus_item_count: int
    materialized_corpus_sha256: str
    materialized_corpus_gzip_sha256: str
    corpus_manifest_sha256: str
    r2_provenance_audit_sha256: str
    r2_provenance_audit_result: str
    corpus_conformance_audit_sha256: str
    corpus_conformance_audit_result: str


@dataclass(frozen=True, slots=True)
class CorpusProjectionObservation:
    """Injected complete-set evidence for payload-only model visibility."""

    projected_item_ids: tuple[str, ...]
    projection_complete: bool
    frozen_identity_verified_before_projection: bool
    audits_verified_before_projection: bool
    payload_only_model_visibility: bool
    metadata_projection_events: int
    gold_or_scoring_projection_events: int
    unattributed_projection_events: int
    prompt_serialization_events: int


def verify_fixture_corpus_projection(
    identity: CorpusProjectionIdentityEvidence,
    observation: CorpusProjectionObservation,
) -> None:
    """Verify injected pre-prompt corpus projection evidence fail closed."""
    identity_snapshot = _snapshot_and_validate_identity(identity)
    observation_snapshot = _snapshot_and_validate_observation(observation)

    if identity_snapshot.materialized_corpus_item_count != len(
        observation_snapshot.projected_item_ids
    ):
        raise CorpusProjectionObservationError(
            "projected item count does not equal the frozen corpus item count"
        )


def _snapshot_and_validate_identity(
    identity: CorpusProjectionIdentityEvidence,
) -> CorpusProjectionIdentityEvidence:
    if type(identity) is not CorpusProjectionIdentityEvidence:
        raise CorpusProjectionIdentityError("corpus projection identity evidence has invalid type")

    snapshot = CorpusProjectionIdentityEvidence(
        corpus_spec_sha256=identity.corpus_spec_sha256,
        materialized_corpus_item_count=identity.materialized_corpus_item_count,
        materialized_corpus_sha256=identity.materialized_corpus_sha256,
        materialized_corpus_gzip_sha256=identity.materialized_corpus_gzip_sha256,
        corpus_manifest_sha256=identity.corpus_manifest_sha256,
        r2_provenance_audit_sha256=identity.r2_provenance_audit_sha256,
        r2_provenance_audit_result=identity.r2_provenance_audit_result,
        corpus_conformance_audit_sha256=identity.corpus_conformance_audit_sha256,
        corpus_conformance_audit_result=identity.corpus_conformance_audit_result,
    )
    _validate_identity_snapshot(snapshot)
    return snapshot


def _validate_identity_snapshot(identity: CorpusProjectionIdentityEvidence) -> None:
    string_fields = (
        ("corpus_spec_sha256", identity.corpus_spec_sha256),
        ("materialized_corpus_sha256", identity.materialized_corpus_sha256),
        ("materialized_corpus_gzip_sha256", identity.materialized_corpus_gzip_sha256),
        ("corpus_manifest_sha256", identity.corpus_manifest_sha256),
        ("r2_provenance_audit_sha256", identity.r2_provenance_audit_sha256),
        ("r2_provenance_audit_result", identity.r2_provenance_audit_result),
        ("corpus_conformance_audit_sha256", identity.corpus_conformance_audit_sha256),
        ("corpus_conformance_audit_result", identity.corpus_conformance_audit_result),
    )
    for name, value in string_fields:
        if type(value) is not str:
            raise CorpusProjectionIdentityError(f"identity field {name} must be an exact string")

    if type(identity.materialized_corpus_item_count) is not int:
        raise CorpusProjectionIdentityError("materialized corpus item count must be an exact integer")

    required = (
        ("corpus_spec_sha256", identity.corpus_spec_sha256, _FROZEN_CORPUS_SPEC_SHA256),
        (
            "materialized_corpus_sha256",
            identity.materialized_corpus_sha256,
            _FROZEN_MATERIALIZED_CORPUS_SHA256,
        ),
        (
            "materialized_corpus_gzip_sha256",
            identity.materialized_corpus_gzip_sha256,
            _FROZEN_MATERIALIZED_CORPUS_GZIP_SHA256,
        ),
        (
            "corpus_manifest_sha256",
            identity.corpus_manifest_sha256,
            _FROZEN_CORPUS_MANIFEST_SHA256,
        ),
        (
            "r2_provenance_audit_sha256",
            identity.r2_provenance_audit_sha256,
            _FROZEN_R2_PROVENANCE_AUDIT_SHA256,
        ),
        (
            "corpus_conformance_audit_sha256",
            identity.corpus_conformance_audit_sha256,
            _FROZEN_CORPUS_CONFORMANCE_AUDIT_SHA256,
        ),
    )
    for name, value, expected in required:
        if value != expected:
            raise CorpusProjectionIdentityError(f"identity field {name} does not match frozen value")

    if identity.materialized_corpus_item_count != _FROZEN_MATERIALIZED_CORPUS_ITEM_COUNT:
        raise CorpusProjectionIdentityError("materialized corpus item count does not match frozen value")
    if identity.r2_provenance_audit_result != "PASS":
        raise CorpusProjectionIdentityError("R2 provenance audit is not PASS")
    if identity.corpus_conformance_audit_result != "PASS":
        raise CorpusProjectionIdentityError("corpus conformance audit is not PASS")


def _snapshot_and_validate_observation(
    observation: CorpusProjectionObservation,
) -> CorpusProjectionObservation:
    if type(observation) is not CorpusProjectionObservation:
        raise CorpusProjectionObservationError("corpus projection observation has invalid type")

    projected_item_ids = observation.projected_item_ids
    if type(projected_item_ids) is not tuple:
        raise CorpusProjectionObservationError("projected item IDs must be an exact tuple")
    if any(type(item_id) is not str for item_id in projected_item_ids):
        raise CorpusProjectionObservationError("projected item IDs must contain exact strings")

    snapshot = CorpusProjectionObservation(
        projected_item_ids=tuple(projected_item_ids),
        projection_complete=observation.projection_complete,
        frozen_identity_verified_before_projection=(
            observation.frozen_identity_verified_before_projection
        ),
        audits_verified_before_projection=observation.audits_verified_before_projection,
        payload_only_model_visibility=observation.payload_only_model_visibility,
        metadata_projection_events=observation.metadata_projection_events,
        gold_or_scoring_projection_events=observation.gold_or_scoring_projection_events,
        unattributed_projection_events=observation.unattributed_projection_events,
        prompt_serialization_events=observation.prompt_serialization_events,
    )
    _validate_observation_snapshot(snapshot)
    return snapshot


def _validate_observation_snapshot(observation: CorpusProjectionObservation) -> None:
    if observation.projected_item_ids != _CANONICAL_ITEM_IDS:
        raise CorpusProjectionObservationError(
            "projected item IDs do not equal the canonical 240-item corpus order"
        )

    controls = (
        ("projection_complete", observation.projection_complete),
        (
            "frozen_identity_verified_before_projection",
            observation.frozen_identity_verified_before_projection,
        ),
        ("audits_verified_before_projection", observation.audits_verified_before_projection),
        ("payload_only_model_visibility", observation.payload_only_model_visibility),
    )
    for name, value in controls:
        if type(value) is not bool or value is not True:
            raise CorpusProjectionObservationError(f"projection control {name} is not proven")

    counters = (
        ("metadata_projection_events", observation.metadata_projection_events),
        ("gold_or_scoring_projection_events", observation.gold_or_scoring_projection_events),
        ("unattributed_projection_events", observation.unattributed_projection_events),
        ("prompt_serialization_events", observation.prompt_serialization_events),
    )
    for name, value in counters:
        if type(value) is not int or value != 0:
            raise CorpusProjectionObservationError(
                f"projection counter {name} must be exact integer zero"
            )
