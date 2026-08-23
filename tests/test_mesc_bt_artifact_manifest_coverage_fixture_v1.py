from __future__ import annotations

from threading import Event, Thread

import pytest

import medscale.mesc._bt_artifact_manifest_coverage_fixture_v1 as manifest_module
from medscale.mesc._bt_artifact_manifest_coverage_fixture_v1 import (
    ArtifactManifestCoverageEvidence,
    ArtifactManifestCoverageTypeError,
    ArtifactManifestCoverageValueError,
    verify_fixture_artifact_manifest_coverage,
)

_BINDING_FIELDS = (
    "mesc_commit_sha",
    "mesc_tree_sha",
    "candidate_revision",
    "model_revision",
    "processor_revision",
    "runtime_revision",
    "hardware_identity",
    "provider_identity",
    "access_evidence",
    "start_timestamp",
    "end_timestamp",
    "raw_per_item_artifact_hashes",
    "normalized_per_item_artifact_hashes",
)
_STATIC_DIGEST_BINDINGS = (
    "CORPUS_SPEC_SHA256=49f554d57e29da4b1d04223d43f1630731e5f8c9b72e7a1e15f959e38c00643b",
    "MATERIALIZED_CORPUS_SHA256=48fba9119f0170eb40775c75f12916e277cb3953abe22357e0b22497dadbbebd",
    "MATERIALIZED_CORPUS_GZIP_SHA256=667cd68e5ccc9356321eb5857c6e9203e1320ec33d866ccf514411c211ceb632",
    "CORPUS_MANIFEST_SHA256=201fa1351923a72097ff7e467b6dce2eb8bd0cfa1e88c73157788f77dd89e745",
    "SCORING_KEYS_SHA256=bb3524bc8dd1f05bad433c664ac3c48a5110939ac78b5ffa2ad8853f944c6318",
    "TASK_PROMPT_BUNDLE_SHA256=54d9da5cf3dad58c0bf9fb28761c15d8f82568013895b8467f1cb7d532c314b7",
    "SYSTEM_PROMPT_SHA256=02bb1a1fe70036c5d5299d6654618a2734aa03550506d1b023904cefc88ba867",
    "NORMALIZED_OUTPUT_SCHEMA_SHA256=3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4",
    "PARSER_CONTRACT_SHA256=9905096b491ddc3bce2b5d668c1f8726f638dde9dba383ac1bb755f1b6b42071",
    "REPORT_VALIDATION_CONTRACT_SHA256=c68fcac507e4ebc164632370d2392631b9fec9c388369eb5b8bfa495e5877c1a",
    "SCORING_CONTRACT_SHA256=a61471d467521b59eb62ee2825d23fa15891bb45a664360aaf2e4ef5882c7d40",
    "PROTOCOL_CONFIG_SHA256=097cdd11f5389203cf432760ec316a78b12d157c0676477de69dde707e058203",
    "PROMPT_PROTOCOL_SHA256=a2a42aef340e27f9396b40810999d5f2c4136af467ce27ee9e3c149e3257c89c",
    "REPORT_SCHEMA_SHA256=cb3fc506b41cc6236959bb4a89bce249db13c99aeb0c7178ff233f6de44e026d",
)
_CANDIDATE_KEYS = (
    "gpt_oss_20b",
    "apertus_1_5_8b",
    "phi_4_multimodal_instruct",
    "medgemma_1_5_4b_it",
)
_ITEM_IDS = tuple(f"BT-{axis}-{index:03d}" for axis in "ABCDEF" for index in range(1, 41))
_THREAD_SYNC_TIMEOUT_SECONDS = 30.0


def _evidence() -> ArtifactManifestCoverageEvidence:
    return ArtifactManifestCoverageEvidence(
        binding_fields=_BINDING_FIELDS,
        static_digest_bindings=_STATIC_DIGEST_BINDINGS,
        candidate_keys=_CANDIDATE_KEYS,
        item_ids=_ITEM_IDS,
        manifest_complete=True,
        no_floating_executable_identity=True,
        candidate_revisions_bound=True,
        model_processor_runtime_revisions_bound=True,
        hardware_provider_identity_bound=True,
        access_evidence_bound=True,
        timestamps_bound=True,
        raw_per_item_hashes_bound=True,
        normalized_per_item_hashes_bound=True,
        unbound_required_fields=0,
        unattributed_artifact_hashes=0,
    )


def test_valid_fixture_artifact_manifest_coverage_passes() -> None:
    verify_fixture_artifact_manifest_coverage(_evidence())


def test_outer_subclass_is_rejected() -> None:
    class EvidenceSubclass(ArtifactManifestCoverageEvidence):
        pass

    evidence = _evidence()
    forged = EvidenceSubclass(**{field: getattr(evidence, field) for field in evidence.__slots__})

    with pytest.raises(ArtifactManifestCoverageTypeError):
        verify_fixture_artifact_manifest_coverage(forged)


@pytest.mark.parametrize(
    "field",
    ["binding_fields", "static_digest_bindings", "candidate_keys", "item_ids"],
)
def test_tuple_fields_require_exact_tuple(field: str) -> None:
    forged = _evidence()
    object.__setattr__(forged, field, list(getattr(forged, field)))

    with pytest.raises(ArtifactManifestCoverageTypeError):
        verify_fixture_artifact_manifest_coverage(forged)


def test_tuple_members_require_exact_strings() -> None:
    class StringSubclass(str):
        pass

    forged = _evidence()
    object.__setattr__(
        forged,
        "binding_fields",
        (StringSubclass(_BINDING_FIELDS[0]), *_BINDING_FIELDS[1:]),
    )

    with pytest.raises(ArtifactManifestCoverageTypeError):
        verify_fixture_artifact_manifest_coverage(forged)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("binding_fields", _BINDING_FIELDS[:-1]),
        ("binding_fields", (*_BINDING_FIELDS, "extra")),
        ("static_digest_bindings", _STATIC_DIGEST_BINDINGS[:-1]),
        (
            "static_digest_bindings",
            ("CORPUS_SPEC_SHA256=" + "0" * 64, *_STATIC_DIGEST_BINDINGS[1:]),
        ),
        ("candidate_keys", (_CANDIDATE_KEYS[1], _CANDIDATE_KEYS[0], *_CANDIDATE_KEYS[2:])),
        ("item_ids", _ITEM_IDS[:-1]),
        ("item_ids", (*_ITEM_IDS, "BT-A-001")),
        ("item_ids", (_ITEM_IDS[1], _ITEM_IDS[0], *_ITEM_IDS[2:])),
    ],
)
def test_frozen_coverage_sequences_fail_closed(field: str, value: tuple[str, ...]) -> None:
    forged = _evidence()
    object.__setattr__(forged, field, value)

    with pytest.raises(ArtifactManifestCoverageValueError):
        verify_fixture_artifact_manifest_coverage(forged)


@pytest.mark.parametrize(
    "field",
    [
        "manifest_complete",
        "no_floating_executable_identity",
        "candidate_revisions_bound",
        "model_processor_runtime_revisions_bound",
        "hardware_provider_identity_bound",
        "access_evidence_bound",
        "timestamps_bound",
        "raw_per_item_hashes_bound",
        "normalized_per_item_hashes_bound",
    ],
)
@pytest.mark.parametrize("value", [False, 1])
def test_controls_require_exact_boolean_true(field: str, value: object) -> None:
    forged = _evidence()
    object.__setattr__(forged, field, value)

    with pytest.raises(ArtifactManifestCoverageValueError):
        verify_fixture_artifact_manifest_coverage(forged)


@pytest.mark.parametrize("field", ["unbound_required_fields", "unattributed_artifact_hashes"])
@pytest.mark.parametrize("value", [-1, 1, True])
def test_counters_require_exact_integer_zero(field: str, value: object) -> None:
    forged = _evidence()
    object.__setattr__(forged, field, value)

    with pytest.raises(ArtifactManifestCoverageValueError):
        verify_fixture_artifact_manifest_coverage(forged)


def test_post_snapshot_mutation_cannot_change_result(monkeypatch: pytest.MonkeyPatch) -> None:
    evidence = _evidence()
    snapshot_ready = Event()
    caller_mutated = Event()
    mutator_failures: list[str] = []
    original_validate_snapshot = manifest_module._validate_snapshot

    def synchronized_validate_snapshot(snapshot: ArtifactManifestCoverageEvidence) -> None:
        snapshot_ready.set()
        if not caller_mutated.wait(timeout=_THREAD_SYNC_TIMEOUT_SECONDS):
            raise AssertionError("timed out waiting for caller mutation")
        original_validate_snapshot(snapshot)

    monkeypatch.setattr(manifest_module, "_validate_snapshot", synchronized_validate_snapshot)

    def mutate_caller() -> None:
        if not snapshot_ready.wait(timeout=_THREAD_SYNC_TIMEOUT_SECONDS):
            mutator_failures.append("timed out waiting for snapshot")
        else:
            object.__setattr__(evidence, "binding_fields", _BINDING_FIELDS[:-1])
            object.__setattr__(evidence, "manifest_complete", False)
            caller_mutated.set()

    mutator = Thread(target=mutate_caller)
    mutator.start()
    try:
        verify_fixture_artifact_manifest_coverage(evidence)
    finally:
        mutator.join(timeout=_THREAD_SYNC_TIMEOUT_SECONDS)

    assert not mutator_failures
    assert caller_mutated.is_set()
    assert not mutator.is_alive()
