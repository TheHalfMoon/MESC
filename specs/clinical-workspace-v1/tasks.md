# Clinical Workspace V1 — Planning Task Ledger

- **Status:** Planning only
- **Parent:** #459

A checkbox records planning progress only. It never grants PHI, clinical, runtime, training, release, or publication authority.

## P0 — Architecture and governance

- [ ] **CW-001 — Canonical capability inventory**
  - Inventory reusable research APIs, storage, FHIR, evidence, dataset, benchmark, identity, and extension surfaces.
  - Acceptance: no duplicate subsystem without a documented gap.

- [ ] **CW-002 — Source refresh**
  - Revalidate every source in `SOURCE_REGISTER.md` at current primary/immutable references.
  - Acceptance: factual capability/license claims bind evidence and revision/date.

- [ ] **CW-003 — ADR/spec conflict map**
  - Reconcile ADR-0003, 0005, 0007, 0008, 0012, 0015, 0020, 0033, 0035, 0036, 0038 plus affected specs.

- [ ] **CW-004 — Trust-zone data-flow model**
  - Freeze Zones R/W/X/P and all allowed/prohibited edges.
  - Acceptance: no workspace-sensitive-data path into research/training/evaluation without a separately governed admission gate.

- [ ] **CW-005 — Threat model**
  - Cover stolen device, malicious attachment, prompt injection, connector/plugin abuse, exfiltration, backup leakage, key loss, audit tampering, unsafe export, and model-output injection.

## P1 — Core workspace contracts

- [ ] **CW-010 — Identity/tenancy/session contract**
- [ ] **CW-011 — Local storage/encryption/key/backup/deletion contract**
- [ ] **CW-012 — Append-only audit/event contract**
- [ ] **CW-013 — Attachment/audio lifecycle contract**
- [ ] **CW-014 — Least-privilege connector capability contract**
- [ ] **CW-015 — Sensitivity-aware export contract**

Dependencies: CW-004/005 before CW-010..015; CW-010 before persistence/audit authorization.

## P2 — User outcome slices

- [ ] **CW-020 — Synthetic local scribe vertical slice**
  - synthetic audio -> transcript -> draft note -> review -> local export.

- [ ] **CW-021 — Cited evidence answer vertical slice**
  - query -> source snapshots -> evidence objects -> synthesis -> uncertainty report.

- [ ] **CW-022 — Encounter/document workspace**
- [ ] **CW-023 — Deterministic graph projection**
- [ ] **CW-024 — Analytics workspace**
- [ ] **CW-025 — Research workspace**
- [ ] **CW-026 — Dataset workspace distinct from training admission**

## P3 — Interoperability and extension

- [ ] **CW-030 — FHIR import/export boundary**
- [ ] **CW-031 — Local database connector**
- [ ] **CW-032 — Plugin/extension sandbox**
- [ ] **CW-033 — Optional sync architecture (planning only)**

## P4 — Product integrity

- [ ] **CW-040 — Migration/versioning/rollback**
- [ ] **CW-041 — Resource/performance budgets**
- [ ] **CW-042 — Accessibility, RTL, Arabic/English and Unicode-safe offsets**
- [ ] **CW-043 — Recovery drills**
- [ ] **CW-044 — Privacy/security qualification**

## P5 — Planning closeout

- [ ] **CW-050 — Independent architecture review**
- [ ] **CW-051 — Exact-head CI/CodeQL/docs qualification**
- [ ] **CW-052 — Protected normal merge**
- [ ] **CW-053 — Fresh-main qualification**
- [ ] **CW-054 — Split separately authorized implementation specs**

## Global stop conditions

Stop if work would:
- move PHI into research;
- weaken MRL/scientific evidence;
- require hidden network access for local-first core behavior;
- silently promote workspace data into training/evaluation;
- leak secrets;
- weaken branch protection;
- create unqualified clinical/device claims;
- consume paid compute without explicit authority.
