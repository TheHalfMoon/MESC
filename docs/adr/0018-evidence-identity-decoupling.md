# ADR-0018 — Decouple Evidence Identity from Container Schema Version

- **Status:** Accepted (founder approved 2026-09-02)
- **Date:** 2026-07-10
- **Decision date:** 2026-09-02
- **Deciders:** Founder
- **Amends:** [ADR-0009](0009-evidence-model.md) (identity-field list)
- **Related:** [ADR-0017](0017-identifier-stability-contract.md) (identifier stability),
  [ADR-0020](0020-public-api-stability.md) (accepted public/data-contract compatibility),
  [ADR-0030](0030-dataset-versioning-and-training-artifact-contract.md) (proposed dataset
  design context only; not authority), [stress test F2](../architecture/reviews/2026-07-10-stress-test.md)

## Context

ADR-0009 includes `schema_version` among the fields hashed into `evidence_id`. The
intent was conservative: if the schema's *meaning* changes, identity should not carry
over silently. The stress test exposed the cost at scale: the first v1→v2 bump re-mints
the id of **every** evidence object simultaneously — at millions of objects, every
knowledge-graph edge, benchmark citation, and cross-corpus reference breaks in one
release. That is the ADR-0017 orphaning hazard, ecosystem-wide.

The window to change the canonical repository identity derivation is **now**: zero evidence
objects exist as committed repository data, so the canonical tree needs no evidence-object
data migration. `EvidenceObject`, identifier derivation, and persisted formats are
public/data contracts under accepted ADR-0020, so local artifacts created from an earlier
release must not be silently reminted when read. Dataset v1 shipped in v0.2.0 and its
persisted schema therefore remains unchanged here under ADR-0020's append-only data-contract
compatibility rule. ADR-0030 remains Proposed and is related design context only; this ADR
does not derive authority from it.

## Decision

1. **Remove `schema_version` from the `evidence_id` hash.** Identity = the claim's
   semantic content: claim text, study type, PICO slots, effect fields, source API +
   identifier. The container schema may evolve (add optional fields, restructure
   storage) without re-minting identities.
2. **Introduce `identity_version` (integer, starts at 1), hashed into the id**, bumped
   **only** when the *meaning* of identity fields changes (e.g., PICO slot semantics
   redefined) — never for additive container evolution. This preserves ADR-0009's
   conservative intent exactly where it matters, and only there.
3. `schema_version` remains on the object (container format marker, per the F1
   format-versioning convention) — it simply no longer participates in identity.
4. ADR-0017's contract extends unchanged: any future `identity_version` bump is a
   breaking change requiring an ADR + lineage-based migration.
5. **Current Dataset v1 and evidence format 1 remain unchanged on disk under accepted
   ADR-0020 data-contract compatibility.** The current writer supports only
   `identity_version == 1` and does not serialize an additional `identity_version` member
   into format-1 artifacts. A non-v1 identity version must fail closed at the persistence
   boundary until a separately governed container/dataset version admits and persists that
   identity version.
6. **Same semantic identity may not hide persisted-content disagreement.** If two objects
   share an `evidence_id` but serialize to different format-1 payloads (for example,
   different `schema_version`, verification state, timestamps, or other non-identity
   fields), both writing and loading fail closed rather than selecting an input by order.
   Exact duplicate payloads remain valid. This preserves order-independent deterministic
   bytes for both emitted and externally supplied stores.
7. **Recognized pre-ADR-0018 identifiers require explicit migration.** The ordinary reader
   detects the historical schema-coupled identifier formula and refuses to silently return
   a reminted id. `migrate_legacy_evidence_file(source, destination)` writes a distinct new
   artifact, never edits the source, and returns the exact old→new id mapping needed to
   update downstream references explicitly.
8. **Preserve the public constructor slot.** `schema_version` retains its historical
   positional argument position; `identity_version` is appended after it. The public API
   change is recorded in `CHANGELOG.md` as required by ADR-0020.

## Consequences

**Positive:** schema evolution (the *common* case: new optional fields) no longer changes
semantic evidence identity; identity discontinuity is reserved for genuine semantic
change (the *rare* case), made explicit by `identity_version`. Existing Dataset v1 and
format-1 artifact schemas are not silently mutated. Legacy local artifacts have an
explicit, auditable migration path, and same-id conflicts cannot make output depend on
input order during either writing or loading.

**Negative:** two version concepts must be understood. While Dataset v1 remains current,
non-default identity versions cannot be persisted; that is deliberate fail-closed behavior,
not an implicit schema upgrade. Previously created local evidence files whose stored ids
match the historical formula require an explicit migration step and downstream reference
remapping before normal loading.

## Alternatives considered

- **Keep as-is.** Rejected: punishes routine evolution with ecosystem-wide id churn;
  the stress test rates this the most expensive latent decision in the evidence layer.
- **No version in identity at all.** Rejected: silently carrying identity across a
  semantic redefinition of PICO fields would be scientifically wrong — the conservative
  guard must survive, just scoped correctly.
- **Add `identity_version` to Dataset v1 immediately.** Rejected because Dataset v1 is a
  shipped persisted data contract and accepted ADR-0020 requires append-only evolution;
  a breaking persisted-format change requires its own ADR + migration. Proposed ADR-0030
  is not used as authority for this conclusion.
- **Silently recompute historical ids on load.** Rejected: downstream references would be
  stranded without an auditable mapping and the caller could not distinguish migration
  from ordinary deserialization.
- **Keep first-occurrence-wins deduplication.** Rejected: once non-identity persisted
  fields may differ, input order would select bytes and violate the deterministic store
  contract.

## Compliance

Acceptance requires a bounded mechanical implementation plus regression coverage:

- `schema_version` remains part of the object and persisted format but no longer
  participates in `evidence_id`;
- `identity_version` is an exact positive integer, defaults to `1`, and participates in
  `evidence_id`;
- changing only `schema_version` preserves `evidence_id`;
- changing `identity_version` re-mints `evidence_id` in memory;
- the historical positional `schema_version` constructor slot remains stable;
- legacy format-1 evidence artifacts semantically default to `identity_version = 1`;
- recognized historical ids fail closed under ordinary loading and migrate only through
  the explicit distinct-destination migration tool;
- the migration tool returns deterministic old→new identity mappings;
- the format-1 writer emits no new field and rejects `identity_version != 1`;
- same-id/non-identical persisted payloads fail closed during both writing and loading,
  independent of input/line order;
- exact duplicate payloads remain accepted deterministically;
- Dataset v1 schema is unchanged;
- the public change is recorded under `CHANGELOG.md` `[Unreleased]`;
- no governance claim depends on Proposed ADR-0030.

No committed canonical evidence-object data migration is required at this decision point.
This ADR grants no model, corpus, runtime, training, promotion, deployment, release, or
clinical authority.
