# MRL-0803 Experiment-0 isolation producer

## Purpose

This package produces deterministic, **untrusted** MRL-0803 contamination and held-out
isolation evidence for the exact synthetic structural Patient corpus admitted by MRL-0802.
It does not execute Experiment-0 and does not authorize model loading, inference, GPU use,
training, promotion, release, or deployment.

The committed authorization is:

```text
mrl-0803-isolation-authorization-v1.json
```

Its exact SHA-256 is bound in the producer implementation. The production entry point also
requires a clean exact Git work tree descended from the authorized canonical base.

## Contamination claim boundary

The MRL-0803 `PASS` disposition is deliberately limited to:

```text
MESC_CONTROLLED_SURFACES_ONLY
```

The producer does **not** claim visibility into, or absence of overlap with, inaccessible
upstream pretraining corpora used by Qwen, Gemma, or any other foundation model.

The MRL-0802 admitted corpus is a terminology-free structural Patient projection containing
only Patient identity, demographic primitives, and normalized city/country/postal/state
address fields. It contains no clinical note text, diagnoses, procedures, medications,
questions/answers, prompts, benchmark answers, or other semantic clinical payload. For that
specific projection, a semantic-content detector is recorded as:

```text
NOT_APPLICABLE_STRUCTURAL_PATIENT_PROJECTION
```

This is not an escape hatch for future training data. Any future training/example lineage
remains subject to MRL-0601..MRL-0607 exact/near/semantic contamination and canary controls.

## Deterministic split

The exact 16-record corpus is partitioned into:

```text
TIER_1_SEARCH       = 8 records
TIER_2_REPLICATION  = 4 records
TIER_3_SEALED       = 4 records
```

Patient records sharing the same normalized synthetic household/address identity are an
indivisible group. Tier 3 is chosen first, Tier 2 second, and Tier 1 receives the remaining
groups. Candidate group subsets are ranked by SHA-256 over canonical policy/tier/group
identity bytes. Runtime randomness and filesystem order are not inputs.

A qualifying split must prove:

- exact corpus SHA-256, byte count, record count, and canonical JSONL order;
- unique Patient ids;
- no exact record overlap across tiers;
- no normalized synthetic household overlap across tiers;
- frozen near-structural Jaccard similarity strictly below `4/5` across tiers;
- Tier 3 exclusion from MESC-controlled training and adaptive search;
- no Tier 3 item-level content in the public lineage report.

## External custody outputs

The producer writes only to an explicit external empty output directory:

```text
split-manifest.json
tier1-search.jsonl
tier2-replication.jsonl
tier3-sealed.jsonl
lineage-report.json
decontamination-report.json
mrl-0803-real-preflight-evidence.json
```

The split manifest and tier JSONL files contain item-level custody information and are not
repository artifacts. Tier 3 custody must remain outside the adaptive research process.
The lineage and decontamination reports expose identities/aggregates needed for independent
verification without carrying Tier 3 Patient ids.

## Trust boundary

A schema-valid output remains untrusted. The producer does not modify:

```text
TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256
real-preflight-evidence-index-v1.json
specs/mesc-research-loop-v1/tasks.md
```

After this producer is independently reviewed, merged, and post-merge qualified, genuine
output must be regenerated from the exact admitted corpus and independently recomputed.
Only then may a separate exact-digest trust-admission mutation be considered under Issue
#407.
