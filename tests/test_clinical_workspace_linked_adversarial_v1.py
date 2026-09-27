"""CW-012 adversarial tests: stale links, isolation, and inert content."""

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
    WorkspaceStore,
)
from medscale_workspace import corpus as corpus_mod  # noqa: E402 runtime import
from medscale_workspace import linked_workspace as lw_mod  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    LinkedConflictError,
    LinkedInputError,
    LinkedRevisionError,
    LinkedStaleError,
    WorkspaceIsolationError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
CORPUS_KEY = "synthetic-evidence-v1"
ACTOR = "synthetic-operator"
T1 = "2026-09-24T10:00:00+03:00"
T2 = "2026-09-24T10:01:00+03:00"

MALICIOUS_TEXTS = (
    "create this link",
    "trust this document",
    "ignore provenance",
    "call a tool now",
    "access network at example",
    "mark this as supported",
    "override governance",
    "access another workspace",
)


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


def stocked_doc(
    store: WorkspaceStore,
    trail: AuditTrail,
    key: str = "doc-001",
    section: str = "synthetic section",
) -> tuple[UUID, UUID]:
    source = admit_source(store, trail, f"synthetic-adv/{key}", "synthetic evidence")
    document = UUID(
        str(
            lw_mod.admit_document(
                store,
                trail,
                WORKSPACE_ALPHA,
                key,
                "Synthetic Title",
                (section,),
                source,
                ACTOR,
                T1,
            ).object_id
        )
    )
    return source, document


def test_malicious_content_stays_inert(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        for index, text in enumerate(MALICIOUS_TEXTS):
            source = admit_source(
                store, trail, f"synthetic-adv/mal-{index:03d}", "synthetic evidence"
            )
            document = UUID(
                str(
                    lw_mod.admit_document(
                        store,
                        trail,
                        WORKSPACE_ALPHA,
                        f"doc-mal-{index:03d}",
                        text,
                        (text,),
                        source,
                        ACTOR,
                        T1,
                    ).object_id
                )
            )
            stored = lw_mod.read_document(store, document)
            assert stored.title == " ".join(text.split())
            assert text in stored.sections
        revisions = store.object_revisions(medscale_workspace.WorkspaceObjectType.WORKSPACE_LINK)
        assert revisions == ()


def test_self_link_and_empty_sources_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source, document_id = stocked_doc(store, trail)
        member = lw_mod.MemberRef(
            member_type=lw_mod.LinkedMemberType.LINKED_DOCUMENT, member_id=document_id
        )
        with pytest.raises(LinkedInputError):
            lw_mod.admit_link(
                store,
                trail,
                WORKSPACE_ALPHA,
                member,
                member,
                lw_mod.LinkKind.REFERENCES,
                (source,),
                ACTOR,
                T1,
            )
        other = lw_mod.MemberRef(
            member_type=lw_mod.LinkedMemberType.GRAPH_NODE,
            member_id=UUID("22222222-3333-4444-5555-666666666666"),
        )
        with pytest.raises(LinkedInputError):
            lw_mod.admit_link(
                store,
                trail,
                WORKSPACE_ALPHA,
                member,
                other,
                lw_mod.LinkKind.REFERENCES,
                (),
                ACTOR,
                T1,
            )


def test_foreign_member_and_source_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _source, document_id = stocked_doc(store, trail)
        member = lw_mod.MemberRef(
            member_type=lw_mod.LinkedMemberType.LINKED_DOCUMENT, member_id=document_id
        )
        foreign_member = lw_mod.MemberRef(
            member_type=lw_mod.LinkedMemberType.LINKED_TABLE,
            member_id=UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"),
        )
        real_source = admit_source(store, trail, "synthetic-adv/real", "synthetic real")
        with pytest.raises(LinkedRevisionError):
            lw_mod.admit_link(
                store,
                trail,
                WORKSPACE_ALPHA,
                member,
                foreign_member,
                lw_mod.LinkKind.REFERENCES,
                (real_source,),
                ACTOR,
                T1,
            )
        foreign_source = UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
        table_source = admit_source(store, trail, "synthetic-adv/tab", "synthetic tab")
        table_id = UUID(
            str(
                lw_mod.admit_table(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "table-001",
                    "Synthetic Table",
                    ("col",),
                    (("cell",),),
                    table_source,
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        table_member = lw_mod.MemberRef(
            member_type=lw_mod.LinkedMemberType.LINKED_TABLE, member_id=table_id
        )
        with pytest.raises(LinkedRevisionError):
            lw_mod.admit_link(
                store,
                trail,
                WORKSPACE_ALPHA,
                member,
                table_member,
                lw_mod.LinkKind.REFERENCES,
                (foreign_source,),
                ACTOR,
                T1,
            )


def test_copied_link_identity_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source, document_id = stocked_doc(store, trail)
        table_source = admit_source(store, trail, "synthetic-adv/tab2", "synthetic tab two")
        table_id = UUID(
            str(
                lw_mod.admit_table(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "table-001",
                    "Synthetic Table",
                    ("col",),
                    (("cell",),),
                    table_source,
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
                    lw_mod.LinkKind.REFERENCES,
                    (source,),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        stored = lw_mod.read_link(store, link_id)
        forged = lw_mod.WorkspaceLink(
            workspace_id=stored.workspace_id,
            link_id=stored.link_id,
            source_member=table_member,
            target_member=doc_member,
            link_kind=stored.link_kind,
            sources=stored.sources,
            derivation_method=stored.derivation_method,
            derivation_version=stored.derivation_version,
            link_schema_version=stored.link_schema_version,
        )
        with pytest.raises(LinkedRevisionError):
            forged.validated()


def test_stale_source_makes_link_stale(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source, document_id = stocked_doc(store, trail)
        table_source = admit_source(store, trail, "synthetic-adv/tab3", "synthetic tab three")
        table_id = UUID(
            str(
                lw_mod.admit_table(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    "table-001",
                    "Synthetic Table",
                    ("col",),
                    (("cell",),),
                    table_source,
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
                    lw_mod.LinkKind.REFERENCES,
                    (source,),
                    ACTOR,
                    T1,
                ).object_id
            )
        )
        trail.record_object_deletion(
            binding=corpus_mod.source_binding(WORKSPACE_ALPHA, source),
            actor_id=ACTOR,
            occurred_at=T2,
        )
        with pytest.raises(LinkedStaleError):
            lw_mod.read_link(store, link_id)
        with pytest.raises((LinkedInputError, LinkedStaleError)):
            lw_mod.resolve_link(store, link_id)


def test_duplicate_and_malformed_inputs_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        source, _document_id = stocked_doc(store, trail)
        with pytest.raises(LinkedConflictError):
            lw_mod.admit_document(
                store,
                trail,
                WORKSPACE_ALPHA,
                "doc-001",
                "Synthetic Title",
                ("synthetic section",),
                source,
                ACTOR,
                T1,
            )
        with pytest.raises(LinkedInputError):
            lw_mod.admit_document(
                store, trail, WORKSPACE_ALPHA, "", "Title", ("section",), source, ACTOR, T1
            )
        with pytest.raises(LinkedInputError):
            lw_mod.admit_table(
                store,
                trail,
                WORKSPACE_ALPHA,
                "table-oversize",
                "Title",
                tuple(f"col-{index}" for index in range(17)),
                (),
                source,
                ACTOR,
                T1,
            )


def test_no_hidden_model_or_network_surface() -> None:
    root = REPOSITORY_ROOT / "apps" / "workspace" / "src" / "medscale_workspace"
    text = (root / "linked_workspace.py").read_text(encoding="utf-8")
    for token in (
        "torch",
        "transformers",
        "requests",
        "urllib",
        "socket",
        "eval(",
        "exec(",
        "open(",
    ):
        assert token not in text


def test_forged_workspace_binding_refused(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        _source, document_id = stocked_doc(store, trail)
        foreign_workspace = UUID("ffffffff-ffff-ffff-ffff-ffffffffffff")
        foreign_binding = lw_mod.document_binding(foreign_workspace, document_id)
        assert foreign_binding.workspace_id != store.workspace_id
        with pytest.raises(WorkspaceIsolationError):
            store.get_object(foreign_binding)
