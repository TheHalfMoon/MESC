# Clinical Workspace Source Refresh — 2026-09-20

- **Status:** Planning evidence for Issue #459
- **Reviewed MedScale base:** `475a389777c02a1992acafa24b1cfd1dae24c46b`
- **Purpose:** refresh external product/donor facts before architecture ratification
- **Policy:** source descriptions are capability observations, not independent quality, safety, compliance, or superiority claims
- **Related:** [ADR-0038](../adr/0038-local-clinical-workspace-boundary.md), [Clinical Workspace V1](../../specs/medscale-clinical-workspace-v1/README.md)

## Method

The planning package separates three evidence classes:

1. **Current primary product/source documentation** — suitable for describing the provider's own documented capabilities.
2. **Current repository state at an immutable revision** — suitable for source/licensing/provenance planning.
3. **Independent evidence** — required before MedScale makes comparative quality, safety, clinical, or performance claims.

A vendor or project describing a capability does not prove that capability is clinically effective or superior. MedScale will reproduce only claims established by its own qualified evidence.

## Canonical MedScale constraints

At the reviewed base, current accepted MedScale documents establish:

- the Research Core is synthetic-only;
- Research Core training/evaluation/benchmark data cannot receive patient or product data;
- MedScale is currently described as research infrastructure rather than a clinician-facing product;
- FHIR is the canonical clinical interchange/representation boundary;
- scope changes costing more than one day to reverse require an ADR;
- model/runtime/training/publication/clinical authority is not implied by planning.

Those facts create the conflict that Issue #459 and proposed ADR-0038 must resolve.

## Abridge — product/workflow reference

### Current primary sources reviewed

- https://www.abridge.com/platform/clinicians
- https://www.abridge.com/
- https://www.abridge.com/product
- https://www.abridge.com/ai
- https://www.abridge.com/blog/orders-real-time-clinical-documentation
- https://www.abridge.com/press-release/abridge-integrates-nejm-jama

Accessed: 2026-09-20.

### Current observed product pattern

Abridge describes an encounter-spanning workflow:

- **before the visit:** relevant history, care gaps, and context;
- **during the visit:** ambient documentation, real-time clinical intelligence, evidence, and order capture;
- **after the visit:** structured specialty note ready for review, editing, and workflow completion.

Abridge also documents:

- contextual evidence inside the encounter workflow;
- source/Linked Evidence concepts for generated documentation;
- spoken intent converted into **draft** medication, laboratory, imaging, referral, procedure, follow-up, and other order suggestions;
- evidence content partnerships with NEJM and JAMA;
- clinician review/edit workflow.

### MedScale disposition

**STUDY / BUILD MEDSCALE-OWNED WORKFLOW.**

Do not copy branding, proprietary implementation claims, or vendor security/compliance assertions. The useful architecture lesson is the encounter arc and the need for source-linked, reviewable outputs.

MedScale V1 should treat generated clinical actions as drafts and preserve a human confirmation boundary.

## OpenEvidence — evidence-workflow reference

### Primary/partner sources reviewed

- https://takehome.openevidence.com/
- https://www.cedars-sinai.org/newsroom/cedars-sinai-enhances-clinical-decision-making-with-openevidence/
- https://www.mountsinai.org/about/newsroom/2026/mount-sinai-and-openevidence-announce-strategic-partnership-to-advance-ai-enabled-clinical-decision-making
- https://www.cochrane.org/about-us/news/cochrane-evidence-inform-openevidence-users

Accessed: 2026-09-20.

The public OpenEvidence homepage could not be treated as the sole source in this review because the fetch path was access-restricted. The package therefore relies on available first-party subdomain material and primary partner announcements rather than inventing missing product details.

### Current observed product pattern

Primary partner materials establish that OpenEvidence is used for natural-language clinical questions and medical-literature retrieval, including integrations where relevant patient-record context can shape retrieval. Cochrane states that its publishing partner licenses Cochrane systematic-review content to OpenEvidence.

### MedScale disposition

**BUILD MEDSCALE-OWNED EVIDENCE WORKSPACE.**

The minimum trustworthy architecture is:

- explicit corpus/source identity;
- query identity;
- retrieval snapshot;
- citation identity;
- claim-to-source relationship;
- evidence-strength metadata where established;
- contradiction/missing-information state;
- source freshness;
- abstention;
- reproducible answer replay.

Patient context, if later authorized, remains a Workspace input and never becomes Research Core evidence automatically.

## OpenMed — implementation donor and comparator

### Repository identity

- Repository: `maziyarpanahi/openmed`
- Reviewed branch: `master`
- Reviewed revision: `5e0ce3991356877a9ec2003637ebdd75fb74f5cd`
- Repository license metadata: Apache-2.0
- SDK root license reviewed: Apache License 2.0
- Accessed: 2026-09-20

### Current observed surface

The current README describes:

- local clinical extraction after required artifacts are available;
- PII detection and de-identification;
- CPU/CUDA execution;
- Apple MLX / iOS support;
- Android / ONNX Runtime Mobile support;
- browser / Transformers.js support;
- Python, REST/service, batch, CLI/MCP/agent-oriented interfaces;
- FHIR-related workflows;
- explicit distinction between local runtime and optional network paths;
- current manifest/model-catalog metadata substantially broader than the repository's July analysis.

### Important correction to historical MedScale analysis

The July `openmed_capability_analysis.md` is no longer safe as a current feature inventory. Its model counts, language counts, backend breadth, and product-scope observations are historical.

The SDK license also **does not establish the license of every model or dataset**. Every artifact must receive its own rights/provenance decision.

### MedScale disposition

- local clinical NER: **ADAPT candidate**
- PII detection/de-identification for Workspace export/privacy workflow: **ADAPT candidate**
- local runtime patterns: **STUDY / ADAPT selectively**
- model/dataset artifacts: **INDIVIDUAL REVIEW REQUIRED**
- OpenMed output as ground truth: **REJECT**
- hard Research Core dependency: **REJECT**

No OpenMed source is imported by this planning package.

## Graphify — graph/provenance donor

### Repository identity

- Repository: `Graphify-Labs/graphify`
- Reviewed branch: `v8`
- Reviewed revision: `20a20d30d8e7eef77675651f0199d87f913bd3e7`
- Repository license metadata: Apache-2.0
- Root license reviewed: Apache License 2.0
- Accessed: 2026-09-20

### Current observed architecture lessons

The repository describes:

- deterministic local parsing for supported structured/code sources;
- a persistent graph;
- query/path/explain operations;
- first-class relationships that distinguish observed/extracted information from inference/ambiguity;
- optional semantic/backend passes rather than making every graph construction step model-dependent.

### MedScale disposition

**STUDY + ADAPT selected Apache-compatible components only after file-level provenance review.**

The patient graph must remain MedScale-owned and healthcare-specific. Its critical borrowed principle is epistemic labeling:

```text
EXTRACTED
DERIVED
INFERRED
ASSERTED
AMBIGUOUS
```

No graph edge becomes medical truth merely because it is connected.

## AFFiNE — local-first workspace reference

### Repository identity

- Repository: `toeverything/AFFiNE`
- Reviewed branch: `canary`
- Reviewed revision: `d897bb3d84099e54a6b3c0bd5f4265f8aa87d190`
- GitHub repository license metadata: `NOASSERTION`
- Root license reviewed: mixed/path-dependent terms
- Accessed: 2026-09-20

### Current observed product principles

The README describes:

- privacy-focused, local-first workspace behavior;
- documents, canvas, tables/databases, linked objects and assets;
- offline/local ownership with optional collaboration;
- self-hosting.

### License boundary

The root license explicitly assigns different terms to portions of the tree and otherwise points to MIT terms. Therefore:

```text
WHOLE_REPOSITORY_IS_MIT = FALSE
DIRECT_TREE_IMPORT_WITHOUT_PATH_REVIEW = FORBIDDEN
```

Every reused path requires its own license/provenance check.

### MedScale disposition

**STUDY interaction/object-model principles first.**

Direct code reuse is permitted only after exact path/revision/license review. MedScale healthcare semantics, security labels, provenance, and clinical workflows remain independent.

## OctoBase — explicit license warning

- Repository: `toeverything/OctoBase`
- Repository license metadata reviewed: AGPL-3.0
- Accessed: 2026-09-20

Disposition:

**REJECT as an implicit dependency of the Apache-2.0 core.**

Any future use would require a separate legal/architecture decision. AFFiNE-related investigation must not accidentally pull OctoBase into the core dependency graph.

## HL7 FHIR R4 — interoperability and provenance reference

Primary R4 references reviewed:

- https://hl7.org/fhir/R4/provenance.html
- https://hl7.org/fhir/R4/auditevent-definitions.html
- https://hl7.org/fhir/R4/security-labels.html

Architecture lessons:

- `Provenance` represents entities/processes/agents involved in producing a target;
- `AuditEvent` is a security/audit event record rather than the same concept as provenance;
- security labels participate in broader access-control/handling policy.

Disposition:

**ADOPT as standards semantics where applicable.**

FHIR semantics do not by themselves establish HIPAA compliance, patient safety, access policy, or clinical correctness.

## Capability-to-source summary

| MedScale target | External lesson | Disposition |
|---|---|---|
| Before/during/after encounter flow | Abridge | BUILD MedScale-owned |
| Ambient transcript -> source-linked draft | Abridge | BUILD MedScale-owned |
| Draft orders/actions behind human confirmation | Abridge | BUILD MedScale-owned |
| Context-aware evidence | Abridge / OpenEvidence | BUILD MedScale-owned |
| Literature search with explicit source corpus | OpenEvidence | BUILD MedScale-owned |
| Evidence quality metadata | Evidence products + Research Core principles | BUILD with transparent method |
| Local clinical NER | OpenMed | ADAPT candidate |
| Local PII/de-identification | OpenMed | ADAPT candidate in Workspace only |
| Local/offline execution | OpenMed / AFFiNE | ADOPT principle |
| Patient graph explainability | Graphify | ADOPT principle / ADAPT selectively |
| Docs + canvas + tables | AFFiNE | STUDY / build bounded Workspace surface |
| FHIR provenance/audit/security semantics | HL7 FHIR R4 | ADOPT standard semantics |

## Claims explicitly not established by this source refresh

This review does **not** establish:

- Abridge, OpenEvidence, OpenMed, Graphify, or AFFiNE clinical superiority;
- medical-device fitness;
- HIPAA or other regulatory compliance for MedScale;
- clinical safety;
- accuracy parity;
- performance parity;
- model/dataset redistribution rights beyond reviewed repository source licenses;
- authority to ingest PHI;
- authority to use external services;
- authority to train or evaluate on Workspace data.

Those require their own executable or legal/governance evidence.

## Refresh rule

Before any implementation task copies or adapts an external source:

1. resolve an immutable source revision;
2. inspect the exact source path;
3. record the applicable license;
4. record required NOTICE/attribution;
5. confirm dependency-license compatibility;
6. copy only the required bounded component;
7. record local changes;
8. add tests proving MedScale behavior independently;
9. never import a donor's performance claim as MedScale evidence.
