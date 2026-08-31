"""Repository-controlled trust root for independent MRL procedure-review receipts.

A syntactically valid reviewer identity or receipt cannot create procedure-admission
authority. Positive trust additionally requires the exact review-receipt content digest
to be provisioned by a separate canonical repository-governance change. The production
registry intentionally starts empty.

The canonical public API is bound to one private registry object and then the object name
is deleted, so ordinary module-level rebinding cannot replace the authority consulted by
already-bound admission code. A private lock-aware replacement callable exists only for
deterministic tests. Arbitrary interpreter-state rewriting remains outside this
contract-level boundary.

This module grants no model, data, network, GPU, training, promotion, deployment, release,
or clinical authority.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from typing import Final

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

TRUST_REGISTRY_VERSION: Final = "MRL-PROCEDURE-REVIEW-TRUST-REGISTRY-V1"

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_REGISTRY_KIND: Final = "mesc.mrl.procedure_review.trust_registry.v1"


class ProcedureReviewTrustError(RuntimeError):
    """Raised when canonical independent-review trust cannot be validated."""


@dataclass(frozen=True, slots=True)
class ProcedureReviewTrustSnapshot:
    """One immutable self-consistent view of canonical review-receipt trust."""

    registry_version: str
    trusted_review_receipt_sha256: frozenset[str]
    registry_sha256: str

    def admits(self, value: str) -> bool:
        """Return whether this exact snapshot admits one receipt digest."""
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            return False
        return value in self.trusted_review_receipt_sha256


class _ProcedureReviewTrustRegistry:
    """Private lock-aware trust state captured by bound public callables."""

    def __init__(self, registry: frozenset[str]) -> None:
        self._lock = Lock()
        self._active_admissions = 0
        self._registry = registry
        self._validated_snapshot_unlocked()

    def snapshot(self) -> ProcedureReviewTrustSnapshot:
        """Capture one validated immutable trust-registry snapshot."""
        with self._lock:
            return self._validated_snapshot_unlocked()

    def registry_sha256(self) -> str:
        """Return the deterministic identity of the current trust snapshot."""
        return self.snapshot().registry_sha256

    def validate(
        self,
        *,
        expected_registry_sha256: str,
        review_receipt_sha256: str,
    ) -> ProcedureReviewTrustSnapshot:
        """Validate registry identity and exact review-receipt membership."""
        snapshot = self.snapshot()
        _require_snapshot_admission(
            snapshot,
            expected_registry_sha256=expected_registry_sha256,
            review_receipt_sha256=review_receipt_sha256,
        )
        return snapshot

    @contextmanager
    def hold(
        self,
        *,
        expected_registry_sha256: str,
        review_receipt_sha256: str,
    ) -> Iterator[ProcedureReviewTrustSnapshot]:
        """Lease one valid review-trust snapshot across pure admission construction."""
        with self._lock:
            snapshot = self._validated_snapshot_unlocked()
            _require_snapshot_admission(
                snapshot,
                expected_registry_sha256=expected_registry_sha256,
                review_receipt_sha256=review_receipt_sha256,
            )
            self._active_admissions += 1

        try:
            yield snapshot
        finally:
            with self._lock:
                self._active_admissions -= 1

    def replace_for_tests(self, registry: frozenset[str]) -> frozenset[str]:
        """Replace synthetic test trust under the same lock used by admission."""
        _validate_registry(registry, test_mode=True)
        with self._lock:
            if self._active_admissions:
                raise ProcedureReviewTrustError(
                    "procedure-review trust registry cannot change during active admission"
                )
            previous = self._registry
            self._registry = registry
            return previous

    def _validated_snapshot_unlocked(self) -> ProcedureReviewTrustSnapshot:
        registry = self._registry
        _validate_registry(registry, test_mode=False)
        payload = {
            "kind": _REGISTRY_KIND,
            "registry_version": TRUST_REGISTRY_VERSION,
            "trusted_review_receipt_sha256": sorted(registry),
        }
        return ProcedureReviewTrustSnapshot(
            registry_version=TRUST_REGISTRY_VERSION,
            trusted_review_receipt_sha256=registry,
            registry_sha256=hashlib.sha256(canonical_json_bytes(payload)).hexdigest(),
        )


def _validate_registry(
    registry: frozenset[str],
    *,
    test_mode: bool,
) -> None:
    prefix = "test " if test_mode else ""
    if type(registry) is not frozenset:
        error: type[Exception] = TypeError if test_mode else ProcedureReviewTrustError
        raise error(f"{prefix}procedure-review trust registry must be an exact frozenset")
    for value in registry:
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            error = ValueError if test_mode else ProcedureReviewTrustError
            raise error(f"{prefix}procedure-review trust entries must be 64 lowercase hex")


def _require_snapshot_admission(
    snapshot: ProcedureReviewTrustSnapshot,
    *,
    expected_registry_sha256: str,
    review_receipt_sha256: str,
) -> None:
    if (
        type(expected_registry_sha256) is not str
        or _SHA256.fullmatch(expected_registry_sha256) is None
    ):
        raise ProcedureReviewTrustError(
            "expected procedure-review trust registry identity must be 64 lowercase hex"
        )
    if type(review_receipt_sha256) is not str or _SHA256.fullmatch(review_receipt_sha256) is None:
        raise ProcedureReviewTrustError(
            "procedure-review receipt identity must be 64 lowercase hex"
        )
    if snapshot.registry_sha256 != expected_registry_sha256:
        raise ProcedureReviewTrustError(
            "procedure-review trust registry changed after receipt admission"
        )
    if not snapshot.admits(review_receipt_sha256):
        raise ProcedureReviewTrustError(
            "procedure-review receipt is not trusted by the canonical registry"
        )


_canonical_registry = _ProcedureReviewTrustRegistry(frozenset())
procedure_review_trust_snapshot = _canonical_registry.snapshot
procedure_review_trust_registry_sha256 = _canonical_registry.registry_sha256
validate_procedure_review_trust = _canonical_registry.validate
hold_procedure_review_trust = _canonical_registry.hold
_replace_procedure_review_trust_registry_for_tests = _canonical_registry.replace_for_tests
del _canonical_registry


__all__ = [
    "TRUST_REGISTRY_VERSION",
    "ProcedureReviewTrustError",
    "ProcedureReviewTrustSnapshot",
    "hold_procedure_review_trust",
    "procedure_review_trust_registry_sha256",
    "procedure_review_trust_snapshot",
    "validate_procedure_review_trust",
]
