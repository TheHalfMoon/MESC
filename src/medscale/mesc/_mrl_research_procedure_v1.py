"""Immutable, content-addressed MRL V1 research procedure artifacts.

Research procedures record reusable research methods and their bounded applicability.
Admission is an independently reviewed lifecycle, not an authority granted by a campaign
or research agent. A procedure can bind the exact admission report that currently judges
it, while the report binds the procedure's pre-admission candidate identity. This breaks
the otherwise circular procedure/report hash dependency without weakening either binding.

These artifacts grant no filesystem, network, model, dataset, GPU, inference, training,
promotion, deployment, release, or clinical authority.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Final

from medscale.mesc._mrl_content_identity_v1 import (
    canonical_semantic_bytes,
    derive_content_sha256,
)
from medscale.mesc._mrl_research_objective_v1 import EvaluationTier

__all__ = [
    "ProcedureAdmissionDecision",
    "ProcedureAdmissionState",
    "ProcedureApplicabilityBounds",
    "ProcedureReportAuthorKind",
    "ResearchProcedure",
    "ResearchProcedureAdmissionReport",
    "ResearchProcedureError",
]

_ID: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")
_STATE_ORDER: Final = {
    "DISCOVERED": 0,
    "CANDIDATE": 1,
    "REPLAYED": 2,
    "TRANSFER_TESTED": 3,
    "REVIEWED": 4,
    "ADMITTED": 5,
}


class ResearchProcedureError(ValueError):
    """Fail-closed validation error for MRL research-procedure artifacts."""


class ProcedureAdmissionState(enum.Enum):
    """Closed admission lifecycle required by the MRL V1 specification."""

    DISCOVERED = "DISCOVERED"
    CANDIDATE = "CANDIDATE"
    REPLAYED = "REPLAYED"
    TRANSFER_TESTED = "TRANSFER_TESTED"
    REVIEWED = "REVIEWED"
    ADMITTED = "ADMITTED"


class ProcedureAdmissionDecision(enum.Enum):
    """Admission decisions that remain distinct from model-promotion authority."""

    CONTINUE = "CONTINUE"
    REJECT = "REJECT"
    ADMIT = "ADMIT"


class ProcedureReportAuthorKind(enum.Enum):
    """Identity class of the actor producing one admission-lifecycle report."""

    RESEARCH_AGENT = "RESEARCH_AGENT"
    CAMPAIGN_AGENT = "CAMPAIGN_AGENT"
    INDEPENDENT_REVIEWER = "INDEPENDENT_REVIEWER"
    OPERATOR = "OPERATOR"


@dataclass(frozen=True, slots=True)
class ProcedureApplicabilityBounds:
    """Typed applicability envelope for one reusable research procedure."""

    research_program_refs: tuple[str, ...]
    task_types: tuple[str, ...]
    model_classes: tuple[str, ...]
    data_classes: tuple[str, ...]
    evaluation_tiers: tuple[EvaluationTier, ...]
    constraints: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_sorted_texts(
            self.research_program_refs,
            "research_program_refs",
            required=True,
        )
        _require_sorted_texts(self.task_types, "task_types", required=True)
        _require_sorted_texts(self.model_classes, "model_classes", required=False)
        _require_sorted_texts(self.data_classes, "data_classes", required=False)
        _require_evaluation_tiers(self.evaluation_tiers)
        _require_sorted_texts(self.constraints, "constraints", required=False)

    def to_dict(self) -> dict[str, object]:
        """Return the canonical JSON-compatible applicability semantics."""
        return {
            "research_program_refs": list(self.research_program_refs),
            "task_types": list(self.task_types),
            "model_classes": list(self.model_classes),
            "data_classes": list(self.data_classes),
            "evaluation_tiers": [int(tier) for tier in self.evaluation_tiers],
            "constraints": list(self.constraints),
        }


@dataclass(frozen=True, slots=True)
class ResearchProcedureAdmissionReport:
    """One immutable state transition in the independent procedure-admission lifecycle."""

    procedure_sha256: str
    state: ProcedureAdmissionState
    applicability_bounds: ProcedureApplicabilityBounds
    replay_evidence_sha256s: tuple[str, ...]
    transfer_evidence_sha256s: tuple[str, ...]
    negative_control_evidence_sha256s: tuple[str, ...]
    author_kind: ProcedureReportAuthorKind
    author_id: str
    reviewer_authority_id: str | None
    review_receipt_sha256: str | None
    decision: ProcedureAdmissionDecision
    reason: str
    supersedes_procedure_sha256s: tuple[str, ...] = ()
    invalidates_procedure_sha256s: tuple[str, ...] = ()
    parent_report: ResearchProcedureAdmissionReport | None = field(
        default=None,
        repr=False,
    )

    def __post_init__(self) -> None:
        _validate_report(self)

    def _validated_snapshot(self) -> ResearchProcedureAdmissionReport:
        """Revalidate and rebuild the complete six-stage report chain before trust views."""
        _require_exact_report(self)
        chain = _collect_report_chain(self)
        _validate_report_chain(chain)
        parent: ResearchProcedureAdmissionReport | None = None
        for report in chain:
            parent = _rebuild_report_unchecked(report, parent)
        if parent is None:
            raise ResearchProcedureError("admission report chain cannot be empty")
        return parent

    def _semantic_dict_with_parent_sha256(
        self,
        parent_sha256: str | None,
    ) -> dict[str, object]:
        return {
            "format": "MRL-RESEARCH-PROCEDURE-ADMISSION-REPORT-V1",
            "procedure_sha256": self.procedure_sha256,
            "state": self.state.value,
            "applicability_bounds": self.applicability_bounds.to_dict(),
            "replay_evidence_sha256s": list(self.replay_evidence_sha256s),
            "transfer_evidence_sha256s": list(self.transfer_evidence_sha256s),
            "negative_control_evidence_sha256s": list(
                self.negative_control_evidence_sha256s
            ),
            "author_kind": self.author_kind.value,
            "author_id": self.author_id,
            "reviewer_authority_id": self.reviewer_authority_id,
            "review_receipt_sha256": self.review_receipt_sha256,
            "decision": self.decision.value,
            "reason": self.reason,
            "supersedes_procedure_sha256s": list(self.supersedes_procedure_sha256s),
            "invalidates_procedure_sha256s": list(self.invalidates_procedure_sha256s),
            "parent_report_sha256": parent_sha256,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return complete semantics from one freshly revalidated report chain."""
        snapshot = self._validated_snapshot()
        parent_sha256 = _derive_report_sha256_validated(snapshot.parent_report)
        return snapshot._semantic_dict_with_parent_sha256(parent_sha256)

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical UTF-8 semantic bytes without self-referential identity."""
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def content_sha256(self) -> str:
        """Derive the current report identity from the fully validated lifecycle chain."""
        snapshot = self._validated_snapshot()
        content_sha256 = _derive_report_sha256_validated(snapshot)
        if content_sha256 is None:
            raise ResearchProcedureError("admission report chain cannot be empty")
        return content_sha256

    def to_dict(self) -> dict[str, object]:
        """Return the semantic report envelope plus its derived content identity."""
        data = self.semantic_dict()
        data["content_sha256"] = derive_content_sha256(data)
        return data


@dataclass(frozen=True, slots=True)
class ResearchProcedure:
    """One immutable reusable research procedure and its current admission binding."""

    procedure_id: str
    version: int
    applicability_bounds: ProcedureApplicabilityBounds
    preconditions: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    forbidden_actions: tuple[str, ...]
    steps: tuple[str, ...]
    expected_artifacts: tuple[str, ...]
    verification_steps: tuple[str, ...]
    known_failure_modes: tuple[str, ...]
    source_campaign_sha256s: tuple[str, ...]
    admission_report_sha256: str | None = None
    admission_report: ResearchProcedureAdmissionReport | None = field(
        default=None,
        repr=False,
    )

    def __post_init__(self) -> None:
        _validate_procedure(self)

    def _validated_snapshot(self) -> ResearchProcedure:
        """Rebuild all reachable semantic and admission evidence before trust views."""
        _require_exact_procedure(self)
        report = None
        if self.admission_report is not None:
            report = self.admission_report._validated_snapshot()
        return ResearchProcedure(
            procedure_id=self.procedure_id,
            version=self.version,
            applicability_bounds=_rebuild_applicability(self.applicability_bounds),
            preconditions=self.preconditions,
            allowed_tools=self.allowed_tools,
            forbidden_actions=self.forbidden_actions,
            steps=self.steps,
            expected_artifacts=self.expected_artifacts,
            verification_steps=self.verification_steps,
            known_failure_modes=self.known_failure_modes,
            source_campaign_sha256s=self.source_campaign_sha256s,
            admission_report_sha256=self.admission_report_sha256,
            admission_report=report,
        )

    def _semantic_dict_with_report_sha256(
        self,
        report_sha256: str | None,
    ) -> dict[str, object]:
        return {
            "format": "MRL-RESEARCH-PROCEDURE-V1",
            "procedure_id": self.procedure_id,
            "version": self.version,
            "applicability_bounds": self.applicability_bounds.to_dict(),
            "preconditions": list(self.preconditions),
            "allowed_tools": list(self.allowed_tools),
            "forbidden_actions": list(self.forbidden_actions),
            "steps": list(self.steps),
            "expected_artifacts": list(self.expected_artifacts),
            "verification_steps": list(self.verification_steps),
            "known_failure_modes": list(self.known_failure_modes),
            "source_campaign_sha256s": list(self.source_campaign_sha256s),
            "admission_report_sha256": report_sha256,
            "can_authorize_model_promotion": False,
        }

    def semantic_dict(self) -> dict[str, object]:
        """Return canonical procedure semantics from one freshly revalidated snapshot."""
        snapshot = self._validated_snapshot()
        return snapshot._semantic_dict_with_report_sha256(
            snapshot.admission_report_sha256
        )

    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical UTF-8 procedure semantic bytes."""
        return canonical_semantic_bytes(self.semantic_dict())

    @property
    def admission_subject_sha256(self) -> str:
        """Return the cycle-safe pre-admission candidate procedure identity.

        This is the canonical procedure digest with ``admission_report_sha256=None``.
        Admission reports bind this identity; the final procedure then binds the report
        digest, so neither artifact needs its own future digest to compute its identity.
        """
        snapshot = self._validated_snapshot()
        payload = snapshot._semantic_dict_with_report_sha256(None)
        return derive_content_sha256(payload)

    @property
    def content_sha256(self) -> str:
        """Derive the complete procedure identity outside its semantic preimage."""
        return derive_content_sha256(self.semantic_dict())

    def to_dict(self) -> dict[str, object]:
        """Return semantic procedure envelope plus derived identities."""
        snapshot = self._validated_snapshot()
        data = snapshot._semantic_dict_with_report_sha256(
            snapshot.admission_report_sha256
        )
        data["admission_subject_sha256"] = derive_content_sha256(
            snapshot._semantic_dict_with_report_sha256(None)
        )
        data["content_sha256"] = derive_content_sha256(data_without_derived(data))
        return data


def data_without_derived(data: dict[str, object]) -> dict[str, object]:
    """Return procedure semantics without derived identities used only by ``to_dict``."""
    semantic = dict(data)
    semantic.pop("admission_subject_sha256", None)
    semantic.pop("content_sha256", None)
    return semantic


def _validate_procedure(procedure: ResearchProcedure) -> None:
    _require_id(procedure.procedure_id, "procedure_id")
    if type(procedure.version) is not int or procedure.version < 1:
        raise ResearchProcedureError("version must be an exact positive integer")
    if type(procedure.applicability_bounds) is not ProcedureApplicabilityBounds:
        raise ResearchProcedureError("applicability_bounds has an invalid type")
    applicability = _rebuild_applicability(procedure.applicability_bounds)
    _require_ordered_texts(procedure.preconditions, "preconditions", required=True)
    _require_sorted_texts(procedure.allowed_tools, "allowed_tools", required=True)
    _require_sorted_texts(
        procedure.forbidden_actions,
        "forbidden_actions",
        required=True,
    )
    if set(procedure.allowed_tools) & set(procedure.forbidden_actions):
        raise ResearchProcedureError("allowed_tools and forbidden_actions cannot overlap")
    _require_ordered_texts(procedure.steps, "steps", required=True)
    _require_sorted_texts(
        procedure.expected_artifacts,
        "expected_artifacts",
        required=True,
    )
    _require_ordered_texts(
        procedure.verification_steps,
        "verification_steps",
        required=True,
    )
    _require_sorted_texts(
        procedure.known_failure_modes,
        "known_failure_modes",
        required=True,
    )
    _require_sorted_sha256s(
        procedure.source_campaign_sha256s,
        "source_campaign_sha256s",
        required=True,
    )

    if procedure.admission_report_sha256 is None:
        if procedure.admission_report is not None:
            raise ResearchProcedureError(
                "admission_report requires admission_report_sha256"
            )
        return
    _require_sha256(procedure.admission_report_sha256, "admission_report_sha256")
    report = procedure.admission_report
    if type(report) is not ResearchProcedureAdmissionReport:
        raise ResearchProcedureError(
            "admission_report_sha256 requires an exact admission report object"
        )
    if report.content_sha256 != procedure.admission_report_sha256:
        raise ResearchProcedureError("admission report object does not match its SHA-256")
    subject_payload = procedure._semantic_dict_with_report_sha256(None)
    subject_payload["applicability_bounds"] = applicability.to_dict()
    subject_sha256 = derive_content_sha256(subject_payload)
    if report.procedure_sha256 != subject_sha256:
        raise ResearchProcedureError(
            "admission report does not bind the procedure admission subject"
        )
    if report.applicability_bounds.to_dict() != applicability.to_dict():
        raise ResearchProcedureError(
            "admission report applicability does not match the procedure"
        )


def _validate_report(report: ResearchProcedureAdmissionReport) -> None:
    chain = _collect_report_chain(report)
    _validate_report_chain(chain)


def _collect_report_chain(
    report: ResearchProcedureAdmissionReport,
) -> tuple[ResearchProcedureAdmissionReport, ...]:
    reverse_chain: list[ResearchProcedureAdmissionReport] = []
    seen: set[int] = set()
    current: ResearchProcedureAdmissionReport | None = report
    while current is not None:
        if type(current) is not ResearchProcedureAdmissionReport:
            raise ResearchProcedureError("admission report chain contains an invalid type")
        identity = id(current)
        if identity in seen:
            raise ResearchProcedureError("admission report chain cannot contain a cycle")
        seen.add(identity)
        reverse_chain.append(current)
        current = current.parent_report
    if len(reverse_chain) > len(_STATE_ORDER):
        raise ResearchProcedureError("admission report chain exceeds the lifecycle bound")
    return tuple(reversed(reverse_chain))


def _validate_report_chain(
    chain: tuple[ResearchProcedureAdmissionReport, ...],
) -> None:
    if not chain:
        raise ResearchProcedureError("admission report chain cannot be empty")
    parent: ResearchProcedureAdmissionReport | None = None
    for report in chain:
        _validate_report_local(report)
        if parent is None:
            if report.state is not ProcedureAdmissionState.DISCOVERED:
                raise ResearchProcedureError(
                    "admission lifecycle must begin at DISCOVERED"
                )
        else:
            _validate_report_transition(parent, report)
        parent = report


def _validate_report_local(report: ResearchProcedureAdmissionReport) -> None:
    _require_sha256(report.procedure_sha256, "procedure_sha256")
    _require_exact_enum(report.state, ProcedureAdmissionState, "state")
    if type(report.applicability_bounds) is not ProcedureApplicabilityBounds:
        raise ResearchProcedureError("report applicability_bounds has an invalid type")
    _ = _rebuild_applicability(report.applicability_bounds)
    _require_sorted_sha256s(
        report.replay_evidence_sha256s,
        "replay_evidence_sha256s",
        required=False,
    )
    _require_sorted_sha256s(
        report.transfer_evidence_sha256s,
        "transfer_evidence_sha256s",
        required=False,
    )
    _require_sorted_sha256s(
        report.negative_control_evidence_sha256s,
        "negative_control_evidence_sha256s",
        required=False,
    )
    _require_exact_enum(report.author_kind, ProcedureReportAuthorKind, "author_kind")
    _require_text(report.author_id, "author_id")
    _require_exact_enum(report.decision, ProcedureAdmissionDecision, "decision")
    _require_text(report.reason, "reason")
    _require_sorted_sha256s(
        report.supersedes_procedure_sha256s,
        "supersedes_procedure_sha256s",
        required=False,
    )
    _require_sorted_sha256s(
        report.invalidates_procedure_sha256s,
        "invalidates_procedure_sha256s",
        required=False,
    )

    ordinal = _STATE_ORDER[report.state.value]
    if ordinal >= _STATE_ORDER[ProcedureAdmissionState.REPLAYED.value]:
        if not report.replay_evidence_sha256s:
            raise ResearchProcedureError("REPLAYED or later requires replay evidence")
    if ordinal >= _STATE_ORDER[ProcedureAdmissionState.TRANSFER_TESTED.value]:
        if not report.transfer_evidence_sha256s:
            raise ResearchProcedureError(
                "TRANSFER_TESTED or later requires representative transfer evidence"
            )
    if ordinal >= _STATE_ORDER[ProcedureAdmissionState.REVIEWED.value]:
        _require_review_authority(report)
        if not report.negative_control_evidence_sha256s:
            raise ResearchProcedureError(
                "REVIEWED or ADMITTED requires negative-control evidence"
            )
    else:
        if report.reviewer_authority_id is not None:
            raise ResearchProcedureError(
                "pre-REVIEWED reports cannot claim reviewer authority"
            )
        if report.review_receipt_sha256 is not None:
            raise ResearchProcedureError(
                "pre-REVIEWED reports cannot claim an immutable review receipt"
            )
        if report.decision is not ProcedureAdmissionDecision.CONTINUE:
            raise ResearchProcedureError(
                "pre-REVIEWED admission reports must use CONTINUE"
            )

    if report.state is ProcedureAdmissionState.REVIEWED:
        if report.decision not in (
            ProcedureAdmissionDecision.REJECT,
            ProcedureAdmissionDecision.ADMIT,
        ):
            raise ResearchProcedureError("REVIEWED report must decide REJECT or ADMIT")
    if report.state is ProcedureAdmissionState.ADMITTED:
        if report.decision is not ProcedureAdmissionDecision.ADMIT:
            raise ResearchProcedureError("ADMITTED report must decide ADMIT")


def _require_review_authority(report: ResearchProcedureAdmissionReport) -> None:
    if report.author_kind not in (
        ProcedureReportAuthorKind.INDEPENDENT_REVIEWER,
        ProcedureReportAuthorKind.OPERATOR,
    ):
        raise ResearchProcedureError(
            "research/campaign agents cannot produce REVIEWED or ADMITTED reports"
        )
    reviewer_id = report.reviewer_authority_id
    if reviewer_id is None:
        raise ResearchProcedureError(
            "REVIEWED or ADMITTED requires reviewer/operator authority identity"
        )
    _require_text(reviewer_id, "reviewer_authority_id")
    review_receipt = report.review_receipt_sha256
    if review_receipt is None:
        raise ResearchProcedureError(
            "REVIEWED or ADMITTED requires an immutable review receipt"
        )
    _require_sha256(review_receipt, "review_receipt_sha256")


def _validate_report_transition(
    parent: ResearchProcedureAdmissionReport,
    report: ResearchProcedureAdmissionReport,
) -> None:
    if report.parent_report is not parent:
        raise ResearchProcedureError("admission report parent identity is inconsistent")
    expected_ordinal = _STATE_ORDER[parent.state.value] + 1
    if _STATE_ORDER[report.state.value] != expected_ordinal:
        raise ResearchProcedureError("admission lifecycle cannot skip or repeat stages")
    if report.procedure_sha256 != parent.procedure_sha256:
        raise ResearchProcedureError("admission report chain changed procedure identity")
    if report.applicability_bounds.to_dict() != parent.applicability_bounds.to_dict():
        raise ResearchProcedureError("admission report chain changed applicability bounds")
    _require_append_only_hashes(
        parent.replay_evidence_sha256s,
        report.replay_evidence_sha256s,
        "replay evidence",
    )
    _require_append_only_hashes(
        parent.transfer_evidence_sha256s,
        report.transfer_evidence_sha256s,
        "transfer evidence",
    )
    _require_append_only_hashes(
        parent.negative_control_evidence_sha256s,
        report.negative_control_evidence_sha256s,
        "negative-control evidence",
    )
    if report.state is ProcedureAdmissionState.ADMITTED:
        if parent.state is not ProcedureAdmissionState.REVIEWED:
            raise ResearchProcedureError("ADMITTED requires an exact REVIEWED parent")
        if parent.decision is not ProcedureAdmissionDecision.ADMIT:
            raise ResearchProcedureError(
                "ADMITTED requires the REVIEWED parent to decide ADMIT"
            )
        if report.reviewer_authority_id != parent.reviewer_authority_id:
            raise ResearchProcedureError("ADMITTED cannot rewrite reviewer authority")
        if report.review_receipt_sha256 != parent.review_receipt_sha256:
            raise ResearchProcedureError("ADMITTED cannot rewrite the review receipt")


def _require_append_only_hashes(
    previous: tuple[str, ...],
    current: tuple[str, ...],
    label: str,
) -> None:
    if not set(previous).issubset(current):
        raise ResearchProcedureError(f"admission lifecycle cannot delete prior {label}")


def _rebuild_report_unchecked(
    report: ResearchProcedureAdmissionReport,
    parent: ResearchProcedureAdmissionReport | None,
) -> ResearchProcedureAdmissionReport:
    snapshot = object.__new__(ResearchProcedureAdmissionReport)
    object.__setattr__(snapshot, "procedure_sha256", report.procedure_sha256)
    object.__setattr__(snapshot, "state", report.state)
    object.__setattr__(
        snapshot,
        "applicability_bounds",
        _rebuild_applicability(report.applicability_bounds),
    )
    object.__setattr__(
        snapshot,
        "replay_evidence_sha256s",
        report.replay_evidence_sha256s,
    )
    object.__setattr__(
        snapshot,
        "transfer_evidence_sha256s",
        report.transfer_evidence_sha256s,
    )
    object.__setattr__(
        snapshot,
        "negative_control_evidence_sha256s",
        report.negative_control_evidence_sha256s,
    )
    object.__setattr__(snapshot, "author_kind", report.author_kind)
    object.__setattr__(snapshot, "author_id", report.author_id)
    object.__setattr__(
        snapshot,
        "reviewer_authority_id",
        report.reviewer_authority_id,
    )
    object.__setattr__(
        snapshot,
        "review_receipt_sha256",
        report.review_receipt_sha256,
    )
    object.__setattr__(snapshot, "decision", report.decision)
    object.__setattr__(snapshot, "reason", report.reason)
    object.__setattr__(
        snapshot,
        "supersedes_procedure_sha256s",
        report.supersedes_procedure_sha256s,
    )
    object.__setattr__(
        snapshot,
        "invalidates_procedure_sha256s",
        report.invalidates_procedure_sha256s,
    )
    object.__setattr__(snapshot, "parent_report", parent)
    return snapshot


def _derive_report_sha256_validated(
    report: ResearchProcedureAdmissionReport | None,
) -> str | None:
    if report is None:
        return None
    parent_sha256: str | None = None
    for current in _collect_report_chain(report):
        payload = current._semantic_dict_with_parent_sha256(parent_sha256)
        parent_sha256 = derive_content_sha256(payload)
    return parent_sha256


def _rebuild_applicability(
    bounds: ProcedureApplicabilityBounds,
) -> ProcedureApplicabilityBounds:
    if type(bounds) is not ProcedureApplicabilityBounds:
        raise ResearchProcedureError("applicability bounds have an invalid type")
    return ProcedureApplicabilityBounds(
        research_program_refs=bounds.research_program_refs,
        task_types=bounds.task_types,
        model_classes=bounds.model_classes,
        data_classes=bounds.data_classes,
        evaluation_tiers=bounds.evaluation_tiers,
        constraints=bounds.constraints,
    )


def _require_exact_report(value: ResearchProcedureAdmissionReport) -> None:
    if type(value) is not ResearchProcedureAdmissionReport:
        raise ResearchProcedureError(
            "admission semantic views require an exact ResearchProcedureAdmissionReport"
        )


def _require_exact_procedure(value: ResearchProcedure) -> None:
    if type(value) is not ResearchProcedure:
        raise ResearchProcedureError(
            "procedure semantic views require an exact ResearchProcedure instance"
        )


def _require_evaluation_tiers(values: tuple[EvaluationTier, ...]) -> None:
    if type(values) is not tuple or not values:
        raise ResearchProcedureError("evaluation_tiers must be a non-empty exact tuple")
    if any(type(value) is not EvaluationTier for value in values):
        raise ResearchProcedureError("evaluation_tiers contain invalid enum types")
    tier_values = tuple(int(value) for value in values)
    if tier_values != tuple(sorted(set(tier_values))):
        raise ResearchProcedureError(
            "evaluation_tiers must be unique and strictly sorted"
        )


def _require_sorted_texts(
    values: tuple[str, ...],
    label: str,
    *,
    required: bool,
) -> None:
    if type(values) is not tuple:
        raise ResearchProcedureError(f"{label} must be an exact tuple")
    if required and not values:
        raise ResearchProcedureError(f"{label} cannot be empty")
    for value in values:
        _require_text(value, label)
    if values != tuple(sorted(set(values))):
        raise ResearchProcedureError(f"{label} must be unique and strictly sorted")


def _require_ordered_texts(
    values: tuple[str, ...],
    label: str,
    *,
    required: bool,
) -> None:
    if type(values) is not tuple:
        raise ResearchProcedureError(f"{label} must be an exact tuple")
    if required and not values:
        raise ResearchProcedureError(f"{label} cannot be empty")
    for value in values:
        _require_text(value, label)
    if len(values) != len(set(values)):
        raise ResearchProcedureError(f"{label} cannot contain duplicate entries")


def _require_sorted_sha256s(
    values: tuple[str, ...],
    label: str,
    *,
    required: bool,
) -> None:
    if type(values) is not tuple:
        raise ResearchProcedureError(f"{label} must be an exact tuple")
    if required and not values:
        raise ResearchProcedureError(f"{label} cannot be empty")
    for value in values:
        _require_sha256(value, label)
    if values != tuple(sorted(set(values))):
        raise ResearchProcedureError(f"{label} must be unique and strictly sorted")


def _require_id(value: str, label: str) -> None:
    _require_text(value, label)
    if not _ID.fullmatch(value):
        raise ResearchProcedureError(f"{label} must use lowercase kebab-case semantics")


def _require_sha256(value: str, label: str) -> None:
    _require_text(value, label)
    if not _SHA256.fullmatch(value):
        raise ResearchProcedureError(f"{label} must be 64 lowercase hex")


def _require_text(value: str, label: str) -> None:
    if type(value) is not str:
        raise ResearchProcedureError(f"{label} must be an exact string")
    if not value or value != value.strip() or any(char in value for char in "\x00\r\n\t"):
        raise ResearchProcedureError(f"{label} must be non-empty canonical text")


def _require_exact_enum(value: object, enum_type: type[enum.Enum], label: str) -> None:
    if type(value) is not enum_type:
        raise ResearchProcedureError(f"{label} has an invalid enum type")
