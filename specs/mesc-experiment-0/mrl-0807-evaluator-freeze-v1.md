# MRL-0807 RQ1/FHIR evaluator freeze producer

## Purpose

This package freezes the evaluator identities needed for the bounded RQ1 FHIR structural
experiment selected by the MRL program. It is deliberately narrower than the full
Experiment-0 tournament: only the rights-qualified and isolation-qualified Synthea FHIR R4
Patient projection is represented.

The producer does not execute a model, disclose sealed Tier-3 items, train, mutate weights,
promote, release, or create clinical authority.

## Frozen evaluator bundle

The bundle contains exactly two deterministic primary evaluators:

1. HL7 FHIR validator CLI `6.10.4`, pinned by public release asset size and SHA-256, with
   FHIR R4 invocation and machine-readable JSON output;
2. MedScale Patient projection set-F1 over the exact admitted MRL-0802 fields.

The second evaluator is required because RQ1 is falsified if constrained generation reaches
structural validity only by collapsing content into empty or degenerate resources. The
score is represented by exact integer counts and a rational numerator/denominator; no
binary floating point, fuzzy matching, embeddings, or LLM-as-judge is used.

## External custody boundary

The producer PR records the official validator identity but does not claim custody of the
binary. After producer merge, `scripts/mesc_mrl_0807_evaluator_qualify.py` must run from a
clean exact-main checkout and must receive the externally stored `validator_cli.jar`. The
qualifier recomputes exact size and SHA-256 and fails closed on any mismatch before it can
emit an evidence candidate.

## Sealed Tier-3 boundary

The committed sealed identity binds only the MRL-0803 external sealed-byte SHA-256 and byte
count. No Patient ID or item content is embedded. Tier 3 remains aggregate-output-only and
is prohibited from adaptive search and training.

## Trust boundary

The qualifier emits an **untrusted** `mesc.mrl.real_preflight.evaluators.v1` evidence
candidate. This producer intentionally does not mutate the production real-preflight trust
registry, evidence index, MRL-0807 slot, or task checkbox. Exact evidence must be produced
and independently revalidated after producer merge, then admitted through a separate
minimal trust PR.

## Separate RQ1 prerequisite

StructureDefinition-to-GBNF compilation and a grammar-capable model backend remain separate
RQ1 execution prerequisites. They are not authorized by Issue #418 and are not implemented
by this evaluator-freeze unit.
