from __future__ import annotations

from pathlib import Path

PYPROJECT = Path("pyproject.toml")
SPEC = Path("specs/mesc-hf-sft-dependency-lock-v1/README.md")
TEST = Path("tests/test_mesc_hf_sft_dependency_lock_v1.py")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


replace_once(
    PYPROJECT,
    'requires-python = ">=3.11"\n',
    'requires-python = ">=3.11,<3.15"\n',
)
replace_once(
    TEST,
    '    assert project["dependencies"] == []\n'
    '    assert tuple(training_extra) == _EXPECTED_TRAINING_PINS\n',
    '    assert project["dependencies"] == []\n'
    '    assert project["requires-python"] == ">=3.11,<3.15"\n'
    '    assert tuple(training_extra) == _EXPECTED_TRAINING_PINS\n',
)
replace_once(
    SPEC,
    "- the selected Torch 2.13.0 provides CPython 3.11 and 3.12 Linux x86-64 wheels.\n",
    "- the selected Torch 2.13.0 publishes PyPI wheels through CPython 3.14 but no\n"
    "  source distribution, so the project metadata is explicitly bounded to Python\n"
    "  `>=3.11,<3.15`; and\n"
    "- repository CI continues to qualify Python 3.11 and 3.12, while the dependency\n"
    "  resolver gate separately proves the frozen training extra resolves at Python 3.14.\n",
)
replace_once(
    SPEC,
    "1. `training-hf-sft` contains exactly the seven pinned top-level packages above;\n",
    "1. project metadata declares Python `>=3.11,<3.15`, matching the locked Torch\n"
    "   artifact ceiling rather than advertising an unsupported future interpreter;\n"
    "2. `training-hf-sft` contains exactly the seven pinned top-level packages above;\n",
)
replace_once(SPEC, "2. `uv lock` resolves", "3. `uv lock` resolves")
replace_once(SPEC, "3. `uv lock --check`", "4. `uv lock --check`")
replace_once(SPEC, "4. the exact top-level", "5. the exact top-level")
replace_once(SPEC, "5. `uv sync --frozen`", "6. `uv sync --frozen`")
replace_once(
    SPEC,
    "6. a dry-run sync of `training-hf-sft` resolves from the frozen lock without modifying it;\n",
    "7. dry-run syncs of `training-hf-sft` resolve from the frozen lock without\n"
    "   installation, including a Python 3.14 edge-of-range check;\n",
)
replace_once(SPEC, "7. the repository dependency-lock", "8. the repository dependency-lock")
replace_once(SPEC, "8. normal Ruff", "9. normal Ruff")
replace_once(SPEC, "9. the dedicated P01-04B", "10. the dedicated P01-04B")
replace_once(SPEC, "10. CodeQL", "11. CodeQL")
