"""Fail-closed static guard for the CW-001 Clinical Workspace boundary."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Sequence

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_SOURCE = _REPO_ROOT / "apps" / "workspace" / "src"
_FORBIDDEN_NETWORK_ROOTS = {
    "aiohttp",
    "boto3",
    "httpx",
    "requests",
    "socket",
    "urllib3",
}
_WRITE_ATTRIBUTES = {
    "mkdir",
    "rename",
    "replace",
    "rmdir",
    "touch",
    "unlink",
    "write_bytes",
    "write_text",
}


def _import_roots(tree: ast.AST) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".", 1)[0])
    return roots


def inspect_workspace_source(source_root: Path) -> list[str]:
    errors: list[str] = []
    if not source_root.is_dir():
        return [f"workspace source directory missing: {source_root}"]

    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(source_root)

        for root in sorted(_import_roots(tree)):
            if root == "medscale":
                errors.append(f"{relative}: Research Core import is forbidden during CW-001")
            elif root in _FORBIDDEN_NETWORK_ROOTS:
                errors.append(f"{relative}: network-capable import is forbidden: {root}")
            elif root != "medscale_workspace" and root not in sys.stdlib_module_names:
                errors.append(f"{relative}: undeclared third-party import is forbidden: {root}")

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and node.func.id == "open":
                errors.append(f"{relative}:{node.lineno}: file writes/opens are forbidden in CW-001")
            elif isinstance(node.func, ast.Attribute) and node.func.attr in _WRITE_ATTRIBUTES:
                errors.append(
                    f"{relative}:{node.lineno}: persistent filesystem mutation is forbidden "
                    f"in CW-001: {node.func.attr}"
                )
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default=str(_DEFAULT_SOURCE))
    namespace = parser.parse_args(argv)
    source_root = Path(str(namespace.source)).resolve()

    errors = inspect_workspace_source(source_root)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    print(f"CW-001 workspace boundary PASS: {source_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
