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
_FORBIDDEN_REFLECTION_PRIMITIVES = {
    "delattr",
    "getattr",
    "globals",
    "locals",
    "setattr",
    "vars",
}
_FORBIDDEN_NAME_REFERENCES = {
    "__builtins__",
}
# Attribute names that reconstruct a capability from the object graph even though
# the code never names the capability directly. Ordinary dunder use that a normal
# class-based module needs (``__init__``, ``__all__``, ``__name__``) is unaffected.
_FORBIDDEN_ATTRIBUTE_REFERENCES = {
    "__bases__",
    "__base__",
    "__builtins__",
    "__class__",
    "__closure__",
    "__code__",
    "__delattr__",
    "__dict__",
    "__func__",
    "__getattr__",
    "__getattribute__",
    "__globals__",
    "__import__",
    "__loader__",
    "__mro__",
    "__reduce__",
    "__reduce_ex__",
    "__self__",
    "__setattr__",
    "__spec__",
    "__subclasses__",
}
_FORBIDDEN_CAPABILITY_REFERENCES = (
    _FORBIDDEN_CALL_PRIMITIVES | _FORBIDDEN_REFLECTION_PRIMITIVES | _FORBIDDEN_NAME_REFERENCES
)


def _bindings(node: ast.AST) -> tuple[list[ast.expr], ast.expr] | None:
    """Return the (targets, value) pair of a simple local binding, if any."""

    if isinstance(node, ast.Assign):
        return list(node.targets), node.value
    if isinstance(node, ast.AnnAssign) and node.value is not None:
        return [node.target], node.value
    if isinstance(node, ast.NamedExpr):
        return [node.target], node.value
    return None


def _resolves_to_capability(value: ast.expr, aliases: set[str]) -> bool:
    """Return True when a bound value statically resolves to a capability."""

    if isinstance(value, ast.Name):
        return value.id in _FORBIDDEN_CAPABILITY_REFERENCES or value.id in aliases
    if isinstance(value, ast.Subscript) and isinstance(value.slice, ast.Constant):
        return value.slice.value in _FORBIDDEN_CAPABILITY_REFERENCES
    return False


def _forbidden_call_aliases(tree: ast.AST) -> set[str]:
    """Collect local names that resolve to a forbidden capability indirectly.

    Taint propagates from a capability name and from a literal dictionary lookup
    of a capability name (for example ``table["__import__"]``) through simple
    bindings, so the eventual call through the alias is still rejected.
    """

    aliases: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            binding = _bindings(node)
            if binding is None:
                continue
            targets, value = binding
            if not _resolves_to_capability(value, aliases):
                continue
            for target in targets:
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

        errors.extend(_capability_errors(relative, tree))
    return errors


def _capability_errors(relative: Path, tree: ast.AST) -> list[str]:
    """Report dynamic capability acquisition that cannot be verified fail-closed."""

    errors: list[str] = []
    forbidden_aliases = _forbidden_call_aliases(tree)
    reported_callees: set[int] = set()

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            if node.func.id in _FORBIDDEN_CALL_PRIMITIVES or node.func.id in forbidden_aliases:
                reported_callees.add(id(node.func))
                errors.append(
                    f"{relative}:{node.lineno}: dynamic import/code/file primitive is forbidden "
                    f"in CW-001: {node.func.id}"
                )
            elif node.func.id in _FORBIDDEN_REFLECTION_PRIMITIVES:
                reported_callees.add(id(node.func))
                errors.append(
                    f"{relative}:{node.lineno}: reflective capability access is forbidden "
                    f"in CW-001: {node.func.id}"
                )
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in _WRITE_ATTRIBUTES:
                errors.append(
                    f"{relative}:{node.lineno}: persistent filesystem mutation is forbidden "
                    f"in CW-001: {node.func.attr}"
                )
        else:
            errors.append(
                f"{relative}:{node.lineno}: call shape cannot be verified fail-closed in CW-001: "
                f"{type(node.func).__name__}"
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_ATTRIBUTE_REFERENCES:
            errors.append(
                f"{relative}:{node.lineno}: object-graph capability attribute is forbidden in "
                f"CW-001: {node.attr}"
            )
            continue
        if not isinstance(node, ast.Name) or node.id not in _FORBIDDEN_CAPABILITY_REFERENCES:
            continue
        if id(node) in reported_callees:
            continue
        errors.append(
            f"{relative}:{node.lineno}: forbidden capability reference is not allowed in CW-001: "
            f"{node.id}"
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
