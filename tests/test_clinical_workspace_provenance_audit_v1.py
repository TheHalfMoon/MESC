"""CW-003 focused acceptance tests for the provenance and audit spines.

Scope: synthetic fixtures only. This module creates no clinical, research,
publication or PHI authority, and every event timestamp below is a supplied literal
rather than a clock reading, because the Workspace package imports no clock.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
from pathlib import Path
from uuid import UUID

import pytest

# mypy: disable-error-code="import-not-found"
# The Workspace package under apps/workspace is deliberately outside strict mypy's
# file set while Issue #464 item 1 is open. These tests import it at runtime through
# sys.path; declaring the missing import here keeps that deferral explicit.

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SRC = REPOSITORY_ROOT / "apps" / "workspace" / "src"
WORKSPACE_MODULES = WORKSPACE_SRC / "medscale_workspace"

sys.path.insert(0, str(WORKSPACE_SRC))

import medscale_workspace  # noqa: E402
from medscale_workspace import (  # noqa: E402
    AuditEventType,
    AuditObjectRef,
    AuditTrail,
    ObjectBinding,
    ObjectWrite,
    ProducerIdentity,
    ProducerKind,
    ReviewState,
    SourceKind,
    SourceRef,
    WorkspaceObjectType,
    WorkspaceStore,
    content_digest_of,
    describe_revision,
    provenance_binding_for,
    read_provenance,
    store_with_provenance,
    verify_provenance,
)
from medscale_workspace.errors import (  # noqa: E402
    ObjectNotFoundError,
    ProvenanceDigestMismatchError,
    ProvenanceError,
    StoreIntegrityError,
    WorkspaceIsolationError,
)
from medscale_workspace.keyprovider import InMemoryTestKeyProvider, new_root_secret  # noqa: E402

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
WORKSPACE_BETA = UUID("1a3d7c22-42f4-4b76-9d6f-0c2c8db0f3a1")
NOTE_OBJECT = UUID("2f1b7c8e-6a4d-4f9c-8f1e-5b6a7c8d9e0f")
SENSITIVE_SYNTHETIC_NOTE = (
    b'SYNTHETIC-NOT-REAL:{"note":"synthetic provenance fixture","finding":"synthetic-only"}'
)
OCCURRED_AT_ONE = "2026-09-21T18:00:00+03:00"
OCCURRED_AT_TWO = "2026-09-21T18:05:00+03:00"
OCCURRED_AT_THREE = "2026-09-21T18:10:00+03:00"


def note_binding(revision: str = "rev-0001", workspace_id: UUID = WORKSPACE_ALPHA) -> ObjectBinding:
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=NOTE_OBJECT,
        object_type=WorkspaceObjectType.ENCOUNTER,
        object_revision=revision,
    )


def open_store(
    root: Path,
    *,
    workspace_id: UUID = WORKSPACE_ALPHA,
    root_secret: bytes | None = None,
) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=workspace_id,
        key_provider=InMemoryTestKeyProvider(root_secret or new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def transcript_source() -> SourceRef:
    return SourceRef(
        kind=SourceKind.TRANSCRIPT_RANGE,
        source_id="synthetic-transcript-0001",
        source_revision="rev-0002",
        locator="00:01:10-00:01:42",
    )


def model_producer() -> ProducerIdentity:
    return ProducerIdentity(
        kind=ProducerKind.MODEL,
        identifier="synthetic-local-drafter",
        version="0.0.1-synthetic",
    )


def store_files(store_path: str) -> tuple[Path, ...]:
    primary = Path(store_path)
    candidates = [primary, Path(f"{store_path}-wal"), Path(f"{store_path}-shm")]
    return tuple(candidate for candidate in candidates if candidate.exists())


# ---------------------------------------------------------------------------
# Provenance: revision identity and source identity
# ---------------------------------------------------------------------------


def test_generated_object_carries_revision_and_source_identity(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        binding = note_binding()
        record = describe_revision(
            binding=binding,
            payload=SENSITIVE_SYNTHETIC_NOTE,
            producer=model_producer(),
            source_refs=(transcript_source(),),
            review_state=ReviewState.DRAFT,
        )
        store_with_provenance(store, record, SENSITIVE_SYNTHETIC_NOTE)
        read_back = read_provenance(store, binding)
        assert store.get_object(binding) == SENSITIVE_SYNTHETIC_NOTE
    assert read_back.binding == binding
    assert read_back.content_digest == content_digest_of(SENSITIVE_SYNTHETIC_NOTE)
    assert read_back.producer.kind is ProducerKind.MODEL
    assert read_back.review_state is ReviewState.DRAFT
    assert [source.kind for source in read_back.source_refs] == [SourceKind.TRANSCRIPT_RANGE]
    assert read_back.source_refs[0].locator == "00:01:10-00:01:42"
    assert read_back.policy_version == "mesc-clinical-workspace-synthetic-only/1"
    assert read_back.provenance_format_version == 1


def test_provenance_record_is_a_separate_object_from_its_content(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        binding = note_binding()
        record = describe_revision(
            binding=binding,
            payload=SENSITIVE_SYNTHETIC_NOTE,
            producer=model_producer(),
            source_refs=(transcript_source(),),
            review_state=ReviewState.DRAFT,
        )
        store_with_provenance(store, record, SENSITIVE_SYNTHETIC_NOTE)
        provenance_identity = provenance_binding_for(binding)
        assert provenance_identity.object_type is WorkspaceObjectType.PROVENANCE_RECORD
        assert provenance_identity.object_id != binding.object_id
        assert store.object_revisions(WorkspaceObjectType.ENCOUNTER) == ((NOTE_OBJECT, "rev-0001"),)
        assert store.object_revisions(WorkspaceObjectType.PROVENANCE_RECORD) == (
            (provenance_identity.object_id, "rev-0001"),
        )
        # The provenance object is encrypted exactly like the content it describes.
        raw = store.get_object(provenance_identity)
    document = json.loads(raw.decode("ascii"))
    assert document["content_digest"] == content_digest_of(SENSITIVE_SYNTHETIC_NOTE)
    assert SENSITIVE_SYNTHETIC_NOTE not in raw


def test_re_verifying_provenance_detects_content_substitution(tmp_path: Path) -> None:
    """A recorded digest is re-verified, not trusted."""

    root_secret = new_root_secret()
    binding = note_binding()
    with open_store(tmp_path, root_secret=root_secret) as store:
        record = describe_revision(
            binding=binding,
            payload=SENSITIVE_SYNTHETIC_NOTE,
            producer=model_producer(),
            source_refs=(transcript_source(),),
            review_state=ReviewState.DRAFT,
        )
        store_with_provenance(store, record, SENSITIVE_SYNTHETIC_NOTE)
        assert verify_provenance(store, binding).content_digest == record.content_digest
        forged = describe_revision(
            binding=binding,
            payload=b"SYNTHETIC-NOT-REAL:different-payload",
            producer=model_producer(),
            source_refs=(transcript_source(),),
            review_state=ReviewState.DRAFT,
        )
        assert forged.content_digest != record.content_digest
        # An actor holding the key can replace the provenance record, but the digest it
        # declares is still re-verified against the stored content.
        assert store.delete_object(provenance_binding_for(binding)) is True
        store.put_objects_atomic(
            (
                ObjectWrite(
                    binding=provenance_binding_for(binding),
                    payload=forged.canonical_bytes(),
                ),
            )
        )
        with pytest.raises(ProvenanceDigestMismatchError):
            verify_provenance(store, binding)


def test_generated_content_without_a_source_is_refused() -> None:
    with pytest.raises(ProvenanceError):
        describe_revision(
            binding=note_binding(),
            payload=SENSITIVE_SYNTHETIC_NOTE,
            producer=model_producer(),
            source_refs=(),
            review_state=ReviewState.DRAFT,
        )


def test_imported_content_may_carry_no_source_reference() -> None:
    record = describe_revision(
        binding=note_binding(),
        payload=SENSITIVE_SYNTHETIC_NOTE,
        producer=ProducerIdentity(
            kind=ProducerKind.IMPORT,
            identifier="synthetic-fhir-fixture",
            version="1.0.0",
        ),
        source_refs=(),
        review_state=ReviewState.IMPORTED,
    )
    assert record.source_refs == ()
    assert record.review_state is ReviewState.IMPORTED


def test_a_digest_that_does_not_match_its_payload_is_refused() -> None:
    record = describe_revision(
        binding=note_binding(),
        payload=SENSITIVE_SYNTHETIC_NOTE,
        producer=model_producer(),
        source_refs=(transcript_source(),),
        review_state=ReviewState.DRAFT,
    )
    with pytest.raises(ProvenanceDigestMismatchError):
        record.verify_payload(b"SYNTHETIC-NOT-REAL:other")


def test_provenance_serialization_is_deterministic() -> None:
    def build() -> bytes:
        return bytes(
            describe_revision(
                binding=note_binding(),
                payload=SENSITIVE_SYNTHETIC_NOTE,
                producer=model_producer(),
                source_refs=(transcript_source(),),
                review_state=ReviewState.DRAFT,
            ).canonical_bytes()
        )

    assert build() == build()
    assert b"source_document" not in build()


def test_provenance_survives_reopening_and_is_workspace_scoped(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    with open_store(tmp_path, root_secret=root_secret) as store:
        binding = note_binding()
        store_with_provenance(
            store,
            describe_revision(
                binding=binding,
                payload=SENSITIVE_SYNTHETIC_NOTE,
                producer=model_producer(),
                source_refs=(transcript_source(),),
                review_state=ReviewState.REVIEWED,
            ),
            SENSITIVE_SYNTHETIC_NOTE,
        )
    with open_store(tmp_path, root_secret=root_secret) as reopened:
        assert read_provenance(reopened, binding).review_state is ReviewState.REVIEWED
        with pytest.raises(WorkspaceIsolationError):
            read_provenance(reopened, note_binding(workspace_id=WORKSPACE_BETA))


def test_provenance_payload_is_absent_from_store_artifacts(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        binding = note_binding()
        store_with_provenance(
            store,
            describe_revision(
                binding=binding,
                payload=SENSITIVE_SYNTHETIC_NOTE,
                producer=model_producer(),
                source_refs=(transcript_source(),),
                review_state=ReviewState.DRAFT,
            ),
            SENSITIVE_SYNTHETIC_NOTE,
        )
        store_path = store.store_path
    blob = b"".join(path.read_bytes() for path in store_files(store_path))
    assert SENSITIVE_SYNTHETIC_NOTE not in blob
    assert b"synthetic provenance fixture" not in blob
    assert b"synthetic-transcript-0001" not in blob
    assert str(NOTE_OBJECT).encode("ascii") in blob


# ---------------------------------------------------------------------------
# Audit: append-only logical events
# ---------------------------------------------------------------------------


def test_audit_trail_appends_and_verifies(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        assert trail.head() is None
        first = trail.append(
            event_type=AuditEventType.WORKSPACE_OPEN,
            actor_id="synthetic-clinician",
            occurred_at=OCCURRED_AT_ONE,
        )
        second = trail.append(
            event_type=AuditEventType.PATIENT_READ,
            actor_id="synthetic-clinician",
            occurred_at=OCCURRED_AT_TWO,
            metadata=(("policy", "synthetic-only"),),
        )
        report = trail.verify()
        events = trail.events()
        anchored = trail.verify(expected_head_event_digest=second.event_digest)
        assert [event.sequence for event in events] == [1, 2]
        assert report.events_verified == 2
        assert report.first_sequence == 1
        assert report.last_sequence == 2
        assert report.head_event_digest == second.event_digest
        assert second.occurred_at == OCCURRED_AT_TWO
        assert second.metadata == (("policy", "synthetic-only"),)
        assert anchored.events_verified == 2
        assert anchored.head_event_digest == second.event_digest
    assert first.previous_event_digest == "0" * 64
    assert second.previous_event_digest == first.event_digest
    assert first.event_id == f"mesc-ws-audit/1:sha256:{first.event_digest}"


def test_audit_events_carry_no_payload_content(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        binding = note_binding()
        store.put_objects_atomic((ObjectWrite(binding=binding, payload=SENSITIVE_SYNTHETIC_NOTE),))
        trail = AuditTrail(store)
        event = trail.record_object_write(
            binding=binding,
            payload=SENSITIVE_SYNTHETIC_NOTE,
            actor_id="synthetic-clinician",
            occurred_at=OCCURRED_AT_ONE,
        )
        serialized = event.canonical_bytes()
        store_path = store.store_path
    assert SENSITIVE_SYNTHETIC_NOTE not in serialized
    assert b"synthetic provenance fixture" not in serialized
    assert event.object_refs[0].content_digest == content_digest_of(SENSITIVE_SYNTHETIC_NOTE)
    assert event.object_refs[0].object_id == NOTE_OBJECT
    assert event.object_refs[0].object_type is WorkspaceObjectType.ENCOUNTER
    blob = b"".join(path.read_bytes() for path in store_files(store_path))
    assert SENSITIVE_SYNTHETIC_NOTE not in blob


def test_deletion_preserves_audit_metadata_without_retaining_content(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    with open_store(tmp_path, root_secret=root_secret) as store:
        binding = note_binding()
        store.put_objects_atomic((ObjectWrite(binding=binding, payload=SENSITIVE_SYNTHETIC_NOTE),))
        trail = AuditTrail(store)
        trail.record_object_write(
            binding=binding,
            payload=SENSITIVE_SYNTHETIC_NOTE,
            actor_id="synthetic-clinician",
            occurred_at=OCCURRED_AT_ONE,
        )
        deletion = trail.record_object_deletion(
            binding=binding,
            actor_id="synthetic-clinician",
            occurred_at=OCCURRED_AT_TWO,
        )
        with pytest.raises(ObjectNotFoundError):
            store.get_object(binding)
        assert store.object_revisions(WorkspaceObjectType.ENCOUNTER) == ()
        trail.verify()
        store_path = store.store_path
    assert deletion.event_type is AuditEventType.OBJECT_DELETE
    reference = deletion.object_refs[0]
    assert reference.object_id == NOTE_OBJECT
    assert reference.object_revision == "rev-0001"
    assert reference.content_digest == content_digest_of(SENSITIVE_SYNTHETIC_NOTE)
    with open_store(tmp_path, root_secret=root_secret) as reopened:
        events = AuditTrail(reopened).events()
        assert [event.event_type for event in events] == [
            AuditEventType.OBJECT_CREATE,
            AuditEventType.OBJECT_DELETE,
        ]
    blob = b"".join(path.read_bytes() for path in store_files(store_path))
    assert SENSITIVE_SYNTHETIC_NOTE not in blob, "deleted content must not survive in the store"


def test_audit_spine_is_separate_from_provenance(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        binding = note_binding()
        store_with_provenance(
            store,
            describe_revision(
                binding=binding,
                payload=SENSITIVE_SYNTHETIC_NOTE,
                producer=model_producer(),
                source_refs=(transcript_source(),),
                review_state=ReviewState.FINALIZED,
            ),
            SENSITIVE_SYNTHETIC_NOTE,
        )
        AuditTrail(store).append(
            event_type=AuditEventType.NOTE_FINALIZE,
            actor_id="synthetic-clinician",
            occurred_at=OCCURRED_AT_THREE,
            object_refs=(
                AuditObjectRef(
                    object_id=binding.object_id,
                    object_type=binding.object_type,
                    object_revision=binding.object_revision,
                ),
            ),
        )
        provenance_ids = {
            object_id
            for object_id, _ in store.object_revisions(WorkspaceObjectType.PROVENANCE_RECORD)
        }
        audit_ids = {
            object_id for object_id, _ in store.object_revisions(WorkspaceObjectType.AUDIT_EVENT)
        }
    assert provenance_ids and audit_ids
    assert not (provenance_ids & audit_ids)


def test_audit_trail_exposes_no_hidden_mutation_surface() -> None:
    public_methods = {
        name
        for name, value in vars(AuditTrail).items()
        if not name.startswith("_") and callable(value)
    }
    assert public_methods == {
        "append",
        "events",
        "head",
        "record_object_deletion",
        "record_object_write",
        "verify",
    }, "the audit spine must expose no update or standalone delete surface"


def test_two_workspaces_have_independent_audit_chains(tmp_path: Path) -> None:
    root_secret = new_root_secret()
    with (
        open_store(tmp_path, workspace_id=WORKSPACE_ALPHA, root_secret=root_secret) as alpha,
        open_store(tmp_path, workspace_id=WORKSPACE_BETA, root_secret=root_secret) as beta,
    ):
        alpha_event = AuditTrail(alpha).append(
            event_type=AuditEventType.WORKSPACE_OPEN,
            actor_id="synthetic-alpha",
            occurred_at=OCCURRED_AT_ONE,
        )
        beta_report = AuditTrail(beta).verify()
        assert beta_report.events_verified == 0
        alpha_report = AuditTrail(alpha).verify()
        assert alpha_report.head_event_digest == alpha_event.event_digest
        assert alpha_event.workspace_id == WORKSPACE_ALPHA


def test_audit_and_provenance_modules_import_no_clock_logging_or_write_primitive() -> None:
    forbidden = {"datetime", "logging", "os", "socket", "subprocess", "time", "pathlib"}
    for module_name in ("audit.py", "provenance.py"):
        tree = ast.parse((WORKSPACE_MODULES / module_name).read_text(encoding="utf-8"))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".", 1)[0])
        assert not (imported & forbidden), f"{module_name} imports {sorted(imported & forbidden)}"


def test_delete_and_put_atomic_applies_both_or_neither(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        binding = note_binding()
        store.put_objects_atomic((ObjectWrite(binding=binding, payload=SENSITIVE_SYNTHETIC_NOTE),))
        from medscale_workspace.errors import StoreConflictError

        other = note_binding(revision="rev-0002")
        store.put_objects_atomic((ObjectWrite(binding=other, payload=b"SYNTHETIC:second"),))
        with pytest.raises(StoreConflictError):
            store.delete_and_put_atomic(
                deletions=(binding,),
                writes=(ObjectWrite(binding=other, payload=b"SYNTHETIC:duplicate-key"),),
            )
        assert store.get_object(binding) == SENSITIVE_SYNTHETIC_NOTE, "the deletion must roll back"
        assert store.get_object(other) == b"SYNTHETIC:second"
        assert store.object_count() == 2


def test_delete_and_put_atomic_requires_work(tmp_path: Path) -> None:
    with open_store(tmp_path) as store, pytest.raises(StoreIntegrityError):
        store.delete_and_put_atomic(deletions=(), writes=())


def test_object_revision_listing_is_deterministic(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        for revision in ("rev-0002", "rev-0001"):
            store.put_objects_atomic(
                (
                    ObjectWrite(
                        binding=note_binding(revision=revision),
                        payload=f"SYNTHETIC:{revision}".encode("ascii"),
                    ),
                )
            )
        first = store.object_revisions(WorkspaceObjectType.ENCOUNTER)
        second = store.object_revisions(WorkspaceObjectType.ENCOUNTER)
    assert first == second
    assert first == ((NOTE_OBJECT, "rev-0001"), (NOTE_OBJECT, "rev-0002"))


def test_store_files_keep_no_plaintext_after_provenance_and_audit_work(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        binding = note_binding()
        store_with_provenance(
            store,
            describe_revision(
                binding=binding,
                payload=SENSITIVE_SYNTHETIC_NOTE,
                producer=model_producer(),
                source_refs=(transcript_source(),),
                review_state=ReviewState.DRAFT,
            ),
            SENSITIVE_SYNTHETIC_NOTE,
        )
        trail = AuditTrail(store)
        trail.record_object_write(
            binding=binding,
            payload=SENSITIVE_SYNTHETIC_NOTE,
            actor_id="synthetic-clinician",
            occurred_at=OCCURRED_AT_ONE,
        )
        store_path = store.store_path
    blob = b"".join(path.read_bytes() for path in store_files(store_path))
    assert hashlib.sha256(SENSITIVE_SYNTHETIC_NOTE).hexdigest().encode("ascii") not in blob
    assert SENSITIVE_SYNTHETIC_NOTE not in blob
