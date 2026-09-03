from __future__ import annotations

from pathlib import Path

from scripts.check_docs_links import check_repository


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_valid_local_file_anchor_and_duplicate_anchor(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "# Home\n[Guide](docs/guide.md#hello-world)\n[Duplicate](docs/guide.md#repeat-1)\n",
    )
    _write(tmp_path / "docs/guide.md", "# Hello, World!\n# Repeat\n# Repeat\n")

    assert check_repository(tmp_path) == ()


def test_missing_local_file_is_reported(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "[Missing](docs/missing.md)\n")

    problems = check_repository(tmp_path)

    assert len(problems) == 1
    assert problems[0].reason == "local target does not exist"


def test_missing_markdown_anchor_is_reported(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "[Guide](docs/guide.md#missing)\n")
    _write(tmp_path / "docs/guide.md", "# Present\n")

    problems = check_repository(tmp_path)

    assert len(problems) == 1
    assert problems[0].reason == "Markdown anchor 'missing' does not exist"


def test_path_escape_is_rejected(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "[Escape](../outside.md)\n")

    problems = check_repository(tmp_path)

    assert len(problems) == 1
    assert problems[0].reason == "target escapes repository root"


def test_external_links_and_fenced_code_are_ignored(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "# Home\n[External](https://example.com/docs)\n```markdown\n[Ignored](missing.md)\n```\n",
    )

    assert check_repository(tmp_path) == ()


def test_reference_target_and_explicit_html_id_are_checked(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "[Guide][guide]\n[guide]: docs/guide.md#stable-id\n")
    _write(tmp_path / "docs/guide.md", '<span id="stable-id"></span>\n')

    assert check_repository(tmp_path) == ()
