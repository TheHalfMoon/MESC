"""CW-012 acceptance tests: linked documents, tables, and cross-object links."""

# mypy: disable-error-code="import-not-found"

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
    DataClass,
    TrustDomain,
    WorkspaceStore,
    classify,
    classify_object,
    guard_object_handoff,
)
from medscale_workspace import corpus as corpus_mod  # noqa: E402 runtime import
from medscale_workspace import linked_workspace as lw_mod  # noqa: E402 runtime import
from medscale_workspace import patient_graph as pg_mod  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    LinkedConflictError,
    LinkedInputError,
    LinkedRevisionError,
    LinkedStaleError,
    ResearchBackflowError,
    WorkspaceIsolationError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
WORKSPACE_BETA = UUID("7dd9e9f4-1c3b-40b4-b10f-5b16db71b00f")
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


def admit_source(store: WorkspaceStore, trail: AuditTrail, locator: str, text: str) -> UUID:
    return UUID(
        str(
            corpus_mod.admit_source(
                store,
                trail,
                WORKSPACE_ALPHA,
                CORPUS_KEY,
                locator,
                "Synthetic source",
                "rev-00000001",
                "2026-09-01",
                text,
                ACTOR,
                T1,
            ).object_id
        )
    )


def admit_graph_node(store: WorkspaceStore, trail: AuditTrail, key: str, source_id: UUID) -> UUID:
    return UUID(
        str(
            pg_mod.admit_node(
                store,
                trail,
                WORKSPACE_ALPHA,
                key,
                pg_mod.NodeKind.PATIENT,
                "synthetic patient",
                source_id,
                ACTOR,
                T1,
            ).object_id
        )
    )


def test_document_links_through_stable_ids(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source_id = admit_source(store, trail, "synthetic-link/doc-001", "synthetic note one")
        document_id = UUID(
            str(
                lw_mod.admit_document(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "doc-001",
                    "Synthetic Ward Note",
                    ("synthetic section one", "synthetic section two"),
                    source_id,
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        document = lw_mod.read_document(store, document_id)
        assert document.document_key == "doc-001"
        assert document.sections == ("synthetic section one", "synthetic section two")
        assert document.document_id == lw_mod.document_id_for(
            WORKSPACE_ALPHA, "doc-001", "rev-00000001"
        )
        with pytest.raises(LinkedConflictError):
            lw_mod.admit_document(
                store,
                trail,
                WORKSPACE_ALPHA,
                "doc-001",
                "Synthetic Ward Note",
                ("synthetic section one", "synthetic section two"),
                source_id,
                ACTOR,
                T1,
            )


def test_table_shape_and_row_width_enforced(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source_id = admit_source(store, trail, "synthetic-link/tab-001", "synthetic table note")
        table_id = UUID(
            str(
                lw_mod.admit_table(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "table-001",
                    "Synthetic Meds",
                    ("drug", "dose"),
                    (("synthetic-a", "5mg"), ("synthetic-b", "10mg")),
                    source_id,
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        table = lw_mod.read_table(store, table_id)
        assert table.columns == ("drug", "dose")
        assert table.rows == (("synthetic-a", "5mg"), ("synthetic-b", "10mg"))
        with pytest.raises(LinkedInputError):
            lw_mod.admit_table(
                store,
                trail,
                WORKSPACE_ALPHA,
                "table-bad",
                "Bad Table",
                ("drug", "dose"),
                (("only-one",),),
                source_id,
                ACTOR,
                T1,
            )
        with pytest.raises(LinkedInputError):
            lw_mod.admit_table(
                store,
                trail,
                WORKSPACE_ALPHA,
                "table-dup",
                "Dup Table",
                ("drug", "drug"),
                (),
                source_id,
                ACTOR,
                T1,
            )


def test_link_binds_document_table_and_graph(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source_id = admit_source(store, trail, "synthetic-link/m-001", "synthetic member note")
        document_id = UUID(
            str(
                lw_mod.admit_document(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "doc-001",
                    "Synthetic Note",
                    ("synthetic section",),
                    source_id,
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        table_id = UUID(
            str(
                lw_mod.admit_table(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "table-001",
                    "Synthetic Table",
                    ("col",),
                    (("synthetic-cell",),),
                    source_id,
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        node_id = admit_graph_node(store, trail, "patient-001", source_id)
        doc_member = lw_mod.MemberRef(
            member_type=lw_mod.LinkedMemberType.LINKED_DOCUMENT, member_id=document_id
        )
        table_member = lw_mod.MemberRef(
            member_type=lw_mod.LinkedMemberType.LINKED_TABLE, member_id=table_id
        )
        node_member = lw_mod.MemberRef(
            member_type=lw_mod.LinkedMemberType.GRAPH_NODE, member_id=node_id
        )
        first = UUID(
            str(
                lw_mod.admit_link(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    doc_member,
                    table_member,
                    lw_mod.LinkKind.REFERENCES,
                    (source_id,),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        second = UUID(
            str(
                lw_mod.admit_link(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    doc_member,
                    node_member,
                    lw_mod.LinkKind.DERIVED_FROM,
                    (source_id,),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        resolved = lw_mod.resolve_link(store, first)
        assert resolved.source_member == doc_member
        assert resolved.target_member == table_member
        assert lw_mod.links_for_member(store, doc_member) == tuple(sorted((first, second), key=str))
        assert lw_mod.links_for_member(store, node_member) == (second,)


def test_offline_persistence_across_reopen(tmp_path: Path) -> None:
    provider = InMemoryTestKeyProvider(new_root_secret())

    def reopen() -> WorkspaceStore:
        return WorkspaceStore.open(
            store_root=str(tmp_path),
            workspace_id=WORKSPACE_ALPHA,
            key_provider=provider,
            application_version=APPLICATION_VERSION,
        )

    with reopen() as store:
        trail = AuditTrail(store)
        source_id = admit_source(store, trail, "synthetic-link/off-001", "synthetic offline note")
        document_id = UUID(
            str(
                lw_mod.admit_document(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "doc-off",
                    "Offline Note",
                    ("synthetic offline section",),
                    source_id,
                    ACTOR,
                    T1,
                ).object_id
            )
        )
    with reopen() as store:
        document = lw_mod.read_document(store, document_id)
        assert document.title == "Offline Note"


def test_stale_link_after_member_deletion(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source_id = admit_source(store, trail, "synthetic-link/del-001", "synthetic delete note")
        document_id = UUID(
            str(
                lw_mod.admit_document(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "doc-del",
                    "Delete Note",
                    ("synthetic section",),
                    source_id,
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        table_id = UUID(
            str(
                lw_mod.admit_table(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "table-del",
                    "Delete Table",
                    ("col",),
                    (("cell",),),
                    source_id,
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        doc_member = lw_mod.MemberRef(
            member_type=lw_mod.LinkedMemberType.LINKED_DOCUMENT, member_id=document_id
        )
        table_member = lw_mod.MemberRef(
            member_type=lw_mod.LinkedMemberType.LINKED_TABLE, member_id=table_id
        )
        link_id = UUID(
            str(
                lw_mod.admit_link(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    doc_member,
                    table_member,
                    lw_mod.LinkKind.CONTAINS,
                    (source_id,),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        removed = lw_mod.delete_member(store, trail, table_member, ACTOR, T2)
        assert removed >= 2
        with pytest.raises(LinkedInputError):
            lw_mod.read_table(store, table_id)
        with pytest.raises(LinkedInputError):
            lw_mod.read_link(store, link_id)
        with pytest.raises((LinkedInputError, LinkedStaleError)):
            lw_mod.resolve_link(store, link_id)


def test_research_refs_stay_read_only(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source_id = admit_source(store, trail, "synthetic-link/res-001", "synthetic research note")
        ref = lw_mod.ResearchRef(artifact_id="synthetic-artifact-001", artifact_version="v1")
        document_id = UUID(
            str(
                lw_mod.admit_document(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "doc-res",
                    "Research Note",
                    ("synthetic section",),
                    source_id,
                    ACTOR,
                    T1,
                    research_refs=(ref,),
                ).object_id
            )
        )
        assert lw_mod.read_document(store, document_id).research_refs == (ref,)
        classified = classify_object(
            binding=lw_mod.document_binding(WORKSPACE_ALPHA, document_id),
            classification=classify(DataClass.SYNTHETIC),
            payload=b"synthetic-payload",
        )
        with pytest.raises(ResearchBackflowError):
            guard_object_handoff(classified, TrustDomain.RESEARCH_CORE)


def test_cross_workspace_link_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source_id = admit_source(store, trail, "synthetic-link/x-001", "synthetic cross note")
        document_id = UUID(
            str(
                lw_mod.admit_document(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "doc-x",
                    "Cross Note",
                    ("synthetic section",),
                    source_id,
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        foreign = UUID("11111111-2222-3333-4444-555555555555")
        doc_member = lw_mod.MemberRef(
            member_type=lw_mod.LinkedMemberType.LINKED_DOCUMENT, member_id=document_id
        )
        foreign_member = lw_mod.MemberRef(
            member_type=lw_mod.LinkedMemberType.GRAPH_NODE, member_id=foreign
        )
        with pytest.raises((LinkedRevisionError, LinkedInputError, WorkspaceIsolationError)):
            lw_mod.admit_link(
                store,
                trail,
                WORKSPACE_ALPHA,
                doc_member,
                foreign_member,
                lw_mod.LinkKind.REFERENCES,
                (source_id,),
                ACTOR,
                T1,
            )
        with pytest.raises(WorkspaceIsolationError):
            lw_mod.admit_document(
                store,
                trail,
                WORKSPACE_BETA,
                "doc-y",
                "Foreign Note",
                ("synthetic section",),
                source_id,
                ACTOR,
                T1,
            )


def test_no_donor_schema_vendored() -> None:
    root = REPOSITORY_ROOT / "apps" / "workspace" / "src" / "medscale_workspace"
    text = (root / "linked_workspace.py").read_text(encoding="utf-8")
    for token in ("affine", "octobase", "graphify", "openmed"):
        assert token not in text.lower()
    assert lw_mod.SCHEMA_VERSION == "cw012-linked-workspace/1"
    assert lw_mod.DERIVATION_METHOD == "cw012-deterministic-linking"
