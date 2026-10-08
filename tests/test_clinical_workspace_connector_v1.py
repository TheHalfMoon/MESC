"""CW-014 acceptance tests: read-only connector framework over fixture transports."""

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
from medscale_workspace import connector as connector_mod  # noqa: E402 runtime import
from medscale_workspace.errors import (  # noqa: E402 runtime import
    ConnectorConflictError,
    ConnectorInputError,
    ConnectorOfflineError,
    ConnectorRevisionError,
    TransportPermanentError,
    TransportTemporaryError,
)
from medscale_workspace.keyprovider import (  # noqa: E402 runtime import
    InMemoryTestKeyProvider,
    new_root_secret,
)
from medscale_workspace.provenance import (  # noqa: E402 runtime import
    SourceKind,
    read_provenance,
)

APPLICATION_VERSION = medscale_workspace.__version__
WORKSPACE_ALPHA = UUID("6cd9e9f4-1c3b-40b4-b10f-5b16db71a9fe")
ACTOR = "synthetic-operator"
T1 = "2026-09-24T10:00:00+03:00"
T2 = "2026-09-24T10:01:00+03:00"
DESTINATION = "fixture://synthetic-fhir/observations"
QUERY = "Observation?patient=pat-001"


class FixtureTransport:
    """Deterministic in-memory fixture transport with scripted behavior."""

    def __init__(
        self,
        payload: dict[str, object] | None = None,
        source_version: str = "1",
        failures: tuple[object, ...] = (),
    ) -> None:
        self.payload: dict[str, object] = {"synthetic": "response"} if payload is None else payload
        self.source_version = source_version
        self.failures: list[object] = list(failures)
        self.calls: list[dict[str, object]] = []

    def fetch(self, *, destination: str, query: str, timeout_ms: int) -> dict[str, object]:
        self.calls.append({"destination": destination, "query": query, "timeout_ms": timeout_ms})
        if self.failures:
            behavior = self.failures.pop(0)
            if isinstance(behavior, BaseException):
                raise behavior
            raise TransportTemporaryError("scripted transport failure")
        return {
            "source_version": self.source_version,
            "retrieved_at": T1,
            "payload": self.payload,
        }


def open_store(root: Path, workspace_id: UUID = WORKSPACE_ALPHA) -> WorkspaceStore:
    return WorkspaceStore.open(
        store_root=str(root),
        workspace_id=workspace_id,
        key_provider=InMemoryTestKeyProvider(new_root_secret()),
        application_version=APPLICATION_VERSION,
    )


def admit_manifest(**overrides: object) -> connector_mod.ConnectorManifest:
    arguments: dict[str, object] = {
        "manifest_name": "synthetic-connector",
        "manifest_version": "1",
        "capabilities": (connector_mod.ConnectorCapability.READ_FHIR,),
        "destinations": (DESTINATION,),
        "timeout_ms": 1000,
        "max_retries": 2,
        "offline": False,
        "credential_id": None,
    }
    arguments.update(overrides)
    return connector_mod.admit_manifest(**arguments)


def test_capability_manifest_least_privilege(tmp_path: Path) -> None:
    manifest = admit_manifest()
    assert connector_mod.ConnectorCapability.READ_FHIR in manifest.capabilities
    with pytest.raises(ConnectorInputError):
        admit_manifest(capabilities=())
    with pytest.raises(ConnectorInputError):
        admit_manifest(capabilities=("WRITE_FHIR",))
    with pytest.raises(ConnectorInputError):
        admit_manifest(
            capabilities=(
                connector_mod.ConnectorCapability.READ_FHIR,
                connector_mod.ConnectorCapability.READ_FHIR,
            )
        )
    with pytest.raises(ConnectorInputError):
        admit_manifest(
            capabilities=(
                connector_mod.ConnectorCapability.READ_FHIR,
                "read-patients-and-write-everything",
            )
        )


def test_destination_allowlist_enforced(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        manifest = admit_manifest()
        transport = FixtureTransport()
        with pytest.raises(ConnectorInputError):
            connector_mod.fetch_envelope(
                store,
                trail,
                WORKSPACE_ALPHA,
                manifest,
                transport,
                "fixture://elsewhere/observations",
                QUERY,
                connector_mod.ConnectorCapability.READ_FHIR,
                ACTOR,
                T1,
            )
        assert transport.calls == []
        with pytest.raises(ConnectorInputError):
            admit_manifest(destinations=("https://example.invalid/fhir",))
        with pytest.raises(ConnectorInputError):
            admit_manifest(destinations=("fixture://synthetic/../escape",))


def test_timeout_retry_bounds_and_offline_state(tmp_path: Path) -> None:
    with pytest.raises(ConnectorInputError):
        admit_manifest(timeout_ms=0)
    with pytest.raises(ConnectorInputError):
        admit_manifest(timeout_ms=60001)
    with pytest.raises(ConnectorInputError):
        admit_manifest(max_retries=6)
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        manifest = admit_manifest()
        flaky = FixtureTransport(
            failures=(
                TransportTemporaryError("boom"),
                TransportTemporaryError("boom"),
            )
        )
        binding = connector_mod.fetch_envelope(
            store,
            trail,
            WORKSPACE_ALPHA,
            manifest,
            flaky,
            DESTINATION,
            QUERY,
            connector_mod.ConnectorCapability.READ_FHIR,
            ACTOR,
            T1,
        )
        assert len(flaky.calls) == 3
        assert all(item["timeout_ms"] == 1000 for item in flaky.calls)
        assert binding.object_id is not None
        down = FixtureTransport(
            failures=(
                TransportTemporaryError("boom"),
                TransportTemporaryError("boom"),
                TransportTemporaryError("boom"),
            )
        )
        with pytest.raises(ConnectorRevisionError):
            connector_mod.fetch_envelope(
                store,
                trail,
                WORKSPACE_ALPHA,
                manifest,
                down,
                DESTINATION,
                "Observation?patient=pat-002",
                connector_mod.ConnectorCapability.READ_FHIR,
                ACTOR,
                T1,
            )
        offline_manifest = admit_manifest(offline=True)
        quiet = FixtureTransport()
        with pytest.raises(ConnectorOfflineError):
            connector_mod.fetch_envelope(
                store,
                trail,
                WORKSPACE_ALPHA,
                offline_manifest,
                quiet,
                DESTINATION,
                QUERY,
                connector_mod.ConnectorCapability.READ_FHIR,
                ACTOR,
                T1,
            )
        assert quiet.calls == []


def test_stale_version_metadata_yields_new_identity(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        manifest = admit_manifest()
        first = connector_mod.fetch_envelope(
            store,
            trail,
            WORKSPACE_ALPHA,
            manifest,
            FixtureTransport(source_version="1"),
            DESTINATION,
            QUERY,
            connector_mod.ConnectorCapability.READ_FHIR,
            ACTOR,
            T1,
        )
        second = connector_mod.fetch_envelope(
            store,
            trail,
            WORKSPACE_ALPHA,
            manifest,
            FixtureTransport(source_version="2"),
            DESTINATION,
            QUERY,
            connector_mod.ConnectorCapability.READ_FHIR,
            ACTOR,
            T2,
        )
        assert first.object_id != second.object_id
        assert connector_mod.read_envelope(store, UUID(str(first.object_id))).source_version == "1"
        assert connector_mod.read_envelope(store, UUID(str(second.object_id))).source_version == "2"
        with pytest.raises(ConnectorConflictError):
            connector_mod.fetch_envelope(
                store,
                trail,
                WORKSPACE_ALPHA,
                manifest,
                FixtureTransport(source_version="1"),
                DESTINATION,
                QUERY,
                connector_mod.ConnectorCapability.READ_FHIR,
                ACTOR,
                T1,
            )


class RawTransport:
    """Fixture transport returning a fixed raw response object verbatim."""

    def __init__(self, raw: object) -> None:
        self.raw = raw

    def fetch(self, *, destination: str, query: str, timeout_ms: int) -> object:
        return self.raw


class RejectingTransport:
    """Fixture transport refusing every fetch as a permanent failure."""

    def fetch(self, *, destination: str, query: str, timeout_ms: int) -> object:
        raise TransportPermanentError("rejected")


def test_malformed_responses_fail_explicitly(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        manifest = admit_manifest()
        for bad_response, query in (
            ({"not": "a response"}, "q-malformed-1"),
            ({"source_version": "1"}, "q-malformed-2"),
            ("a string response", "q-malformed-3"),
            (["a list response"], "q-malformed-4"),
            (
                {
                    "source_version": "1",
                    "retrieved_at": T1,
                    "payload": {f"key-{index:03d}": "z" * 900 for index in range(40)},
                },
                "q-malformed-5",
            ),
            (
                {
                    "source_version": "1",
                    "retrieved_at": T1,
                    "payload": {"oversized": "x" * 2000},
                },
                "q-malformed-6",
            ),
        ):
            transport = RawTransport(bad_response)
            with pytest.raises(ConnectorInputError):
                connector_mod.fetch_envelope(
                    store,
                    trail,
                    WORKSPACE_ALPHA,
                    manifest,
                    transport,
                    DESTINATION,
                    query,
                    connector_mod.ConnectorCapability.READ_FHIR,
                    ACTOR,
                    T1,
                )
        permanent = RejectingTransport()
        with pytest.raises(ConnectorInputError):
            connector_mod.fetch_envelope(
                store,
                trail,
                WORKSPACE_ALPHA,
                manifest,
                permanent,
                DESTINATION,
                "q-permanent",
                connector_mod.ConnectorCapability.READ_FHIR,
                ACTOR,
                T1,
            )


def test_writes_mechanically_disabled(tmp_path: Path) -> None:
    assert not hasattr(connector_mod, "write_envelope")
    assert not hasattr(connector_mod, "store_write")
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        manifest = admit_manifest()
        binding = connector_mod.fetch_envelope(
            store,
            trail,
            WORKSPACE_ALPHA,
            manifest,
            FixtureTransport(),
            DESTINATION,
            QUERY,
            connector_mod.ConnectorCapability.READ_FHIR,
            ACTOR,
            T1,
        )
        assert binding.object_id is not None
        kinds = [event.event_type for event in trail.events()]
        assert connector_mod.AuditEventType.CONNECTOR_READ in kinds
        assert connector_mod.AuditEventType.CONNECTOR_WRITE not in kinds


def test_connector_provenance_mapping(tmp_path: Path) -> None:
    with open_store(tmp_path) as store:
        trail = AuditTrail(store)
        manifest = admit_manifest(credential_id="synthetic-credential-001")
        binding = connector_mod.fetch_envelope(
            store,
            trail,
            WORKSPACE_ALPHA,
            manifest,
            FixtureTransport(),
            DESTINATION,
            QUERY,
            connector_mod.ConnectorCapability.READ_FHIR,
            ACTOR,
            T1,
        )
        record = read_provenance(store, binding)
        kinds = [item.kind for item in record.source_refs]
        assert SourceKind.CONNECTOR_RESPONSE in kinds
        record.verify_payload(store.get_object(binding))
        stored = connector_mod.read_envelope(store, UUID(str(binding.object_id)))
        assert stored.destination == DESTINATION
        assert stored.query == QUERY
