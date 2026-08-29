"""MRL-0799 exact-head qualification for the complete MRL machine-state surface."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from medscale.mesc._mrl_machine_state_generation_v1 import generate_machine_state

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_EXPECTED_OUTPUTS = {
    "CAPABILITY_MATRIX.json",
    "PROJECT_STATE.json",
    "RESEARCH_PROGRAM_INDEX.json",
}


def _git_text(*arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=_REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def test_machine_state_exact_head_qualification(tmp_path: Path) -> None:
    """Prove all projections bind the exact tested Git HEAD/tree and reproduce exactly."""
    expected_commit = _git_text("rev-parse", "HEAD")
    expected_tree = _git_text("rev-parse", "HEAD^{tree}")
    output_dir = tmp_path / "machine-state"

    rendered = generate_machine_state(_REPOSITORY_ROOT, output_dir)

    assert rendered.commit_sha == expected_commit
    assert rendered.tree_sha == expected_tree
    assert {filename for filename, _ in rendered.files()} == _EXPECTED_OUTPUTS

    for filename, payload in rendered.files():
        projection = json.loads(payload)
        assert isinstance(projection, dict), filename
        assert projection["repository"] == {
            "commit_sha": expected_commit,
            "tree_sha": expected_tree,
        }
        assert projection["projection_kind"] == "DERIVED_NON_AUTHORITATIVE"
        assert projection["can_authorize"] is False
        assert (output_dir / filename).read_bytes() == payload

    checked = generate_machine_state(_REPOSITORY_ROOT, output_dir, check=True)
    assert checked == rendered
