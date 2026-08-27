from pathlib import Path

source_path = Path("src/medscale/mesc/_mrl_research_input_admission_v1.py")
source = source_path.read_text(encoding="utf-8")

old_guard = '''        _require_exact_admission(node)\n        if node_id in active:\n            raise ResearchInputAdmissionError("cyclic research-input parent lineage is forbidden")\n        if node_id in visited:\n            continue\n        if depth > _MAX_LINEAGE_DEPTH:\n            raise ResearchInputAdmissionError(\n                "research-input parent lineage exceeds the fail-closed depth limit"\n            )\n'''
new_guard = '''        _require_exact_admission(node)\n        if node_id in active:\n            raise ResearchInputAdmissionError("cyclic research-input parent lineage is forbidden")\n        if depth > _MAX_LINEAGE_DEPTH:\n            raise ResearchInputAdmissionError(\n                "research-input parent lineage exceeds the fail-closed depth limit"\n            )\n        if node_id in visited:\n            continue\n'''
if source.count(old_guard) != 1:
    raise SystemExit("shared-depth traversal guard marker changed")
source = source.replace(old_guard, new_guard, 1)
source_path.write_text(source, encoding="utf-8")

test_path = Path("tests/test_mesc_mrl_research_input_admission_v1.py")
tests = test_path.read_text(encoding="utf-8")
marker = '''def test_deep_lineage_hash_work_is_linear_during_construction_and_validation(\n    monkeypatch: pytest.MonkeyPatch,\n) -> None:\n'''
if tests.count(marker) != 1:
    raise SystemExit("depth regression insertion marker changed")
regression = '''def test_shared_ancestor_cannot_bypass_depth_limit() -> None:\n    shared = _learning_contract()\n\n    deep = shared\n    for index in range(128):\n        deep = replace(\n            _learning_contract(),\n            input_id=f"research-input-shared-depth-{index:03d}",\n            transformation_kind="summary",\n            parent_inputs=(ResearchInputParentRef(parent_admission=deep),),\n        )\n    deep_ref = ResearchInputParentRef(parent_admission=deep)\n\n    shallow_ref: ResearchInputParentRef | None = None\n    for index in range(512):\n        shallow = replace(\n            _learning_contract(),\n            input_id=f"research-input-shallow-shared-{index:03d}",\n            transformation_kind="summary",\n            parent_inputs=(ResearchInputParentRef(parent_admission=shared),),\n        )\n        candidate = ResearchInputParentRef(parent_admission=shallow)\n        if candidate.admission_sha256 < deep_ref.admission_sha256:\n            shallow_ref = candidate\n            break\n    assert shallow_ref is not None\n\n    root = replace(\n        _learning_contract(),\n        input_id="research-input-shared-depth-overflow",\n        transformation_kind="merge",\n        parent_inputs=(shallow_ref, deep_ref),\n    )\n\n    with pytest.raises(ResearchInputAdmissionError, match="depth limit"):\n        root.semantic_dict()\n\n\n'''
tests = tests.replace(marker, regression + marker, 1)
test_path.write_text(tests, encoding="utf-8")
