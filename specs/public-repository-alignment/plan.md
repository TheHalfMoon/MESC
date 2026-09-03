# Public Repository Alignment — Plan

## Current verified baseline

- ALIGN-24 authorization base: `8a6c3bf6f51b2e6f72fcdc3ce3c14dfc5f1b4f5c` (PR #352 / ALIGN-23 merge).
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
- Result: required CI checks public repository Markdown links/anchors deterministically without network access or hosted-documentation authority.

The post-ALIGN-22 audit found no concrete hosted-documentation consumer/provider. A hosting/deployment unit is therefore **not currently justified**; this is a deliberate no-op avoidance decision, not a claim that a hosted site exists.

### Release/version governance

- Status: **complete through ALIGN-23**.
- Issue: #351.
- PR: #352.
- Merge: `8a6c3bf6f51b2e6f72fcdc3ce3c14dfc5f1b4f5c`.
- Result: ADR-0010/ADR-0011 and current release/version/licensing policy were reconciled and accepted without creating external publication authority.

| Planned item | Current audit status |
|---|---|
| Pin GitHub Actions SHAs | ✅ implemented in current audited workflows |
| Coverage enforcement | ✅ implemented (`pytest --cov`; configured floor) |
| Documentation source/link hygiene | ✅ implemented through ALIGN-22 |
| Build wheel/sdist | ✅ implemented |
| PR-safe artifact upload/download byte-identity qualification | ✅ implemented in `release.yml` |
| Clean installed-wheel + `medscale --version` smoke | ✅ implemented and canonical through ALIGN-21 |
| Release/version/licensing governance | ✅ reconciled and accepted through ALIGN-23 |
| TestPyPI Trusted Publishing repository path | 🔄 ALIGN-24 active under issue #353; fail-closed implementation + PR qualification in progress |
| TestPyPI external activation | ⏸ not verified by repository tooling; protected Environment + matching Trusted Publisher + operator enable decision required |
| Production PyPI publication | ⬜ not implemented; separate future authority required if pursued |
| CODEOWNERS | ✅ implemented |
| Issue/PR templates | ✅ implemented |
| Hosted documentation deployment | ⏸ not currently justified; requires a concrete consumer/provider |

### Fail-closed TestPyPI qualification — ALIGN-24

- Status: **in progress under issue #353**.
- Authorization base: `8a6c3bf6f51b2e6f72fcdc3ce3c14dfc5f1b4f5c`.
- Goal: implement and machine-qualify a TestPyPI Trusted Publishing repository path that remains disabled until separately evidenced external trust/protection exists.
- The distribution edge must follow successful GitHub Release creation, reuse the exact same-run qualified artifact, perform no rebuild, use job-local OIDC permission, reference the governed `testpypi` Environment, use the SHA-pinned official PyPA publisher, and require an explicit `TESTPYPI_PUBLISH_ENABLED == 'true'` guard.
- Required repository tests must fail closed if the workflow contract drifts and PR qualification must perform no upload or OIDC publication.
- Repository implementation must not be presented as proof that the protected Environment or TestPyPI Trusted Publisher exists. External activation remains separately evidence-dependent.
- ALIGN-24 does not set the enable variable, create a tag/GitHub Release, upload to TestPyPI, or implement production PyPI.

After ALIGN-24, re-audit the repository-readiness state and execute ALIGN-10 as the final evidence synthesis. If TestPyPI external trust/environment evidence remains unavailable, ALIGN-10 must carry that fact into its GO/NO-GO recommendation rather than manufacturing publication readiness.

## ALIGN-10 — Final publication recommendation

- Status: **pending after ALIGN-24**.
- ALIGN-10 is a GO/NO-GO evidence synthesis, not automatic publication authority.
- It must distinguish repository implementation/qualification from external activation and from scientific evidence readiness.
- Do not tag, release, publish to PyPI/TestPyPI/Hugging Face, or claim publication readiness unless the exact applicable evidence supports that conclusion.

## Release boundary

Documentation alignment, release automation, package build capability, an existing historical tag, fixture-only plumbing qualification, clean-wheel/version-binding qualification, documentation-source qualification, accepted governance, a fail-closed TestPyPI repository path, and passing CI are distinct facts. None of them alone authorizes a new tag, external publication, model promotion, training run, dataset publication, hosted documentation deployment, or product deployment.

## Deliverables

- `specs/public-repository-alignment/spec.md`
- `specs/public-repository-alignment/plan.md`
- `specs/public-repository-alignment/tasks.md`
- Scoped issues/PRs with exact allowlists and exact-head qualification evidence
- Final ALIGN-10 GO/NO-GO report only after its predecessors are complete
