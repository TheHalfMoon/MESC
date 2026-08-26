"""Semantic release evidence for fail-closed MESC release qualification.

This module validates already-supplied evidence bytes in memory. It performs no network,
release, model, GPU, provider, or training work. Opaque digest presence alone is not
semantic evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Final, Literal, cast

from medscale.mesc._canonical_json_v1 import canonical_json_bytes
from medscale.reproducibility import content_hash

ReleaseEvidenceKind = Literal["PROVENANCE", "RIGHTS", "SBOM", "EVALUATION"]

_PROGRAM_VERSION: Final = "MESC-RELEASE-SEMANTIC-EVIDENCE-V1"
_EXECUTOR_VERSION: Final = "MESC-TRAINING-EXECUTOR-V1"
_RESULT_MANIFEST_KIND: Final = "mesc.training_execution.results.v1"
_REPO: Final = re.compile(r"^[^/\s]+/[^/\s]+$", flags=re.ASCII)
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_GIT_SHA: Final = re.compile(r"^[0-9a-f]{40}$", flags=re.ASCII)
_BOUND_KIND: Final = {
    "PROVENANCE": "mesc.release.provenance.v1",
    "RIGHTS": "mesc.release.rights.v1",
    "SBOM": "mesc.release.sbom.v1",
    "EVALUATION": "mesc.release.evaluation.v1",
}
_TRAINING_RECEIPT_KEYS: Final = frozenset(
    {
        "backend_id",
        "backend_version",
        "corpus_binding_sha256",
        "dependency_lock_sha256",
        "disposition",
        "environment_sha256",
        "execution_manifest_sha256",
        "executor_version",
        "experiment_id",
        "failure_reason",
        "finished_at",
        "launch_plan_sha256",
        "local_asset_attestation_sha256",
        "model_id",
        "readiness_manifest_sha256",
        "repository_sha",
        "repository_tree",
        "result_artifacts",
        "result_manifest_sha256",
        "revision",
        "role",
        "run_plan_sha256",
        "runtime_qualification_sha256",
        "started_at",
        "training_authorization_receipt_sha256",
        "training_dataset_sha256",
        "weights_sha256",
    }
)
_BOUND_DOCUMENT_KEYS: Final = frozenset(
    {
        "artifact_byte_count",
        "artifact_sha256",
        "asset_manifest_sha256",
        "disposition",
        "kind",
        "release_id",
        "repository",
        "tag_name",
        "training_execution_receipt_sha256",
    }
)


class ReleaseSemanticEvidenceError(ValueError):
    """Raised when release evidence cannot be validated fail-closed."""


@dataclass(frozen=True, slots=True)
class TrainingExecutionEvidence:
    """Validated canonical bytes for one successful core training receipt."""

    canonical_bytes: bytes = field(repr=False)
    receipt_sha256: str = field(init=False)
    result_manifest_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        payload = _parse_canonical_object(self.canonical_bytes, label="training receipt")
        if frozenset(payload) != _TRAINING_RECEIPT_KEYS:
            raise ReleaseSemanticEvidenceError(
                "training receipt must contain the exact canonical executor receipt keys"
            )
        if payload["executor_version"] != _EXECUTOR_VERSION:
            raise ReleaseSemanticEvidenceError("training receipt executor_version is invalid")
        if payload["disposition"] != "SUCCEEDED":
            raise ReleaseSemanticEvidenceError("training receipt disposition must be SUCCEEDED")
        if payload["failure_reason"] is not None:
            raise ReleaseSemanticEvidenceError(
                "successful training receipt cannot retain failure_reason"
            )

        for field_name in (
            "corpus_binding_sha256",
            "dependency_lock_sha256",
            "environment_sha256",
            "execution_manifest_sha256",
            "launch_plan_sha256",
            "local_asset_attestation_sha256",
            "readiness_manifest_sha256",
            "result_manifest_sha256",
            "run_plan_sha256",
            "runtime_qualification_sha256",
            "training_authorization_receipt_sha256",
            "training_dataset_sha256",
            "weights_sha256",
        ):
            _require_sha256(payload[field_name], field=field_name)
        for field_name in ("repository_sha", "repository_tree", "revision"):
            _require_git_sha(payload[field_name], field=field_name)
        for field_name in (
            "backend_id",
            "backend_version",
            "experiment_id",
            "finished_at",
            "model_id",
            "role",
            "started_at",
        ):
            _require_text(payload[field_name], field=field_name)

        artifacts = _require_result_artifacts(payload["result_artifacts"])
        expected_manifest = content_hash(
            {
                "artifacts": artifacts,
                "kind": _RESULT_MANIFEST_KIND,
            }
        )
        result_manifest = cast(str, payload["result_manifest_sha256"])
        if result_manifest != expected_manifest:
            raise ReleaseSemanticEvidenceError(
                "training receipt result_manifest_sha256 does not match result_artifacts"
            )

        object.__setattr__(self, "receipt_sha256", content_hash(payload))
        object.__setattr__(self, "result_manifest_sha256", result_manifest)


@dataclass(frozen=True, slots=True)
class ReleaseBoundEvidenceDocument:
    """One release-bound evidence envelope plus the exact evidence artifact bytes."""

    kind: ReleaseEvidenceKind
    canonical_envelope_bytes: bytes = field(repr=False)
    artifact_bytes: bytes = field(repr=False)
    repository: str = field(init=False)
    tag_name: str = field(init=False)
    release_id: int = field(init=False)
    asset_manifest_sha256: str = field(init=False)
    training_execution_receipt_sha256: str = field(init=False)
    artifact_sha256: str = field(init=False)
    artifact_byte_count: int = field(init=False)
    document_sha256: str = field(init=False)

    def __post_init__(self) -> None:
        if self.kind not in _BOUND_KIND:
            raise ReleaseSemanticEvidenceError("release evidence kind is invalid")
        if type(self.artifact_bytes) is not bytes or not self.artifact_bytes:
            raise ReleaseSemanticEvidenceError("release evidence artifact bytes must be non-empty")

        payload = _parse_canonical_object(
            self.canonical_envelope_bytes,
            label=f"{self.kind.lower()} evidence envelope",
        )
        if frozenset(payload) != _BOUND_DOCUMENT_KEYS:
            raise ReleaseSemanticEvidenceError(
                "release evidence envelope must contain the exact canonical key set"
            )
        if payload["kind"] != _BOUND_KIND[self.kind]:
            raise ReleaseSemanticEvidenceError("release evidence envelope kind does not match role")
        if payload["disposition"] != "PASS":
            raise ReleaseSemanticEvidenceError("release evidence disposition must be PASS")

        repository = _require_repository(payload["repository"])
        tag_name = _require_text(payload["tag_name"], field="tag_name")
        release_id = _require_positive_int(payload["release_id"], field="release_id")
        asset_manifest = _require_sha256(
            payload["asset_manifest_sha256"],
            field="asset_manifest_sha256",
        )
        training_receipt = _require_sha256(
            payload["training_execution_receipt_sha256"],
            field="training_execution_receipt_sha256",
        )
        artifact_sha = _require_sha256(payload["artifact_sha256"], field="artifact_sha256")
        artifact_count = _require_positive_int(
            payload["artifact_byte_count"],
            field="artifact_byte_count",
        )

        observed_sha = hashlib.sha256(self.artifact_bytes).hexdigest()
        if artifact_sha != observed_sha:
            raise ReleaseSemanticEvidenceError(
                "release evidence artifact_sha256 does not match exact artifact bytes"
            )
        if artifact_count != len(self.artifact_bytes):
            raise ReleaseSemanticEvidenceError(
                "release evidence artifact_byte_count does not match exact artifact bytes"
            )
        _validate_artifact_semantics(
            kind=self.kind,
            artifact_bytes=self.artifact_bytes,
            asset_manifest_sha256=asset_manifest,
            training_execution_receipt_sha256=training_receipt,
        )

        object.__setattr__(self, "repository", repository)
        object.__setattr__(self, "tag_name", tag_name)
        object.__setattr__(self, "release_id", release_id)
        object.__setattr__(self, "asset_manifest_sha256", asset_manifest)
        object.__setattr__(self, "training_execution_receipt_sha256", training_receipt)
        object.__setattr__(self, "artifact_sha256", artifact_sha)
        object.__setattr__(self, "artifact_byte_count", artifact_count)
        object.__setattr__(self, "document_sha256", content_hash(payload))

    def to_dict(self) -> dict[str, object]:
        return {
            "artifact_byte_count": self.artifact_byte_count,
            "artifact_sha256": self.artifact_sha256,
            "asset_manifest_sha256": self.asset_manifest_sha256,
            "document_sha256": self.document_sha256,
            "kind": self.kind,
            "release_id": self.release_id,
            "repository": self.repository,
            "tag_name": self.tag_name,
            "training_execution_receipt_sha256": self.training_execution_receipt_sha256,
        }


@dataclass(frozen=True, slots=True)
class ReleaseSemanticEvidenceBundle:
    """Typed evidence bundle required before release qualification may succeed."""

    training_execution: TrainingExecutionEvidence
    provenance: ReleaseBoundEvidenceDocument
    rights: ReleaseBoundEvidenceDocument
    sbom: ReleaseBoundEvidenceDocument
    evaluation: ReleaseBoundEvidenceDocument
    program_version: str = _PROGRAM_VERSION

    def __post_init__(self) -> None:
        if self.program_version != _PROGRAM_VERSION:
            raise ReleaseSemanticEvidenceError(
                f"program_version must be exactly {_PROGRAM_VERSION}"
            )
        if type(self.training_execution) is not TrainingExecutionEvidence:
            raise ReleaseSemanticEvidenceError(
                "training_execution must be exact TrainingExecutionEvidence"
            )
        documents = (
            ("PROVENANCE", self.provenance),
            ("RIGHTS", self.rights),
            ("SBOM", self.sbom),
            ("EVALUATION", self.evaluation),
        )
        for expected_kind, document in documents:
            if type(document) is not ReleaseBoundEvidenceDocument:
                raise ReleaseSemanticEvidenceError(
                    "release evidence documents must use exact canonical types"
                )
            if document.kind != expected_kind:
                raise ReleaseSemanticEvidenceError(
                    f"{expected_kind.lower()} document occupies the wrong evidence role"
                )

        reference = self.provenance
        for _, document in documents:
            if document.repository != reference.repository:
                raise ReleaseSemanticEvidenceError("evidence documents disagree on repository")
            if document.tag_name != reference.tag_name:
                raise ReleaseSemanticEvidenceError("evidence documents disagree on tag_name")
            if document.release_id != reference.release_id:
                raise ReleaseSemanticEvidenceError("evidence documents disagree on release_id")
            if document.asset_manifest_sha256 != reference.asset_manifest_sha256:
                raise ReleaseSemanticEvidenceError(
                    "evidence documents disagree on asset_manifest_sha256"
                )
            if document.training_execution_receipt_sha256 != self.training_execution.receipt_sha256:
                raise ReleaseSemanticEvidenceError(
                    "evidence document training receipt identity does not match validated receipt"
                )

    @property
    def repository(self) -> str:
        return self.provenance.repository

    @property
    def tag_name(self) -> str:
        return self.provenance.tag_name

    @property
    def release_id(self) -> int:
        return self.provenance.release_id

    @property
    def asset_manifest_sha256(self) -> str:
        return self.provenance.asset_manifest_sha256

    @property
    def bundle_sha256(self) -> str:
        return content_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation": self.evaluation.to_dict(),
            "program_version": self.program_version,
            "provenance": self.provenance.to_dict(),
            "rights": self.rights.to_dict(),
            "sbom": self.sbom.to_dict(),
            "training_execution_receipt_sha256": self.training_execution.receipt_sha256,
        }


def _parse_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        raise ReleaseSemanticEvidenceError(f"{label} must be non-empty exact bytes")
    try:
        text = raw.decode("utf-8")
        parsed = json.loads(text, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseSemanticEvidenceError(f"{label} must be valid UTF-8 JSON") from exc
    if type(parsed) is not dict:
        raise ReleaseSemanticEvidenceError(f"{label} must be a JSON object")
    payload = cast(dict[str, object], parsed)
    if canonical_json_bytes(payload) != raw:
        raise ReleaseSemanticEvidenceError(f"{label} bytes are not canonical JSON")
    return payload


def _parse_artifact_object(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseSemanticEvidenceError(f"{label} artifact must be valid UTF-8 JSON") from exc
    if type(parsed) is not dict:
        raise ReleaseSemanticEvidenceError(f"{label} artifact must be a JSON object")
    return cast(dict[str, object], parsed)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ReleaseSemanticEvidenceError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def _require_result_artifacts(value: object) -> list[dict[str, object]]:
    if type(value) is not list or not value:
        raise ReleaseSemanticEvidenceError("training receipt result_artifacts must be non-empty")
    artifacts: list[dict[str, object]] = []
    paths: list[str] = []
    for item in value:
        if type(item) is not dict:
            raise ReleaseSemanticEvidenceError("training receipt artifact must be an object")
        artifact = cast(dict[str, object], item)
        if frozenset(artifact) != {"byte_count", "path", "sha256"}:
            raise ReleaseSemanticEvidenceError("training receipt artifact keys are invalid")
        path = _require_text(artifact["path"], field="artifact path")
        _require_sha256(artifact["sha256"], field="artifact sha256")
        _require_positive_int(artifact["byte_count"], field="artifact byte_count")
        paths.append(path)
        artifacts.append(artifact)
    if paths != sorted(paths) or len(paths) != len(set(paths)):
        raise ReleaseSemanticEvidenceError(
            "training receipt result_artifacts must have unique canonical path ordering"
        )
    return artifacts


def _validate_artifact_semantics(
    *,
    kind: ReleaseEvidenceKind,
    artifact_bytes: bytes,
    asset_manifest_sha256: str,
    training_execution_receipt_sha256: str,
) -> None:
    document = _parse_artifact_object(artifact_bytes, label=kind.lower())
    if kind == "SBOM":
        cyclonedx = document.get("bomFormat") == "CycloneDX"
        spdx = isinstance(document.get("spdxVersion"), str) and cast(
            str, document["spdxVersion"]
        ).startswith("SPDX-")
        if not cyclonedx and not spdx:
            raise ReleaseSemanticEvidenceError("SBOM artifact must identify CycloneDX or SPDX JSON")
        return

    if kind in ("RIGHTS", "EVALUATION") and document.get("disposition") != "PASS":
        raise ReleaseSemanticEvidenceError(f"{kind.lower()} artifact disposition must be PASS")
    if document.get("asset_manifest_sha256") != asset_manifest_sha256:
        raise ReleaseSemanticEvidenceError(
            f"{kind.lower()} artifact is not bound to the release asset manifest"
        )
    if kind in ("PROVENANCE", "EVALUATION") and (
        document.get("training_execution_receipt_sha256") != training_execution_receipt_sha256
    ):
        raise ReleaseSemanticEvidenceError(
            f"{kind.lower()} artifact is not bound to the training execution receipt"
        )


def _require_repository(value: object) -> str:
    if not isinstance(value, str) or _REPO.fullmatch(value) is None:
        raise ReleaseSemanticEvidenceError("repository must be exactly owner/name")
    return value


def _require_text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ReleaseSemanticEvidenceError(f"{field} must be non-empty NUL-free text")
    return value.strip()


def _require_sha256(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ReleaseSemanticEvidenceError(f"{field} must be exactly 64 lowercase hex characters")
    return value


def _require_git_sha(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _GIT_SHA.fullmatch(value) is None:
        raise ReleaseSemanticEvidenceError(f"{field} must be exactly 40 lowercase hex characters")
    return value


def _require_positive_int(value: object, *, field: str) -> int:
    if type(value) is not int or value <= 0:
        raise ReleaseSemanticEvidenceError(f"{field} must be a positive int")
    return value


__all__ = [
    "ReleaseBoundEvidenceDocument",
    "ReleaseEvidenceKind",
    "ReleaseSemanticEvidenceBundle",
    "ReleaseSemanticEvidenceError",
    "TrainingExecutionEvidence",
]
