"""Shared pytest lifecycle guards for MESC tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from _training_authorization_test_support import (
    restore_training_authorization_test_trust,
)


@pytest.fixture(autouse=True)
def _restore_training_authorization_trust_after_test() -> Iterator[None]:
    """Never leak synthetic authorization trust across test boundaries."""
    try:
        yield
    finally:
        restore_training_authorization_test_trust()
