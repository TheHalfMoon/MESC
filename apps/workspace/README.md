# MedScale Clinical Workspace

CW-001 established a Python-only application boundary for the future local Clinical Workspace.
CW-002 adds governed local protected storage under [ADR-0039](../../docs/adr/0039-local-protected-storage-and-key-management.md),
ratified by the Founder under R6 with amendment A1
([ratification record](../../specs/medscale-clinical-workspace-v1/adr-0039-founder-ratification.md)).
CW-003 adds the provenance spine and the append-only audit spine on top of that store
(activated under Issue #471).
CW-004 adds the canonical typed data classification and the mechanical no-backflow guard that
enforces the Research Core / Workspace / Domain X separation (activated under Issue #474).

Current scope:

- synthetic patient and encounter fixtures only;
- deterministic local object identity;
- one encrypted local store per workspace: standard-library `sqlite3`, WAL,
  `synchronous=FULL` on the write path, `foreign_keys=ON`, `secure_delete=ON` and an
  explicit busy timeout;
- AES-256-GCM envelope encryption with a 96-bit cryptographically random per-operation
  nonce and associated data binding workspace id, object id, object type, immutable
  revision, key version and encryption-format version;
- HKDF-SHA-256 per-workspace/per-key-version key derivation from a high-entropy root
  secret that is never persisted;
- an `ACTIVE -> ROTATING -> RETIRING -> RETIRED` key-version state machine with
  deterministic resume after interruption and no writes under a retired key;
- a provenance record per object revision: producer identity, explicit source references,
  review state, recorded content digest, format and policy versions, and a rule that
  generated content must reference at least one source;
- an append-only audit spine: one immutable object per event, digest-derived event identity,
  chain-position object identity, predecessor-digest chaining, replay and occupied-position
  collisions instead of append, a validated caller-supplied ISO-8601 occurrence time, and one
  transaction that deletes content while recording the deletion;
- one canonical typed classification vocabulary: five trust domains, the admitted data
  classes, and one table binding every class to exactly one domain, so a domain is always
  derived and never asserted by the caller;
- a mechanical no-backflow guard: Domain R is refused as a destination for every source, a
  quarantined export is refused automatic Research admission and refused re-admission as
  Workspace state, Workspace telemetry/analytics/logs are refused as Research Core data,
  secret-class material is refused every flow, declared-but-unauthorised flows fail closed,
  and an undeclared edge is refused by default;
- a Domain X export containment proof: an export target must be a strict path below a declared
  quarantine root and outside every declared Research Core root, and de-identification is
  recorded as a transformation of an export, never as an admission;
- no plaintext fallback anywhere in the path;
- no microphone or ambient capture;
- no EHR/FHIR connector;
- no model execution;
- no connector credentials and no network requirement.

Exactly one third-party runtime dependency is admitted, for the AEAD primitive only:
`cryptography==50.0.1` (`Apache-2.0 OR BSD-3-Clause`). The Research Core package remains free
of runtime dependencies, and `pyproject.toml`/`uv.lock` stay byte-identical to the frozen
MRL-0809 static prerequisite digests: CI installs the Workspace dependency into the shard
environment instead. See
[cw-002-dependency-license-review.md](../../specs/medscale-clinical-workspace-v1/cw-002-dependency-license-review.md).

The Research Core remains independently packaged from `src/medscale`. The Workspace is a
separate package under `apps/workspace` and imports no Research Core modules.
`scripts/check_clinical_workspace_boundary.py` enforces that fail-closed boundary, including
the CW-002 rules that `sqlite3` is imported only by `storage.py`, that `cryptography` is
imported only by `aead.py`, that the store path is resolved by exactly one module, and that
the reserved password-derived KDF is absent. The guard also carries the CW-003 rule that only
`storage.py` may touch the private store connection, and the CW-004 rules that the typed
classification vocabulary is defined once in `data_class.py`, that the declared flow table and
every guard entry point are defined once in `nobackflow.py`, that a classification literal or a
`TrustDomain`/`DataClass` member may not be named anywhere else, and that both declared tables
must be validated at import time so an incomplete table fails closed.

Recorded limitations, not hidden:

- no platform protected-secret-storage provider is implemented in CW-002 (a Windows DPAPI
  binding would need `ctypes`, which the boundary guard prohibits, and a weaker
  cross-platform substitute is exactly what amendment A1.7 forbids). The production
  resolver therefore returns an explicitly unavailable provider and the store fails closed
  rather than writing with a weakly protected key.
- AES-256-GCM does not defeat a valid historical whole-store rollback performed with a
  still-valid key, and CW-002 implements no rollback detector (A1.5).
- SQLite structural data and the metadata listed by
  `WorkspaceStore.plaintext_metadata_scope()` remain visible in a copied store (A1.10).
- `secure_delete=ON` is defense in depth only and is not proof of cryptographic erasure
  (A1.11).
- CW-002 implements store initialization only; the remaining migration classes and their
  manifest/preflight/rollback machinery are CW-018.
- the audit spine is append-only at the API, identity and chain level; there is no
  database-level write-once trigger, and a removed tail event verifies internally unless a
  head digest is retained outside the store. Stricter storage-level enforcement belongs to
  CW-018, and the independent security lane at CW-019 owns attacking it.
- the CW-004 export containment check is pure path algebra over caller-supplied absolute paths,
  because this package holds no filesystem capability (`os`, `pathlib` and `open` are forbidden
  by the boundary guard). It therefore does not resolve symlinks, junctions or reparse points:
  a link placed inside an admitted quarantine root is outside this unit's detection scope until
  the first later unit that obtains a filesystem capability, and it remains in scope for CW-019.
- the CW-004 guard decides and records; it performs no I/O, so it neither stages an export on
  disk nor asserts that a chosen destination exists.

CW-002, CW-003 and CW-004 do not authorize PHI, real-patient import, clinical production use,
EHR writes, external model execution, training on Workspace data, research admission,
publication, paid compute, or MRL changes.
