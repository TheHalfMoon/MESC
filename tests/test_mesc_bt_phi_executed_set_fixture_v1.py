"""Fixture-only qualification for the Phi executed-set evidence verifier."""

from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._bt_phi_executed_set_fixture_v1 import (
    PhiExecutedSetManifestError,
    PhiExecutedSetObservationError,
    PhiRemoteCodeExecutionObservation,
    verify_phi_executed_set_evidence,
)
from medscale.mesc._bt_phi_remote_code_fixture_v1 import (
    PhiRemoteCodeManifest,
    PhiRemoteCodeManifestEntry,
    parse_phi_remote_code_manifest,
)

_BLOB_A = "a" * 40
_BLOB_B = "b" * 40
_DIGEST_A = "c" * 64
_DIGEST_B = "d" * 64


class _PathSpoof:
    """Non-string equality spoof used to regression-test path exact typing."""

    def __init__(self, value: str) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, str) and other == self.value


class _StringSubclass(str):
    """String subclass that compares equal to the canonical plain string."""


class _IntSubclass(int):
    """Integer subclass that compares equal to the canonical plain integer."""


def _entry(byte_length: int, blob_sha: str, path: str, sha256: str) -> str:
    return (
        f'{{"byte_length":{byte_length},"git_blob_sha":"{blob_sha}",'
        f'"path":"{path}","sha256":"{sha256}"}}'
    )


def _manifest() -> PhiRemoteCodeManifest:
    payload = (
        "["
        + ",".join(
            [
                _entry(12, _BLOB_A, "modeling_phi4mm.py", _DIGEST_A),
                _entry(34, _BLOB_B, "processing_phi4mm.py", _DIGEST_B),
            ]
        )
        + "]"
    ).encode("ascii")
    return parse_phi_remote_code_manifest(payload)


def _observation(manifest: PhiRemoteCodeManifest) -> PhiRemoteCodeExecutionObservation:
    return PhiRemoteCodeExecutionObservation(
        executed_remote_code_paths=tuple(entry.path for entry in manifest.entries),
        observation_complete=True,
        observation_started_before_model_process_start=True,
        observation_ended_after_model_process_exit=True,
        dynamic_remote_fetch_attempts=0,
        unattributed_remote_code_execution_events=0,
    )


def test_valid_complete_observation_matches_manifest_exactly() -> None:
    manifest = _manifest()

    verify_phi_executed_set_evidence(manifest, _observation(manifest))


def test_forged_manifest_is_rejected_before_observation_validation() -> None:
    manifest = _manifest()
    forged = PhiRemoteCodeManifest(
        entries=manifest.entries,
        sha256="0" * 64,
        byte_length=manifest.byte_length,
    )
    malformed_observation = cast(PhiRemoteCodeExecutionObservation, object())

    with pytest.raises(PhiExecutedSetManifestError, match="canonical bytes"):
        verify_phi_executed_set_evidence(forged, malformed_observation)


def test_manifest_revalidation_rejects_nested_string_subclass_spoof() -> None:
    manifest = _manifest()
    first, second = manifest.entries
    forged_first = PhiRemoteCodeManifestEntry(
        byte_length=first.byte_length,
        git_blob_sha=first.git_blob_sha,
        path=_StringSubclass(first.path),
        sha256=first.sha256,
    )
    forged = PhiRemoteCodeManifest(
        entries=(forged_first, second),
        sha256=manifest.sha256,
        byte_length=manifest.byte_length,
    )
    assert forged == manifest

    with pytest.raises(PhiExecutedSetManifestError, match="non-exact field types"):
        verify_phi_executed_set_evidence(forged, _observation(manifest))


def test_manifest_revalidation_rejects_outer_integer_subclass_spoof() -> None:
    manifest = _manifest()
    forged = PhiRemoteCodeManifest(
        entries=manifest.entries,
        sha256=manifest.sha256,
        byte_length=_IntSubclass(manifest.byte_length),
    )
    assert forged == manifest

    with pytest.raises(PhiExecutedSetManifestError, match="non-exact field types"):
        verify_phi_executed_set_evidence(forged, _observation(manifest))


def test_manifest_requires_exact_validated_type() -> None:
    manifest = _manifest()

    with pytest.raises(PhiExecutedSetManifestError, match="parser-validated"):
        verify_phi_executed_set_evidence(
            cast(PhiRemoteCodeManifest, object()),
            _observation(manifest),
        )


def test_observation_requires_exact_type() -> None:
    manifest = _manifest()

    with pytest.raises(PhiExecutedSetObservationError, match="invalid type"):
        verify_phi_executed_set_evidence(
            manifest,
            cast(PhiRemoteCodeExecutionObservation, object()),
        )


def test_path_container_requires_exact_tuple() -> None:
    manifest = _manifest()
    valid = _observation(manifest)
    invalid_paths = cast(tuple[str, ...], list(valid.executed_remote_code_paths))

    with pytest.raises(PhiExecutedSetObservationError, match="exact tuple"):
        verify_phi_executed_set_evidence(
            manifest,
            replace(valid, executed_remote_code_paths=invalid_paths),
        )


def test_paths_reject_non_string_equality_spoof() -> None:
    manifest = _manifest()
    valid = _observation(manifest)
    first_path, second_path = valid.executed_remote_code_paths
    spoofed_paths = cast(
        tuple[str, ...],
        (_PathSpoof(first_path), second_path),
    )
    assert spoofed_paths == valid.executed_remote_code_paths

    with pytest.raises(PhiExecutedSetObservationError, match="exact strings"):
        verify_phi_executed_set_evidence(
            manifest,
            replace(valid, executed_remote_code_paths=spoofed_paths),
        )


@pytest.mark.parametrize(
    "paths",
    [
        ("modeling_phi4mm.py",),
        ("modeling_phi4mm.py", "processing_phi4mm.py", "extra.py"),
        ("processing_phi4mm.py", "modeling_phi4mm.py"),
        ("modeling_phi4mm.py", "modeling_phi4mm.py", "processing_phi4mm.py"),
    ],
)
def test_executed_path_tuple_must_equal_canonical_manifest(paths: tuple[str, ...]) -> None:
    manifest = _manifest()
    valid = _observation(manifest)

    with pytest.raises(PhiExecutedSetObservationError, match="does not equal"):
        verify_phi_executed_set_evidence(
            manifest,
            replace(valid, executed_remote_code_paths=paths),
        )


def test_all_completeness_controls_require_exact_true() -> None:
    manifest = _manifest()
    valid = _observation(manifest)
    invalid_observations = (
        replace(valid, observation_complete=False),
        replace(valid, observation_started_before_model_process_start=False),
        replace(valid, observation_ended_after_model_process_exit=False),
        replace(valid, observation_complete=cast(bool, 1)),
    )

    for invalid in invalid_observations:
        with pytest.raises(PhiExecutedSetObservationError, match="not proven"):
            verify_phi_executed_set_evidence(manifest, invalid)


def test_dynamic_remote_fetch_attempts_must_be_exact_integer_zero() -> None:
    manifest = _manifest()
    valid = _observation(manifest)
    invalid_observations = (
        replace(valid, dynamic_remote_fetch_attempts=1),
        replace(valid, dynamic_remote_fetch_attempts=-1),
        replace(valid, dynamic_remote_fetch_attempts=True),
    )

    for invalid in invalid_observations:
        with pytest.raises(PhiExecutedSetObservationError, match="exact integer zero"):
            verify_phi_executed_set_evidence(manifest, invalid)


def test_unattributed_execution_events_must_be_exact_integer_zero() -> None:
    manifest = _manifest()
    valid = _observation(manifest)
    invalid_observations = (
        replace(valid, unattributed_remote_code_execution_events=1),
        replace(valid, unattributed_remote_code_execution_events=-1),
        replace(valid, unattributed_remote_code_execution_events=True),
    )

    for invalid in invalid_observations:
        with pytest.raises(PhiExecutedSetObservationError, match="exact integer zero"):
            verify_phi_executed_set_evidence(manifest, invalid)
