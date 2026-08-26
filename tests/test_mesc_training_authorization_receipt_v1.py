"""Tests for MESC training-authorization receipts."""

from __future__ import annotations

import pytest

from medscale.mesc._training_authorization_receipt_v1 import (
    TrainingAuthorizationReceipt,
    TrainingAuthorizationReceiptError,
    build_training_authorization_receipt,
)

_A = "a" * 64
_B = "b" * 64
_C = "c" * 64
_D = "d" * 64


def _build(*, authorize: bool) -> TrainingAuthorizationReceipt:
    return build_training_authorization_receipt(
        authorizer_id="founder",
        subject_readiness_manifest_sha256=_A,
        runtime_qualification_sha256=_B,
        corpus_binding_sha256=_C,
        local_asset_attestation_sha256=_D,
        authorization_statement="Authorize TRAINING_EXECUTION for the bound readiness subject.",
        authorize=authorize,
    )


def test_authorize_false_is_blocked_and_not_real_training() -> None:
    receipt = _build(authorize=False)
    assert receipt.disposition == "BLOCKED"
    assert receipt.real_training_authorized is False
    assert "explicit authorize=true was not supplied" in receipt.blockers
    assert len(receipt.receipt_sha256) == 64


def test_authorize_true_emits_authorized() -> None:
    receipt = _build(authorize=True)
    assert receipt.disposition == "AUTHORIZED"
    assert receipt.real_training_authorized is True
    assert receipt.authorization_scope == "TRAINING_EXECUTION"
    assert receipt.blockers == ()


def test_refuses_empty_authorizer() -> None:
    with pytest.raises(TrainingAuthorizationReceiptError, match="authorizer_id"):
        build_training_authorization_receipt(
            authorizer_id=" ",
            subject_readiness_manifest_sha256=_A,
            runtime_qualification_sha256=_B,
            corpus_binding_sha256=_C,
            local_asset_attestation_sha256=_D,
            authorization_statement="Authorize TRAINING_EXECUTION.",
            authorize=True,
        )


def test_deterministic_identity() -> None:
    left = _build(authorize=True)
    right = _build(authorize=True)
    assert left.receipt_sha256 == right.receipt_sha256
    blocked = _build(authorize=False)
    assert blocked.receipt_sha256 != left.receipt_sha256
