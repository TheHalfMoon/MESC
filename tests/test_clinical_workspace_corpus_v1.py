"""CW-009 focused acceptance tests for the synthetic evidence corpus."""

# mypy: disable-error-code="import-not-found"
# The Workspace package under apps/workspace is deliberately outside strict mypy file
# set while Issue 464 item 1 is open. These tests import it at runtime through sys.path.

from __future__ import annotations

import sys
from pathlib import Path
from uuid import UUID

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402 runtime import
from medscale_workspace import (  # noqa: E402 runtime import
    AuditTrail,
    WorkspaceStore,
)
from medscale_workspace import corpus as corpus_mod  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    CorpusConflictError,
    CorpusInputError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)
from medscale_workspace.provenance import (  # noqa: E402 runtime import
    ReviewState,
    read_provenance,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
CORPUS_KEY = "synthetic-evidence-v1"
ACTOR = "synthetic-operator"
T1 = "2026-09-24T10:00:00+03:00"
T2 = "2026-09-24T10:01:00+03:00"


def open_store(root: Path, workspace_id: UUID = WORKSPACE_ALPHA) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=workspace_id,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def admit(
    store: WorkspaceStore,
    trail: AuditTrail,
    locator: str = "synthetic-corpus/doc-001",
    title: str = "Synthetic hydration guideline",
    revision: str = "rev-00000001",
    date: str = "2026-01-05",
    text: str = "synthetic guideline: hydration monitoring for ward patients",
) -> UUID:
    binding = corpus_mod.admit_source(
        store, trail, WORKSPACE_ALPHA, CORPUS_KEY, locator, title, revision, date, text, ACTOR, T1
    )
    return UUID(str(binding.object_id))


def test_admitted_source_has_stable_identity(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source_id = admit(store, trail)
        expected = corpus_mod.source_id_for(
            WORKSPACE_ALPHA, CORPUS_KEY, "synthetic-corpus/doc-001", "rev-00000001"
        )
        assert source_id == expected
        source = corpus_mod.read_source(store, source_id)
        assert source.locator == "synthetic-corpus/doc-001"
        assert source.title == "Synthetic hydration guideline"
        assert source.source_revision == "rev-00000001"
        assert source.source_date == "2026-01-05"
        assert source.text == "synthetic guideline: hydration monitoring for ward patients"
        record = read_provenance(store, corpus_mod.source_binding(WORKSPACE_ALPHA, source_id))
        assert record.review_state is ReviewState.IMPORTED


def test_changed_bytes_or_revision_change_identity(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        first = admit(store, trail)
        second = admit(store, trail, locator="synthetic-corpus/doc-001", revision="rev-00000002")
        assert second != first
        third = admit(store, trail, locator="synthetic-corpus/doc-002")
        assert third != first
        assert third != second


def test_duplicate_admission_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        admit(store, trail)
        with pytest.raises(CorpusConflictError):
            admit(store, trail)


def test_source_digest_binds_exact_bytes(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source_id = admit(store, trail)
        source = corpus_mod.read_source(store, source_id)
        assert source.content_digest.startswith("sha256:")
        assert len(source.content_digest) == len("sha256:") + 64


def test_corpus_identity_is_deterministic(tmp_path: Path) -> None:
    corpus_id = corpus_mod.corpus_id_for(WORKSPACE_ALPHA, CORPUS_KEY)
    assert corpus_id == corpus_mod.corpus_id_for(WORKSPACE_ALPHA, CORPUS_KEY)
    assert corpus_id != corpus_mod.corpus_id_for(WORKSPACE_ALPHA, "other-corpus")


def test_malformed_source_fields_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        with pytest.raises(CorpusInputError):
            admit(store, trail, locator="   ")
        with pytest.raises(CorpusInputError):
            admit(store, trail, date="05-01-2026")
        with pytest.raises(CorpusInputError):
            admit(store, trail, text="")
        with pytest.raises(CorpusInputError):
            admit(store, trail, text="x" * 5000)
