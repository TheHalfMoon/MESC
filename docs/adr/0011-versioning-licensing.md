# ADR-0011 — Artifact Versioning Schemes and the Licensing Matrix

- **Status:** Accepted
- **Date:** 2026-07-10
- **Accepted:** 2026-09-03 after reconciliation to canonical `main`
- **Deciders:** Operator (solo founder)
- **Supersedes:** none (completes the licence decision left as a "working assumption"
  in Vision §8; the Apache-2.0 LICENSE file has been in force since T0)
- **Superseded by:** none
- **Related:** [ADR-0006](0006-model-access-strategy.md) (model tiers),
  [ADR-0009](0009-evidence-model.md) (schema versioning),
  [releases/versioning.md](../releases/versioning.md),
  [releases/licensing.md](../releases/licensing.md)

## Context

Five artifact classes with different mutation semantics need version schemes that make
*content change visible in citations*; and the platform invariant (everything shipped
permits derivatives + commercial use) needs a per-artifact licensing matrix rather than
a single repo licence. Datasets can inherit composite upstream terms, and model weights
can inherit base-model terms.

At acceptance, the repository/package baseline remains version `0.2.0` and the
repository licence is Apache-2.0. Acceptance governs future artifact identity and
release decisions; it does not retroactively create, relicense, publish, or validate an
artifact whose own evidence or upstream terms are absent.

## Decision

1. **Versioning schemes** are specified in
   [releases/versioning.md](../releases/versioning.md): SemVer for the Python package;
   `vX.Y` without PATCH for models/datasets/benchmarks; append-only integers for
   governed schemas per ADR-0009; and prefixed git tags (`<artifact>-vX.Y`) for
   non-package artifacts in the single repository.
2. **Licensing matrix** is specified in
   [releases/licensing.md](../releases/licensing.md): Apache-2.0 repo-wide for code and
   documentation; MedScale-authored adapter release eligibility only where the base
   terms are compatible with the applicable release policy; CC-BY-4.0 for published
   wholly synthetic datasets when their provenance permits it; field-level composite
   treatment for mixed-source litdb exports; permissive-only runtime dependencies; and
   compatibility review for anything vendored.
3. **Tier-2 derivatives** remain unreleased absent a dedicated Accepted ADR and the
   applicable upstream/release evidence. ADR acceptance does not convert model access
   into redistribution authority.
4. **Citation:** `CITATION.cff` is maintained for package/repository releases as
   applicable; artifact cards carry exact version/citation information; papers cite
   exact artifact versions, never "latest".
5. **Version and licence claims are evidence-bound.** A policy rule can require a
   check, but the repository must not claim that a mechanical enforcement exists until
   that enforcement is actually implemented and qualified.

## Consequences

**Positive:** versions become claims about immutable content; licence questions are
resolved by a stable matrix rather than release-time improvisation; citations can bind
to exact artifact identities.

**Negative / costs:** no-PATCH versioning makes even small data/weight corrections
visible version bumps; field-level dataset licensing demands per-field provenance;
mechanical release validation may require additional separately scoped implementation
before a particular artifact can be distributed.

## Alternatives considered

- **CalVer for datasets.** Rejected: dates say *when*, not *whether comparability
  broke* — the property citations need.
- **Single CC licence for all data.** Rejected: upstream terms are heterogeneous;
  blanket licensing can over-claim rights or impose unnecessary restrictions.
- **Dual-licensing docs vs code.** Rejected for the repository baseline: the current
  repo-wide Apache-2.0 licence provides a simpler boundary; standalone publications can
  follow their separately applicable publication terms.

## Compliance

From acceptance on 2026-09-03,
[releases/versioning.md](../releases/versioning.md) and
[releases/licensing.md](../releases/licensing.md) are binding release policy.

Mechanical enforcement must be added and qualified in the workflow or validation unit
that actually needs it. Acceptance alone does not prove SPDX validation, manifest
validation, dataset redistribution eligibility, model redistribution eligibility, or
external publication readiness, and it grants no model/data execution, training,
publication, or deployment authority.
