"""Fail-closed fixture validation for executor/harness execution-set evidence.

This module validates only caller-supplied observation evidence for the
``FD-MESC-BT-EXEC-1`` Section D predicate that the complete executed/imported
executor-and-harness path set equals the canonical executor allowlist exactly.
It does not start a process, import or execute harness code, observe a real
runtime, access a filesystem or network, access a model or provider, dispatch
prompts, run inference, rank candidates, select a winner, or train.
"""

from __future__ import annotations

from dataclasses import dataclass

from medscale.mesc._bt_executor_allowlist_v1 import (
    ExecutorAllowlist,
    ExecutorAllowlistEntry,
    canonical_executor_allowlist_bytes,
    parse_executor_allowlist,
)


class ExecutorExecutedSetError(ValueError):
    """Base class for fail-closed executor executed-set evidence violations."""


class ExecutorExecutedSetAllowlistError(ExecutorExecutedSetError):
    """The supplied allowlist is not a parser-validated canonical allowlist."""


class ExecutorExecutedSetObservationError(ExecutorExecutedSetError):
    """The supplied execution/import observation is malformed or incomplete."""


@dataclass(frozen=True, slots=True)
class ExecutorHarnessExecutionObservation:
    """Injected full-lifecycle observation of executor/harness path use."""

    executed_or_imported_paths: tuple[str, ...]
    observation_complete: bool
    observation_started_before_first_execution_or_import: bool
    observation_ended_after_last_execution_or_import: bool
    unattributed_execution_or_import_events: int


def verify_executor_executed_set_evidence(
    allowlist: ExecutorAllowlist,
    observation: ExecutorHarnessExecutionObservation,
) -> None:
    """Verify a complete injected path-set observation against the allowlist."""
    _revalidate_allowlist(allowlist)
    _validate_observation_shape(observation)

    expected_paths = tuple(entry.path for entry in allowlist.entries)
    if observation.executed_or_imported_paths != expected_paths:
        raise ExecutorExecutedSetObservationError(
            "observed executor/harness path set does not equal the canonical allowlist"
        )


def _revalidate_allowlist(allowlist: ExecutorAllowlist) -> None:
    if type(allowlist) is not ExecutorAllowlist:
        raise ExecutorExecutedSetAllowlistError("allowlist is not parser-validated")
    _validate_allowlist_object_types(allowlist)

    try:
        canonical = canonical_executor_allowlist_bytes(allowlist.entries)
        reparsed = parse_executor_allowlist(canonical)
    except Exception as error:
        raise ExecutorExecutedSetAllowlistError(
            "allowlist object does not contain valid canonical allowlist content"
        ) from error

    if reparsed != allowlist:
        raise ExecutorExecutedSetAllowlistError(
            "allowlist object identity does not match its canonical bytes"
        )


def _validate_allowlist_object_types(allowlist: ExecutorAllowlist) -> None:
    if type(allowlist.entries) is not tuple:
        raise ExecutorExecutedSetAllowlistError(
            "allowlist object contains non-exact field types"
        )
    if type(allowlist.sha256) is not str or type(allowlist.byte_length) is not int:
        raise ExecutorExecutedSetAllowlistError(
            "allowlist object contains non-exact field types"
        )

    for entry in allowlist.entries:
        if type(entry) is not ExecutorAllowlistEntry:
            raise ExecutorExecutedSetAllowlistError(
                "allowlist object contains non-exact field types"
            )
        if type(entry.git_blob_sha) is not str or type(entry.path) is not str:
            raise ExecutorExecutedSetAllowlistError(
                "allowlist object contains non-exact field types"
            )


def _validate_observation_shape(
    observation: ExecutorHarnessExecutionObservation,
) -> None:
    if type(observation) is not ExecutorHarnessExecutionObservation:
        raise ExecutorExecutedSetObservationError("execution observation has invalid type")

    paths = observation.executed_or_imported_paths
    if type(paths) is not tuple:
        raise ExecutorExecutedSetObservationError(
            "executed/imported paths must be an exact tuple"
        )
    if any(type(path) is not str for path in paths):
        raise ExecutorExecutedSetObservationError(
            "executed/imported paths must contain exact strings"
        )

    controls = (
        ("observation_complete", observation.observation_complete),
        (
            "observation_started_before_first_execution_or_import",
            observation.observation_started_before_first_execution_or_import,
        ),
        (
            "observation_ended_after_last_execution_or_import",
            observation.observation_ended_after_last_execution_or_import,
        ),
    )
    for name, value in controls:
        if type(value) is not bool or value is not True:
            raise ExecutorExecutedSetObservationError(
                f"execution observation control {name} is not proven"
            )

    counter = observation.unattributed_execution_or_import_events
    if type(counter) is not int or counter != 0:
        raise ExecutorExecutedSetObservationError(
            "unattributed execution/import events must be exact integer zero"
        )
