"""Tests for the canonical MESC supervised-training example contract."""

from __future__ import annotations

from typing import Any

import pytest

from medscale.mesc._training_example_contract_v1 import (
    TrainingCorpusV1,
    TrainingExampleContractError,
    TrainingExampleV1,
    TrainingMessage,
    build_training_corpus,
)

_SHA_A = "a" * 64
_SHA_B = "b" * 64


class _FakeMessage(TrainingMessage):
    def to_dict(self) -> dict[str, str]:
        return {"role": "assistant", "content": "forged"}


class _FakeExample(TrainingExampleV1):
    pass


def _example(
    example_type: type[TrainingExampleV1] = TrainingExampleV1,
    **overrides: object,
) -> TrainingExampleV1:
    values: dict[str, Any] = {
        "example_id": "example-1",
        "training_record_id": "record-1",
        "source_id": "source-1",
        "source_revision": "rev-1",
        "source_license": "Apache-2.0",
        "source_sha256": _SHA_A,
        "source_timestamp": "2026-08-01T00:00:00+00:00",
        "origin": "synthetic",
        "synthetic_provenance_sha256": _SHA_B,
        "evidence_refs": ("evidence-1",),
        "task_type": "evidence-grounded-answer",
        "specialty": "internal-medicine",
        "patient_population": "adult",
        "language": "en",
        "training_stage": "evidence_sft",
        "prompt": (
            TrainingMessage(role="system", content="Use only the supplied evidence."),
            TrainingMessage(role="user", content="What does the evidence support?"),
        ),
        "completion": TrainingMessage(role="assistant", content="The evidence supports X."),
        "uncertainty_class": "SUPPORTED",
        "abstention_target": "ANSWER_SUPPORTED",
        "contradiction_state": "NONE",
        "verification_state": "VERIFIED",
        "clinician_review_state": "REVIEWED_PASS",
        "contamination_state": "CLEAR",
    }
    values.update(overrides)
    return example_type(**values)


def test_valid_example_is_eligible_and_content_addressed() -> None:
    example = _example()
    assert example.eligible_for_sft is True
    assert len(example.example_sha256) == 64
    assert example.example_sha256 == _example().example_sha256


def test_training_record_identity_participates_in_example_identity() -> None:
    assert _example().example_sha256 != _example(training_record_id="record-2").example_sha256


def test_training_record_id_matches_upstream_freeze_identifier_domain() -> None:
    unicode_id = f"{chr(0x03B1)}-1"
    assert _example(training_record_id=unicode_id).training_record_id == unicode_id
    assert _example(training_record_id="Record 1").training_record_id == "Record 1"
    with pytest.raises(
        TrainingExampleContractError,
        match="training_record_id must be a non-empty",
    ):
        _example(training_record_id="")


def test_trl_projection_is_conversational_prompt_completion_only() -> None:
    example = _example()
    assert example.to_trl_prompt_completion() == {
        "prompt": [
            {"role": "system", "content": "Use only the supplied evidence."},
            {"role": "user", "content": "What does the evidence support?"},
        ],
        "completion": [{"role": "assistant", "content": "The evidence supports X."}],
    }


def test_synthetic_example_requires_provenance_hash() -> None:
    with pytest.raises(TrainingExampleContractError, match="synthetic examples require"):
        _example(synthetic_provenance_sha256=None)


def test_hand_authored_fixture_rejects_synthetic_provenance_claim() -> None:
    with pytest.raises(TrainingExampleContractError, match="must not claim synthetic provenance"):
        _example(origin="hand_authored_fixture")


def test_hand_authored_fixture_without_synthetic_provenance_is_valid() -> None:
    example = _example(origin="hand_authored_fixture", synthetic_provenance_sha256=None)
    assert example.eligible_for_sft is True


def test_non_r2_origin_is_rejected() -> None:
    with pytest.raises(TrainingExampleContractError, match="unsupported origin"):
        _example(origin="external_clinical")


def test_prompt_must_end_with_user_message() -> None:
    with pytest.raises(TrainingExampleContractError, match="prompt must end with a user"):
        _example(prompt=(TrainingMessage(role="assistant", content="history"),))


def test_system_message_is_leading_and_unique() -> None:
    with pytest.raises(TrainingExampleContractError, match="leading system"):
        _example(
            prompt=(
                TrainingMessage(role="user", content="Question"),
                TrainingMessage(role="system", content="Late system"),
                TrainingMessage(role="user", content="Question again"),
            )
        )


def test_completion_must_be_assistant() -> None:
    with pytest.raises(TrainingExampleContractError, match="completion role"):
        _example(completion=TrainingMessage(role="user", content="wrong role"))


def test_message_subclasses_are_rejected_at_canonical_boundaries() -> None:
    fake_user = _FakeMessage(role="user", content="Question")
    with pytest.raises(TrainingExampleContractError, match="exact TrainingMessage"):
        _example(prompt=(fake_user,))

    fake_completion = _FakeMessage(role="assistant", content="Answer")
    with pytest.raises(TrainingExampleContractError, match="exact TrainingMessage"):
        _example(completion=fake_completion)


def test_evidence_refs_are_required_unique_and_immutable() -> None:
    with pytest.raises(TrainingExampleContractError, match="evidence_refs must be non-empty"):
        _example(evidence_refs=())
    with pytest.raises(TrainingExampleContractError, match="must not contain duplicates"):
        _example(evidence_refs=("evidence-1", "evidence-1"))

    mutable_refs: Any = ["evidence-1"]
    with pytest.raises(TrainingExampleContractError, match="immutable tuple"):
        _example(evidence_refs=mutable_refs)


def test_source_sha_and_language_are_strict() -> None:
    with pytest.raises(TrainingExampleContractError, match="source_sha256"):
        _example(source_sha256="ABC")
    with pytest.raises(TrainingExampleContractError, match="language"):
        _example(language="english")


def test_non_string_timestamp_fails_with_contract_error() -> None:
    with pytest.raises(TrainingExampleContractError, match="source_timestamp"):
        _example(source_timestamp=123)


def test_unhashable_literal_like_values_fail_with_contract_error() -> None:
    with pytest.raises(TrainingExampleContractError, match="unsupported origin"):
        _example(origin=[])
    with pytest.raises(TrainingExampleContractError, match="unsupported training_stage"):
        _example(training_stage=[])


def test_supported_answer_requires_supported_noncontradictory_state() -> None:
    with pytest.raises(TrainingExampleContractError, match="ANSWER_SUPPORTED"):
        _example(uncertainty_class="PARTIAL")
    with pytest.raises(TrainingExampleContractError, match="ANSWER_SUPPORTED"):
        _example(contradiction_state="PRESENT")


def test_abstention_targets_enforce_semantic_state() -> None:
    conflicted = _example(
        uncertainty_class="CONFLICTED",
        abstention_target="ABSTAIN_CONFLICTED_EVIDENCE",
        contradiction_state="PRESENT",
    )
    assert conflicted.eligible_for_sft is True
    with pytest.raises(TrainingExampleContractError, match="ABSTAIN_CONFLICTED_EVIDENCE"):
        _example(abstention_target="ABSTAIN_CONFLICTED_EVIDENCE")

    safety = _example(
        training_stage="safety_sft",
        uncertainty_class="SAFETY_CRITICAL",
        abstention_target="ESCALATE_SAFETY",
    )
    assert safety.abstention_target == "ESCALATE_SAFETY"


def test_unreviewed_unverified_or_contaminated_examples_are_not_eligible() -> None:
    assert _example(verification_state="PENDING").eligible_for_sft is False
    assert _example(clinician_review_state="PENDING").eligible_for_sft is False
    assert _example(contamination_state="BLOCKED").eligible_for_sft is False


def test_corpus_rejects_ineligible_examples() -> None:
    ineligible = (
        _example(verification_state="PENDING"),
        _example(clinician_review_state="PENDING"),
        _example(contamination_state="BLOCKED"),
    )
    for example in ineligible:
        with pytest.raises(TrainingExampleContractError, match="every corpus example"):
            TrainingCorpusV1(examples=(example,))


def test_corpus_direct_construction_rejects_mutable_or_wrong_member_container() -> None:
    mutable_examples: Any = [_example()]
    with pytest.raises(TrainingExampleContractError, match="examples must be a tuple"):
        TrainingCorpusV1(examples=mutable_examples)

    wrong_member: Any = ("not-an-example",)
    with pytest.raises(
        TrainingExampleContractError,
        match="members must be exact TrainingExampleV1",
    ):
        TrainingCorpusV1(examples=wrong_member)


def test_example_subclasses_are_rejected_by_corpus_and_builder() -> None:
    forged = _example(_FakeExample)
    with pytest.raises(
        TrainingExampleContractError,
        match="members must be exact TrainingExampleV1",
    ):
        TrainingCorpusV1(examples=(forged,))
    with pytest.raises(TrainingExampleContractError, match="only exact TrainingExampleV1"):
        build_training_corpus([forged])


def test_build_corpus_sorts_examples_and_rejects_duplicates() -> None:
    second = _example(example_id="example-2", source_sha256="c" * 64)
    corpus = build_training_corpus((second, _example()))
    assert [example.example_id for example in corpus.examples] == ["example-1", "example-2"]

    with pytest.raises(TrainingExampleContractError, match="duplicate example_id"):
        build_training_corpus((_example(), _example()))


def test_build_corpus_freezes_lists_and_rejects_forged_runtime_inputs() -> None:
    valid_list = [_example()]
    corpus = build_training_corpus(valid_list)
    assert isinstance(corpus.examples, tuple)

    wrong_member: Any = ["not-an-example"]
    with pytest.raises(TrainingExampleContractError, match="only exact TrainingExampleV1"):
        build_training_corpus(wrong_member)

    wrong_container: Any = "example-1"
    with pytest.raises(TrainingExampleContractError, match="sequence of TrainingExampleV1"):
        build_training_corpus(wrong_container)


def test_corpus_exposes_unique_sorted_t5_training_record_ids() -> None:
    first_id = f"{chr(0x03B2)}-2"
    second_id = f"{chr(0x03B1)}-1"
    first = _example(example_id="example-1", training_record_id=first_id)
    second = _example(
        example_id="example-2",
        training_record_id=second_id,
        source_sha256="c" * 64,
    )
    third = _example(
        example_id="example-3",
        training_record_id=first_id,
        source_sha256="d" * 64,
    )
    corpus = build_training_corpus((third, first, second))
    assert corpus.training_record_ids == tuple(sorted((first_id, second_id)))


def test_corpus_hash_and_jsonl_are_order_independent_at_builder_boundary() -> None:
    first = _example()
    second = _example(example_id="example-2", source_sha256="c" * 64)
    left = build_training_corpus((first, second))
    right = build_training_corpus((second, first))
    assert left.corpus_sha256 == right.corpus_sha256
    assert left.canonical_jsonl() == right.canonical_jsonl()
    assert left.canonical_jsonl().endswith("\n")


def test_corpus_identity_changes_when_auditable_content_changes() -> None:
    original = build_training_corpus((_example(),))
    changed = build_training_corpus((_example(source_license="MIT"),))
    assert original.corpus_sha256 != changed.corpus_sha256


def test_corpus_trl_projection_preserves_sorted_example_order() -> None:
    second = _example(example_id="example-2", source_sha256="c" * 64)
    corpus = build_training_corpus((second, _example()))
    records = corpus.to_trl_records()
    assert records[0] == _example().to_trl_prompt_completion()
    assert records[1] == second.to_trl_prompt_completion()
