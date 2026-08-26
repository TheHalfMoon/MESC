"""Tests for fail-closed MESC training-authorization receipts."""

from __future__ import annotations

import hashlib
from typing import cast
from unittest.mock import patch

import pytest

from medscale.mesc import _training_authorization_trust_v1 as authorization_trust
from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.mesc._training_authorization_receipt_v1 import (
    TrainingAuthorizationReceipt,
    TrainingAuthorizationReceiptError,
    build_training_authorization_receipt,
)

_SUBJECT = "a" * 64
_RUNTIME = "b" * 64
_CORPUS = "c" * 64
_STATEMENT = "Fixture authorization for the exact TRAINING_EXECUTION subject."


def _artifact(*, authorize: bool) -> bytes:
    return canonical_json_bytes(
        {
            "authorization_scope": "TRAINING_EXECUTION",
            "authorization_statement": _STATEMENT,
            "authorization_subject_sha256": _SUBJECT,
            "authorize": authorize,
            "authorizer_id": "fixture-founder",
            "corpus_binding_sha256": _CORPUS,
            "kind": "mesc.training_authorization.v1",
            "runtime_qualification_sha256": _RUNTIME,
        }
    )


def _build(
    *,
    authorize: bool,
    with_artifact: bool | None = None,
    trust_artifact: bool = True,
) -> TrainingAuthorizationReceipt:
    include_artifact = authorize if with_artifact is None else with_artifact
    artifact = _artifact(authorize=authorize) if include_artifact else None
    if authorize and artifact is not None and trust_artifact:
        trusted = frozenset({hashlib.sha256(artifact).hexdigest()})
        with patch.object(
            authorization_trust,
            "TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256",
            trusted,
        ):
            return build_training_authorization_receipt(
                authorizer_id="fixture-founder",
                authorization_subject_sha256=_SUBJECT,
                runtime_qualification_sha256=_RUNTIME,
                corpus_binding_sha256=_CORPUS,
                authorization_statement=_STATEMENT,
                authorize=authorize,
                authorization_artifact=artifact,
            )
    return build_training_authorization_receipt(
        authorizer_id="fixture-founder",
        authorization_subject_sha256=_SUBJECT,
        runtime_qualification_sha256=_RUNTIME,
        corpus_binding_sha256=_CORPUS,
        authorization_statement=_STATEMENT,
        authorize=authorize,
        authorization_artifact=artifact,
    )


def test_authorize_false_is_blocked_and_not_real_training() -> None:
    receipt = _build(authorize=False)
    assert receipt.disposition == "BLOCKED"
    assert receipt.real_training_authorized is False
    assert "explicit authorize=true was not supplied" in receipt.blockers
    assert receipt.authorization_artifact_sha256 is None
    assert len(receipt.receipt_sha256) == 64


def test_authorize_true_without_artifact_is_rejected() -> None:
    with pytest.raises(
        TrainingAuthorizationReceiptError,
        match="requires validated authorization_artifact bytes",
    ):
        _build(authorize=True, with_artifact=False)


def test_caller_created_canonical_artifact_is_rejected_without_trust_registry() -> None:
    with pytest.raises(TrainingAuthorizationReceiptError, match="trusted authorization registry"):
        _build(authorize=True, trust_artifact=False)


def test_explicit_artifact_authorization_binds_pre_authorization_subject() -> None:
    receipt = _build(authorize=True)
    assert receipt.disposition == "AUTHORIZED"
    assert receipt.real_training_authorized is True
    assert receipt.authorization_subject_sha256 == _SUBJECT
    assert receipt.runtime_qualification_sha256 == _RUNTIME
    assert receipt.corpus_binding_sha256 == _CORPUS
    assert receipt.authorization_artifact_sha256 is not None
    assert len(receipt.authorization_artifact_sha256) == 64
    assert receipt.authorization_trust_registry_sha256 is not None
    assert len(receipt.authorization_trust_registry_sha256) == 64
    assert receipt.blockers == ()


def test_artifact_semantics_must_match_supplied_bindings() -> None:
    artifact = canonical_json_bytes(
        {
            "authorization_scope": "TRAINING_EXECUTION",
            "authorization_statement": _STATEMENT,
            "authorization_subject_sha256": "d" * 64,
            "authorize": True,
            "authorizer_id": "fixture-founder",
            "corpus_binding_sha256": _CORPUS,
            "kind": "mesc.training_authorization.v1",
            "runtime_qualification_sha256": _RUNTIME,
        }
    )
    with pytest.raises(TrainingAuthorizationReceiptError, match="authorization_subject_sha256"):
        build_training_authorization_receipt(
            authorizer_id="fixture-founder",
            authorization_subject_sha256=_SUBJECT,
            runtime_qualification_sha256=_RUNTIME,
            corpus_binding_sha256=_CORPUS,
            authorization_statement=_STATEMENT,
            authorize=True,
            authorization_artifact=artifact,
        )


def test_noncanonical_artifact_bytes_are_rejected() -> None:
    noncanonical = _artifact(authorize=True).rstrip(b"\n")
    with pytest.raises(TrainingAuthorizationReceiptError, match="not canonical JSON"):
        build_training_authorization_receipt(
            authorizer_id="fixture-founder",
            authorization_subject_sha256=_SUBJECT,
            runtime_qualification_sha256=_RUNTIME,
            corpus_binding_sha256=_CORPUS,
            authorization_statement=_STATEMENT,
            authorize=True,
            authorization_artifact=noncanonical,
        )


def test_duplicate_or_nonstandard_json_is_rejected() -> None:
    duplicate = (
        b'{"authorization_scope":"TRAINING_EXECUTION","authorization_scope":"TRAINING_EXECUTION"}\n'
    )
    with pytest.raises(TrainingAuthorizationReceiptError, match="duplicate key"):
        build_training_authorization_receipt(
            authorizer_id="fixture-founder",
            authorization_subject_sha256=_SUBJECT,
            runtime_qualification_sha256=_RUNTIME,
            corpus_binding_sha256=_CORPUS,
            authorization_statement=_STATEMENT,
            authorize=True,
            authorization_artifact=duplicate,
        )

    nonstandard = _artifact(authorize=True).replace(b'"authorize":true', b'"authorize":NaN')
    with pytest.raises(TrainingAuthorizationReceiptError, match="non-standard JSON constant"):
        build_training_authorization_receipt(
            authorizer_id="fixture-founder",
            authorization_subject_sha256=_SUBJECT,
            runtime_qualification_sha256=_RUNTIME,
            corpus_binding_sha256=_CORPUS,
            authorization_statement=_STATEMENT,
            authorize=True,
            authorization_artifact=nonstandard,
        )


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


def test_authorized_receipt_cannot_be_constructed_without_artifact() -> None:
    with pytest.raises(TrainingAuthorizationReceiptError, match="validated authorization artifact"):
        TrainingAuthorizationReceipt(
            disposition="AUTHORIZED",
            authorization_scope="TRAINING_EXECUTION",
            authorizer_id="fixture-founder",
            authorization_subject_sha256=_SUBJECT,
            runtime_qualification_sha256=_RUNTIME,
            corpus_binding_sha256=_CORPUS,
            authorization_statement=_STATEMENT,
            real_training_authorized=True,
            blockers=(),
        )


def test_deterministic_identity() -> None:
    left = _build(authorize=True)
    right = _build(authorize=True)
    assert left.receipt_sha256 == right.receipt_sha256
    assert _build(authorize=False).receipt_sha256 != left.receipt_sha256


def test_authorized_receipt_rejects_current_trust_after_registry_revocation() -> None:
    receipt = _build(authorize=True)

    with pytest.raises(
        TrainingAuthorizationReceiptError,
        match=(
            r"current authorization trust is not admitted by the canonical "
            r"authorization trust registry"
        ),
    ):
        receipt.validate_current_trust()
