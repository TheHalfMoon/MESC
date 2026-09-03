from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Protocol, cast


class _Problem(Protocol):
    reason: str
    target: str


class _RepositoryChecker(Protocol):
    def __call__(self, root: Path) -> tuple[_Problem, ...]: ...


class _CheckerModule(Protocol):
    check_repository: _RepositoryChecker


def _load_checker() -> _RepositoryChecker:
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "check_docs_links.py"
    module_name = "_align22_docs_link_checker"
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load docs link checker from {script_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return cast(_CheckerModule, module).check_repository


check_repository = _load_checker()


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


def test_github_slug_preserves_punctuation_gap_as_double_hyphen(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "[Rule](docs/guide.md#r4--one-ticket-per-session)\n"
        "[Canonical](docs/guide.md#canonical-sources--precedence)\n",
    )
    _write(
        tmp_path / "docs/guide.md",
        "# R4 — One ticket per session\n# Canonical sources & precedence\n",
    )

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


def test_inline_code_and_prose_ids_do_not_create_html_anchors(tmp_path: Path) -> None:
    _write(tmp_path / "README.md", "[Guide](docs/guide.md#fake-id)\n")
    _write(
        tmp_path / "docs/guide.md",
        '`id="fake-id"`\nplain id="fake-id" text\n',
    )

    problems = check_repository(tmp_path)

    assert len(problems) == 1
    assert problems[0].reason == "Markdown anchor 'fake-id' does not exist"


def test_single_and_multiline_html_comments_are_excluded(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "[Hidden one](docs/guide.md#hidden-one)\n"
        "[Hidden two](docs/guide.md#hidden-two)\n"
        "<!-- [Ignored single](docs/missing-single.md) -->\n"
        "<!--\n"
        "[Ignored multi](docs/missing-multi.md)\n"
        "-->\n",
    )
    _write(
        tmp_path / "docs/guide.md",
        '<!-- <span id="hidden-one"></span> -->\n'
        "<!--\n"
        '<span id="hidden-two"></span>\n'
        "-->\n",
    )

    problems = check_repository(tmp_path)

    assert tuple(problem.target for problem in problems) == (
        "docs/guide.md#hidden-one",
        "docs/guide.md#hidden-two",
    )
    assert all("does not exist" in problem.reason for problem in problems)


def test_comment_close_then_inline_marker_does_not_hide_rendered_link(tmp_path: Path) -> None:
    _write(
        tmp_path / "README.md",
        "<!--\n"
        "comment\n"
        "--> `<!-- not a comment -->` [Missing](docs/missing.md)\n",
    )

    problems = check_repository(tmp_path)

    assert len(problems) == 1
    assert problems[0].target == "docs/missing.md"
    assert problems[0].reason == "local target does not exist"
