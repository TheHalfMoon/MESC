from __future__ import annotations

from pathlib import Path

SOURCE = Path("src/medscale/mesc/_training_hf_local_sft_backend_v1.py")
TEST = Path("tests/test_mesc_training_hf_local_sft_backend_v1.py")
SPEC = Path("specs/mesc-hf-local-sft-backend-v1/README.md")


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match in {path}, found {count}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


replace_once(
    SOURCE,
    "            finished_at = _utc_now()\n            summary = {",
    "            publication_ready_at = _utc_now()\n            summary = {",
)
replace_once(
    SOURCE,
    '                "finished_at": finished_at,\n',
    '                "publication_ready_at": publication_ready_at,\n',
)
replace_once(
    SOURCE,
    "            )\n            staging = None\n            return TrainingBackendResult(\n",
    "            )\n            staging = None\n            finished_at = _utc_now()\n            return TrainingBackendResult(\n",
)
replace_once(
    TEST,
    '    assert summary["finished_at"] == result.finished_at\n',
    '    assert "finished_at" not in summary\n'
    '    assert summary["publication_ready_at"] >= result.started_at\n'
    '    assert result.finished_at >= summary["publication_ready_at"]\n',
)
replace_once(
    SPEC,
    "- backend success disposition and exact start/finish timestamps; and\n",
    "- backend success disposition, exact start timestamp, and pre-publication\n"
    "  `publication_ready_at` timestamp; and\n",
)
replace_once(
    SPEC,
    "commit, `training-summary.json` already binds `disposition = SUCCEEDED`, the exact backend\nstart/finish timestamps, and the repository-relative result parent. If an asynchronous\n",
    "commit, `training-summary.json` already binds `disposition = SUCCEEDED`, the exact backend\nstart timestamp, the pre-publication `publication_ready_at` timestamp, and the\nrepository-relative result parent. The returned `TrainingBackendResult.finished_at` is\ncaptured only after the no-replace publication commit succeeds. If an asynchronous\n",
)
replace_once(
    SPEC,
    "The backend records actual UTC whole-second start/finish timestamps.\n",
    "The backend records actual UTC whole-second timestamps. `started_at` marks backend entry,\n`publication_ready_at` in the immutable summary marks the last pre-publication completion\npoint, and returned `finished_at` is captured only after atomic publication succeeds.\n",
)
