# Paper Publication Workflow

- **Status:** Strategy (ADR-0010, Accepted)
- **Original strategy date:** 2026-07-10
- **Reconciled:** 2026-09-03 under ALIGN-23
- **Related:** [research questions](../research/research_questions.md),
  [reproducibility policy](../research/reproducibility_policy.md), Rule R1/R7,
  [Blueprint §12](../vision/MEDSCALE_STRATEGIC_BLUEPRINT_V1.md) (the paper arc)

This document is binding publication policy for any future paper/replication package.
It is not evidence that experiments, result artifacts, papers, submissions, preprints,
or replication packages currently exist or are authorized.

## The pipeline

```
Research question (RQ, falsifiable, pre-registered criteria)
        ↓
Authorized execution + code at an exact canonical revision
        ↓
Experiments (manifests: seeds, data hashes, environment)
        ↓
Results (committed qualified artifacts; required uncertainty/negative results)
        ↓
Paper (verified citations; claims trace to artifacts)
        ↓
Released artifacts cited by exact version
        ↓
Replication package (tag + manifests + snapshots/pointers + exact commands)
```

No stage may manufacture a later stage. A planned run is not a result; a result is not
a released artifact; a draft is not a publication; and a publication policy is not
publication authority.

## Stage gates

1. **Before experiments:** applicable research questions/falsification criteria and
   execution authority must already be canonical. Experiments test those criteria;
   they do not redefine them post hoc.
2. **Before drafting:** every numerical/scientific claim intended for the paper must
   trace to committed, qualified evidence under the applicable research governance.
   Writing starts from evidence, not memory or fixture-only plumbing.
3. **Citations:** references must satisfy the repository's applicable citation/evidence
   rules and be mechanically or independently verified where required before
   submission.
4. **Before submission:** the replication package must be separately authorized,
   assembled, and verified from its own governed inputs. A package tag may not be
   created merely because this policy describes one.
5. **Preprint/publication:** venue choice, licence, submission, DOI/archive actions,
   and external publication remain explicit future actions requiring their applicable
   authority. Artifact versions, not `latest`, are cited when publication occurs.

## Replication package requirements

A qualified package should contain or deterministically reference the canonical source
revision/tag, manifests of cited artifacts, governed data snapshot identities,
environment specification, exact commands/seeds, expected committed outputs, and a
README sufficient for an independent reproduction attempt. Required material must be
evidence-backed; missing external data/rights/compute cannot be replaced with invented
artifacts.

## Honesty clauses

- Negative or null results under pre-registered criteria remain first-class outcomes.
- Superlative capability claims require their own applicable comparative evidence.
- Paper prose may not strengthen a result beyond what its exact evidence/manifests
  support.
- Mission Zero and MRL canonical state outrank publication plans and prose summaries.

## Authorship & acknowledgment

Authorship and acknowledgments follow actual contributions and applicable venue policy.
Tools, including AI assistants, are acknowledged according to venue requirements and
are not treated as evidence-generating human participants or authors merely because
this repository used them.
