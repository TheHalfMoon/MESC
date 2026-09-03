# Licensing Strategy

- **Status:** Binding policy (ADR-0011, Accepted)
- **Original design date:** 2026-07-10
- **Governance reconciliation:** 2026-09-03
- **Related:** Rule R3, [governance rules](../governance/rules.md), ADR-0006 (model tiers),
  `data/litdb/LICENSE.md` (live example of field-level review)

Platform invariant: anything MedScale distributes must have terms compatible with the
applicable governed use/distribution promise. This document maps that requirement onto
artifact classes; it does not create rights that upstream licences do not grant.

The repository/code/documentation baseline at governance reconciliation is Apache-2.0.
Dataset/model publication eligibility remains evidence- and upstream-terms-dependent.

## The matrix

| Artifact | Licence / release boundary | Reasoning |
|---|---|---|
| Code (`medscale`, scorers, adapters) | **Apache-2.0** repository baseline | Permissive + patent grant |
| Documentation, ADRs, guides | Apache-2.0 under the repo-wide baseline | One repository licence avoids an artificial docs/code boundary |
| MedScale-authored model adapters | Apache-2.0 only when base/upstream terms permit that release | Adapter authorship does not erase base-model terms |
| `medscale-base-ref` configuration artifacts | Apache-2.0 when they contain only MedScale-authored config/docs and no third-party weights | Configuration identity is distinct from redistributed model weights |
| Tier-2 / passthrough-restricted derivatives | **Not released** absent dedicated Accepted governance and applicable upstream authority | Evaluation/access permission is not redistribution authority |
| Wholly synthetic published datasets | CC-BY-4.0 when provenance/upstream terms permit | Data and code use different conventional distribution licences |
| Generated data | Governed by dataset licence plus generator/upstream provenance | Model-output terms and provenance remain review inputs |
| LitDB export | **Composite, field-level** according to recorded upstream terms; non-redistributable fields excluded | Mixed upstream terms cannot be blanket-licensed |
| Benchmark (spec + scorers + data) | Code under Apache-2.0; data under its separately established dataset terms | Executable code and distributable data have different provenance |
| Papers/preprints | Venue/publication terms; separately governed from repository code | Publication policy is venue- and artifact-specific |
| External runtime dependencies | Permissive-only under the accepted dependency policy | Adoption requires compatibility review |
| Vendored material | Must pass explicit compatibility/provenance review | Repository licence cannot overwrite third-party terms |

## Inheritance rules

1. **Base → adapter:** a released adapter must satisfy the base model's applicable
   redistribution terms and the MedScale release boundary. Tier classification is a
   governance aid, not a substitute for exact upstream terms at release time.
2. **Data source → dataset:** each contributing field/item retains the applicable
   upstream constraint: pass through, attribute, or exclude as required.
3. **Dataset → model:** training data terms must permit the intended training and
   redistribution of resulting artifacts; that evidence belongs in the training/release
   manifest before publication eligibility can be claimed.
4. **Vendoring compatibility:** permissive compatibility must be verified before bytes
   enter a distributable repository/artifact. A policy statement is not mechanical
   evidence that an unchecked dependency is compatible.

## Citation requirements

- Repo/package: `CITATION.cff` is maintained as applicable to releases.
- Each distributed dataset/model card carries exact version/citation metadata.
- Papers cite exact artifact versions, never "latest".
- Upstream attribution is preserved wherever its terms require it.
- Inbound scientific claims continue to follow the separately applicable evidence
  governance; accepting this licensing policy does not authorize new evidence.

## Enforcement boundary

ADR-0011 makes this matrix binding policy. Mechanical SPDX, manifest, or dependency
licence validation is claimed only where the repository actually implements and
qualifies that validation. Missing mechanical enforcement is a scoped implementation
gap, not permission to bypass licence review.
