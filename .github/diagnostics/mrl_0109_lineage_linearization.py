from pathlib import Path
import re


path = Path("src/medscale/mesc/_mrl_research_input_admission_v1.py")
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one marker, found {count}")
    text = text.replace(old, new, 1)


replace_once(
    "Untrusted research execution must therefore run outside the\n"
    "trust-bearing interpreter/process under the separately governed execution boundary.\n"
    '"""',
    "Untrusted research execution must therefore run outside the\n"
    "trust-bearing interpreter/process under the separately governed execution boundary.\n\n"
    "Lineage validation is iterative, graph-bounded, and non-amplifying: pathological\n"
    "depth or breadth fails closed instead of triggering repeated recursive snapshots.\n"
    '"""',
    "module integrity note",
)

replace_once(
    '''    def __post_init__(self) -> None:
        _require_exact_admission(self.parent_admission)
        parent = self.parent_admission._validated_snapshot()
        object.__setattr__(
            self,
            "_bound_admission_sha256",
            derive_content_sha256(parent._semantic_dict_validated()),
        )
        object.__setattr__(self, "_bound_classification", parent.classification)
        object.__setattr__(
            self,
            "_bound_disposition",
            _disposition_for_classification(parent.classification),
        )
''',
    '''    def __post_init__(self) -> None:
        _require_exact_admission(self.parent_admission)
        _, current_sha256, current_classification, current_disposition = (
            _validated_admission_state(self.parent_admission)
        )
        object.__setattr__(self, "_bound_admission_sha256", current_sha256)
        object.__setattr__(self, "_bound_classification", current_classification)
        object.__setattr__(self, "_bound_disposition", current_disposition)
''',
    "parent ref post init",
)

replace_once(
    '''    def _validated_binding(
        self,
    ) -> tuple[str, ResearchInputClassification, ResearchInputDisposition]:
        _require_exact_parent_ref(self)
        _require_exact_admission(self.parent_admission)
        parent = self.parent_admission._validated_snapshot()
        current_sha256 = derive_content_sha256(parent._semantic_dict_validated())
        current_classification = parent.classification
        current_disposition = _disposition_for_classification(current_classification)
        if (
            current_sha256 != self._bound_admission_sha256
            or current_classification is not self._bound_classification
            or current_disposition is not self._bound_disposition
        ):
            raise ResearchInputAdmissionError(
                "parent admission binding changed after reference creation"
            )
        return current_sha256, current_classification, current_disposition
''',
    '''    def _validated_binding(
        self,
    ) -> tuple[str, ResearchInputClassification, ResearchInputDisposition]:
        _require_exact_parent_ref(self)
        _require_exact_admission(self.parent_admission)
        _, current_sha256, current_classification, current_disposition = (
            _validated_admission_state(self.parent_admission)
        )
        _require_sha256(self._bound_admission_sha256, "bound parent admission sha256")
        _require_exact_enum(
            self._bound_classification,
            ResearchInputClassification,
            "bound parent classification",
        )
        _require_exact_enum(
            self._bound_disposition,
            ResearchInputDisposition,
            "bound parent disposition",
        )
        if (
            current_sha256 != self._bound_admission_sha256
            or current_classification is not self._bound_classification
            or current_disposition is not self._bound_disposition
        ):
            raise ResearchInputAdmissionError(
                "parent admission binding changed after reference creation"
            )
        return current_sha256, current_classification, current_disposition
''',
    "parent ref validated binding",
)

replace_once(
    '''    def _validated_snapshot(self) -> ResearchInputParentRef:
        self._validated_binding()
        return ResearchInputParentRef(parent_admission=self.parent_admission._validated_snapshot())
''',
    '''    def _validated_snapshot(self) -> ResearchInputParentRef:
        """Validate the live binding without recursively rebuilding its ancestry."""
        self._validated_binding()
        return self
''',
    "parent ref snapshot",
)

replace_once(
    '''    def require_admission_graph_trust(root: ResearchInputAdmissionContract) -> None:
        stack = [root]
''',
    '''    def require_admission_graph_trust(root: ResearchInputAdmissionContract) -> None:
        _validated_admission_state(root)
        stack = [root]
''',
    "trust graph validation",
)

if text.count("trust_gate(self._validated_snapshot())") != 2:
    raise SystemExit("trust wrapper marker count changed")
text = text.replace("trust_gate(self._validated_snapshot())", "trust_gate(self)")

head, tail = text.split("class ResearchInputAdmissionContract:", 1)
pattern = re.compile(
    r"    def __post_init__\(self\) -> None:\n.*?\n    @property\n    def disposition",
    re.S,
)
tail, count = pattern.subn(
    "    def __post_init__(self) -> None:\n"
    "        _validated_admission_state(self)\n\n"
    "    @property\n"
    "    def disposition",
    tail,
    count=1,
)
if count != 1:
    raise SystemExit(f"contract post-init replacement count={count}")
text = head + "class ResearchInputAdmissionContract:" + tail

replace_once(
    '''    @property
    def disposition(self) -> ResearchInputDisposition:
        """Return policy disposition; authority still requires a public admission gate."""
        _require_exact_admission(self)
        snapshot = self._validated_snapshot()
        return _disposition_for_classification(snapshot.classification)
''',
    '''    @property
    def disposition(self) -> ResearchInputDisposition:
        """Return validated policy disposition; authority still requires a public gate."""
        _require_exact_admission(self)
        return _validated_admission_state(self)[3]
''',
    "contract disposition",
)

replace_once(
    '''    @_bind_learning_admission_trust(_require_admission_graph_trust)
    def require_learning_admission(self, surface: ResearchLearningSurface) -> None:
        """Fail closed unless this exact input may enter the requested MRL learning surface."""
        _require_exact_admission(self)
        _require_exact_enum(surface, ResearchLearningSurface, "surface")
        snapshot = self._validated_snapshot()
        if (
            _disposition_for_classification(snapshot.classification)
            is not ResearchInputDisposition.LEARNING_ADMITTED
        ):
            raise ResearchInputAdmissionError("input is not admitted as an MRL learning signal")
        if surface not in snapshot.allowed_learning_surfaces:
            raise ResearchInputAdmissionError(
                f"input is not admitted to learning surface {surface.value!r}"
            )
''',
    '''    @_bind_learning_admission_trust(_require_admission_graph_trust)
    def require_learning_admission(self, surface: ResearchLearningSurface) -> None:
        """Fail closed unless this exact input may enter the requested MRL learning surface."""
        _require_exact_admission(self)
        _require_exact_enum(surface, ResearchLearningSurface, "surface")
        _, _, _, disposition = _validated_admission_state(self)
        if disposition is not ResearchInputDisposition.LEARNING_ADMITTED:
            raise ResearchInputAdmissionError("input is not admitted as an MRL learning signal")
        if surface not in self.allowed_learning_surfaces:
            raise ResearchInputAdmissionError(
                f"input is not admitted to learning surface {surface.value!r}"
            )
''',
    "learning admission method",
)

replace_once(
    '''    @_bind_external_evaluation_trust(_require_admission_graph_trust)
    def require_external_evaluation_use(self) -> None:
        """Fail closed unless this input is separately classified as external evidence only."""
        _require_exact_admission(self)
        snapshot = self._validated_snapshot()
        if (
            _disposition_for_classification(snapshot.classification)
            is not ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY
        ):
            raise ResearchInputAdmissionError(
                "input is not admitted as separately governed external evaluation evidence"
            )
''',
    '''    @_bind_external_evaluation_trust(_require_admission_graph_trust)
    def require_external_evaluation_use(self) -> None:
        """Fail closed unless this input is separately classified as external evidence only."""
        _require_exact_admission(self)
        _, _, _, disposition = _validated_admission_state(self)
        if disposition is not ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY:
            raise ResearchInputAdmissionError(
                "input is not admitted as separately governed external evaluation evidence"
            )
''',
    "external admission method",
)

pattern = re.compile(
    r"    def _validated_snapshot\(self\) -> ResearchInputAdmissionContract:\n.*?\n    def _semantic_dict_validated",
    re.S,
)
text, count = pattern.subn(
    "    def _validated_snapshot(self) -> ResearchInputAdmissionContract:\n"
    "        \"\"\"Validate the live graph without recursively rebuilding equivalent objects.\"\"\"\n"
    "        _validated_admission_state(self)\n"
    "        return self\n\n"
    "    def _semantic_dict_validated",
    text,
    count=1,
)
if count != 1:
    raise SystemExit(f"contract snapshot replacement count={count}")

pattern = re.compile(
    r"    def _semantic_dict_validated\(self\) -> dict\[str, object\]:\n.*?\n    def semantic_dict",
    re.S,
)
text, count = pattern.subn(
    "    def _semantic_dict_validated(self) -> dict[str, object]:\n"
    "        \"\"\"Return semantics from one bounded, fully validated graph pass.\"\"\"\n"
    "        return _validated_admission_state(self)[0]\n\n"
    "    def semantic_dict",
    text,
    count=1,
)
if count != 1:
    raise SystemExit(f"semantic private replacement count={count}")

pattern = re.compile(
    r"    def semantic_dict\(self\) -> dict\[str, object\]:\n.*?\n\n    @property\n    def semantic_bytes",
    re.S,
)
text, count = pattern.subn(
    "    def semantic_dict(self) -> dict[str, object]:\n"
    "        \"\"\"Return complete semantics from one bounded validated graph pass.\"\"\"\n"
    "        _require_exact_admission(self)\n"
    "        return _validated_admission_state(self)[0]\n\n"
    "    @property\n"
    "    def semantic_bytes",
    text,
    count=1,
)
if count != 1:
    raise SystemExit(f"semantic_dict replacement count={count}")

replace_once(
    '''    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical UTF-8 semantic bytes from a fresh snapshot."""
        _require_exact_admission(self)
        snapshot = self._validated_snapshot()
        return canonical_semantic_bytes(snapshot._semantic_dict_validated())
''',
    '''    @property
    def semantic_bytes(self) -> bytes:
        """Return canonical UTF-8 bytes from one bounded validated graph pass."""
        _require_exact_admission(self)
        semantic, _, _, _ = _validated_admission_state(self)
        return canonical_semantic_bytes(semantic)
''',
    "semantic bytes",
)

replace_once(
    '''    @property
    def content_sha256(self) -> str:
        """Derive content identity outside the semantic preimage."""
        _require_exact_admission(self)
        snapshot = self._validated_snapshot()
        return derive_content_sha256(snapshot._semantic_dict_validated())
''',
    '''    @property
    def content_sha256(self) -> str:
        """Derive content identity outside the semantic preimage."""
        _require_exact_admission(self)
        return _validated_admission_state(self)[1]
''',
    "content digest",
)

replace_once(
    '''    def to_dict(self) -> dict[str, object]:
        """Return semantic envelope plus derived content identity."""
        _require_exact_admission(self)
        snapshot = self._validated_snapshot()
        data = snapshot._semantic_dict_validated()
        data["content_sha256"] = derive_content_sha256(data)
        return data
''',
    '''    def to_dict(self) -> dict[str, object]:
        """Return semantic envelope plus derived content identity."""
        _require_exact_admission(self)
        data, content_sha256, _, _ = _validated_admission_state(self)
        data["content_sha256"] = content_sha256
        return data
''',
    "to_dict",
)

pattern = re.compile(
    r"def _require_acyclic_parent_lineage\(root: ResearchInputAdmissionContract\) -> None:\n.*?\n\ndef _require_source_permission_binding",
    re.S,
)
graph_helpers = r'''def _parent_graph_postorder(
    root: ResearchInputAdmissionContract,
) -> list[ResearchInputAdmissionContract]:
    """Return parent-first order while bounding cycles, depth, and graph cardinality."""
    max_depth = 128
    max_nodes = 4096
    active: set[int] = set()
    visited: set[int] = set()
    discovered: set[int] = set()
    order: list[ResearchInputAdmissionContract] = []
    stack: list[tuple[ResearchInputAdmissionContract, int, bool]] = [(root, 0, False)]

    while stack:
        node, depth, exiting = stack.pop()
        node_id = id(node)
        if exiting:
            active.remove(node_id)
            visited.add(node_id)
            order.append(node)
            continue
        _require_exact_admission(node)
        if node_id in active:
            raise ResearchInputAdmissionError("cyclic research-input parent lineage is forbidden")
        if node_id in visited:
            continue
        if depth > max_depth:
            raise ResearchInputAdmissionError(
                "research-input parent lineage exceeds the fail-closed depth limit"
            )
        if node_id not in discovered:
            discovered.add(node_id)
            if len(discovered) > max_nodes:
                raise ResearchInputAdmissionError(
                    "research-input parent lineage exceeds the fail-closed node limit"
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

    return order


def _validated_admission_state(
    root: ResearchInputAdmissionContract,
) -> tuple[dict[str, object], str, ResearchInputClassification, ResearchInputDisposition]:
    """Validate and serialize an admission DAG once, memoizing every ancestor by identity."""
    states: dict[
        int,
        tuple[dict[str, object], str, ResearchInputClassification, ResearchInputDisposition],
    ] = {}

    for node in _parent_graph_postorder(root):
        _require_token(node.input_id, "input_id")
        _require_sha256(node.classification_policy_sha256, "classification_policy_sha256")
        _require_exact_enum(node.classification, ResearchInputClassification, "classification")
        _require_optional_sha256(node.source_artifact_sha256, "source_artifact_sha256")
        _require_optional_sha256(node.source_contract_sha256, "source_contract_sha256")
        _require_learning_surfaces(node.allowed_learning_surfaces)
        parents = node.parent_inputs
        _require_transformation_lineage(node.transformation_kind, parents)

        disposition = _disposition_for_classification(node.classification)
        if disposition is ResearchInputDisposition.LEARNING_ADMITTED:
            if node.source_artifact_sha256 is None or node.source_contract_sha256 is None:
                raise ResearchInputAdmissionError(
                    "learning-admitted input requires exact source artifact and contract identities"
                )
            if not node.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "learning-admitted input requires at least one explicit learning surface"
                )
            _require_source_permission_binding(node)
        elif disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY:
            if node.source_artifact_sha256 is None or node.source_contract_sha256 is None:
                raise ResearchInputAdmissionError(
                    "external evaluation evidence requires exact artifact and governing contract identities"
                )
            if node.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "external evaluation evidence cannot enter an MRL learning surface"
                )
            _require_source_permission_binding(node)
        else:
            if node.source_permission is not None:
                raise ResearchInputAdmissionError(
                    "rejected input cannot carry a source permission into MRL"
                )
            if node.source_artifact_sha256 is not None or node.source_contract_sha256 is not None:
                raise ResearchInputAdmissionError(
                    "rejected input cannot carry source artifact or contract identities into MRL"
                )
            if node.allowed_learning_surfaces:
                raise ResearchInputAdmissionError(
                    "rejected input cannot enter an MRL learning surface"
                )

        parent_payloads: list[dict[str, str]] = []
        parent_digests: list[str] = []
        parent_dispositions: list[ResearchInputDisposition] = []
        for parent_ref in parents:
            _require_exact_parent_ref(parent_ref)
            parent = parent_ref.parent_admission
            _require_exact_admission(parent)
            parent_state = states.get(id(parent))
            if parent_state is None:
                raise ResearchInputAdmissionError("parent admission validation order is incomplete")
            _, parent_sha256, parent_classification, parent_disposition = parent_state
            _require_sha256(
                parent_ref._bound_admission_sha256,
                "bound parent admission sha256",
            )
            _require_exact_enum(
                parent_ref._bound_classification,
                ResearchInputClassification,
                "bound parent classification",
            )
            _require_exact_enum(
                parent_ref._bound_disposition,
                ResearchInputDisposition,
                "bound parent disposition",
            )
            if (
                parent_sha256 != parent_ref._bound_admission_sha256
                or parent_classification is not parent_ref._bound_classification
                or parent_disposition is not parent_ref._bound_disposition
            ):
                raise ResearchInputAdmissionError(
                    "parent admission binding changed after reference creation"
                )
            parent_payloads.append(
                {
                    "admission_sha256": parent_sha256,
                    "classification": parent_classification.value,
                    "disposition": parent_disposition.value,
                }
            )
            parent_digests.append(parent_sha256)
            parent_dispositions.append(parent_disposition)

        if tuple(parent_digests) != tuple(sorted(set(parent_digests))):
            raise ResearchInputAdmissionError(
                "parent_inputs must be unique and strictly sorted by admission_sha256"
            )
        for parent_disposition in parent_dispositions:
            if (
                parent_disposition is ResearchInputDisposition.REJECTED
                and disposition is not ResearchInputDisposition.REJECTED
            ):
                raise ResearchInputAdmissionError(
                    "a rejected parent cannot be transformed into an admissible MRL input"
                )
            if (
                parent_disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY
                and disposition is ResearchInputDisposition.LEARNING_ADMITTED
            ):
                raise ResearchInputAdmissionError(
                    "external evaluation evidence cannot be transformed into an MRL learning signal"
                )

        source_permission_sha256: str | None = None
        if node.source_permission is not None:
            _require_exact_source_permission(node.source_permission)
            permission = node.source_permission._validated_snapshot()
            source_permission_sha256 = derive_content_sha256(
                permission._semantic_dict_validated()
            )

        semantic: dict[str, object] = {
            "format": "MRL-RESEARCH-INPUT-ADMISSION-V1",
            "input_id": node.input_id,
            "classification_policy_sha256": node.classification_policy_sha256,
            "classification": node.classification.value,
            "disposition": disposition.value,
            "source_artifact_sha256": node.source_artifact_sha256,
            "source_contract_sha256": node.source_contract_sha256,
            "allowed_learning_surfaces": [
                surface.value for surface in node.allowed_learning_surfaces
            ],
            "source_permission_sha256": source_permission_sha256,
            "transformation_kind": node.transformation_kind,
            "parent_inputs": parent_payloads,
        }
        content_sha256 = derive_content_sha256(semantic)
        states[id(node)] = (semantic, content_sha256, node.classification, disposition)

    state = states.get(id(root))
    if state is None:
        raise ResearchInputAdmissionError("research-input graph validation produced no root state")
    return state


def _require_source_permission_binding'''
text, count = pattern.subn(graph_helpers, text, count=1)
if count != 1:
    raise SystemExit(f"graph helper replacement count={count}")

pattern = re.compile(
    r"\ndef _require_no_lineage_laundering\(.*?\n\ndef _require_transformation_lineage",
    re.S,
)
text, count = pattern.subn("\n\ndef _require_transformation_lineage", text, count=1)
if count != 1:
    raise SystemExit(f"remove laundering helper count={count}")

pattern = re.compile(
    r"\ndef _require_parent_refs\(.*?\n\ndef _require_learning_surfaces",
    re.S,
)
text, count = pattern.subn("\n\ndef _require_learning_surfaces", text, count=1)
if count != 1:
    raise SystemExit(f"remove parent refs helper count={count}")

path.write_text(text, encoding="utf-8")

test_path = Path("tests/test_mesc_mrl_research_input_admission_v1.py")
tests = test_path.read_text(encoding="utf-8")
addition = r'''


def _deep_learning_chain(depth: int) -> ResearchInputAdmissionContract:
    """Build one valid linear ancestry for amplification-regression coverage."""
    current = _learning_contract()
    for index in range(depth):
        parent = ResearchInputParentRef(parent_admission=current)
        current = replace(
            _learning_contract(),
            input_id=f"research-input-depth-{index:03d}",
            transformation_kind="summary",
            parent_inputs=(parent,),
        )
    return current


def test_deep_acyclic_lineage_validation_is_bounded_and_deterministic() -> None:
    contract = _deep_learning_chain(96)

    first = contract.semantic_dict()
    second = contract.semantic_dict()
    assert first == second
    assert contract.content_sha256 == contract.to_dict()["content_sha256"]
    assert len(contract.content_sha256) == 64
    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):
        contract.require_learning_admission(ResearchLearningSurface.OBSERVATION)


def test_parent_lineage_beyond_depth_limit_fails_closed() -> None:
    current = _deep_learning_chain(128)
    parent = ResearchInputParentRef(parent_admission=current)

    with pytest.raises(ResearchInputAdmissionError, match="depth limit"):
        replace(
            _learning_contract(),
            input_id="research-input-too-deep",
            transformation_kind="summary",
            parent_inputs=(parent,),
        )
'''
if "test_deep_acyclic_lineage_validation_is_bounded_and_deterministic" in tests:
    raise SystemExit("deep-lineage regression already present")
test_path.write_text(tests + addition, encoding="utf-8")
