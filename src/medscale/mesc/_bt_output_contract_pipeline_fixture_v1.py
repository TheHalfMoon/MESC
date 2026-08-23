"""Fail-closed fixture validation for frozen output-contract pipeline evidence.

This module validates only caller-supplied fixture evidence for the Backbone
Tournament output-processing boundary. It does not read tournament artifacts,
construct prompts, call models, parse real model output, score real cases,
validate a real report, rank candidates, select a winner, or train.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

_FROZEN_NORMALIZED_OUTPUT_SCHEMA_SHA256: Final = (
    "3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4"
)
_FROZEN_PARSER_CONTRACT_SHA256: Final = (
    "9905096b491ddc3bce2b5d668c1f8726f638dde9dba383ac1bb755f1b6b42071"
)
_FROZEN_SCORING_CONTRACT_SHA256: Final = (
    "a61471d467521b59eb62ee2825d23fa15891bb45a664360aaf2e4ef5882c7d40"
)
_FROZEN_REPORT_VALIDATION_CONTRACT_SHA256: Final = (
    "c68fcac507e4ebc164632370d2392631b9fec9c388369eb5b8bfa495e5877c1a"
)
_FROZEN_REPORT_SCHEMA_SHA256: Final = (
    "cb3fc506b41cc6236959bb4a89bce249db13c99aeb0c7178ff233f6de44e026d"
)
_CANONICAL_PROCESSING_ORDER: Final = (
    "parser",
    "normalized_schema_validator",
    "scorer",
    "report_validator",
)


class OutputContractPipelineError(ValueError):
    """Base class for fail-closed output-contract fixture violations."""


class OutputContractIdentityError(OutputContractPipelineError):
    """Frozen output-contract identity evidence is invalid."""


class OutputPipelineObservationError(OutputContractPipelineError):
    """Output-processing pipeline observation evidence is invalid."""


@dataclass(frozen=True, slots=True)
class OutputContractIdentityEvidence:
    """Injected identities for the frozen output-processing contracts."""

    normalized_output_schema_sha256: str
    parser_contract_sha256: str
    scoring_contract_sha256: str
    report_validation_contract_sha256: str
    report_schema_sha256: str


@dataclass(frozen=True, slots=True)
class OutputPipelineObservation:
    """Injected ordering and retry evidence for output processing."""

    processing_order: tuple[str, ...]
    contract_identities_verified_before_processing: bool
    parser_completed_before_schema_validation: bool
    schema_validation_completed_before_scoring: bool
    scoring_completed_before_report_validation: bool
    semantic_repair_prohibited: bool
    parse_retry_attempts: int
    schema_retry_attempts: int
    semantic_retry_attempts: int
    unattributed_processing_events: int


def verify_fixture_output_contract_pipeline(
    identity: OutputContractIdentityEvidence,
    observation: OutputPipelineObservation,
) -> None:
    """Verify injected output-contract identities and pipeline evidence fail closed."""
    _snapshot_and_validate_identity(identity)
    _snapshot_and_validate_observation(observation)


def _snapshot_and_validate_identity(
    identity: OutputContractIdentityEvidence,
) -> OutputContractIdentityEvidence:
    if type(identity) is not OutputContractIdentityEvidence:
        raise OutputContractIdentityError("output-contract identity evidence has invalid type")

    snapshot = OutputContractIdentityEvidence(
        normalized_output_schema_sha256=identity.normalized_output_schema_sha256,
        parser_contract_sha256=identity.parser_contract_sha256,
        scoring_contract_sha256=identity.scoring_contract_sha256,
        report_validation_contract_sha256=identity.report_validation_contract_sha256,
        report_schema_sha256=identity.report_schema_sha256,
    )
    _validate_identity_snapshot(snapshot)
    return snapshot


def _validate_identity_snapshot(identity: OutputContractIdentityEvidence) -> None:
    required = (
        (
            "normalized_output_schema_sha256",
            identity.normalized_output_schema_sha256,
            _FROZEN_NORMALIZED_OUTPUT_SCHEMA_SHA256,
        ),
        (
            "parser_contract_sha256",
            identity.parser_contract_sha256,
            _FROZEN_PARSER_CONTRACT_SHA256,
        ),
        (
            "scoring_contract_sha256",
            identity.scoring_contract_sha256,
            _FROZEN_SCORING_CONTRACT_SHA256,
        ),
        (
            "report_validation_contract_sha256",
            identity.report_validation_contract_sha256,
            _FROZEN_REPORT_VALIDATION_CONTRACT_SHA256,
        ),
        (
            "report_schema_sha256",
            identity.report_schema_sha256,
            _FROZEN_REPORT_SCHEMA_SHA256,
        ),
    )
    for name, value, expected in required:
        if type(value) is not str:
            raise OutputContractIdentityError(f"identity field {name} must be an exact string")
        if value != expected:
            raise OutputContractIdentityError(f"identity field {name} does not match frozen value")


def _snapshot_and_validate_observation(
    observation: OutputPipelineObservation,
) -> OutputPipelineObservation:
    if type(observation) is not OutputPipelineObservation:
        raise OutputPipelineObservationError("output-pipeline observation has invalid type")
    if type(observation.processing_order) is not tuple:
        raise OutputPipelineObservationError("processing_order must be an exact tuple")

    processing_order = tuple(observation.processing_order)
    snapshot = OutputPipelineObservation(
        processing_order=processing_order,
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
    _validate_observation_snapshot(snapshot)
    return snapshot


def _validate_observation_snapshot(observation: OutputPipelineObservation) -> None:
    if type(observation.processing_order) is not tuple:
        raise OutputPipelineObservationError("processing_order snapshot must be an exact tuple")
    for value in observation.processing_order:
        if type(value) is not str:
            raise OutputPipelineObservationError(
                "processing_order members must be exact strings"
            )
    if observation.processing_order != _CANONICAL_PROCESSING_ORDER:
        raise OutputPipelineObservationError(
            "processing_order must equal parser -> schema -> scorer -> report validator"
        )

    controls = (
        (
            "contract_identities_verified_before_processing",
            observation.contract_identities_verified_before_processing,
        ),
        (
            "parser_completed_before_schema_validation",
            observation.parser_completed_before_schema_validation,
        ),
        (
            "schema_validation_completed_before_scoring",
            observation.schema_validation_completed_before_scoring,
        ),
        (
            "scoring_completed_before_report_validation",
            observation.scoring_completed_before_report_validation,
        ),
        ("semantic_repair_prohibited", observation.semantic_repair_prohibited),
    )
    for name, control_value in controls:
        if type(control_value) is not bool or control_value is not True:
            raise OutputPipelineObservationError(
                f"output-pipeline control {name} must be exact boolean true"
            )

    counters = (
        ("parse_retry_attempts", observation.parse_retry_attempts),
        ("schema_retry_attempts", observation.schema_retry_attempts),
        ("semantic_retry_attempts", observation.semantic_retry_attempts),
        ("unattributed_processing_events", observation.unattributed_processing_events),
    )
    for name, counter_value in counters:
        if type(counter_value) is not int or counter_value != 0:
            raise OutputPipelineObservationError(
                f"output-pipeline counter {name} must be exact integer zero"
            )
