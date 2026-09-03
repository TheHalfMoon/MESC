# Public Repository Alignment — Plan

## Current verified baseline

- ALIGN-22 authorization base: `5e8ee576ff51301ac94eb4876e11d777120b193d` (PR #347 / ALIGN-21 merge).
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

- Status: **complete through ALIGN-20**.
- Issue: #344.
- PR: #345.
- Merge: `3a632457d92bfd98075b6dc082324a9f92a89d97`.
- Result: `medscale mesc-fixture-smoke` provides a deterministic offline fixture-only non-evidence path over the canonical MRL fixture contracts, with exact-head CI/CodeQL and independent semantic review completed before guarded merge.

## Phase 7 — CI, packaging, contributor hardening

### Package/release qualification

- Status: **complete through ALIGN-21**.
- Issue: #346.
- PR: #347.
- Merge: `5e8ee576ff51301ac94eb4876e11d777120b193d`.
- Result: the SHA-pinned release workflow reuses its exact built wheel for clean-install qualification, proves installed metadata/CLI consistency, and binds the tag path generically to `v<installed-version>` before GitHub Release creation without creating publication authority.

| Planned item | Current audit status |
|---|---|
| Pin GitHub Actions SHAs | ✅ implemented in current audited workflows |
| Coverage enforcement | ✅ implemented (`pytest --cov`; configured floor) |
| Build wheel/sdist | ✅ implemented |
| PR-safe artifact upload/download byte-identity qualification | ✅ implemented in `release.yml` |
| Clean installed-wheel + `medscale --version` smoke | ✅ implemented and canonical through ALIGN-21 |
| TestPyPI dry-run/trusted-publishing qualification | ⬜ remaining; OIDC/environment/external publisher authority remains separately gated |
| CODEOWNERS | ✅ implemented |
| Issue/PR templates | ✅ implemented |

### Documentation source readiness — ALIGN-22

- Status: **in progress under ALIGN-22 / issue #348**.
- Authorization base: `5e8ee576ff51301ac94eb4876e11d777120b193d`.
- Exact implementation allowlist: the paths recorded in #348, unless the issue is explicitly refined first for an evidence-discovered broken-link repair.

Required outcomes:

1. Add a deterministic Python-stdlib link checker over public root Markdown plus `docs/**/*.md`.
2. Validate repository-local inline links, images, reference-definition targets, and Markdown fragments without network access.
3. Reject missing paths, repository-root escapes, and missing Markdown anchors; support deterministic duplicate-heading anchors and explicit HTML ids.
4. Ignore external URI schemes and fenced-code examples rather than converting documentation examples into live dependencies.
5. Add focused tests and execute the checker inside the existing required CI quality jobs with no dependency, lockfile, permission, or third-party Action addition.
6. Record source/link readiness truth without claiming a hosted documentation site, renderer, deployment, DNS/domain route, or publication authority.
7. Require exact-head full CI/CodeQL, focused tests, repository-wide source check, independent substantive semantic review, diff-check verification, and resolved review threads before guarded merge.

After ALIGN-22, re-audit only the remaining verified gaps. A hosted renderer/deployment provider, if a concrete consumer justifies one, and TestPyPI trusted-publishing qualification remain separate scopes and must not be silently bundled into source readiness.

## ALIGN-10 — Final publication recommendation

- Status: **pending**.
- ALIGN-10 is a GO/NO-GO evidence synthesis, not automatic publication authority.
- Do not tag, release, publish to PyPI/TestPyPI/Hugging Face, or claim publication readiness until all required predecessor work is canonically complete and the recommendation is supported by exact evidence.

## Release boundary

Documentation alignment, release automation, package build capability, an existing historical tag, fixture-only plumbing qualification, clean-wheel/version-binding qualification, documentation-source qualification, and passing CI are distinct facts. None of them alone authorizes a new tag, external publication, model promotion, training run, dataset publication, hosted documentation deployment, or product deployment.

## Deliverables

- `specs/public-repository-alignment/spec.md`
- `specs/public-repository-alignment/plan.md`
- `specs/public-repository-alignment/tasks.md`
- Scoped issues/PRs with exact allowlists and exact-head qualification evidence
- Final ALIGN-10 GO/NO-GO report only after its predecessors are complete
