# Public Repository Alignment — Plan

## Current verified baseline

- ALIGN-19 authorization base: `1f27f4128229f1c3c973355c5a14bcac2cec0dfe` (PR #341 / ALIGN-18 merge).
- Canonical repository: `TheHalfMoon/MESC` on `main`.
- Package version: `0.2.0`.
- Existing release tag: `v0.2.0` → commit `d2e651a55c92f2218aca49acaa5b7bd18a75f096`.
- Human-readable alignment status never outranks canonical specifications, accepted governance, exact-head verification, or evidence-dependent gates.

## Historical completed sequence

### Phase 0 — Truth capture

Completed: divergence/public API/version/doc-index audits and initial PR sequencing were captured.

### Phase 1 — Repository formatting and typing hygiene

Completed as `Not Applicable / NO-GO` after audit found no behavior-preserving hygiene-only candidate. No empty PR was created.

### Phase 2 — Evidence/dataset foundations

Completed through ALIGN-12/13/14 and their merged implementation/governance records.

### Phase 3 — Evaluation boundary

Completed through ALIGN-15. Historical decisions remain recorded in their own specifications/ADRs; later code growth does not rewrite those old review records.

### Phase 4 — Model runtime/governance boundary

Completed through ALIGN-16 and ALIGN-17, including ADR-0033 history. Those documents are historical decision records, not a frozen description of every capability that later entered the repository.

### Phase 4.5 — Public repository identity

- ALIGN-18: **complete**.
- Issue: #340.
- PR: #341.
- Merge: `1f27f4128229f1c3c973355c5a14bcac2cec0dfe`.
- Result: live repository URLs, CODEOWNERS identity, ADR index, and active canonical-source/public-origin statements reconciled to `TheHalfMoon/MESC`.

## Phase 5 — Public documentation truth sync

- Status: **in progress under ALIGN-19 / issue #342**.
- Authorization base: `1f27f4128229f1c3c973355c5a14bcac2cec0dfe`.
- Scope: documentation/status reconciliation only.

### Audit result

`CHANGELOG.md` and `CITATION.cff` were inspected and require no Phase 5 mutation. The exact implementation allowlist is therefore limited to the nine files named in issue #342.

### Required Phase 5 outcomes

1. README status distinguishes implemented capability from research-phase completion and removes any present-tense claim that FHIR grammar-constrained generation is already a release capability.
2. ROADMAP distinguishes legacy T-phase objectives from current granular governance and records `fhirkit` validation / benchmark surfaces as implemented-but-not-equivalent-to-phase-complete.
3. RELEASES records the existing v0.2.0 tag truth and no longer claims release workflow/coverage are absent.
4. Execution/release/ecosystem docs reflect the actual current repository surfaces without manufacturing execution or publication authority.
5. This spec/plan/task ledger records ALIGN-18 complete and ALIGN-19 as the only active alignment ticket.
6. Exact-head CI, CodeQL, substantive independent semantic review, and review-thread reconciliation pass before guarded merge.

Phase 5 is not complete until ALIGN-19 merges and post-merge truth is verified.

## Phase 6 — Executable golden path

- Status: **not authorized / not started**.
- Opens only after Phase 5 canonical completion under a new ticket.
- Intended bounded goal: deterministic offline fixture-only smoke path proving a truthful end-to-end research artifact flow without external data, model download, GPU, credentials, or fabricated result evidence.
- Exact command, files, expected output, and acceptance evidence must be defined by the successor ticket before implementation.

## Phase 7 — CI, packaging, contributor hardening

- Status: **partially implemented; remaining work not yet authorized by ALIGN-19**.

| Planned item | Current audit status |
|---|---|
| Pin GitHub Actions SHAs | ✅ implemented in current audited workflows |
| Coverage enforcement | ✅ implemented (`pytest --cov`; configured floor) |
| Build wheel/sdist | ✅ implemented |
| PR-safe artifact upload/download byte-identity qualification | ✅ implemented in `release.yml` |
| Clean installed-wheel + `medscale --version` smoke | ⬜ remaining hardening candidate |
| TestPyPI dry-run/trusted-publishing qualification | ⬜ remaining; must be OIDC/environment-gated and separately authorized |
| CODEOWNERS | ✅ implemented |
| Issue/PR templates | ✅ implemented |

A future Phase 7 ticket must target only the remaining verified gaps; it must not reimplement completed controls merely because this historical plan once listed them as pending.

## ALIGN-10 — Final publication recommendation

- Status: **pending**.
- ALIGN-10 is a GO/NO-GO evidence synthesis, not automatic publication authority.
- Do not tag, release, publish to PyPI/TestPyPI/Hugging Face, or claim publication readiness until all required predecessor work is canonically complete and the recommendation is supported by exact evidence.

## Release boundary

Documentation alignment, release automation, package build capability, an existing historical tag, and passing CI are distinct facts. None of them alone authorizes a new tag, external publication, model promotion, training run, dataset publication, or deployment.

## Deliverables

- `specs/public-repository-alignment/spec.md`
- `specs/public-repository-alignment/plan.md`
- `specs/public-repository-alignment/tasks.md`
- Scoped issues/PRs with exact allowlists and exact-head qualification evidence
- Final ALIGN-10 GO/NO-GO report only after its predecessors are complete
