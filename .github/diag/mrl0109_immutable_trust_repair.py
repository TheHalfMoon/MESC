from pathlib import Path

trust = Path("src/medscale/mesc/_mrl_research_input_permission_trust_v1.py")
trust.write_text('''"""Immutable repository-controlled trust root for MRL research-input permissions.

A caller cannot create research-input authority by constructing well-formed permission
semantics. Public admission gates consult one immutable trust snapshot captured from
canonical repository code at import time. The canonical registry intentionally starts
empty, so this module grants no research-input, model, dataset, network, training,
promotion, deployment, or clinical authority.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from medscale.mesc._canonical_json_v1 import canonical_json_bytes

TRUST_REGISTRY_VERSION: Final = "MRL-RESEARCH-INPUT-SOURCE-PERMISSION-TRUST-V1"

_SHA256: Final = re.compile(r"^[0-9a-f]{64}$", flags=re.ASCII)
_REGISTRY_KIND: Final = "mesc.mrl.research_input_source_permission.trust_registry.v1"


class ResearchInputPermissionTrustError(RuntimeError):
    """Raised when canonical research-input source-permission trust is invalid."""


@dataclass(frozen=True, slots=True)
class ResearchInputPermissionTrustSnapshot:
    """One immutable canonical source-permission trust snapshot."""

    registry_version: str
    trusted_source_permission_sha256: frozenset[str]
    registry_sha256: str

    def admits(self, value: str) -> bool:
        """Return whether this exact snapshot admits one source-permission digest."""
        if type(value) is not str or _SHA256.fullmatch(value) is None:
            return False
        return value in self.trusted_source_permission_sha256


def _validated_registry_snapshot(
    registry: frozenset[str],
) -> ResearchInputPermissionTrustSnapshot:
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
    return ResearchInputPermissionTrustSnapshot(
        registry_version=TRUST_REGISTRY_VERSION,
        trusted_source_permission_sha256=registry,
        registry_sha256=hashlib.sha256(canonical_json_bytes(payload)).hexdigest(),
    )


def _build_canonical_trust_api(
    registry: frozenset[str],
) -> tuple[
    Callable[[], ResearchInputPermissionTrustSnapshot],
    Callable[[str], ResearchInputPermissionTrustSnapshot],
]:
    """Bind public trust operations to one immutable registry snapshot."""
    canonical_snapshot = _validated_registry_snapshot(registry)

    def snapshot() -> ResearchInputPermissionTrustSnapshot:
        return canonical_snapshot

    def validate(permission_sha256: str) -> ResearchInputPermissionTrustSnapshot:
        if type(permission_sha256) is not str or _SHA256.fullmatch(permission_sha256) is None:
            raise ResearchInputPermissionTrustError(
                "source permission identity must be 64 lowercase hex characters"
            )
        if not canonical_snapshot.admits(permission_sha256):
            raise ResearchInputPermissionTrustError(
                "source permission is not trusted by the canonical registry"
            )
        return canonical_snapshot

    return snapshot, validate


(
    research_input_permission_trust_snapshot,
    validate_research_input_source_permission_trust,
) = _build_canonical_trust_api(frozenset())
del _build_canonical_trust_api


__all__ = [
    "TRUST_REGISTRY_VERSION",
    "ResearchInputPermissionTrustError",
    "ResearchInputPermissionTrustSnapshot",
    "research_input_permission_trust_snapshot",
    "validate_research_input_source_permission_trust",
]
''', encoding="utf-8")

admission = Path("src/medscale/mesc/_mrl_research_input_admission_v1.py")
text = admission.read_text(encoding="utf-8")
old_import = "from medscale.mesc import _mrl_research_input_permission_trust_v1 as permission_trust\n"
new_import = '''from medscale.mesc._mrl_research_input_permission_trust_v1 import (\n    ResearchInputPermissionTrustSnapshot,\n    research_input_permission_trust_snapshot as _canonical_permission_trust_snapshot,\n)\n'''
assert old_import in text
text = text.replace(old_import, new_import, 1)

old_trust = '''    try:\n        permission_trust.validate_research_input_source_permission_trust(permission_sha256)\n    except permission_trust.ResearchInputPermissionTrustError as exc:\n        raise ResearchInputAdmissionError(\n            "source permission is not trusted by canonical research-input governance"\n        ) from exc\n'''
assert old_trust in text
text = text.replace(old_trust, "", 1)

old_learning = '''        snapshot = self._validated_snapshot()\n        if (\n            _disposition_for_classification(snapshot.classification)\n            is not ResearchInputDisposition.LEARNING_ADMITTED\n        ):\n            raise ResearchInputAdmissionError("input is not admitted as an MRL learning signal")\n        if surface not in snapshot.allowed_learning_surfaces:\n            raise ResearchInputAdmissionError(\n                f"input is not admitted to learning surface {surface.value!r}"\n            )\n'''
new_learning = old_learning + '''        _require_admission_graph_trust(snapshot)\n'''
assert old_learning in text
text = text.replace(old_learning, new_learning, 1)

old_external = '''        snapshot = self._validated_snapshot()\n        if (\n            _disposition_for_classification(snapshot.classification)\n            is not ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY\n        ):\n            raise ResearchInputAdmissionError(\n                "input is not admitted as separately governed external evaluation evidence"\n            )\n'''
new_external = old_external + '''        _require_admission_graph_trust(snapshot)\n'''
assert old_external in text
text = text.replace(old_external, new_external, 1)

marker = "def _require_no_lineage_laundering(\n"
assert marker in text
helper = '''def _require_admission_graph_trust(root: ResearchInputAdmissionContract) -> None:\n    """Require current canonical trust for every admissible node in this lineage graph."""\n    trust_snapshot = _canonical_permission_trust_snapshot()\n    if type(trust_snapshot) is not ResearchInputPermissionTrustSnapshot:\n        raise ResearchInputAdmissionError(\n            "canonical research-input permission trust snapshot has an invalid runtime type"\n        )\n    stack = [root]\n    visited: set[int] = set()\n    while stack:\n        node = stack.pop()\n        node_id = id(node)\n        if node_id in visited:\n            continue\n        visited.add(node_id)\n        _require_exact_admission(node)\n        disposition = _disposition_for_classification(node.classification)\n        if disposition is not ResearchInputDisposition.REJECTED:\n            _require_source_permission_binding(node)\n            permission = node.source_permission\n            if type(permission) is not ResearchInputSourcePermission:\n                raise ResearchInputAdmissionError(\n                    "admissible input requires an exact ResearchInputSourcePermission"\n                )\n            permission_snapshot = permission._validated_snapshot()\n            permission_sha256 = derive_content_sha256(\n                permission_snapshot._semantic_dict_validated()\n            )\n            if not trust_snapshot.admits(permission_sha256):\n                raise ResearchInputAdmissionError(\n                    "source permission is not trusted by canonical research-input governance"\n                )\n        for parent_ref in node.parent_inputs:\n            _require_exact_parent_ref(parent_ref)\n            stack.append(parent_ref.parent_admission)\n\n\n'''
text = text.replace(marker, helper + marker, 1)
text = text.replace(
    '        """Return the canonical disposition after fresh exact-type validation."""\n',
    '        """Return policy disposition; authority still requires a public admission gate."""\n',
    1,
)
admission.write_text(text, encoding="utf-8")

tests = Path("tests/test_mesc_mrl_research_input_admission_v1.py")
t = tests.read_text(encoding="utf-8")
t = t.replace("from collections.abc import Iterator\n", "")
start = t.index("@pytest.fixture(autouse=True)\ndef _reset_source_permission_trust()")
end = t.index("\ndef _learning_contract(", start)
replacement = '''def _source_permission(\n    *,\n    permission_id: str,\n    source_artifact_sha256: str,\n    source_contract_sha256: str,\n    classification: ResearchInputClassification,\n    allowed_learning_surfaces: tuple[ResearchLearningSurface, ...],\n) -> ResearchInputSourcePermission:\n    return ResearchInputSourcePermission(\n        permission_id=permission_id,\n        source_artifact_sha256=source_artifact_sha256,\n        source_contract_sha256=source_contract_sha256,\n        classification=classification,\n        allowed_learning_surfaces=allowed_learning_surfaces,\n    )\n\n'''
t = t[:start] + replacement + t[end + 1 :]
t = t.replace("_trusted_permission(", "_source_permission(")

old = '''    assert contract.disposition is ResearchInputDisposition.LEARNING_ADMITTED\n    contract.require_learning_admission(ResearchLearningSurface.CAMPAIGN_HISTORY)\n    contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)\n'''
new = '''    assert contract.disposition is ResearchInputDisposition.LEARNING_ADMITTED\n    for surface in (\n        ResearchLearningSurface.CAMPAIGN_HISTORY,\n        ResearchLearningSurface.OBSERVATION,\n    ):\n        with pytest.raises(ResearchInputAdmissionError, match="not trusted"):\n            contract.require_learning_admission(surface)\n'''
assert old in t
t = t.replace(old, new, 1)

t = t.replace(
    '''    contract.require_external_evaluation_use()\n    for surface in ResearchLearningSurface:\n''',
    '''    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):\n        contract.require_external_evaluation_use()\n    for surface in ResearchLearningSurface:\n''',
    1,
)

t = t.replace(
    '''    assert transformed.disposition is ResearchInputDisposition.LEARNING_ADMITTED\n    transformed.require_learning_admission(ResearchLearningSurface.OBSERVATION)\n    assert transformed.content_sha256 != _learning_contract().content_sha256\n''',
    '''    assert transformed.disposition is ResearchInputDisposition.LEARNING_ADMITTED\n    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):\n        transformed.require_learning_admission(ResearchLearningSurface.OBSERVATION)\n    assert transformed.content_sha256 != _learning_contract().content_sha256\n''',
    1,
)

old = '''    contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)\n\n\ndef test_source_permission_revocation_invalidates_existing_admission() -> None:\n    contract = _learning_contract()\n    permission_trust._replace_research_input_permission_trust_registry_for_tests(frozenset())\n    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):\n        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)\n    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):\n        _ = contract.content_sha256\n'''
new = '''    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):\n        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)\n\n\ndef test_caller_cannot_mint_canonical_source_permission_trust(monkeypatch: pytest.MonkeyPatch) -> None:\n    permission = _source_permission(\n        permission_id="caller-minted-permission",\n        source_artifact_sha256="4" * 64,\n        source_contract_sha256="5" * 64,\n        classification=ResearchInputClassification.RESEARCH_ARTIFACT,\n        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),\n    )\n    contract = ResearchInputAdmissionContract(\n        input_id="caller-minted-input",\n        classification_policy_sha256="a" * 64,\n        classification=ResearchInputClassification.RESEARCH_ARTIFACT,\n        source_artifact_sha256="4" * 64,\n        source_contract_sha256="5" * 64,\n        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),\n        source_permission=permission,\n    )\n    fake_snapshot = permission_trust.ResearchInputPermissionTrustSnapshot(\n        registry_version=permission_trust.TRUST_REGISTRY_VERSION,\n        trusted_source_permission_sha256=frozenset({permission.content_sha256}),\n        registry_sha256="f" * 64,\n    )\n    monkeypatch.setattr(\n        permission_trust,\n        "TRUSTED_RESEARCH_INPUT_SOURCE_PERMISSION_SHA256",\n        frozenset({permission.content_sha256}),\n        raising=False,\n    )\n    monkeypatch.setattr(\n        permission_trust,\n        "research_input_permission_trust_snapshot",\n        lambda: fake_snapshot,\n    )\n    monkeypatch.setattr(\n        permission_trust,\n        "validate_research_input_source_permission_trust",\n        lambda _value: fake_snapshot,\n    )\n\n    assert not hasattr(permission_trust, "_replace_research_input_permission_trust_registry_for_tests")\n    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):\n        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)\n'''
assert old in t
t = t.replace(old, new, 1)

old = '''    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):\n        ResearchInputAdmissionContract(\n            input_id="untrusted-input",\n            classification_policy_sha256="a" * 64,\n            classification=ResearchInputClassification.RESEARCH_ARTIFACT,\n            source_artifact_sha256="8" * 64,\n            source_contract_sha256="6" * 64,\n            allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),\n            source_permission=permission,\n        )\n'''
new = '''    contract = ResearchInputAdmissionContract(\n        input_id="untrusted-input",\n        classification_policy_sha256="a" * 64,\n        classification=ResearchInputClassification.RESEARCH_ARTIFACT,\n        source_artifact_sha256="8" * 64,\n        source_contract_sha256="6" * 64,\n        allowed_learning_surfaces=(ResearchLearningSurface.OBSERVATION,),\n        source_permission=permission,\n    )\n    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):\n        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)\n'''
assert old in t
t = t.replace(old, new, 1)

t = t.replace(
    '''    with pytest.raises(ResearchInputAdmissionError, match=r"not trusted|governing source contract"):\n        contract.semantic_dict()\n''',
    '''    with pytest.raises(ResearchInputAdmissionError, match="governing source contract"):\n        contract.semantic_dict()\n''',
    1,
)

tests.write_text(t, encoding="utf-8")
