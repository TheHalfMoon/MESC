"""Fixture-only Backbone Tournament evidence-bundle primitives.

This module is a bounded implementation scaffold for FD-MESC-BT-EXEC-1
Section D. It validates caller-supplied fixture attempt observations and
serializes deterministic evidence artifacts. It performs no filesystem I/O,
network access, model access, prompt construction, inference, or provider work.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, TypeAlias

CandidateKey: TypeAlias = Literal[
    "gpt_oss_20b",
    "apertus_1_5_8b",
    "phi_4_multimodal_instruct",
    "medgemma_1_5_4b_it",
]
AttemptDisposition: TypeAlias = Literal[
    "success",
    "timeout",
    "infrastructure_error",
    "terminal_error",
]

CANDIDATE_KEYS: Final[tuple[CandidateKey, ...]] = (
    "gpt_oss_20b",
    "apertus_1_5_8b",
    "phi_4_multimodal_instruct",
    "medgemma_1_5_4b_it",
)

_PATH_COMPONENT_RE: Final = re.compile(r"^[A-Za-z0-9._-]+$")
_RETRYABLE: Final = frozenset({"infrastructure_error"})
_ALLOWED_DISPOSITIONS: Final = frozenset(
    {"success", "timeout", "infrastructure_error", "terminal_error"}
)


class FixtureEvidenceError(ValueError):
    """Base class for fixture evidence-contract failures."""


class FixtureEvidenceBlockedError(FixtureEvidenceError):
    """A fail-closed evidence condition that blocks bundle construction."""


@dataclass(frozen=True, slots=True)
class FixtureAttemptObservation:
    """One caller-supplied generation-attempt observation over fixture data."""

    candidate_key: CandidateKey
    item_id: str
    attempt_number: int
    start_monotonic_ns: int
    end_monotonic_ns: int
    elapsed_ns: int
    disposition: AttemptDisposition
    raw_response: bytes | None


@dataclass(frozen=True, slots=True)
class EvidenceArtifact:
    """One deterministic artifact emitted by the fixture evidence compiler."""

    path: str
    payload: bytes


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    """Manifest identity for one emitted artifact."""

    path: str
    byte_length: int
    sha256: str


@dataclass(frozen=True, slots=True)
class FixtureEvidenceBundle:
    """Deterministic evidence artifacts plus the manifest over those artifacts."""

    artifacts: tuple[EvidenceArtifact, ...]
    manifest: tuple[ArtifactDigest, ...]
    manifest_bytes: bytes
    manifest_sha256: str


def build_fixture_evidence_bundle(
    observations: Sequence[FixtureAttemptObservation],
    *,
    expected_item_ids: Sequence[str],
) -> FixtureEvidenceBundle:
    """Validate fixture observations and build deterministic evidence artifacts.

    Output ordering is candidate-major using ``CANDIDATE_KEYS`` and then the
    caller-supplied ``expected_item_ids`` order. Attempts are ordered by attempt
    number. The function is pure: all returned artifacts exist only as bytes.
    """
    item_ids = _validate_expected_item_ids(expected_item_ids)
    grouped = _group_observations(observations, item_ids)

    attempt_documents: list[dict[str, object]] = []
    item_documents: list[dict[str, object]] = []
    raw_artifacts: list[EvidenceArtifact] = []

    for candidate_key in CANDIDATE_KEYS:
        for item_id in item_ids:
            key = (candidate_key, item_id)
            attempts = grouped.get(key)
            if attempts is None:
                raise FixtureEvidenceBlockedError(
                    f"missing evidence for candidate/item pair: {candidate_key}/{item_id}"
                )
            ordered = _validate_attempt_sequence(candidate_key, item_id, attempts)
            for observation in ordered:
                raw_path: str | None = None
                raw_sha256: str | None = None
                raw_byte_length: int | None = None
                if observation.raw_response is not None:
                    raw_path = _raw_response_path(observation)
                    raw_payload = observation.raw_response
                    raw_sha256 = _sha256(raw_payload)
                    raw_byte_length = len(raw_payload)
                    raw_artifacts.append(EvidenceArtifact(path=raw_path, payload=raw_payload))
                if observation.disposition == "success" and observation.raw_response is None:
                    raise FixtureEvidenceBlockedError(
                        "successful attempt must carry exact raw-response bytes"
                    )
                attempt_documents.append(
                    {
                        "attempt_number": observation.attempt_number,
                        "candidate_key": observation.candidate_key,
                        "disposition": observation.disposition,
                        "elapsed_ns": observation.elapsed_ns,
                        "end_monotonic_ns": observation.end_monotonic_ns,
                        "item_id": observation.item_id,
                        "raw_response_byte_length": raw_byte_length,
                        "raw_response_path": raw_path,
                        "raw_response_sha256": raw_sha256,
                        "start_monotonic_ns": observation.start_monotonic_ns,
                    }
                )

            item_documents.append(
                {
                    "attempt_count": len(ordered),
                    "candidate_key": candidate_key,
                    "item_id": item_id,
                    "terminal_disposition": ordered[-1].disposition,
                    "terminal_item_latency_ns": sum(item.elapsed_ns for item in ordered),
                }
            )

    raw_artifacts.sort(key=lambda artifact: artifact.path.encode("ascii"))
    fixed_artifacts = [
        EvidenceArtifact(path="attempts.jsonl", payload=_canonical_jsonl(attempt_documents)),
        EvidenceArtifact(path="items.jsonl", payload=_canonical_jsonl(item_documents)),
    ]
    artifacts = tuple(sorted(raw_artifacts + fixed_artifacts, key=lambda item: item.path))
    _require_unique_artifact_paths(artifacts)

    manifest = tuple(
        ArtifactDigest(
            path=artifact.path,
            byte_length=len(artifact.payload),
            sha256=_sha256(artifact.payload),
        )
        for artifact in artifacts
    )
    manifest_bytes = _canonical_json(
        [
            {
                "byte_length": entry.byte_length,
                "path": entry.path,
                "sha256": entry.sha256,
            }
            for entry in manifest
        ]
    )
    return FixtureEvidenceBundle(
        artifacts=artifacts,
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        manifest_sha256=_sha256(manifest_bytes),
    )


def verify_fixture_evidence_bundle(bundle: FixtureEvidenceBundle) -> None:
    """Recompute every digest/length and require exact manifest bytes."""
    _require_unique_artifact_paths(bundle.artifacts)
    paths = tuple(artifact.path for artifact in bundle.artifacts)
    if paths != tuple(sorted(paths)):
        raise FixtureEvidenceBlockedError("artifact paths must be sorted canonically")

    recomputed = tuple(
        ArtifactDigest(
            path=artifact.path,
            byte_length=len(artifact.payload),
            sha256=_sha256(artifact.payload),
        )
        for artifact in bundle.artifacts
    )
    if bundle.manifest != recomputed:
        raise FixtureEvidenceBlockedError("artifact manifest does not match exact artifact bytes")

    expected_manifest_bytes = _canonical_json(
        [
            {
                "byte_length": entry.byte_length,
                "path": entry.path,
                "sha256": entry.sha256,
            }
            for entry in recomputed
        ]
    )
    if bundle.manifest_bytes != expected_manifest_bytes:
        raise FixtureEvidenceBlockedError("manifest bytes are not canonical for the artifact set")
    if bundle.manifest_sha256 != _sha256(expected_manifest_bytes):
        raise FixtureEvidenceBlockedError("manifest SHA-256 does not match exact manifest bytes")


def _validate_expected_item_ids(expected_item_ids: Sequence[str]) -> tuple[str, ...]:
    item_ids = tuple(expected_item_ids)
    if not item_ids:
        raise FixtureEvidenceBlockedError("expected_item_ids must not be empty")
    if len(set(item_ids)) != len(item_ids):
        raise FixtureEvidenceBlockedError("expected_item_ids contains duplicates")
    for item_id in item_ids:
        _validate_component(item_id, field="item_id")
    return item_ids


def _group_observations(
    observations: Sequence[FixtureAttemptObservation],
    item_ids: tuple[str, ...],
) -> dict[tuple[CandidateKey, str], list[FixtureAttemptObservation]]:
    expected_items = frozenset(item_ids)
    groups: dict[tuple[CandidateKey, str], list[FixtureAttemptObservation]] = {}
    for observation in observations:
        candidate_key = _validate_candidate_key(observation.candidate_key)
        _validate_component(observation.item_id, field="item_id")
        if observation.item_id not in expected_items:
            raise FixtureEvidenceBlockedError(
                f"observation item_id is outside expected set: {observation.item_id}"
            )
        _validate_observation_scalars(observation)
        groups.setdefault((candidate_key, observation.item_id), []).append(observation)
    return groups


def _validate_candidate_key(value: object) -> CandidateKey:
    if type(value) is not str or value not in CANDIDATE_KEYS:
        raise FixtureEvidenceBlockedError(f"unsupported candidate_key: {value!r}")
    return value


def _validate_component(value: object, *, field: str) -> str:
    if type(value) is not str or not value or _PATH_COMPONENT_RE.fullmatch(value) is None:
        raise FixtureEvidenceBlockedError(f"{field} must be a non-empty ASCII path component")
    if value in {".", ".."}:
        raise FixtureEvidenceBlockedError(f"{field} may not be '.' or '..'")
    return value


def _validate_observation_scalars(observation: FixtureAttemptObservation) -> None:
    attempt_number = _require_nonnegative_int(observation.attempt_number, field="attempt_number")
    if attempt_number not in {1, 2}:
        raise FixtureEvidenceBlockedError("attempt_number must be exactly 1 or 2")

    start_monotonic_ns = _require_nonnegative_int(
        observation.start_monotonic_ns, field="start_monotonic_ns"
    )
    end_monotonic_ns = _require_nonnegative_int(
        observation.end_monotonic_ns, field="end_monotonic_ns"
    )
    elapsed_ns = _require_nonnegative_int(observation.elapsed_ns, field="elapsed_ns")
    if end_monotonic_ns < start_monotonic_ns:
        raise FixtureEvidenceBlockedError("end_monotonic_ns precedes start_monotonic_ns")
    if elapsed_ns != end_monotonic_ns - start_monotonic_ns:
        raise FixtureEvidenceBlockedError("elapsed_ns does not match monotonic timestamps")

    disposition: object = observation.disposition
    if type(disposition) is not str or disposition not in _ALLOWED_DISPOSITIONS:
        raise FixtureEvidenceBlockedError(f"unsupported disposition: {disposition!r}")

    raw_response: object = observation.raw_response
    if raw_response is not None and type(raw_response) is not bytes:
        raise FixtureEvidenceBlockedError("raw_response must be exact bytes or None")


def _require_nonnegative_int(value: object, *, field: str) -> int:
    if type(value) is not int:
        raise FixtureEvidenceBlockedError(f"{field} must be a non-negative integer")
    if value < 0:
        raise FixtureEvidenceBlockedError(f"{field} must be a non-negative integer")
    return value


def _validate_attempt_sequence(
    candidate_key: CandidateKey,
    item_id: str,
    observations: Sequence[FixtureAttemptObservation],
) -> tuple[FixtureAttemptObservation, ...]:
    if len(observations) not in {1, 2}:
        raise FixtureEvidenceBlockedError(
            f"candidate/item pair must contain one or two attempts: {candidate_key}/{item_id}"
        )
    ordered = tuple(sorted(observations, key=lambda item: item.attempt_number))
    expected_numbers = tuple(range(1, len(ordered) + 1))
    actual_numbers = tuple(item.attempt_number for item in ordered)
    if actual_numbers != expected_numbers:
        raise FixtureEvidenceBlockedError("attempt numbers must be unique and contiguous from one")
    if len(ordered) == 2 and ordered[0].disposition not in _RETRYABLE:
        raise FixtureEvidenceBlockedError(
            "second attempt requires infrastructure_error as the first disposition"
        )
    return ordered


def _raw_response_path(observation: FixtureAttemptObservation) -> str:
    return (
        f"raw-responses/{observation.candidate_key}/{observation.item_id}/"
        f"attempt-{observation.attempt_number}.bin"
    )


def _require_unique_artifact_paths(artifacts: Sequence[EvidenceArtifact]) -> None:
    seen: set[str] = set()
    for artifact in artifacts:
        _validate_artifact_path(artifact.path)
        if type(artifact.payload) is not bytes:
            raise FixtureEvidenceBlockedError("artifact payload must be exact bytes")
        if artifact.path in seen:
            raise FixtureEvidenceBlockedError(f"duplicate artifact path: {artifact.path}")
        seen.add(artifact.path)


def _validate_artifact_path(path: object) -> str:
    if type(path) is not str or not path:
        raise FixtureEvidenceBlockedError("artifact path must be a non-empty string")
    try:
        path.encode("ascii")
    except UnicodeEncodeError as error:
        raise FixtureEvidenceBlockedError("artifact path must be ASCII") from error
    parts = path.split("/")
    if any(_PATH_COMPONENT_RE.fullmatch(part) is None or part in {".", ".."} for part in parts):
        raise FixtureEvidenceBlockedError("artifact path violates the closed ASCII grammar")
    return path


def _canonical_json(value: object) -> bytes:
    text = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return text.encode("ascii")


def _canonical_jsonl(records: Sequence[dict[str, object]]) -> bytes:
    return b"".join(_canonical_json(record) + b"\n" for record in records)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
