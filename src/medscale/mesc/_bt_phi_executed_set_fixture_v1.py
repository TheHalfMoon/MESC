"""Fail-closed fixture validation for Phi remote-code execution-set evidence.

This module validates only caller-supplied observation evidence for the
``FD-MESC-BT-EXEC-1`` Section C.3 predicate that the complete executed Phi
remote-code file set equals the canonical manifest exactly and that no remote
fetch occurs during the model-process lifecycle. It does not start a process,
import or execute remote code, observe a real runtime, access a filesystem or
network, access a model or provider, dispatch prompts, run inference, rank
candidates, select a winner, or train.
"""

from __future__ import annotations

from dataclasses import dataclass

from medscale.mesc._bt_phi_remote_code_fixture_v1 import (
    PhiRemoteCodeManifest,
    canonical_phi_remote_code_manifest_bytes,
    parse_phi_remote_code_manifest,
)


class PhiExecutedSetError(ValueError):
    """Base class for fail-closed Phi executed-set evidence violations."""


class PhiExecutedSetManifestError(PhiExecutedSetError):
    """The supplied manifest is not a parser-validated canonical manifest."""


class PhiExecutedSetObservationError(PhiExecutedSetError):
    """The supplied execution-set observation is malformed or incomplete."""


@dataclass(frozen=True, slots=True)
class PhiRemoteCodeExecutionObservation:
    """Injected full-lifecycle observation of Phi remote-code execution paths."""

    executed_remote_code_paths: tuple[str, ...]
    observation_complete: bool
    observation_started_before_first_remote_code_import: bool
    observation_ended_after_model_process_exit: bool
    dynamic_remote_fetch_attempts: int
    unattributed_remote_code_execution_events: int


def verify_phi_executed_set_evidence(
    manifest: PhiRemoteCodeManifest,
    observation: PhiRemoteCodeExecutionObservation,
) -> None:
    """Verify a complete injected executed-set observation against the manifest."""
    _revalidate_manifest(manifest)
    _validate_observation_shape(observation)

    expected_paths = tuple(entry.path for entry in manifest.entries)
    if observation.executed_remote_code_paths != expected_paths:
        raise PhiExecutedSetObservationError(
            "observed Phi remote-code execution set does not equal the canonical manifest"
        )


def _revalidate_manifest(manifest: PhiRemoteCodeManifest) -> None:
    if type(manifest) is not PhiRemoteCodeManifest:
        raise PhiExecutedSetManifestError("manifest is not parser-validated")

    try:
        canonical = canonical_phi_remote_code_manifest_bytes(manifest.entries)
        reparsed = parse_phi_remote_code_manifest(canonical)
    except Exception as error:
        raise PhiExecutedSetManifestError(
            "manifest object does not contain valid canonical manifest content"
        ) from error

    if reparsed != manifest:
        raise PhiExecutedSetManifestError(
            "manifest object identity does not match its canonical bytes"
        )


def _validate_observation_shape(observation: PhiRemoteCodeExecutionObservation) -> None:
    if type(observation) is not PhiRemoteCodeExecutionObservation:
        raise PhiExecutedSetObservationError("execution observation has invalid type")

    paths = observation.executed_remote_code_paths
    if type(paths) is not tuple:
        raise PhiExecutedSetObservationError("executed remote-code paths must be an exact tuple")
    if any(type(path) is not str for path in paths):
        raise PhiExecutedSetObservationError(
            "executed remote-code paths must contain exact strings"
        )

    controls = (
        ("observation_complete", observation.observation_complete),
        (
            "observation_started_before_first_remote_code_import",
            observation.observation_started_before_first_remote_code_import,
        ),
        (
            "observation_ended_after_model_process_exit",
            observation.observation_ended_after_model_process_exit,
        ),
    )
    for name, value in controls:
        if type(value) is not bool or value is not True:
            raise PhiExecutedSetObservationError(
                f"execution observation control {name} is not proven"
            )

    counters = (
        ("dynamic_remote_fetch_attempts", observation.dynamic_remote_fetch_attempts),
        (
            "unattributed_remote_code_execution_events",
            observation.unattributed_remote_code_execution_events,
        ),
    )
    for name, counter_value in counters:
        if type(counter_value) is not int or counter_value != 0:
            raise PhiExecutedSetObservationError(
                f"execution observation counter {name} must be exact integer zero"
            )
