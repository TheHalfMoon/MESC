"""Fail-closed MESC release-artifact qualification for Spec 012 admission.

Assesses already-observed GitHub Release facts. Never invents assets, never uploads
releases, and never clears MedScale Spec 012 without complete verified evidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from medscale.reproducibility import content_hash

ReleaseQualificationDisposition = Literal["BLOCKED", "RELEASE_READY"]

_PROGRAM_VERSION: Final = "MESC-RELEASE-ARTIFACT-QUALIFICATION-V1"
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_REPO: Final = re.compile(r"^[^/\s]+/[^/\s]+$", flags=re.ASCII)


class ReleaseArtifactQualificationError(ValueError):
    """Raised when release qualification cannot be constructed fail-closed."""


@dataclass(frozen=True, slots=True)
class ReleaseAssetObservation:
    """One observed downloadable GitHub Release asset."""

    name: str
    size_bytes: int
    content_sha256: str
    browser_download_url: str

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ReleaseArtifactQualificationError("asset name must be a non-empty string")
        if type(self.size_bytes) is not int or self.size_bytes <= 0:
            raise ReleaseArtifactQualificationError("asset size_bytes must be a positive int")
        _require_sha256(self.content_sha256, field="asset content_sha256")
        if not isinstance(self.browser_download_url, str) or not self.browser_download_url.strip():
            raise ReleaseArtifactQualificationError(
                "asset browser_download_url must be a non-empty string"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "browser_download_url": self.browser_download_url.strip(),
            "content_sha256": self.content_sha256,
            "name": self.name.strip(),
            "size_bytes": self.size_bytes,
        }


@dataclass(frozen=True, slots=True)
class ReleaseObservation:
    """Observed GitHub Release facts supplied by an external observer."""

    repository: str
    tag_name: str
    release_id: int
    assets: tuple[ReleaseAssetObservation, ...]
    provenance_sha256: str | None
    rights_sha256: str | None
    sbom_sha256: str | None
    evaluation_report_sha256: str | None
    training_execution_receipt_sha256: str | None
    independent_refetch_verified: bool
    asset_hashes_verified: bool

    def __post_init__(self) -> None:
        if not isinstance(self.repository, str) or _REPO.fullmatch(self.repository) is None:
            raise ReleaseArtifactQualificationError(
                "repository must be exactly owner/name with no spaces"
            )
        if not isinstance(self.tag_name, str) or not self.tag_name.strip():
            raise ReleaseArtifactQualificationError("tag_name must be a non-empty string")
        if type(self.release_id) is not int or self.release_id <= 0:
            raise ReleaseArtifactQualificationError("release_id must be a positive int")
        if type(self.assets) is not tuple:
            raise ReleaseArtifactQualificationError("assets must be a tuple")
        for asset in self.assets:
            if type(asset) is not ReleaseAssetObservation:
                raise ReleaseArtifactQualificationError(
                    "each asset must be exactly ReleaseAssetObservation"
                )
        names = [asset.name.strip() for asset in self.assets]
        if len(set(names)) != len(names):
            raise ReleaseArtifactQualificationError("asset names must be unique")
        for field, value in (
            ("provenance_sha256", self.provenance_sha256),
            ("rights_sha256", self.rights_sha256),
            ("sbom_sha256", self.sbom_sha256),
            ("evaluation_report_sha256", self.evaluation_report_sha256),
            ("training_execution_receipt_sha256", self.training_execution_receipt_sha256),
        ):
            if value is not None:
                _require_sha256(value, field=field)
        if type(self.independent_refetch_verified) is not bool:
            raise ReleaseArtifactQualificationError("independent_refetch_verified must be a bool")
        if type(self.asset_hashes_verified) is not bool:
            raise ReleaseArtifactQualificationError("asset_hashes_verified must be a bool")

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_hashes_verified": self.asset_hashes_verified,
            "assets": [asset.to_dict() for asset in self.assets],
            "evaluation_report_sha256": self.evaluation_report_sha256,
            "independent_refetch_verified": self.independent_refetch_verified,
            "provenance_sha256": self.provenance_sha256,
            "release_id": self.release_id,
            "repository": self.repository,
            "rights_sha256": self.rights_sha256,
            "sbom_sha256": self.sbom_sha256,
            "tag_name": self.tag_name.strip(),
            "training_execution_receipt_sha256": self.training_execution_receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class ReleaseArtifactQualificationReport:
    """Fail-closed qualification result for one observed release."""

    disposition: ReleaseQualificationDisposition
    observation_sha256: str
    blockers: tuple[str, ...]
    asset_count: int
    medscale_spec_012_admission_readiness: str
    program_version: str = _PROGRAM_VERSION

    def __post_init__(self) -> None:
        if self.program_version != _PROGRAM_VERSION:
            raise ReleaseArtifactQualificationError(
                f"program_version must be exactly {_PROGRAM_VERSION}"
            )
        if self.disposition not in ("BLOCKED", "RELEASE_READY"):
            raise ReleaseArtifactQualificationError("disposition is invalid")
        _require_sha256(self.observation_sha256, field="observation_sha256")
        if type(self.blockers) is not tuple:
            raise ReleaseArtifactQualificationError("blockers must be a tuple")
        if type(self.asset_count) is not int or self.asset_count < 0:
            raise ReleaseArtifactQualificationError("asset_count must be a non-negative int")
        if self.disposition == "RELEASE_READY":
            if self.blockers:
                raise ReleaseArtifactQualificationError(
                    "RELEASE_READY reports cannot retain blockers"
                )
            if self.asset_count <= 0:
                raise ReleaseArtifactQualificationError(
                    "RELEASE_READY requires a positive asset_count"
                )
            if self.medscale_spec_012_admission_readiness != "READY":
                raise ReleaseArtifactQualificationError(
                    "RELEASE_READY requires medscale_spec_012_admission_readiness=READY"
                )
        if self.disposition == "BLOCKED":
            if not self.blockers:
                raise ReleaseArtifactQualificationError("BLOCKED reports must record blockers")
            if self.medscale_spec_012_admission_readiness != "NOT_READY":
                raise ReleaseArtifactQualificationError(
                    "BLOCKED requires medscale_spec_012_admission_readiness=NOT_READY"
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "asset_count": self.asset_count,
            "blockers": list(self.blockers),
            "disposition": self.disposition,
            "medscale_spec_012_admission_readiness": self.medscale_spec_012_admission_readiness,
            "observation_sha256": self.observation_sha256,
            "program_version": self.program_version,
        }


def qualify_release_artifact(
    observation: ReleaseObservation,
) -> ReleaseArtifactQualificationReport:
    """Qualify one observed release without inventing assets or remote fetches."""
    if type(observation) is not ReleaseObservation:
        raise ReleaseArtifactQualificationError("observation must be exactly ReleaseObservation")

    blockers: list[str] = []
    if not observation.assets:
        blockers.append("release assets are empty")
    if observation.provenance_sha256 is None:
        blockers.append("provenance_sha256 is absent")
    if observation.rights_sha256 is None:
        blockers.append("rights_sha256 is absent")
    if observation.sbom_sha256 is None:
        blockers.append("sbom_sha256 is absent")
    if observation.evaluation_report_sha256 is None:
        blockers.append("evaluation_report_sha256 is absent")
    if observation.training_execution_receipt_sha256 is None:
        blockers.append("training_execution_receipt_sha256 is absent")
    if not observation.independent_refetch_verified:
        blockers.append("independent re-fetch verification is false")
    if not observation.asset_hashes_verified:
        blockers.append("asset hash verification is false")

    disposition: ReleaseQualificationDisposition = "BLOCKED" if blockers else "RELEASE_READY"
    return ReleaseArtifactQualificationReport(
        disposition=disposition,
        observation_sha256=content_hash(observation.to_dict()),
        blockers=tuple(blockers),
        asset_count=len(observation.assets),
        medscale_spec_012_admission_readiness=(
            "READY" if disposition == "RELEASE_READY" else "NOT_READY"
        ),
    )


def _require_sha256(value: str, *, field: str) -> None:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ReleaseArtifactQualificationError(
            f"{field} must be exactly 64 lowercase hex characters"
        )


__all__ = [
    "ReleaseArtifactQualificationError",
    "ReleaseArtifactQualificationReport",
    "ReleaseAssetObservation",
    "ReleaseObservation",
    "ReleaseQualificationDisposition",
    "qualify_release_artifact",
]
