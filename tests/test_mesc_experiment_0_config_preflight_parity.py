from __future__ import annotations

import ast
import json
import math
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = ROOT / "notebooks" / "MESC_Experiment_0_Colab.ipynb"


def _notebook_code() -> str:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )


def _load_functions(*names: str) -> dict[str, Any]:
    tree = ast.parse(_notebook_code())
    wanted_constants = {
        "GIT_RE",
        "KEY_RE",
        "CANDIDATE_CLASSES",
        "SECRET_FIELDS",
        "SECRET_PATTERNS",
    }
    wanted_functions = set(names)
    module_body: list[ast.stmt] = []
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id in wanted_constants
                for target in node.targets
            )
        ) or (
            isinstance(node, ast.FunctionDef)
            and node.name in wanted_functions
        ):
            module_body.append(node)
    module = ast.Module(body=module_body, type_ignores=[])
    ast.fix_missing_locations(module)
    namespace: dict[str, Any] = {"json": json, "math": math, "re": re}
    exec(compile(module, str(NOTEBOOK_PATH), "exec"), namespace)
    return namespace


FUNCTIONS = _load_functions(
    "strict_json_loads",
    "validate_no_secret_bearing_config",
    "validate_git_identity",
    "validate_candidate_roster",
    "validate_non_negative_finite_number",
    "validate_budget_config",
    "validate_runtime_policy",
)
STRICT_JSON = cast(Callable[[str], object], FUNCTIONS["strict_json_loads"])
VALIDATE_SECRETS = cast(
    Callable[[str, object], None],
    FUNCTIONS["validate_no_secret_bearing_config"],
)
VALIDATE_GIT = cast(Callable[[object, str], None], FUNCTIONS["validate_git_identity"])
VALIDATE_ROSTER = cast(Callable[[object], None], FUNCTIONS["validate_candidate_roster"])
VALIDATE_NUMBER = cast(
    Callable[[object, str], None],
    FUNCTIONS["validate_non_negative_finite_number"],
)
VALIDATE_BUDGETS = cast(
    Callable[[dict[str, object]], None],
    FUNCTIONS["validate_budget_config"],
)
VALIDATE_RUNTIME = cast(Callable[[object], None], FUNCTIONS["validate_runtime_policy"])


def _candidate(**updates: object) -> dict[str, object]:
    candidate: dict[str, object] = {
        "candidate_id": "candidate-a",
        "candidate_revision": "a" * 40,
        "candidate_class": "SELECTABLE_FOUNDATION",
        "evidence_key": "candidate-a",
        "supported_input_modalities": ["text", "vision"],
    }
    candidate.update(updates)
    return candidate


def _budget_config() -> dict[str, object]:
    return {
        "resource_budget": {
            "max_gpu_hours": 1.0,
            "max_wall_hours": 2.0,
            "max_storage_bytes": 1024,
            "max_retries": 0,
        },
        "query_budget": {"max_adaptive_queries": 0},
        "result_exposure_budget": {
            "tier1_max_exposures": 1,
            "tier2_max_exposures": 1,
            "tier3_allowed_fields": [],
        },
    }


def _runtime_policy() -> dict[str, object]:
    return {
        "provider": "GOOGLE_COLAB",
        "require_hosted_gpu": True,
        "allowed_gpu_count": 1,
        "allowed_gpu_models": ["NVIDIA A100-SXM4-40GB"],
        "allow_unlisted_gpu_model": False,
    }


def test_strict_json_rejects_duplicate_keys_and_non_finite_constants() -> None:
    with pytest.raises(ValueError, match="duplicate JSON key"):
        STRICT_JSON('{"a":1,"a":2}')
    with pytest.raises(ValueError, match="non-finite JSON constant"):
        STRICT_JSON('{"a":NaN}')
    with pytest.raises(ValueError, match="non-finite JSON constant"):
        STRICT_JSON('{"a":Infinity}')


def test_config_secret_scan_rejects_secret_fields_and_serialized_tokens() -> None:
    with pytest.raises(ValueError, match="forbidden secret-bearing field"):
        VALIDATE_SECRETS('{"token":"placeholder"}', {"token": "placeholder"})
    with pytest.raises(ValueError, match="possible secret-bearing value"):
        VALIDATE_SECRETS(
            '{"note":"hf_abcdefghijklmnopqrstuvwxyz"}',
            {"note": "hf_abcdefghijklmnopqrstuvwxyz"},
        )


@pytest.mark.parametrize("value", ["main", "A" * 40, "a" * 39, "a" * 41, ""])
def test_git_identity_requires_lowercase_40_hex(value: str) -> None:
    with pytest.raises(ValueError, match="40-hex"):
        VALIDATE_GIT(value, "repository_sha")
    VALIDATE_GIT("a" * 40, "repository_sha")


def test_candidate_roster_rejects_moving_revision_and_duplicate_identity() -> None:
    with pytest.raises(ValueError, match="candidate_revision"):
        VALIDATE_ROSTER([_candidate(candidate_revision="main")])
    duplicate = _candidate(evidence_key="candidate-b")
    with pytest.raises(ValueError, match="duplicate candidate identity"):
        VALIDATE_ROSTER([_candidate(), duplicate])


def test_candidate_roster_requires_vision_for_selectable_foundation() -> None:
    with pytest.raises(ValueError, match="requires vision"):
        VALIDATE_ROSTER([_candidate(supported_input_modalities=["text"])])
    VALIDATE_ROSTER(
        [
            _candidate(
                candidate_class="REFERENCE_ONLY",
                supported_input_modalities=["text"],
            )
        ]
    )


@pytest.mark.parametrize("value", [True, -1, float("inf"), float("-inf"), float("nan")])
def test_numeric_budget_validator_rejects_non_finite_negative_or_boolean(value: object) -> None:
    with pytest.raises(ValueError, match="non-negative finite number"):
        VALIDATE_NUMBER(value, "budget")


def test_budget_config_rejects_invalid_numeric_ceiling() -> None:
    config = _budget_config()
    resource = cast(dict[str, object], config["resource_budget"])
    resource["max_gpu_hours"] = float("nan")
    with pytest.raises(ValueError, match="max_gpu_hours"):
        VALIDATE_BUDGETS(config)


def test_runtime_policy_requires_hosted_gpu_and_unique_model_allowlist() -> None:
    policy = _runtime_policy()
    policy["require_hosted_gpu"] = False
    with pytest.raises(ValueError, match="require_hosted_gpu"):
        VALIDATE_RUNTIME(policy)

    policy = _runtime_policy()
    policy["allowed_gpu_models"] = ["GPU-A", "GPU-A"]
    with pytest.raises(ValueError, match="duplicate model name"):
        VALIDATE_RUNTIME(policy)


def test_all_parity_gates_execute_before_repository_clone() -> None:
    code = _notebook_code()
    clone = code.index('["git", "clone"')
    for marker in (
        "strict_json_loads(config_text)",
        "validate_no_secret_bearing_config(config_text, config)",
        "CONFIG_REPOSITORY_IDENTITY_INVALID",
        "CONFIG_CANDIDATE_ROSTER_INVALID",
        "FROZEN_BUDGET_INVALID",
        "RUNTIME_POLICY_INVALID",
    ):
        assert code.index(marker) < clone


def test_preflight_remains_preparation_only_without_candidate_execution() -> None:
    code = _notebook_code()
    stop = code.index("CANDIDATE_EXECUTION_ADAPTERS_NOT_CANONICAL_YET")
    assert stop > code.index('["git", "clone"')
    for token in (
        "optimizer.step(",
        ".backward(",
        "SFTTrainer(",
        "get_peft_model(",
        "FastLanguageModel.from_pretrained(",
    ):
        assert token not in code
