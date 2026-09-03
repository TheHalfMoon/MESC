from __future__ import annotations

import re
from pathlib import Path

_WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "release.yml"
_JOB_HEADER_RE = re.compile(r"^  [a-z0-9-]+:\s*$", re.MULTILINE)
_PUBLISH_ACTION = "pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33"
_DOWNLOAD_ACTION = "actions/download-artifact@3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c"


def _workflow_text() -> str:
    return _WORKFLOW.read_text(encoding="utf-8")


def _job_block(text: str, job_id: str) -> str:
    marker = f"  {job_id}:\n"
    start = text.index(marker)
    tail = text[start + len(marker) :]
    next_job = _JOB_HEADER_RE.search(tail)
    end = len(text) if next_job is None else start + len(marker) + next_job.start()
    return text[start:end]


def test_testpypi_publish_job_is_fail_closed_and_least_privilege() -> None:
    text = _workflow_text()
    block = _job_block(text, "testpypi-publish")
    compact = " ".join(line.strip() for line in block.splitlines())

    assert "needs: github-release" in block
    assert "github.event_name == 'push'" in block
    assert "startsWith(github.ref, 'refs/tags/v')" in block
    assert "vars.TESTPYPI_PUBLISH_ENABLED == 'true'" in block
    assert "environment: testpypi" in block
    assert "permissions: id-token: write" in compact

    workflow_prefix = text.split("jobs:", maxsplit=1)[0]
    assert "permissions:\n  contents: read" in workflow_prefix
    assert "id-token:" not in workflow_prefix
    assert text.count("id-token:") == block.count("id-token:") == 1


def test_testpypi_publish_job_reuses_exact_artifact_without_rebuild_or_secret() -> None:
    text = _workflow_text()
    block = _job_block(text, "testpypi-publish")

    assert _DOWNLOAD_ACTION in block
    assert "name: dist-${{ github.ref_name }}" in block
    assert "path: dist" in block
    assert _PUBLISH_ACTION in block
    assert "repository-url: https://test.pypi.org/legacy/" in block
    assert "packages-dir: dist" in block
    assert "attestations: true" in block
    assert text.count(_PUBLISH_ACTION) == 1

    for forbidden in (
        "actions/checkout@",
        "uv build",
        "password:",
        "user:",
        "secrets.",
        "twine",
    ):
        assert forbidden not in block
