from __future__ import annotations

from threading import Event, Thread

import pytest

import medscale.mesc._bt_corpus_projection_fixture_v1 as projection_module
from medscale.mesc._bt_corpus_projection_fixture_v1 import (
    CorpusProjectionIdentityError,
    CorpusProjectionIdentityEvidence,
    CorpusProjectionObservation,
    CorpusProjectionObservationError,
    verify_fixture_corpus_projection,
)

_CORPUS_SPEC_SHA256 = "49f554d57e29da4b1d04223d43f1630731e5f8c9b72e7a1e15f959e38c00643b"
_CORPUS_SHA256 = "48fba9119f0170eb40775c75f12916e277cb3953abe22357e0b22497dadbbebd"
_CORPUS_GZIP_SHA256 = "667cd68e5ccc9356321eb5857c6e9203e1320ec33d866ccf514411c211ceb632"
_CORPUS_MANIFEST_SHA256 = "201fa1351923a72097ff7e467b6dce2eb8bd0cfa1e88c73157788f77dd89e745"
_R2_PROVENANCE_AUDIT_SHA256 = (
    "a8f6fd8d9c9f60c5a1a2bedc0bbb49182e635772cf50dae1e9e9028a4eb09398"
)
_CORPUS_CONFORMANCE_AUDIT_SHA256 = (
    "842f2e0dbeaea59087223ddd94c8a95844c8f14822a16e1549e67c0c850c67f2"
)
_AXES = ("A", "B", "C", "D", "E", "F")
_ITEM_IDS = tuple(
    f"BT-{axis}-{index:03d}" for axis in _AXES for index in range(1, 41)
)
_THREAD_SYNC_TIMEOUT_SECONDS = 30.0


class _StringSubclass(str):
    pass


class _IdentitySubclass(CorpusProjectionIdentityEvidence):
    pass


class _ObservationSubclass(CorpusProjectionObservation):
    pass


def _identity() -> CorpusProjectionIdentityEvidence:
    return CorpusProjectionIdentityEvidence(
        corpus_spec_sha256=_CORPUS_SPEC_SHA256,
        materialized_corpus_item_count=240,
        materialized_corpus_sha256=_CORPUS_SHA256,
        materialized_corpus_gzip_sha256=_CORPUS_GZIP_SHA256,
        corpus_manifest_sha256=_CORPUS_MANIFEST_SHA256,
        r2_provenance_audit_sha256=_R2_PROVENANCE_AUDIT_SHA256,
        r2_provenance_audit_result="PASS",
        corpus_conformance_audit_sha256=_CORPUS_CONFORMANCE_AUDIT_SHA256,
        corpus_conformance_audit_result="PASS",
    )


def _observation() -> CorpusProjectionObservation:
    return CorpusProjectionObservation(
        projected_item_ids=_ITEM_IDS,
        projection_complete=True,
        frozen_identity_verified_before_projection=True,
        audits_verified_before_projection=True,
        payload_only_model_visibility=True,
        metadata_projection_events=0,
        gold_or_scoring_projection_events=0,
        unattributed_projection_events=0,
        prompt_serialization_events=0,
    )


def test_valid_fixture_corpus_projection_passes() -> None:
    verify_fixture_corpus_projection(_identity(), _observation())


def test_identity_requires_exact_outer_type() -> None:
    valid = _identity()
    forged = _IdentitySubclass(
        corpus_spec_sha256=valid.corpus_spec_sha256,
        materialized_corpus_item_count=valid.materialized_corpus_item_count,
        materialized_corpus_sha256=valid.materialized_corpus_sha256,
        materialized_corpus_gzip_sha256=valid.materialized_corpus_gzip_sha256,
        corpus_manifest_sha256=valid.corpus_manifest_sha256,
        r2_provenance_audit_sha256=valid.r2_provenance_audit_sha256,
        r2_provenance_audit_result=valid.r2_provenance_audit_result,
        corpus_conformance_audit_sha256=valid.corpus_conformance_audit_sha256,
        corpus_conformance_audit_result=valid.corpus_conformance_audit_result,
    )

    with pytest.raises(CorpusProjectionIdentityError):
        verify_fixture_corpus_projection(forged, _observation())


def test_observation_requires_exact_outer_type() -> None:
    valid = _observation()
    frozen_identity_before_projection = valid.frozen_identity_verified_before_projection
    forged = _ObservationSubclass(
        projected_item_ids=valid.projected_item_ids,
        projection_complete=valid.projection_complete,
        frozen_identity_verified_before_projection=frozen_identity_before_projection,
        audits_verified_before_projection=valid.audits_verified_before_projection,
        payload_only_model_visibility=valid.payload_only_model_visibility,
        metadata_projection_events=valid.metadata_projection_events,
        gold_or_scoring_projection_events=valid.gold_or_scoring_projection_events,
        unattributed_projection_events=valid.unattributed_projection_events,
        prompt_serialization_events=valid.prompt_serialization_events,
    )

    with pytest.raises(CorpusProjectionObservationError):
        verify_fixture_corpus_projection(_identity(), forged)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("corpus_spec_sha256", "0" * 64),
        ("materialized_corpus_item_count", 239),
        ("materialized_corpus_sha256", "0" * 64),
        ("materialized_corpus_gzip_sha256", "0" * 64),
        ("corpus_manifest_sha256", "0" * 64),
        ("r2_provenance_audit_sha256", "0" * 64),
        ("r2_provenance_audit_result", "FAIL"),
        ("corpus_conformance_audit_sha256", "0" * 64),
        ("corpus_conformance_audit_result", "FAIL"),
    ],
)
def test_identity_requires_exact_frozen_values(field: str, value: object) -> None:
    forged = _identity()
    object.__setattr__(forged, field, value)

    with pytest.raises(CorpusProjectionIdentityError):
        verify_fixture_corpus_projection(forged, _observation())


def test_identity_rejects_string_subclass() -> None:
    forged = _identity()
    object.__setattr__(forged, "corpus_spec_sha256", _StringSubclass(_CORPUS_SPEC_SHA256))

    with pytest.raises(CorpusProjectionIdentityError):
        verify_fixture_corpus_projection(forged, _observation())


def test_identity_rejects_bool_as_item_count() -> None:
    forged = _identity()
    object.__setattr__(forged, "materialized_corpus_item_count", True)

    with pytest.raises(CorpusProjectionIdentityError):
        verify_fixture_corpus_projection(forged, _observation())


def test_projected_item_ids_require_exact_tuple() -> None:
    forged = _observation()
    object.__setattr__(forged, "projected_item_ids", list(_ITEM_IDS))

    with pytest.raises(CorpusProjectionObservationError):
        verify_fixture_corpus_projection(_identity(), forged)


def test_projected_item_ids_reject_string_subclass() -> None:
    forged = _observation()
    object.__setattr__(
        forged,
        "projected_item_ids",
        (_StringSubclass(_ITEM_IDS[0]), *_ITEM_IDS[1:]),
    )

    with pytest.raises(CorpusProjectionObservationError):
        verify_fixture_corpus_projection(_identity(), forged)


@pytest.mark.parametrize(
    "item_ids",
    [
        _ITEM_IDS[:-1],
        (*_ITEM_IDS, "BT-G-001"),
        (_ITEM_IDS[1], _ITEM_IDS[0], *_ITEM_IDS[2:]),
        (_ITEM_IDS[0], _ITEM_IDS[0], *_ITEM_IDS[2:]),
    ],
)
def test_projected_item_ids_must_equal_canonical_order(item_ids: tuple[str, ...]) -> None:
    forged = _observation()
    object.__setattr__(forged, "projected_item_ids", item_ids)

    with pytest.raises(CorpusProjectionObservationError):
        verify_fixture_corpus_projection(_identity(), forged)


@pytest.mark.parametrize(
    "field",
    [
        "projection_complete",
        "frozen_identity_verified_before_projection",
        "audits_verified_before_projection",
        "payload_only_model_visibility",
    ],
)
def test_projection_controls_require_exact_true(field: str) -> None:
    forged = _observation()
    object.__setattr__(forged, field, False)

    with pytest.raises(CorpusProjectionObservationError):
        verify_fixture_corpus_projection(_identity(), forged)


@pytest.mark.parametrize(
    "field",
    [
        "projection_complete",
        "frozen_identity_verified_before_projection",
        "audits_verified_before_projection",
        "payload_only_model_visibility",
    ],
)
def test_projection_controls_reject_integer_spoof(field: str) -> None:
    forged = _observation()
    object.__setattr__(forged, field, 1)

    with pytest.raises(CorpusProjectionObservationError):
        verify_fixture_corpus_projection(_identity(), forged)


@pytest.mark.parametrize(
    "field",
    [
        "metadata_projection_events",
        "gold_or_scoring_projection_events",
        "unattributed_projection_events",
        "prompt_serialization_events",
    ],
)
@pytest.mark.parametrize("value", [-1, 1, True])
def test_projection_counters_require_exact_integer_zero(field: str, value: object) -> None:
    forged = _observation()
    object.__setattr__(forged, field, value)

    with pytest.raises(CorpusProjectionObservationError):
        verify_fixture_corpus_projection(_identity(), forged)


def test_identity_post_snapshot_mutation_cannot_change_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity()
    observation = _observation()
    observation_snapshotted = Event()
    identity_mutated = Event()
    mutator_failures: list[str] = []
    original_snapshot_observation = projection_module._snapshot_and_validate_observation

    def synchronized_snapshot_observation(
        value: CorpusProjectionObservation,
    ) -> CorpusProjectionObservation:
        snapshot = original_snapshot_observation(value)
        observation_snapshotted.set()
        if not identity_mutated.wait(timeout=_THREAD_SYNC_TIMEOUT_SECONDS):
            raise AssertionError("timed out waiting for identity mutation")
        return snapshot

    monkeypatch.setattr(
        projection_module,
        "_snapshot_and_validate_observation",
        synchronized_snapshot_observation,
    )

    def mutate_identity() -> None:
        if not observation_snapshotted.wait(timeout=_THREAD_SYNC_TIMEOUT_SECONDS):
            mutator_failures.append("timed out waiting for observation snapshot")
        else:
            object.__setattr__(identity, "materialized_corpus_item_count", 239)
            identity_mutated.set()

    mutator = Thread(target=mutate_identity)
    mutator.start()
    try:
        verify_fixture_corpus_projection(identity, observation)
    finally:
        mutator.join(timeout=_THREAD_SYNC_TIMEOUT_SECONDS)

    assert not mutator_failures
    assert identity_mutated.is_set()
    assert not mutator.is_alive()


def test_observation_post_snapshot_mutation_cannot_change_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity()
    observation = _observation()
    observation_snapshotted = Event()
    observation_mutated = Event()
    mutator_failures: list[str] = []
    original_snapshot_observation = projection_module._snapshot_and_validate_observation

    def synchronized_snapshot_observation(
        value: CorpusProjectionObservation,
    ) -> CorpusProjectionObservation:
        snapshot = original_snapshot_observation(value)
        observation_snapshotted.set()
        if not observation_mutated.wait(timeout=_THREAD_SYNC_TIMEOUT_SECONDS):
            raise AssertionError("timed out waiting for observation mutation")
        return snapshot

    monkeypatch.setattr(
        projection_module,
        "_snapshot_and_validate_observation",
        synchronized_snapshot_observation,
    )

    def mutate_observation() -> None:
        if not observation_snapshotted.wait(timeout=_THREAD_SYNC_TIMEOUT_SECONDS):
            mutator_failures.append("timed out waiting for observation snapshot")
        else:
            object.__setattr__(observation, "projected_item_ids", _ITEM_IDS[:-1])
            observation_mutated.set()

    mutator = Thread(target=mutate_observation)
    mutator.start()
    try:
        verify_fixture_corpus_projection(identity, observation)
    finally:
        mutator.join(timeout=_THREAD_SYNC_TIMEOUT_SECONDS)

    assert not mutator_failures
    assert observation_mutated.is_set()
    assert not mutator.is_alive()
