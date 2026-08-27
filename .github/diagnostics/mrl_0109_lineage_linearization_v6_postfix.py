from pathlib import Path

path = Path("src/medscale/mesc/_mrl_research_input_admission_v1.py")
text = path.read_text(encoding="utf-8")
old = '                "external evaluation evidence requires exact artifact and governing contract identities"\n'
new = (
    '                "external evaluation evidence requires exact artifact and "\n'
    '                "governing contract identities"\n'
)
count = text.count(old)
if count != 1:
    raise SystemExit(f"expected one long external-evidence message, found {count}")
path.write_text(text.replace(old, new, 1), encoding="utf-8")
