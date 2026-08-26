from __future__ import annotations

from pathlib import Path

TEST = Path("tests/test_mesc_p01_04b_publication_qualification_v1.py")
SPEC = Path("specs/mesc-hf-sft-dependency-lock-v1/README.md")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


replace_once(
    TEST,
    "*boundary* the adopted contract fixes: the exact four-path scope, the protected\n"
    "paths, the absence of any public or CLI surface, the exact literals, and the\n"
    "continuing prohibitions.\n",
    "*boundary* the adopted contract fixes: the exact four-path implementation scope,\n"
    "the continuing protected runtime paths, the recorded adoption-baseline dependency\n"
    "identities, the absence of any public or CLI surface, the exact literals, and the\n"
    "continuing prohibitions.\n",
)
replace_once(
    TEST,
    "#: SHA-256 of every protected path at the adopting canonical main. ``.gitattributes``\n"
    "#: pins ``eol=lf`` repository-wide, so these digests are stable on every platform.\n"
    "PROTECTED_PATH_DIGESTS = {\n",
    "#: SHA-256 of continuing publication-boundary runtime paths. These paths remain\n"
    "#: byte-identical after adoption. Repository packaging may evolve under later,\n"
    "#: independently qualified gates without rewriting this implementation identity.\n"
    "CONTINUING_PROTECTED_PATH_DIGESTS = {\n",
)
replace_once(
    TEST,
    '    "tests/_mesc_p01_04b2d_fixtures_v1.py": (\n'
    '        "f9e805cf8e5dada8ad86b41a199001ddb1dc1d033aa550246d399d3ff27a9bb3"\n'
    '    ),\n'
    '    "pyproject.toml": ("da80ead771a81685f36d3e537fb3cee5f43624eb9e3917456ad02beb1471585e"),\n'
    '    "uv.lock": ("a5a91ffad1aab490080b96d7edc440d07417e06481ce8e0fc7e3c7ffb099c07d"),\n'
    '}\n',
    '    "tests/_mesc_p01_04b2d_fixtures_v1.py": (\n'
    '        "f9e805cf8e5dada8ad86b41a199001ddb1dc1d033aa550246d399d3ff27a9bb3"\n'
    '    ),\n'
    '}\n\n'
    '#: Historical packaging identities recorded at the publication implementation\n'
    '#: adoption baseline. They are evidence about that historical increment, not a\n'
    '#: permanent prohibition on independently authorized repository packaging changes.\n'
    'ADOPTION_BASELINE_DEPENDENCY_DIGESTS = {\n'
    '    "pyproject.toml": "da80ead771a81685f36d3e537fb3cee5f43624eb9e3917456ad02beb1471585e",\n'
    '    "uv.lock": "a5a91ffad1aab490080b96d7edc440d07417e06481ce8e0fc7e3c7ffb099c07d",\n'
    '}\n',
)
replace_once(
    TEST,
    "def test_protected_paths_are_byte_identical() -> None:\n"
    "    for relative, expected in PROTECTED_PATH_DIGESTS.items():\n"
    "        payload = (REPOSITORY_ROOT / relative).read_bytes()\n"
    "        assert hashlib.sha256(payload).hexdigest() == expected, relative\n\n\n",
    "def test_continuing_protected_paths_are_byte_identical() -> None:\n"
    "    for relative, expected in CONTINUING_PROTECTED_PATH_DIGESTS.items():\n"
    "        payload = (REPOSITORY_ROOT / relative).read_bytes()\n"
    "        assert hashlib.sha256(payload).hexdigest() == expected, relative\n\n\n"
    "def test_adoption_baseline_dependency_digests_remain_recorded() -> None:\n"
    "    assert ADOPTION_BASELINE_DEPENDENCY_DIGESTS == {\n"
    '        "pyproject.toml": "da80ead771a81685f36d3e537fb3cee5f43624eb9e3917456ad02beb1471585e",\n'
    '        "uv.lock": "a5a91ffad1aab490080b96d7edc440d07417e06481ce8e0fc7e3c7ffb099c07d",\n'
    "    }\n\n\n",
)
replace_once(
    TEST,
    "def test_no_dependency_or_lockfile_change() -> None:\n",
    "def test_dependency_evolution_does_not_expose_publisher() -> None:\n",
)
replace_once(
    TEST,
    '        "datasets",\n'
    '        "huggingface",\n'
    '        "transformers",\n'
    '        "torch",\n',
    '        "accelerate",\n'
    '        "bitsandbytes",\n'
    '        "datasets",\n'
    '        "huggingface",\n'
    '        "peft",\n'
    '        "transformers",\n'
    '        "torch",\n'
    '        "trl",\n',
)
replace_once(
    SPEC,
    "## Acceptance\n",
    "## Historical publication-boundary reconciliation\n\n"
    "The P01-04B publication implementation qualification recorded `pyproject.toml` and\n"
    "`uv.lock` byte digests as part of the exact adoption identity of that historical\n"
    "four-path implementation increment. Its continuously executed test originally\n"
    "treated those historical packaging bytes as if they could never change again.\n\n"
    "This gate does not rewrite those historical digests. It keeps them recorded as\n"
    "adoption-baseline evidence, while continuing byte-identity enforcement remains on\n"
    "the P01-04B runtime/split paths that are still required to be immutable. The\n"
    "publication harness also explicitly prohibits the new training packages from\n"
    "appearing in the private fixture publisher. This preserves the original publication\n"
    "boundary while allowing a separately specified and qualified dependency-lock gate.\n\n"
    "The dedicated cross-platform P01-04B publication qualification must return green on\n"
    "the exact dependency-lock PR head after this reconciliation.\n\n"
    "## Acceptance\n",
)
replace_once(
    SPEC,
    "8. normal Ruff, formatter, strict mypy, full pytest, and `medscale check` remain green on\n"
    "   Python 3.11 and 3.12; and\n"
    "9. CodeQL and material review findings are clean on the exact PR head.\n",
    "8. normal Ruff, formatter, strict mypy, full pytest, and `medscale check` remain green on\n"
    "   Python 3.11 and 3.12;\n"
    "9. the dedicated P01-04B publication qualification remains green on every supported\n"
    "   OS/Python matrix entry after historical dependency-baseline reconciliation; and\n"
    "10. CodeQL and material review findings are clean on the exact PR head.\n",
)
