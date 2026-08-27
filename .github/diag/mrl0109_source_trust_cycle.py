from pathlib import Path

TRUST_SOURCE = '''"""Repository-controlled trust roots for MRL research-input source permissions.

A source permission is not trusted merely because a caller can construct valid semantics.
Its exact content digest must also be provisioned by a separate canonical repository change.
The production registry intentionally starts empty, so this module alone grants no research
input, model, dataset, network, training, promotion, deployment, or clinical authority.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from threading import Lock
from typing import Final

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

TRUST_REGISTRY_VERSION: Final = "MRL-RESEARCH-INPUT-SOURCE-PERMISSION-TRUST-V1"
TRUSTED_RESEARCH_INPUT_SOURCE_PERMISSION_SHA256: frozenset[str] = frozenset()

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_REGISTRY_KIND: Final = "mesc.mrl.research_input_source_permission.trust_registry.v1"
_REGISTRY_LOCK: Final = Lock()


class ResearchInputPermissionTrustError(RuntimeError):
    """Raised when canonical research-input source-permission trust is invalid."""


@dataclass(frozen=True, slots=True)
class ResearchInputPermissionTrustSnapshot:
    """One validated immutable view of the canonical source-permission registry."""

    registry_version: str
    trusted_source_permission_sha256: frozenset[str]
    registry_sha256: str

    def admits(self, value: str) -> bool:
        """Return whether this exact snapshot admits one source-permission digest."""
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            return False
        return value in self.trusted_source_permission_sha256


def research_input_permission_trust_snapshot() -> ResearchInputPermissionTrustSnapshot:
    """Capture one validated immutable registry snapshot under the registry lock."""
    with _REGISTRY_LOCK:
        return _validated_registry_snapshot_unlocked()


def validate_research_input_source_permission_trust(
    permission_sha256: str,
) -> ResearchInputPermissionTrustSnapshot:
    """Require one exact source-permission digest in the current canonical registry."""
    if type(permission_sha256) is not str or _SHA256.fullmatch(permission_sha256) is None:
        raise ResearchInputPermissionTrustError(
            "source permission identity must be 64 lowercase hex characters"
        )
    snapshot = research_input_permission_trust_snapshot()
    if not snapshot.admits(permission_sha256):
        raise ResearchInputPermissionTrustError(
            "source permission is not trusted by the canonical registry"
        )
    return snapshot


def _validated_registry_snapshot_unlocked() -> ResearchInputPermissionTrustSnapshot:
    registry = TRUSTED_RESEARCH_INPUT_SOURCE_PERMISSION_SHA256
    if type(registry) is not frozenset:
        raise ResearchInputPermissionTrustError(
            "research-input source-permission trust registry must be an exact frozenset"
        )
    for value in registry:
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            raise ResearchInputPermissionTrustError(
                "research-input source-permission trust entries must be 64 lowercase hex characters"
            )
    payload = {
        "kind": _REGISTRY_KIND,
        "registry_version": TRUST_REGISTRY_VERSION,
        "trusted_source_permission_sha256": sorted(registry),
    }
    registry_sha256 = hashlib.sha256(canonical_json_bytes(payload)).hexdigest()
    return ResearchInputPermissionTrustSnapshot(
        registry_version=TRUST_REGISTRY_VERSION,
        trusted_source_permission_sha256=registry,
        registry_sha256=registry_sha256,
    )


def _replace_research_input_permission_trust_registry_for_tests(
    registry: frozenset[str],
) -> frozenset[str]:
    """Replace the test registry under the same lock used for production snapshots."""
    if type(registry) is not frozenset:
        raise TypeError("test source-permission trust registry must be an exact frozenset")
    for value in registry:
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            raise ValueError(
                "test source-permission trust entries must be 64 lowercase hex characters"
            )
    with _REGISTRY_LOCK:
        previous = TRUSTED_RESEARCH_INPUT_SOURCE_PERMISSION_SHA256
        globals()["TRUSTED_RESEARCH_INPUT_SOURCE_PERMISSION_SHA256"] = registry
        return previous


__all__ = [
    "TRUST_REGISTRY_VERSION",
    "ResearchInputPermissionTrustError",
    "ResearchInputPermissionTrustSnapshot",
    "research_input_permission_trust_snapshot",
    "validate_research_input_source_permission_trust",
]
'''

PERMISSION_CLASS = '''

@dataclass(frozen=True, slots=True)
class ResearchInputSourcePermission:
    """Trusted-by-digest permission for one exact potentially admissible source."""

    permission_id: str
    source_artifact_sha256: str
    classification: ResearchInputClassification
    allowed_learning_surfaces: tuple[ResearchLearningSurface, ...]

    def __post_init__(self) -> None:
        _require_token(self.permission_id, "permission_id")
        _require_sha256(self.source_artifact_sha256, "source_artifact_sha256")
        _require_exact_enum(self.classification, ResearchInputClassification, "classification")
        _require_learning_surfaces(self.allowed_learning_surfaces)
        disposition = _disposition_for_classification(self.classification)
        if disposition is ResearchInputDisposition.REJECTED:
            raise ResearchInputAdmissionError(
                "source permissions cannot authorize a rejected classification"
            )
        if disposition is ResearchInputDisposition.LEARNING_ADMITTED:
            if not self.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "learning source permission requires at least one learning surface"
                )
        elif self.allowed_learning_surfaces:
            raise ResearchInputAdmissionError(
                "external-evaluation source permission cannot grant learning surfaces"
            )

    def _validated_snapshot(self) -> ResearchInputSourcePermission:
        _require_exact_source_permission(self)
        return ResearchInputSourcePermission(
            permission_id=self.permission_id,
            source_artifact_sha256=self.source_artifact_sha256,
            classification=self.classification,
            allowed_learning_surfaces=self.allowed_learning_surfaces,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-RESEARCH-INPUT-SOURCE-PERMISSION-V1",
            "permission_id": self.permission_id,
            "source_artifact_sha256": self.source_artifact_sha256,
            "classification": self.classification.value,
            "allowed_learning_surfaces": [
                surface.value for surface in self.allowed_learning_surfaces
            ],
        }

    @property
    def content_sha256(self) -> str:
        _require_exact_source_permission(self)
        snapshot = self._validated_snapshot()
        return derive_content_sha256(snapshot._semantic_dict_validated())

    def to_dict(self) -> dict[str, object]:
        _require_exact_source_permission(self)
        snapshot = self._validated_snapshot()
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data
'''

OLD_POST = '''        _require_learning_surfaces(self.allowed_learning_surfaces)
        _require_parent_refs(self.parent_inputs)
        _require_transformation_lineage(self.transformation_kind, self.parent_inputs)

        disposition = _disposition_for_classification(self.classification)
        if disposition is ResearchInputDisposition.LEARNING_ADMITTED:
            if self.source_artifact_sha256 is None or self.source_contract_sha256 is None:
                raise ResearchInputAdmissionError(
                    "learning-admitted input requires exact source artifact and contract identities"
                )
            if not self.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "learning-admitted input requires at least one explicit learning surface"
                )
        elif disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY:
            if self.source_artifact_sha256 is None or self.source_contract_sha256 is None:
                raise ResearchInputAdmissionError(
                    "external evaluation evidence requires exact artifact and "
                    "governing contract identities"
                )
            if self.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "external evaluation evidence cannot enter an MRL learning surface"
                )
        else:
            if self.source_artifact_sha256 is not None or self.source_contract_sha256 is not None:
                raise ResearchInputAdmissionError(
                    "rejected input cannot carry source artifact or contract identities into MRL"
                )
            if self.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "rejected input cannot enter an MRL learning surface"
                )

        _require_no_lineage_laundering(disposition, self.parent_inputs)
'''

NEW_POST = '''        _require_learning_surfaces(self.allowed_learning_surfaces)
        try:
            _require_parent_refs(self.parent_inputs)
            _require_transformation_lineage(self.transformation_kind, self.parent_inputs)

            disposition = _disposition_for_classification(self.classification)
            if disposition is ResearchInputDisposition.LEARNING_ADMITTED:
                if self.source_artifact_sha256 is None or self.source_contract_sha256 is None:
                    raise ResearchInputAdmissionError(
                        "learning-admitted input requires exact source artifact and contract identities"
                    )
                if not self.allowed_learning_surfaces:
                    raise ResearchInputAdmissionError(
                        "learning-admitted input requires at least one explicit learning surface"
                    )
                _require_source_permission_binding(self)
            elif disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY:
                if self.source_artifact_sha256 is None or self.source_contract_sha256 is None:
                    raise ResearchInputAdmissionError(
                        "external evaluation evidence requires exact artifact and "
                        "governing contract identities"
                    )
                if self.allowed_learning_surfaces:
                    raise ResearchInputAdmissionError(
                        "external evaluation evidence cannot enter an MRL learning surface"
                    )
                _require_source_permission_binding(self)
            else:
                if self.source_permission is not None:
                    raise ResearchInputAdmissionError(
                        "rejected input cannot carry a source permission into MRL"
                    )
                if self.source_artifact_sha256 is not None or self.source_contract_sha256 is not None:
                    raise ResearchInputAdmissionError(
                        "rejected input cannot carry source artifact or contract identities into MRL"
                    )
                if self.allowed_learning_surfaces:
                    raise ResearchInputAdmissionError(
                        "rejected input cannot enter an MRL learning surface"
                    )

            _require_no_lineage_laundering(disposition, self.parent_inputs)
        except RecursionError as exc:
            raise ResearchInputAdmissionError(
                "cyclic research-input parent lineage is forbidden"
            ) from exc
'''

OLD_SNAPSHOT = '''    def _validated_snapshot(self) -> ResearchInputAdmissionContract:
        _require_exact_admission(self)
        _require_parent_refs(self.parent_inputs)
        parents = tuple(parent._validated_snapshot() for parent in self.parent_inputs)
        return ResearchInputAdmissionContract(
            input_id=self.input_id,
            classification_policy_sha256=self.classification_policy_sha256,
            classification=self.classification,
            source_artifact_sha256=self.source_artifact_sha256,
            source_contract_sha256=self.source_contract_sha256,
            allowed_learning_surfaces=self.allowed_learning_surfaces,
            transformation_kind=self.transformation_kind,
            parent_inputs=parents,
        )
'''

NEW_SNAPSHOT = '''    def _validated_snapshot(self) -> ResearchInputAdmissionContract:
        _require_exact_admission(self)
        try:
            _require_parent_refs(self.parent_inputs)
            parents = tuple(parent._validated_snapshot() for parent in self.parent_inputs)
            permission = (
                self.source_permission._validated_snapshot()
                if self.source_permission is not None
                else None
            )
            return ResearchInputAdmissionContract(
                input_id=self.input_id,
                classification_policy_sha256=self.classification_policy_sha256,
                classification=self.classification,
                source_artifact_sha256=self.source_artifact_sha256,
                source_contract_sha256=self.source_contract_sha256,
                allowed_learning_surfaces=self.allowed_learning_surfaces,
                source_permission=permission,
                transformation_kind=self.transformation_kind,
                parent_inputs=parents,
            )
        except RecursionError as exc:
            raise ResearchInputAdmissionError(
                "cyclic research-input parent lineage is forbidden"
            ) from exc
'''

SOURCE_BINDING = '''

def _require_source_permission_binding(contract: ResearchInputAdmissionContract) -> None:
    permission = contract.source_permission
    if type(permission) is not ResearchInputSourcePermission:
        raise ResearchInputAdmissionError(
            "admissible input requires an exact ResearchInputSourcePermission"
        )
    snapshot = permission._validated_snapshot()
    permission_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
    if contract.classification_policy_sha256 != permission_sha256:
        raise ResearchInputAdmissionError(
            "classification_policy_sha256 must bind the exact source permission"
        )
    if contract.source_contract_sha256 != permission_sha256:
        raise ResearchInputAdmissionError(
            "source_contract_sha256 must bind the exact source permission"
        )
    if contract.source_artifact_sha256 != snapshot.source_artifact_sha256:
        raise ResearchInputAdmissionError(
            "source permission does not bind the admitted source artifact"
        )
    if contract.classification is not snapshot.classification:
        raise ResearchInputAdmissionError(
            "source permission does not authorize the admitted classification"
        )
    if contract.allowed_learning_surfaces != snapshot.allowed_learning_surfaces:
        raise ResearchInputAdmissionError(
            "source permission does not authorize the requested learning surfaces"
        )
    try:
        permission_trust.validate_research_input_source_permission_trust(permission_sha256)
    except permission_trust.ResearchInputPermissionTrustError as exc:
        raise ResearchInputAdmissionError(
            "source permission is not trusted by canonical research-input governance"
        ) from exc
'''

TEST_HELPERS = '''

@pytest.fixture(autouse=True)
def _reset_source_permission_trust():
    previous = permission_trust._replace_research_input_permission_trust_registry_for_tests(
        frozenset()
    )
    try:
        yield
    finally:
        permission_trust._replace_research_input_permission_trust_registry_for_tests(previous)


def _trust_permission(permission: ResearchInputSourcePermission) -> None:
    snapshot = permission_trust.research_input_permission_trust_snapshot()
    permission_trust._replace_research_input_permission_trust_registry_for_tests(
        snapshot.trusted_source_permission_sha256 | frozenset({permission.content_sha256})
    )


def _trusted_permission(
    *,
    permission_id: str,
    source_artifact_sha256: str,
    classification: ResearchInputClassification,
    allowed_learning_surfaces: tuple[ResearchLearningSurface, ...],
) -> ResearchInputSourcePermission:
    permission = ResearchInputSourcePermission(
        permission_id=permission_id,
        source_artifact_sha256=source_artifact_sha256,
        classification=classification,
        allowed_learning_surfaces=allowed_learning_surfaces,
    )
    _trust_permission(permission)
    return permission
'''

NEW_LEARNING = '''def _learning_contract(
    classification: ResearchInputClassification = ResearchInputClassification.RESEARCH_ARTIFACT,
) -> ResearchInputAdmissionContract:
    surfaces = (
        ResearchLearningSurface.CAMPAIGN_HISTORY,
        ResearchLearningSurface.OBSERVATION,
    )
    permission = _trusted_permission(
        permission_id=f"permission-{classification.value.lower()}",
        source_artifact_sha256="b" * 64,
        classification=classification,
        allowed_learning_surfaces=surfaces,
    )
    return ResearchInputAdmissionContract(
        input_id="research-input-001",
        classification_policy_sha256=permission.content_sha256,
        classification=classification,
        source_artifact_sha256="b" * 64,
        source_contract_sha256=permission.content_sha256,
        allowed_learning_surfaces=surfaces,
        source_permission=permission,
    )
'''

NEW_EXTERNAL = '''def _external_contract() -> ResearchInputAdmissionContract:
    permission = _trusted_permission(
        permission_id="permission-external-evidence",
        source_artifact_sha256="d" * 64,
        classification=ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE,
        allowed_learning_surfaces=(),
    )
    return ResearchInputAdmissionContract(
        input_id="external-evidence-001",
        classification_policy_sha256=permission.content_sha256,
        classification=ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE,
        source_artifact_sha256="d" * 64,
        source_contract_sha256=permission.content_sha256,
        allowed_learning_surfaces=(),
        source_permission=permission,
    )
'''

NEW_PARENT_HELPER = '''def _parent_ref(
    *,
    sha_char: str,
    classification: ResearchInputClassification,
    disposition: ResearchInputDisposition,
) -> ResearchInputParentRef:
    if disposition is ResearchInputDisposition.REJECTED:
        parent = ResearchInputAdmissionContract(
            input_id=f"parent-{sha_char}",
            classification_policy_sha256="a" * 64,
            classification=classification,
            source_artifact_sha256=None,
            source_contract_sha256=None,
            allowed_learning_surfaces=(),
        )
    else:
        surfaces = (
            (ResearchLearningSurface.OBSERVATION,)
            if disposition is ResearchInputDisposition.LEARNING_ADMITTED
            else ()
        )
        permission = _trusted_permission(
            permission_id=f"permission-parent-{sha_char}",
            source_artifact_sha256=sha_char * 64,
            classification=classification,
            allowed_learning_surfaces=surfaces,
        )
        parent = ResearchInputAdmissionContract(
            input_id=f"parent-{sha_char}",
            classification_policy_sha256=permission.content_sha256,
            classification=classification,
            source_artifact_sha256=sha_char * 64,
            source_contract_sha256=permission.content_sha256,
            allowed_learning_surfaces=surfaces,
            source_permission=permission,
        )
    reference = ResearchInputParentRef(parent_admission=parent)
    assert reference.disposition is disposition
    return reference
'''

EXTRA_TESTS = '''

def test_untrusted_source_permission_cannot_mint_learning_admission() -> None:
    permission = ResearchInputSourcePermission(
        permission_id="untrusted-permission",
        source_artifact_sha256="8" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        ResearchInputAdmissionContract(
            input_id="untrusted-input",
            classification_policy_sha256=permission.content_sha256,
            classification=ResearchInputClassification.RESEARCH_ARTIFACT,
            source_artifact_sha256="8" * 64,
            source_contract_sha256=permission.content_sha256,
            allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
            source_permission=permission,
        )


def test_source_permission_semantics_must_match_admission() -> None:
    permission = _trusted_permission(
        permission_id="bounded-permission",
        source_artifact_sha256="9" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    with pytest.raises(ResearchInputAdmissionError, match="requested learning surfaces"):
        ResearchInputAdmissionContract(
            input_id="mismatched-input",
            classification_policy_sha256=permission.content_sha256,
            classification=ResearchInputClassification.RESEARCH_ARTIFACT,
            source_artifact_sha256="9" * 64,
            source_contract_sha256=permission.content_sha256,
            allowed_learning_surfaces=(ResearchLearningSurface.CAMPAIGN_HISTORY,),
            source_permission=permission,
        )


def test_source_permission_revocation_invalidates_existing_admission() -> None:
    contract = _learning_contract()
    permission_trust._replace_research_input_permission_trust_registry_for_tests(frozenset())
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        _ = contract.content_sha256


def test_rejected_input_cannot_carry_source_permission() -> None:
    permission = _trusted_permission(
        permission_id="rejected-mismatch-permission",
        source_artifact_sha256="7" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    with pytest.raises(ResearchInputAdmissionError, match="cannot carry a source permission"):
        ResearchInputAdmissionContract(
            input_id="rejected-with-permission",
            classification_policy_sha256="a" * 64,
            classification=ResearchInputClassification.PHI_OR_PATIENT_DATA,
            source_artifact_sha256=None,
            source_contract_sha256=None,
            allowed_learning_surfaces=(),
            source_permission=permission,
        )


def test_self_referential_lineage_fails_closed_without_recursion_error() -> None:
    contract = _learning_contract()
    parent = ResearchInputParentRef(parent_admission=contract)
    object.__setattr__(contract, "transformation_kind", "summary")
    object.__setattr__(contract, "parent_inputs", (parent,))
    with pytest.raises(ResearchInputAdmissionError, match="cyclic research-input parent lineage"):
        contract.semantic_dict()
    with pytest.raises(ResearchInputAdmissionError, match="cyclic research-input parent lineage"):
        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)


def test_mutually_cyclic_lineage_fails_closed_without_recursion_error() -> None:
    first = _learning_contract()
    second = _learning_contract()
    first_ref = ResearchInputParentRef(parent_admission=first)
    second_ref = ResearchInputParentRef(parent_admission=second)
    object.__setattr__(first, "transformation_kind", "summary")
    object.__setattr__(first, "parent_inputs", (second_ref,))
    object.__setattr__(second, "transformation_kind", "summary")
    object.__setattr__(second, "parent_inputs", (first_ref,))
    with pytest.raises(ResearchInputAdmissionError, match="cyclic research-input parent lineage"):
        first.to_dict()
'''

trust_path = Path("src/medscale/mesc/_mrl_research_input_permission_trust_v1.py")
trust_path.write_text(TRUST_SOURCE)

source_path = Path("src/medscale/mesc/_mrl_research_input_admission_v1.py")
source = source_path.read_text()
source = source.replace(
    "from typing import Final\n\nfrom medscale.mesc._mrl_content_identity_v1 import (",
    "from typing import Final\n\nfrom medscale.mesc import _mrl_research_input_permission_trust_v1 as permission_trust\nfrom medscale.mesc._mrl_content_identity_v1 import (",
)
source = source.replace(
    '    "ResearchInputParentRef",\n    "ResearchLearningSurface",\n',
    '    "ResearchInputParentRef",\n    "ResearchInputSourcePermission",\n    "ResearchLearningSurface",\n',
)
marker = "\n\n@dataclass(frozen=True, slots=True)\nclass ResearchInputParentRef:"
if marker not in source:
    raise SystemExit("parent-ref insertion marker missing")
source = source.replace(marker, PERMISSION_CLASS + marker, 1)
source = source.replace(
    "    allowed_learning_surfaces: tuple[ResearchLearningSurface, ...]\n"
    "    transformation_kind: str | None = None\n",
    "    allowed_learning_surfaces: tuple[ResearchLearningSurface, ...]\n"
    "    source_permission: ResearchInputSourcePermission | None = field(default=None, repr=False)\n"
    "    transformation_kind: str | None = None\n",
    1,
)
if OLD_POST not in source:
    raise SystemExit("admission post-init block missing")
source = source.replace(OLD_POST, NEW_POST, 1)
if OLD_SNAPSHOT not in source:
    raise SystemExit("admission snapshot block missing")
source = source.replace(OLD_SNAPSHOT, NEW_SNAPSHOT, 1)
disposition_marker = "\n\ndef _require_no_lineage_laundering("
if disposition_marker not in source:
    raise SystemExit("source-binding insertion marker missing")
source = source.replace(disposition_marker, SOURCE_BINDING + disposition_marker, 1)
exact_marker = '''def _require_exact_parent_ref(value: ResearchInputParentRef) -> None:
    if type(value) is not ResearchInputParentRef:
        raise ResearchInputAdmissionError(
            "parent input reference must be an exact ResearchInputParentRef instance"
        )
'''
if exact_marker not in source:
    raise SystemExit("exact-parent helper marker missing")
source = source.replace(
    exact_marker,
    exact_marker
    + '''\n\ndef _require_exact_source_permission(value: ResearchInputSourcePermission) -> None:\n    if type(value) is not ResearchInputSourcePermission:\n        raise ResearchInputAdmissionError(\n            "source permission must be an exact ResearchInputSourcePermission instance"\n        )\n''',
    1,
)
source_path.write_text(source)

test_path = Path("tests/test_mesc_mrl_research_input_admission_v1.py")
tests = test_path.read_text()
tests = tests.replace(
    "import pytest\n\nfrom medscale.mesc._mrl_research_input_admission_v1 import (",
    "import pytest\n\nfrom medscale.mesc import _mrl_research_input_permission_trust_v1 as permission_trust\nfrom medscale.mesc._mrl_research_input_admission_v1 import (",
)
tests = tests.replace(
    "    ResearchInputParentRef,\n    ResearchLearningSurface,\n)",
    "    ResearchInputParentRef,\n    ResearchInputSourcePermission,\n    ResearchLearningSurface,\n)",
)
helper_marker = "\n\ndef _learning_contract("
if helper_marker not in tests:
    raise SystemExit("test helper insertion marker missing")
tests = tests.replace(helper_marker, TEST_HELPERS + helper_marker, 1)
start = tests.index("def _learning_contract(")
end = tests.index("\n\ndef _external_contract()", start)
tests = tests[:start] + NEW_LEARNING + tests[end:]
start = tests.index("def _external_contract()")
end = tests.index("\n\ndef _rejected_contract(", start)
tests = tests[:start] + NEW_EXTERNAL + tests[end:]
start = tests.index("def _parent_ref(")
end = tests.index("\n\ndef test_content_identity_is_outside_semantic_preimage", start)
tests = tests[:start] + NEW_PARENT_HELPER + tests[end:]
tests += EXTRA_TESTS
test_path.write_text(tests)
