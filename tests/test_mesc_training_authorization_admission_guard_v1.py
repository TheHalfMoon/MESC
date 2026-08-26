"""Regression tests for final training-authorization backend admission."""

from __future__ import annotations

from typing import Any

import pytest

import medscale.mesc._training_authorization_trust_v1 as authorization_trust
import medscale.mesc._training_executor_v1 as executor_module
import test_mesc_training_executor_v1 as executor_test_support
from _training_authorization_test_support import (
    restore_training_authorization_test_trust,
)
from medscale.mesc._training_authorization_receipt_v1 import (
    TrainingAuthorizationReceiptError,
)
from medscale.mesc._training_executor_v1 import (
    TrainingExecutionError,
    TrainingExecutionManifest,
    execute_training,
)
from medscale.mesc._training_readiness_v1 import assess_training_readiness


def test_revocation_after_launch_recompute_blocks_backend_invocation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, readiness, launch, binding, assets, environment = executor_test_support._bundle()
    backend = executor_test_support._SuccessBackend()
    original = executor_module._build_execution_manifest

    def _revoke_after_manifest(**kwargs: Any) -> TrainingExecutionManifest:
        execution_manifest = original(**kwargs)
        restore_training_authorization_test_trust()
        return execution_manifest

    monkeypatch.setattr(
        executor_module,
        "_build_execution_manifest",
        _revoke_after_manifest,
    )

    with pytest.raises(
        TrainingExecutionError,
        match="authorization trust changed before backend invocation",
    ):
        execute_training(
            manifest=manifest,
            readiness=readiness,
            launch_plan=launch,
            corpus_binding=binding,
            local_assets=assets,
            environment=environment,
            role="compact",
            backend=backend,
        )

    assert backend.calls == 0


def test_malformed_registry_is_domain_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, _, _, _, _, _ = executor_test_support._bundle()
    receipt = manifest.training_authorization_receipt
    assert receipt is not None

    monkeypatch.setattr(
        authorization_trust,
        "TRUSTED_TRAINING_AUTHORIZATION_ARTIFACT_SHA256",
        frozenset({"malformed"}),
    )

    with pytest.raises(
        TrainingAuthorizationReceiptError,
        match="not admitted by the canonical authorization trust registry",
    ):
        receipt.validate_current_trust()

    report = assess_training_readiness(manifest)
    assert report.can_launch_training is False
    assert (
        "training authorization receipt is not trusted by the current canonical registry"
        in report.blockers
    )
