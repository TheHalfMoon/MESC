from __future__ import annotations

from threading import Event, Thread

import pytest

import medscale.mesc._bt_output_contract_pipeline_fixture_v1 as pipeline_module
from medscale.mesc._bt_output_contract_pipeline_fixture_v1 import (
    OutputContractIdentityError,
    OutputContractIdentityEvidence,
    OutputPipelineObservation,
    OutputPipelineObservationError,
    verify_fixture_output_contract_pipeline,
)

_NORMALIZED_OUTPUT_SCHEMA_SHA256 = (
    "3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4"
)
_PARSER_CONTRACT_SHA256 = "9905096b491ddc3bce2b5d668c1f8726f638dde9dba383ac1bb755f1b6b42071"
_SCORING_CONTRACT_SHA256 = "a61471d467521b59eb62ee2825d23fa15891bb45a664360aaf2e4ef5882c7d40"
_REPORT_VALIDATION_CONTRACT_SHA256 = (
    "c68fcac507e4ebc164632370d2392631b9fec9c388369eb5b8bfa495e5877c1a"
)
_REPORT_SCHEMA_SHA256 = "cb3fc506b41cc6236959bb4a89bce249db13c99aeb0c7178ff233f6de44e026d"
_PROCESSING_ORDER = (
    "parser",
    "normalized_schema_validator",
    "scorer",
    "report_validator",
)
_THREAD_SYNC_TIMEOUT_SECONDS = 30.0


def _identity() -> OutputContractIdentityEvidence:
    return OutputContractIdentityEvidence(
        normalized_output_schema_sha256=_NORMALIZED_OUTPUT_SCHEMA_SHA256,
        parser_contract_sha256=_PARSER_CONTRACT_SHA256,
        scoring_contract_sha256=_SCORING_CONTRACT_SHA256,
        report_validation_contract_sha256=_REPORT_VALIDATION_CONTRACT_SHA256,
        report_schema_sha256=_REPORT_SCHEMA_SHA256,
    )


def _observation() -> OutputPipelineObservation:
    return OutputPipelineObservation(
        processing_order=_PROCESSING_ORDER,
        contract_identities_verified_before_processing=True,
        parser_completed_before_schema_validation=True,
        schema_validation_completed_before_scoring=True,
        scoring_completed_before_report_validation=True,
        semantic_repair_prohibited=True,
        parse_retry_attempts=0,
        schema_retry_attempts=0,
        semantic_retry_attempts=0,
        unattributed_processing_events=0,
    )


def test_valid_fixture_output_contract_pipeline_passes() -> None:
    verify_fixture_output_contract_pipeline(_identity(), _observation())


def test_identity_outer_subclass_is_rejected() -> None:
    class IdentitySubclass(OutputContractIdentityEvidence):
        pass

    identity = _identity()
    forged = IdentitySubclass(
        normalized_output_schema_sha256=identity.normalized_output_schema_sha256,
        parser_contract_sha256=identity.parser_contract_sha256,
        scoring_contract_sha256=identity.scoring_contract_sha256,
        report_validation_contract_sha256=identity.report_validation_contract_sha256,
        report_schema_sha256=identity.report_schema_sha256,
    )

    with pytest.raises(OutputContractIdentityError):
        verify_fixture_output_contract_pipeline(forged, _observation())


def test_observation_outer_subclass_is_rejected() -> None:
    class ObservationSubclass(OutputPipelineObservation):
        pass

    observation = _observation()
    forged = ObservationSubclass(
        processing_order=observation.processing_order,
        contract_identities_verified_before_processing=(
            observation.contract_identities_verified_before_processing
        ),
        parser_completed_before_schema_validation=(
            observation.parser_completed_before_schema_validation
        ),
        schema_validation_completed_before_scoring=(
            observation.schema_validation_completed_before_scoring
        ),
        scoring_completed_before_report_validation=(
            observation.scoring_completed_before_report_validation
        ),
        semantic_repair_prohibited=observation.semantic_repair_prohibited,
        parse_retry_attempts=observation.parse_retry_attempts,
        schema_retry_attempts=observation.schema_retry_attempts,
        semantic_retry_attempts=observation.semantic_retry_attempts,
        unattributed_processing_events=observation.unattributed_processing_events,
    )

    with pytest.raises(OutputPipelineObservationError):
        verify_fixture_output_contract_pipeline(_identity(), forged)


@pytest.mark.parametrize(
    "field",
    [
        "normalized_output_schema_sha256",
        "parser_contract_sha256",
        "scoring_contract_sha256",
        "report_validation_contract_sha256",
        "report_schema_sha256",
    ],
)
def test_identity_digest_mismatch_fails_closed(field: str) -> None:
    forged = _identity()
    object.__setattr__(forged, field, "0" * 64)

    with pytest.raises(OutputContractIdentityError):
        verify_fixture_output_contract_pipeline(forged, _observation())


def test_identity_string_subclass_is_rejected() -> None:
    class StringSubclass(str):
        pass

    forged = _identity()
    object.__setattr__(
        forged,
        "parser_contract_sha256",
        StringSubclass(_PARSER_CONTRACT_SHA256),
    )

    with pytest.raises(OutputContractIdentityError):
        verify_fixture_output_contract_pipeline(forged, _observation())


def test_processing_order_requires_exact_tuple() -> None:
    forged = _observation()
    object.__setattr__(forged, "processing_order", list(_PROCESSING_ORDER))

    with pytest.raises(OutputPipelineObservationError):
        verify_fixture_output_contract_pipeline(_identity(), forged)


def test_processing_order_member_requires_exact_string() -> None:
    class StringSubclass(str):
        pass

    forged = _observation()
    object.__setattr__(
        forged,
        "processing_order",
        (StringSubclass("parser"), *_PROCESSING_ORDER[1:]),
    )

    with pytest.raises(OutputPipelineObservationError):
        verify_fixture_output_contract_pipeline(_identity(), forged)


@pytest.mark.parametrize(
    "processing_order",
    [
        _PROCESSING_ORDER[:-1],
        (*_PROCESSING_ORDER, "extra"),
        (_PROCESSING_ORDER[1], _PROCESSING_ORDER[0], *_PROCESSING_ORDER[2:]),
        (_PROCESSING_ORDER[0], _PROCESSING_ORDER[0], *_PROCESSING_ORDER[2:]),
    ],
)
def test_processing_order_must_be_exact_canonical_sequence(
    processing_order: tuple[str, ...],
) -> None:
    forged = _observation()
    object.__setattr__(forged, "processing_order", processing_order)

    with pytest.raises(OutputPipelineObservationError):
        verify_fixture_output_contract_pipeline(_identity(), forged)


@pytest.mark.parametrize(
    "field",
    [
        "contract_identities_verified_before_processing",
        "parser_completed_before_schema_validation",
        "schema_validation_completed_before_scoring",
        "scoring_completed_before_report_validation",
        "semantic_repair_prohibited",
    ],
)
@pytest.mark.parametrize("value", [False, 1])
def test_pipeline_controls_require_exact_boolean_true(field: str, value: object) -> None:
    forged = _observation()
    object.__setattr__(forged, field, value)

    with pytest.raises(OutputPipelineObservationError):
        verify_fixture_output_contract_pipeline(_identity(), forged)


@pytest.mark.parametrize(
    "field",
    [
        "parse_retry_attempts",
        "schema_retry_attempts",
        "semantic_retry_attempts",
        "unattributed_processing_events",
    ],
)
@pytest.mark.parametrize("value", [-1, 1, True])
def test_pipeline_counters_require_exact_integer_zero(field: str, value: object) -> None:
    forged = _observation()
    object.__setattr__(forged, field, value)

    with pytest.raises(OutputPipelineObservationError):
        verify_fixture_output_contract_pipeline(_identity(), forged)


def test_identity_post_snapshot_mutation_cannot_change_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = _identity()
    observation = _observation()
    observation_snapshotted = Event()
    identity_mutated = Event()
    mutator_failures: list[str] = []
    original_snapshot_observation = pipeline_module._snapshot_and_validate_observation

    def synchronized_snapshot_observation(
        value: OutputPipelineObservation,
    ) -> OutputPipelineObservation:
        snapshot = original_snapshot_observation(value)
        observation_snapshotted.set()
        if not identity_mutated.wait(timeout=_THREAD_SYNC_TIMEOUT_SECONDS):
            raise AssertionError("timed out waiting for identity mutation")
        return snapshot

    monkeypatch.setattr(
        pipeline_module,
        "_snapshot_and_validate_observation",
        synchronized_snapshot_observation,
    )

    def mutate_identity() -> None:
        if not observation_snapshotted.wait(timeout=_THREAD_SYNC_TIMEOUT_SECONDS):
            mutator_failures.append("timed out waiting for observation snapshot")
        else:
            object.__setattr__(identity, "parser_contract_sha256", "0" * 64)
            identity_mutated.set()

    mutator = Thread(target=mutate_identity)
    mutator.start()
    try:
        verify_fixture_output_contract_pipeline(identity, observation)
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
    original_snapshot_observation = pipeline_module._snapshot_and_validate_observation

    def synchronized_snapshot_observation(
        value: OutputPipelineObservation,
    ) -> OutputPipelineObservation:
        snapshot = original_snapshot_observation(value)
        observation_snapshotted.set()
        if not observation_mutated.wait(timeout=_THREAD_SYNC_TIMEOUT_SECONDS):
            raise AssertionError("timed out waiting for observation mutation")
        return snapshot

    monkeypatch.setattr(
        pipeline_module,
        "_snapshot_and_validate_observation",
        synchronized_snapshot_observation,
    )

    def mutate_observation() -> None:
        if not observation_snapshotted.wait(timeout=_THREAD_SYNC_TIMEOUT_SECONDS):
            mutator_failures.append("timed out waiting for observation snapshot")
        else:
            object.__setattr__(observation, "processing_order", _PROCESSING_ORDER[:-1])
            observation_mutated.set()

    mutator = Thread(target=mutate_observation)
    mutator.start()
    try:
        verify_fixture_output_contract_pipeline(identity, observation)
    finally:
        mutator.join(timeout=_THREAD_SYNC_TIMEOUT_SECONDS)

    assert not mutator_failures
    assert observation_mutated.is_set()
    assert not mutator.is_alive()
