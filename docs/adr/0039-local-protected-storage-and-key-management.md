# ADR-0039 — Local protected storage and key management for the Clinical Workspace

- **Status:** Proposed — awaiting Founder ratification under R6
- **Date:** 2026-09-21
- **Deciders:** Founder
- **Supersedes:** none
- **Superseded by:** none
- **Related:** ADR-0038, [data security and threat model](../../specs/medscale-clinical-workspace-v1/data_security.md), [migration, compatibility and recovery contract](../../specs/medscale-clinical-workspace-v1/migration_recovery.md), [task ledger](../../specs/medscale-clinical-workspace-v1/tasks.md) CW-002, rules R2/R3/R6

## Context

CW-002 requires protected local storage using synthetic sensitive fixtures. The CW-000 data security contract states explicitly that "exact cryptographic libraries and database choices require a separate implementation ADR/security review", and it already fixes the acceptance surface: database encryption at rest, authenticated encryption for sensitive blobs, key material stored separately from encrypted payloads, a per-workspace data-encryption key or equivalent compartment, a recorded key version per encrypted object, crash-safe rotation, revocation that cannot silently continue writes, and no plaintext fallback after an encryption failure.

The migration contract adds migration classes M0–M5, a migration manifest, preflight, crash recovery, validation, rollback, and a downgrade policy. R2 keeps development synthetic-only. R3 requires permissive licensing for anything shipped. R6 requires this decision to be recorded as an ADR and approved before implementation, because a storage and key-management choice is expensive to reverse once real workspace state exists.

CW-001 deliberately left the Workspace package at zero dependencies behind a fail-closed boundary guard whose standard-library allowlist excludes `sqlite3` and whose prohibited-import list excludes cryptography providers. Introducing storage and key management is therefore a governed capability expansion of that guard, not a routine dependency addition.

## Decision

1. **Storage engine — standard-library SQLite.** Store workspace state in a single-file SQLite database through the Python standard library `sqlite3` module, in WAL mode, writing through explicit transactions. No third-party database engine is introduced.
2. **Payload protection — envelope encryption with an AEAD.** Encrypt each sensitive serialized payload before insert with AES-256-GCM. Bind workspace id, object id, object type, key version and encryption-format version as associated data, so a ciphertext cannot be relocated to another object or another workspace undetected.
3. **Key separation and derivation.** Keep the root secret outside the database, in the platform secret store where one exists (Windows DPAPI/Credential Manager, macOS Keychain, Linux Secret Service). Derive a per-workspace data-encryption key from the root secret, the workspace id and a per-workspace random salt using a memory-hard KDF (`hashlib.scrypt`, standard library). Record the key version with every encrypted object and refuse to write with a retired or unknown key version.
4. **No plaintext fallback.** If the platform secret store is unavailable, the application fails closed rather than persisting the root secret in plain text or a weakly protected file. Automated tests use an explicit in-memory key provider that is never written to disk; the test provider cannot be selected by configuration in a production path.
5. **One new dependency, for the cipher primitive only.** Add `cryptography` (dual-licensed Apache-2.0 / BSD-3-Clause, permissive, prebuilt wheels, no mandatory cloud runtime) for AEAD primitives. Key derivation, envelope encoding, key-version handling and migration remain in our own reviewed code. The standard library exposes no AEAD cipher, so a vetted dependency is the safe choice rather than a hand-rolled construction.
6. **Migration discipline.** Treat application version, workspace schema version, policy version and encryption-format version as first-class recorded state. Apply forward-only migrations in the M1–M3 classes from the CW-000 contract, emit a migration manifest for every state-changing migration, use the checkpoint table for crash recovery, and refuse a downgrade the running application cannot read.
7. **Governed boundary-guard change.** Extend the CW-001 guard for CW-002 to admit `sqlite3` and the cipher provider while keeping the network, process, dynamic-import and persistent-mutation prohibitions, and add a rule that workspace code may only touch the single workspace store path resolved by one dedicated module.
8. **Synthetic-only development.** Encrypted fixtures remain synthetic. This ADR creates no PHI, real-patient-data, clinical-production or EHR-write authority.
9. **Durability and integrity pragmas are part of the decision.** Run the store with `journal_mode=WAL`, `synchronous=FULL` on the write path, `foreign_keys=ON`, `secure_delete=ON` and an explicit busy timeout. The crash-safety claim in this ADR holds only under those settings, so CW-002 tests must assert the effective pragma values instead of trusting defaults.
10. **Key-material lifetime.** Never persist key material in the store, never include it in the store file, logs, diagnostics or crash reporting, and keep the root secret and derived data-encryption keys in process memory only for the shortest window needed to decrypt or encrypt. CW-002 tests must assert that key bytes appear neither in the store file nor in captured log output.

## Consequences

**Positive**

- local-first, offline and zero-cost: no server, no network surface, no paid service;
- supply-chain growth is a single widely deployed, permissively licensed package;
- associated-data binding closes ciphertext relocation and swap attacks, which a naive per-row encryption design leaves open;
- per-workspace keys with recorded versions make rotation, revocation and "no silent write after retirement" directly testable;
- SQLite's transactional semantics support the crash-safety tests CW-002 already requires.

**Negative / costs**

- a single-writer store limits write concurrency; acceptable for a single-user local V1, but it constrains later multi-writer designs;
- envelope encryption is application-level code, so it must be reviewed adversarially rather than trusted as a library feature;
- the boundary guard's allowlist widens, which is a real capability expansion recorded here explicitly instead of being slipped in silently;
- root-secret loss means data loss; recovery semantics must be documented and exercised in CW-018, and key availability is already a preflight requirement in the migration contract;
- one new dependency enters the Workspace package, which CW-001 deliberately kept at zero.

## Alternatives considered

- **SQLCipher or another encrypted-SQLite distribution** — rejected: a native/embedded library increases supply-chain and packaging risk, is harder to validate on Windows, and hides the envelope design from review instead of exposing it as reviewable application code.
- **Pure standard-library cryptography** — rejected: the standard library exposes no AEAD cipher; hand-rolled authenticated encryption is not acceptable for a clinical trust domain.
- **Third-party database engine (DuckDB, PostgreSQL, …)** — rejected: DuckDB adds a heavyweight dependency without solving key management; PostgreSQL adds a server and a network surface that contradicts the local-first boundary.
- **Operating-system keyring only, with no envelope design** — rejected: availability and semantics differ per platform, and a keyring alone cannot express key versions, rotation or per-workspace compartments.
- **Whole-disk or platform encryption only** — rejected: the CW-000 contract requires that a copied database file be unreadable without key material.

## Compliance

CW-002 acceptance must demonstrate: a copied store is unreadable without key material; key and payload locations are separated; transactions are crash-safe; workspaces stay isolated; key rotation completes without silent data loss; there is no plaintext fallback; and dependency/source licence review passes. Enforcement is by the extended boundary guard plus focused and adversarial tests, with the independent security lane at CW-019 and the connector/storage review requirements already defined in the CW-000 threat model.

This ADR is **Proposed**. Under R6, CW-002 implementation must not begin until the Founder ratifies this decision, and CW-002 must then be separately activated under repository governance.
