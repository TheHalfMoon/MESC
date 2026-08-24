"""Semantic report conformance and pipeline composition for tournament fixtures.

All evidence is caller supplied and in memory. This module validates the frozen
``MESC-BT-REPORT-VALIDATION-V1`` invariants, recomputes gates and role results
through the canonical fixture scoring engine, and composes that result with the
already-canonical output-pipeline observation verifier. It does not read a real
report, corpus, scoring key, activation package, provider, model, or execution
artifact and does not grant execution authority.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal, cast

from medscale.mesc._bt_output_contract_pipeline_fixture_v1 import (
    OutputContractIdentityEvidence,
    OutputPipelineObservation,
    verify_fixture_output_contract_pipeline,
)
from medscale.mesc._bt_report_schema_fixture_v1 import (
    REPORT_SCHEMA_SHA256,
    validate_report_schema_fixture,
)
from medscale.mesc._bt_tournament_scoring_engine_fixture_v1 import (
    AxisScores,
    CandidateGateResult,
    CandidateSelectionFixture,
    RoleSelectionResult,
    select_role_fixture,
    validate_candidate_selection_fixture,
)

TerminalErrorClass = Literal[
    "TIMEOUT",
    "RUNTIME_FAILURE",
    "GENERATION_FAILURE",
    "PARSE_FAILURE",
    "SCHEMA_FAILURE",
    "SAFETY_FAILURE",
]

REPORT_VALIDATION_CONTRACT_VERSION: Final = "MESC-BT-REPORT-VALIDATION-V1"
REPORT_VALIDATION_CONTRACT_SHA256: Final = (
    "c68fcac507e4ebc164632370d2392631b9fec9c388369eb5b8bfa495e5877c1a"
)
SCORING_CONTRACT_SHA256: Final = "a61471d467521b59eb62ee2825d23fa15891bb45a664360aaf2e4ef5882c7d40"
PROTOCOL_CONFIG_SHA256: Final = "097cdd11f5389203cf432760ec316a78b12d157c0676477de69dde707e058203"

_CANONICAL_CANDIDATE_REVISIONS: Final[dict[str, str]] = {
    "openai/gpt-oss-20b": "6cee5e81ee83917806bbde320786a8fb61efebee",
    "swiss-ai/Apertus-v1.5-8B": "a411d838600baf0e3635a3daf66fb7c55fc97bb6",
    "microsoft/Phi-4-multimodal-instruct": "93f923e1a7727d1c4f446756212d9d3e8fcc5d81",
    "google/medgemma-1.5-4b-it": "91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b",
}
_ERROR_CLASSES: Final[tuple[TerminalErrorClass, ...]] = (
    "TIMEOUT",
    "RUNTIME_FAILURE",
    "GENERATION_FAILURE",
    "PARSE_FAILURE",
    "SCHEMA_FAILURE",
    "SAFETY_FAILURE",
)
_CANONICAL_ITEM_IDS: Final = frozenset(
    f"BT-{axis}-{index:03d}" for axis in "ABCDEF" for index in range(1, 41)
)


class ReportConformanceFixtureError(ValueError):
    """Semantic fixture evidence violates the frozen report-validation contract."""


@dataclass(frozen=True, slots=True)
class ActivationBindingFixture:
    """Injected fixture view of the execution package bindings, not real authority."""

    mesc_commit_sha: str
    mesc_tree_sha: str
    protocol_config_sha256: str
    scoring_contract_sha256: str
    report_schema_sha256: str
    artifact_manifest_sha256: str
    admitted_candidate_pairs: tuple[tuple[str, str], ...]
    binding_evidence_passed: bool


@dataclass(frozen=True, slots=True)
class CorpusAuditFixture:
    """Injected PASS facts for the two pre-execution corpus audits."""

    r2_provenance_audit_passed: bool
    spec_conformance_audit_passed: bool
    audit_artifacts_bound_before_prompt_serialization: bool


@dataclass(frozen=True, slots=True)
class FailedItemFixture:
    """One injected canonical terminal failed-item disposition."""

    item_id: str
    error_class: TerminalErrorClass


@dataclass(frozen=True, slots=True)
class CandidateTerminalDispositionFixture:
    """Injected terminal item partition for one candidate fixture."""

    candidate_id: str
    completed_item_ids: tuple[str, ...]
    failed_items: tuple[FailedItemFixture, ...]


@dataclass(frozen=True, slots=True)
class ReportConformanceResult:
    """Recomputed role outcomes after full fixture report conformance validation."""

    candidate_ids: tuple[str, ...]
    compact: RoleSelectionResult
    flagship_reasoner: RoleSelectionResult


def validate_report_conformance_fixture(
    *,
    report: dict[str, object],
    activation: ActivationBindingFixture,
    corpus_audits: CorpusAuditFixture,
    terminal_dispositions: tuple[CandidateTerminalDispositionFixture, ...],
) -> ReportConformanceResult:
    """Validate all deterministic report-contract invariants available to fixtures."""
    validate_report_schema_fixture(report)
    root = report
    activation_snapshot = _validate_activation_fixture(activation)
    _validate_corpus_audit_fixture(corpus_audits)

    _require_report_binding(root, "mesc_commit_sha", activation_snapshot.mesc_commit_sha)
    _require_report_binding(root, "mesc_tree_sha", activation_snapshot.mesc_tree_sha)
    _require_report_binding(
        root,
        "protocol_config_sha256",
        activation_snapshot.protocol_config_sha256,
    )
    _require_report_binding(
        root,
        "scoring_contract_sha256",
        activation_snapshot.scoring_contract_sha256,
    )
    _require_report_binding(
        root,
        "report_schema_sha256",
        activation_snapshot.report_schema_sha256,
    )
    _require_report_binding(
        root,
        "artifact_manifest_sha256",
        activation_snapshot.artifact_manifest_sha256,
    )

    candidate_objects = cast(list[object], root["candidate_reports"])
    candidates = tuple(cast(dict[str, object], item) for item in candidate_objects)
    candidate_ids = tuple(cast(str, candidate["candidate_id"]) for candidate in candidates)
    if len(set(candidate_ids)) != len(candidate_ids):
        raise ReportConformanceFixtureError("candidate_reports candidate IDs must be unique")

    report_pairs = tuple(
        (cast(str, candidate["candidate_id"]), cast(str, candidate["candidate_revision"]))
        for candidate in candidates
    )
    admitted = frozenset(activation_snapshot.admitted_candidate_pairs)
    if not set(report_pairs).issubset(admitted):
        raise ReportConformanceFixtureError(
            "candidate report pair is not admitted by the injected activation fixture"
        )

    dispositions = _validate_terminal_dispositions(terminal_dispositions, candidate_ids)
    selection_candidates: list[CandidateSelectionFixture] = []
    for candidate in candidates:
        candidate_id = cast(str, candidate["candidate_id"])
        _validate_accounting(candidate, dispositions[candidate_id])
        selection_candidates.append(_candidate_selection_from_report(candidate))

    candidate_tuple = tuple(selection_candidates)
    compact = select_role_fixture(candidate_tuple, role="compact")
    flagship = select_role_fixture(candidate_tuple, role="flagship_reasoner")
    role_results = cast(dict[str, object], root["role_results"])
    _require_role_result_matches(
        cast(dict[str, object], role_results["compact"]),
        compact,
        path="$.role_results.compact",
    )
    _require_role_result_matches(
        cast(dict[str, object], role_results["flagship_reasoner"]),
        flagship,
        path="$.role_results.flagship_reasoner",
    )

    return ReportConformanceResult(
        candidate_ids=candidate_ids,
        compact=compact,
        flagship_reasoner=flagship,
    )


def validate_fixture_output_pipeline_to_report(
    *,
    output_contract_identity: OutputContractIdentityEvidence,
    output_pipeline_observation: OutputPipelineObservation,
    report: dict[str, object],
    activation: ActivationBindingFixture,
    corpus_audits: CorpusAuditFixture,
    terminal_dispositions: tuple[CandidateTerminalDispositionFixture, ...],
) -> ReportConformanceResult:
    """Compose canonical parser->schema->scorer->report-validator fixture evidence."""
    verify_fixture_output_contract_pipeline(
        output_contract_identity,
        output_pipeline_observation,
    )
    return validate_report_conformance_fixture(
        report=report,
        activation=activation,
        corpus_audits=corpus_audits,
        terminal_dispositions=terminal_dispositions,
    )


def _validate_activation_fixture(value: ActivationBindingFixture) -> ActivationBindingFixture:
    if type(value) is not ActivationBindingFixture:
        raise ReportConformanceFixtureError("activation must be exact ActivationBindingFixture")
    if type(value.binding_evidence_passed) is not bool or value.binding_evidence_passed is not True:
        raise ReportConformanceFixtureError(
            "activation fixture binding evidence must be exact true"
        )

    string_fields = (
        ("mesc_commit_sha", value.mesc_commit_sha, 40),
        ("mesc_tree_sha", value.mesc_tree_sha, 40),
        ("protocol_config_sha256", value.protocol_config_sha256, 64),
        ("scoring_contract_sha256", value.scoring_contract_sha256, 64),
        ("report_schema_sha256", value.report_schema_sha256, 64),
        ("artifact_manifest_sha256", value.artifact_manifest_sha256, 64),
    )
    for name, field, length in string_fields:
        _require_lower_hex(field, length=length, field=name)
    if value.protocol_config_sha256 != PROTOCOL_CONFIG_SHA256:
        raise ReportConformanceFixtureError("activation protocol-config identity is not frozen")
    if value.scoring_contract_sha256 != SCORING_CONTRACT_SHA256:
        raise ReportConformanceFixtureError("activation scoring-contract identity is not frozen")
    if value.report_schema_sha256 != REPORT_SCHEMA_SHA256:
        raise ReportConformanceFixtureError("activation report-schema identity is not frozen")

    pairs = value.admitted_candidate_pairs
    if type(pairs) is not tuple or not 2 <= len(pairs) <= 4:
        raise ReportConformanceFixtureError(
            "activation admitted_candidate_pairs must contain 2..4 pairs"
        )
    snapshot_pairs: list[tuple[str, str]] = []
    for pair in pairs:
        if type(pair) is not tuple or len(pair) != 2:
            raise ReportConformanceFixtureError(
                "activation candidate pair must be an exact 2-tuple"
            )
        candidate_id, revision = pair
        if type(candidate_id) is not str or type(revision) is not str:
            raise ReportConformanceFixtureError(
                "activation candidate pair members must be exact strings"
            )
        if _CANONICAL_CANDIDATE_REVISIONS.get(candidate_id) != revision:
            raise ReportConformanceFixtureError(
                "activation candidate pair is not in the frozen roster"
            )
        snapshot_pairs.append((candidate_id, revision))
    if len(set(snapshot_pairs)) != len(snapshot_pairs):
        raise ReportConformanceFixtureError("activation candidate pairs must be unique")

    return ActivationBindingFixture(
        mesc_commit_sha=value.mesc_commit_sha,
        mesc_tree_sha=value.mesc_tree_sha,
        protocol_config_sha256=value.protocol_config_sha256,
        scoring_contract_sha256=value.scoring_contract_sha256,
        report_schema_sha256=value.report_schema_sha256,
        artifact_manifest_sha256=value.artifact_manifest_sha256,
        admitted_candidate_pairs=tuple(snapshot_pairs),
        binding_evidence_passed=True,
    )


def _validate_corpus_audit_fixture(value: CorpusAuditFixture) -> None:
    if type(value) is not CorpusAuditFixture:
        raise ReportConformanceFixtureError("corpus_audits must be exact CorpusAuditFixture")
    controls = (
        ("r2_provenance_audit_passed", value.r2_provenance_audit_passed),
        ("spec_conformance_audit_passed", value.spec_conformance_audit_passed),
        (
            "audit_artifacts_bound_before_prompt_serialization",
            value.audit_artifacts_bound_before_prompt_serialization,
        ),
    )
    for name, control in controls:
        if type(control) is not bool or control is not True:
            raise ReportConformanceFixtureError(f"corpus audit fixture {name} must be exact true")


def _validate_terminal_dispositions(
    values: tuple[CandidateTerminalDispositionFixture, ...],
    candidate_ids: tuple[str, ...],
) -> dict[str, CandidateTerminalDispositionFixture]:
    if type(values) is not tuple or len(values) != len(candidate_ids):
        raise ReportConformanceFixtureError(
            "terminal_dispositions must be an exact tuple matching candidate count"
        )

    snapshots: dict[str, CandidateTerminalDispositionFixture] = {}
    for value in values:
        if type(value) is not CandidateTerminalDispositionFixture:
            raise ReportConformanceFixtureError(
                "terminal disposition must be exact CandidateTerminalDispositionFixture"
            )
        candidate_id = value.candidate_id
        if type(candidate_id) is not str or candidate_id not in candidate_ids:
            raise ReportConformanceFixtureError("terminal disposition candidate is not reported")
        if candidate_id in snapshots:
            raise ReportConformanceFixtureError("terminal disposition candidates must be unique")
        if type(value.completed_item_ids) is not tuple or type(value.failed_items) is not tuple:
            raise ReportConformanceFixtureError("terminal item collections must be exact tuples")

        completed: list[str] = []
        for item_id in value.completed_item_ids:
            _require_canonical_item_id(item_id, field="completed_item_ids")
            completed.append(item_id)
        if len(set(completed)) != len(completed):
            raise ReportConformanceFixtureError("completed item IDs must be unique")

        failed: list[FailedItemFixture] = []
        failed_ids: list[str] = []
        for failed_item in value.failed_items:
            if type(failed_item) is not FailedItemFixture:
                raise ReportConformanceFixtureError("failed item must be exact FailedItemFixture")
            _require_canonical_item_id(failed_item.item_id, field="failed_items.item_id")
            if (
                type(failed_item.error_class) is not str
                or failed_item.error_class not in _ERROR_CLASSES
            ):
                raise ReportConformanceFixtureError("failed item error_class is not frozen")
            failed.append(
                FailedItemFixture(
                    item_id=failed_item.item_id,
                    error_class=failed_item.error_class,
                )
            )
            failed_ids.append(failed_item.item_id)
        if len(set(failed_ids)) != len(failed_ids):
            raise ReportConformanceFixtureError("failed item IDs must be unique")
        if set(completed) & set(failed_ids):
            raise ReportConformanceFixtureError("completed and failed item IDs must be disjoint")
        if set(completed) | set(failed_ids) != _CANONICAL_ITEM_IDS:
            raise ReportConformanceFixtureError(
                "terminal disposition must partition the exact canonical 240-item ID set"
            )

        snapshots[candidate_id] = CandidateTerminalDispositionFixture(
            candidate_id=candidate_id,
            completed_item_ids=tuple(completed),
            failed_items=tuple(failed),
        )

    if set(snapshots) != set(candidate_ids):
        raise ReportConformanceFixtureError("terminal disposition candidate set must equal reports")
    return snapshots


def _validate_accounting(
    candidate: dict[str, object],
    disposition: CandidateTerminalDispositionFixture,
) -> None:
    candidate_id = cast(str, candidate["candidate_id"])
    errors = cast(dict[str, object], candidate["errors"])
    total = cast(int, errors["total"])
    class_sum = sum(cast(int, errors[name]) for name in _ERROR_CLASSES)
    if total != class_sum:
        raise ReportConformanceFixtureError(f"{candidate_id}: errors.total must equal typed sum")
    completed = cast(int, candidate["items_completed"])
    if completed + total != 240:
        raise ReportConformanceFixtureError(
            f"{candidate_id}: items_completed + errors.total must equal 240"
        )
    if completed != len(disposition.completed_item_ids):
        raise ReportConformanceFixtureError(
            f"{candidate_id}: items_completed does not match terminal disposition"
        )
    if total != len(disposition.failed_items):
        raise ReportConformanceFixtureError(
            f"{candidate_id}: errors.total does not match terminal disposition"
        )

    exclusions = cast(list[object], candidate["exclusions"])
    if len(exclusions) != total:
        raise ReportConformanceFixtureError(
            f"{candidate_id}: exclusion count must equal errors.total"
        )
    exclusion_by_id: dict[str, str] = {}
    for raw in exclusions:
        exclusion = cast(dict[str, object], raw)
        item_id = cast(str, exclusion["item_id"])
        error_class = cast(str, exclusion["error_class"])
        if item_id in exclusion_by_id:
            raise ReportConformanceFixtureError(
                f"{candidate_id}: exclusion item IDs must be unique"
            )
        exclusion_by_id[item_id] = error_class

    expected_by_id = {item.item_id: item.error_class for item in disposition.failed_items}
    if exclusion_by_id != expected_by_id:
        raise ReportConformanceFixtureError(
            f"{candidate_id}: exclusions must equal canonical failed item IDs/classes"
        )
    if set(exclusion_by_id) & set(disposition.completed_item_ids):
        raise ReportConformanceFixtureError(
            f"{candidate_id}: completed item must not appear in exclusions"
        )

    expected_counts = Counter(item.error_class for item in disposition.failed_items)
    for error_class in _ERROR_CLASSES:
        if cast(int, errors[error_class]) != expected_counts[error_class]:
            raise ReportConformanceFixtureError(
                f"{candidate_id}: {error_class} count does not match exclusions"
            )


def _candidate_selection_from_report(candidate: dict[str, object]) -> CandidateSelectionFixture:
    axes = cast(dict[str, object], candidate["axis_scores"])
    operational = cast(dict[str, object], candidate["operational"])
    scores = AxisScores(
        medical_reasoning=_decimal(axes["medical_reasoning"]),
        evidence_fidelity=_decimal(axes["evidence_fidelity"]),
        uncertainty_abstention=_decimal(axes["uncertainty_abstention"]),
        safety=_decimal(axes["safety"]),
        structured_fhir=_decimal(axes["structured_fhir"]),
        operational_reproducibility=_decimal(axes["operational_reproducibility"]),
    )
    fixture = CandidateSelectionFixture(
        candidate_id=cast(str, candidate["candidate_id"]),
        candidate_revision=cast(str, candidate["candidate_revision"]),
        axis_scores=scores,
        aggregate_score=_decimal(candidate["aggregate_score"]),
        critical_safety_failures=cast(int, candidate["critical_safety_failures"]),
        gates=CandidateGateResult(
            compact=cast(Literal["PASS", "FAIL"], candidate["compact_gate"]),
            flagship_reasoner=cast(Literal["PASS", "FAIL"], candidate["flagship_gate"]),
        ),
        peak_vram_mb=_decimal(operational["peak_vram_mb"]),
        median_latency_ms=_decimal(operational["median_latency_ms"]),
    )
    try:
        return validate_candidate_selection_fixture(fixture)
    except ValueError as error:
        raise ReportConformanceFixtureError(
            f"candidate scoring/gate recomputation failed: {error}"
        ) from error


def _require_role_result_matches(
    reported: dict[str, object],
    expected: RoleSelectionResult,
    *,
    path: str,
) -> None:
    if reported["outcome"] != expected.outcome:
        raise ReportConformanceFixtureError(f"{path}.outcome does not match recomputation")
    if reported["candidate_id"] != expected.candidate_id:
        raise ReportConformanceFixtureError(f"{path}.candidate_id does not match recomputation")
    if reported["reason"] != expected.reason:
        raise ReportConformanceFixtureError(f"{path}.reason does not match recomputation")
    reported_tied = cast(list[object], reported["tied_candidate_ids"])
    tied_ids = tuple(cast(str, item) for item in reported_tied)
    if expected.reason == "EXACT_TIE_AFTER_ALL_FROZEN_TIE_BREAKERS":
        if set(tied_ids) != set(expected.tied_candidate_ids) or len(tied_ids) != len(
            expected.tied_candidate_ids
        ):
            raise ReportConformanceFixtureError(
                f"{path}.tied_candidate_ids does not contain the exact recomputed tie set"
            )
    elif tied_ids:
        raise ReportConformanceFixtureError(f"{path}.tied_candidate_ids must be empty")


def _require_report_binding(report: dict[str, object], field: str, expected: str) -> None:
    if report[field] != expected or type(report[field]) is not str:
        raise ReportConformanceFixtureError(f"$.{field} does not match activation binding")


def _require_lower_hex(value: object, *, length: int, field: str) -> str:
    if type(value) is not str:
        raise ReportConformanceFixtureError(f"{field} must be an exact string")
    text = value
    if len(text) != length or any(character not in "0123456789abcdef" for character in text):
        raise ReportConformanceFixtureError(f"{field} must be lowercase hexadecimal")
    return text


def _require_canonical_item_id(value: object, *, field: str) -> str:
    if type(value) is not str or value not in _CANONICAL_ITEM_IDS:
        raise ReportConformanceFixtureError(f"{field} must belong to canonical 240-item ID set")
    return value


def _decimal(value: object) -> Decimal:
    if type(value) is Decimal:
        return value
    if type(value) is int:
        return Decimal(value)
    raise ReportConformanceFixtureError("normalized report number must be exact int or Decimal")
