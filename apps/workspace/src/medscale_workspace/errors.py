"""Typed fail-closed errors for CW-002 protected local storage.

Every CW-002 failure is a distinct class so callers never have to parse messages to
decide what happened, and so a failure can never be silently reinterpreted as a
success or downgraded into a plaintext fallback.
"""

from __future__ import annotations


class WorkspaceStoreError(Exception):
    """Base class for every CW-002 storage, key, envelope and version failure."""


class StorePathError(WorkspaceStoreError):
    """The workspace store path is not a single admitted file path."""


class ObjectBindingError(WorkspaceStoreError):
    """An object binding is malformed or not immutable enough to bind as AEAD data."""


class KeyProviderUnavailableError(WorkspaceStoreError):
    """Protected key storage is unavailable; CW-002 has no plaintext fallback."""


class KeyMaterialUnavailableError(WorkspaceStoreError):
    """The requested key version cannot be produced by the active key provider."""


class KeyStateError(WorkspaceStoreError):
    """A key version was used in a state the CW-002 key state machine forbids."""


class KeyRotationError(WorkspaceStoreError):
    """A key-rotation transition violated its preconditions."""


class EnvelopeFormatError(WorkspaceStoreError):
    """The envelope is malformed or uses an unsupported encryption format version."""


class EnvelopeAuthenticationError(WorkspaceStoreError):
    """AEAD authentication failed: the ciphertext or its binding was altered."""


class StoreVersionError(WorkspaceStoreError):
    """Recorded store versions are absent, unreadable, or unsupported here."""


class StoreIntegrityError(WorkspaceStoreError):
    """A declared store invariant is violated (key state, metadata, pragmas)."""


class WorkspaceIsolationError(WorkspaceStoreError):
    """An operation crossed the workspace boundary and was refused."""


class ObjectNotFoundError(WorkspaceStoreError):
    """The requested object revision is not present in this workspace store."""


class StoreConflictError(WorkspaceStoreError):
    """An immutable object revision already exists and cannot be overwritten."""


class ProvenanceError(WorkspaceStoreError):
    """A provenance record is malformed or its declared identity is not truthful."""


class ProvenanceDigestMismatchError(ProvenanceError):
    """The recorded content digest does not match the payload bound to it."""


class AuditError(WorkspaceStoreError):
    """An audit event is malformed or was not produced by this audit spine."""


class AuditChainError(AuditError):
    """The append-only audit chain is broken, reordered or otherwise not intact."""


class AuditReplayError(AuditError):
    """An audit event was replayed instead of appended exactly once."""


class DataClassificationError(WorkspaceStoreError):
    """A data class, trust domain or classification document is unknown or malformed.

    CW-004 fails closed here rather than defaulting: an unadmitted classification
    never resolves to a domain, and therefore never becomes Research Core admission.
    """


class BackflowError(WorkspaceStoreError):
    """Base class for every flow the CW-004 no-backflow guard refused."""


class ResearchBackflowError(BackflowError):
    """Workspace-side data was refused admission into Research Core (W/E/P -> R)."""


class ExportAdmissionError(BackflowError):
    """A quarantined export was refused automatic admission into Research Core (X -> R)."""


class TelemetryBackflowError(BackflowError):
    """Workspace telemetry, analytics or log state was refused as Research Core data."""


class SecretEgressError(BackflowError):
    """Secret-class material was refused: it is never a payload, log or prompt class."""


class WorkspaceAdmissionError(BackflowError):
    """A quarantined export was refused admission into the Workspace domain (X -> W)."""


class UndeclaredFlowError(BackflowError):
    """The requested trust-domain flow is not declared, so the guard refuses it."""


class UnavailableAuthorityError(BackflowError):
    """The flow is declared, but the governance authority it needs is not granted here."""


class ExplicitExportRequestError(BackflowError):
    """An export was refused because no explicit user export request was recorded."""


class ExportBoundaryError(BackflowError):
    """An export destination escaped, or could not be proven to stay inside, Domain X."""


class EncounterSessionError(WorkspaceStoreError):
    """Base class for every CW-005 synthetic encounter session lifecycle failure."""


class EncounterConsentError(EncounterSessionError):
    """Simulated capture was attempted without valid recording consent and policy."""


class EncounterStateError(EncounterSessionError):
    """A session lifecycle transition violated the deterministic state machine."""


class EncounterIdentityError(EncounterSessionError):
    """A session, chunk, or encounter identity was stale, foreign, or malformed."""


class EncounterChunkError(EncounterSessionError):
    """A synthetic audio chunk identity, order, or payload was refused."""


class EncounterReplayError(EncounterChunkError):
    """A chunk identity or sequence was replayed instead of appended exactly once."""


class EncounterRetentionError(EncounterSessionError):
    """Retention metadata was missing, malformed, or contradicted session policy."""


class EncounterDeleteError(EncounterSessionError):
    """A delete-cascade precondition failed or an orphaned session object remains."""


class EncounterConcurrentError(EncounterSessionError):
    """A concurrent lifecycle or chunk transition collided and was refused."""


class AsrError(WorkspaceStoreError):
    """Base class for every CW-006 offline ASR adapter failure."""


class AsrManifestError(AsrError):
    """A local ASR artifact manifest member is missing or drifts from the ADR identities."""


class AsrModelUnavailableError(AsrError):
    """The verified local model snapshot is absent, so transcription fails closed."""


class AsrRevisionError(AsrManifestError):
    """A model, runtime, or artifact revision is mutable, missing, or mismatched."""


class AsrInputError(AsrError):
    """An ASR input identity, payload, language, or binding was refused."""


class AsrTimestampError(AsrInputError):
    """A transcript timestamp is malformed, impossible, or out of order."""


class AsrLanguageError(AsrInputError):
    """A requested or detected language tag is not admitted here."""


class AsrBackendError(AsrError):
    """A transcription backend returned malformed output or broke the local-only contract."""


class AsrConflictError(AsrError):
    """A transcript identity was replayed instead of stored exactly once."""


class DraftError(WorkspaceStoreError):
    pass


class DraftInputError(DraftError):
    pass


class DraftRevisionError(DraftInputError):
    pass


class DraftTemplateError(DraftError):
    pass


class DraftSupportError(DraftError):
    pass


class DraftBackendError(DraftError):
    pass


class DraftConflictError(DraftError):
    pass


class ReviewError(WorkspaceStoreError):
    """Base class for every CW-008 human review and finalization failure."""


class ReviewInputError(ReviewError):
    """A review identity, actor, timestamp, or document member was refused."""


class ReviewRevisionError(ReviewInputError):
    """A review revision identity, lineage, or parent precondition was refused."""


class ReviewTransitionError(ReviewError):
    """A review state transition violated the deterministic state machine."""


class ReviewSupportError(ReviewError):
    """A span support claim inside a review revision failed mechanical checks."""


class ReviewSuggestionError(ReviewError):
    """An order/code/task suggestion identity, decision, or mutation was refused."""


class ReviewConflictError(ReviewError):
    """A review revision identity already exists and cannot be overwritten."""


class CorpusError(WorkspaceStoreError):
    """Base class for every CW-009 evidence corpus and retrieval failure."""


class CorpusInputError(CorpusError):
    """A corpus identity, source field, actor, or timestamp was refused."""


class CorpusRevisionError(CorpusInputError):
    """A corpus source revision identity or lineage precondition was refused."""


class CorpusConflictError(CorpusError):
    """A corpus source identity already exists and cannot be overwritten."""


class SnapshotError(WorkspaceStoreError):
    """Base class for every CW-009 retrieval snapshot failure."""


class SnapshotInputError(SnapshotError):
    """A snapshot identity, manifest member, or parameter was refused."""


class SnapshotConflictError(SnapshotError):
    """A snapshot identity already exists and cannot be overwritten."""


class RetrievalError(WorkspaceStoreError):
    """Base class for every CW-009 query execution and replay failure."""


class RetrievalInputError(RetrievalError):
    """A query identity, parameter, or document member was refused."""


class RetrievalReplayError(RetrievalError):
    """A deterministic replay precondition failed or a replay diverged."""


class RetrievalConflictError(RetrievalError):
    """A query or result identity already exists and cannot be overwritten."""


class ClaimError(WorkspaceStoreError):
    """Base class for every CW-010 claim-set decomposition failure."""


class ClaimInputError(ClaimError):
    """A claim-set identity, answer field, claim field, or citation was refused."""


class ClaimRevisionError(ClaimInputError):
    """A claim-set revision identity or lineage precondition was refused."""


class ClaimConflictError(ClaimError):
    """A claim-set identity already exists and cannot be overwritten."""


class LinkError(WorkspaceStoreError):
    """Base class for every CW-010 claim-source link failure."""


class LinkInputError(LinkError):
    """A link identity, binding, stance, range, actor, or timestamp was refused."""


class LinkRevisionError(LinkInputError):
    """A linked source, snapshot, query, or result revision precondition was refused."""


class LinkConflictError(LinkError):
    """A claim-source link identity already exists and cannot be overwritten."""


class StrengthError(WorkspaceStoreError):
    """Base class for every CW-010 evidence-strength assessment failure."""


class StrengthInputError(StrengthError):
    """An assessment identity, method, date, limit, reason, or parameter was refused."""


class StrengthVerdictError(StrengthError):
    """A verdict contradicted its linked evidence stances or freshness state."""


class StrengthReplayError(StrengthError):
    """A stored assessment no longer verifies against its linked evidence."""


class StrengthConflictError(StrengthError):
    """An assessment identity already exists and cannot be overwritten."""
