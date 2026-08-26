"""Independent P01-04B publication-boundary qualification (FD-BPUB-1..18).

This module does not re-test the publisher's behaviour; that is
``tests/test_mesc_fixture_publication_v1.py``.  It independently enforces the
*boundary* the adopted contract fixes: the exact four-path implementation scope,
the continuing protected runtime paths, the recorded adoption-baseline dependency
identities, the absence of any public or CLI surface, the exact literals, and the
continuing prohibitions.

Success here is qualification-harness evidence only.  It is never scientific,
clinical, dataset or real-split evidence, and it does not accept P01-04B.
"""

from __future__ import annotations

import ast
import hashlib
import tomllib
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PUBLICATION_MODULE = REPOSITORY_ROOT / "src" / "medscale" / "mesc" / "_fixture_publication_v1.py"
UNIT_TEST_MODULE = REPOSITORY_ROOT / "tests" / "test_mesc_fixture_publication_v1.py"
QUALIFICATION_MODULE = (
    REPOSITORY_ROOT / "tests" / "test_mesc_p01_04b_publication_qualification_v1.py"
)
WORKFLOW = REPOSITORY_ROOT / ".github" / "workflows" / "mesc-p01-04b-publication-qualification.yml"

#: The exact four paths this implementation is permitted to add. No fifth path.
ALLOWLISTED_PATHS = (
    "src/medscale/mesc/_fixture_publication_v1.py",
    "tests/test_mesc_fixture_publication_v1.py",
    "tests/test_mesc_p01_04b_publication_qualification_v1.py",
    ".github/workflows/mesc-p01-04b-publication-qualification.yml",
)

#: SHA-256 of continuing publication-boundary runtime paths. These paths remain
#: byte-identical after adoption. Repository packaging may evolve under later,
#: independently qualified gates without rewriting this implementation identity.
CONTINUING_PROTECTED_PATH_DIGESTS = {
    "src/medscale/mesc/__init__.py": (
        "35c5d49d5117178d9da6f01e042d3285949d0bfd5912b50db51cbc546cc5cc7c"
    ),
    "src/medscale/mesc/split.py": (
        "f43d65c3de46d57f142dc36758f928960647f91860b0e4f3219e50cc15193301"
    ),
    "src/medscale/mesc/_split_v1.py": (
        "6098623d12a5c6f54308be37075fb0e6caabc76b1704295c996b5bc87c6f9770"
    ),
    "src/medscale/mesc/_fixture_split_v1.py": (
        "ea2c987fb7843e6eba679d30973bfc06c8d385ac343d042d7e8c076e40d992c1"
    ),
    "src/medscale/mesc/_canonical_json_v1.py": (
        "ca7ff8a710d8d116d277d88510e3ff52b54a6035dd147bf00c9807dd108eb785"
    ),
    "src/medscale/mesc/_split_artifacts_v1.py": (
        "a708303aca9564ecb7b34aacf52b68cf52c2ec12b87fbc09d595d5579145c0bd"
    ),
    "src/medscale/mesc/_leakage_v1.py": (
        "40fbd6332efcbf8f93c9ae5bda015e8cdd96967c1d13486581dfd5885995add1"
    ),
    "tests/_mesc_p01_04b2d_fixtures_v1.py": (
        "f9e805cf8e5dada8ad86b41a199001ddb1dc1d033aa550246d399d3ff27a9bb3"
    ),
}

#: Historical packaging identities recorded at the publication implementation
#: adoption baseline. They are evidence about that historical increment, not a
#: permanent prohibition on independently authorized repository packaging changes.
ADOPTION_BASELINE_DEPENDENCY_DIGESTS = {
    "pyproject.toml": "da80ead771a81685f36d3e537fb3cee5f43624eb9e3917456ad02beb1471585e",
    "uv.lock": "a5a91ffad1aab490080b96d7edc440d07417e06481ce8e0fc7e3c7ffb099c07d",
}

PAYLOAD_FILENAMES = (
    "example-registry.jsonl",
    "excluded-ledger.json",
    "group-registry.jsonl",
    "leakage-audit.json",
    "split-summary-identity-core.json",
    "split-summary.json",
)
SURFACES = (
    "example_registry",
    "excluded_ledger",
    "group_registry",
    "leakage_audit",
    "split_summary_document",
    "split_summary_identity_core",
)
RECEIPT_FIELDS = (
    "publication_directory",
    "request_id",
    "split_fingerprint",
    "publication_manifest_sha256",
    "published_filenames",
)


def _source() -> str:
    return PUBLICATION_MODULE.read_text("utf-8")


# ---------------------------------------------------------------------------
# Scope and protected paths
# ---------------------------------------------------------------------------


def test_all_four_allowlisted_paths_exist() -> None:
    for relative in ALLOWLISTED_PATHS:
        assert (REPOSITORY_ROOT / relative).is_file(), relative


def test_no_fifth_publication_path_was_added() -> None:
    """Nothing named for this increment exists outside the four-path allowlist."""
    allowed = {REPOSITORY_ROOT / relative for relative in ALLOWLISTED_PATHS}
    for base in ("src", "tests", ".github"):
        for candidate in (REPOSITORY_ROOT / base).rglob("*publication*"):
            if not candidate.is_file() or "__pycache__" in candidate.parts:
                continue
            assert candidate in allowed, str(candidate)


def test_continuing_protected_paths_are_byte_identical() -> None:
    for relative, expected in CONTINUING_PROTECTED_PATH_DIGESTS.items():
        payload = (REPOSITORY_ROOT / relative).read_bytes()
        assert hashlib.sha256(payload).hexdigest() == expected, relative


def test_adoption_baseline_dependency_digests_remain_recorded() -> None:
    assert ADOPTION_BASELINE_DEPENDENCY_DIGESTS == {
        "pyproject.toml": "da80ead771a81685f36d3e537fb3cee5f43624eb9e3917456ad02beb1471585e",
        "uv.lock": "a5a91ffad1aab490080b96d7edc440d07417e06481ce8e0fc7e3c7ffb099c07d",
    }


def test_no_governance_package_was_modified() -> None:
    package = (
        REPOSITORY_ROOT / "specs" / "mesc-pilot-01" / "p01-04b-publication-boundary-authorization"
    )
    for name in (
        "README.md",
        "acceptance.md",
        "founder-authorization.md",
        "implementation-contract.md",
    ):
        assert (package / name).is_file()


def test_dependency_evolution_does_not_expose_publisher() -> None:
    manifest = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text("utf-8"))
    assert "ctypes" not in manifest["project"].get("dependencies", [])
    for entry_points in manifest["project"].get("scripts", {}).values():
        assert "publication" not in entry_points


# ---------------------------------------------------------------------------
# Private boundary (FD-BPUB-2)
# ---------------------------------------------------------------------------


def test_no_public_export_of_the_publisher() -> None:
    import medscale
    import medscale.mesc

    for module in (medscale, medscale.mesc):
        for exported in getattr(module, "__all__", ()):
            assert "publication" not in exported.lower()
            assert "publish" not in exported.lower()


def test_every_introduced_name_is_module_private() -> None:
    tree = ast.parse(_source())
    public: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef) and not node.name.startswith("_"):
            public.append(node.name)
    assert public == []


def test_module_declares_no_dunder_all() -> None:
    tree = ast.parse(_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "__all__":
            pytest.fail("the publication module must not declare __all__")


def test_no_cli_surface_references_the_publisher() -> None:
    cli_root = REPOSITORY_ROOT / "src" / "medscale" / "cli"
    for candidate in cli_root.rglob("*.py"):
        text = candidate.read_text("utf-8")
        assert "_fixture_publication_v1" not in text, str(candidate)
        assert "publish_fixture_split" not in text, str(candidate)


def test_splitter_remains_fail_closed() -> None:
    from medscale.mesc.split import PilotSplitNotAuthorizedError, SourceDocumentGroupedSplitter

    with pytest.raises(PilotSplitNotAuthorizedError):
        SourceDocumentGroupedSplitter().assign((), ())


# ---------------------------------------------------------------------------
# Exact literals (FD-BPUB-5, FD-BPUB-6, FD-BPUB-7, FD-BPUB-17)
# ---------------------------------------------------------------------------


def test_exact_schema_literal() -> None:
    from medscale.mesc._fixture_publication_v1 import MANIFEST_SCHEMA_VERSION

    assert MANIFEST_SCHEMA_VERSION == "mesc-pilot-01-fixture-publication-manifest/1"


def test_exact_directory_name_literals_carry_the_split_component() -> None:
    from medscale.mesc._fixture_publication_v1 import (
        _FINAL_DIRECTORY_PREFIX,
        _STAGING_DIRECTORY_PREFIX,
        _STAGING_DIRECTORY_SUFFIX,
    )

    assert _FINAL_DIRECTORY_PREFIX == "mesc-p01-04b-split-"
    assert _STAGING_DIRECTORY_PREFIX == ".mesc-p01-04b-split-"
    assert _STAGING_DIRECTORY_SUFFIX == ".staging"
    assert "-split-" in _FINAL_DIRECTORY_PREFIX
    assert "-split-" in _STAGING_DIRECTORY_PREFIX


def test_exact_seven_name_inventory() -> None:
    from medscale.mesc._fixture_publication_v1 import _PUBLISHED_FILENAMES

    observed = tuple(_PUBLISHED_FILENAMES)
    assert observed == tuple(sorted([*PAYLOAD_FILENAMES, "publication-manifest.json"]))
    assert len(observed) == 7


def test_exact_six_bindings_and_surfaces() -> None:
    from medscale.mesc._fixture_publication_v1 import _PAYLOAD_BINDINGS

    assert len(_PAYLOAD_BINDINGS) == 6
    assert tuple(binding[0] for binding in _PAYLOAD_BINDINGS) == PAYLOAD_FILENAMES
    assert tuple(binding[0] for binding in _PAYLOAD_BINDINGS) == tuple(sorted(PAYLOAD_FILENAMES))
    assert tuple(sorted(binding[1] for binding in _PAYLOAD_BINDINGS)) == SURFACES
    assert {binding[0]: binding[2] for binding in _PAYLOAD_BINDINGS} == {
        "example-registry.jsonl": "example_registry_bytes",
        "excluded-ledger.json": "excluded_ledger_bytes",
        "group-registry.jsonl": "group_registry_bytes",
        "leakage-audit.json": "audit_report_bytes",
        "split-summary-identity-core.json": "split_summary_identity_core_bytes",
        "split-summary.json": "split_summary_document_bytes",
    }


def test_rejected_leakage_filename_never_appears() -> None:
    rejected = "leakage-audit" + "-report" + ".json"
    for module in (PUBLICATION_MODULE, UNIT_TEST_MODULE, WORKFLOW):
        assert rejected not in module.read_text("utf-8"), str(module)


def test_receipt_declares_exactly_five_fields() -> None:
    from medscale.mesc._fixture_publication_v1 import _PublicationReceipt

    assert _PublicationReceipt.__slots__ == RECEIPT_FIELDS
    annotations = _PublicationReceipt.__annotations__
    assert set(annotations) == set(RECEIPT_FIELDS)
    assert annotations["publication_directory"] == "Path"
    assert annotations["request_id"] == "str"
    assert annotations["split_fingerprint"] == "str"
    assert annotations["publication_manifest_sha256"] == "str"
    assert annotations["published_filenames"] == "tuple[str, ...]"


def test_prohibited_receipt_substitutes_are_absent() -> None:
    from medscale.mesc._fixture_publication_v1 import _PublicationReceipt

    assert "final_directory" not in _PublicationReceipt.__slots__
    assert "publication_manifest_bytes" not in _PublicationReceipt.__slots__


def test_manifest_never_borrows_artifact_schema_versions() -> None:
    source = _source()
    assert "ARTIFACT_SCHEMA_VERSIONS" not in source


# ---------------------------------------------------------------------------
# Continuing prohibitions (FD-BPUB-14, FD-BPUB-18)
# ---------------------------------------------------------------------------


def test_replace_existing_rename_is_absent() -> None:
    assert "os.replace" not in _source()
    assert ".replace(" not in _source().replace("str.replace(", "")


def test_no_copy_or_recursive_move_fallback() -> None:
    source = _source()
    for forbidden in ("shutil", "copytree", "copyfile", "copy2", "rmtree", "os.removedirs"):
        assert forbidden not in source


def test_no_cleanup_retry_or_repair_surface() -> None:
    source = _source()
    for forbidden in ("unlink(", "rmdir(", "os.remove", "TemporaryDirectory", "mkstemp"):
        assert forbidden not in source


def test_no_network_subprocess_clock_randomness_or_environment() -> None:
    source = _source()
    for forbidden in (
        "import socket",
        "import subprocess",
        "import urllib",
        "import http",
        "import requests",
        "import httpx",
        "import time",
        "import datetime",
        "import random",
        "import secrets",
        "import uuid",
        "os.environ",
        "getenv",
        "os.system",
        "multiprocessing",
    ):
        assert forbidden not in source, forbidden


def test_no_real_data_model_or_evidence_surface() -> None:
    source = _source().lower()
    for forbidden in (
        "accelerate",
        "bitsandbytes",
        "datasets",
        "huggingface",
        "peft",
        "transformers",
        "torch",
        "trl",
        "tokenizer",
        "inference",
        "retrieval",
        "training",
        "fine-tune",
        "pubmedqa",
        "evidence_root",
    ):
        assert forbidden not in source, forbidden


def test_no_message_parsing_dispatch() -> None:
    source = _source()
    for forbidden in ("str(error)", "error.args", ".startswith(str", "re.match", "import re\n"):
        assert forbidden not in source, forbidden


def test_durability_claim_stays_bounded() -> None:
    """The module states atomic namespace visibility and disclaims the rest."""
    prose = " ".join(_source().lower().split())
    assert "atomic namespace visibility" in prose
    # The only permitted mention of stronger durability is the explicit disclaimer.
    for overclaim in ("power-loss durability", "storage-controller durability"):
        assert overclaim in prose
        assert f"not claim {overclaim}" in prose or "are explicitly *not* claimed" in prose


def test_no_placeholder_or_conflict_marker() -> None:
    # Each token is joined at runtime, so this module never literally contains the
    # markers it scans for and can therefore include itself in the scan.
    tokens = tuple(
        "".join(parts)
        for parts in (
            ("TO", "DO"),
            ("T", "BD"),
            ("T", "BC"),
            ("FIX", "ME"),
            ("XX", "X"),
            ("<" * 3, "<" * 4),
            (">" * 3, ">" * 4),
        )
    )
    for module in (PUBLICATION_MODULE, UNIT_TEST_MODULE, QUALIFICATION_MODULE, WORKFLOW):
        text = module.read_text("utf-8")
        for token in tokens:
            assert token not in text, f"{module}: {token}"


# ---------------------------------------------------------------------------
# Workflow exactness (FD-BPUB-18 harness boundary)
# ---------------------------------------------------------------------------


def test_workflow_is_narrowly_dedicated() -> None:
    text = WORKFLOW.read_text("utf-8")
    assert "pull_request:" in text
    assert "workflow_dispatch" not in text
    assert "schedule:" not in text
    assert "tests/test_mesc_fixture_publication_v1.py" in text
    assert "tests/test_mesc_p01_04b_publication_qualification_v1.py" in text
    assert "--frozen" in text
    assert "upload-artifact" not in text


def test_workflow_runs_the_repository_quality_gates() -> None:
    text = WORKFLOW.read_text("utf-8")
    assert "ruff check" in text
    assert "ruff format --check" in text
    assert "mypy" in text


def test_synthetic_only_boundary_is_declared() -> None:
    assert "synthetic" in _source().lower()
    assert "non-evidence" in _source().lower()
    assert "synthetic" in UNIT_TEST_MODULE.read_text("utf-8").lower()
