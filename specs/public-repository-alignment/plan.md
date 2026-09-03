# Public Repository Alignment — Plan

## Current verified baseline

- ALIGN-23 authorization base: `02b4ad0956aef613a792a1de853d31b4e1c41fda` (PR #349 / ALIGN-22 merge).
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

### Documentation source readiness

- Status: **complete through ALIGN-22**.
- Issue: #348.
- PR: #349.
- Merge: `02b4ad0956aef613a792a1de853d31b4e1c41fda`.
- Result: required CI now checks public repository Markdown links/anchors deterministically without network access or hosted-documentation authority.

The post-ALIGN-22 audit found no concrete hosted-documentation consumer/provider. A hosting/deployment unit is therefore **not currently justified**; this is a deliberate no-op avoidance decision, not a claim that a hosted site exists.

| Planned item | Current audit status |
|---|---|
| Pin GitHub Actions SHAs | ✅ implemented in current audited workflows |
| Coverage enforcement | ✅ implemented (`pytest --cov`; configured floor) |
| Documentation source/link hygiene | ✅ implemented through ALIGN-22 |
| Build wheel/sdist | ✅ implemented |
| PR-safe artifact upload/download byte-identity qualification | ✅ implemented in `release.yml` |
| Clean installed-wheel + `medscale --version` smoke | ✅ implemented and canonical through ALIGN-21 |
| Release/version/licensing governance | 🔄 ALIGN-23 active: reconcile and accept ADR-0010/0011 against current truth |
| TestPyPI trusted-publishing qualification | ⬜ remaining after ALIGN-23; OIDC/environment/external publisher authority separately gated |
| CODEOWNERS | ✅ implemented |
| Issue/PR templates | ✅ implemented |
| Hosted documentation deployment | ⏸ not currently justified; requires a concrete consumer/provider |

### Release/version governance — ALIGN-23

- Status: **in progress under issue #351**.
- Authorization base: `02b4ad0956aef613a792a1de853d31b4e1c41fda`.
- Goal: reconcile ADR-0010/ADR-0011 and the current release/versioning/licensing docs to canonical implemented truth before recording acceptance.
- Acceptance must not convert current package/GitHub-Release automation into TestPyPI/PyPI/Hugging Face publication authority.
- Historical execution/audit records remain historical and are not rewritten merely because current governance is accepted later.

After ALIGN-23, re-audit the remaining verified gap. The currently evidenced package-distribution successor is TestPyPI trusted-publishing qualification, which must remain separately scoped and must use exact artifact reuse, OIDC trusted publishing, least privilege, an explicitly gated environment, and independently verified no-publication-by-qualification semantics.

## ALIGN-10 — Final publication recommendation

- Status: **pending**.
- ALIGN-10 is a GO/NO-GO evidence synthesis, not automatic publication authority.
- Do not tag, release, publish to PyPI/TestPyPI/Hugging Face, or claim publication readiness until all required predecessor work is canonically complete and the recommendation is supported by exact evidence.

## Release boundary

Documentation alignment, release automation, package build capability, an existing historical tag, fixture-only plumbing qualification, clean-wheel/version-binding qualification, documentation-source qualification, accepted governance, and passing CI are distinct facts. None of them alone authorizes a new tag, external publication, model promotion, training run, dataset publication, hosted documentation deployment, or product deployment.

## Deliverables

- `specs/public-repository-alignment/spec.md`
- `specs/public-repository-alignment/plan.md`
- `specs/public-repository-alignment/tasks.md`
- Scoped issues/PRs with exact allowlists and exact-head qualification evidence
- Final ALIGN-10 GO/NO-GO report only after its predecessors are complete
