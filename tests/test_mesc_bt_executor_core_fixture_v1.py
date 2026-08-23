"""Fixture-only qualification for the Backbone Tournament executor core."""

from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from medscale.mesc._bt_executor_core_fixture_v1 import (
    TOURNAMENT_CANDIDATES,
    ArtifactDigest,
    CandidateBinding,
    FixtureAttemptFailureError,
    FixtureExecutionItem,
    FixtureExecutorBlockedError,
    FixtureExecutorError,
    FixtureProjectionError,
    PostGenerationHooks,
    RetryableFailureKind,
    RetryPolicy,
    build_fixture_item,
    hash_artifacts,
    run_fixture_item,
    run_fixture_item_across_all_candidates,
    summarize_candidate_latencies,
)


class FakeAdapter:
    fixture_only = True

    def __init__(self, actions: list[object] | None = None) -> None:
        self.actions = list(actions or ["ok"])
        self.calls: list[tuple[str, bytes, int]] = []

    def invoke(self, candidate: CandidateBinding, model_payload: bytes, timeout_ms: int) -> str:
        self.calls.append((candidate.key, model_payload, timeout_ms))
        action = self.actions.pop(0) if self.actions else "ok"
        if isinstance(action, Exception):
            raise action
        return str(action)


class LiveLikeAdapter(FakeAdapter):
    fixture_only = False


class TickClock:
    def __init__(self, values: list[int]) -> None:
        self.values = list(values)

    def __call__(self) -> int:
        return self.values.pop(0)


def _item() -> FixtureExecutionItem:
    return build_fixture_item(
        item_id="BT-FIXTURE-001",
        axis="A",
        model_payload={"question": "fixture", "context": ["synthetic"]},
        gold_payload={"gold_answer": "yes"},
        forbidden_gold_keys=frozenset({"gold_answer", "score"}),
    )


def _hooks(events: list[str] | None = None) -> PostGenerationHooks:
    log = events if events is not None else []

    def parser(raw: str) -> object:
        log.append("parser")
        return {"answer": raw}

    def schema(parsed: object) -> None:
        assert parsed == {"answer": "ok"}
        log.append("schema")

    def scorer(parsed: object, gold: bytes) -> object:
        assert parsed == {"answer": "ok"}
        assert b"gold_answer" in gold
        log.append("scorer")
        return {"correct": True}

    def report(item_id: str, candidate: CandidateBinding, parsed: object, score: object) -> None:
        assert item_id == "BT-FIXTURE-001"
        assert candidate.key in {entry.key for entry in TOURNAMENT_CANDIDATES}
        assert parsed == {"answer": "ok"}
        assert score == {"correct": True}
        log.append("report")

    return PostGenerationHooks(
        parser=parser,
        schema_validator=schema,
        scorer=scorer,
        report_validator=report,
    )


def _policy(*retryable: RetryableFailureKind) -> RetryPolicy:
    return RetryPolicy(
        timeout_ms=30_000,
        retryable_failure_kinds=frozenset(retryable),
    )


def test_candidate_registry_is_exact_and_ordered() -> None:
    assert [candidate.key for candidate in TOURNAMENT_CANDIDATES] == [
        "gpt_oss_20b",
        "apertus_1_5_8b",
        "phi_4_multimodal_instruct",
        "medgemma_1_5_4b_it",
    ]
    assert [candidate.model_revision for candidate in TOURNAMENT_CANDIDATES] == [
        "6cee5e81ee83917806bbde320786a8fb61efebee",
        "a411d838600baf0e3635a3daf66fb7c55fc97bb6",
        "93f923e1a7727d1c4f446756212d9d3e8fcc5d81",
        "91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b",
    ]


def test_fixture_item_separates_model_visible_and_gold_bytes() -> None:
    model = {"question": "fixture", "nested": {"evidence": ["x"]}}
    gold = {"gold_answer": "yes"}
    item = build_fixture_item(
        item_id="BT-FIXTURE-001",
        axis="A",
        model_payload=model,
        gold_payload=gold,
        forbidden_gold_keys=frozenset({"gold_answer"}),
    )
    model["question"] = "mutated"
    gold["gold_answer"] = "no"

    assert item.model_payload == b'{"nested":{"evidence":["x"]},"question":"fixture"}'
    assert item.gold_payload == b'{"gold_answer":"yes"}'
    assert item.model_payload_sha256 == hashlib.sha256(item.model_payload).hexdigest()
    assert item.gold_payload_sha256 == hashlib.sha256(item.gold_payload).hexdigest()


def test_nested_gold_key_in_model_payload_is_blocked() -> None:
    with pytest.raises(FixtureProjectionError, match="gold_answer"):
        build_fixture_item(
            item_id="BT-FIXTURE-001",
            axis="A",
            model_payload={"nested": [{"gold_answer": "yes"}]},
            gold_payload={"gold_answer": "yes"},
            forbidden_gold_keys=frozenset({"gold_answer"}),
        )


def test_success_captures_raw_response_and_runs_hooks_in_strict_order() -> None:
    events: list[str] = []
    adapter = FakeAdapter(["ok"])
    item = _item()
    result = run_fixture_item(
        item=item,
        candidate_key="gpt_oss_20b",
        adapter=adapter,
        retry_policy=_policy("infrastructure_error"),
        hooks=_hooks(events),
        monotonic_ns=TickClock([1_000_000, 4_000_000]),
    )

    assert events == ["parser", "schema", "scorer", "report"]
    assert len(result.attempts) == 1
    assert result.terminal_disposition == "success"
    assert result.terminal_item_latency_ms == 3.0
    assert result.raw_response == "ok"
    assert result.raw_response_sha256 == hashlib.sha256(b"ok").hexdigest()
    assert result.postprocess_complete is True
    assert adapter.calls[0][1] == item.model_payload
    assert item.gold_payload not in adapter.calls[0][1]


def test_one_retry_sums_generation_attempt_latency() -> None:
    adapter = FakeAdapter([FixtureAttemptFailureError("infrastructure_error"), "ok"])
    result = run_fixture_item(
        item=_item(),
        candidate_key="gpt_oss_20b",
        adapter=adapter,
        retry_policy=_policy("infrastructure_error"),
        hooks=_hooks(),
        monotonic_ns=TickClock([0, 2_000_000, 5_000_000, 12_000_000]),
    )

    assert [attempt.disposition for attempt in result.attempts] == [
        "infrastructure_error",
        "success",
    ]
    assert result.terminal_item_latency_ms == 9.0
    assert len(adapter.calls) == 2


def test_second_retryable_failure_is_terminal_with_no_third_attempt() -> None:
    adapter = FakeAdapter(
        [
            FixtureAttemptFailureError("infrastructure_error"),
            FixtureAttemptFailureError("infrastructure_error"),
        ]
    )
    result = run_fixture_item(
        item=_item(),
        candidate_key="gpt_oss_20b",
        adapter=adapter,
        retry_policy=_policy("infrastructure_error"),
        hooks=_hooks(),
        monotonic_ns=TickClock([0, 1_000_000, 2_000_000, 5_000_000]),
    )

    assert len(result.attempts) == 2
    assert len(adapter.calls) == 2
    assert result.terminal_disposition == "infrastructure_error"
    assert result.terminal_item_latency_ms == 4.0
    assert result.postprocess_complete is False


def test_timeout_is_terminal_and_cannot_be_declared_retryable() -> None:
    with pytest.raises(FixtureExecutorError, match="only infrastructure_error"):
        _policy("timeout")

    adapter = FakeAdapter([FixtureAttemptFailureError("timeout"), "ok"])
    result = run_fixture_item(
        item=_item(),
        candidate_key="gpt_oss_20b",
        adapter=adapter,
        retry_policy=_policy("infrastructure_error"),
        hooks=_hooks(),
        monotonic_ns=TickClock([0, 1_000_000]),
    )
    assert result.terminal_disposition == "timeout"
    assert result.terminal_item_latency_ms == 1.0
    assert len(result.attempts) == 1
    assert len(adapter.calls) == 1


def test_terminal_error_never_retries() -> None:
    adapter = FakeAdapter([FixtureAttemptFailureError("terminal_error"), "ok"])
    result = run_fixture_item(
        item=_item(),
        candidate_key="gpt_oss_20b",
        adapter=adapter,
        retry_policy=_policy("infrastructure_error"),
        hooks=_hooks(),
        monotonic_ns=TickClock([0, 1_000_000]),
    )
    assert result.terminal_disposition == "terminal_error"
    assert len(adapter.calls) == 1
    assert result.postprocess_complete is False


def test_unclassified_adapter_exception_fails_closed() -> None:
    adapter = FakeAdapter([RuntimeError("unexpected")])
    with pytest.raises(FixtureExecutorBlockedError, match="unclassified"):
        run_fixture_item(
            item=_item(),
            candidate_key="gpt_oss_20b",
            adapter=adapter,
            retry_policy=_policy("infrastructure_error"),
            hooks=_hooks(),
            monotonic_ns=TickClock([0, 1_000_000]),
        )


def test_monotonic_clock_regression_is_blocked() -> None:
    with pytest.raises(FixtureExecutorBlockedError, match="backwards"):
        run_fixture_item(
            item=_item(),
            candidate_key="gpt_oss_20b",
            adapter=FakeAdapter(["ok"]),
            retry_policy=_policy("infrastructure_error"),
            hooks=_hooks(),
            monotonic_ns=TickClock([2_000_000, 1_000_000]),
        )


def test_non_fixture_adapter_is_blocked_before_invocation() -> None:
    adapter = LiveLikeAdapter(["ok"])
    with pytest.raises(FixtureExecutorBlockedError, match="fixture_only"):
        run_fixture_item(
            item=_item(),
            candidate_key="gpt_oss_20b",
            adapter=adapter,
            retry_policy=_policy("infrastructure_error"),
            hooks=_hooks(),
            monotonic_ns=TickClock([0, 1]),
        )
    assert adapter.calls == []


def test_post_generation_failure_is_blocked() -> None:
    def failing_parser(_: str) -> object:
        raise ValueError("bad output")

    hooks = replace(_hooks(), parser=failing_parser)
    with pytest.raises(FixtureExecutorBlockedError, match="hook chain"):
        run_fixture_item(
            item=_item(),
            candidate_key="gpt_oss_20b",
            adapter=FakeAdapter(["ok"]),
            retry_policy=_policy("infrastructure_error"),
            hooks=hooks,
            monotonic_ns=TickClock([0, 1_000_000]),
        )


def test_all_candidates_execute_sequentially_in_frozen_order() -> None:
    events: list[str] = []

    def parser(raw: str) -> object:
        return {"answer": raw}

    def schema(_: object) -> None:
        return None

    def scorer(_: object, __: bytes) -> object:
        return {"score": 1}

    def report(_: str, candidate: CandidateBinding, __: object, ___: object) -> None:
        events.append(candidate.key)

    adapter = FakeAdapter(["ok", "ok", "ok", "ok"])
    result = run_fixture_item_across_all_candidates(
        item=_item(),
        adapter=adapter,
        retry_policy=_policy("infrastructure_error"),
        hooks=PostGenerationHooks(parser, schema, scorer, report),
        monotonic_ns=TickClock([0, 1, 2, 3, 4, 5, 6, 7]),
    )
    expected = [candidate.key for candidate in TOURNAMENT_CANDIDATES]
    assert [call[0] for call in adapter.calls] == expected
    assert events == expected
    assert [entry.candidate_key for entry in result.candidate_results] == expected


def test_artifact_hashing_is_sorted_and_exact() -> None:
    entries = hash_artifacts({"b/out.json": b"two", "a/out.json": b"one"})
    assert entries == (
        ArtifactDigest(
            path="a/out.json",
            sha256=hashlib.sha256(b"one").hexdigest(),
            byte_length=3,
        ),
        ArtifactDigest(
            path="b/out.json",
            sha256=hashlib.sha256(b"two").hexdigest(),
            byte_length=3,
        ),
    )


@pytest.mark.parametrize("path", ["/abs", "a/../b", "a\\b", "ümlaut"])
def test_artifact_hashing_rejects_invalid_paths(path: str) -> None:
    with pytest.raises(FixtureExecutorBlockedError):
        hash_artifacts({path: b"x"})


def test_latency_summary_requires_240_unique_items_and_uses_even_median_rule() -> None:
    base = run_fixture_item(
        item=_item(),
        candidate_key="gpt_oss_20b",
        adapter=FakeAdapter(["ok"]),
        retry_policy=_policy("infrastructure_error"),
        hooks=_hooks(),
        monotonic_ns=TickClock([0, 1_000_000]),
    )
    results = tuple(
        replace(base, item_id=f"BT-FIXTURE-{index:03d}", terminal_item_latency_ms=float(index))
        for index in range(1, 241)
    )
    summary = summarize_candidate_latencies("gpt_oss_20b", results)
    assert summary.median_latency_ms == 120.5
    assert len(summary.terminal_item_latency_ms) == 240


def test_latency_summary_rejects_wrong_count_duplicate_and_nonfinite() -> None:
    base = run_fixture_item(
        item=_item(),
        candidate_key="gpt_oss_20b",
        adapter=FakeAdapter(["ok"]),
        retry_policy=_policy("infrastructure_error"),
        hooks=_hooks(),
        monotonic_ns=TickClock([0, 1_000_000]),
    )
    with pytest.raises(FixtureExecutorBlockedError, match="240"):
        summarize_candidate_latencies("gpt_oss_20b", (base,))

    duplicates = tuple(replace(base, item_id="same") for _ in range(240))
    with pytest.raises(FixtureExecutorBlockedError, match="duplicate"):
        summarize_candidate_latencies("gpt_oss_20b", duplicates)

    nonfinite = tuple(
        replace(base, item_id=f"id-{index}", terminal_item_latency_ms=float(index))
        for index in range(240)
    )
    nonfinite = (replace(nonfinite[0], terminal_item_latency_ms=float("inf")), *nonfinite[1:])
    with pytest.raises(FixtureExecutorBlockedError, match="finite"):
        summarize_candidate_latencies("gpt_oss_20b", nonfinite)
