# ADR-0039 — Local protected storage and key management for the Clinical Workspace

- **Status:** Accepted by Founder under R6 — ratified 2026-09-21 with Amendment A1
- **Date:** 2026-09-21 (proposed and ratified the same day)
- **Ratified:** 2026-09-21 by the Founder (Abdulaziz M. Alshehri) under R6, with amendment A1 —
  see the [Founder ratification and amendment record](../../specs/medscale-clinical-workspace-v1/adr-0039-founder-ratification.md)
- **Deciders:** Founder
- **Supersedes:** none
- **Superseded by:** none
- **Decision history:** Proposed 2026-09-21 (PR #466); ratified and amended 2026-09-21 in
  response to the Founder decision recorded under Issue #467. Superseded proposal text is
  annotated in place rather than deleted.
- **Related:** ADR-0038, [data security and threat model](../../specs/medscale-clinical-workspace-v1/data_security.md), [migration, compatibility and recovery contract](../../specs/medscale-clinical-workspace-v1/migration_recovery.md), [task ledger](../../specs/medscale-clinical-workspace-v1/tasks.md) CW-002, [ratification record](../../specs/medscale-clinical-workspace-v1/adr-0039-founder-ratification.md), rules R2/R3/R6

## Context

CW-002 requires protected local storage using synthetic sensitive fixtures. The CW-000 data security contract states explicitly that "exact cryptographic libraries and database choices require a separate implementation ADR/security review", and it already fixes the acceptance surface: database encryption at rest, authenticated encryption for sensitive blobs, key material stored separately from encrypted payloads, a per-workspace data-encryption key or equivalent compartment, a recorded key version per encrypted object, crash-safe rotation, revocation that cannot silently continue writes, and no plaintext fallback after an encryption failure.

The migration contract adds migration classes M0–M5, a migration manifest, preflight, crash recovery, validation, rollback, and a downgrade policy. R2 keeps development synthetic-only. R3 requires permissive licensing for anything shipped. R6 requires this decision to be recorded as an ADR and approved before implementation, because a storage and key-management choice is expensive to reverse once real workspace state exists.

CW-001 deliberately left the Workspace package at zero dependencies behind a fail-closed boundary guard whose standard-library allowlist excludes `sqlite3` and whose prohibited-import list excludes cryptography providers. Introducing storage and key management is therefore a governed capability expansion of that guard, not a routine dependency addition.

## Decision

1. **Storage engine — standard-library SQLite.** Store workspace state in a single-file SQLite database through the Python standard library `sqlite3` module, in WAL mode, writing through explicit transactions. No third-party database engine is introduced.
2. **Payload protection — envelope encryption with an AEAD.** Encrypt each sensitive serialized payload before insert with AES-256-GCM. Bind workspace id, object id, object type, key version and encryption-format version as associated data, so a ciphertext cannot be relocated to another object or another workspace undetected. **Amended by A1.4:** the immutable object/revision identity is bound as associated data as well; **A1.3** fixes a 96-bit cryptographically random per-operation nonce stored in the envelope; **A1.5** forbids claiming whole-store rollback protection.
3. **Key separation and derivation.** Keep the root secret outside the database, in the platform secret store where one exists (Windows DPAPI/Credential Manager, macOS Keychain, Linux Secret Service). Record the key version with every encrypted object and refuse to write with a retired or unknown key version. **Amended by A1.1:** derive a per-workspace data-encryption key from the high-entropy root secret, the workspace id and an explicit per-workspace random salt using **HKDF-SHA-256**, not `hashlib.scrypt`. **A1.2** reserves `scrypt` for a future password/passphrase-derived root-key path that CW-002 does not implement, and **A1.6** fixes the key-rotation state machine.
4. **No plaintext fallback.** If the platform secret store is unavailable, the application fails closed rather than persisting the root secret in plain text or a weakly protected file. Automated tests use an explicit in-memory key provider that is never written to disk; the test provider cannot be selected by configuration in a production path. **Extended by A1.7:** the platform key provider declares explicit capabilities, no weak cross-platform adapter exists to claim support, and unsupported or unavailable protected secret storage fails closed.
5. **One new dependency, for the cipher primitive only.** Add `cryptography` (dual-licensed Apache-2.0 / BSD-3-Clause, permissive, prebuilt wheels, no mandatory cloud runtime) for AEAD primitives. Key derivation, envelope encoding, key-version handling and migration remain in our own reviewed code. The standard library exposes no AEAD cipher, so a vetted dependency is the safe choice rather than a hand-rolled construction. **A1.8** reconciles the platform key-provider path with this policy: no further runtime dependency is introduced, and if one were genuinely required the implementation path stops and a governance amendment is recorded instead.
6. **Migration discipline.** Treat application version, workspace schema version, policy version and encryption-format version as first-class recorded state. Apply forward-only migrations in the M1–M3 classes from the CW-000 contract, emit a migration manifest for every state-changing migration, use the checkpoint table for crash recovery, and refuse a downgrade the running application cannot read. **A1.6** fixes the rotation state machine that M3 migrations must implement, and **A1.9** adds migration artifacts to the required leakage-test surface.
7. **Governed boundary-guard change.** Extend the CW-001 guard for CW-002 to admit `sqlite3` and the cipher provider while keeping the network, process, dynamic-import and persistent-mutation prohibitions, and add a rule that workspace code may only touch the single workspace store path resolved by one dedicated module.
8. **Synthetic-only development.** Encrypted fixtures remain synthetic. This ADR creates no PHI, real-patient-data, clinical-production or EHR-write authority.
9. **Durability and integrity pragmas are part of the decision.** Run the store with `journal_mode=WAL`, `synchronous=FULL` on the write path, `foreign_keys=ON`, `secure_delete=ON` and an explicit busy timeout. The crash-safety claim in this ADR holds only under those settings, so CW-002 tests must assert the effective pragma values instead of trusting defaults. **A1.11** bounds this: `secure_delete=ON` is defense in depth, never proof of cryptographic erasure.
10. **Key-material lifetime.** Never persist key material in the store, never include it in the store file, logs, diagnostics or crash reporting, and keep the root secret and derived data-encryption keys in process memory only for the shortest window needed to decrypt or encrypt. CW-002 tests must assert that key bytes appear neither in the store file nor in captured log output. **A1.9** widens the tested surface beyond the main database file to `-wal`, `-shm`, SQLite/temp files, logs, diagnostics, exceptions, migration artifacts and (once relevant) snapshots/backups; **A1.10** requires an explicit, tested statement of which metadata stays plaintext.

## Amendment A1 (Founder, 2026-09-21)

Amendment A1 was supplied with the Founder's ratification under R6 and is incorporated here
before any CW-002 implementation exists. Its normative text is recorded, with identifiers
`A1.1`–`A1.12`, in the [Founder ratification and amendment record](../../specs/medscale-clinical-workspace-v1/adr-0039-founder-ratification.md). In summary:

| Item | Change to this ADR |
|---|---|
| A1.1 | workspace/version keys are derived with HKDF-SHA-256 from a high-entropy root secret, not `scrypt` |
| A1.2 | `scrypt` is reserved for a future password/passphrase-derived root-key path; CW-002 has no such path |
| A1.3 | explicit AES-256-GCM nonce contract: 96-bit, cryptographically random per operation, never reused with the same key, stored in the envelope, with misuse/reuse adversarial tests |
| A1.4 | associated data additionally binds the immutable object/revision identity alongside workspace id, object id, object type, key version and encryption-format version |
| A1.5 | no overclaim that AES-GCM defeats valid historical whole-store rollback; the unimplemented protection is documented as a limitation |
| A1.6 | explicit `ACTIVE -> ROTATING -> RETIRING -> RETIRED` key state machine with no silent writes from retired keys, deterministic resume, and no mixed untracked key state |
| A1.7 | platform key-provider abstraction with explicitly declared capabilities; no weak cross-platform adapters; unavailable protected secret storage fails closed |
| A1.8 | the key-provider path is reconciled with the dependency policy; no silent dependency, and a genuine additional need stops the path for a governance amendment |
| A1.9 | plaintext/key leakage tests cover the database file, `-wal`, `-shm`, SQLite/temp files, logs, diagnostics, exceptions, migration artifacts and later snapshot/backup paths |
| A1.10 | explicit, tested statement of which metadata remains plaintext and which data must be encrypted; no implied whole-file opacity |
| A1.11 | `secure_delete=ON` is defense in depth only, never proof of cryptographic erasure |
| A1.12 | every pre-existing ADR-0039 principle is preserved unless A1 explicitly changes it |

This amendment changes no property of the decision's scope: it stays synthetic-only, local-first,
offline-capable and dependency-bounded by `cryptography` alone.

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
- one new dependency enters the Workspace package, which CW-001 deliberately kept at zero;
- (A1.5) AES-256-GCM authenticates objects but does not by itself defeat a valid historical whole-store rollback performed with a still-valid key; CW-002 implements no rollback detector and must state that limitation rather than imply protection it does not have;
- (A1.9/A1.10) SQLite structural and explicitly declared metadata remain visible in a copied store, so the leak-tested surface is broader than the encrypted payloads and partial opacity must be stated precisely.

## Alternatives considered

- **SQLCipher or another encrypted-SQLite distribution** — rejected: a native/embedded library increases supply-chain and packaging risk, is harder to validate on Windows, and hides the envelope design from review instead of exposing it as reviewable application code.
- **Pure standard-library cryptography** — rejected: the standard library exposes no AEAD cipher; hand-rolled authenticated encryption is not acceptable for a clinical trust domain.
- **Third-party database engine (DuckDB, PostgreSQL, …)** — rejected: DuckDB adds a heavyweight dependency without solving key management; PostgreSQL adds a server and a network surface that contradicts the local-first boundary.
- **Operating-system keyring only, with no envelope design** — rejected: availability and semantics differ per platform, and a keyring alone cannot express key versions, rotation or per-workspace compartments.
- **Whole-disk or platform encryption only** — rejected: the CW-000 contract requires that a copied database file be unreadable without key material.

## Compliance

CW-002 acceptance must demonstrate: a copied store is unreadable without key material; key and payload locations are separated; transactions are crash-safe; workspaces stay isolated; key rotation completes without silent data loss; there is no plaintext fallback; and dependency/source licence review passes. Enforcement is by the extended boundary guard plus focused and adversarial tests, with the independent security lane at CW-019 and the connector/storage review requirements already defined in the CW-000 threat model.

This ADR was **Proposed** on 2026-09-21 (PR #466) and is now **Accepted by the Founder under R6
as amended by A1**. CW-002 was activated for implementation under Issue #467 after ratification.
Activation confers no acceptance: every CW-002 acceptance item above, and every amended security
clarification in A1, must still be demonstrated by evidence bound to the exact qualified head and
to fresh canonical `main`.
