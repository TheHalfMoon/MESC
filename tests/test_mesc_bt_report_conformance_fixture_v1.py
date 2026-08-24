from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from typing import cast

import pytest

from medscale.mesc._bt_output_contract_pipeline_fixture_v1 import (
    OutputContractIdentityEvidence,
    OutputPipelineObservation,
)
from medscale.mesc._bt_report_conformance_fixture_v1 import (
    ActivationBindingFixture,
    CandidateTerminalDispositionFixture,
    CorpusAuditFixture,
    FailedItemFixture,
    ReportConformanceFixtureError,
    validate_fixture_output_pipeline_to_report,
    validate_report_conformance_fixture,
)
from medscale.mesc._bt_report_schema_fixture_v1 import (
    REPORT_SCHEMA_SHA256,
    ReportSchemaFixtureError,
    validate_report_schema_fixture,
)

_CANDIDATES = (
    (
        "openai/gpt-oss-20b",
        "6cee5e81ee83917806bbde320786a8fb61efebee",
    ),
    (
        "swiss-ai/Apertus-v1.5-8B",
        "a411d838600baf0e3635a3daf66fb7c55fc97bb6",
    ),
)
_ALL_ITEM_IDS = tuple(
    f"BT-{axis}-{index:03d}" for axis in "ABCDEF" for index in range(1, 41)
)


def _candidate_report(candidate_id: str, revision: str, score: str) -> dict[str, object]:
    value = Decimal(score)
    return {
        "candidate_id": candidate_id,
        "candidate_revision": revision,
        "items_attempted": 240,
        "items_completed": 240,
        "axis_scores": {
            "medical_reasoning": value,
            "evidence_fidelity": value,
            "uncertainty_abstention": value,
            "safety": value,
            "structured_fhir": value,
            "operational_reproducibility": value,
        },
        "aggregate_score": value,
        "critical_safety_failures": 0,
        "compact_gate": "PASS",
        "flagship_gate": "PASS",
        "errors": {
            "total": 0,
            "TIMEOUT": 0,
            "RUNTIME_FAILURE": 0,
            "GENERATION_FAILURE": 0,
            "PARSE_FAILURE": 0,
            "SCHEMA_FAILURE": 0,
            "SAFETY_FAILURE": 0,
        },
        "exclusions": [],
        "negative_results": [],
        "operational": {
            "median_latency_ms": Decimal("100"),
            "p95_latency_ms": Decimal("150"),
            "peak_vram_mb": Decimal("1000"),
            "input_tokens": 1000,
            "output_tokens": 200,
            "provider_cost": "N/A",
        },
    }


def _report() -> dict[str, object]:
    first = _candidate_report(*_CANDIDATES[0], "100.00")
    second = _candidate_report(*_CANDIDATES[1], "90.00")
    winner = _CANDIDATES[0][0]
    return {
        "schema_version": "MESC-BT-REPORT-V1",
        "mesc_commit_sha": "a" * 40,
        "mesc_tree_sha": "b" * 40,
        "protocol_id": "MESC-BT-PROTOCOL-V1",
        "protocol_config_sha256": (
            "097cdd11f5389203cf432760ec316a78b12d157c0676477de69dde707e058203"
        ),
        "prompt_bundle_sha256": (
            "54d9da5cf3dad58c0bf9fb28761c15d8f82568013895b8467f1cb7d532c314b7"
        ),
        "system_prompt_sha256": (
            "02bb1a1fe70036c5d5299d6654618a2734aa03550506d1b023904cefc88ba867"
        ),
        "prompt_protocol_sha256": (
            "a2a42aef340e27f9396b40810999d5f2c4136af467ce27ee9e3c149e3257c89c"
        ),
        "corpus_spec_sha256": (
            "49f554d57e29da4b1d04223d43f1630731e5f8c9b72e7a1e15f959e38c00643b"
        ),
        "materialized_corpus_sha256": (
            "48fba9119f0170eb40775c75f12916e277cb3953abe22357e0b22497dadbbebd"
        ),
        "materialized_corpus_gzip_sha256": (
            "667cd68e5ccc9356321eb5857c6e9203e1320ec33d866ccf514411c211ceb632"
        ),
        "materialized_corpus_item_count": 240,
        "corpus_manifest_sha256": (
            "201fa1351923a72097ff7e467b6dce2eb8bd0cfa1e88c73157788f77dd89e745"
        ),
        "scoring_keys_sha256": (
            "bb3524bc8dd1f05bad433c664ac3c48a5110939ac78b5ffa2ad8853f944c6318"
        ),
        "normalized_output_schema_sha256": (
            "3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4"
        ),
        "parser_contract_sha256": (
            "9905096b491ddc3bce2b5d668c1f8726f638dde9dba383ac1bb755f1b6b42071"
        ),
        "scoring_contract_sha256": (
            "a61471d467521b59eb62ee2825d23fa15891bb45a664360aaf2e4ef5882c7d40"
        ),
        "report_validation_contract_sha256": (
            "c68fcac507e4ebc164632370d2392631b9fec9c388369eb5b8bfa495e5877c1a"
        ),
        "report_schema_sha256": REPORT_SCHEMA_SHA256,
        "candidate_reports": [first, second],
        "role_results": {
            "compact": {
                "outcome": "WINNER",
                "candidate_id": winner,
                "reason": "TIE_BREAK_RESOLVED_WINNER",
                "tied_candidate_ids": [],
            },
            "flagship_reasoner": {
                "outcome": "WINNER",
                "candidate_id": winner,
                "reason": "TIE_BREAK_RESOLVED_WINNER",
                "tied_candidate_ids": [],
            },
        },
        "negative_results": [],
        "artifact_manifest_sha256": "c" * 64,
    }


def _activation() -> ActivationBindingFixture:
    return ActivationBindingFixture(
        mesc_commit_sha="a" * 40,
        mesc_tree_sha="b" * 40,
        protocol_config_sha256=(
            "097cdd11f5389203cf432760ec316a78b12d157c0676477de69dde707e058203"
        ),
        scoring_contract_sha256=(
            "a61471d467521b59eb62ee2825d23fa15891bb45a664360aaf2e4ef5882c7d40"
        ),
        report_schema_sha256=REPORT_SCHEMA_SHA256,
        artifact_manifest_sha256="c" * 64,
        admitted_candidate_pairs=_CANDIDATES,
        binding_evidence_passed=True,
    )


def _audits() -> CorpusAuditFixture:
    return CorpusAuditFixture(
        r2_provenance_audit_passed=True,
        spec_conformance_audit_passed=True,
        audit_artifacts_bound_before_prompt_serialization=True,
    )


def _dispositions() -> tuple[CandidateTerminalDispositionFixture, ...]:
    return tuple(
        CandidateTerminalDispositionFixture(
            candidate_id=candidate_id,
            completed_item_ids=_ALL_ITEM_IDS,
            failed_items=(),
        )
        for candidate_id, _ in _CANDIDATES
    )


def _pipeline_identity() -> OutputContractIdentityEvidence:
    return OutputContractIdentityEvidence(
        normalized_output_schema_sha256=(
            "3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4"
        ),
        parser_contract_sha256=(
            "9905096b491ddc3bce2b5d668c1f8726f638dde9dba383ac1bb755f1b6b42071"
        ),
        scoring_contract_sha256=(
            "a61471d467521b59eb62ee2825d23fa15891bb45a664360aaf2e4ef5882c7d40"
        ),
        report_validation_contract_sha256=(
            "c68fcac507e4ebc164632370d2392631b9fec9c388369eb5b8bfa495e5877c1a"
        ),
        report_schema_sha256=REPORT_SCHEMA_SHA256,
    )


def _pipeline_observation() -> OutputPipelineObservation:
    return OutputPipelineObservation(
        processing_order=(
            "parser",
            "normalized_schema_validator",
            "scorer",
            "report_validator",
        ),
        contract_identities_verified_before_processing=True,
        parser_completed_before_schema_validation=True,
        schema_validation_completed_before_scoring=True,
        scoring_completed_before_report_validation=True,
        semantic_repair_prohibited=True,
        parse_retry_attempts=0,
        schema_retry_attempts=0,
        semantic_retry_attempts=0,
        unattributed_processing_events=0,
    )


def test_schema_and_semantic_report_conformance_pass_for_frozen_fixture() -> None:
    report = _report()
    validate_report_schema_fixture(report)
    result = validate_report_conformance_fixture(
        report=report,
        activation=_activation(),
        corpus_audits=_audits(),
        terminal_dispositions=_dispositions(),
    )

    assert result.candidate_ids == tuple(candidate_id for candidate_id, _ in _CANDIDATES)
    assert result.compact.candidate_id == _CANDIDATES[0][0]
    assert result.flagship_reasoner.candidate_id == _CANDIDATES[0][0]


def test_pipeline_composition_validates_order_then_report() -> None:
    result = validate_fixture_output_pipeline_to_report(
        output_contract_identity=_pipeline_identity(),
        output_pipeline_observation=_pipeline_observation(),
        report=_report(),
        activation=_activation(),
        corpus_audits=_audits(),
        terminal_dispositions=_dispositions(),
    )
    assert result.compact.reason == "TIE_BREAK_RESOLVED_WINNER"


def test_schema_rejects_extra_key_float_and_noncanonical_item_id() -> None:
    extra = _report()
    extra["unexpected"] = True
    with pytest.raises(ReportSchemaFixtureError, match="exactly the frozen keys"):
        validate_report_schema_fixture(extra)

    floating = _report()
    candidate = cast(dict[str, object], cast(list[object], floating["candidate_reports"])[0])
    axes = cast(dict[str, object], candidate["axis_scores"])
    axes["safety"] = 100.0
    with pytest.raises(ReportSchemaFixtureError, match="int or Decimal"):
        validate_report_schema_fixture(floating)

    bad_item = _report()
    candidate = cast(dict[str, object], cast(list[object], bad_item["candidate_reports"])[0])
    candidate["negative_results"] = [
        {"category": "OTHER", "summary": "x", "item_id": "BT-A-041"}
    ]
    with pytest.raises(ReportSchemaFixtureError, match="invalid frozen format"):
        validate_report_schema_fixture(bad_item)


def test_schema_rejects_wrong_frozen_identity_and_invalid_role_variant() -> None:
    report = _report()
    report["scoring_contract_sha256"] = "d" * 64
    with pytest.raises(ReportSchemaFixtureError, match="frozen schema constant"):
        validate_report_schema_fixture(report)

    role = _report()
    roles = cast(dict[str, object], role["role_results"])
    compact = cast(dict[str, object], roles["compact"])
    compact["tied_candidate_ids"] = [_CANDIDATES[1][0]]
    with pytest.raises(ReportSchemaFixtureError, match="empty for WINNER"):
        validate_report_schema_fixture(role)


def test_conformance_rejects_unproven_activation_or_corpus_audit() -> None:
    activation = _activation()
    unproven = ActivationBindingFixture(
        mesc_commit_sha=activation.mesc_commit_sha,
        mesc_tree_sha=activation.mesc_tree_sha,
        protocol_config_sha256=activation.protocol_config_sha256,
        scoring_contract_sha256=activation.scoring_contract_sha256,
        report_schema_sha256=activation.report_schema_sha256,
        artifact_manifest_sha256=activation.artifact_manifest_sha256,
        admitted_candidate_pairs=activation.admitted_candidate_pairs,
        binding_evidence_passed=False,
    )
    with pytest.raises(ReportConformanceFixtureError, match="binding evidence"):
        validate_report_conformance_fixture(
            report=_report(),
            activation=unproven,
            corpus_audits=_audits(),
            terminal_dispositions=_dispositions(),
        )

    failed_audit = CorpusAuditFixture(
        r2_provenance_audit_passed=True,
        spec_conformance_audit_passed=False,
        audit_artifacts_bound_before_prompt_serialization=True,
    )
    with pytest.raises(ReportConformanceFixtureError, match="spec_conformance_audit_passed"):
        validate_report_conformance_fixture(
            report=_report(),
            activation=_activation(),
            corpus_audits=failed_audit,
            terminal_dispositions=_dispositions(),
        )


def test_conformance_rejects_unadmitted_pair_and_wrong_revision_mapping() -> None:
    activation = _activation()
    only_first = ActivationBindingFixture(
        mesc_commit_sha=activation.mesc_commit_sha,
        mesc_tree_sha=activation.mesc_tree_sha,
        protocol_config_sha256=activation.protocol_config_sha256,
        scoring_contract_sha256=activation.scoring_contract_sha256,
        report_schema_sha256=activation.report_schema_sha256,
        artifact_manifest_sha256=activation.artifact_manifest_sha256,
        admitted_candidate_pairs=(
            _CANDIDATES[0],
            (
                "microsoft/Phi-4-multimodal-instruct",
                "93f923e1a7727d1c4f446756212d9d3e8fcc5d81",
            ),
        ),
        binding_evidence_passed=True,
    )
    with pytest.raises(ReportConformanceFixtureError, match="not admitted"):
        validate_report_conformance_fixture(
            report=_report(),
            activation=only_first,
            corpus_audits=_audits(),
            terminal_dispositions=_dispositions(),
        )

    wrong_mapping = _report()
    candidates = cast(list[object], wrong_mapping["candidate_reports"])
    second = cast(dict[str, object], candidates[1])
    second["candidate_revision"] = _CANDIDATES[0][1]
    with pytest.raises(ReportConformanceFixtureError, match="not admitted"):
        validate_report_conformance_fixture(
            report=wrong_mapping,
            activation=_activation(),
            corpus_audits=_audits(),
            terminal_dispositions=_dispositions(),
        )


def test_accounting_and_exclusions_must_match_terminal_disposition_exactly() -> None:
    report = _report()
    candidates = cast(list[object], report["candidate_reports"])
    first = cast(dict[str, object], candidates[0])
    first["items_completed"] = 239
    errors = cast(dict[str, object], first["errors"])
    errors["total"] = 1
    errors["TIMEOUT"] = 1
    first["exclusions"] = [
        {"item_id": "BT-A-001", "reason": "fixture timeout", "error_class": "TIMEOUT"}
    ]
    first_disposition = CandidateTerminalDispositionFixture(
        candidate_id=_CANDIDATES[0][0],
        completed_item_ids=_ALL_ITEM_IDS[1:],
        failed_items=(FailedItemFixture(item_id="BT-A-001", error_class="TIMEOUT"),),
    )
    dispositions = (first_disposition, _dispositions()[1])
    validate_report_conformance_fixture(
        report=report,
        activation=_activation(),
        corpus_audits=_audits(),
        terminal_dispositions=dispositions,
    )

    wrong = deepcopy(report)
    wrong_first = cast(dict[str, object], cast(list[object], wrong["candidate_reports"])[0])
    wrong_first["exclusions"] = [
        {"item_id": "BT-A-002", "reason": "fixture timeout", "error_class": "TIMEOUT"}
    ]
    with pytest.raises(ReportConformanceFixtureError, match="exclusions must equal"):
        validate_report_conformance_fixture(
            report=wrong,
            activation=_activation(),
            corpus_audits=_audits(),
            terminal_dispositions=dispositions,
        )


def test_terminal_disposition_must_partition_all_240_canonical_items() -> None:
    dispositions = list(_dispositions())
    first = dispositions[0]
    dispositions[0] = CandidateTerminalDispositionFixture(
        candidate_id=first.candidate_id,
        completed_item_ids=first.completed_item_ids[:-1],
        failed_items=(),
    )
    with pytest.raises(ReportConformanceFixtureError, match="partition the exact canonical"):
        validate_report_conformance_fixture(
            report=_report(),
            activation=_activation(),
            corpus_audits=_audits(),
            terminal_dispositions=tuple(dispositions),
        )


def test_gate_and_role_results_are_recomputed_fail_closed() -> None:
    bad_gate = _report()
    first = cast(dict[str, object], cast(list[object], bad_gate["candidate_reports"])[0])
    first["flagship_gate"] = "FAIL"
    with pytest.raises(ReportConformanceFixtureError, match="scoring/gate recomputation"):
        validate_report_conformance_fixture(
            report=bad_gate,
            activation=_activation(),
            corpus_audits=_audits(),
            terminal_dispositions=_dispositions(),
        )

    bad_role = _report()
    roles = cast(dict[str, object], bad_role["role_results"])
    flagship = cast(dict[str, object], roles["flagship_reasoner"])
    flagship["candidate_id"] = _CANDIDATES[1][0]
    with pytest.raises(ReportConformanceFixtureError, match="candidate_id does not match"):
        validate_report_conformance_fixture(
            report=bad_role,
            activation=_activation(),
            corpus_audits=_audits(),
            terminal_dispositions=_dispositions(),
        )
