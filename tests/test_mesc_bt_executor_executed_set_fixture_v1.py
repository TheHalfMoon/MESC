from __future__ import annotations

from typing import cast

import pytest

from medscale.mesc._bt_executor_allowlist_v1 import (
    ExecutorAllowlist,
    ExecutorAllowlistEntry,
    canonical_executor_allowlist_bytes,
    parse_executor_allowlist,
)
from medscale.mesc._bt_executor_executed_set_fixture_v1 import (
    ExecutorExecutedSetAllowlistError,
    ExecutorExecutedSetObservationError,
    ExecutorHarnessExecutionObservation,
    verify_executor_executed_set_evidence,
)

_PATHS = ("src/medscale/mesc/a.py", "src/medscale/mesc/b.py")


class _StringSubclass(str):
    pass


class _PathSpoof:
    def __eq__(self, other: object) -> bool:
        return True


class _AllowlistSubclass(ExecutorAllowlist):
    pass


class _EntrySubclass(ExecutorAllowlistEntry):
    pass


class _ObservationSubclass(ExecutorHarnessExecutionObservation):
    pass


def _allowlist() -> ExecutorAllowlist:
    entries = (
        ExecutorAllowlistEntry(git_blob_sha="a" * 40, path=_PATHS[0]),
        ExecutorAllowlistEntry(git_blob_sha="b" * 40, path=_PATHS[1]),
    )
    return parse_executor_allowlist(canonical_executor_allowlist_bytes(entries))


def _observation() -> ExecutorHarnessExecutionObservation:
    return ExecutorHarnessExecutionObservation(
        executed_or_imported_paths=_PATHS,
        observation_complete=True,
        observation_started_before_first_execution_or_import=True,
        observation_ended_after_last_execution_or_import=True,
        unattributed_execution_or_import_events=0,
    )


def test_valid_fixture_executed_set_evidence_passes() -> None:
    verify_executor_executed_set_evidence(_allowlist(), _observation())


def test_allowlist_requires_exact_outer_type() -> None:
    valid = _allowlist()
    forged = _AllowlistSubclass(
        entries=valid.entries,
        sha256=valid.sha256,
        byte_length=valid.byte_length,
    )

    with pytest.raises(ExecutorExecutedSetAllowlistError):
        verify_executor_executed_set_evidence(forged, _observation())


def test_allowlist_rejects_non_tuple_entries() -> None:
    forged = _allowlist()
    object.__setattr__(forged, "entries", list(forged.entries))

    with pytest.raises(ExecutorExecutedSetAllowlistError):
        verify_executor_executed_set_evidence(forged, _observation())


def test_allowlist_rejects_entry_subclass() -> None:
    forged = _allowlist()
    original = forged.entries[0]
    subclass_entry = _EntrySubclass(
        git_blob_sha=original.git_blob_sha,
        path=original.path,
    )
    object.__setattr__(forged, "entries", (subclass_entry, forged.entries[1]))

    with pytest.raises(ExecutorExecutedSetAllowlistError):
        verify_executor_executed_set_evidence(forged, _observation())


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("sha256", _StringSubclass("0" * 64)),
        ("byte_length", True),
    ],
)
def test_allowlist_rejects_non_exact_metadata_types(field: str, value: object) -> None:
    forged = _allowlist()
    object.__setattr__(forged, field, value)

    with pytest.raises(ExecutorExecutedSetAllowlistError):
        verify_executor_executed_set_evidence(forged, _observation())


@pytest.mark.parametrize("field", ["git_blob_sha", "path"])
def test_allowlist_rejects_entry_string_subclass(field: str) -> None:
    forged = _allowlist()
    entry = forged.entries[0]
    object.__setattr__(entry, field, _StringSubclass(getattr(entry, field)))

    with pytest.raises(ExecutorExecutedSetAllowlistError):
        verify_executor_executed_set_evidence(forged, _observation())


def test_allowlist_rejects_forged_digest_even_with_canonical_entries() -> None:
    forged = _allowlist()
    object.__setattr__(forged, "sha256", "0" * 64)

    with pytest.raises(ExecutorExecutedSetAllowlistError):
        verify_executor_executed_set_evidence(forged, _observation())


def test_observation_requires_exact_type() -> None:
    forged = _ObservationSubclass(
        executed_or_imported_paths=_PATHS,
        observation_complete=True,
        observation_started_before_first_execution_or_import=True,
        observation_ended_after_last_execution_or_import=True,
        unattributed_execution_or_import_events=0,
    )

    with pytest.raises(ExecutorExecutedSetObservationError):
        verify_executor_executed_set_evidence(_allowlist(), forged)


def test_paths_require_exact_tuple_container() -> None:
    forged = _observation()
    object.__setattr__(forged, "executed_or_imported_paths", list(_PATHS))

    with pytest.raises(ExecutorExecutedSetObservationError):
        verify_executor_executed_set_evidence(_allowlist(), forged)


def test_paths_reject_string_subclass() -> None:
    forged = _observation()
    object.__setattr__(
        forged,
        "executed_or_imported_paths",
        (_StringSubclass(_PATHS[0]), _PATHS[1]),
    )

    with pytest.raises(ExecutorExecutedSetObservationError):
        verify_executor_executed_set_evidence(_allowlist(), forged)


def test_paths_reject_equality_spoof() -> None:
    forged = _observation()
    object.__setattr__(
        forged,
        "executed_or_imported_paths",
        (cast(str, _PathSpoof()), _PATHS[1]),
    )

    with pytest.raises(ExecutorExecutedSetObservationError):
        verify_executor_executed_set_evidence(_allowlist(), forged)


@pytest.mark.parametrize(
    "paths",
    [
        (_PATHS[0],),
        (_PATHS[0], _PATHS[1], "src/medscale/mesc/extra.py"),
        (_PATHS[1], _PATHS[0]),
        (_PATHS[0], _PATHS[0], _PATHS[1]),
    ],
)
def test_path_set_must_equal_allowlist_exactly(paths: tuple[str, ...]) -> None:
    forged = _observation()
    object.__setattr__(forged, "executed_or_imported_paths", paths)

    with pytest.raises(ExecutorExecutedSetObservationError):
        verify_executor_executed_set_evidence(_allowlist(), forged)


@pytest.mark.parametrize(
    "field",
    [
        "observation_complete",
        "observation_started_before_first_execution_or_import",
        "observation_ended_after_last_execution_or_import",
    ],
)
def test_completeness_controls_require_exact_true(field: str) -> None:
    forged = _observation()
    object.__setattr__(forged, field, False)

    with pytest.raises(ExecutorExecutedSetObservationError):
        verify_executor_executed_set_evidence(_allowlist(), forged)


@pytest.mark.parametrize(
    "field",
    [
        "observation_complete",
        "observation_started_before_first_execution_or_import",
        "observation_ended_after_last_execution_or_import",
    ],
)
def test_completeness_controls_reject_integer_spoof(field: str) -> None:
    forged = _observation()
    object.__setattr__(forged, field, 1)

    with pytest.raises(ExecutorExecutedSetObservationError):
        verify_executor_executed_set_evidence(_allowlist(), forged)


@pytest.mark.parametrize("value", [-1, 1, True])
def test_unattributed_event_counter_requires_exact_integer_zero(value: object) -> None:
    forged = _observation()
    object.__setattr__(forged, "unattributed_execution_or_import_events", value)

    with pytest.raises(ExecutorExecutedSetObservationError):
        verify_executor_executed_set_evidence(_allowlist(), forged)
