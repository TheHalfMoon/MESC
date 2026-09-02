# ADR-0018 — Decouple Evidence Identity from Container Schema Version

- **Status:** Accepted (founder approved 2026-09-02)
- **Date:** 2026-07-10
- **Decision date:** 2026-09-02
- **Deciders:** Founder
- **Amends:** [ADR-0009](0009-evidence-model.md) (identity-field list)
- **Related:** [ADR-0017](0017-identifier-stability-contract.md) (identifier stability),
  [stress test F2](../architecture/reviews/2026-07-10-stress-test.md)

## Context

ADR-0009 includes `schema_version` among the fields hashed into `evidence_id`. The
intent was conservative: if the schema's *meaning* changes, identity should not carry
over silently. The stress test exposed the cost at scale: the first v1→v2 bump re-mints
the id of **every** evidence object simultaneously — at millions of objects, every
knowledge-graph edge, benchmark citation, and cross-corpus reference breaks in one
release. That is the ADR-0017 orphaning hazard, ecosystem-wide.

The window to change this is **now**: zero evidence objects exist as committed data, so
the amendment costs nothing today and avoids a coordinated mass migration later.

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

## Consequences

**Positive:** schema evolution (the *common* case: new optional fields) becomes free —
no migrations, no orphaned references; identity discontinuity is reserved for genuine
semantic change (the *rare* case), made explicit by `identity_version`.
**Negative:** two version fields to understand (mitigated: glossary + docstrings state
the rule in one line — *schema versions the container, identity_version versions the
meaning*).

## Alternatives considered

- **Keep as-is.** Rejected: punishes routine evolution with ecosystem-wide id churn;
  the stress test rates this the most expensive latent decision in the evidence layer.
- **No version in identity at all.** Rejected: silently carrying identity across a
  semantic redefinition of PICO fields would be scientifically wrong — the conservative
  guard must survive, just scoped correctly.

## Compliance

Acceptance requires one mechanical change to `medscale.evidence` plus persistence and
regression coverage:

- `schema_version` remains serialized but no longer participates in `evidence_id`;
- `identity_version` is an exact positive integer, defaults to `1`, is serialized, and
  participates in `evidence_id`;
- legacy format-1 evidence artifacts without `identity_version` load as version `1`;
- changing only `schema_version` preserves `evidence_id`;
- changing `identity_version` re-mints `evidence_id`.

No data migration is required because no committed evidence objects exist at the decision
point. This ADR grants no model, corpus, runtime, training, promotion, deployment, release,
or clinical authority.
