"""Fail-closed temporal-canary recycling guard for MESC Research Loop V1.

MRL-0607 prevents identities from one sealed MRL-0606 temporal-canary chain from being
admitted as training or adaptive-search artifacts. The guard records identity comparisons
only. A clear report proves only that the supplied attempted-use set does not recycle the
sealed canary chain; it grants no training, search, data, model, execution, or promotion
authority.
"""

from __future__ import annotations

import enum
import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_temporal_canary_fixture_workflow_v1 import (
    TemporalCanaryFixtureReceipt,
    TemporalCanaryFixtureWorkflowError,
)

__all__ = [
    "CanaryArtifactUse",
    "CanaryRecyclingDisposition",
    "CanaryRecyclingError",
    "CanaryRecyclingGuardReport",
    "CanaryRecyclingTarget",
    "build_canary_recycling_guard_report",
    "require_no_canary_recycling",
]

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CanaryRecyclingError(ValueError):
    """Fail-closed validation or enforcement error for MRL-0607."""


class CanaryRecyclingTarget(enum.Enum):
    """Closed set of destinations from which the canary chain must be excluded."""

    TRAINING = "TRAINING"
    SEARCH = "SEARCH"


class CanaryRecyclingDisposition(enum.Enum):
    """Deterministic disposition for one exact attempted-use set."""

    CLEAR = "CLEAR"
    BLOCKED = "BLOCKED"


def _make_use_identity_registry() -> tuple[
    Callable[[CanaryArtifactUse, str], None],
    Callable[[CanaryArtifactUse], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: CanaryArtifactUse, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise CanaryRecyclingError("canary artifact use construction identity already exists")
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: CanaryArtifactUse) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise CanaryRecyclingError("canary artifact use construction identity is missing")
        return identity

    return store, load


def _make_report_identity_registry() -> tuple[
    Callable[[CanaryRecyclingGuardReport, str], None],
    Callable[[CanaryRecyclingGuardReport], str],
]:
    identities: dict[int, str] = {}

    def remove(key: int) -> None:
        identities.pop(key, None)

    def store(value: CanaryRecyclingGuardReport, content_sha256: str) -> None:
        key = id(value)
        if key in identities:
            raise CanaryRecyclingError(
                "canary recycling report construction identity already exists"
            )
        identities[key] = content_sha256
        weakref.finalize(value, remove, key)

    def load(value: CanaryRecyclingGuardReport) -> str:
        identity = identities.get(id(value))
        if identity is None:
            raise CanaryRecyclingError("canary recycling report construction identity is missing")
        return identity

    return store, load


_store_use_identity, _load_use_identity = _make_use_identity_registry()
_store_report_identity, _load_report_identity = _make_report_identity_registry()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class CanaryArtifactUse:
    """One exact artifact identity proposed for training or adaptive search."""

    target: CanaryRecyclingTarget
    artifact_sha256: str

    def __post_init__(self) -> None:
        if type(self.target) is not CanaryRecyclingTarget:
            raise CanaryRecyclingError("target must be an exact CanaryRecyclingTarget")
        _require_sha256(self.artifact_sha256, "artifact_sha256")
        _store_use_identity(self, derive_content_sha256(self._to_dict_validated()))

    def _validated_snapshot(self) -> CanaryArtifactUse:
        if type(self) is not CanaryArtifactUse:
            raise CanaryRecyclingError("attempted use must be an exact CanaryArtifactUse")
        bound_content_sha256 = _load_use_identity(self)
        _require_sha256(bound_content_sha256, "bound attempted-use content_sha256")
        snapshot = CanaryArtifactUse(
            target=self.target,
            artifact_sha256=self.artifact_sha256,
        )
        if derive_content_sha256(snapshot._to_dict_validated()) != bound_content_sha256:
            raise CanaryRecyclingError("canary artifact use identity changed after construction")
        return snapshot

    def _to_dict_validated(self) -> dict[str, str]:
        return {
            "artifact_sha256": self.artifact_sha256,
            "target": self.target.value,
        }

    def to_dict(self) -> dict[str, str]:
        return self._validated_snapshot()._to_dict_validated()


@dataclass(frozen=True, slots=True, weakref_slot=True)
class CanaryRecyclingGuardReport:
    """Construction-bound evidence that evaluates one exact canary-use attempt set."""

    canary_receipt_sha256: str
    protected_artifact_sha256s: tuple[str, ...]
    attempted_uses: tuple[CanaryArtifactUse, ...]
    blocked_uses: tuple[CanaryArtifactUse, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.canary_receipt_sha256, "canary_receipt_sha256")
        _require_sha_tuple(self.protected_artifact_sha256s, "protected_artifact_sha256s")
        attempted_snapshots = _validated_use_tuple(self.attempted_uses, "attempted_uses")
        blocked_snapshots = _validated_use_tuple(self.blocked_uses, "blocked_uses")
        _require_sorted_unique_uses(attempted_snapshots, "attempted_uses")
        _require_sorted_unique_uses(blocked_snapshots, "blocked_uses")
        expected_blocked = tuple(
            use
            for use in attempted_snapshots
            if use.artifact_sha256 in self.protected_artifact_sha256s
        )
        if tuple(_use_key(use) for use in blocked_snapshots) != tuple(
            _use_key(use) for use in expected_blocked
        ):
            raise CanaryRecyclingError(
                "blocked_uses must exactly equal attempted uses that overlap "
                "the protected canary chain"
            )
        _store_report_identity(
            self,
            derive_content_sha256(self._semantic_dict_validated()),
        )

    def _validated_snapshot(self) -> CanaryRecyclingGuardReport:
        if type(self) is not CanaryRecyclingGuardReport:
            raise CanaryRecyclingError(
                "report must be an exact CanaryRecyclingGuardReport"
            )
        bound_content_sha256 = _load_report_identity(self)
        _require_sha256(bound_content_sha256, "bound report content_sha256")
        snapshot = CanaryRecyclingGuardReport(
            canary_receipt_sha256=self.canary_receipt_sha256,
            protected_artifact_sha256s=tuple(self.protected_artifact_sha256s),
            attempted_uses=tuple(use._validated_snapshot() for use in self.attempted_uses),
            blocked_uses=tuple(use._validated_snapshot() for use in self.blocked_uses),
        )
        if derive_content_sha256(snapshot._semantic_dict_validated()) != bound_content_sha256:
            raise CanaryRecyclingError(
                "canary recycling report identity changed after construction"
            )
        return snapshot

    def _disposition_validated(self) -> CanaryRecyclingDisposition:
        if self.blocked_uses:
            return CanaryRecyclingDisposition.BLOCKED
        return CanaryRecyclingDisposition.CLEAR

    @property
    def disposition(self) -> CanaryRecyclingDisposition:
        return self._validated_snapshot()._disposition_validated()

    @property
    def can_authorize_training(self) -> bool:
        return False

    @property
    def can_authorize_search(self) -> bool:
        return False

    @property
    def can_authorize(self) -> bool:
        return False

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "attempted_uses": [use._to_dict_validated() for use in self.attempted_uses],
            "blocked_uses": [use._to_dict_validated() for use in self.blocked_uses],
            "can_authorize": False,
            "can_authorize_search": False,
            "can_authorize_training": False,
            "canary_receipt_sha256": self.canary_receipt_sha256,
            "disposition": self._disposition_validated().value,
            "format": "MRL-CANARY-RECYCLING-GUARD-REPORT-V1",
            "protected_artifact_sha256s": list(self.protected_artifact_sha256s),
        }

    def semantic_dict(self) -> dict[str, object]:
        return self._validated_snapshot()._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


def build_canary_recycling_guard_report(
    receipt: TemporalCanaryFixtureReceipt,
    attempted_uses: tuple[CanaryArtifactUse, ...],
) -> CanaryRecyclingGuardReport:
    """Evaluate training/search artifact identities against one sealed canary chain."""
    if type(receipt) is not TemporalCanaryFixtureReceipt:
        raise CanaryRecyclingError(
            "receipt must be an exact TemporalCanaryFixtureReceipt"
        )
    try:
        receipt_snapshot = receipt._validated_snapshot()
    except TemporalCanaryFixtureWorkflowError as exc:
        raise CanaryRecyclingError("canary receipt failed canonical revalidation") from exc

    attempted_snapshots = _validated_use_tuple(attempted_uses, "attempted_uses")
    _require_sorted_unique_uses(attempted_snapshots, "attempted_uses")
    protected_artifact_sha256s = tuple(
        sorted(
            {
                receipt_snapshot.content_sha256,
                receipt_snapshot.manifest_sha256,
                receipt_snapshot.canary_artifact_sha256,
                receipt_snapshot.evaluation_sha256,
            }
        )
    )
    blocked_uses = tuple(
        use
        for use in attempted_snapshots
        if use.artifact_sha256 in protected_artifact_sha256s
    )
    return CanaryRecyclingGuardReport(
        canary_receipt_sha256=receipt_snapshot.content_sha256,
        protected_artifact_sha256s=protected_artifact_sha256s,
        attempted_uses=attempted_snapshots,
        blocked_uses=blocked_uses,
    )


def require_no_canary_recycling(
    receipt: TemporalCanaryFixtureReceipt,
    attempted_uses: tuple[CanaryArtifactUse, ...],
) -> CanaryRecyclingGuardReport:
    """Return a clear report or fail closed when any canary-chain identity is recycled."""
    report = build_canary_recycling_guard_report(receipt, attempted_uses)
    if report.disposition is CanaryRecyclingDisposition.BLOCKED:
        blocked_targets = ",".join(use.target.value for use in report.blocked_uses)
        raise CanaryRecyclingError(
            f"temporal-canary recycling into training/search is prohibited: {blocked_targets}"
        )
    return report


def _validated_use_tuple(
    values: tuple[CanaryArtifactUse, ...],
    label: str,
) -> tuple[CanaryArtifactUse, ...]:
    if type(values) is not tuple:
        raise CanaryRecyclingError(f"{label} must be an exact tuple")
    if any(type(value) is not CanaryArtifactUse for value in values):
        raise CanaryRecyclingError(f"{label} contains an invalid item type")
    return tuple(value._validated_snapshot() for value in values)


def _require_sorted_unique_uses(
    values: tuple[CanaryArtifactUse, ...],
    label: str,
) -> None:
    keys = tuple(_use_key(value) for value in values)
    if keys != tuple(sorted(set(keys))):
        raise CanaryRecyclingError(f"{label} must be unique and sorted by target/artifact identity")


def _use_key(value: CanaryArtifactUse) -> tuple[str, str]:
    return (value.target.value, value.artifact_sha256)


def _require_sha_tuple(values: tuple[str, ...], label: str) -> None:
    if type(values) is not tuple or not values:
        raise CanaryRecyclingError(f"{label} must be a non-empty exact tuple")
    for value in values:
        _require_sha256(value, label)
    if values != tuple(sorted(set(values))):
        raise CanaryRecyclingError(f"{label} must be unique and strictly sorted")


def _require_sha256(value: object, label: str) -> None:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CanaryRecyclingError(f"{label} must be 64 lowercase hex")
