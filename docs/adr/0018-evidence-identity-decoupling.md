# ADR-0018 — Decouple Evidence Identity from Container Schema Version

- **Status:** Accepted (founder approved 2026-09-02)
- **Date:** 2026-07-10
- **Decision date:** 2026-09-02
- **Deciders:** Founder
- **Amends:** [ADR-0009](0009-evidence-model.md) (identity-field list)
- **Related:** [ADR-0017](0017-identifier-stability-contract.md) (identifier stability),
  [ADR-0030](0030-dataset-versioning-and-training-artifact-contract.md) (frozen Dataset v1
  schema), [stress test F2](../architecture/reviews/2026-07-10-stress-test.md)

## Context

ADR-0009 includes `schema_version` among the fields hashed into `evidence_id`. The
intent was conservative: if the schema's *meaning* changes, identity should not carry
over silently. The stress test exposed the cost at scale: the first v1→v2 bump re-mints
the id of **every** evidence object simultaneously — at millions of objects, every
knowledge-graph edge, benchmark citation, and cross-corpus reference breaks in one
release. That is the ADR-0017 orphaning hazard, ecosystem-wide.

The window to change the identity derivation is **now**: zero evidence objects exist as
committed data, so the amendment requires no evidence-object data migration. Dataset v1,
however, is already a public-frozen artifact schema under ADR-0030 and must not be silently
expanded by this amendment.

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
4. ADR-0017's contract extends unchanged: any `identity_version` bump is a breaking
   change requiring an ADR + lineage-based migration.
5. **Dataset v1 and evidence format 1 remain unchanged on disk.** The current writer
   supports only `identity_version == 1` and does not serialize an additional
   `identity_version` member into format-1 artifacts. A non-v1 identity version must fail
   closed at the persistence boundary until a separately governed container/dataset
   version admits and persists that identity version.

## Consequences

**Positive:** schema evolution (the *common* case: new optional fields) no longer changes
semantic evidence identity; identity discontinuity is reserved for genuine semantic
change (the *rare* case), made explicit by `identity_version`. Existing Dataset v1 and
format-1 artifact schemas are not silently mutated.

**Negative:** two version concepts must be understood. While Dataset v1 remains current,
non-default identity versions cannot be persisted; that is deliberate fail-closed behavior,
not an implicit schema upgrade. A future identity-version bump must coordinate its new
container/dataset format under ADR-0030.

## Alternatives considered

- **Keep as-is.** Rejected: punishes routine evolution with ecosystem-wide id churn;
  the stress test rates this the most expensive latent decision in the evidence layer.
- **No version in identity at all.** Rejected: silently carrying identity across a
  semantic redefinition of PICO fields would be scientifically wrong — the conservative
  guard must survive, just scoped correctly.
- **Add `identity_version` to Dataset v1 immediately.** Rejected: ADR-0030 freezes that
  public schema and requires a new dataset version/ADR for schema changes. ADR-0018 does
  not bypass that later governance boundary.

## Compliance

Acceptance requires a bounded mechanical implementation plus regression coverage:

- `schema_version` remains part of the object and persisted format but no longer
  participates in `evidence_id`;
- `identity_version` is an exact positive integer, defaults to `1`, and participates in
  `evidence_id`;
- changing only `schema_version` preserves `evidence_id`;
- changing `identity_version` re-mints `evidence_id` in memory;
- legacy format-1 evidence artifacts load with `identity_version = 1`;
- the format-1 writer emits no new field and rejects `identity_version != 1`;
- the current reader rejects a non-v1 identity version presented to the format-1
  persistence layer;
- Dataset v1 schema is unchanged.

No committed evidence-object data migration is required at this decision point. This ADR
grants no model, corpus, runtime, training, promotion, deployment, release, or clinical
authority.
