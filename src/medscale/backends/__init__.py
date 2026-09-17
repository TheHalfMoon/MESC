"""Backend package entry point.

Importing this package never fails.

Backends must gate optional dependencies at their own constructors and raise
explicit, actionable errors instead of failing during core package import.
"""

from __future__ import annotations

from medscale.backends.common import (
    BackendError,
    BackendMissingDependencyError,
    BackendUnsupportedGrammarError,
    BackendUnsupportedModelError,
    GenerationConfig,
    ModelBackend,
)

__all__ = [
    "BackendError",
    "BackendMissingDependencyError",
    "BackendUnsupportedGrammarError",
    "BackendUnsupportedModelError",
    "GenerationConfig",
    "ModelBackend",
]
