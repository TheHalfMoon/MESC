from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from typing import Callable

import pytest

from medscale.mesc._mrl_research_hypothesis_v1 import (
    ResearchHypothesis,
    ResearchHypothesisError,
)


def _hypothesis() -> ResearchHypothesis:
    return ResearchHypothesis(
        hypothesis_id="hypothesis-001",
        objective_sha256="a" * 64,
        mechanism="A bounded retrieval-depth reduction lowers unsupported-answer rate.",
        predicted_effects=(
            "Unsupported-answer rate decreases without a safety-floor regression.",
            "Median retrieval latency decreases.",
        ),
        predicted_failure_modes=(
            "Reduced context may lower evidence fidelity on multi-document cases.",
        ),
        falsification_criteria=(
            "The unsupported-answer rate does not improve on the frozen search evaluator.",
            "Any applicable hard evidence floor regresses.",
        ),
        evidence_refs=("evidence:baseline-001", "evidence:retrieval-audit-001"),
        parent_hypothesis_ids=(),
        created_from_campaign_state_sha256="b" * 64,
    )


def test_content_identity_is_outside_semantic_preimage() -> None:
    hypothesis = _hypothesis()

    assert b"content_sha256" not in hypothesis.semantic_bytes
    assert "content_sha256" not in hypothesis.semantic_dict()
    assert hypothesis.to_dict()["content_sha256"] == hypothesis.content_sha256
    assert len(hypothesis.content_sha256) == 64


def test_equivalent_hypotheses_have_byte_stable_identity() -> None:
    first = _hypothesis()
    second = _hypothesis()

    assert first.semantic_bytes == second.semantic_bytes
    assert first.content_sha256 == second.content_sha256


def test_semantic_envelope_contains_exact_required_fields() -> None:
    payload = _hypothesis().semantic_dict()

    assert set(payload) == {
        "format",
        "hypothesis_id",
        "objective_sha256",
        "mechanism",
        "predicted_effects",
        "predicted_failure_modes",
        "falsification_criteria",
        "evidence_refs",
        "parent_hypothesis_ids",
        "created_from_campaign_state_sha256",
    }
    assert payload["format"] == "MRL-RESEARCH-HYPOTHESIS-V1"


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: replace(value, hypothesis_id="hypothesis-002"),
        lambda value: replace(value, objective_sha256="c" * 64),
        lambda value: replace(
            value,
            mechanism="A different bounded mechanism predicts a different causal effect.",
        ),
        lambda value: replace(
            value,
            predicted_effects=(
                "Median retrieval latency decreases.",
                "Unsupported-answer rate decreases without a safety-floor regression.",
            ),
        ),
        lambda value: replace(
            value,
            predicted_failure_modes=(
                "Reduced context may lower abstention quality on ambiguous cases.",
            ),
        ),
        lambda value: replace(
            value,
            falsification_criteria=(
                "Any applicable hard evidence floor regresses.",
            ),
        ),
        lambda value: replace(
            value,
            evidence_refs=("evidence:baseline-001", "evidence:new-audit-001"),
        ),
        lambda value: replace(value, parent_hypothesis_ids=("hypothesis-parent-001",)),
        lambda value: replace(value, created_from_campaign_state_sha256="d" * 64),
    ],
)
def test_every_material_semantic_change_changes_identity(
    mutate: Callable[[ResearchHypothesis], ResearchHypothesis],
) -> None:
    original = _hypothesis()
    changed = mutate(original)

    assert changed.content_sha256 != original.content_sha256


def test_hypothesis_is_frozen() -> None:
    hypothesis = _hypothesis()

    with pytest.raises(FrozenInstanceError):
        hypothesis.mechanism = "changed"  # type: ignore[misc]


@pytest.mark.parametrize(
    "hypothesis_id",
    ["", " Hypothesis-001", "Hypothesis-001", "hypothesis_001", "hypothesis--001"],
)
def test_invalid_hypothesis_identity_fails_closed(hypothesis_id: str) -> None:
    with pytest.raises(ResearchHypothesisError):
        replace(_hypothesis(), hypothesis_id=hypothesis_id)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("objective_sha256", "A" * 64),
        ("objective_sha256", "a" * 63),
        ("created_from_campaign_state_sha256", "g" * 64),
        ("created_from_campaign_state_sha256", "b" * 65),
    ],
)
def test_invalid_sha_bindings_fail_closed(field: str, value: str) -> None:
    with pytest.raises(ResearchHypothesisError, match="64 lowercase hex"):
        replace(_hypothesis(), **{field: value})


@pytest.mark.parametrize(
    "mechanism",
    ["", " leading-space", "trailing-space ", "line\nbreak", "nul\x00text", "tab\ttext"],
)
def test_mechanism_must_be_canonical_nonempty_text(mechanism: str) -> None:
    with pytest.raises(ResearchHypothesisError, match="canonical text"):
        replace(_hypothesis(), mechanism=mechanism)


@pytest.mark.parametrize(
    "field",
    ["predicted_effects", "predicted_failure_modes", "falsification_criteria"],
)
def test_required_scientific_statements_cannot_be_empty(field: str) -> None:
    with pytest.raises(ResearchHypothesisError, match="cannot be empty"):
        replace(_hypothesis(), **{field: ()})


@pytest.mark.parametrize(
    "field",
    ["predicted_effects", "predicted_failure_modes", "falsification_criteria"],
)
def test_scientific_statements_reject_duplicates(field: str) -> None:
    statement = "A material scientific statement."
    with pytest.raises(ResearchHypothesisError, match="duplicate"):
        replace(_hypothesis(), **{field: (statement, statement)})


@pytest.mark.parametrize(
    "field",
    ["predicted_effects", "predicted_failure_modes", "falsification_criteria"],
)
def test_scientific_statement_collections_require_exact_tuples(field: str) -> None:
    with pytest.raises(ResearchHypothesisError, match="exact tuple"):
        replace(_hypothesis(), **{field: ["statement"]})  # type: ignore[arg-type]


def test_statement_order_is_explicit_semantic_data() -> None:
    hypothesis = _hypothesis()
    reordered = replace(
        hypothesis,
        predicted_effects=tuple(reversed(hypothesis.predicted_effects)),
    )

    assert reordered.predicted_effects != hypothesis.predicted_effects
    assert reordered.content_sha256 != hypothesis.content_sha256


def test_evidence_refs_are_optional_but_content_addressed_when_present() -> None:
    without_evidence = replace(_hypothesis(), evidence_refs=())

    assert without_evidence.semantic_dict()["evidence_refs"] == []
    assert without_evidence.content_sha256 != _hypothesis().content_sha256


def test_evidence_refs_must_be_unique_and_canonically_sorted() -> None:
    hypothesis = _hypothesis()

    with pytest.raises(ResearchHypothesisError, match="strictly sorted"):
        replace(
            hypothesis,
            evidence_refs=tuple(reversed(hypothesis.evidence_refs)),
        )
    with pytest.raises(ResearchHypothesisError, match="strictly sorted"):
        replace(hypothesis, evidence_refs=("evidence:a", "evidence:a"))


def test_root_hypothesis_may_have_no_parent() -> None:
    assert _hypothesis().parent_hypothesis_ids == ()


def test_parent_hypothesis_ids_are_canonical_and_cannot_self_reference() -> None:
    hypothesis = _hypothesis()

    with pytest.raises(ResearchHypothesisError, match="strictly sorted"):
        replace(
            hypothesis,
            parent_hypothesis_ids=("hypothesis-z", "hypothesis-a"),
        )
    with pytest.raises(ResearchHypothesisError, match="kebab-case"):
        replace(hypothesis, parent_hypothesis_ids=("Hypothesis-parent",))
    with pytest.raises(ResearchHypothesisError, match="cannot reference itself"):
        replace(hypothesis, parent_hypothesis_ids=(hypothesis.hypothesis_id,))


def test_reference_collections_require_exact_tuples() -> None:
    with pytest.raises(ResearchHypothesisError, match="exact tuple"):
        replace(_hypothesis(), evidence_refs=[])  # type: ignore[arg-type]
    with pytest.raises(ResearchHypothesisError, match="exact tuple"):
        replace(_hypothesis(), parent_hypothesis_ids=[])  # type: ignore[arg-type]


def test_free_form_try_entry_without_expected_effects_cannot_be_canonical() -> None:
    with pytest.raises(ResearchHypothesisError, match="predicted_effects cannot be empty"):
        replace(
            _hypothesis(),
            mechanism="Try a different retrieval depth.",
            predicted_effects=(),
        )


def test_free_form_try_entry_without_falsification_cannot_be_canonical() -> None:
    with pytest.raises(ResearchHypothesisError, match="falsification_criteria cannot be empty"):
        replace(
            _hypothesis(),
            mechanism="Try a different retrieval depth.",
            falsification_criteria=(),
        )


def test_post_construction_mechanism_mutation_fails_closed_at_public_views() -> None:
    hypothesis = _hypothesis()
    object.__setattr__(hypothesis, "mechanism", "forged\nmechanism")

    with pytest.raises(ResearchHypothesisError, match="canonical text"):
        hypothesis.semantic_dict()
    with pytest.raises(ResearchHypothesisError, match="canonical text"):
        _ = hypothesis.semantic_bytes
    with pytest.raises(ResearchHypothesisError, match="canonical text"):
        _ = hypothesis.content_sha256
    with pytest.raises(ResearchHypothesisError, match="canonical text"):
        hypothesis.to_dict()


def test_post_construction_statement_mutation_fails_closed_at_public_views() -> None:
    hypothesis = _hypothesis()
    object.__setattr__(hypothesis, "falsification_criteria", ())

    with pytest.raises(ResearchHypothesisError, match="cannot be empty"):
        hypothesis.semantic_dict()
    with pytest.raises(ResearchHypothesisError, match="cannot be empty"):
        _ = hypothesis.content_sha256


def test_post_construction_reference_type_confusion_fails_closed() -> None:
    hypothesis = _hypothesis()
    object.__setattr__(hypothesis, "evidence_refs", ["evidence:forged"])

    with pytest.raises(ResearchHypothesisError, match="exact tuple"):
        hypothesis.semantic_dict()
    with pytest.raises(ResearchHypothesisError, match="exact tuple"):
        hypothesis.to_dict()


def test_post_construction_parent_self_reference_fails_closed() -> None:
    hypothesis = _hypothesis()
    object.__setattr__(hypothesis, "parent_hypothesis_ids", (hypothesis.hypothesis_id,))

    with pytest.raises(ResearchHypothesisError, match="cannot reference itself"):
        hypothesis.semantic_dict()
    with pytest.raises(ResearchHypothesisError, match="cannot reference itself"):
        _ = hypothesis.content_sha256
