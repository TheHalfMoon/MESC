"""Fail-closed Hugging Face publication planning and dry-run qualification."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

SCHEMA_PLAN = "MESC-HF-PUBLICATION-PLAN-V1"
SCHEMA_RECEIPT = "MESC-HF-PUBLICATION-DRY-RUN-RECEIPT-V1"
CANONICAL_REPOSITORY = "TheHalfMoon/MESC"
CANONICAL_HF_OWNER = "MedScaleAI"

ArtifactClass = Literal["space", "model", "dataset"]
Disposition = Literal["DRY_RUN_READY", "BLOCKED"]

_SHA40 = re.compile(r"^[0-9a-f]{40}$", re.ASCII)
_SHA64 = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
_REPO = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$", re.ASCII)
_LICENSE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.+-]*$", re.ASCII)
_ARTIFACT_CLASSES: frozenset[str] = frozenset({"space", "model", "dataset"})
_PLAN_KEYS: frozenset[str] = frozenset(
    {
        "artifact_class",
        "artifacts",
        "card_sha256",
        "destination_owner",
        "destination_repo",
        "external_upload_enabled",
        "license_id",
        "provenance_sha256",
        "rights_sha256",
        "schema_version",
        "source_repository",
        "source_sha",
        "source_tag",
        "source_tree",
    }
)
_ARTIFACT_KEYS: frozenset[str] = frozenset({"byte_count", "path", "sha256"})


class HfPublicationQualificationError(ValueError):
    """Raised when a publication plan is malformed or unsafe."""


@dataclass(frozen=True, slots=True)
class HfPublicationArtifact:
    path: str
    byte_count: int
    sha256: str

    def __post_init__(self) -> None:
        pure = PurePosixPath(self.path)
        if (
            not self.path
            or self.path.startswith("/")
            or "\\" in self.path
            or pure.as_posix() != self.path
            or any(part in {"", ".", ".."} for part in pure.parts)
        ):
            raise HfPublicationQualificationError("artifact path must be safe and relative")
        if type(self.byte_count) is not int or self.byte_count <= 0:
            raise HfPublicationQualificationError("artifact byte_count must be positive")
        _require_sha256(self.sha256, field="artifact sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "byte_count": self.byte_count,
            "path": self.path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class HfPublicationPlan:
    artifact_class: ArtifactClass
    destination_owner: str
    destination_repo: str
    source_repository: str
    source_sha: str
    source_tree: str
    source_tag: str
    artifacts: tuple[HfPublicationArtifact, ...]
    card_sha256: str
    rights_sha256: str
    provenance_sha256: str
    license_id: str
    external_upload_enabled: bool = False
    schema_version: str = SCHEMA_PLAN

    def __post_init__(self) -> None:
        if self.schema_version != SCHEMA_PLAN:
            raise HfPublicationQualificationError("publication plan schema drifted")
        if self.artifact_class not in _ARTIFACT_CLASSES:
            raise HfPublicationQualificationError("unsupported Hugging Face artifact class")
        if not self.destination_owner or "/" in self.destination_owner:
            raise HfPublicationQualificationError("destination_owner is invalid")
        if _REPO.fullmatch(self.destination_repo) is None:
            raise HfPublicationQualificationError("destination_repo must be lowercase kebab-case")
        if not self.source_repository or self.source_repository.count("/") != 1:
            raise HfPublicationQualificationError("source_repository is invalid")
        if _SHA40.fullmatch(self.source_sha) is None:
            raise HfPublicationQualificationError("source_sha must be lowercase SHA-1")
        if _SHA40.fullmatch(self.source_tree) is None:
            raise HfPublicationQualificationError("source_tree must be lowercase SHA-1")
        if not self.source_tag or any(ch.isspace() for ch in self.source_tag):
            raise HfPublicationQualificationError("source_tag is invalid")
        if not self.artifacts:
            raise HfPublicationQualificationError("publication plan requires artifacts")
        paths = tuple(item.path for item in self.artifacts)
        if len(paths) != len(set(paths)):
            raise HfPublicationQualificationError("artifact paths must be unique")
        for field, value in (
            ("card_sha256", self.card_sha256),
            ("rights_sha256", self.rights_sha256),
            ("provenance_sha256", self.provenance_sha256),
        ):
            _require_sha256(value, field=field)
        if _LICENSE.fullmatch(self.license_id) is None:
            raise HfPublicationQualificationError("license_id is invalid")
        if type(self.external_upload_enabled) is not bool:
            raise HfPublicationQualificationError("external_upload_enabled must be bool")

    @property
    def artifact_manifest_sha256(self) -> str:
        payload = [item.to_dict() for item in sorted(self.artifacts, key=lambda row: row.path)]
        return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()

    @property
    def destination_repo_type(self) -> str:
        mapping = {"space": "space", "model": "model", "dataset": "dataset"}
        return mapping[self.artifact_class]

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_class": self.artifact_class,
            "artifacts": [
                item.to_dict() for item in sorted(self.artifacts, key=lambda row: row.path)
            ],
            "card_sha256": self.card_sha256,
            "destination_owner": self.destination_owner,
            "destination_repo": self.destination_repo,
            "external_upload_enabled": self.external_upload_enabled,
            "license_id": self.license_id,
            "provenance_sha256": self.provenance_sha256,
            "rights_sha256": self.rights_sha256,
            "schema_version": self.schema_version,
            "source_repository": self.source_repository,
            "source_sha": self.source_sha,
            "source_tag": self.source_tag,
            "source_tree": self.source_tree,
        }


@dataclass(frozen=True, slots=True)
class HfPublicationQualification:
    disposition: Disposition
    plan_sha256: str
    artifact_manifest_sha256: str
    blockers: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.plan_sha256, field="plan_sha256")
        _require_sha256(self.artifact_manifest_sha256, field="artifact_manifest_sha256")
        if self.disposition == "DRY_RUN_READY" and self.blockers:
            raise HfPublicationQualificationError(
                "DRY_RUN_READY qualification cannot contain blockers"
            )
        if self.disposition == "BLOCKED" and not self.blockers:
            raise HfPublicationQualificationError("BLOCKED qualification requires blockers")


def parse_publication_plan(raw: bytes) -> HfPublicationPlan:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HfPublicationQualificationError("publication plan is invalid JSON") from exc
    if type(payload) is not dict or set(payload) != _PLAN_KEYS:
        raise HfPublicationQualificationError("publication plan keys drifted")
    if canonical_json_bytes(payload) != raw:
        raise HfPublicationQualificationError("publication plan must be canonical JSON")
    rows = payload["artifacts"]
    if type(rows) is not list or not rows:
        raise HfPublicationQualificationError("artifacts must be a non-empty list")
    artifacts: list[HfPublicationArtifact] = []
    for row in rows:
        if type(row) is not dict or set(row) != _ARTIFACT_KEYS:
            raise HfPublicationQualificationError("artifact entry keys drifted")
        artifacts.append(
            HfPublicationArtifact(
                path=row["path"],
                byte_count=row["byte_count"],
                sha256=row["sha256"],
            )
        )
    return HfPublicationPlan(
        artifact_class=payload["artifact_class"],
        destination_owner=payload["destination_owner"],
        destination_repo=payload["destination_repo"],
        source_repository=payload["source_repository"],
        source_sha=payload["source_sha"],
        source_tree=payload["source_tree"],
        source_tag=payload["source_tag"],
        artifacts=tuple(artifacts),
        card_sha256=payload["card_sha256"],
        rights_sha256=payload["rights_sha256"],
        provenance_sha256=payload["provenance_sha256"],
        license_id=payload["license_id"],
        external_upload_enabled=payload["external_upload_enabled"],
        schema_version=payload["schema_version"],
    )


def qualify_publication_plan(
    plan: HfPublicationPlan,
    *,
    expected_repository: str,
    expected_sha: str,
    expected_tree: str,
    expected_tag: str,
    expected_owner: str = CANONICAL_HF_OWNER,
) -> HfPublicationQualification:
    if type(plan) is not HfPublicationPlan:
        raise HfPublicationQualificationError("plan must be exactly HfPublicationPlan")
    blockers: list[str] = []
    if plan.source_repository != expected_repository:
        blockers.append("source repository does not match canonical repository")
    if plan.source_sha != expected_sha:
        blockers.append("source SHA does not match canonical source")
    if plan.source_tree != expected_tree:
        blockers.append("source tree does not match canonical source")
    if plan.source_tag != expected_tag:
        blockers.append("source tag does not match canonical source")
    if plan.destination_owner != expected_owner:
        blockers.append("destination owner is outside the authorized allowlist")
    if plan.external_upload_enabled:
        blockers.append("external upload must remain disabled during repository qualification")
    artifacts_by_path = {item.path: item for item in plan.artifacts}
    if "README.md" not in artifacts_by_path:
        blockers.append("Hugging Face card README.md is absent")
    elif artifacts_by_path["README.md"].sha256 != plan.card_sha256:
        blockers.append("card_sha256 does not bind README.md")
    disposition: Disposition = "BLOCKED" if blockers else "DRY_RUN_READY"
    plan_sha256 = hashlib.sha256(canonical_json_bytes(plan.to_dict())).hexdigest()
    return HfPublicationQualification(
        disposition=disposition,
        plan_sha256=plan_sha256,
        artifact_manifest_sha256=plan.artifact_manifest_sha256,
        blockers=tuple(blockers),
    )


def build_dry_run_receipt(
    plan: HfPublicationPlan,
    qualification: HfPublicationQualification,
    *,
    expected_repository: str,
    expected_sha: str,
    expected_tree: str,
    expected_tag: str,
    expected_owner: str = CANONICAL_HF_OWNER,
) -> bytes:
    fresh = qualify_publication_plan(
        plan,
        expected_repository=expected_repository,
        expected_sha=expected_sha,
        expected_tree=expected_tree,
        expected_tag=expected_tag,
        expected_owner=expected_owner,
    )
    if qualification != fresh:
        raise HfPublicationQualificationError(
            "qualification does not match fresh plan qualification"
        )
    if fresh.disposition != "DRY_RUN_READY" or fresh.blockers:
        raise HfPublicationQualificationError(
            "dry-run receipt requires a DRY_RUN_READY qualification"
        )
    expected_plan_sha = hashlib.sha256(canonical_json_bytes(plan.to_dict())).hexdigest()
    if fresh.plan_sha256 != expected_plan_sha:
        raise HfPublicationQualificationError("qualification does not bind this plan")
    if fresh.artifact_manifest_sha256 != plan.artifact_manifest_sha256:
        raise HfPublicationQualificationError(
            "qualification artifact manifest does not bind this plan"
        )
    receipt = {
        "artifact_class": plan.artifact_class,
        "artifact_manifest_sha256": plan.artifact_manifest_sha256,
        "destination_owner": plan.destination_owner,
        "destination_repo": plan.destination_repo,
        "destination_repo_type": plan.destination_repo_type,
        "external_upload_performed": False,
        "plan_sha256": fresh.plan_sha256,
        "schema_version": SCHEMA_RECEIPT,
        "source_repository": plan.source_repository,
        "source_sha": plan.source_sha,
        "source_tag": plan.source_tag,
        "source_tree": plan.source_tree,
    }
    return canonical_json_bytes(receipt)


def _require_sha256(value: str, *, field: str) -> None:
    if type(value) is not str or _SHA64.fullmatch(value) is None:
        raise HfPublicationQualificationError(
            f"{field} must be exactly 64 lowercase hex characters"
        )


__all__ = [
    "CANONICAL_HF_OWNER",
    "CANONICAL_REPOSITORY",
    "SCHEMA_PLAN",
    "SCHEMA_RECEIPT",
    "HfPublicationArtifact",
    "HfPublicationPlan",
    "HfPublicationQualification",
    "HfPublicationQualificationError",
    "build_dry_run_receipt",
    "parse_publication_plan",
    "qualify_publication_plan",
]
