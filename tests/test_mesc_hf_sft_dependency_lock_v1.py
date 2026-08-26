"""Regression tests for the canonical Hugging Face SFT dependency lock."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Final, cast

_REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
_EXPECTED_TRAINING_PINS: Final = (
    "accelerate==1.14.0",
    "bitsandbytes==0.50.1",
    "datasets==5.0.1",
    "peft==0.20.0",
    "torch==2.13.0",
    "transformers==5.15.1",
    "trl==1.10.0",
)


def _read_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as handle:
        return cast(dict[str, object], tomllib.load(handle))


def test_training_extra_is_exact_and_default_dependencies_stay_empty() -> None:
    project_document = _read_toml(_REPOSITORY_ROOT / "pyproject.toml")
    project = cast(dict[str, object], project_document["project"])
    optional_dependencies = cast(dict[str, object], project["optional-dependencies"])
    training_extra = cast(list[str], optional_dependencies["training-hf-sft"])

    assert project["dependencies"] == []
    assert tuple(training_extra) == _EXPECTED_TRAINING_PINS


def test_uv_lock_contains_exact_top_level_training_versions() -> None:
    lock_document = _read_toml(_REPOSITORY_ROOT / "uv.lock")
    packages = cast(list[dict[str, object]], lock_document["package"])

    for pin in _EXPECTED_TRAINING_PINS:
        name, expected_version = pin.split("==", maxsplit=1)
        versions = {
            cast(str, package["version"]) for package in packages if package.get("name") == name
        }
        assert versions == {expected_version}, (name, versions)
