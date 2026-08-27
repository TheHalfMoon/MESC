from pathlib import Path

admission = Path("src/medscale/mesc/_mrl_research_input_admission_v1.py")
text = admission.read_text(encoding="utf-8")
old = '''    snapshot = permission._validated_snapshot()\n    permission_sha256 = derive_content_sha256(snapshot._semantic_dict_validated())\n    if contract.source_artifact_sha256 != snapshot.source_artifact_sha256:\n'''
new = '''    snapshot = permission._validated_snapshot()\n    if contract.source_artifact_sha256 != snapshot.source_artifact_sha256:\n'''
assert old in text
admission.write_text(text.replace(old, new, 1), encoding="utf-8")
