# MedScale Documentation

The canonical documentation for MedScale. Start here.

## Reading order

1. [README](../README.md) — what MedScale is, in one page.
2. [Strategic Blueprint](vision/MEDSCALE_STRATEGIC_BLUEPRINT_V1.md) — the full narrative.
3. [Research Vision](vision/MEDSCALE_RESEARCH_VISION.md) — scope authority (what is / is not).
4. [Research Questions](research/research_questions.md) — RQ1–RQ7.
5. [Program Rules R1–R7](governance/rules.md) — the rules the docs cite by number.
6. [Glossary](glossary.md) — terminology.

## Map

| Area | Documents |
|---|---|
| **Vision** | [Strategic Blueprint](vision/MEDSCALE_STRATEGIC_BLUEPRINT_V1.md) · [Research Vision](vision/MEDSCALE_RESEARCH_VISION.md) |
| **Research** | [index](research/README.md) · [research questions](research/research_questions.md) · [paper taxonomy](research/paper_taxonomy.md) · [reproducibility policy](research/reproducibility_policy.md) · [experiment framework](research/experiment_framework.md) · [novelty candidates](research/novelty_candidates.md) |
| **Governance** | [rules R1–R7](governance/rules.md) · [roles & authority](governance/roles_and_authority.md) · [governance index](governance/README.md) |
| **Reviews** | [post-round-1 architecture review](architecture/reviews/2026-07-10-post-round1.md) · [scientific integrity review #1](research/reviews/2026-07-10-scientific-integrity-round1.md) · [CTO review #1](architecture/reviews/2026-07-10-cto-review.md) · [architectural stress test](architecture/reviews/2026-07-10-stress-test.md) · [survivability audit (2038 test)](architecture/reviews/2026-07-10-survivability-audit.md) |
| **Architecture** | [ecosystem analysis](architecture/ecosystem_analysis.md) · [reference architecture](architecture/medscale_reference_architecture.md) · [ecosystem evolution (Linux-style long view)](architecture/ecosystem_evolution.md) · [model-agnostic platform](architecture/model_agnostic_platform.md) · [AI model strategy](architecture/ai_model_strategy.md) · [OpenMed strategy](architecture/openmed_integration_strategy.md) · [OpenMed capability analysis](architecture/openmed_capability_analysis.md) · [interoperability strategy](architecture/interoperability_strategy.md) · [HF distribution](architecture/distribution_hf.md) |
| **Models** | [model registry](models/model_registry.md) · [LLM landscape](models/llm_landscape.md) · [model card schema](models/schemas/model_card_schema.md) |
| **Strategy** | [MESC strategic model roadmap](strategy/mesc_strategic_model_roadmap_2026-08-18.md) · [MCRL](strategy/mesc_capability_realization_layer_2026-08-18.md) · [frontier program](strategy/mesc_frontier_program_2026-08-18.md) · [post-B0 reconciliation](strategy/mesc_pr122_post_b0_reconciliation_2026-08-19.md) · [donor reviews](strategy/donors/) |
| **Decisions** | [ADR template](adr/0000-template.md) · [0003 topology](adr/0003-repository-topology.md) · [0004 T0 scope](adr/0004-t0-foundation-scope.md) · [0005 research-intelligence scope](adr/0005-research-intelligence-scope.md) · [0006 model access](adr/0006-model-access-strategy.md) · [0007 OpenMed adapter](adr/0007-openmed-adapter.md) · [0008 FHIR canonical](adr/0008-interoperability-fhir-canonical.md) · [0009 evidence model](adr/0009-evidence-model.md) · [0012 layered architecture (hybrid)](adr/0012-layered-architecture-model.md) · [0015 model-agnostic platform](adr/0015-model-agnostic-platform.md) · [0016 raw-archive storage (Option A)](adr/0016-raw-archive-storage.md) · [0017 identifier stability contract](adr/0017-identifier-stability-contract.md) · [0018 evidence identity decoupling](adr/0018-evidence-identity-decoupling.md) · [0020 public API stability policy](adr/0020-public-api-stability.md) — all Accepted · [0010 release architecture](adr/0010-release-architecture.md) *(Proposed)* · [0011 versioning & licensing](adr/0011-versioning-licensing.md) *(Proposed)* · [0013 language strategy](adr/0013-language-strategy.md) *(Proposed)* · [0014 core namespace](adr/0014-core-namespace.md) *(Proposed)* · [0019 continuity & succession](adr/0019-continuity-and-succession.md) *(Proposed)* · [0021 extension architecture](adr/0021-extension-architecture.md) *(Proposed — design only)* · [0022 screening decision semantics](adr/0022-screening-decision-semantics.md) *(Accepted — Mission Zero GO gate)* |
| **Releases** | [publication & artifact lifecycle](releases/README.md) — lifecycle, versioning, process + checklists, distribution, licensing, cards, benchmark publication, papers, manifests, CI/CD design |
| **Guides** | [research quick start](guides/research_quickstart.md) · [first systematic review](guides/first_systematic_review.md) · [troubleshooting](guides/troubleshooting.md) · [developer guide](guides/developer_guide.md) |
| **Execution** | [phase planning (T0–T7)](execution/README.md) · [Mission Zero operations manual](execution/mission_zero/README.md) — protocol · daily checklist · incident response · journal · completion criteria · metrics · lessons-learned framework |
| **Archive** | [superseded material](archive/) |

## Canonical sources & precedence

To avoid drift between overlapping documents, precedence is explicit:

- **Scope** (what is in/out of the program) → the **Research Vision** governs.
- **Narrative / external presentation** → the **Strategic Blueprint**.
- **Rules cited by number** → **`governance/rules.md`**.
- **A decision of record** → the relevant **ADR** overrides prose elsewhere.

Where the Blueprint's condensed 3-horizon presentation and the Vision's 4-horizon model
differ, the **Vision governs** (see [ROADMAP](../ROADMAP.md)).

## Naming conventions

- Docs: `lower_snake_case.md` (except the two flagship vision docs and root community
  files such as `README`, `LICENSE`, which are `SCREAMING_SNAKE` / conventional).
- ADRs: `NNNN-kebab-title.md`, append-only numbering.
- Front-matter: a short block of `Status` / `Date` / `Related` at the top of each doc.
