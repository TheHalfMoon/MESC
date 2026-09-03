# Public Repository Alignment — Plan

## Current verified baseline

- ALIGN-21 authorization base: `3a632457d92bfd98075b6dc082324a9f92a89d97` (PR #345 / ALIGN-20 merge).
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

- Status: **in progress under ALIGN-21 / issue #346**.
- Authorization base: `3a632457d92bfd98075b6dc082324a9f92a89d97`.
- Exact implementation allowlist: the six files recorded in #346.

| Planned item | Current audit status |
|---|---|
| Pin GitHub Actions SHAs | ✅ implemented in current audited workflows |
| Coverage enforcement | ✅ implemented (`pytest --cov`; configured floor) |
| Build wheel/sdist | ✅ implemented |
| PR-safe artifact upload/download byte-identity qualification | ✅ implemented in `release.yml` |
| Clean installed-wheel + `medscale --version` smoke | ⏳ active under ALIGN-21; must qualify the exact built wheel without source checkout and bind installed metadata to CLI/tag version |
| TestPyPI dry-run/trusted-publishing qualification | ⬜ remaining; must be OIDC/environment-gated and separately authorized |
| CODEOWNERS | ✅ implemented |
| Issue/PR templates | ✅ implemented |

### Required ALIGN-21 outcomes

1. Reuse the exact built wheel for install qualification; do not rebuild a second candidate.
2. Add a PR-safe clean Python 3.11 environment that does not check out repository source, installs the downloaded wheel with `--no-deps`, derives its installed version from `importlib.metadata`, requires the CLI to report that version, and for the current candidate requires `0.2.0`.
3. Add the equivalent tag-path gate, derive the installed wheel version, require the CLI to match it, require the `vX.Y.Z` tag to equal `v<installed-version>`, and require that gate before the existing GitHub Release job. The tag path must remain future-version capable rather than hard-coded to `0.2.0`.
4. Preserve SHA-pinned third-party Actions and least-privilege permissions.
5. Keep publication, trusted publishing, versioning mutations, model/data execution, and deployment out of scope.
6. Require exact-head full CI/CodeQL, release-workflow PR-safe build/roundtrip/install qualification, independent substantive semantic review, diff-check verification, and resolved review threads before guarded merge.

After ALIGN-21, re-audit only the remaining verified gaps. TestPyPI trusted publishing and hosted-doc/link-hygiene readiness remain separately scoped; they must not be bundled into this unit.

## ALIGN-10 — Final publication recommendation

- Status: **pending**.
- ALIGN-10 is a GO/NO-GO evidence synthesis, not automatic publication authority.
- Do not tag, release, publish to PyPI/TestPyPI/Hugging Face, or claim publication readiness until all required predecessor work is canonically complete and the recommendation is supported by exact evidence.

## Release boundary

Documentation alignment, release automation, package build capability, an existing historical tag, fixture-only plumbing qualification, clean-wheel/version-binding qualification, and passing CI are distinct facts. None of them alone authorizes a new tag, external publication, model promotion, training run, dataset publication, or deployment.

## Deliverables

- `specs/public-repository-alignment/spec.md`
- `specs/public-repository-alignment/plan.md`
- `specs/public-repository-alignment/tasks.md`
- Scoped issues/PRs with exact allowlists and exact-head qualification evidence
- Final ALIGN-10 GO/NO-GO report only after its predecessors are complete
