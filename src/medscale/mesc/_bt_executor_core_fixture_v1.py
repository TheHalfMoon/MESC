"""Fixture-only Backbone Tournament executor core primitives.

This module is an implementation scaffold for ``FD-MESC-BT-EXEC-1`` Section D.
It deliberately has no model loader, provider client, network code, filesystem
reader, credential access, runtime acquisition, prompt template, or canonical
Repair-2 corpus loader.  Every execution surface is dependency-injected and is
restricted to deterministic fixture data.

The core provides exact candidate ordering, model-visible/gold separation,
bounded retry state, monotonic attempt timing, raw-response evidence capture,
strict post-generation hook ordering, latency aggregation, and artifact hashing.
It grants no execution authority and cannot perform a live tournament by itself.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final, Literal, Protocol, TypeAlias, cast

CandidateKey: TypeAlias = Literal[
    "gpt_oss_20b",
    "apertus_1_5_8b",
    "phi_4_multimodal_instruct",
    "medgemma_1_5_4b_it",
]
AttemptFailureKind: TypeAlias = Literal["timeout", "infrastructure_error", "terminal_error"]
AttemptDisposition: TypeAlias = Literal[
    "success",
    "timeout",
    "infrastructure_error",
    "terminal_error",
]
RetryableFailureKind: TypeAlias = Literal["timeout", "infrastructure_error"]
JsonValue: TypeAlias = "bool | int | str | list[JsonValue] | dict[str, JsonValue] | None"

_PATH_RE: Final = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$")
_MAX_ATTEMPTS: Final = 2
_NANOSECONDS_PER_MILLISECOND: Final = 1_000_000
_TOURNAMENT_ITEM_COUNT: Final = 240


class FixtureExecutorError(ValueError):
    """Base class for fixture executor contract violations."""


class FixtureExecutorBlockedError(FixtureExecutorError):
    """A fail-closed executor condition that must terminate the current operation."""


class FixtureProjectionError(FixtureExecutorError):
    """Fixture payload projection is invalid or exposes a prohibited gold key."""


class FixtureAttemptFailureError(RuntimeError):
    """A classified attempt failure emitted by a fixture adapter."""

    def __init__(self, kind: AttemptFailureKind) -> None:
        super().__init__(kind)
        self.kind = kind


@dataclass(frozen=True, slots=True)
class CandidateBinding:
    """One immutable candidate identity from FD-MESC-BT-EXEC-1 Section C."""

    key: CandidateKey
    model_id: str
    model_revision: str
    processor_id: str
    processor_revision: str
    trust_remote_code: bool
    precision_mode: str
    gated_access: bool


TOURNAMENT_CANDIDATES: Final = (
    CandidateBinding(
        key="gpt_oss_20b",
        model_id="openai/gpt-oss-20b",
        model_revision="6cee5e81ee83917806bbde320786a8fb61efebee",
        processor_id="openai/gpt-oss-20b",
        processor_revision="6cee5e81ee83917806bbde320786a8fb61efebee",
        trust_remote_code=False,
        precision_mode="NATIVE_MXFP4",
        gated_access=False,
    ),
    CandidateBinding(
        key="apertus_1_5_8b",
        model_id="swiss-ai/Apertus-v1.5-8B",
        model_revision="a411d838600baf0e3635a3daf66fb7c55fc97bb6",
        processor_id="swiss-ai/Apertus-v1.5-8B",
        processor_revision="a411d838600baf0e3635a3daf66fb7c55fc97bb6",
        trust_remote_code=False,
        precision_mode="BF16",
        gated_access=True,
    ),
    CandidateBinding(
        key="phi_4_multimodal_instruct",
        model_id="microsoft/Phi-4-multimodal-instruct",
        model_revision="93f923e1a7727d1c4f446756212d9d3e8fcc5d81",
        processor_id="microsoft/Phi-4-multimodal-instruct",
        processor_revision="93f923e1a7727d1c4f446756212d9d3e8fcc5d81",
        trust_remote_code=True,
        precision_mode="BF16",
        gated_access=False,
    ),
    CandidateBinding(
        key="medgemma_1_5_4b_it",
        model_id="google/medgemma-1.5-4b-it",
        model_revision="91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b",
        processor_id="google/medgemma-1.5-4b-it",
        processor_revision="91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b",
        trust_remote_code=False,
        precision_mode="BF16",
        gated_access=True,
    ),
)
_CANDIDATE_BY_KEY: Final = {candidate.key: candidate for candidate in TOURNAMENT_CANDIDATES}


@dataclass(frozen=True, slots=True)
class FixtureExecutionItem:
    """Immutable fixture input with physically separate model-visible and gold bytes."""

    item_id: str
    axis: str
    model_payload: bytes
    model_payload_sha256: str
    gold_payload: bytes
    gold_payload_sha256: str


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Activation-bindable retry policy with a hard maximum of one retry."""

    timeout_ms: int
    retryable_failure_kinds: frozenset[RetryableFailureKind]

    def __post_init__(self) -> None:
        if type(self.timeout_ms) is not int or self.timeout_ms <= 0:
            raise FixtureExecutorError("timeout_ms must be a positive integer")
        allowed = frozenset({"infrastructure_error"})
        if not self.retryable_failure_kinds.issubset(allowed):
            raise FixtureExecutorError("only infrastructure_error may be retryable")
        object.__setattr__(self, "retryable_failure_kinds", frozenset(self.retryable_failure_kinds))


@dataclass(frozen=True, slots=True)
class AttemptEvidence:
    """Exact evidence for one fixture generation attempt."""

    candidate_key: CandidateKey
    item_id: str
    attempt_number: int
    start_monotonic_ns: int
    end_monotonic_ns: int
    elapsed_ns: int
    elapsed_ms: float
    disposition: AttemptDisposition
    raw_response: str | None
    raw_response_sha256: str | None


@dataclass(frozen=True, slots=True)
class ItemExecutionResult:
    """Terminal fixture result for one candidate/item pair."""

    candidate_key: CandidateKey
    item_id: str
    attempts: tuple[AttemptEvidence, ...]
    terminal_disposition: AttemptDisposition
    terminal_item_latency_ms: float
    raw_response: str | None
    raw_response_sha256: str | None
    postprocess_complete: bool


@dataclass(frozen=True, slots=True)
class FixtureTournamentItemResult:
    """Sequential results for exactly the four authorized candidate identities."""

    item_id: str
    candidate_results: tuple[ItemExecutionResult, ...]


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    """SHA-256 and byte length for one deterministic artifact."""

    path: str
    sha256: str
    byte_length: int


@dataclass(frozen=True, slots=True)
class CandidateLatencySummary:
    """Raw 240-item terminal latencies and their contract median."""

    candidate_key: CandidateKey
    terminal_item_latency_ms: tuple[float, ...]
    median_latency_ms: float


class FixtureAttemptAdapter(Protocol):
    """A non-production adapter used only by deterministic fixture qualification."""

    fixture_only: bool

    def invoke(
        self,
        candidate: CandidateBinding,
        model_payload: bytes,
        timeout_ms: int,
    ) -> str: ...


Parser = Callable[[str], object]
SchemaValidator = Callable[[object], None]
Scorer = Callable[[object, bytes], object]
ReportValidator = Callable[[str, CandidateBinding, object, object], None]
MonotonicClock = Callable[[], int]


@dataclass(frozen=True, slots=True)
class PostGenerationHooks:
    """Strict parser -> schema -> scorer -> report-validator hook chain."""

    parser: Parser
    schema_validator: SchemaValidator
    scorer: Scorer
    report_validator: ReportValidator


def build_fixture_item(
    *,
    item_id: str,
    axis: str,
    model_payload: Mapping[str, object],
    gold_payload: Mapping[str, object],
    forbidden_gold_keys: frozenset[str],
) -> FixtureExecutionItem:
    """Build an immutable fixture item while proving key-based gold non-exposure."""
    if type(item_id) is not str or not item_id.strip():
        raise FixtureProjectionError("item_id must be a non-blank string")
    if type(axis) is not str or not axis.strip():
        raise FixtureProjectionError("axis must be a non-blank string")
    if not forbidden_gold_keys:
        raise FixtureProjectionError("forbidden_gold_keys must not be empty")
    if any(type(key) is not str or not key for key in forbidden_gold_keys):
        raise FixtureProjectionError("forbidden_gold_keys must contain non-empty strings")

    normalized_model = _normalize_json(model_payload)
    normalized_gold = _normalize_json(gold_payload)
    _reject_forbidden_keys(normalized_model, forbidden_gold_keys)
    model_bytes = _canonical_json_bytes(normalized_model)
    gold_bytes = _canonical_json_bytes(normalized_gold)
    return FixtureExecutionItem(
        item_id=item_id,
        axis=axis,
        model_payload=model_bytes,
        model_payload_sha256=_sha256(model_bytes),
        gold_payload=gold_bytes,
        gold_payload_sha256=_sha256(gold_bytes),
    )


def run_fixture_item(
    *,
    item: FixtureExecutionItem,
    candidate_key: CandidateKey,
    adapter: FixtureAttemptAdapter,
    retry_policy: RetryPolicy,
    hooks: PostGenerationHooks,
    monotonic_ns: MonotonicClock,
) -> ItemExecutionResult:
    """Run one candidate/item fixture through the bounded attempt state machine."""
    candidate = _candidate(candidate_key)
    if getattr(adapter, "fixture_only", None) is not True:
        raise FixtureExecutorBlockedError("adapter must explicitly declare fixture_only=True")

    attempts: list[AttemptEvidence] = []
    for attempt_number in range(1, _MAX_ATTEMPTS + 1):
        evidence = _invoke_fixture_attempt(
            item=item,
            candidate=candidate,
            adapter=adapter,
            timeout_ms=retry_policy.timeout_ms,
            attempt_number=attempt_number,
            monotonic_ns=monotonic_ns,
        )
        attempts.append(evidence)
        if evidence.disposition == "success":
            _run_post_generation_hooks(item, candidate, evidence.raw_response, hooks)
            return _build_item_result(item, candidate, attempts, postprocess_complete=True)

        retryable = evidence.disposition in retry_policy.retryable_failure_kinds
        if attempt_number == 1 and retryable:
            continue
        return _build_item_result(item, candidate, attempts, postprocess_complete=False)

    raise FixtureExecutorBlockedError("attempt state machine exceeded its hard bound")


def run_fixture_item_across_all_candidates(
    *,
    item: FixtureExecutionItem,
    adapter: FixtureAttemptAdapter,
    retry_policy: RetryPolicy,
    hooks: PostGenerationHooks,
    monotonic_ns: MonotonicClock,
) -> FixtureTournamentItemResult:
    """Run one fixture item sequentially over the exact four-candidate order."""
    results = tuple(
        run_fixture_item(
            item=item,
            candidate_key=candidate.key,
            adapter=adapter,
            retry_policy=retry_policy,
            hooks=hooks,
            monotonic_ns=monotonic_ns,
        )
        for candidate in TOURNAMENT_CANDIDATES
    )
    return FixtureTournamentItemResult(item_id=item.item_id, candidate_results=results)


def summarize_candidate_latencies(
    candidate_key: CandidateKey,
    results: tuple[ItemExecutionResult, ...],
) -> CandidateLatencySummary:
    """Require exactly 240 unique item results and compute the frozen median rule."""
    _candidate(candidate_key)
    if len(results) != _TOURNAMENT_ITEM_COUNT:
        raise FixtureExecutorBlockedError(
            "candidate latency summary requires exactly 240 item results"
        )
    if any(result.candidate_key != candidate_key for result in results):
        raise FixtureExecutorBlockedError("candidate latency summary mixes candidate identities")
    item_ids = [result.item_id for result in results]
    if len(set(item_ids)) != _TOURNAMENT_ITEM_COUNT:
        raise FixtureExecutorBlockedError("candidate latency summary contains duplicate item IDs")
    values = tuple(result.terminal_item_latency_ms for result in results)
    median = _median_240(values)
    return CandidateLatencySummary(
        candidate_key=candidate_key,
        terminal_item_latency_ms=values,
        median_latency_ms=median,
    )


def hash_artifacts(artifacts: Mapping[str, bytes]) -> tuple[ArtifactDigest, ...]:
    """Hash exact artifact bytes in deterministic ASCII-path order."""
    validated_paths = [_validate_artifact_path(path) for path in artifacts]
    entries: list[ArtifactDigest] = []
    for path in sorted(validated_paths, key=lambda value: value.encode("ascii")):
        payload = artifacts[path]
        if type(payload) is not bytes:
            raise FixtureExecutorBlockedError(f"artifact {path!r} must be exact bytes")
        entries.append(ArtifactDigest(path=path, sha256=_sha256(payload), byte_length=len(payload)))
    return tuple(entries)


def _invoke_fixture_attempt(
    *,
    item: FixtureExecutionItem,
    candidate: CandidateBinding,
    adapter: FixtureAttemptAdapter,
    timeout_ms: int,
    attempt_number: int,
    monotonic_ns: MonotonicClock,
) -> AttemptEvidence:
    start = _read_monotonic_ns(monotonic_ns)
    raw_response: str | None = None
    disposition: AttemptDisposition = "terminal_error"
    unknown_error: Exception | None = None
    try:
        raw_response = adapter.invoke(candidate, item.model_payload, timeout_ms)
        if type(raw_response) is not str:
            raise FixtureExecutorBlockedError("fixture adapter must return a string response")
        disposition = "success"
    except FixtureAttemptFailureError as error:
        disposition = error.kind
    except FixtureExecutorError:
        raise
    except Exception as error:
        unknown_error = error
    end = _read_monotonic_ns(monotonic_ns)
    if end < start:
        raise FixtureExecutorBlockedError("monotonic clock moved backwards")
    elapsed_ns = end - start
    evidence = AttemptEvidence(
        candidate_key=candidate.key,
        item_id=item.item_id,
        attempt_number=attempt_number,
        start_monotonic_ns=start,
        end_monotonic_ns=end,
        elapsed_ns=elapsed_ns,
        elapsed_ms=elapsed_ns / _NANOSECONDS_PER_MILLISECOND,
        disposition=disposition,
        raw_response=raw_response,
        raw_response_sha256=None if raw_response is None else _sha256(raw_response.encode("utf-8")),
    )
    if unknown_error is not None:
        message = "fixture adapter raised an unclassified exception"
        raise FixtureExecutorBlockedError(message) from unknown_error
    return evidence


def _run_post_generation_hooks(
    item: FixtureExecutionItem,
    candidate: CandidateBinding,
    raw_response: str | None,
    hooks: PostGenerationHooks,
) -> None:
    if raw_response is None:
        raise FixtureExecutorBlockedError("successful attempt is missing its raw response")
    try:
        parsed = hooks.parser(raw_response)
        hooks.schema_validator(parsed)
        score = hooks.scorer(parsed, item.gold_payload)
        hooks.report_validator(item.item_id, candidate, parsed, score)
    except Exception as error:
        raise FixtureExecutorBlockedError("post-generation hook chain failed closed") from error


def _build_item_result(
    item: FixtureExecutionItem,
    candidate: CandidateBinding,
    attempts: list[AttemptEvidence],
    *,
    postprocess_complete: bool,
) -> ItemExecutionResult:
    if not attempts:
        raise FixtureExecutorBlockedError("item result requires at least one attempt")
    terminal = attempts[-1]
    latency_ms = sum(attempt.elapsed_ms for attempt in attempts)
    if not math.isfinite(latency_ms) or latency_ms < 0:
        raise FixtureExecutorBlockedError(
            "terminal item latency is not a non-negative finite number"
        )
    return ItemExecutionResult(
        candidate_key=candidate.key,
        item_id=item.item_id,
        attempts=tuple(attempts),
        terminal_disposition=terminal.disposition,
        terminal_item_latency_ms=latency_ms,
        raw_response=terminal.raw_response,
        raw_response_sha256=terminal.raw_response_sha256,
        postprocess_complete=postprocess_complete,
    )


def _candidate(candidate_key: CandidateKey) -> CandidateBinding:
    try:
        return _CANDIDATE_BY_KEY[candidate_key]
    except KeyError as error:
        raise FixtureExecutorBlockedError(f"unknown candidate key: {candidate_key!r}") from error


def _median_240(values: tuple[float, ...]) -> float:
    if len(values) != _TOURNAMENT_ITEM_COUNT:
        raise FixtureExecutorBlockedError("median requires exactly 240 terminal item latencies")
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise FixtureExecutorBlockedError("latency values must be numeric")
        if not math.isfinite(value) or value < 0:
            raise FixtureExecutorBlockedError("latency values must be non-negative and finite")
    ordered = sorted(float(value) for value in values)
    return (ordered[119] + ordered[120]) / 2.0


def _read_monotonic_ns(clock: MonotonicClock) -> int:
    value = clock()
    if type(value) is not int or value < 0:
        message = "monotonic clock must return a non-negative integer nanosecond value"
        raise FixtureExecutorBlockedError(message)
    return value


def _validate_artifact_path(path: object) -> str:
    if type(path) is not str:
        raise FixtureExecutorBlockedError("artifact path must be a string")
    try:
        path.encode("ascii")
    except UnicodeEncodeError as error:
        raise FixtureExecutorBlockedError("artifact path must be ASCII") from error
    if _PATH_RE.fullmatch(path) is None:
        raise FixtureExecutorBlockedError(f"invalid artifact path: {path!r}")
    if any(component in {".", ".."} for component in path.split("/")):
        raise FixtureExecutorBlockedError(f"artifact path contains a dot component: {path!r}")
    return path


def _reject_forbidden_keys(value: JsonValue, forbidden: frozenset[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in forbidden:
                message = f"model-visible payload contains prohibited key {key!r}"
                raise FixtureProjectionError(message)
            _reject_forbidden_keys(child, forbidden)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_keys(child, forbidden)


def _normalize_json(value: object) -> JsonValue:
    if value is None or type(value) is bool or type(value) is int:
        return cast(JsonValue, value)
    if type(value) is str:
        return cast(JsonValue, unicodedata.normalize("NFC", value))
    if isinstance(value, Mapping):
        snapshot = list(value.items())
        if any(type(key) is not str for key, _ in snapshot):
            raise FixtureProjectionError("fixture JSON object keys must be exact strings")
        normalized: dict[str, JsonValue] = {}
        for raw_key, child in snapshot:
            key = unicodedata.normalize("NFC", cast(str, raw_key))
            if key in normalized:
                message = "fixture JSON key normalization produced a duplicate key"
                raise FixtureProjectionError(message)
            normalized[key] = _normalize_json(child)
        return normalized
    if isinstance(value, list | tuple):
        return [_normalize_json(child) for child in value]
    raise FixtureProjectionError(f"unsupported fixture JSON value type: {type(value).__name__}")


def _canonical_json_bytes(value: JsonValue) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, UnicodeEncodeError, ValueError) as error:
        raise FixtureProjectionError("fixture JSON canonicalization failed") from error


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
