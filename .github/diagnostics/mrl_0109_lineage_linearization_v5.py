from __future__ import annotations

from pathlib import Path
import re

SOURCE = Path("src/medscale/mesc/_mrl_research_input_admission_v1.py")
TESTS = Path("tests/test_mesc_mrl_research_input_admission_v1.py")
SPEC = Path("specs/mesc-research-loop-v1/spec.md")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one marker, found {count}")
    return text.replace(old, new, 1)


def patch_source() -> None:
    text = SOURCE.read_text(encoding="utf-8")

    text = replace_once(
        text,
        '_TOKEN_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")\n'
        '_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")\n',
        '_TOKEN_ID: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]*$")\n'
        '_SHA256: Final = re.compile(r"^[0-9a-f]{64}$")\n'
        '_MAX_LINEAGE_DEPTH: Final = 128\n'
        '_MAX_LINEAGE_NODES: Final = 4096\n'
        '_MAX_LINEAGE_EDGES: Final = 16384\n',
        "lineage limits",
    )

    before_ref, ref_and_after = text.split("class ResearchInputParentRef:", 1)
    ref_body, after_ref = ref_and_after.split("\ndef _build_admission_graph_trust_gate", 1)
    ref_pattern = re.compile(r"    def __post_init__\(self\) -> None:\n.*?\n\n    def _validated_binding", re.S)
    ref_replacement = '''    def __post_init__(self) -> None:\n        _require_exact_admission(self.parent_admission)\n        _, current_sha256, current_classification, current_disposition = (\n            _local_admission_state(self.parent_admission)\n        )\n        object.__setattr__(self, "_bound_admission_sha256", current_sha256)\n        object.__setattr__(self, "_bound_classification", current_classification)\n        object.__setattr__(self, "_bound_disposition", current_disposition)\n\n    def _validated_binding'''
    ref_body, count = ref_pattern.subn(ref_replacement, ref_body, count=1)
    if count != 1:
        raise SystemExit(f"parent ref constructor replacement count={count}")
    text = before_ref + "class ResearchInputParentRef:" + ref_body + "\ndef _build_admission_graph_trust_gate" + after_ref

    before_contract, contract_and_after = text.split("class ResearchInputAdmissionContract:", 1)
    contract_body, after_contract = contract_and_after.split("\ndel _bind_learning_admission_trust", 1)
    contract_pattern = re.compile(r"    def __post_init__\(self\) -> None:\n.*?\n\n    @property\n    def disposition", re.S)
    contract_replacement = '''    def __post_init__(self) -> None:\n        # Exact-type enforcement belongs to authoritative/public validation. A subclass may\n        # exist as an untrusted object, but every public view and admission gate rejects it.\n        if type(self) is not ResearchInputAdmissionContract:\n            return\n        _local_admission_state(self)\n\n    @property\n    def disposition'''
    contract_body, count = contract_pattern.subn(contract_replacement, contract_body, count=1)
    if count != 1:
        raise SystemExit(f"contract constructor replacement count={count}")
    text = before_contract + "class ResearchInputAdmissionContract:" + contract_body + "\ndel _bind_learning_admission_trust" + after_contract

    local_helper = '''def _local_admission_state(\n    node: ResearchInputAdmissionContract,\n) -> tuple[dict[str, object], str, ResearchInputClassification, ResearchInputDisposition]:\n    """Validate one envelope using bound parent metadata without traversing ancestry."""\n    _require_exact_admission(node)\n    _require_token(node.input_id, "input_id")\n    _require_sha256(node.classification_policy_sha256, "classification_policy_sha256")\n    _require_exact_enum(node.classification, ResearchInputClassification, "classification")\n    _require_optional_sha256(node.source_artifact_sha256, "source_artifact_sha256")\n    _require_optional_sha256(node.source_contract_sha256, "source_contract_sha256")\n    _require_learning_surfaces(node.allowed_learning_surfaces)\n    parents = node.parent_inputs\n    if type(parents) is not tuple:\n        raise ResearchInputAdmissionError("parent_inputs must be an exact tuple")\n    if len(parents) > _MAX_LINEAGE_NODES:\n        raise ResearchInputAdmissionError(\n            "research-input parent lineage exceeds the fail-closed direct-parent limit"\n        )\n    _require_transformation_lineage(node.transformation_kind, parents)\n\n    disposition = _disposition_for_classification(node.classification)\n    if disposition is ResearchInputDisposition.LEARNING_ADMITTED:\n        if node.source_artifact_sha256 is None or node.source_contract_sha256 is None:\n            raise ResearchInputAdmissionError(\n                "learning-admitted input requires exact source artifact and contract identities"\n            )\n        if not node.allowed_learning_surfaces:\n            raise ResearchInputAdmissionError(\n                "learning-admitted input requires at least one explicit learning surface"\n            )\n        _require_source_permission_binding(node)\n    elif disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY:\n        if node.source_artifact_sha256 is None or node.source_contract_sha256 is None:\n            raise ResearchInputAdmissionError(\n                "external evaluation evidence requires exact artifact and governing contract identities"\n            )\n        if node.allowed_learning_surfaces:\n            raise ResearchInputAdmissionError(\n                "external evaluation evidence cannot enter an MRL learning surface"\n            )\n        _require_source_permission_binding(node)\n    else:\n        if node.source_permission is not None:\n            raise ResearchInputAdmissionError(\n                "rejected input cannot carry a source permission into MRL"\n            )\n        if node.source_artifact_sha256 is not None or node.source_contract_sha256 is not None:\n            raise ResearchInputAdmissionError(\n                "rejected input cannot carry source artifact or contract identities into MRL"\n            )\n        if node.allowed_learning_surfaces:\n            raise ResearchInputAdmissionError(\n                "rejected input cannot enter an MRL learning surface"\n            )\n\n    parent_payloads: list[dict[str, str]] = []\n    parent_digests: list[str] = []\n    for parent_ref in parents:\n        _require_exact_parent_ref(parent_ref)\n        _require_exact_admission(parent_ref.parent_admission)\n        _require_sha256(parent_ref._bound_admission_sha256, "bound parent admission sha256")\n        _require_exact_enum(\n            parent_ref._bound_classification,\n            ResearchInputClassification,\n            "bound parent classification",\n        )\n        _require_exact_enum(\n            parent_ref._bound_disposition,\n            ResearchInputDisposition,\n            "bound parent disposition",\n        )\n        if (\n            parent_ref._bound_disposition is ResearchInputDisposition.REJECTED\n            and disposition is not ResearchInputDisposition.REJECTED\n        ):\n            raise ResearchInputAdmissionError(\n                "a rejected parent cannot be transformed into an admissible MRL input"\n            )\n        if (\n            parent_ref._bound_disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY\n            and disposition is ResearchInputDisposition.LEARNING_ADMITTED\n        ):\n            raise ResearchInputAdmissionError(\n                "external evaluation evidence cannot be transformed into an MRL learning signal"\n            )\n        parent_payloads.append(\n            {\n                "admission_sha256": parent_ref._bound_admission_sha256,\n                "classification": parent_ref._bound_classification.value,\n                "disposition": parent_ref._bound_disposition.value,\n            }\n        )\n        parent_digests.append(parent_ref._bound_admission_sha256)\n\n    if tuple(parent_digests) != tuple(sorted(set(parent_digests))):\n        raise ResearchInputAdmissionError(\n            "parent_inputs must be unique and strictly sorted by admission_sha256"\n        )\n\n    source_permission_sha256: str | None = None\n    if node.source_permission is not None:\n        _require_exact_source_permission(node.source_permission)\n        permission = node.source_permission._validated_snapshot()\n        source_permission_sha256 = derive_content_sha256(permission._semantic_dict_validated())\n\n    semantic: dict[str, object] = {\n        "format": "MRL-RESEARCH-INPUT-ADMISSION-V1",\n        "input_id": node.input_id,\n        "classification_policy_sha256": node.classification_policy_sha256,\n        "classification": node.classification.value,\n        "disposition": disposition.value,\n        "source_artifact_sha256": node.source_artifact_sha256,\n        "source_contract_sha256": node.source_contract_sha256,\n        "allowed_learning_surfaces": [surface.value for surface in node.allowed_learning_surfaces],\n        "source_permission_sha256": source_permission_sha256,\n        "transformation_kind": node.transformation_kind,\n        "parent_inputs": parent_payloads,\n    }\n    content_sha256 = derive_content_sha256(semantic)\n    return semantic, content_sha256, node.classification, disposition\n\n\n'''
    marker = "def _parent_graph_postorder(\n"
    if text.count(marker) != 1:
        raise SystemExit("parent graph helper marker changed")
    text = text.replace(marker, local_helper + marker, 1)

    text = replace_once(
        text,
        "    max_depth = 128\n    max_nodes = 4096\n    active: set[int] = set()\n",
        "    active: set[int] = set()\n",
        "remove local graph limits",
    )
    text = replace_once(
        text,
        "    discovered: set[int] = set()\n    order: list[ResearchInputAdmissionContract] = []\n",
        "    discovered: set[int] = set()\n    edge_count = 0\n    order: list[ResearchInputAdmissionContract] = []\n",
        "edge counter",
    )
    text = text.replace("        if depth > max_depth:\n", "        if depth > _MAX_LINEAGE_DEPTH:\n", 1)
    text = text.replace("            if len(discovered) > max_nodes:\n", "            if len(discovered) > _MAX_LINEAGE_NODES:\n", 1)
    text = replace_once(
        text,
        '        parents = node.parent_inputs\n        if type(parents) is not tuple:\n            raise ResearchInputAdmissionError("parent_inputs must be an exact tuple")\n        active.add(node_id)\n',
        '        parents = node.parent_inputs\n        if type(parents) is not tuple:\n            raise ResearchInputAdmissionError("parent_inputs must be an exact tuple")\n        edge_count += len(parents)\n        if edge_count > _MAX_LINEAGE_EDGES:\n            raise ResearchInputAdmissionError(\n                "research-input parent lineage exceeds the fail-closed edge limit"\n            )\n        active.add(node_id)\n',
        "graph edge bound",
    )

    SOURCE.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from medscale.mesc import _mrl_research_input_permission_trust_v1 as permission_trust\n",
        "from medscale.mesc import _mrl_research_input_admission_v1 as admission_module\n"
        "from medscale.mesc import _mrl_research_input_permission_trust_v1 as permission_trust\n",
        "admission module test import",
    )

    old_depth = '''def test_parent_lineage_beyond_depth_limit_fails_closed() -> None:\n    current = _deep_learning_chain(128)\n    parent = ResearchInputParentRef(parent_admission=current)\n\n    with pytest.raises(ResearchInputAdmissionError, match="depth limit"):\n        replace(\n            _learning_contract(),\n            input_id="research-input-too-deep",\n            transformation_kind="summary",\n            parent_inputs=(parent,),\n        )\n'''
    new_depth = '''def test_parent_lineage_beyond_depth_limit_fails_closed() -> None:\n    current = _deep_learning_chain(128)\n    parent = ResearchInputParentRef(parent_admission=current)\n    too_deep = replace(\n        _learning_contract(),\n        input_id="research-input-too-deep",\n        transformation_kind="summary",\n        parent_inputs=(parent,),\n    )\n\n    with pytest.raises(ResearchInputAdmissionError, match="depth limit"):\n        too_deep.semantic_dict()\n'''
    text = replace_once(text, old_depth, new_depth, "depth-limit regression")

    addition = '''\n\ndef test_deep_lineage_hash_work_is_linear_during_construction_and_validation(\n    monkeypatch: pytest.MonkeyPatch,\n) -> None:\n    original = admission_module.derive_content_sha256\n    calls = 0\n\n    def counted(payload: object) -> str:\n        nonlocal calls\n        calls += 1\n        return original(payload)\n\n    monkeypatch.setattr(admission_module, "derive_content_sha256", counted)\n    depth = 96\n    contract = _deep_learning_chain(depth)\n    assert calls <= 8 * (depth + 1)\n\n    calls = 0\n    contract.semantic_dict()\n    assert calls <= 3 * (depth + 1)\n\n\ndef test_direct_parent_breadth_is_bounded_at_construction() -> None:\n    parent = ResearchInputParentRef(parent_admission=_learning_contract())\n    with pytest.raises(ResearchInputAdmissionError, match="direct-parent limit"):\n        replace(\n            _learning_contract(),\n            input_id="research-input-too-wide",\n            transformation_kind="merge",\n            parent_inputs=(parent,) * 4097,\n        )\n'''
    if "test_deep_lineage_hash_work_is_linear_during_construction_and_validation" in text:
        raise SystemExit("linear-work regression already present")
    TESTS.write_text(text + addition, encoding="utf-8")


def patch_spec() -> None:
    text = SPEC.read_text(encoding="utf-8")
    marker = (
        "metadata or ordinary rebindable module names.\n\n"
        "This contract-level threat model does **not** treat a caller with arbitrary Python code\n"
    )
    replacement = (
        "metadata or ordinary rebindable module names.\n\n"
        "Canonical implementations must bound lineage depth, node cardinality, and edge count.\n"
        "Construction-time checks may inspect only the local envelope and already-bound direct\n"
        "parent metadata; every public semantic/hash/admission view must revalidate the complete\n"
        "reachable lineage with a bounded, memoized graph pass. Shared or deep ancestry must not\n"
        "trigger repeated subtree reconstruction, and pathological lineage must fail closed.\n\n"
        "This contract-level threat model does **not** treat a caller with arbitrary Python code\n"
    )
    text = replace_once(text, marker, replacement, "spec lineage work bound")
    SPEC.write_text(text, encoding="utf-8")


patch_source()
patch_tests()
patch_spec()
