"""Deterministic fixture-only mutation policy for MRL-0202.

This module enforces the exact mutation envelope frozen by one canonical
ResearchExperimentPlan. It performs no filesystem writes, patch application, subprocess
execution, network access, model/data access, GPU work, training, promotion, deployment,
release, or clinical action.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_experiment_plan_v1 import (
    ResearchExperimentPlan,
    ResearchExperimentPlanError,
)

__all__ = [
    "FixtureMutationDisposition",
    "FixtureMutationPolicy",
    "FixtureMutationPolicyError",
    "assess_fixture_mutation_path",
    "build_fixture_mutation_policy",
    "require_fixture_mutation_allowed",
]

_ID: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")

# These repository surfaces confer or define authority and are never campaign-mutable.
# The plan's own allow-list is narrower still; this permanent set is defense in depth.
_PROTECTED_AUTHORITY_SURFACES: Final[tuple[str, ...]] = (
    ".github",
    "CAPABILITY_MATRIX.json",
    "PROJECT_STATE.json",
    "RESEARCH_PROGRAM_INDEX.json",
    "SECURITY.md",
    "collaboration/reviewers",
    "data",
    "docs/adr",
    "docs/research/research_program_registry.md",
    "specs",
    "src",
)


class FixtureMutationPolicyError(ValueError):
    """Fail-closed validation error for the MRL fixture mutation policy."""


class FixtureMutationDisposition(enum.Enum):
    """Non-authoritative result of checking one proposed fixture mutation path."""

    ALLOW = "ALLOW"
    REJECT_OUTSIDE_ALLOW_LIST = "REJECT_OUTSIDE_ALLOW_LIST"
    REJECT_PROTECTED_AUTHORITY = "REJECT_PROTECTED_AUTHORITY"


@dataclass(frozen=True, slots=True)
class FixtureMutationPolicy:
    """Content-addressed policy bound to one exact ResearchExperimentPlan."""

    policy_id: str
    experiment_plan_sha256: str
    allowed_surfaces: tuple[str, ...]
    forbidden_surfaces: tuple[str, ...]
    protected_authority_surfaces: tuple[str, ...]
    fixture_only: bool = True
    non_evidence: bool = True

    def __post_init__(self) -> None:
        _validate_policy(self)

    def _validated_snapshot(self) -> FixtureMutationPolicy:
        _require_exact_type(self, FixtureMutationPolicy, "fixture_mutation_policy")
        return FixtureMutationPolicy(
            policy_id=self.policy_id,
            experiment_plan_sha256=self.experiment_plan_sha256,
            allowed_surfaces=self.allowed_surfaces,
            forbidden_surfaces=self.forbidden_surfaces,
            protected_authority_surfaces=self.protected_authority_surfaces,
            fixture_only=self.fixture_only,
            non_evidence=self.non_evidence,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-FIXTURE-MUTATION-POLICY-V1",
            "policy_id": self.policy_id,
            "experiment_plan_sha256": self.experiment_plan_sha256,
            "allowed_surfaces": list(self.allowed_surfaces),
            "forbidden_surfaces": list(self.forbidden_surfaces),
            "protected_authority_surfaces": list(
                self.protected_authority_surfaces
            ),
            "fixture_only": self.fixture_only,
            "non_evidence": self.non_evidence,
            "can_apply_mutation": False,
            "can_authorize_real_execution": False,
            "can_authorize_training": False,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        _require_exact_type(self, FixtureMutationPolicy, "fixture_mutation_policy")
        snapshot = FixtureMutationPolicy._validated_snapshot(self)
        return snapshot._semantic_dict_validated()

    @property
    def semantic_bytes(self) -> bytes:
        _require_exact_type(self, FixtureMutationPolicy, "fixture_mutation_policy")
        return canonical_semantic_bytes(FixtureMutationPolicy.semantic_dict(self))

    @property
    def content_sha256(self) -> str:
        _require_exact_type(self, FixtureMutationPolicy, "fixture_mutation_policy")
        return derive_content_sha256(FixtureMutationPolicy.semantic_dict(self))

    def to_dict(self) -> dict[str, object]:
        _require_exact_type(self, FixtureMutationPolicy, "fixture_mutation_policy")
        data = FixtureMutationPolicy.semantic_dict(self)
        data["content_sha256"] = derive_content_sha256(data)
        return data


def build_fixture_mutation_policy(
    plan: ResearchExperimentPlan,
) -> FixtureMutationPolicy:
    """Derive the only valid fixture mutation policy from one exact frozen plan."""

    plan_snapshot = _snapshot_plan(plan)
    return FixtureMutationPolicy(
        policy_id=f"{plan_snapshot.experiment_plan_id}-mutation-policy",
        experiment_plan_sha256=plan_snapshot.content_sha256,
        allowed_surfaces=plan_snapshot.mutation_surfaces,
        forbidden_surfaces=plan_snapshot.objective.forbidden_mutation_surfaces,
        protected_authority_surfaces=_PROTECTED_AUTHORITY_SURFACES,
    )


def assess_fixture_mutation_path(
    plan: ResearchExperimentPlan,
    policy: FixtureMutationPolicy,
    path: str,
) -> FixtureMutationDisposition:
    """Check one canonical relative path without applying any mutation."""

    plan_snapshot = _snapshot_plan(plan)
    policy_snapshot = _snapshot_policy(policy)
    _require_policy_binds_plan(policy_snapshot, plan_snapshot)
    _require_canonical_relative_path(path, "path")

    if any(
        _paths_overlap(path, surface)
        for surface in policy_snapshot.protected_authority_surfaces
    ):
        return FixtureMutationDisposition.REJECT_PROTECTED_AUTHORITY

    if any(
        _paths_overlap(path, surface)
        for surface in policy_snapshot.forbidden_surfaces
    ):
        return FixtureMutationDisposition.REJECT_PROTECTED_AUTHORITY

    if any(
        _path_contains(surface, path)
        for surface in policy_snapshot.allowed_surfaces
    ):
        return FixtureMutationDisposition.ALLOW

    return FixtureMutationDisposition.REJECT_OUTSIDE_ALLOW_LIST


def require_fixture_mutation_allowed(
    plan: ResearchExperimentPlan,
    policy: FixtureMutationPolicy,
    path: str,
) -> None:
    """Fail closed unless one path is inside the exact frozen mutation envelope."""

    disposition = assess_fixture_mutation_path(plan, policy, path)
    if disposition is not FixtureMutationDisposition.ALLOW:
        raise FixtureMutationPolicyError(
            f"mutation path {path!r} rejected: {disposition.value}"
        )


def _validate_policy(policy: FixtureMutationPolicy) -> None:
    _require_id(policy.policy_id, "policy_id")
    _require_sha256(policy.experiment_plan_sha256, "experiment_plan_sha256")
    _require_true(policy.fixture_only, "fixture_only")
    _require_true(policy.non_evidence, "non_evidence")
    _require_paths(policy.allowed_surfaces, "allowed_surfaces", allow_empty=True)
    _require_paths(policy.forbidden_surfaces, "forbidden_surfaces", allow_empty=True)
    _require_paths(
        policy.protected_authority_surfaces,
        "protected_authority_surfaces",
    )
    if policy.protected_authority_surfaces != _PROTECTED_AUTHORITY_SURFACES:
        raise FixtureMutationPolicyError(
            "protected_authority_surfaces must exactly match the canonical policy"
        )
    for allowed in policy.allowed_surfaces:
        if any(
            _paths_overlap(allowed, protected)
            for protected in policy.protected_authority_surfaces
        ):
            raise FixtureMutationPolicyError(
                f"allowed surface {allowed!r} overlaps protected authority"
            )
        if any(
            _paths_overlap(allowed, forbidden)
            for forbidden in policy.forbidden_surfaces
        ):
            raise FixtureMutationPolicyError(
                f"allowed surface {allowed!r} overlaps a frozen forbidden surface"
            )


def _snapshot_plan(plan: ResearchExperimentPlan) -> ResearchExperimentPlan:
    _require_exact_type(plan, ResearchExperimentPlan, "research_experiment_plan")
    try:
        return ResearchExperimentPlan._validated_snapshot(plan)
    except ResearchExperimentPlanError as exc:
        raise FixtureMutationPolicyError(
            "research_experiment_plan failed canonical revalidation"
        ) from exc


def _snapshot_policy(policy: FixtureMutationPolicy) -> FixtureMutationPolicy:
    _require_exact_type(policy, FixtureMutationPolicy, "fixture_mutation_policy")
    return FixtureMutationPolicy._validated_snapshot(policy)


def _require_policy_binds_plan(
    policy: FixtureMutationPolicy,
    plan: ResearchExperimentPlan,
) -> None:
    if policy.experiment_plan_sha256 != plan.content_sha256:
        raise FixtureMutationPolicyError(
            "fixture mutation policy does not bind the supplied experiment plan"
        )
    if policy.allowed_surfaces != plan.mutation_surfaces:
        raise FixtureMutationPolicyError(
            "fixture mutation policy allow-list does not exactly match the plan"
        )
    if policy.forbidden_surfaces != plan.objective.forbidden_mutation_surfaces:
        raise FixtureMutationPolicyError(
            "fixture mutation policy forbidden surfaces do not exactly match the plan objective"
        )


def _require_paths(
    values: tuple[str, ...],
    label: str,
    *,
    allow_empty: bool = False,
) -> None:
    if type(values) is not tuple:
        raise FixtureMutationPolicyError(f"{label} must be an exact tuple")
    if not values and not allow_empty:
        raise FixtureMutationPolicyError(f"{label} cannot be empty")
    for value in values:
        _require_canonical_relative_path(value, label)
    if values != tuple(sorted(set(values))):
        raise FixtureMutationPolicyError(
            f"{label} must be unique and strictly sorted"
        )


def _require_canonical_relative_path(value: str, label: str) -> None:
    if type(value) is not str or not value:
        raise FixtureMutationPolicyError(f"{label} must be non-empty exact str")
    parts = value.split("/")
    if (
        value.startswith("/")
        or value.endswith("/")
        or "\x00" in value
        or "\\" in value
        or any(part in ("", ".", "..") for part in parts)
    ):
        raise FixtureMutationPolicyError(
            f"{label} contains non-canonical relative path {value!r}"
        )


def _path_contains(envelope: str, candidate: str) -> bool:
    return envelope == candidate or candidate.startswith(f"{envelope}/")


def _paths_overlap(left: str, right: str) -> bool:
    return _path_contains(left, right) or _path_contains(right, left)


def _require_id(value: str, label: str) -> None:
    if type(value) is not str or not _ID.fullmatch(value):
        raise FixtureMutationPolicyError(
            f"{label} must be lowercase kebab-case [a-z0-9-]"
        )


def _require_sha256(value: str, label: str) -> None:
    if type(value) is not str or not _SHA256.fullmatch(value):
        raise FixtureMutationPolicyError(
            f"{label} must be a lowercase 64-character SHA-256 digest"
        )


def _require_true(value: bool, label: str) -> None:
    if value is not True:
        raise FixtureMutationPolicyError(f"{label} must be exactly true")


def _require_exact_type(value: object, expected: type[object], label: str) -> None:
    if type(value) is not expected:
        raise FixtureMutationPolicyError(
            f"{label} must be exact {expected.__name__}"
        )
