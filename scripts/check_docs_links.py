from __future__ import annotations

import argparse
import html
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

PUBLIC_ROOT_MARKDOWN: tuple[str, ...] = (
    "README.md",
    "ROADMAP.md",
    "RELEASES.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
)

_INLINE_LINK_RE = re.compile(r"!?\[[^\]\n]*\]\(([^)\n]+)\)")
_REFERENCE_DEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s*(\S.*)$")
_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$")
_EXPLICIT_ID_RE = re.compile(r"\bid\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE)
_INLINE_CODE_RE = re.compile(r"`+[^`\n]*`+")
_LINK_TEXT_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s")
_NON_SLUG_RE = re.compile(r"[^\w\-\s]", re.UNICODE)


@dataclass(frozen=True, slots=True)
class LinkProblem:
    source: str
    line: int
    target: str
    reason: str

    def render(self) -> str:
        return f"{self.source}:{self.line}: {self.target!r}: {self.reason}"


def iter_public_markdown(root: Path) -> tuple[Path, ...]:
    files: set[Path] = set()
    for name in PUBLIC_ROOT_MARKDOWN:
        candidate = root / name
        if candidate.is_file():
            files.add(candidate)

    docs = root / "docs"
    if docs.is_dir():
        files.update(path for path in docs.rglob("*.md") if path.is_file())

    return tuple(sorted(files, key=lambda path: path.as_posix()))


def _strip_html_comments(line: str, *, in_comment: bool) -> tuple[str, bool]:
    searchable = list(line)
    if not in_comment:
        for match in _INLINE_CODE_RE.finditer(line):
            searchable[match.start() : match.end()] = "\0" * (match.end() - match.start())
    marker_line = "".join(searchable)

    visible: list[str] = []
    cursor = 0
    while cursor < len(line):
        if in_comment:
            end = line.find("-->", cursor)
            if end < 0:
                return "".join(visible), True
            cursor = end + 3
            in_comment = False
            continue

        start = marker_line.find("<!--", cursor)
        if start < 0:
            visible.append(line[cursor:])
            break
        visible.append(line[cursor:start])
        cursor = start + 4
        in_comment = True

    return "".join(visible), in_comment


def _outside_fenced_code(lines: Iterable[str]) -> Iterable[tuple[int, str]]:
    fence_char: str | None = None
    fence_len = 0
    in_html_comment = False
    for line_number, line in enumerate(lines, start=1):
        if fence_char is not None:
            stripped = line.lstrip()
            if stripped.startswith(fence_char * fence_len):
                run_len = len(stripped) - len(stripped.lstrip(fence_char))
                if run_len >= fence_len:
                    fence_char = None
                    fence_len = 0
            continue

        visible, in_html_comment = _strip_html_comments(line, in_comment=in_html_comment)
        stripped = visible.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            fence_char = stripped[0]
            fence_len = len(stripped) - len(stripped.lstrip(fence_char))
            continue
        yield line_number, visible


def _destination(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if value.startswith("<"):
        closing = value.find(">")
        if closing >= 0:
            return value[1:closing].strip()
    return value.split(maxsplit=1)[0]


def _targets_from_line(line: str) -> tuple[str, ...]:
    cleaned = _INLINE_CODE_RE.sub("", line)
    targets = [_destination(match.group(1)) for match in _INLINE_LINK_RE.finditer(cleaned)]
    reference = _REFERENCE_DEF_RE.match(cleaned)
    if reference is not None:
        targets.append(_destination(reference.group(1)))
    return tuple(target for target in targets if target)


def _github_slug(text: str) -> str:
    value = html.unescape(text.strip())
    value = _INLINE_CODE_RE.sub(lambda match: match.group(0).strip("`"), value)
    value = _LINK_TEXT_RE.sub(lambda match: match.group(1), value)
    value = _HTML_TAG_RE.sub("", value)
    value = value.lower()
    value = _NON_SLUG_RE.sub("", value)
    return _WHITESPACE_RE.sub("-", value.strip())


def _explicit_html_ids(line: str) -> tuple[str, ...]:
    cleaned = _INLINE_CODE_RE.sub("", line)
    ids: list[str] = []
    for tag in _HTML_TAG_RE.findall(cleaned):
        ids.extend(_EXPLICIT_ID_RE.findall(tag))
    return tuple(ids)


def _markdown_anchors(path: Path) -> frozenset[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    text = path.read_text(encoding="utf-8")
    for _, line in _outside_fenced_code(text.splitlines()):
        anchors.update(_explicit_html_ids(line))
        heading = _HEADING_RE.match(line)
        if heading is None:
            continue
        base = _github_slug(heading.group(2))
        if not base:
            continue
        duplicate_index = counts.get(base, 0)
        counts[base] = duplicate_index + 1
        anchor = base if duplicate_index == 0 else f"{base}-{duplicate_index}"
        anchors.add(anchor)
    return frozenset(anchors)


def _resolve_local_target(
    root: Path,
    source: Path,
    target: str,
) -> tuple[Path, str] | None:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or target.startswith("//"):
        return None

    fragment = unquote(parsed.fragment)
    raw_path = unquote(parsed.path)
    if not raw_path:
        candidate = source
    elif raw_path.startswith("/"):
        candidate = root / raw_path.lstrip("/")
    else:
        candidate = source.parent / raw_path

    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    try:
        candidate_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("target escapes repository root") from exc
    return candidate_resolved, fragment


def _check_target(*, root: Path, source: Path, line_number: int, target: str) -> LinkProblem | None:
    try:
        resolved = _resolve_local_target(root, source, target)
    except ValueError as exc:
        return LinkProblem(
            source=source.relative_to(root).as_posix(),
            line=line_number,
            target=target,
            reason=str(exc),
        )
    if resolved is None:
        return None

    candidate, fragment = resolved
    if not candidate.exists():
        return LinkProblem(
            source=source.relative_to(root).as_posix(),
            line=line_number,
            target=target,
            reason="local target does not exist",
        )

    if fragment and candidate.is_file() and candidate.suffix.lower() == ".md":
        anchors = _markdown_anchors(candidate)
        if fragment not in anchors:
            return LinkProblem(
                source=source.relative_to(root).as_posix(),
                line=line_number,
                target=target,
                reason=f"Markdown anchor {fragment!r} does not exist",
            )
    return None


def check_repository(root: Path) -> tuple[LinkProblem, ...]:
    root = root.resolve()
    problems: list[LinkProblem] = []
    for source in iter_public_markdown(root):
        text = source.read_text(encoding="utf-8")
        for line_number, line in _outside_fenced_code(text.splitlines()):
            for target in _targets_from_line(line):
                problem = _check_target(
                    root=root,
                    source=source,
                    line_number=line_number,
                    target=target,
                )
                if problem is not None:
                    problems.append(problem)
    return tuple(problems)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate repository-local links in MedScale public Markdown sources."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (defaults to the parent of scripts/)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.root).resolve()
    files = iter_public_markdown(root)
    if not files:
        print("docs link hygiene: FAIL (no public Markdown source files)", file=sys.stderr)
        return 2

    problems = check_repository(root)
    if problems:
        print(f"docs link hygiene: FAIL ({len(problems)} problem(s))", file=sys.stderr)
        for problem in problems:
            print(problem.render(), file=sys.stderr)
        return 1

    print(f"docs link hygiene: PASS ({len(files)} Markdown files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
