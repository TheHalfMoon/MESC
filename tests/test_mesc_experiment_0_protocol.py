from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "specs" / "mesc-experiment-0" / "experiment-config.template.json"
NOTEBOOK_PATH = ROOT / "notebooks" / "MESC_Experiment_0_Colab.ipynb"


def _notebook_code() -> str:
    """Return all notebook code cells as one searchable source string."""
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    )


def test_experiment_0_config_template_is_fail_closed() -> None:
    """The committed template cannot be mistaken for execution authority."""
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert config["schema_version"] == "MESC-EXPERIMENT-0-CONFIG-V1"
    assert config["status"] == "UNFROZEN_TEMPLATE_ONLY"
    assert config["candidate_roster"] == []
    assert config["network_policy"]["allow_model_acquisition"] is False
    assert config["network_policy"]["allow_dataset_acquisition"] is False
    assert all(value is None for value in config["authority_bindings"].values())
    sealed = config["sealed_evaluation_policy"]
    assert sealed["tier3_item_access_by_research_process"] is False


def test_experiment_0_notebook_gates_before_repository_or_candidate_execution() -> None:
    """Frozen-config and MRL gates occur before repository or candidate access."""
    notebook = json.loads(NOTEBOOK_PATH.read_text(encoding="utf-8"))
    code_cells = [
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell.get("cell_type") == "code"
    ]
    config_gate_index = next(
        i for i, source in enumerate(code_cells) if "CONFIG_NOT_FROZEN" in source
    )
    repository_clone_index = next(
        i for i, source in enumerate(code_cells) if '"git", "clone"' in source
    )
    terminal_stop_index = next(
        i
        for i, source in enumerate(code_cells)
        if "CANDIDATE_EXECUTION_ADAPTERS_NOT_CANONICAL_YET" in source
    )
    assert config_gate_index < repository_clone_index < terminal_stop_index


def test_experiment_0_notebook_contains_no_training_path_or_frozen_model_id() -> None:
    """Preparation code has no training primitive or hard-coded foundation identity."""
    code = _notebook_code()
    for token in (
        "optimizer.step(",
        ".backward(",
        "SFTTrainer(",
        "Trainer(",
        "get_peft_model(",
        "FastLanguageModel.from_pretrained(",
    ):
        assert token not in code
    assert "Qwen/Qwen3.8-27B" not in code
    assert "meta-llama/" not in code


def test_experiment_0_notebook_requires_complete_mrl_binding_set() -> None:
    """MRL-0801 through MRL-0809 plus MRL-0899 are explicit gates."""
    code = _notebook_code()
    required = [f"mrl_0{number}_" for number in range(801, 810)] + ["mrl_0899_"]
    for prefix in required:
        assert prefix in code


def test_runtime_policy_is_validated_before_gpu_policy_access() -> None:
    """Malformed runtime policy fails before GPU-policy values are used."""
    code = _notebook_code()
    validation = code.index("if not isinstance(runtime_policy, dict):")
    gpu_count_read = code.index('allowed_gpu_count = runtime_policy.get("allowed_gpu_count")')
    runtime_use = code.index('expected_count = runtime_policy["allowed_gpu_count"]')
    assert validation < gpu_count_read < runtime_use


def test_environment_manifest_avoids_pip_freeze_and_direct_urls() -> None:
    """Environment evidence stores package name/version metadata only."""
    code = _notebook_code()
    assert "pip freeze" not in code
    assert '"packages": packages' in code
    assert 'distribution.metadata.get("Name")' in code
    assert "direct_url" not in code
