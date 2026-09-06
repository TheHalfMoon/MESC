from __future__ import annotations

import ast
import importlib.util
import json
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

ROOT = "mesc-experiment-0-evidence"
REPO_ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = REPO_ROOT / "notebooks" / "MESC_Experiment_0_Colab.ipynb"


def _load_module(path: Path, name: str) -> ModuleType:
    """Load a repository test module without requiring tests to be a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURES = _load_module(
    Path(__file__).with_name("test_verify_mesc_experiment_0_evidence.py"),
    "mesc_exp0_frozen_identity_fixtures",
)
INTEGRITY = _load_module(
    Path(__file__).with_name("test_verify_mesc_experiment_0_evidence_integrity.py"),
    "mesc_exp0_frozen_identity_integrity",
)
VERIFIER = FIXTURES.VERIFIER


def _write_mutated_result_bundle(
    tmp_path: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> Path:
    """Create one synthetic bundle whose lane result is mutated before verification."""
    docs = FIXTURES._base_docs()
    result_path, result = INTEGRITY._synthetic_bound_result(docs)
    mutate(result)
    docs[result_path] = FIXTURES._json_bytes(result)
    bundle = tmp_path / "frozen-identity-negative.zip"
    FIXTURES._write_bundle(bundle, docs)
    return bundle


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dataset_id", "unfrozen-dataset", "dataset/split/tier binding is not frozen"),
        ("split_id", "unfrozen-split", "dataset/split/tier binding is not frozen"),
        ("held_out_tier", "unfrozen-tier", "dataset/split/tier binding is not frozen"),
        ("evaluator_id", "unfrozen-evaluator", "evaluator binding is not frozen"),
        ("scoring_policy_id", "unfrozen-scoring", "scoring-policy binding is not frozen"),
        ("prompt_template_id", "unfrozen-prompt", "prompt-template binding is not frozen"),
        (
            "generation_config_id",
            "unfrozen-generation",
            "generation-config binding is not frozen",
        ),
    ],
)
def test_verify_rejects_each_unfrozen_lane_identity(
    tmp_path: Path,
    field: str,
    value: str,
    message: str,
) -> None:
    """Every lane identity must resolve to the exact frozen Experiment-0 config."""

    def mutate(result: dict[str, Any]) -> None:
        result[field] = value

    bundle = _write_mutated_result_bundle(tmp_path, mutate)
    with pytest.raises(VERIFIER.EvidenceError, match=message):
        VERIFIER.verify(str(bundle))


@pytest.mark.parametrize("field", ["split_id", "held_out_tier"])
def test_verify_rejects_missing_split_or_tier_binding(tmp_path: Path, field: str) -> None:
    """Split and held-out tier metadata are mandatory on every lane result."""

    def mutate(result: dict[str, Any]) -> None:
        result.pop(field)

    bundle = _write_mutated_result_bundle(tmp_path, mutate)
    with pytest.raises(VERIFIER.EvidenceError, match=rf"missing fields \['{field}'\]"):
        VERIFIER.verify(str(bundle))


@pytest.mark.parametrize("field", ["split_id", "held_out_tier"])
def test_verify_rejects_blank_split_or_tier_binding(tmp_path: Path, field: str) -> None:
    """Present-but-blank split or tier metadata cannot satisfy the frozen identity contract."""

    def mutate(result: dict[str, Any]) -> None:
        result[field] = "   "

    bundle = _write_mutated_result_bundle(tmp_path, mutate)
    with pytest.raises(VERIFIER.EvidenceError, match=rf"{field}: expected non-empty string"):
        VERIFIER.verify(str(bundle))


def _notebook_code() -> str:
    """Return all notebook code cells as one source string."""
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )


def _load_notebook_identity_validator() -> Callable[[object, tuple[str, ...], str], None]:
    """Extract only the pure frozen-identity validator from the Colab notebook."""
    tree = ast.parse(_notebook_code())
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "validate_frozen_identity_records"
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {}
    exec(compile(module, str(NOTEBOOK_PATH), "exec"), namespace)
    return namespace["validate_frozen_identity_records"]


NOTEBOOK_VALIDATE_IDENTITIES = _load_notebook_identity_validator()


def test_notebook_identity_validator_accepts_complete_dataset_tuple() -> None:
    """The Colab gate accepts a complete unique dataset/split/tier identity tuple."""
    NOTEBOOK_VALIDATE_IDENTITIES(
        [{"dataset_id": "dataset-a", "split_id": "split-a", "held_out_tier": "tier-1"}],
        ("dataset_id", "split_id", "held_out_tier"),
        "dataset_identities",
    )


@pytest.mark.parametrize("missing_field", ["dataset_id", "split_id", "held_out_tier"])
def test_notebook_identity_validator_rejects_missing_dataset_tuple_field(
    missing_field: str,
) -> None:
    """The Colab gate fails closed when a frozen dataset tuple is incomplete."""
    record = {"dataset_id": "dataset-a", "split_id": "split-a", "held_out_tier": "tier-1"}
    record.pop(missing_field)
    with pytest.raises(ValueError, match=missing_field):
        NOTEBOOK_VALIDATE_IDENTITIES(
            [record],
            ("dataset_id", "split_id", "held_out_tier"),
            "dataset_identities",
        )


@pytest.mark.parametrize(
    ("records", "key_fields", "label"),
    [
        ([{}], ("evaluator_id",), "evaluator_identities"),
        ([{}], ("scoring_policy_id",), "scoring_policy_identities"),
        ([{}], ("prompt_template_id",), "prompt_template_identities"),
        ([{}], ("generation_config_id",), "generation_configs"),
    ],
)
def test_notebook_identity_validator_rejects_missing_single_identities(
    records: list[dict[str, str]],
    key_fields: tuple[str, ...],
    label: str,
) -> None:
    """The Colab gate validates every frozen evaluator/scoring/prompt/generation identity."""
    with pytest.raises(ValueError, match=key_fields[0]):
        NOTEBOOK_VALIDATE_IDENTITIES(records, key_fields, label)


def test_notebook_identity_validator_rejects_duplicate_dataset_tuple() -> None:
    """Duplicate frozen dataset tuples are ambiguous and fail closed before runtime access."""
    record = {"dataset_id": "dataset-a", "split_id": "split-a", "held_out_tier": "tier-1"}
    with pytest.raises(ValueError, match="duplicate frozen identity"):
        NOTEBOOK_VALIDATE_IDENTITIES(
            [record, dict(record)],
            ("dataset_id", "split_id", "held_out_tier"),
            "dataset_identities",
        )


def test_notebook_wires_all_frozen_identity_requirements_before_clone() -> None:
    """The Colab control plane binds every evaluation identity before repository access."""
    code = _notebook_code()
    validation = code.index("FROZEN_IDENTITY_REQUIREMENTS")
    identity_gate = code.index("CONFIG_FROZEN_IDENTITY_INVALID")
    clone = code.index('["git", "clone"')
    assert validation < identity_gate < clone
    for field in (
        "dataset_id",
        "split_id",
        "held_out_tier",
        "evaluator_id",
        "scoring_policy_id",
        "prompt_template_id",
        "generation_config_id",
    ):
        assert field in code
