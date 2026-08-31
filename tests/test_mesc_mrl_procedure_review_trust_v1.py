"""MRL-0406 tests for repository-controlled procedure-review trust."""

from __future__ import annotations

import pytest

from medscale.mesc import _mrl_procedure_review_trust_v1 as review_trust
from medscale.mesc._mrl_procedure_review_trust_v1 import (
    ProcedureReviewTrustError,
    hold_procedure_review_trust,
    procedure_review_trust_registry_sha256,
    procedure_review_trust_snapshot,
    validate_procedure_review_trust,
)


def test_production_review_trust_registry_starts_empty() -> None:
    snapshot = procedure_review_trust_snapshot()

    assert snapshot.trusted_review_receipt_sha256 == frozenset()
    assert snapshot.registry_sha256 == procedure_review_trust_registry_sha256()
    assert snapshot.admits("0" * 64) is False


def test_synthetic_test_trust_requires_exact_receipt_and_registry_identity() -> None:
    receipt_sha256 = "a" * 64
    previous = review_trust._replace_procedure_review_trust_registry_for_tests(
        frozenset({receipt_sha256})
    )
    try:
        registry_sha256 = procedure_review_trust_registry_sha256()
        snapshot = validate_procedure_review_trust(
            expected_registry_sha256=registry_sha256,
            review_receipt_sha256=receipt_sha256,
        )
        assert snapshot.admits(receipt_sha256) is True

        with pytest.raises(
            ProcedureReviewTrustError,
            match="changed after receipt admission",
        ):
            validate_procedure_review_trust(
                expected_registry_sha256="0" * 64,
                review_receipt_sha256=receipt_sha256,
            )

        with pytest.raises(
            ProcedureReviewTrustError,
            match="not trusted",
        ):
            validate_procedure_review_trust(
                expected_registry_sha256=registry_sha256,
                review_receipt_sha256="b" * 64,
            )
    finally:
        review_trust._replace_procedure_review_trust_registry_for_tests(previous)


def test_disposable_snapshot_mutation_cannot_change_future_trust() -> None:
    receipt_sha256 = "c" * 64
    previous = review_trust._replace_procedure_review_trust_registry_for_tests(
        frozenset({receipt_sha256})
    )
    try:
        snapshot = procedure_review_trust_snapshot()
        object.__setattr__(
            snapshot,
            "trusted_review_receipt_sha256",
            frozenset({"d" * 64}),
        )

        fresh = procedure_review_trust_snapshot()
        assert fresh.admits(receipt_sha256) is True
        assert fresh.admits("d" * 64) is False
    finally:
        review_trust._replace_procedure_review_trust_registry_for_tests(previous)


def test_trust_registry_cannot_change_during_active_admission_lease() -> None:
    receipt_sha256 = "e" * 64
    previous = review_trust._replace_procedure_review_trust_registry_for_tests(
        frozenset({receipt_sha256})
    )
    try:
        registry_sha256 = procedure_review_trust_registry_sha256()
        with hold_procedure_review_trust(
            expected_registry_sha256=registry_sha256,
            review_receipt_sha256=receipt_sha256,
        ), pytest.raises(
            ProcedureReviewTrustError,
            match="cannot change during active admission",
        ):
            review_trust._replace_procedure_review_trust_registry_for_tests(frozenset())
    finally:
        review_trust._replace_procedure_review_trust_registry_for_tests(previous)


@pytest.mark.parametrize(
    "registry",
    (
        {"f" * 64},
        frozenset({"INVALID"}),
    ),
)
def test_test_trust_replacement_rejects_noncanonical_registry(
    registry: object,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        review_trust._replace_procedure_review_trust_registry_for_tests(
            registry  # type: ignore[arg-type]
        )
