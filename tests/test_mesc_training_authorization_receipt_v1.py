"""Tests for fail-closed MESC training-authorization receipts."""

from __future__ import annotations

from typing import cast

import pytest

from medscale.mesc._training_authorization_receipt_v1 import (
    TrainingAuthorizationReceipt,
    TrainingAuthorizationReceiptError,
    build_training_authorization_receipt,
)

_SUBJECT = "a" * 64
_RUNTIME = "b" * 64
_CORPUS = "c" * 64


def _build(*, authorize: bool) -> TrainingAuthorizationReceipt:
    return build_training_authorization_receipt(
        authorizer_id="fixture-founder",
        authorization_subject_sha256=_SUBJECT,
        runtime_qualification_sha256=_RUNTIME,
        corpus_binding_sha256=_CORPUS,
        authorization_statement="Fixture authorization for the exact TRAINING_EXECUTION subject.",
        authorize=authorize,
    )


def test_authorize_false_is_blocked_and_not_real_training() -> None:
    receipt = _build(authorize=False)
    assert receipt.disposition == "BLOCKED"
    assert receipt.real_training_authorized is False
    assert "explicit authorize=true was not supplied" in receipt.blockers
    assert len(receipt.receipt_sha256) == 64


def test_explicit_fixture_authorization_binds_pre_authorization_subject() -> None:
    receipt = _build(authorize=True)
    assert receipt.disposition == "AUTHORIZED"
    assert receipt.real_training_authorized is True
    assert receipt.authorization_subject_sha256 == _SUBJECT
    assert receipt.runtime_qualification_sha256 == _RUNTIME
    assert receipt.corpus_binding_sha256 == _CORPUS
    assert receipt.blockers == ()


def test_post_launch_local_asset_hash_is_not_an_authorization_input() -> None:
    with pytest.raises(TypeError, match="unexpected keyword"):
        build_training_authorization_receipt(  # type: ignore[call-arg]
            authorizer_id="fixture-founder",
            authorization_subject_sha256=_SUBJECT,
            runtime_qualification_sha256=_RUNTIME,
            corpus_binding_sha256=_CORPUS,
            local_asset_attestation_sha256="d" * 64,
            authorization_statement="Fixture authorization.",
            authorize=False,
        )


def test_refuses_empty_authorizer() -> None:
    with pytest.raises(TrainingAuthorizationReceiptError, match="authorizer_id"):
        build_training_authorization_receipt(
            authorizer_id=" ",
            authorization_subject_sha256=_SUBJECT,
            runtime_qualification_sha256=_RUNTIME,
            corpus_binding_sha256=_CORPUS,
            authorization_statement="Fixture authorization.",
            authorize=False,
        )


def test_receipt_blockers_are_immutable() -> None:
    with pytest.raises(TrainingAuthorizationReceiptError, match="blockers must be an exact tuple"):
        TrainingAuthorizationReceipt(
            disposition="BLOCKED",
            authorization_scope="TRAINING_EXECUTION",
            authorizer_id="fixture-founder",
            authorization_subject_sha256=_SUBJECT,
            runtime_qualification_sha256=_RUNTIME,
            corpus_binding_sha256=_CORPUS,
            authorization_statement="Fixture authorization.",
            real_training_authorized=False,
            blockers=cast(tuple[str, ...], ["mutable"]),
        )


def test_deterministic_identity() -> None:
    left = _build(authorize=True)
    right = _build(authorize=True)
    assert left.receipt_sha256 == right.receipt_sha256
    assert _build(authorize=False).receipt_sha256 != left.receipt_sha256
