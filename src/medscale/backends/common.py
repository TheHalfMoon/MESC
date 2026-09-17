"""Shared backend contracts and error types.

Backends must remain optional. This module intentionally avoids importing
optional dependencies and keeps the layer usable by core MedScale installs.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "BackendError",
    "BackendMissingDependencyError",
    "BackendUnsupportedGrammarError",
    "BackendUnsupportedModelError",
    "GenerationConfig",
    "ModelBackend",
]


class BackendError(Exception):
    """Base backend surface failure."""


class BackendMissingDependencyError(BackendError):
    """An optional dependency is missing for the requested backend."""


class BackendUnsupportedGrammarError(BackendError):
    """A backend cannot enforce the requested grammar contract."""


class BackendUnsupportedModelError(BackendError):
    """A backend cannot serve the requested model."""


@dataclass(frozen=True)
class GenerationConfig:
    """Explicit generation configuration shared across backends."""

    backend_name: str
    backend_version: str = "0.1.0"
    do_sample: bool = False
    temperature: float = 0.0
    top_p: float = 1.0
    max_new_tokens: int = 512
    seed: int = 42
    grammar: str | None = None
    stop: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.backend_name.strip():
            raise ValueError("backend_name must be non-empty")
        if self.temperature < 0:
            raise ValueError("temperature must be >= 0")
        if self.seed < 0:
            raise ValueError("seed must be non-negative")


class ModelBackend:
    """Lightweight backend wrapper for optional execution."""

    def __init__(self, name: str, available: bool, missing_install_hint: str = "") -> None:
        self.name = name
        self.version = "0.1.0"
        self._available = available
        self.missing_install_hint = missing_install_hint

    def is_available(self) -> bool:
        """Return whether this backend can execute in the current environment."""
        return self._available

    def missing_reason(self) -> str:
        """Return a human-readable failure message when unavailable."""
        if self.missing_install_hint:
            return self.missing_install_hint
        return f"{self.name} backend is unavailable."
