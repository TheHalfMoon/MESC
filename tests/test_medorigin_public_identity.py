"""Regression tests for MedOrigin's public identity and historical compatibility.

Only actively maintained public entry points are inspected. Historical research
artifacts, versioned contracts, imports and immutable receipts are intentionally
outside this test's scope.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_HOME = "https://github.com/TheHalfMoon/MedOrigin"


def _text(path: str) -> str:
    return (_REPO / path).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("path", "title"),
    [
        ("README.md", "# MedOrigin"),
        ("docs/README.md", "# MedOrigin Documentation"),
        ("apps/workspace/README.md", "# MedOrigin Clinical Workspace"),
        ("docs/vision/MEDORIGIN_OVERVIEW.md", "# MedOrigin — Project Overview"),
        ("docs/BRAND_TRANSITION.md", "# MedOrigin — Identity and Compatibility Policy"),
        ("ROADMAP.md", "# MedOrigin Roadmap"),
        ("CONTRIBUTING.md", "# Contributing to MedOrigin"),
    ],
)
def test_public_entry_points_use_medorigin(path: str, title: str) -> None:
    """Public-facing entry-point headings must not silently revert."""
    assert title in _text(path).splitlines()


def test_readme_points_to_current_repository_and_describes_limits() -> None:
    """The quickstart and current status must remain truthful and reachable."""
    readme = _text("README.md")
    assert "# MedOrigin" in readme.splitlines()
    assert f"git clone {_HOME}.git" in readme
    assert "cd MedOrigin" in readme
    assert f"{_HOME}/actions/workflows/ci.yml" in readme
    assert "not a medical device" in readme.lower()
    assert "synthetic-only" in readme.lower()
    assert "CW-021" in readme
    assert "MRL-0809" in readme
    # Historical links are valid in archival records, but not as today's clone URL.
    assert "git clone https://github.com/TheHalfMoon/MESC" not in readme
    assert "git clone https://github.com/TheHalfMoon/MedScale" not in readme


def test_citation_uses_current_repository_without_inventing_release() -> None:
    """The citation should reference MedOrigin but retain the historical release."""
    citation = _text("CITATION.cff")
    assert 'title: "MedOrigin: Verifiable medical AI research infrastructure"' in citation
    assert f'repository-code: "{_HOME}"' in citation
    assert f'url: "{_HOME}"' in citation
    assert "version: 0.2.0" in citation
    assert 'date-released: "2026-07-13"' in citation


def test_security_and_docs_link_to_current_home() -> None:
    """Public security, docs and accepted governance status must remain current."""
    assert f"{_HOME}/security/advisories/new" in _text("SECURITY.md")
    docs_index = _text("docs/README.md")
    assert "(BRAND_TRANSITION.md)" in docs_index
    assert "(vision/MEDORIGIN_OVERVIEW.md)" in docs_index
    for identifier, filename, title in [
        ("0010", "0010-release-architecture.md", "release architecture"),
        ("0011", "0011-versioning-licensing.md", "versioning & licensing"),
    ]:
        adr = _text(f"docs/adr/{filename}")
        assert "- **Status:** Accepted" in adr
        assert f"[{identifier} {title}](adr/{filename}) *(Accepted)*" in docs_index


def test_public_brand_does_not_erase_legacy_compatibility() -> None:
    """Branding is not a license to alter source-bound package/API identities."""
    policy = _text("docs/BRAND_TRANSITION.md")
    overview = _text("docs/vision/MEDORIGIN_OVERVIEW.md")
    readme = _text("README.md")
    assert "The Python distribution, import package, and command remain `medscale`." in policy
    assert "MESC" in policy and "MedScale" in policy
    assert "`medscale`" in overview
    assert "`medscale`" in readme
    assert "not a finished desktop or web application" in overview
