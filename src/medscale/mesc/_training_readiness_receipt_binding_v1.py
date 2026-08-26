"""Fail-closed binding of receipt objects into training readiness manifests.

Consumes already-produced runtime-qualification and training-authorization receipts and
writes both typed objects and their digests into a scientific readiness manifest. Opaque
forged digests alone are not accepted as PASS/AUTHORIZED proof.
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
    if type(manifest) is not TrainingReadinessManifest:
        raise TrainingReadinessReceiptBindingError(
            "manifest must be exactly TrainingReadinessManifest"
        )
    if type(receipt) is not TrainingRuntimeQualificationReceipt:
        raise TrainingReadinessReceiptBindingError(
            "receipt must be exactly TrainingRuntimeQualificationReceipt"
        )
    if (
        manifest.training_authorization_receipt_sha256 is not None
        or manifest.training_authorization_receipt is not None
    ):
        raise TrainingReadinessReceiptBindingError(
            "manifest must not already bind training authorization; "
            "bind runtime before authorization"
        )

    scientific = assess_training_readiness(
        replace(
            manifest,
            runtime_qualification_sha256=None,
            runtime_qualification_receipt=None,
            training_authorization_receipt_sha256=None,
            training_authorization_receipt=None,
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
    existing_receipt = manifest.runtime_qualification_receipt
    if existing_receipt is not None and existing_receipt.receipt_sha256 != digest:
        raise TrainingReadinessReceiptBindingError(
            "manifest already binds a different runtime_qualification_receipt"
        )

    return replace(
        manifest,
        runtime_qualification_sha256=digest,
        runtime_qualification_receipt=receipt,
    )


def bind_training_authorization_to_readiness(
    manifest: TrainingReadinessManifest,
    receipt: TrainingAuthorizationReceipt,
    *,
    runtime_qualification: TrainingRuntimeQualificationReceipt,
) -> TrainingReadinessManifest:
    """Bind one AUTHORIZED training-authorization receipt into a readiness manifest.

    Requires the exact runtime receipt object that produced the bound runtime digest.
    Authorization subject identity is ``manifest.authorization_subject_sha256``.
    """
    if type(manifest) is not TrainingReadinessManifest:
        raise TrainingReadinessReceiptBindingError(
            "manifest must be exactly TrainingReadinessManifest"
        )
    if type(receipt) is not TrainingAuthorizationReceipt:
        raise TrainingReadinessReceiptBindingError(
            "receipt must be exactly TrainingAuthorizationReceipt"
        )
    if type(runtime_qualification) is not TrainingRuntimeQualificationReceipt:
        raise TrainingReadinessReceiptBindingError(
            "runtime_qualification must be exactly TrainingRuntimeQualificationReceipt"
        )
    if manifest.runtime_qualification_sha256 is None or (
        manifest.runtime_qualification_receipt is None
    ):
        raise TrainingReadinessReceiptBindingError(
            "runtime qualification digest and typed receipt must already be bound"
        )
    if manifest.corpus_binding_sha256 is None:
        raise TrainingReadinessReceiptBindingError("corpus_binding_sha256 must already be bound")
    if runtime_qualification.disposition != "PASS" or not runtime_qualification.platform_qualified:
        raise TrainingReadinessReceiptBindingError(
            "runtime receipt must be PASS with platform_qualified=true"
        )
    if runtime_qualification.receipt_sha256 != manifest.runtime_qualification_sha256:
        raise TrainingReadinessReceiptBindingError(
            "runtime_qualification receipt digest must match bound runtime_qualification_sha256"
        )
    if receipt.disposition != "AUTHORIZED" or not receipt.real_training_authorized:
        raise TrainingReadinessReceiptBindingError(
            "authorization receipt must be AUTHORIZED with real_training_authorized=true"
        )
    if receipt.authorization_subject_sha256 != manifest.authorization_subject_sha256:
        raise TrainingReadinessReceiptBindingError(
            "authorization_subject_sha256 must match the current readiness authorization subject"
        )
    if receipt.runtime_qualification_sha256 != manifest.runtime_qualification_sha256:
        raise TrainingReadinessReceiptBindingError(
            "authorization runtime_qualification_sha256 must match the bound runtime receipt"
        )
    if receipt.corpus_binding_sha256 != manifest.corpus_binding_sha256:
        raise TrainingReadinessReceiptBindingError(
            "authorization corpus_binding_sha256 must match the bound corpus identity"
        )

    digest = receipt.receipt_sha256
    existing = manifest.training_authorization_receipt_sha256
    if existing is not None and existing != digest:
        raise TrainingReadinessReceiptBindingError(
            "manifest already binds a different training_authorization_receipt_sha256"
        )
    existing_receipt = manifest.training_authorization_receipt
    if existing_receipt is not None and existing_receipt.receipt_sha256 != digest:
        raise TrainingReadinessReceiptBindingError(
            "manifest already binds a different training_authorization_receipt"
        )

    return replace(
        manifest,
        training_authorization_receipt_sha256=digest,
        training_authorization_receipt=receipt,
    )


def construct_ready_to_launch_readiness(
    scientific_manifest: TrainingReadinessManifest,
    *,
    runtime_qualification: TrainingRuntimeQualificationReceipt,
    training_authorization: TrainingAuthorizationReceipt,
) -> tuple[TrainingReadinessManifest, TrainingReadinessReport]:
    """Bind runtime then authorization and require READY_TO_LAUNCH."""
    if (
        scientific_manifest.runtime_qualification_sha256 is not None
        or scientific_manifest.runtime_qualification_receipt is not None
    ):
        raise TrainingReadinessReceiptBindingError(
            "scientific_manifest must not already bind runtime qualification"
        )
    if (
        scientific_manifest.training_authorization_receipt_sha256 is not None
        or scientific_manifest.training_authorization_receipt is not None
    ):
        raise TrainingReadinessReceiptBindingError(
            "scientific_manifest must not already bind training authorization"
        )

    with_runtime = bind_runtime_qualification_to_readiness(
        scientific_manifest,
        runtime_qualification,
    )
    with_auth = bind_training_authorization_to_readiness(
        with_runtime,
        training_authorization,
        runtime_qualification=runtime_qualification,
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
