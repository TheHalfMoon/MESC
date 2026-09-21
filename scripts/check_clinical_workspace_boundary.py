"""Fail-closed static guard for the Clinical Workspace boundary.

CW-001 introduced the guard and kept the Workspace package at zero dependencies.
CW-002 is a recorded capability expansion (ADR-0039 decision 7, amendment A1.12):
the guard now admits exactly ``sqlite3``, ``hashlib``, ``hmac``, ``secrets`` and one
restricted ``cryptography`` module for the AEAD primitive, and adds the CW-002
structural rules that make the expansion mechanical rather than conventional:

* ``sqlite3`` is imported only by ``storage.py``;
* ``cryptography`` is imported only by ``aead.py``, from the AEAD module only;
* key derivation never imports ``cryptography``, and the reserved ``scrypt`` path is
  absent from the Workspace sources entirely (A1.1/A1.2);
* the store path is resolved by exactly one module, and every ``sqlite3.connect``
  call takes its path from that resolver (ADR-0039 decision 7);
* the nonce size is a single 96-bit constant used by every nonce call (A1.3);
* the production key-provider resolver cannot reach the in-memory test provider.

Network, process, dynamic-import and persistent-mutation prohibitions are unchanged.
"""

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
    "hashlib",
    "hmac",
    "json",
    "secrets",
    "sqlite3",
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

_ALLOWED_THIRD_PARTY_MODULES = {
    "cryptography.hazmat.primitives.ciphers.aead",
}
_STORAGE_MODULE = "storage.py"
_AEAD_MODULE = "aead.py"
_STORE_PATH_MODULE = "store_path.py"
_KEY_DERIVATION_MODULE = "keyderive.py"
_STORE_PATH_RESOLVER = "resolve_workspace_store_path"
_PLATFORM_PROVIDER_RESOLVER = "resolve_platform_key_provider"
_IN_MEMORY_TEST_PROVIDER = "InMemoryTestKeyProvider"
_NONCE_CONSTANT = "NONCE_SIZE_BYTES"
_ADMITTED_NONCE_SIZE_BYTES = 12
_RESERVED_PASSWORD_KDF = "scrypt"
_PRIVATE_CONNECTION_ATTRIBUTE = "_connection"

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
_FORBIDDEN_IMPORTING_PRIMITIVES = {
    "breakpoint",
    "help",
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
    # Frame introspection reaches a module's real globals and builtins through an
    # exception or a suspended frame without naming ``__builtins__`` directly.
    "__traceback__",
    "ag_frame",
    "cr_frame",
    "f_back",
    "f_builtins",
    "f_code",
    "f_globals",
    "f_locals",
    "gi_frame",
    "tb_frame",
    "tb_next",
}
_FORBIDDEN_CAPABILITY_REFERENCES = (
    _FORBIDDEN_CALL_PRIMITIVES
    | _FORBIDDEN_REFLECTION_PRIMITIVES
    | _FORBIDDEN_IMPORTING_PRIMITIVES
    | _FORBIDDEN_NAME_REFERENCES
)


def _literal_string(node: ast.expr) -> str | None:
    """Return the constant string value of an expression, folding ``+`` concatenation."""

    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_string(node.left)
        right = _literal_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


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
    if isinstance(value, ast.Subscript):
        return _literal_string(value.slice) in _FORBIDDEN_CAPABILITY_REFERENCES
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


def _imported_modules(tree: ast.AST) -> set[str]:
    """Return every dotted module path named by an import statement."""

    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _resolver_bound_names(tree: ast.AST) -> set[str]:
    """Return local names bound to a call of the single store-path resolver."""

    names: set[str] = set()
    for node in ast.walk(tree):
        binding = _bindings(node)
        if binding is None:
            continue
        targets, value = binding
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == _STORE_PATH_RESOLVER
        ):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _function_definitions(tree: ast.AST, name: str) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name
    ]


def _module_constants(tree: ast.AST) -> dict[str, object]:
    constants: dict[str, object] = {}
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Constant):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                constants[target.id] = node.value.value
    return constants


def inspect_workspace_source(source_root: Path) -> list[str]:
    errors: list[str] = []
    if not source_root.is_dir():
        return [f"workspace source directory missing: {source_root}"]

    trees: dict[Path, ast.AST] = {}
    for path in sorted(source_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        trees[path] = tree
        relative = path.relative_to(source_root)

        for module in sorted(_imported_modules(tree)):
            root = module.split(".", 1)[0]
            if root == "medscale":
                errors.append(f"{relative}: Research Core import is forbidden")
            elif root in _FORBIDDEN_NETWORK_ROOTS:
                errors.append(f"{relative}: network-capable import is forbidden: {root}")
            elif root in _FORBIDDEN_ESCAPE_ROOTS:
                errors.append(f"{relative}: boundary escape import is forbidden: {root}")
            elif root == "medscale_workspace":
                continue
            elif root in sys.stdlib_module_names and root not in _ALLOWED_STDLIB_ROOTS:
                errors.append(f"{relative}: stdlib import is not allowlisted: {root}")
            elif root not in sys.stdlib_module_names:
                if module in _ALLOWED_THIRD_PARTY_MODULES:
                    continue
                errors.append(f"{relative}: undeclared third-party import is forbidden: {module}")

        errors.extend(_capability_errors(relative, tree))
    errors.extend(_cw002_structure_errors(source_root, trees))
    return errors


def _cw002_structure_errors(source_root: Path, trees: dict[Path, ast.AST]) -> list[str]:
    """Report violations of the CW-002 capability-expansion rules."""

    errors: list[str] = []
    relative_by_name = {path.name: path.relative_to(source_root) for path in trees}
    storage_path = relative_by_name.get(_STORAGE_MODULE)
    aead_path = relative_by_name.get(_AEAD_MODULE)
    store_path_path = relative_by_name.get(_STORE_PATH_MODULE)
    key_derivation_path = relative_by_name.get(_KEY_DERIVATION_MODULE)

    for name, relative in (
        (_STORAGE_MODULE, storage_path),
        (_AEAD_MODULE, aead_path),
        (_STORE_PATH_MODULE, store_path_path),
        (_KEY_DERIVATION_MODULE, key_derivation_path),
    ):
        if relative is None:
            errors.append(f"CW-002 requires {name}")

    resolver_definitions: list[str] = []
    connect_calls = 0

    for path, tree in sorted(trees.items(), key=lambda item: str(item[0])):
        relative = path.relative_to(source_root)
        modules = _imported_modules(tree)
        imports_sqlite = any(module == "sqlite3" for module in modules)
        imports_cipher = any(module.startswith("cryptography") for module in modules)
        if imports_sqlite and relative.name != _STORAGE_MODULE:
            errors.append(
                f"{relative}: sqlite3 may be imported only by {_STORAGE_MODULE} "
                "(ADR-0039 decision 7)"
            )
        if relative.name == _STORAGE_MODULE and not imports_sqlite:
            errors.append(f"{relative}: {_STORAGE_MODULE} must import sqlite3")
        if imports_cipher and relative.name != _AEAD_MODULE:
            errors.append(f"{relative}: cryptography may be imported only by {_AEAD_MODULE}")
        if relative.name == _AEAD_MODULE and not imports_cipher:
            errors.append(f"{relative}: {_AEAD_MODULE} must import the AEAD primitive")
        if relative.name == _STORE_PATH_MODULE and (imports_sqlite or imports_cipher):
            errors.append(
                f"{relative}: the store-path resolver must not import storage or cipher providers"
            )
        if relative.name == _KEY_DERIVATION_MODULE and imports_cipher:
            errors.append(
                f"{relative}: key derivation must stay in reviewed code and must not "
                "import cryptography (ADR-0039 decision 5)"
            )
        if relative.name != _STORAGE_MODULE and any(
            isinstance(node, ast.Attribute) and node.attr == _PRIVATE_CONNECTION_ATTRIBUTE
            for node in ast.walk(tree)
        ):
            errors.append(
                f"{relative}: only {_STORAGE_MODULE} may touch the private store connection; "
                "every other module must use the public store API"
            )

        source_text = path.read_text(encoding="utf-8")
        if _RESERVED_PASSWORD_KDF in source_text:
            errors.append(f"{relative}: the reserved password KDF is not admitted in CW-002 (A1.2)")

        if _function_definitions(tree, _STORE_PATH_RESOLVER):
            resolver_definitions.append(path.name)

        bound_resolver_names = _resolver_bound_names(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = node.func
            if not isinstance(function, ast.Attribute) or function.attr != "connect":
                continue
            if not isinstance(function.value, ast.Name) or function.value.id != "sqlite3":
                continue
            connect_calls += 1
            if relative.name != _STORAGE_MODULE:
                errors.append(
                    f"{relative}:{node.lineno}: sqlite3.connect is admitted only in "
                    f"{_STORAGE_MODULE}"
                )
                continue
            argument = node.args[0] if node.args else None
            direct = (
                isinstance(argument, ast.Call)
                and isinstance(argument.func, ast.Name)
                and argument.func.id == _STORE_PATH_RESOLVER
            )
            bound = isinstance(argument, ast.Name) and argument.id in bound_resolver_names
            if not (direct or bound):
                errors.append(
                    f"{relative}:{node.lineno}: sqlite3.connect must take its path from "
                    f"{_STORE_PATH_RESOLVER} (ADR-0039 decision 7)"
                )

        if relative.name == _AEAD_MODULE:
            constants = _module_constants(tree)
            if constants.get(_NONCE_CONSTANT) != _ADMITTED_NONCE_SIZE_BYTES:
                errors.append(
                    f"{relative}: {_NONCE_CONSTANT} must be declared as "
                    f"{_ADMITTED_NONCE_SIZE_BYTES} (A1.3)"
                )
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                is_token_bytes = (
                    isinstance(function, ast.Attribute) and function.attr == "token_bytes"
                )
                if not is_token_bytes:
                    continue
                argument = node.args[0] if node.args else None
                if not (isinstance(argument, ast.Name) and argument.id == _NONCE_CONSTANT):
                    errors.append(
                        f"{relative}:{node.lineno}: nonce generation must use "
                        f"{_NONCE_CONSTANT} (A1.3)"
                    )

        if relative.name == "keyprovider.py":
            for definition in _function_definitions(tree, _PLATFORM_PROVIDER_RESOLVER):
                body_names = {
                    node.id for node in ast.walk(definition) if isinstance(node, ast.Name)
                }
                if _IN_MEMORY_TEST_PROVIDER in body_names:
                    errors.append(
                        f"{relative}:{definition.lineno}: the production provider resolver "
                        f"must not reach {_IN_MEMORY_TEST_PROVIDER}"
                    )

    if resolver_definitions != [_STORE_PATH_MODULE]:
        observed = ", ".join(resolver_definitions) or "none"
        errors.append(
            f"{_STORE_PATH_RESOLVER} must be defined exactly once in {_STORE_PATH_MODULE}; "
            f"observed: {observed}"
        )
    if connect_calls == 0:
        errors.append("no admitted sqlite3.connect call was found in the workspace sources")
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
                    f"in the Clinical Workspace: {node.func.id}"
                )
            elif node.func.id in _FORBIDDEN_REFLECTION_PRIMITIVES:
                reported_callees.add(id(node.func))
                errors.append(
                    f"{relative}:{node.lineno}: reflective capability access is forbidden "
                    f"in the Clinical Workspace: {node.func.id}"
                )
            elif node.func.id in _FORBIDDEN_IMPORTING_PRIMITIVES:
                reported_callees.add(id(node.func))
                errors.append(
                    f"{relative}:{node.lineno}: runtime code-importing builtin is forbidden "
                    f"in the Clinical Workspace: {node.func.id}"
                )
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in _WRITE_ATTRIBUTES:
                errors.append(
                    f"{relative}:{node.lineno}: persistent filesystem mutation is forbidden "
                    f"in the Clinical Workspace: {node.func.attr}"
                )
        else:
            errors.append(
                f"{relative}:{node.lineno}: call shape cannot be verified fail-closed in the "
                f"Clinical Workspace: {type(node.func).__name__}"
            )

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_ATTRIBUTE_REFERENCES:
            errors.append(
                f"{relative}:{node.lineno}: object-graph capability attribute is forbidden in "
                f"the Clinical Workspace: {node.attr}"
            )
            continue
        if not isinstance(node, ast.Name) or node.id not in _FORBIDDEN_CAPABILITY_REFERENCES:
            continue
        if id(node) in reported_callees:
            continue
        errors.append(
            f"{relative}:{node.lineno}: forbidden capability reference is not allowed in the "
            f"Clinical Workspace: {node.id}"
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

    print(f"CW-002 workspace boundary PASS: {source_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
