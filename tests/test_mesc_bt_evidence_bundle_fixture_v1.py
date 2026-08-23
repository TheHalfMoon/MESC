from __future__ import annotations

from dataclasses import replace
from typing import cast

import pytest

from medscale.mesc._bt_evidence_bundle_fixture_v1 import (
    CANDIDATE_KEYS,
    ArtifactDigest,
    AttemptDisposition,
    CandidateKey,
    EvidenceArtifact,
    FixtureAttemptObservation,
    FixtureEvidenceBlockedError,
    build_fixture_evidence_bundle,
    verify_fixture_evidence_bundle,
)


def _attempt(
    candidate: CandidateKey,
    item_id: str,
    *,
    number: int = 1,
    start: int = 100,
    end: int = 200,
    disposition: AttemptDisposition = "success",
    raw: bytes | None = b"fixture-response",
) -> FixtureAttemptObservation:
    return FixtureAttemptObservation(
        candidate_key=candidate,
        item_id=item_id,
        attempt_number=number,
        start_monotonic_ns=start,
        end_monotonic_ns=end,
        elapsed_ns=end - start,
        disposition=disposition,
        raw_response=raw,
    )


def _matrix(
    item_ids: tuple[str, ...] = ("ITEM-001", "ITEM-002"),
) -> list[FixtureAttemptObservation]:
    return [_attempt(candidate, item_id) for candidate in CANDIDATE_KEYS for item_id in item_ids]


def test_builds_exact_candidate_item_matrix_and_verifies() -> None:
    bundle = build_fixture_evidence_bundle(_matrix(), expected_item_ids=("ITEM-001", "ITEM-002"))
    verify_fixture_evidence_bundle(bundle)
    assert bundle.manifest_sha256
    assert bundle.manifest_bytes.endswith(b"]")
    assert not bundle.manifest_bytes.endswith(b"\n")


def test_deterministic_under_observation_input_permutation() -> None:
    original = _matrix()
    reversed_input = list(reversed(original))
    first = build_fixture_evidence_bundle(original, expected_item_ids=("ITEM-001", "ITEM-002"))
    second = build_fixture_evidence_bundle(
        reversed_input, expected_item_ids=("ITEM-001", "ITEM-002")
    )
    assert first == second


def test_missing_candidate_item_pair_blocks() -> None:
    observations = _matrix()
    observations.pop()
    with pytest.raises(FixtureEvidenceBlockedError, match="missing evidence"):
        build_fixture_evidence_bundle(observations, expected_item_ids=("ITEM-001", "ITEM-002"))


def test_unknown_candidate_blocks() -> None:
    observations = _matrix()
    observations[0] = _attempt(cast(CandidateKey, "unknown"), "ITEM-001")
    with pytest.raises(FixtureEvidenceBlockedError, match="unsupported candidate_key"):
        build_fixture_evidence_bundle(observations, expected_item_ids=("ITEM-001", "ITEM-002"))


def test_unexpected_item_blocks() -> None:
    observations = _matrix()
    observations[0] = _attempt(CANDIDATE_KEYS[0], "ITEM-999")
    with pytest.raises(FixtureEvidenceBlockedError, match="outside expected set"):
        build_fixture_evidence_bundle(observations, expected_item_ids=("ITEM-001", "ITEM-002"))


def test_duplicate_expected_item_blocks() -> None:
    with pytest.raises(FixtureEvidenceBlockedError, match="duplicates"):
        build_fixture_evidence_bundle([], expected_item_ids=("ITEM-001", "ITEM-001"))


def test_empty_expected_item_set_blocks() -> None:
    with pytest.raises(FixtureEvidenceBlockedError, match="must not be empty"):
        build_fixture_evidence_bundle([], expected_item_ids=())


def test_item_id_path_escape_blocks() -> None:
    with pytest.raises(FixtureEvidenceBlockedError, match="path component"):
        build_fixture_evidence_bundle([], expected_item_ids=("../escape",))


def test_elapsed_mismatch_blocks() -> None:
    observations = _matrix()
    observations[0] = replace(observations[0], elapsed_ns=99)
    with pytest.raises(FixtureEvidenceBlockedError, match="elapsed_ns"):
        build_fixture_evidence_bundle(observations, expected_item_ids=("ITEM-001", "ITEM-002"))


def test_negative_monotonic_value_blocks() -> None:
    observations = _matrix()
    observations[0] = replace(observations[0], start_monotonic_ns=-1, elapsed_ns=201)
    with pytest.raises(FixtureEvidenceBlockedError, match="start_monotonic_ns"):
        build_fixture_evidence_bundle(observations, expected_item_ids=("ITEM-001", "ITEM-002"))


def test_end_before_start_blocks() -> None:
    observations = _matrix()
    observations[0] = replace(
        observations[0], start_monotonic_ns=200, end_monotonic_ns=100, elapsed_ns=0
    )
    with pytest.raises(FixtureEvidenceBlockedError, match="precedes"):
        build_fixture_evidence_bundle(observations, expected_item_ids=("ITEM-001", "ITEM-002"))


def test_success_without_raw_response_blocks() -> None:
    observations = _matrix()
    observations[0] = replace(observations[0], raw_response=None)
    with pytest.raises(FixtureEvidenceBlockedError, match="successful attempt"):
        build_fixture_evidence_bundle(observations, expected_item_ids=("ITEM-001", "ITEM-002"))


def test_only_infrastructure_failure_can_trigger_second_attempt() -> None:
    observations = _matrix(("ITEM-001",))
    observations[0] = _attempt(
        CANDIDATE_KEYS[0],
        "ITEM-001",
        number=1,
        start=100,
        end=300,
        disposition="infrastructure_error",
        raw=None,
    )
    observations.append(
        _attempt(
            CANDIDATE_KEYS[0],
            "ITEM-001",
            number=2,
            start=400,
            end=700,
            disposition="success",
            raw=b"retry-ok",
        )
    )
    bundle = build_fixture_evidence_bundle(observations, expected_item_ids=("ITEM-001",))
    items = next(item.payload for item in bundle.artifacts if item.path == "items.jsonl")
    assert b'"terminal_item_latency_ns":500' in items
    assert b'"attempt_count":2' in items

    timeout_observations = _matrix(("ITEM-001",))
    timeout_observations[0] = _attempt(
        CANDIDATE_KEYS[0],
        "ITEM-001",
        number=1,
        start=100,
        end=300,
        disposition="timeout",
        raw=None,
    )
    timeout_observations.append(
        _attempt(
            CANDIDATE_KEYS[0],
            "ITEM-001",
            number=2,
            start=400,
            end=700,
            disposition="success",
            raw=b"must-not-be-admitted",
        )
    )
    with pytest.raises(FixtureEvidenceBlockedError, match="requires infrastructure_error"):
        build_fixture_evidence_bundle(timeout_observations, expected_item_ids=("ITEM-001",))


def test_retry_after_success_blocks() -> None:
    observations = _matrix(("ITEM-001",))
    observations.append(_attempt(CANDIDATE_KEYS[0], "ITEM-001", number=2, start=300, end=400))
    with pytest.raises(FixtureEvidenceBlockedError, match="requires infrastructure_error"):
        build_fixture_evidence_bundle(observations, expected_item_ids=("ITEM-001",))


def test_duplicate_attempt_number_blocks() -> None:
    observations = _matrix(("ITEM-001",))
    observations[0] = replace(
        observations[0], disposition="infrastructure_error", raw_response=None
    )
    observations.append(_attempt(CANDIDATE_KEYS[0], "ITEM-001", number=1, disposition="success"))
    with pytest.raises(FixtureEvidenceBlockedError, match="unique and contiguous"):
        build_fixture_evidence_bundle(observations, expected_item_ids=("ITEM-001",))


def test_third_attempt_blocks() -> None:
    observations = _matrix(("ITEM-001",))
    observations[0] = replace(
        observations[0], disposition="infrastructure_error", raw_response=None
    )
    observations.extend(
        [
            _attempt(
                CANDIDATE_KEYS[0],
                "ITEM-001",
                number=2,
                disposition="infrastructure_error",
                raw=None,
            ),
            replace(_attempt(CANDIDATE_KEYS[0], "ITEM-001"), attempt_number=2),
        ]
    )
    with pytest.raises(FixtureEvidenceBlockedError, match="one or two attempts"):
        build_fixture_evidence_bundle(observations, expected_item_ids=("ITEM-001",))


def test_raw_response_is_separate_hashed_artifact() -> None:
    bundle = build_fixture_evidence_bundle(_matrix(("ITEM-001",)), expected_item_ids=("ITEM-001",))
    raw = next(item for item in bundle.artifacts if item.path.endswith("attempt-1.bin"))
    digest = next(item for item in bundle.manifest if item.path == raw.path)
    assert digest.byte_length == len(raw.payload)
    assert len(digest.sha256) == 64
    attempts = next(item.payload for item in bundle.artifacts if item.path == "attempts.jsonl")
    assert raw.payload not in attempts
    assert digest.sha256.encode("ascii") in attempts


def test_manifest_paths_are_sorted_and_unique() -> None:
    bundle = build_fixture_evidence_bundle(_matrix(("ITEM-001",)), expected_item_ids=("ITEM-001",))
    paths = [item.path for item in bundle.manifest]
    assert paths == sorted(paths)
    assert len(paths) == len(set(paths))


def test_verify_rejects_tampered_artifact_bytes() -> None:
    bundle = build_fixture_evidence_bundle(_matrix(("ITEM-001",)), expected_item_ids=("ITEM-001",))
    artifacts = list(bundle.artifacts)
    artifacts[0] = EvidenceArtifact(path=artifacts[0].path, payload=artifacts[0].payload + b"x")
    tampered = replace(bundle, artifacts=tuple(artifacts))
    with pytest.raises(FixtureEvidenceBlockedError, match="manifest does not match"):
        verify_fixture_evidence_bundle(tampered)


def test_verify_rejects_tampered_manifest_bytes() -> None:
    bundle = build_fixture_evidence_bundle(_matrix(("ITEM-001",)), expected_item_ids=("ITEM-001",))
    tampered = replace(bundle, manifest_bytes=bundle.manifest_bytes + b"\n")
    with pytest.raises(FixtureEvidenceBlockedError, match="manifest bytes"):
        verify_fixture_evidence_bundle(tampered)


def test_verify_rejects_tampered_manifest_sha256() -> None:
    bundle = build_fixture_evidence_bundle(_matrix(("ITEM-001",)), expected_item_ids=("ITEM-001",))
    tampered = replace(bundle, manifest_sha256="0" * 64)
    with pytest.raises(FixtureEvidenceBlockedError, match="manifest SHA-256"):
        verify_fixture_evidence_bundle(tampered)


def test_verify_rejects_duplicate_artifact_path() -> None:
    bundle = build_fixture_evidence_bundle(_matrix(("ITEM-001",)), expected_item_ids=("ITEM-001",))
    duplicate = replace(bundle, artifacts=(*bundle.artifacts, bundle.artifacts[0]))
    with pytest.raises(FixtureEvidenceBlockedError, match="duplicate artifact path"):
        verify_fixture_evidence_bundle(duplicate)


def test_verify_rejects_unsorted_artifacts() -> None:
    bundle = build_fixture_evidence_bundle(_matrix(("ITEM-001",)), expected_item_ids=("ITEM-001",))
    unsorted = replace(bundle, artifacts=tuple(reversed(bundle.artifacts)))
    with pytest.raises(FixtureEvidenceBlockedError, match="sorted canonically"):
        verify_fixture_evidence_bundle(unsorted)


def test_verify_rejects_manifest_entry_tamper() -> None:
    bundle = build_fixture_evidence_bundle(_matrix(("ITEM-001",)), expected_item_ids=("ITEM-001",))
    manifest = list(bundle.manifest)
    manifest[0] = ArtifactDigest(
        path=manifest[0].path,
        byte_length=manifest[0].byte_length + 1,
        sha256=manifest[0].sha256,
    )
    tampered = replace(bundle, manifest=tuple(manifest))
    with pytest.raises(FixtureEvidenceBlockedError, match="manifest does not match"):
        verify_fixture_evidence_bundle(tampered)
