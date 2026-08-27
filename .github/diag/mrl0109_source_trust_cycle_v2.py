from __future__ import annotations

from pathlib import Path

SOURCE_PATH = Path("src/medscale/mesc/_mrl_research_input_admission_v1.py")
TEST_PATH = Path("tests/test_mesc_mrl_research_input_admission_v1.py")


def _replace_between(text: str, start: str, end: str, replacement: str) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise SystemExit(f"missing start marker: {start!r}")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise SystemExit(f"missing end marker: {end!r}")
    return text[:start_index] + replacement + text[end_index:]


PERMISSION_CLASS = '''@dataclass(frozen=True, slots=True)
class ResearchInputSourcePermission:
    """Content-addressed permission for one exact governed research-input source."""

    permission_id: str
    source_artifact_sha256: str
    source_contract_sha256: str
    classification: ResearchInputClassification
    allowed_learning_surfaces: tuple[ResearchLearningSurface, ...]

    def __post_init__(self) -> None:
        _require_token(self.permission_id, "permission_id")
        _require_sha256(self.source_artifact_sha256, "source_artifact_sha256")
        _require_sha256(self.source_contract_sha256, "source_contract_sha256")
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
            source_contract_sha256=self.source_contract_sha256,
            classification=self.classification,
            allowed_learning_surfaces=self.allowed_learning_surfaces,
        )

    def _semantic_dict_validated(self) -> dict[str, object]:
        return {
            "format": "MRL-RESEARCH-INPUT-SOURCE-PERMISSION-V1",
            "permission_id": self.permission_id,
            "source_artifact_sha256": self.source_artifact_sha256,
            "source_contract_sha256": self.source_contract_sha256,
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


LINEAGE_AND_BINDING = '''def _require_acyclic_parent_lineage(root: ResearchInputAdmissionContract) -> None:
    """Reject cyclic or pathologically deep parent graphs before recursive validation."""
    max_depth = 128
    active: set[int] = set()
    visited: set[int] = set()
    stack: list[tuple[ResearchInputAdmissionContract, int, bool]] = [(root, 0, False)]

    while stack:
        node, depth, exiting = stack.pop()
        node_id = id(node)
        if exiting:
            active.remove(node_id)
            visited.add(node_id)
            continue
        _require_exact_admission(node)
        if node_id in active:
            raise ResearchInputAdmissionError(
                "cyclic research-input parent lineage is forbidden"
            )
        if node_id in visited:
            continue
        if depth > max_depth:
            raise ResearchInputAdmissionError(
                "research-input parent lineage exceeds the fail-closed depth limit"
            )
        parents = node.parent_inputs
        if type(parents) is not tuple:
            raise ResearchInputAdmissionError("parent_inputs must be an exact tuple")
        active.add(node_id)
        stack.append((node, depth, True))
        for parent_ref in reversed(parents):
            _require_exact_parent_ref(parent_ref)
            parent = parent_ref.parent_admission
            _require_exact_admission(parent)
            stack.append((parent, depth + 1, False))


def _require_source_permission_binding(contract: ResearchInputAdmissionContract) -> None:
    permission = contract.source_permission
    if type(permission) is not ResearchInputSourcePermission:
        raise ResearchInputAdmissionError(
            "admissible input requires an exact ResearchInputSourcePermission"
        )
    snapshot = permission._validated_snapshot()
    permission_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())
    if contract.source_artifact_sha256 != snapshot.source_artifact_sha256:
        raise ResearchInputAdmissionError(
            "source permission does not bind the admitted source artifact"
        )
    if contract.source_contract_sha256 != snapshot.source_contract_sha256:
        raise ResearchInputAdmissionError(
            "source permission does not bind the governing source contract"
        )
    if contract.classification is not snapshot.classification:
        raise ResearchInputAdmissionError(
            "source permission does not authorize the admitted classification"
        )
    requested = frozenset(contract.allowed_learning_surfaces)
    permitted = frozenset(snapshot.allowed_learning_surfaces)
    if not requested.issubset(permitted):
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


TRUSTED_PERMISSION_HELPER = '''def _trusted_permission(
    *,
    permission_id: str,
    source_artifact_sha256: str,
    source_contract_sha256: str,
    classification: ResearchInputClassification,
    allowed_learning_surfaces: tuple[ResearchLearningSurface, ...],
) -> ResearchInputSourcePermission:
    permission = ResearchInputSourcePermission(
        permission_id=permission_id,
        source_artifact_sha256=source_artifact_sha256,
        source_contract_sha256=source_contract_sha256,
        classification=classification,
        allowed_learning_surfaces=allowed_learning_surfaces,
    )
    _trust_permission(permission)
    return permission
'''


LEARNING_HELPER = '''def _learning_contract(
    classification: ResearchInputClassification = ResearchInputClassification.RESEARCH_ARTIFACT,
) -> ResearchInputAdmissionContract:
    surfaces = (
        ResearchLearningSurface.CAMPAIGN_HISTORY,
        ResearchLearningSurface.OBSERVATION,
    )
    permission = _trusted_permission(
        permission_id=f"permission-{classification.value.lower()}",
        source_artifact_sha256="b" * 64,
        source_contract_sha256="c" * 64,
        classification=classification,
        allowed_learning_surfaces=surfaces,
    )
    return ResearchInputAdmissionContract(
        input_id="research-input-001",
        classification_policy_sha256="a" * 64,
        classification=classification,
        source_artifact_sha256="b" * 64,
        source_contract_sha256="c" * 64,
        allowed_learning_surfaces=surfaces,
        source_permission=permission,
    )
'''


EXTERNAL_HELPER = '''def _external_contract() -> ResearchInputAdmissionContract:
    permission = _trusted_permission(
        permission_id="permission-external-evidence",
        source_artifact_sha256="d" * 64,
        source_contract_sha256="e" * 64,
        classification=ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE,
        allowed_learning_surfaces=(),
    )
    return ResearchInputAdmissionContract(
        input_id="external-evidence-001",
        classification_policy_sha256="a" * 64,
        classification=ResearchInputClassification.EXTERNAL_EVALUATION_EVIDENCE,
        source_artifact_sha256="d" * 64,
        source_contract_sha256="e" * 64,
        allowed_learning_surfaces=(),
        source_permission=permission,
    )
'''


PARENT_HELPER = '''def _parent_ref(
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
            source_contract_sha256="b" * 64,
            classification=classification,
            allowed_learning_surfaces=surfaces,
        )
        parent = ResearchInputAdmissionContract(
            input_id=f"parent-{sha_char}",
            classification_policy_sha256="a" * 64,
            classification=classification,
            source_artifact_sha256=sha_char * 64,
            source_contract_sha256="b" * 64,
            allowed_learning_surfaces=surfaces,
            source_permission=permission,
        )
    reference = ResearchInputParentRef(parent_admission=parent)
    assert reference.disposition is disposition
    return reference
'''


EXTRA_TESTS = '''def test_untrusted_source_permission_cannot_mint_learning_admission() -> None:
    permission = ResearchInputSourcePermission(
        permission_id="untrusted-permission",
        source_artifact_sha256="8" * 64,
        source_contract_sha256="6" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        ResearchInputAdmissionContract(
            input_id="untrusted-input",
            classification_policy_sha256="a" * 64,
            classification=ResearchInputClassification.RESEARCH_ARTIFACT,
            source_artifact_sha256="8" * 64,
            source_contract_sha256="6" * 64,
            allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
            source_permission=permission,
        )


def test_source_permission_semantics_must_match_admission() -> None:
    permission = _trusted_permission(
        permission_id="bounded-permission",
        source_artifact_sha256="9" * 64,
        source_contract_sha256="5" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    with pytest.raises(ResearchInputAdmissionError, match="requested learning surfaces"):
        ResearchInputAdmissionContract(
            input_id="mismatched-input",
            classification_policy_sha256="a" * 64,
            classification=ResearchInputClassification.RESEARCH_ARTIFACT,
            source_artifact_sha256="9" * 64,
            source_contract_sha256="5" * 64,
            allowed_learning_surfaces=(ResearchLearningSurface.CAMPAIGN_HISTORY,),
            source_permission=permission,
        )


def test_source_permission_binds_governing_contract_identity() -> None:
    permission = _trusted_permission(
        permission_id="contract-bound-permission",
        source_artifact_sha256="7" * 64,
        source_contract_sha256="3" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
    )
    with pytest.raises(ResearchInputAdmissionError, match="governing source contract"):
        ResearchInputAdmissionContract(
            input_id="wrong-contract-input",
            classification_policy_sha256="a" * 64,
            classification=ResearchInputClassification.RESEARCH_ARTIFACT,
            source_artifact_sha256="7" * 64,
            source_contract_sha256="4" * 64,
            allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
            source_permission=permission,
        )


def test_source_permission_allows_a_strict_surface_subset() -> None:
    permission = _trusted_permission(
        permission_id="subset-permission",
        source_artifact_sha256="6" * 64,
        source_contract_sha256="2" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        allowed_learning_surfaces=(
            ResearchLearningSurface.CAMPAIGN_HISTORY,
            ResearchLearningSurface.OBSERVATION,
        ),
    )
    contract = ResearchInputAdmissionContract(
        input_id="subset-input",
        classification_policy_sha256="f" * 64,
        classification=ResearchInputClassification.RESEARCH_ARTIFACT,
        source_artifact_sha256="6" * 64,
        source_contract_sha256="2" * 64,
        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),
        source_permission=permission,
    )
    contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)


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
        source_contract_sha256="4" * 64,
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


def test_permission_mutation_fails_closed_after_trust_admission() -> None:
    contract = _learning_contract()
    assert contract.source_permission is not None
    object.__setattr__(contract.source_permission, "source_contract_sha256", "1" * 64)
    with pytest.raises(ResearchInputAdmissionError, match="not trusted|governing source contract"):
        contract.semantic_dict()


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


source = SOURCE_PATH.read_text()
source = _replace_between(
    source,
    "@dataclass(frozen=True, slots=True)\nclass ResearchInputSourcePermission:",
    "\n\n@dataclass(frozen=True, slots=True)\nclass ResearchInputParentRef:",
    PERMISSION_CLASS,
)
source = _replace_between(
    source,
    "def _require_source_permission_binding(",
    "\n\ndef _require_no_lineage_laundering(",
    LINEAGE_AND_BINDING,
)
source = source.replace(
    "    def _validated_snapshot(self) -> ResearchInputAdmissionContract:\n"
    "        _require_exact_admission(self)\n"
    "        try:\n",
    "    def _validated_snapshot(self) -> ResearchInputAdmissionContract:\n"
    "        _require_exact_admission(self)\n"
    "        _require_acyclic_parent_lineage(self)\n"
    "        try:\n",
    1,
)
semantic_marker = '''            "allowed_learning_surfaces": [
                surface.value for surface in self.allowed_learning_surfaces
            ],
            "transformation_kind": self.transformation_kind,
'''
semantic_replacement = '''            "allowed_learning_surfaces": [
                surface.value for surface in self.allowed_learning_surfaces
            ],
            "source_permission_sha256": (
                derive_content_sha256(self.source_permission._semantic_dict_validated())
                if self.source_permission is not None
                else None
            ),
            "transformation_kind": self.transformation_kind,
'''
if semantic_marker not in source:
    raise SystemExit("admission semantic marker missing")
source = source.replace(semantic_marker, semantic_replacement, 1)
SOURCE_PATH.write_text(source)


tests = TEST_PATH.read_text()
tests = _replace_between(
    tests,
    "def _trusted_permission(",
    "\n\ndef _learning_contract(",
    TRUSTED_PERMISSION_HELPER,
)
tests = _replace_between(
    tests,
    "def _learning_contract(",
    "\n\ndef _external_contract()",
    LEARNING_HELPER,
)
tests = _replace_between(
    tests,
    "def _external_contract()",
    "\n\ndef _rejected_contract(",
    EXTERNAL_HELPER,
)
tests = _replace_between(
    tests,
    "def _parent_ref(",
    "\n\ndef test_content_identity_is_outside_semantic_preimage",
    PARENT_HELPER,
)
extra_start = tests.find("def test_untrusted_source_permission_cannot_mint_learning_admission()")
if extra_start < 0:
    raise SystemExit("extra-test marker missing")
tests = tests[:extra_start] + EXTRA_TESTS
set_marker = '''        "allowed_learning_surfaces",
        "transformation_kind",
'''
set_replacement = '''        "allowed_learning_surfaces",
        "source_permission_sha256",
        "transformation_kind",
'''
if set_marker not in tests:
    raise SystemExit("semantic set marker missing")
tests = tests.replace(set_marker, set_replacement, 1)
TEST_PATH.write_text(tests)
