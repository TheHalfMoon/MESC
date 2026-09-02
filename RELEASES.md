# MedScale v0.2.0 Release Notes

**Release date:** 2026-07-13  
**Tag:** `v0.2.0` (existing annotated tag)  
**Tagged commit:** `d2e651a55c92f2218aca49acaa5b7bd18a75f096`  
**Python:** 3.11, 3.12  
**Historical release qualification:** ruff PASS · mypy PASS · pytest 340/340 PASS

These notes describe the v0.2.0 release baseline. Later repository hardening is not retroactively presented as evidence that it ran on the tag.

## Highlights

- Complete v0.2 milestone set: M1 release engineering, M2 evidence infrastructure, M3 benchmark framework, Dataset v1, S0 stabilization, M4 optional backends, M5 FHIR boundary, and M6 collaboration workflow.
- Deterministic, content-addressed, local-first research intelligence platform with architecture-enforced boundaries.
- Optional backends (`transformers`, `llama.cpp`) isolated behind extras and dedicated qualification.
- FHIR boundary frozen to deterministic `ValidationReport` contracts with optional local validator integration.
- Multi-reviewer collaboration workflow with append-only logs, deterministic merge, conflict visibility, and PRISMA replay.

## New capabilities

### Release engineering

- Structured logging, release workflow, coverage enforcement, storage hygiene checks, and architecture enforcement.

### Evidence infrastructure

- `medscale.evidence` subpackage with frozen models, grading, protocol, and backward-compatible shim.
- Evidence store and checks packages isolated from `litdb`.

### Benchmarks

- Deterministic benchmark spec, task contract, frozen scorers, and artifact-first replay.
- Five frozen run identities: `spec_id`, `snapshot_id`, `software_version`, `git_sha`, `scorer_version`.

### Dataset v1

- Deterministic manifest, schema, and seed-42 content-hash split.
- Sibling `.sha256` checksums and metadata/license enforcement.

### FHIR boundary

- `medscale.fhirkit` package with `ValidationReport`, deterministic serialization, and content-addressed storage.
- Optional local validator boundary with explicit install guidance when the dependency is unavailable.

### Collaboration workflow

- Reviewer-scoped append-only JSONL logs with hash chaining.
- Deterministic merge by timestamp ordering with conflict visibility.
- PRISMA reproducibility from merged reviewer logs.

## Quality at the v0.2.0 baseline

- 340 deterministic tests.
- Ruff, strict Mypy, Pytest, and coverage green in the release qualification recorded for the baseline.
- Optional extras isolated.
- Architecture tests enforce dependency boundaries.

## Current repository release automation

The repository now contains `.github/workflows/release.yml`. On a `v*` tag push it runs a quality gate, builds wheel/sdist artifacts, and can create a GitHub Release from those artifacts. On pull requests that modify the workflow it also performs a PR-safe build/upload/download byte-identity qualification. All referenced third-party Actions in that workflow are SHA-pinned.

The current CI configuration also enforces a coverage floor. These are current repository facts; this section does not claim that every later workflow revision ran against the historical v0.2.0 tag.

## Known limitations of the v0.2.0 release baseline

- ADR-0023, ADR-0024, and ADR-0025 formal registry entries were deferred at the release baseline.
- `Snapshot` alias was not declared in `workspace.py` `__all__` at the release baseline (TD-001).
- The adapter layer used `urllib` for live retrieval; core paths remained offline-only.
- A `v0.2.0` tag exists, but this document does not claim a GitHub Release object was retroactively created for it.

## Tag status

`v0.2.0` already exists. Do not recreate, move, or replace the tag as part of documentation reconciliation.
