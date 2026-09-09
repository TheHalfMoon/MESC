# OpenMed comparison and MedScale gap review

- **Status:** Source-backed planning review; no performance experiment conducted.
- **Date:** 2026-09-09.
- **MedScale baseline:** `ef5a70e86ff829efe52e042aaa37ce4bb8c418fe`.
- **Related:** [implementation roadmap](../execution/implementation_roadmap_2026-09-09.md),
  [backlog](../execution/implementation_backlog_2026-09-09.md),
  [historical analysis](openmed_capability_analysis.md), [ADR-0007](../adr/0007-openmed-adapter.md).

## What the sources establish

The current [OpenMed README](https://github.com/maziyarpanahi/openmed) describes local
extraction/de-identification, multilingual models, Python/mobile/browser interfaces,
FHIR-related workflows, evaluation and agent tooling. It distinguishes offline core execution
after artifact provisioning from optional network paths. Its SDK license does not establish
the terms of every model or dataset. These are upstream descriptions, not independently
verified quality results. The dynamic repository page was inspected on 2026-09-09; it is
not an immutable benchmark baseline. Pin a commit and model artifacts during MS-04.

The fetched [OpenMed package configuration](https://github.com/maziyarpanahi/openmed/blob/master/pyproject.toml)
(blob `27e0637e8aa19ca2fc9eeaa94da13d1cd28adbde`) confirms separate optional integrations,
including FHIR, and a core dependency list. Neither SDK packaging nor a model count
demonstrates medical correctness. This review did not run OpenMed or inspect all its code.

MedScale's source evidence includes [package configuration](../../pyproject.toml),
[model protocols](../../src/medscale/modelkit/interfaces.py),
[FHIR exports](../../src/medscale/fhirkit/__init__.py),
[benchmark exports](../../src/medscale/bench/__init__.py),
[Experiment-0 status](../../specs/mesc-experiment-0/STATUS.md),
[MRL tasks](../../specs/mesc-research-loop-v1/tasks.md), and
[current strategy](../strategy/mesc_health_model_program_2026-09-05.md).
These establish implementation surfaces and declared boundaries; they are not model-quality
results. This assessment did not perform a full security audit, clinical validation, model
evaluation, or exhaustive repository-wide feature audit.

## Capability-by-capability decision

| Area | Fair interpretation | MedScale action |
|---|---|---|
| Clinical extraction | OpenMed is a relevant comparator; MedScale already owns the `SpanExtractor` boundary | Implement the optional adapter and compare on identical independent synthetic gold, MS-04/05 |
| FHIR | OpenMed documents FHIR workflows; claiming it has no FHIR support would be unjustified | Demonstrate MedScale's particular structural, semantic and provenance contract, MS-03 |
| Evidence and reproducibility | MedScale has deterministic evidence/benchmark infrastructure; upstream also documents evaluation tooling | Compare specific reproducible workflows, not an unsupported claim that upstream lacks rigor |
| English/Arabic | Multilingual support exists upstream; language count does not establish medical quality | Independently reviewed language and code-switching slices, MS-06 |
| Offline operation | Both projects describe local execution boundaries | Verify missing-artifact failures and absence of network in the actual supported replay path |
| Adoption | OpenMed offers several interfaces; MedScale's research quickstart centers on screening | Deliver a direct synthetic verification example without importing mobile/clinical product scope |
| Privacy services | A deployment capability in OpenMed, outside MedScale's current core scope | Preserve ADR-0007 and the one-way Afia boundary; no feature-parity de-identification project |
| Health-model quality | An SDK is not the same evaluation object as MESC model weights | Use qualified model comparators in Experiment-0; do not frame an SDK feature gap as a model win |

## Gaps to close first

1. **A complete user outcome.** The package needs an obvious path from synthetic input to
   a report whose claims a researcher can inspect. Module lists are insufficient.
2. **FHIR semantics beyond syntax.** Explicit source support, negation, subject, units and
   reference integrity must accompany generation. Passing a JSON/FHIR check alone is weak evidence.
3. **A fair overlap benchmark.** Neither this review nor current roadmap prose proves an
   advantage over OpenMed. Freeze the comparator, label mappings, thresholds and common workload.
4. **Independent bilingual gold.** Translation and model confidence cannot substitute for
   medical annotation; unknown or underpowered slices must remain inconclusive.
5. **Real qualification evidence.** Experiment-0 preparation and infrastructure do not
   satisfy runtime, asset, evaluator and execution gates. Use the existing MRL path.
6. **Scope coherence.** Keep synthetic default admission explicit while resolving any
   public/de-identified-data proposal against accepted source-specific decisions and R2.
7. **Usability evidence.** Measure first successful reproduction with external researchers,
   not only internal test counts.

## Corrections to historical assumptions

The July capability analysis remains historical context for ADR-0007. Do not reuse its model
counts, language counts, blanket artifact-license interpretation, unconditional network
characterization, or family naming examples as current facts. The public model name is
MESC under ADR-0036. Artifact rights remain item-specific. Existing accepted decisions are
not rewritten by a newer comparison page.

The opportunity is an integrated, inspectable research workflow with measured quality.
It is a hypothesis to demonstrate, not an exclusive capability claim. The delivery plan
prioritizes that hypothesis while retaining OpenMed as a useful baseline and optional dependency.

## Claim policy for future reports

Use a statement such as: “At these immutable revisions, on this synthetic dataset and
declared label set, MedScale achieved this metric difference with this confidence interval.”
Publish scripts, permitted artifacts, seeds, failures and runtime facts. A negative result
must receive the same treatment. Do not generalize a synthetic extraction result to clinical
safety, universal model leadership, all languages, or all of OpenMed.

## Planning-package verification

On 2026-09-09, the repository's `scripts/check_docs_links.py` was executed with the
bundled Python runtime on Windows and returned:

```text
docs link hygiene: PASS (125 Markdown files)
```

`git diff --check` exited 0. A targeted `python -m pytest -q
tests/test_docs_link_hygiene.py` attempt could not start because that runtime has no
`pytest` module. Full CI and independent review remain pending; no model benchmark or
training was run. These checks validate documentation source hygiene only.
