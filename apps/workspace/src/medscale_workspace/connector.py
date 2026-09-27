"""Read-only external connector framework for CW-014.

Capability-scoped connector contracts without production credentials. Development
runs against mock/local fixture transports only: a transport exposes exactly one
``fetch`` method and this module performs no network I/O, no filesystem I/O, and
no model execution; it holds no network, filesystem, or model capability by design.

A manifest binds one connector identity to a non-empty subset of the admitted
read-only capabilities, a non-empty ``fixture://`` destination allowlist, timeout
and retry bounds, an offline flag, and an opaque credential reference. Secret
bytes never enter this module: the credential reference is an opaque identifier
and audit metadata records only whether a credential reference was bound, never
any secret material.

Every fetch refuses offline connectors without touching the transport, enforces
the destination allowlist and the capability set, retries transport-reported
temporary failures at most ``max_retries`` times, and refuses malformed or
oversized responses at named stages. Writes are mechanically disabled: no write
capability exists in the admitted set, no write entry point exists in this
module, and the transport contract exposes no write method.

Fetched envelopes are immutable stored objects with deterministic identities: a
new source version yields a new envelope identity and nothing overwrites. Every
read re-verifies the provenance digest and the workspace binding.

Response payload text is data, not authority. Payloads are stored verbatim,
never evaluated, never executed, and never consulted for capability, policy,
or governance decisions. Malicious strings remain inert.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID, uuid5

from medscale_workspace.audit import AuditEventType, AuditObjectRef, AuditTrail
from medscale_workspace.binding import ObjectBinding
from medscale_workspace.data_class import synthetic_data_class_value
from medscale_workspace.errors import (
    ConnectorConflictError,
    ConnectorInputError,
    ConnectorOfflineError,
    ConnectorRevisionError,
    ConnectorStaleError,
    ObjectNotFoundError,
    ProvenanceDigestMismatchError,
    StoreConflictError,
    TransportPermanentError,
    TransportTemporaryError,
    WorkspaceIsolationError,
)
from medscale_workspace.identity import WorkspaceObjectType
from medscale_workspace.provenance import (
    ProducerIdentity,
    ProducerKind,
    ReviewState,
    SourceKind,
    SourceRef,
    content_digest_of,
    describe_revision,
    provenance_binding_for,
    read_provenance,
    store_with_provenance,
)
from medscale_workspace.storage import WorkspaceStore
from medscale_workspace.versions import POLICY_VERSION

CONNECTOR_NAMESPACE = UUID("c014ec70-0004-4000-8000-000000000014")
CONNECTOR_REVISION = "connector-envelope-00000001"
PRODUCER_VERSION = "cw014-v1"
DERIVATION_METHOD = "cw014-deterministic-connector"
DERIVATION_METHOD_VERSION = "1"
SCHEMA_VERSION = "cw014-connector/1"
ENVELOPE_SCHEMA_VERSION = 1
DESTINATION_SCHEME = "fixture"
MAXIMUM_NAME_CHARS = 128
MAXIMUM_IDENTIFIER_CHARS = 128
MAXIMUM_DESTINATION_CHARS = 512
MAXIMUM_QUERY_CHARS = 512
MAXIMUM_VERSION_CHARS = 64
MAXIMUM_ENVELOPE_BYTES = 32768
MAXIMUM_VALUE_CHARS = 1024
MAXIMUM_VALUES_PER_LIST = 128
MAXIMUM_VALUE_DEPTH = 8
MINIMUM_TIMEOUT_MS = 1
MAXIMUM_TIMEOUT_MS = 60000
MAXIMUM_RETRIES = 5
MAXIMUM_OCCURRED_AT_CHARS = 64


class ConnectorCapability(StrEnum):
    """The read-only capabilities a connector manifest may admit.

    No write capability exists in this set by design: writes are mechanically
    disabled because they cannot be named, requested, or performed.
    """

    READ_FHIR = "read-fhir"
    READ_FILE = "read-file"
    READ_DIRECTORY = "read-directory"


@dataclass(frozen=True, slots=True)
class ConnectorManifest:
    """One validated connector contract held by the caller."""

    connector_id: UUID
    manifest_name: str
    manifest_version: str
    capabilities: tuple
    destinations: tuple
    timeout_ms: int
    max_retries: int
    offline: bool
    credential_id: str | None

    def validated(self):
        if not isinstance(self.connector_id, UUID):
            raise ConnectorInputError("a connector identity must be a UUID value")
        manifest_name = _admit_identifier(self.manifest_name, "connector name")
        manifest_version = _admit_identifier(self.manifest_version, "connector manifest version")
        if not isinstance(self.capabilities, tuple) or not self.capabilities:
            raise ConnectorInputError("a connector manifest needs a non-empty capability tuple")
        capabilities = tuple(_admit_capability(item) for item in self.capabilities)
        if len(set(capabilities)) != len(capabilities):
            raise ConnectorInputError("a connector manifest must not repeat a capability")
        if not isinstance(self.destinations, tuple) or not self.destinations:
            raise ConnectorInputError("a connector manifest needs a non-empty destination tuple")
        destinations = tuple(_admit_destination(item) for item in self.destinations)
        if len(set(destinations)) != len(destinations):
            raise ConnectorInputError("a connector manifest must not repeat a destination")
        timeout_ms = _admit_timeout(self.timeout_ms)
        max_retries = _admit_retries(self.max_retries)
        if not isinstance(self.offline, bool):
            raise ConnectorInputError("a connector offline flag must be a boolean")
        credential_id = None
        if self.credential_id is not None:
            credential_id = _admit_identifier(self.credential_id, "connector credential reference")
        return ConnectorManifest(
            connector_id=self.connector_id,
            manifest_name=manifest_name,
            manifest_version=manifest_version,
            capabilities=capabilities,
            destinations=destinations,
            timeout_ms=timeout_ms,
            max_retries=max_retries,
            offline=self.offline,
            credential_id=credential_id,
        )

    def to_document(self):
        return {
            "connector_id": str(self.connector_id),
            "manifest_name": self.manifest_name,
            "manifest_version": self.manifest_version,
            "capabilities": [item.value for item in self.capabilities],
            "destinations": list(self.destinations),
            "timeout_ms": self.timeout_ms,
            "max_retries": self.max_retries,
            "offline": self.offline,
            "credential_bound": self.credential_id is not None,
            "derivation_method": DERIVATION_METHOD,
            "derivation_version": DERIVATION_METHOD_VERSION,
            "schema_version": SCHEMA_VERSION,
            "data_class": synthetic_data_class_value(),
            "policy_version": POLICY_VERSION,
        }


@dataclass(frozen=True, slots=True)
class ConnectorEnvelope:
    """One immutable stored connector fetch result."""

    workspace_id: UUID
    envelope_id: UUID
    connector_id: UUID
    manifest_digest: str
    destination: str
    query: str
    query_digest: str
    source_version: str
    retrieved_at: str
    payload: tuple
    content_digest: str | None

    def validated(self):
        if not isinstance(self.workspace_id, UUID):
            raise ConnectorInputError("a connector workspace id must be a UUID value")
        if not isinstance(self.envelope_id, UUID):
            raise ConnectorInputError("a connector envelope identity must be a UUID value")
        if not isinstance(self.connector_id, UUID):
            raise ConnectorInputError("a connector identity must be a UUID value")
        manifest_digest = _admit_digest(self.manifest_digest)
        destination = _admit_destination(self.destination)
        query = _admit_query(self.query)
        query_digest = _admit_digest(self.query_digest)
        source_version = _admit_version(self.source_version)
        retrieved_at = _admit_occurred_at(self.retrieved_at)
        if not isinstance(self.payload, tuple):
            raise ConnectorInputError("connector payload must be a tuple of entries")
        payload = tuple(_validated_payload_entry(item) for item in self.payload)
        content_digest = None
        if self.content_digest is not None:
            content_digest = _admit_digest(self.content_digest)
        return ConnectorEnvelope(
            workspace_id=self.workspace_id,
            envelope_id=self.envelope_id,
            connector_id=self.connector_id,
            manifest_digest=manifest_digest,
            destination=destination,
            query=query,
            query_digest=query_digest,
            source_version=source_version,
            retrieved_at=retrieved_at,
            payload=payload,
            content_digest=content_digest,
        )

    def to_document(self):
        return {
            "workspace_id": str(self.workspace_id),
            "envelope_id": str(self.envelope_id),
            "connector_id": str(self.connector_id),
            "manifest_digest": self.manifest_digest,
            "destination": self.destination,
            "query": self.query,
            "query_digest": self.query_digest,
            "source_version": self.source_version,
            "retrieved_at": self.retrieved_at,
            "payload": [_payload_entry_to_document(item) for item in self.payload],
            "content_digest": self.content_digest,
            "derivation_method": DERIVATION_METHOD,
            "derivation_version": DERIVATION_METHOD_VERSION,
            "envelope_schema_version": ENVELOPE_SCHEMA_VERSION,
            "data_class": synthetic_data_class_value(),
            "policy_version": POLICY_VERSION,
        }

    @staticmethod
    def from_document(document):
        if not isinstance(document, dict):
            raise ConnectorInputError("a stored connector envelope must be a JSON object")
        expected = (
            "workspace_id",
            "envelope_id",
            "connector_id",
            "manifest_digest",
            "destination",
            "query",
            "query_digest",
            "source_version",
            "retrieved_at",
            "payload",
            "content_digest",
            "derivation_method",
            "derivation_version",
            "envelope_schema_version",
            "data_class",
            "policy_version",
        )
        for name in expected:
            if name not in document:
                raise ConnectorInputError("a stored connector envelope is missing a member")
        try:
            workspace_id = UUID(str(document["workspace_id"]))
        except ValueError as error:
            raise ConnectorInputError("a stored connector workspace id is not a UUID") from error
        try:
            envelope_id = UUID(str(document["envelope_id"]))
        except ValueError as error:
            raise ConnectorInputError(
                "a stored connector envelope identity is not a UUID"
            ) from error
        try:
            connector_id = UUID(str(document["connector_id"]))
        except ValueError as error:
            raise ConnectorInputError("a stored connector identity is not a UUID") from error
        raw_payload = document["payload"]
        if not isinstance(raw_payload, list):
            raise ConnectorInputError("stored connector payload must be a JSON array")
        if document["derivation_method"] != DERIVATION_METHOD:
            raise ConnectorInputError("a stored connector derivation method is not admitted here")
        if document["derivation_version"] != DERIVATION_METHOD_VERSION:
            raise ConnectorInputError("a stored connector derivation version is not admitted here")
        schema = document["envelope_schema_version"]
        if isinstance(schema, bool) or schema != ENVELOPE_SCHEMA_VERSION:
            raise ConnectorInputError("a stored connector schema version is not admitted here")
        if document["data_class"] != synthetic_data_class_value():
            raise ConnectorInputError("a stored connector data class is not admitted here")
        if document["policy_version"] != POLICY_VERSION:
            raise ConnectorInputError("a stored connector policy version is not admitted here")
        for name in ("manifest_digest", "query_digest"):
            if not isinstance(document[name], str):
                raise ConnectorInputError(f"a stored {name} must be a string")
        if document["content_digest"] is not None and not isinstance(
            document["content_digest"], str
        ):
            raise ConnectorInputError("a stored content digest must be a string or null")
        for name in ("destination", "query", "source_version", "retrieved_at"):
            if not isinstance(document[name], str):
                raise ConnectorInputError(f"a stored {name} must be a string")
        return ConnectorEnvelope(
            workspace_id=workspace_id,
            envelope_id=envelope_id,
            connector_id=connector_id,
            manifest_digest=document["manifest_digest"],
            destination=document["destination"],
            query=document["query"],
            query_digest=document["query_digest"],
            source_version=document["source_version"],
            retrieved_at=document["retrieved_at"],
            payload=tuple(_payload_entry_from_document(item) for item in raw_payload),
            content_digest=document["content_digest"],
        ).validated()


def connector_id_for(manifest_name):
    """Return the deterministic identity of one named connector."""
    admitted = _admit_identifier(manifest_name, "connector name")
    return uuid5(CONNECTOR_NAMESPACE, admitted)


def manifest_digest_for(manifest):
    """Return the digest binding one validated manifest revision."""
    admitted = manifest.validated()
    return content_digest_of(_canonical_bytes(admitted.to_document()))


def envelope_id_for(workspace_id, connector_id, destination, query, source_version):
    """Return the deterministic identity of one connector fetch result."""
    if not isinstance(workspace_id, UUID):
        raise ConnectorInputError("a workspace id must be a UUID value")
    if not isinstance(connector_id, UUID):
        raise ConnectorInputError("a connector identity must be a UUID value")
    admitted_destination = _admit_destination(destination)
    admitted_query = _admit_query(query)
    admitted_version = _admit_version(source_version)
    query_digest = content_digest_of(admitted_query.encode("ascii"))
    return uuid5(
        CONNECTOR_NAMESPACE,
        ":".join(
            (
                str(workspace_id),
                str(connector_id),
                admitted_destination,
                query_digest,
                admitted_version,
            )
        ),
    )


def envelope_binding(workspace_id, envelope_id):
    """Return the store binding of one admitted connector envelope."""
    if not isinstance(workspace_id, UUID):
        raise ConnectorInputError("a workspace id must be a UUID value")
    if not isinstance(envelope_id, UUID):
        raise ConnectorInputError("a connector envelope identity must be a UUID value")
    return ObjectBinding(
        workspace_id=workspace_id,
        object_id=envelope_id,
        object_type=WorkspaceObjectType.CONNECTOR_ENVELOPE,
        object_revision=CONNECTOR_REVISION,
    )


def admit_manifest(
    manifest_name,
    manifest_version,
    capabilities,
    destinations,
    timeout_ms,
    max_retries,
    offline=False,
    credential_id=None,
):
    """Validate one connector manifest without storing anything."""
    if not isinstance(capabilities, tuple):
        raise ConnectorInputError("a connector manifest needs a capability tuple")
    if not isinstance(destinations, tuple):
        raise ConnectorInputError("a connector manifest needs a destination tuple")
    return ConnectorManifest(
        connector_id=connector_id_for(manifest_name),
        manifest_name=manifest_name,
        manifest_version=manifest_version,
        capabilities=capabilities,
        destinations=destinations,
        timeout_ms=timeout_ms,
        max_retries=max_retries,
        offline=offline,
        credential_id=credential_id,
    ).validated()


def fetch_envelope(
    store,
    trail,
    workspace_id,
    manifest,
    transport,
    destination,
    query,
    capability,
    actor_id,
    occurred_at,
):
    """Fetch one read-only connector result through a fixture transport.

    Offline connectors are refused without touching the transport. Temporary
    transport failures are retried at most ``max_retries`` times; anything else
    fails explicitly. The response is validated, stored as an immutable
    envelope with provenance, and recorded with a redacted audit event.
    """
    if not isinstance(store, WorkspaceStore):
        raise ConnectorInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise ConnectorInputError("an audit trail is required")
    if not isinstance(workspace_id, UUID):
        raise ConnectorInputError("a workspace id must be a UUID value")
    if workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a connector fetch crossed the workspace boundary")
    admitted = manifest.validated()
    if admitted.offline:
        raise ConnectorOfflineError("the connector declares offline state")
    admitted_destination = _admit_destination(destination)
    if admitted_destination not in admitted.destinations:
        raise ConnectorInputError("the fetch destination is not allowlisted")
    admitted_capability = _admit_capability(capability)
    if admitted_capability not in admitted.capabilities:
        raise ConnectorInputError("the fetch capability is not admitted by the manifest")
    admitted_query = _admit_query(query)
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    fetch = getattr(transport, "fetch", None)
    if not callable(fetch):
        raise ConnectorInputError("a fixture transport needs a fetch method")
    attempts = 1 + admitted.max_retries
    response = None
    for _attempt in range(attempts):
        try:
            response = fetch(
                destination=admitted_destination,
                query=admitted_query,
                timeout_ms=admitted.timeout_ms,
            )
        except TransportTemporaryError:
            response = None
            continue
        except TransportPermanentError as error:
            raise ConnectorInputError("the fixture transport refused the fetch") from error
        break
    if response is None:
        raise ConnectorRevisionError("the connector fetch failed after its retry bound")
    source_version, retrieved_at, payload = _admit_response(response)
    query_digest = content_digest_of(admitted_query.encode("ascii"))
    envelope = ConnectorEnvelope(
        workspace_id=workspace_id,
        envelope_id=envelope_id_for(
            workspace_id,
            admitted.connector_id,
            admitted_destination,
            admitted_query,
            source_version,
        ),
        connector_id=admitted.connector_id,
        manifest_digest=manifest_digest_for(admitted),
        destination=admitted_destination,
        query=admitted_query,
        query_digest=query_digest,
        source_version=source_version,
        retrieved_at=retrieved_at,
        payload=payload,
        content_digest=None,
    ).validated()
    binding = envelope_binding(workspace_id, envelope.envelope_id)
    stored = _canonical_bytes(envelope.to_document())
    producer = ProducerIdentity(
        kind=ProducerKind.IMPORT, identifier=actor, version=PRODUCER_VERSION
    )
    source_refs = (
        SourceRef(
            kind=SourceKind.CONNECTOR_RESPONSE,
            source_id=str(envelope.envelope_id),
            source_revision=envelope.source_version,
            locator=admitted_destination,
        ),
    )
    record = describe_revision(
        binding=binding,
        payload=stored,
        producer=producer,
        source_refs=source_refs,
        review_state=ReviewState.IMPORTED,
    )
    try:
        store_with_provenance(store, record, stored)
    except StoreConflictError as error:
        raise ConnectorConflictError("the connector envelope identity already exists") from error
    trail.append(
        event_type=AuditEventType.CONNECTOR_READ,
        actor_id=actor,
        occurred_at=moment,
        object_refs=(
            AuditObjectRef(
                object_id=envelope.envelope_id,
                object_type=WorkspaceObjectType.CONNECTOR_ENVELOPE,
                object_revision=CONNECTOR_REVISION,
                content_digest=record.content_digest,
            ),
        ),
        metadata=(
            ("connector_id", str(admitted.connector_id)),
            ("destination", admitted_destination),
            ("source_version", source_version),
            ("envelope_digest", record.content_digest),
            ("credential_bound", "true" if admitted.credential_id is not None else "false"),
        ),
    )
    return binding


def read_envelope(store, envelope_id):
    """Read and verify one stored connector envelope."""
    if not isinstance(store, WorkspaceStore):
        raise ConnectorInputError("a workspace store is required")
    if not isinstance(envelope_id, UUID):
        raise ConnectorInputError("a connector envelope identity must be a UUID value")
    binding = envelope_binding(store.workspace_id, envelope_id)
    try:
        raw = store.get_object(binding)
    except ObjectNotFoundError as error:
        raise ConnectorInputError("the connector identity is not present in this store") from error
    try:
        text = raw.decode("ascii")
    except UnicodeDecodeError as error:
        raise ConnectorInputError("a stored connector envelope is not ASCII JSON") from error
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as error:
        raise ConnectorInputError("a stored connector envelope is not JSON") from error
    envelope = ConnectorEnvelope.from_document(payload)
    if envelope.workspace_id != store.workspace_id:
        raise WorkspaceIsolationError("a connector envelope crossed the workspace boundary")
    if envelope.envelope_id != envelope_id:
        raise ConnectorInputError("a stored connector identity does not match its binding")
    record = read_provenance(store, binding)
    try:
        record.verify_payload(raw)
    except ProvenanceDigestMismatchError as error:
        raise ConnectorStaleError("a connector envelope digest no longer matches") from error
    return envelope.validated()


def delete_envelope(store, trail, envelope_id, actor_id, occurred_at):
    """Delete one admitted connector envelope; the audit trail survives."""
    if not isinstance(store, WorkspaceStore):
        raise ConnectorInputError("a workspace store is required")
    if not isinstance(trail, AuditTrail):
        raise ConnectorInputError("an audit trail is required")
    if not isinstance(envelope_id, UUID):
        raise ConnectorInputError("a connector envelope identity must be a UUID value")
    actor = _admit_identifier(actor_id, "actor id")
    moment = _admit_occurred_at(occurred_at)
    envelope = read_envelope(store, envelope_id)
    binding = envelope_binding(store.workspace_id, envelope.envelope_id)
    trail.record_object_deletion(binding=binding, actor_id=actor, occurred_at=moment)
    trail.record_object_deletion(
        binding=provenance_binding_for(binding), actor_id=actor, occurred_at=moment
    )
    return binding


def _admit_response(response):
    if not isinstance(response, dict):
        raise ConnectorInputError("a connector response must be a JSON object")
    for name in ("source_version", "retrieved_at", "payload"):
        if name not in response:
            raise ConnectorInputError("a connector response is missing a member")
    source_version = _admit_version(response["source_version"])
    retrieved_at = _admit_occurred_at(response["retrieved_at"])
    payload = _freeze_value(response["payload"], 0)
    encoded = _canonical_bytes({"payload": _payload_value_to_json(payload)})
    if len(encoded) > MAXIMUM_ENVELOPE_BYTES:
        raise ConnectorInputError("a connector response exceeds the admitted envelope size")
    if isinstance(payload, tuple):
        return source_version, retrieved_at, payload
    return source_version, retrieved_at, (("value", payload),)


def _admit_capability(raw):
    if isinstance(raw, ConnectorCapability):
        return raw
    if isinstance(raw, str):
        try:
            return ConnectorCapability(raw.strip())
        except ValueError as error:
            raise ConnectorInputError("a connector capability is not admitted here") from error
    raise ConnectorInputError("a connector capability must be admitted here")


def _admit_destination(raw):
    value = _admit_path(raw, "connector destination")
    if "://" not in value:
        raise ConnectorInputError("a connector destination needs a scheme")
    scheme, _, rest = value.partition("://")
    if scheme != DESTINATION_SCHEME:
        raise ConnectorInputError("a connector destination must use the fixture scheme")
    if not rest or rest.startswith("/"):
        raise ConnectorInputError("a connector destination needs a fixture name")
    for segment in rest.split("/"):
        if not segment:
            raise ConnectorInputError("a connector destination must not carry empty segments")
        if segment == "..":
            raise ConnectorInputError("a connector destination must not traverse upwards")
    return value


def _admit_query(raw):
    if not isinstance(raw, str):
        raise ConnectorInputError("a connector query must be a string")
    value = raw.strip()
    if not value:
        raise ConnectorInputError("a connector query must be non-empty")
    if len(value) > MAXIMUM_QUERY_CHARS:
        raise ConnectorInputError("a connector query is longer than the admitted maximum")
    if not value.isascii():
        raise ConnectorInputError("a connector query must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise ConnectorInputError("a connector query must not contain whitespace or controls")
    return value


def _admit_version(raw):
    if not isinstance(raw, str):
        raise ConnectorInputError("a connector version must be a string")
    value = raw.strip()
    if not value:
        raise ConnectorInputError("a connector version must be non-empty")
    if len(value) > MAXIMUM_VERSION_CHARS:
        raise ConnectorInputError("a connector version is longer than the admitted maximum")
    if not value.isascii():
        raise ConnectorInputError("a connector version must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise ConnectorInputError("a connector version must not contain whitespace or controls")
    return value


def _admit_timeout(raw):
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise ConnectorInputError("a connector timeout must be an integer of milliseconds")
    if raw < MINIMUM_TIMEOUT_MS or raw > MAXIMUM_TIMEOUT_MS:
        raise ConnectorInputError("a connector timeout is outside the admitted bounds")
    return raw


def _admit_retries(raw):
    if not isinstance(raw, int) or isinstance(raw, bool):
        raise ConnectorInputError("a connector retry bound must be an integer")
    if raw < 0 or raw > MAXIMUM_RETRIES:
        raise ConnectorInputError("a connector retry bound is outside the admitted limit")
    return raw


def _freeze_value(value, depth):
    if depth > MAXIMUM_VALUE_DEPTH:
        raise ConnectorInputError("a connector value is nested too deeply")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        if len(value) > MAXIMUM_VALUE_CHARS:
            raise ConnectorInputError("a connector string value is too long")
        return value
    if isinstance(value, list):
        if len(value) > MAXIMUM_VALUES_PER_LIST:
            raise ConnectorInputError("a connector list value carries too many members")
        return tuple(_freeze_value(item, depth + 1) for item in value)
    if isinstance(value, dict):
        frozen = []
        for name in sorted(value):
            if not isinstance(name, str):
                raise ConnectorInputError("a connector object key must be a string")
            frozen.append((name, _freeze_value(value[name], depth + 1)))
        return tuple(frozen)
    raise ConnectorInputError("a connector value has an unadmitted JSON type")


def _validated_payload_entry(entry):
    if not isinstance(entry, tuple) or len(entry) != 2:
        raise ConnectorInputError("connector payload needs key/value entries")
    name, value = entry
    _admit_identifier(name, "connector payload key")
    return (name, _freeze_value(_thaw_value(value), 0))


def _thaw_value(value):
    if isinstance(value, tuple):
        if value and all(
            isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
            for item in value
        ):
            return {item[0]: _thaw_value(item[1]) for item in value}
        return [_thaw_value(item) for item in value]
    if isinstance(value, list):
        return [_thaw_value(item) for item in value]
    return value


def _payload_entry_to_document(entry):
    name, value = entry
    return {"key": name, "value": _payload_value_to_json(value)}


def _payload_entry_from_document(document):
    if not isinstance(document, dict):
        raise ConnectorInputError("a stored connector payload entry must be a JSON object")
    if "key" not in document or "value" not in document:
        raise ConnectorInputError("a stored connector payload entry is missing a member")
    if not isinstance(document["key"], str):
        raise ConnectorInputError("a stored connector payload key must be a string")
    return (document["key"], _payload_value_from_json(document["value"]))


def _payload_value_to_json(value):
    if isinstance(value, tuple):
        if value and all(
            isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], str)
            for item in value
        ):
            document = {}
            for item in value:
                document[item[0]] = _payload_value_to_json(item[1])
            return {"object": document}
        return [_payload_value_to_json(item) for item in value]
    if isinstance(value, list):
        return [_payload_value_to_json(item) for item in value]
    return value


def _payload_value_from_json(document):
    if isinstance(document, dict) and set(document) == {"object"}:
        frozen = []
        for name in sorted(document["object"]):
            frozen.append((name, _payload_value_from_json(document["object"][name])))
        return tuple(frozen)
    if isinstance(document, list):
        return tuple(_payload_value_from_json(item) for item in document)
    return document


def _admit_identifier(raw, label):
    if not isinstance(raw, str):
        raise ConnectorInputError(f"{label} must be a string")
    value = raw.strip()
    if not value:
        raise ConnectorInputError(f"{label} must be non-empty")
    if len(value) > MAXIMUM_IDENTIFIER_CHARS:
        raise ConnectorInputError(f"{label} is longer than the admitted maximum")
    if not value.isascii():
        raise ConnectorInputError(f"{label} must be ASCII")
    for character in value:
        if character.isspace() or not character.isprintable():
            raise ConnectorInputError(f"{label} must not contain whitespace or controls")
    return value


def _admit_digest(raw):
    if not isinstance(raw, str) or not raw.startswith("sha256:"):
        raise ConnectorInputError("content digest must be a sha256: digest")
    hex_part = raw[len("sha256:") :]
    if len(hex_part) != 64 or any(character not in "0123456789abcdef" for character in hex_part):
        raise ConnectorInputError("content digest must carry 64 lowercase hex characters")
    return raw


def _admit_occurred_at(raw):
    if not isinstance(raw, str):
        raise ConnectorInputError("a connector occurrence time must be a string")
    value = raw.strip()
    if not value:
        raise ConnectorInputError("a connector occurrence time must be non-empty")
    if len(value) > MAXIMUM_OCCURRED_AT_CHARS:
        raise ConnectorInputError("a connector occurrence time is longer than the admitted maximum")
    if len(value) < 20 or value[10:11] != "T":
        raise ConnectorInputError("a connector occurrence time must be an ISO-8601 instant")
    if not value.isascii():
        raise ConnectorInputError("a connector occurrence time must be ASCII")
    return value


def _admit_path(raw, label):
    if not isinstance(raw, str):
        raise ConnectorInputError(f"a {label} must be a string")
    value = raw.strip()
    if not value:
        raise ConnectorInputError(f"a {label} must be non-empty")
    if len(value) > MAXIMUM_DESTINATION_CHARS:
        raise ConnectorInputError(f"a {label} is longer than the admitted maximum")
    if not value.isascii():
        raise ConnectorInputError(f"a {label} must be ASCII")
    for character in value:
        if not character.isprintable() or character.isspace():
            raise ConnectorInputError(f"a {label} must not contain whitespace or controls")
    if "\\" in value:
        raise ConnectorInputError(f"a {label} must use forward slashes")
    return value


def _canonical_bytes(document):
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "ascii"
    )
