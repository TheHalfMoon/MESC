from pathlib import Path

path = Path("tests/test_mesc_mrl_research_input_admission_v1.py")
text = path.read_text(encoding="utf-8")
old = '''    assert transformed.disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY\n    transformed.require_external_evaluation_use()\n'''
new = '''    assert transformed.disposition is ResearchInputDisposition.EXTERNAL_EVALUATION_ONLY\n    with pytest.raises(ResearchInputAdmissionError, match="not trusted"):\n        transformed.require_external_evaluation_use()\n'''
assert old in text
path.write_text(text.replace(old, new, 1), encoding="utf-8")
