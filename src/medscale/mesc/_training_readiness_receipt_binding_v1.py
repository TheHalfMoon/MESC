"""Fail-closed binding of receipt objects into training readiness manifests.

Consumes already-produced runtime-qualification and training-authorization receipts and
writes only their content-addressed digests into a scientific readiness manifest. Opaque
forged digests are not accepted as PASS/AUTHORIZED proof.
"""

from __future__ import annotations

from dataclasses import replace

from medscale.mesc._training_authorization_receipt_v1 import TrainingAuthorizationReceipt
from medscale.mesc._training_readiness_v1 import (
    TrainingReadinessManifest,
    TrainingReadinessReport,
    assess_training_readiness,
)
from medscale.mesc._training_runtime_qualification_v1 import (
    TrainingRuntimeQualificationReceipt,
)


class TrainingReadinessReceiptBindingError(ValueError):
    """Raised when a receipt cannot be bound into readiness fail-closed."""


def bind_runtime_qualification_to_readiness(
    manifest: TrainingReadinessManifest,
    receipt: TrainingRuntimeQualificationReceipt,
) -> TrainingReadinessManifest:
    """Bind one PASS platform-qualified runtime receipt into a readiness manifest."""
    if not isinstance(manifest, TrainingReadinessManifest):
        raise TrainingReadinessReceiptBindingError("manifest must be a TrainingReadinessManifest")
    if not isinstance(receipt, TrainingRuntimeQualificationReceipt):
        raise TrainingReadinessReceiptBindingError(
            "receipt must be a TrainingRuntimeQualificationReceipt"
        )

    scientific = assess_training_readiness(
        replace(
            manifest,
            runtime_qualification_sha256=None,
            training_authorization_receipt_sha256=None,
        )
    )
    if scientific.disposition == "BLOCKED":
        raise TrainingReadinessReceiptBindingError(
            "scientific readiness is BLOCKED; cannot bind runtime qualification"
        )
    if receipt.disposition != "PASS" or not receipt.platform_qualified:
        raise TrainingReadinessReceiptBindingError(
            "runtime receipt must be PASS with platform_qualified=true"
        )

    digest = receipt.receipt_sha256
    existing = manifest.runtime_qualification_sha256
    if existing is not None and existing != digest:
        raise TrainingReadinessReceiptBindingError(
            "manifest already binds a different runtime_qualification_sha256"
        )

    return replace(
        manifest,
        runtime_qualification_sha256=digest,
    )


def bind_training_authorization_to_readiness(
    manifest: TrainingReadinessManifest,
    receipt: TrainingAuthorizationReceipt,
) -> TrainingReadinessManifest:
    """Bind one AUTHORIZED training-authorization receipt into a readiness manifest."""
    if not isinstance(manifest, TrainingReadinessManifest):
        raise TrainingReadinessReceiptBindingError("manifest must be a TrainingReadinessManifest")
    if not isinstance(receipt, TrainingAuthorizationReceipt):
        raise TrainingReadinessReceiptBindingError("receipt must be a TrainingAuthorizationReceipt")
    if manifest.runtime_qualification_sha256 is None:
        raise TrainingReadinessReceiptBindingError(
            "runtime_qualification_sha256 must already be bound"
        )
    if receipt.disposition != "AUTHORIZED" or not receipt.real_training_authorized:
        raise TrainingReadinessReceiptBindingError(
            "authorization receipt must be AUTHORIZED with real_training_authorized=true"
        )
    if receipt.subject_readiness_manifest_sha256 != manifest.manifest_sha256:
        raise TrainingReadinessReceiptBindingError(
            "authorization subject_readiness_manifest_sha256 must match the current "
            "pre-authorization readiness manifest"
        )
    if receipt.runtime_qualification_sha256 != manifest.runtime_qualification_sha256:
        raise TrainingReadinessReceiptBindingError(
            "authorization runtime_qualification_sha256 must match the bound runtime receipt"
        )

    digest = receipt.receipt_sha256
    existing = manifest.training_authorization_receipt_sha256
    if existing is not None and existing != digest:
        raise TrainingReadinessReceiptBindingError(
            "manifest already binds a different training_authorization_receipt_sha256"
        )

    return replace(
        manifest,
        training_authorization_receipt_sha256=digest,
    )


def construct_ready_to_launch_readiness(
    scientific_manifest: TrainingReadinessManifest,
    *,
    runtime_qualification: TrainingRuntimeQualificationReceipt,
    training_authorization: TrainingAuthorizationReceipt,
) -> tuple[TrainingReadinessManifest, TrainingReadinessReport]:
    """Bind runtime then authorization and require READY_TO_LAUNCH.

    ``training_authorization.subject_readiness_manifest_sha256`` must equal the
    intermediate manifest identity after runtime binding (pre-authorization subject).
    """
    if scientific_manifest.runtime_qualification_sha256 is not None:
        raise TrainingReadinessReceiptBindingError(
            "scientific_manifest must not already bind runtime_qualification_sha256"
        )
    if scientific_manifest.training_authorization_receipt_sha256 is not None:
        raise TrainingReadinessReceiptBindingError(
            "scientific_manifest must not already bind training_authorization_receipt_sha256"
        )

    with_runtime = bind_runtime_qualification_to_readiness(
        scientific_manifest,
        runtime_qualification,
    )
    with_auth = bind_training_authorization_to_readiness(
        with_runtime,
        training_authorization,
    )
    report = assess_training_readiness(with_auth)
    if report.disposition != "READY_TO_LAUNCH":
        raise TrainingReadinessReceiptBindingError("bound readiness must assess as READY_TO_LAUNCH")
    return with_auth, report


__all__ = [
    "TrainingReadinessReceiptBindingError",
    "bind_runtime_qualification_to_readiness",
    "bind_training_authorization_to_readiness",
    "construct_ready_to_launch_readiness",
]
