from pathlib import Path

path = Path("tests/test_mesc_mrl_research_input_admission_v1.py")
text = path.read_text(encoding="utf-8")

import_marker = "from dataclasses import FrozenInstanceError, replace\n\nimport pytest\n"
if text.count(import_marker) != 1:
    raise SystemExit("test import marker changed")
text = text.replace(
    import_marker,
    "import importlib\nfrom dataclasses import FrozenInstanceError, replace\n\nimport pytest\n",
    1,
)

alias = "from medscale.mesc import _mrl_research_input_admission_v1 as admission_module\n"
if text.count(alias) != 1:
    raise SystemExit("admission module alias marker changed")
text = text.replace(alias, "", 1)

old = "    original = admission_module.derive_content_sha256\n"
new = (
    "    admission_module = importlib.import_module(\n"
    "        \"medscale.mesc._mrl_research_input_admission_v1\"\n"
    "    )\n"
    "    original = getattr(admission_module, \"derive_content_sha256\")\n"
)
if text.count(old) != 1:
    raise SystemExit("hash instrumentation marker changed")
text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
