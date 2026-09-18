"""Repository-local Python toolchain invariants."""

from __future__ import annotations

import tomllib
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_local_python_pin_matches_canonical_baseline() -> None:
    """Plain `uv sync` must resolve the ADR-0003 Python 3.11 baseline."""
    assert (_REPOSITORY_ROOT / ".python-version").read_text(encoding="utf-8") == "3.11\n"


def test_mypy_target_matches_local_python_pin() -> None:
    """The local interpreter baseline and static-analysis target must not drift."""
    configuration = tomllib.loads((_REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pin = (_REPOSITORY_ROOT / ".python-version").read_text(encoding="utf-8").strip()
    assert configuration["tool"]["mypy"]["python_version"] == pin
