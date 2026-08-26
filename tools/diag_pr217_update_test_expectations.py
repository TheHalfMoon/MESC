from pathlib import Path

path = Path("tests/test_mesc_release_semantic_evidence_v1.py")
text = path.read_text(encoding="utf-8")

replacements = {
    'with pytest.raises(ReleaseSemanticEvidenceError, match="SUCCEEDED"):\n': (
        'with pytest.raises(\n'
        '    ReleaseSemanticEvidenceError,\n'
        '    match="canonical executor invariants",\n'
        '):\n'
    ),
    'with pytest.raises(ReleaseSemanticEvidenceError, match="result_manifest_sha256"):\n': (
        'with pytest.raises(\n'
        '    ReleaseSemanticEvidenceError,\n'
        '    match="canonical executor invariants",\n'
        '):\n'
    ),
}

for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f"missing expectation anchor: {old!r}")
    text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
