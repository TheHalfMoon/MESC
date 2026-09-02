# Public Repository Alignment — Plan

## Current verified baseline

- ALIGN-20 authorization base: `a5df6403e9087f1c63f95eccbad9d0e2b61a96e1` (PR #343 / ALIGN-19 merge).
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

- Status: **complete through ALIGN-19**.
- Issue: #342.
- PR: #343.
- Merge: `a5df6403e9087f1c63f95eccbad9d0e2b61a96e1`.
- Result: README/ROADMAP/release/execution/ecosystem/alignment-control status reconciled without creating model, training, publication, deployment, or clinical authority.

`CHANGELOG.md` and `CITATION.cff` were inspected during Phase 5 and intentionally excluded from its implementation allowlist because no Phase 5 mutation was required.

## Phase 6 — Executable golden path

- Status: **in progress under ALIGN-20 / issue #344**.
- Authorization base: `a5df6403e9087f1c63f95eccbad9d0e2b61a96e1`.
- Exact implementation allowlist: the eight files recorded in #344.

### Required Phase 6 outcomes

1. Add `medscale mesc-fixture-smoke` as an additive research command without changing existing CLI-stable command semantics.
2. Reuse the existing canonical MRL `complete_fixture_loop()` contracts instead of introducing a parallel evaluator/receipt/decision engine.
3. Run one fixed in-memory non-perfect fixture candidate that deterministically produces `REJECT`.
4. Emit canonical JSON content identities for the proposal, observation, receipt, decision, and loop result with explicit fixture-only/non-evidence and false authority flags.
5. Prove byte-identical repeated stdout and no filesystem writes in focused tests.
6. Keep the path offline: no external data, network, model/tokenizer download, inference, GPU/provider, credentials, training, campaign-state mutation, promotion, release, deployment, or clinical action.
7. Document that this path qualifies repository plumbing only and is not research evidence or real-experiment readiness.
8. Require exact-head Ruff/Mypy/full CI/CodeQL, substantive independent semantic review, diff-check verification, and resolved review threads before guarded merge.

Phase 6 is not complete until ALIGN-20 merges and post-merge truth is verified.

## Phase 7 — CI, packaging, contributor hardening

- Status: **partially implemented; remaining work not yet authorized by ALIGN-20**.

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

Documentation alignment, release automation, package build capability, an existing historical tag, fixture-only plumbing qualification, and passing CI are distinct facts. None of them alone authorizes a new tag, external publication, model promotion, training run, dataset publication, or deployment.

## Deliverables

- `specs/public-repository-alignment/spec.md`
- `specs/public-repository-alignment/plan.md`
- `specs/public-repository-alignment/tasks.md`
- Scoped issues/PRs with exact allowlists and exact-head qualification evidence
- Final ALIGN-10 GO/NO-GO report only after its predecessors are complete
