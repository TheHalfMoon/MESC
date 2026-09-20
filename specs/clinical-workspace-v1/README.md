# Clinical Workspace Reconciliation V1

- **Status:** Planning only
- **Issue:** #459
- **Proposed ADR:** [ADR-0038](../../docs/adr/0038-local-clinical-workspace-boundary.md)
- **Planning base:** `475a389777c02a1992acafa24b1cfd1dae24c46b`

## Goal

Make the expanded MedScale vision implementation-ready without weakening the existing research core, MRL evidence model, no-PHI research boundary, reproducibility contracts, or authority separation.

## Capability families

1. local medical scribe;
2. cited evidence/research assistance;
3. encounter/document workspace;
4. patient/data graph projection;
5. analytics workspace;
6. research workspace;
7. dataset workspace;
8. FHIR/EHR and database connector boundaries;
9. local privacy, encryption, audit, backup, deletion, migration, and export controls;
10. capability-scoped extensions/plugins.

## Proposed topology

```text
src/medscale/
  existing research namespaces
  workspace/
    contracts/
    local_store/
    identity/
    encounters/
    scribe/
    evidence/
    graph/
    analytics/
    research/
    datasets/
    connectors/
    export/
    audit/
```

This is planning only; no module is authorized by being named here.

## Scribe flow

```text
synthetic/local audio fixture
  -> capture contract
  -> transcription adapter
  -> timestamp/speaker provenance
  -> draft note transform
  -> review state
  -> local export
```

Required behavior:
- no silent network fallback;
- unsupported audio/device fails explicitly;
- confidence/uncertainty is retained;
- output remains draft;
- audio retention is explicit;
- no research/training admission.

## Evidence flow

```text
question
  -> retrieval plan
  -> source snapshots
  -> evidence objects
  -> cited synthesis
  -> uncertainty/coverage report
  -> workspace artifact
```

Generated text cannot be relabeled as source evidence.

## Graph contract

Graph state is a deterministic derived projection over stable identifiers. Every edge/node retains source identity. The graph is rebuildable and never the canonical owner of research evidence.

## Dataset contract

Workspace dataset operations are distinct from governed training-dataset admission. Viewing, labeling, filtering, or versioning a local dataset does not grant training or evaluation authority.

## Security freeze requirements

Before implementation:
- local encryption at rest;
- key ownership/recovery;
- process isolation;
- workspace lock/session behavior;
- audit integrity;
- deletion including backups;
- audio/attachment handling;
- file import validation;
- connector credential storage;
- retrieved-content prompt-injection controls;
- export policy;
- plugin permissions;
- migration rollback;
- crash-consistent storage;
- corruption recovery;
- synthetic adversarial fixtures.

## Acceptance template for every capability

Each slice must define:
- user outcome;
- trusted inputs;
- produced artifacts;
- source-of-truth owner;
- sensitivity class;
- offline behavior;
- network behavior;
- failure semantics;
- synthetic tests;
- security tests;
- migration contract;
- observability without payload leakage;
- rollback;
- authority required for real-world activation.

## Governance

This package does not change MRL-0809/MRL-0899, corpus/Tier-3 access, training, model policy, publication, release, paid compute, or clinical authority.

## Exit

Planning V1 is ready for implementation only when ADR-0038, source register, threat/data-flow model, conflict map, and task ledger are independently reviewed and canonically qualified.
