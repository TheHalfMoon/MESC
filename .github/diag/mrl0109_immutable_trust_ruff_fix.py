from pathlib import Path

admission = Path("src/medscale/mesc/_mrl_research_input_admission_v1.py")
text = admission.read_text(encoding="utf-8")
old = '''    snapshot = permission._validated_snapshot()\n    permission_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())\n    if contract.source_artifact_sha256 != snapshot.source_artifact_sha256:\n'''
new = '''    snapshot = permission._validated_snapshot()\n    if contract.source_artifact_sha256 != snapshot.source_artifact_sha256:\n'''
assert old in text
admission.write_text(text.replace(old, new, 1), encoding="utf-8")

tests = Path("tests/test_mesc_mrl_research_input_admission_v1.py")
t = tests.read_text(encoding="utf-8")
old_def = "def test_caller_cannot_mint_canonical_source_permission_trust(monkeypatch: pytest.MonkeyPatch) -> None:\n"
new_def = '''def test_caller_cannot_mint_canonical_source_permission_trust(\n    monkeypatch: pytest.MonkeyPatch,\n) -> None:\n'''
assert old_def in t
t = t.replace(old_def, new_def, 1)
old_assert = '''    assert not hasattr(permission_trust, "_replace_research_input_permission_trust_registry_for_tests")\n'''
new_assert = '''    assert not hasattr(\n        permission_trust,\n        "_replace_research_input_permission_trust_registry_for_tests",\n    )\n'''
assert old_assert in t
tests.write_text(t.replace(old_assert, new_assert, 1), encoding="utf-8")
