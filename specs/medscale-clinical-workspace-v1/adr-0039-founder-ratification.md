# ADR-0039 — Founder Ratification and Amendment A1

```text
Status:
FOUNDER RATIFICATION RECORDED WITH AMENDMENT A1

ADR-0039:
ACCEPTED BY FOUNDER UNDER R6 — AS AMENDED BY A1

CW-002:
ACTIVATED FOR IMPLEMENTATION UNDER ISSUE #467

IMPLEMENTATION OF CW-002:
AUTHORIZED ONLY WITHIN THE AMENDED ADR-0039 CONTRACT

PHI INGESTION / REAL PATIENT IMPORT / CLINICAL PRODUCTION USE /
EHR WRITE / AUTONOMOUS ACTION / REMOTE MODEL EGRESS /
TRAINING ON WORKSPACE DATA / RESEARCH ADMISSION FROM WORKSPACE:
NOT AUTHORIZED
```

- **Founder / Product Owner / Roadmap Owner:** Abdulaziz M. Alshehri
- **Decision date:** 2026-09-21
- **Authority cited:** Rule R6 ([rules R1–R7](../../docs/governance/rules.md)), [roles and authority](../../docs/governance/roles_and_authority.md)
- **Governing issue:** [#467](https://github.com/TheHalfMoon/MESC/issues/467) — CW-002 activation gate
- **Proposal merged as:** PR #466 (`docs/adr-0039-local-protected-storage`) at `2026-09-21T16:26:57Z`
- **Canonical `main` at the moment of the decision:** `75a3cd1aa355fa8201ee41202807eaf5fafa7fb1`
- **Subject ADR:** [ADR-0039 — Local protected storage and key management for the Clinical Workspace](../../docs/adr/0039-local-protected-storage-and-key-management.md)
- **Related contracts:** [data security and threat model](data_security.md), [migration, compatibility and recovery](migration_recovery.md), [task ledger](tasks.md) CW-002

This record is the canonical ratification artifact for ADR-0039. On any conflict between
this record and the proposal text of ADR-0039 as it stood before ratification, this record
controls and the ADR's amendment section restates the change.

---

## 1. Live state entering the decision

Verified directly against the live repository and GitHub state, not from memory:

```text
CW-000                                = CLOSED_CANONICAL
CW-001                                = CLOSED_CANONICAL
canonical main                        = 75a3cd1aa355fa8201ee41202807eaf5fafa7fb1
ADR-0038                              = Accepted by Founder under R6, canonically effective
ADR-0039 status before this record    = Proposed — awaiting Founder ratification under R6
CW-002                                = ELIGIBLE_NOT_ACTIVATED
CW-003 through CW-021                 = BLOCKED_DEPENDENCY
Issue #467                            = OPEN (activation gate)
```

CW-002's contract requires its own implementation ADR ratified under R6 **and** separate
activation before any implementation begins. The proposal (`ADR-0039`, merged as `Proposed`)
satisfied the first half; it did not by itself confer implementation authority.

## 2. Ratification decision

The Founder amends and ratifies ADR-0039 under R6 as the implementation contract for CW-002,
subject to all existing MESC governance, evidence, security, licensing, synthetic-only and
no-PHI constraints.

```text
ADR_0039 = ACCEPTED BY FOUNDER (2026-09-21, R6), AS AMENDED BY A1
ADR_0039_REJECTION = NOT EXERCISED
ADR_0039_AS_PROPOSED = NOT ACCEPTED UNCHANGED — AMENDMENT A1 ALSO APPLIES
```

Amendment A1 was supplied with the ratification and is incorporated before any CW-002
implementation exists. Because ADR-0039 had never been implemented and no state, artifact or
contract was ever produced under the superseded derivation choice, the amendment is part of
first ratification and requires no second ADR.

Decision history is preserved, not rewritten: the superseded proposal text remains visible in
ADR-0039's decision items as an explicit "amended by A1.n" annotation, and this record states
exactly what replaced it.

## 3. Amendment A1 — normative security clarifications

The identifiers `A1.1` through `A1.12` are fixed by this record and map one-to-one onto the
amendment items supplied with the Founder's ratification. No identifier may be renumbered,
merged, split or extended.

### A1.1 — HKDF-SHA-256 for workspace and version key derivation

Workspace and version encryption keys are derived from a **high-entropy root secret** using
**HKDF-SHA-256**, with the workspace identity and an explicit per-workspace random salt bound
into the derivation inputs. `hashlib.scrypt` is **not** the workspace-key derivation function.

### A1.2 — `scrypt` reserved for a future password-derived root-key path

`scrypt` is reserved for a future password/passphrase-derived root-key path, and only if such a
path is explicitly introduced under its own governance decision. CW-002 implements no
password-derived key path and no interactive passphrase flow.

### A1.3 — Explicit AES-256-GCM nonce contract

```text
nonce size           96 bits (12 bytes)
generation           cryptographically random for every encryption operation
reuse                never reuse a nonce with the same key
storage              the nonce is stored as part of the encryption envelope
tests                misuse/reuse adversarial tests are required
```

A deterministic or counter-derived nonce is not permitted in CW-002.

### A1.4 — AEAD associated-data binding

Associated data is bound at minimum to:

```text
workspace id
object id
object type
immutable object/revision identity
key version
encryption-format version
```

Relocating a ciphertext to another workspace, object, type, revision, key version or format
version must fail authentication rather than decrypt.

### A1.5 — No overclaim of whole-store rollback protection

AES-256-GCM authenticates objects; it does not by itself defeat a valid historical whole-store
rollback performed with a still-valid key. Because CW-002 implements no rollback detector, the
limitation is documented explicitly and must never be presented as protection that exists.

### A1.6 — Explicit key-rotation state machine

```text
ACTIVE -> ROTATING -> RETIRING -> RETIRED
```

Required semantics:

```text
new writes                       use the new active key
prior key during verified
  migration                      may remain decrypt-only
retired keys                     cannot silently resume writes
interrupted rotation             resumes deterministically
mixed untracked key state        is not permitted
```

### A1.7 — Platform key-provider abstraction with explicit capabilities

The platform key provider is an abstraction that declares its explicit supported capabilities.
Weak cross-platform adapters must not be created merely to claim platform support. When
protected secret storage is unsupported or unavailable, the implementation fails closed.

### A1.8 — Dependency-policy reconciliation

The platform key-provider path is reconciled with ADR-0039's dependency policy before
implementation. No additional runtime dependency may be introduced silently. If another
dependency is genuinely required, that implementation path stops and the required
ADR/governance amendment is recorded instead of violating the accepted contract.

```text
CW-002 runtime dependency surface = cryptography (AEAD primitive) only
password-hashing dependency       = none
keyring/secret-service dependency = none
```

The Windows-protected-storage and test providers are implemented with the Python standard
library plus `cryptography`; ADR-0039 decision 5 is therefore **not** reopened by A1.

### A1.9 — Plaintext and key-leakage test surface

Leakage tests must cover more than the main SQLite database file. At minimum:

```text
SQLite database file
-wal
-shm (where applicable)
SQLite/temp files (where applicable)
logs
captured diagnostics
exceptions
migration artifacts
snapshots/backups once those paths become relevant
```

### A1.10 — Explicit plaintext-metadata scope

Which metadata may remain plaintext and which data must be encrypted is defined explicitly and
tested. The implementation must not imply whole-file opacity while SQLite structural or
allowed metadata remains visible.

### A1.11 — `secure_delete=ON` is defense in depth only

`secure_delete=ON` is retained as defense in depth. It is **not** proof of cryptographic
erasure. Deletion and cryptographic-erasure semantics remain governed by the explicit
deletion/key-lifecycle contracts, and CW-002 must not claim erasure on the strength of that
pragma.

### A1.12 — Preserved ADR-0039 principles

All existing ADR-0039 principles are preserved unless A1 explicitly changes them:

```text
standard-library SQLite              key separation
WAL                                  no plaintext fallback
explicit transactions                synthetic-only development
synchronous=FULL on the write path   forward-governed migrations
foreign_keys=ON                      boundary-guard widening only as explicitly authorized
secure_delete=ON as defense in depth cryptography as the AEAD dependency
explicit busy timeout                local-first / offline / no paid service requirement
AES-256-GCM
```

## 4. Effect on ADR-0039 decision items

| ADR-0039 item | Effect of ratification and A1 |
|---|---|
| 1 — storage engine is standard-library SQLite | unchanged |
| 2 — AES-256-GCM envelope encryption with AAD binding | **extended** by A1.3, A1.4, A1.5 |
| 3 — key separation and derivation | **amended** by A1.1, A1.2 |
| 4 — no plaintext fallback | unchanged; **extended** by A1.7 (fail closed when protected secret storage is unavailable) |
| 5 — one new dependency (`cryptography`) for the cipher primitive only | unchanged; **reconciled** by A1.8 |
| 6 — migration discipline | unchanged; **extended** by A1.6 (rotation state machine) and A1.9 (migration artifacts in the leakage surface) |
| 7 — governed boundary-guard change | unchanged; the single-store-path rule is implemented mechanically as part of CW-002 |
| 8 — synthetic-only development | unchanged |
| 9 — durability and integrity pragmas | unchanged; **bounded** by A1.11 |
| 10 — key-material lifetime | unchanged; **extended** by A1.9 (broader leakage surface) |
| — plaintext/encrypted metadata scope | **added** by A1.10 |
| — rollback limitation | **added** by A1.5 |

## 5. CW-002 activation

CW-002 — *Local protected storage and key abstraction* — is activated as the one active
implementation unit under R4, governed by Issue #467 and by ADR-0039 as amended.

Required execution order after activation:

```text
ACTIVATE -> PLAN -> IMPLEMENT -> TEST -> ADVERSARIAL TEST -> REVIEW
-> EXACT-HEAD QUALIFY -> PROTECTED MERGE -> FRESH-MAIN QUALIFY -> CANONICAL CLOSEOUT
```

Activation does not by itself satisfy any acceptance criterion. Every CW-002 acceptance item,
including the amended security clarifications above, must still be demonstrated by evidence
bound to the exact qualified head and to fresh canonical `main`.

## 6. Security expectations carried into CW-002

CW-002 acceptance must independently demonstrate at least:

```text
copied protected storage cannot reveal sensitive payload plaintext without valid key material
workspace isolation fails closed
object relocation / ciphertext swapping fails authentication (AAD binding)
revision swapping fails
wrong workspace / object id / object type / key version fails
nonce misuse and reuse protections are tested (A1.3)
no plaintext fallback exists
key material is absent from persistence, logs, diagnostics and exceptions (A1.9)
retired keys cannot perform new writes (A1.6)
interrupted key rotation is resumable and deterministic (A1.6)
key/provider unavailability fails before unsafe persistence (A1.7)
schema / encryption / application / policy versions are recorded correctly
migrations obey the accepted migration contract
the boundary guard remains fail-closed outside explicitly admitted capabilities
no network / process / dynamic-import / Research-Core backflow capability is introduced
synthetic fixtures remain synthetic
no PHI authority is inferred
```

Hostile and benign cases are tested separately and independently.

## 7. Non-grants

This ratification, and the CW-002 activation it enables, authorize nothing beyond the amended
ADR-0039 contract. The following remain in force unchanged:

```text
PHI_INGESTION = NOT_AUTHORIZED
REAL_PATIENT_IMPORT = NOT_AUTHORIZED
CLINICAL_PRODUCTION_USE = NOT_AUTHORIZED
EHR_WRITE = NOT_AUTHORIZED
AUTONOMOUS_ACTION = NOT_AUTHORIZED
REMOTE_MODEL_EGRESS = NOT_AUTHORIZED
TRAINING_ON_WORKSPACE_DATA = NOT_AUTHORIZED
RESEARCH_ADMISSION_FROM_WORKSPACE = NOT_AUTHORIZED
MRL_CONTRACT_MUTATION = NOT_AUTHORIZED
NEW_MRL_STAGE4_ATTEMPT = NOT_AUTHORIZED
PAID_COMPUTE = NOT_AUTHORIZED
```

MRL-0809 remains separately governed (Issues #429/#450) and MRL-0899 remains dependent on it.
No MRL Stage-4 authority is created, implied or consumed by Clinical Workspace work.

Issue #464 remains a separate, independently governed record of CW-001 follow-up findings and
is not folded into CW-002.

## 8. What this record does not do

This record does not implement CW-002, does not add a dependency, does not widen the CW-001
boundary guard, does not merge any implementation, and does not close CW-002. It records a
decision and an activation; the implementation, its adversarial evidence, its independent
review, its exact-head qualification, its protected merge, its fresh-main qualification and
its canonical closeout are all still owed.

```text
ACTIVATION IS NOT IMPLEMENTATION.
ELIGIBILITY IS NEVER AUTHORITY.
QUALIFICATION IS NEVER AUTHORITY.
```
