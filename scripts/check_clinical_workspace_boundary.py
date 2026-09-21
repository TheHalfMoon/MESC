"""Fail-closed static guard for the CW-001 Clinical Workspace boundary."""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Sequence
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_SOURCE = _REPO_ROOT / "apps" / "workspace" / "src"
_ALLOWED_STDLIB_ROOTS = {
    "__future__",
    "dataclasses",
    "enum",
    "json",
    "uuid",
}
_FORBIDDEN_ESCAPE_ROOTS = {
    "ctypes",
    "importlib",
    "multiprocessing",
    "os",
    "subprocess",
}
_FORBIDDEN_NETWORK_ROOTS = {
    "aiohttp",
    "boto3",
    "ftplib",
    "http",
    "httpx",
    "requests",
    "smtplib",
    "socket",
    "telnetlib",
    "urllib",
    "urllib3",
    "xmlrpc",
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

_FORBIDDEN_CALL_PRIMITIVES = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "open",
}


def _forbidden_call_aliases(tree: ast.AST) -> set[str]:
    aliases: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Name):
                continue
            if node.value.id not in _FORBIDDEN_CALL_PRIMITIVES and node.value.id not in aliases:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases.add(target.id)
                    changed = True
    return aliases



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
            elif root in _FORBIDDEN_ESCAPE_ROOTS:
                errors.append(f"{relative}: boundary escape import is forbidden: {root}")
            elif root == "medscale_workspace":
                continue
            elif root in sys.stdlib_module_names and root not in _ALLOWED_STDLIB_ROOTS:
                errors.append(f"{relative}: stdlib import is not allowlisted for CW-001: {root}")
            elif root not in sys.stdlib_module_names:
                errors.append(f"{relative}: undeclared third-party import is forbidden: {root}")

        forbidden_aliases = _forbidden_call_aliases(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if isinstance(node.func, ast.Name) and (
                node.func.id in _FORBIDDEN_CALL_PRIMITIVES or node.func.id in forbidden_aliases
            ):
                errors.append(
                    f"{relative}:{node.lineno}: dynamic import/code/file primitive is forbidden "
                    f"in CW-001: {node.func.id}"
                )
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
