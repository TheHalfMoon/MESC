# Clinical Workspace V1 — Capability Map

- **Status:** Proposed planning artifact
- **Date:** 2026-09-20
- **Parent:** [Clinical Workspace V1](README.md)
- **Source evidence:** [2026-09-20 source refresh](../../docs/architecture/clinical_workspace_source_refresh_2026-09-20.md)

## Disposition vocabulary

- **BUILD** — implement a MedScale-owned capability after its task becomes authorized.
- **ADAPT** — bounded reuse of an external component is plausible after exact source/license/provenance review.
- **STUDY** — learn product/architecture patterns; no code reuse implied.
- **REJECT** — deliberately excluded from V1 or incompatible with current governance.
- **LATER** — valid future capability but not V1 critical path.

No disposition below is implementation authority.

## Capability matrix

| Capability | Reference lesson | MedScale disposition | V1 acceptance idea | Boundary |
|---|---|---|---|---|
| Pre-visit context summary | Abridge | BUILD | synthetic patient timeline produces source-linked summary | Workspace only |
| Ambient encounter capture | Abridge | BUILD | visible consented recording lifecycle, offline fixture | Workspace only |
| Medical ASR | Abridge/OpenMed ecosystem | BUILD adapter | local adapter, exact runtime identity, no silent cloud | Workspace only |
| Speaker segmentation | ambient workflow | LATER/BUILD if justified | bounded diarization with uncertainty | Workspace only |
| Live transcript | Abridge | BUILD | timestamped revisioned transcript | Workspace only |
| Source-linked note draft | Abridge Linked Evidence pattern | BUILD | every generated supported span links to source | Workspace only |
| Specialty templates | Abridge workflow pattern | BUILD | versioned templates, no hidden prompt drift | Workspace only |
| Draft orders/tasks | Abridge order-capture pattern | BUILD | draft only + explicit human confirmation | Workspace only |
| Coding suggestions | Abridge/OpenEvidence references | BUILD later | suggestion+rationale; never auto-submit | Workspace only |
| Patient summary draft | encounter workflow | BUILD | source-linked + review required | Workspace only |
| Natural-language evidence search | OpenEvidence | BUILD | query -> frozen retrieval snapshot -> sources | Workspace + Research primitives |
| Patient-context evidence query | OpenEvidence partner deployments | LATER | policy-controlled context; no unauthorized egress | Workspace only |
| Evidence citations | OpenEvidence/Abridge + Research Core | BUILD | source identity + claim-source links | shared interface |
| Evidence strength metadata | OpenEvidence-style workflow | BUILD | transparent method/version; UNKNOWN allowed | Workspace/Research |
| Contradiction detection | evidence workflow | BUILD | conflicting sources surfaced | Workspace/Research |
| Local clinical NER | OpenMed | ADAPT candidate | pinned artifact, offline deterministic baseline | Workspace adapter |
| PII detection | OpenMed | ADAPT candidate | synthetic privacy fixtures first | Workspace only |
| De-identification | OpenMed | ADAPT candidate | residual identifier tests; Domain X only | Export staging |
| Automatic research admission after de-id | none | REJECT | mechanical guard must block | R2 boundary |
| Local CPU/CUDA execution | OpenMed | STUDY/ADAPT | explicit backend identity | Workspace |
| Apple/mobile/browser local backends | OpenMed | LATER | platform-specific qualification | Workspace |
| REST service as default architecture | OpenMed | REJECT for core | no server required for local path | Workspace optional later |
| Persistent patient graph | Graphify | BUILD | source-derived graph rebuilds deterministically | Workspace |
| Explainable graph paths | Graphify | BUILD | path returns source refs + epistemic state | Workspace |
| EXTRACTED/INFERRED distinction | Graphify | BUILD principle | edge state mandatory | Workspace |
| Code graph semantics copied to patients | Graphify | REJECT | healthcare-owned schema required | Workspace |
| Docs + canvas | AFFiNE | STUDY/BUILD | local object blocks; healthcare semantics | Workspace |
| Tables/databases | AFFiNE | STUDY/BUILD | linked patient/research tables | Workspace |
| Realtime collaboration | AFFiNE | LATER | requires separate identity/sync threat model | Workspace |
| Cloud sync required for core | none | REJECT | local path fully usable offline | Workspace |
| Self-hosting | AFFiNE/OpenMed patterns | LATER/BUILD | no vendor account required for core | Workspace |
| FHIR R4 import/export | HL7/current MedScale | BUILD | bounded resources, validation stages | Integration |
| FHIR Provenance mapping | HL7 | BUILD | generated/exported objects map provenance | Integration |
| AuditEvent semantics | HL7 | BUILD principle | security audit separate from provenance | Workspace |
| Security labels | HL7 | BUILD principle | labels retained through import/export | Workspace |
| EHR read connector | product integrations | LATER after V1 core | read-only first | Integration |
| EHR write connector | product integrations | REJECT until separate authority | no V1 write | Integration |
| Local analytics | Founder scope | BUILD | operational metrics remain Workspace data | Workspace |
| Research artifact explorer | Founder scope/Research Core | BUILD | read-only Research Core UI | Workspace -> Research |
| Dataset management | Founder scope | BUILD | Research dataset vs export staging separated | both domains |
| Clinical export staging | privacy/data workflow | BUILD | explicit Domain X manifest | Domain X |
| Training from Workspace feedback | none | REJECT | no-backflow test | forbidden |
| Workspace telemetry into Research Core | none | REJECT | no-backflow test | forbidden |
| Autonomous diagnosis/treatment | none | REJECT | human review boundary | forbidden |

## End-to-end V1 journeys

### Journey A — Synthetic encounter

```text
synthetic patient
-> local encounter
-> fixture/local audio
-> transcript
-> source-linked draft note
-> clinician-style review fixture
-> FHIR preview
-> audit/provenance replay
```

Success requires no network, credentials, PHI, or MRL runtime.

### Journey B — Evidence question

```text
question
-> authorized/local corpus
-> retrieval snapshot
-> claim synthesis
-> source links
-> evidence metadata
-> contradiction/abstention
-> reproducible replay
```

### Journey C — Longitudinal patient view

```text
synthetic FHIR/history
-> normalized Workspace objects
-> patient timeline
-> provenance-labeled graph
-> explainable path/query
-> source drill-down
```

### Journey D — Dataset/export boundary

```text
Workspace selection
-> explicit export
-> optional de-identification
-> residual-risk checks
-> Domain X manifest
-> STOP
```

Research admission is a different later workflow.

## V1 definition of useful

A V1 can be useful without real PHI if a third party can reproduce these synthetic journeys locally and inspect:

- what the system saw;
- what it generated;
- what evidence supports it;
- what was inferred;
- what the human changed;
- what would be exported;
- what was blocked;
- what exact software/model/source identity produced the result.

## V1 exclusions

To keep V1 coherent:

- no real patient data;
- no production EHR writes;
- no autonomous orders;
- no billing submission;
- no cloud-required core;
- no model training from Workspace state;
- no collaboration/sync until identity/encryption model is separately reviewed;
- no attempt to copy every competitor feature before trust boundaries work.
