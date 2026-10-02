from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPAIR_MANIFEST = Path("specs/mesc-experiment-0/mrl-0809-static-prerequisites-v2-repair-1.json")
ZERO_SHA256 = "0" * 64


def _sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def _load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads((ROOT / path).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _assert_bound_file(entry: object) -> None:
    assert isinstance(entry, dict)
    path = entry.get("path")
    expected = entry.get("sha256")
    assert isinstance(path, str) and path
    assert isinstance(expected, str) and expected != ZERO_SHA256
    assert expected == _sha256(path)


def test_repair_source_hashes_are_finalized_and_match_repository_bytes() -> None:
    manifest = _load_json(REPAIR_MANIFEST)

    _assert_bound_file(manifest.get("preserved_v2_static_manifest"))
    _assert_bound_file(manifest.get("repair_authorization"))

    sources = manifest.get("sources")
    assert isinstance(sources, list) and sources
    for source in sources:
        _assert_bound_file(source)


def test_repair_authorization_binds_the_founder_decision_record() -> None:
    manifest = _load_json(REPAIR_MANIFEST)
    authorization_entry = manifest.get("repair_authorization")
    assert isinstance(authorization_entry, dict)
    authorization_path = authorization_entry.get("path")
    assert isinstance(authorization_path, str) and authorization_path

    authorization = _load_json(authorization_path)
    _assert_bound_file(authorization.get("decision_record"))

    assert authorization.get("repair_scope") == "REPOSITORY_REPAIR_ONLY"
    assert authorization.get("runtime_attempts_authorized") == 0
    non_grants = authorization.get("non_grants")
    assert isinstance(non_grants, dict)
    assert non_grants.get("new_stage4_attempt") is False
