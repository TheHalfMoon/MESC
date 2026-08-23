"""Fail-closed fixture validation for Backbone Tournament manifest coverage evidence.

This module validates only caller-supplied fixture declarations. It does not read,
hash, create, or persist tournament artifacts and grants no execution authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

_REQUIRED_BINDING_FIELDS: Final = (
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
_REQUIRED_STATIC_DIGEST_BINDINGS: Final = (
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
_CANONICAL_CANDIDATE_KEYS: Final = (
    "gpt_oss_20b",
    "apertus_1_5_8b",
    "phi_4_multimodal_instruct",
    "medgemma_1_5_4b_it",
)
_CANONICAL_ITEM_IDS: Final = tuple(
    f"BT-{axis}-{index:03d}" for axis in "ABCDEF" for index in range(1, 41)
)


class ArtifactManifestCoverageError(ValueError):
    """Base class for fixture manifest-coverage violations."""


class ArtifactManifestCoverageTypeError(ArtifactManifestCoverageError):
    """Fixture manifest-coverage evidence has an invalid exact type."""


class ArtifactManifestCoverageValueError(ArtifactManifestCoverageError):
    """Fixture manifest-coverage evidence does not match the frozen contract."""


@dataclass(frozen=True, slots=True)
class ArtifactManifestCoverageEvidence:
    """Injected declaration of required future manifest binding coverage."""

    binding_fields: tuple[str, ...]
    static_digest_bindings: tuple[str, ...]
    candidate_keys: tuple[str, ...]
    item_ids: tuple[str, ...]
    manifest_complete: bool
    no_floating_executable_identity: bool
    candidate_revisions_bound: bool
    model_processor_runtime_revisions_bound: bool
    hardware_provider_identity_bound: bool
    access_evidence_bound: bool
    timestamps_bound: bool
    raw_per_item_hashes_bound: bool
    normalized_per_item_hashes_bound: bool
    unbound_required_fields: int
    unattributed_artifact_hashes: int


def verify_fixture_artifact_manifest_coverage(evidence: ArtifactManifestCoverageEvidence) -> None:
    """Verify a caller-supplied fixture manifest coverage declaration fail closed."""
    snapshot = _snapshot(evidence)
    _validate_snapshot(snapshot)


def _snapshot(evidence: ArtifactManifestCoverageEvidence) -> ArtifactManifestCoverageEvidence:
    if type(evidence) is not ArtifactManifestCoverageEvidence:
        raise ArtifactManifestCoverageTypeError("manifest coverage evidence has invalid type")

    binding_fields = evidence.binding_fields
    static_digest_bindings = evidence.static_digest_bindings
    candidate_keys = evidence.candidate_keys
    item_ids = evidence.item_ids
    if type(binding_fields) is not tuple:
        raise ArtifactManifestCoverageTypeError("binding_fields must be an exact tuple")
    if type(static_digest_bindings) is not tuple:
        raise ArtifactManifestCoverageTypeError("static_digest_bindings must be an exact tuple")
    if type(candidate_keys) is not tuple:
        raise ArtifactManifestCoverageTypeError("candidate_keys must be an exact tuple")
    if type(item_ids) is not tuple:
        raise ArtifactManifestCoverageTypeError("item_ids must be an exact tuple")

    return ArtifactManifestCoverageEvidence(
        binding_fields=binding_fields,
        static_digest_bindings=static_digest_bindings,
        candidate_keys=candidate_keys,
        item_ids=item_ids,
        manifest_complete=evidence.manifest_complete,
        no_floating_executable_identity=evidence.no_floating_executable_identity,
        candidate_revisions_bound=evidence.candidate_revisions_bound,
        model_processor_runtime_revisions_bound=evidence.model_processor_runtime_revisions_bound,
        hardware_provider_identity_bound=evidence.hardware_provider_identity_bound,
        access_evidence_bound=evidence.access_evidence_bound,
        timestamps_bound=evidence.timestamps_bound,
        raw_per_item_hashes_bound=evidence.raw_per_item_hashes_bound,
        normalized_per_item_hashes_bound=evidence.normalized_per_item_hashes_bound,
        unbound_required_fields=evidence.unbound_required_fields,
        unattributed_artifact_hashes=evidence.unattributed_artifact_hashes,
    )


def _validate_snapshot(evidence: ArtifactManifestCoverageEvidence) -> None:
    tuple_fields = (
        ("binding_fields", evidence.binding_fields, _REQUIRED_BINDING_FIELDS),
        (
            "static_digest_bindings",
            evidence.static_digest_bindings,
            _REQUIRED_STATIC_DIGEST_BINDINGS,
        ),
        ("candidate_keys", evidence.candidate_keys, _CANONICAL_CANDIDATE_KEYS),
        ("item_ids", evidence.item_ids, _CANONICAL_ITEM_IDS),
    )
    for name, value, expected in tuple_fields:
        if any(type(member) is not str for member in value):
            raise ArtifactManifestCoverageTypeError(f"{name} members must be exact strings")
        if value != expected:
            raise ArtifactManifestCoverageValueError(f"{name} does not match frozen coverage")

    controls = (
        ("manifest_complete", evidence.manifest_complete),
        ("no_floating_executable_identity", evidence.no_floating_executable_identity),
        ("candidate_revisions_bound", evidence.candidate_revisions_bound),
        (
            "model_processor_runtime_revisions_bound",
            evidence.model_processor_runtime_revisions_bound,
        ),
        ("hardware_provider_identity_bound", evidence.hardware_provider_identity_bound),
        ("access_evidence_bound", evidence.access_evidence_bound),
        ("timestamps_bound", evidence.timestamps_bound),
        ("raw_per_item_hashes_bound", evidence.raw_per_item_hashes_bound),
        ("normalized_per_item_hashes_bound", evidence.normalized_per_item_hashes_bound),
    )
    for name, value in controls:
        if type(value) is not bool or value is not True:
            raise ArtifactManifestCoverageValueError(
                f"manifest coverage control {name} must be exact boolean true"
            )

    counters = (
        ("unbound_required_fields", evidence.unbound_required_fields),
        ("unattributed_artifact_hashes", evidence.unattributed_artifact_hashes),
    )
    for name, value in counters:
        if type(value) is not int or value != 0:
            raise ArtifactManifestCoverageValueError(
                f"manifest coverage counter {name} must be exact integer zero"
            )
