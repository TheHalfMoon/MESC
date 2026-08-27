from pathlib import Path

path = Path("src/medscale/mesc/_mrl_research_input_admission_v1.py")
text = path.read_text(encoding="utf-8")
old = '''    def __post_init__(self) -> None:
        _validated_admission_state(self)
'''
new = '''    def __post_init__(self) -> None:
        # Exact-type enforcement belongs to authoritative/public validation. A subclass may
        # exist as an untrusted object, but every public view and admission gate rejects it.
        if type(self) is not ResearchInputAdmissionContract:
            return
        _validated_admission_state(self)
'''
if text.count(old) != 1:
    raise SystemExit(f"expected one admission post-init marker, found {text.count(old)}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
