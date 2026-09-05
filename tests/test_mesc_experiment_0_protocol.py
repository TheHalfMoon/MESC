from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "specs" / "mesc-experiment-0" / "experiment-config.template.json"
NOTEBOOK_PATH = ROOT / "notebooks" / "MESC_Experiment_0_Colab.ipynb"


def _notebook_code() -> str:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )


def test_experiment_0_config_template_is_fail_closed() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    assert config["schema_version"] == "MESC-EXPERIMENT-0-CONFIG-V1"
    assert config["status"] == "UNFROZEN_TEMPLATE_ONLY"
    assert config["candidate_roster"] == []
    assert config["network_policy"]["allow_model_acquisition"] is False
    assert config["network_policy"]["allow_dataset_acquisition"] is False
    assert all(value is None for value in config["authority_bindings"].values())
    assert config["sealed_evaluation_policy"]["tier3_item_access_by_research_process"] is False


def test_experiment_0_notebook_gates_before_repository_or_candidate_execution() -> None:
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    code_cells = [
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    ]

    config_gate_index = next(
        index for index, source in enumerate(code_cells) if "CONFIG_NOT_FROZEN" in source
    )
    repository_clone_index = next(
        index for index, source in enumerate(code_cells) if '"git", "clone"' in source
    )
    terminal_stop_index = next(
        index
        for index, source in enumerate(code_cells)
        if "CANDIDATE_EXECUTION_ADAPTERS_NOT_CANONICAL_YET" in source
    )

    assert config_gate_index < repository_clone_index < terminal_stop_index


def test_experiment_0_notebook_contains_no_training_path_or_frozen_model_id() -> None:
    code = _notebook_code()

    forbidden_training_tokens = (
        "optimizer.step(",
        ".backward(",
        "SFTTrainer(",
        "Trainer(",
        "get_peft_model(",
        "FastLanguageModel.from_pretrained(",
    )
    for token in forbidden_training_tokens:
        assert token not in code

    assert "Qwen/Qwen3.8-27B" not in code
    assert "meta-llama/" not in code


def test_experiment_0_notebook_requires_complete_mrl_binding_set() -> None:
    code = _notebook_code()
    required = [f"mrl_0{number}_" for number in range(801, 810)] + ["mrl_0899_"]

    for prefix in required:
        assert prefix in code
