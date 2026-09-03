# Public Repository Alignment — Plan

## Final verified baseline

- Canonical repository: `TheHalfMoon/MESC` on `main`.
- ALIGN-10 authorization base: `b6f26b3dedce20e559b3936e9f85f962153e826e`
  (PR #354 / ALIGN-24 merge).
- ALIGN-10 issue: #355.
- Package version: `0.2.0`.
- Existing annotated tag: `v0.2.0` → commit
  `d2e651a55c92f2218aca49acaa5b7bd18a75f096`.
- Human-readable alignment status never outranks canonical specifications, accepted
  governance, exact-head verification, or evidence-dependent gates.

## Historical completed sequence

### Phase 0 — Truth capture

Completed: divergence/public API/version/doc-index audits and initial PR sequencing were
captured.

### Phase 1 — Repository formatting and typing hygiene

Completed as `Not Applicable / NO-GO` after audit found no behavior-preserving hygiene-only
candidate. No empty PR was created.

### Phase 2 — Evidence/dataset foundations

Completed through ALIGN-12/13/14 and their merged implementation/governance records.

### Phase 3 — Evaluation boundary

Completed through ALIGN-15. Historical decisions remain recorded in their own
specifications/ADRs; later code growth does not rewrite those old review records.

### Phase 4 — Model runtime/governance boundary

Completed through ALIGN-16 and ALIGN-17, including ADR-0033 history. Those documents are
historical decision records, not a frozen description of every capability that later entered
the repository.

### Phase 4.5 — Public repository identity

- ALIGN-18: **complete**.
- Issue: #340.
- PR: #341.
- Merge: `1f27f4128229f1c3c973355c5a14bcac2cec0dfe`.
- Result: live repository URLs, CODEOWNERS identity, ADR index, and active canonical-source/
  public-origin statements reconciled to `TheHalfMoon/MESC`.

## Phase 5 — Public documentation truth sync

- ALIGN-19: **complete**.
- Issue: #342.
- PR: #343.
- Merge: `a5df6403e9087f1c63f95eccbad9d0e2b61a96e1`.
- Result: README/ROADMAP/release/execution/ecosystem/alignment-control status reconciled
  without creating model, training, publication, deployment, or clinical authority.

`CHANGELOG.md` and `CITATION.cff` were inspected during Phase 5 and intentionally excluded
from its implementation allowlist because no Phase 5 mutation was required.

## Phase 6 — Executable golden path

- ALIGN-20: **complete**.
- Issue: #344.
- PR: #345.
- Merge: `3a632457d92bfd98075b6dc082324a9f92a89d97`.
- Result: `medscale mesc-fixture-smoke` provides a deterministic offline fixture-only
  non-evidence path over the canonical MRL fixture contracts, with exact-head CI/CodeQL and
  independent semantic review completed before guarded merge.

## Phase 7 — CI, packaging, contributor and distribution hardening

### Package/release qualification — ALIGN-21

- Status: **complete**.
- Issue: #346.
- PR: #347.
- Merge: `5e8ee576ff51301ac94eb4876e11d777120b193d`.
- Result: the SHA-pinned release workflow reuses its exact built wheel for clean-install
  qualification, proves installed metadata/CLI consistency, and binds the tag path
  generically to `v<installed-version>` before GitHub Release creation without creating
  publication authority.

### Documentation source readiness — ALIGN-22

- Status: **complete**.
- Issue: #348.
- PR: #349.
- Merge: `02b4ad0956aef613a792a1de853d31b4e1c41fda`.
- Result: required CI checks public repository Markdown links/anchors deterministically
  without network access or hosted-documentation authority.

The post-ALIGN-22 audit found no concrete hosted-documentation consumer/provider. A hosting/
deployment unit is therefore **not currently justified**; this is a deliberate no-op
avoidance decision, not a claim that a hosted site exists.

### Release/version governance — ALIGN-23

- Status: **complete**.
- Issue: #351.
- PR: #352.
- Merge: `8a6c3bf6f51b2e6f72fcdc3ce3c14dfc5f1b4f5c`.
- Result: ADR-0010/ADR-0011 and current release/version/licensing policy were reconciled and
  accepted without creating external publication authority.

### Fail-closed TestPyPI repository path — ALIGN-24

- Status: **complete**.
- Issue: #353.
- PR: #354.
- Merge: `b6f26b3dedce20e559b3936e9f85f962153e826e`.
- Merge tree: `f9766cbd6a3d4a79c6d08c8f9547b0b51adfbb75`, matching the exact qualified
  PR-head tree.
- Result: a disabled-by-default TestPyPI Trusted Publishing repository path is implemented
  and PR-qualified. It runs only for the governed tag path plus explicit enable variable,
  requires successful GitHub Release creation first, reuses the exact same-run qualified
  artifact, performs no checkout/rebuild, uses job-local OIDC permission, references the
  governed `testpypi` Environment name, and uses the SHA-pinned official PyPA publisher.
- External activation remains unverified. Repository code does not prove the protected
  Environment, matching TestPyPI Trusted Publisher, or explicit enable decision exists.

| Planned item | Final alignment audit status |
|---|---|
| Pin GitHub Actions SHAs | ✅ implemented in current audited workflows |
| Coverage enforcement | ✅ implemented (`pytest --cov`; configured floor) |
| Documentation source/link hygiene | ✅ implemented through ALIGN-22 |
| Build wheel/sdist | ✅ implemented |
| PR-safe artifact upload/download byte-identity qualification | ✅ implemented in `release.yml` |
| Clean installed-wheel + `medscale --version` smoke | ✅ implemented and canonical through ALIGN-21 |
| Release/version/licensing governance | ✅ reconciled and accepted through ALIGN-23 |
| TestPyPI Trusted Publishing repository path | ✅ implemented and PR-qualified through ALIGN-24; disabled by default |
| TestPyPI external activation | ⏸ **NO-GO / UNVERIFIED**; protected Environment + matching Trusted Publisher + explicit enable decision required |
| Production PyPI publication | ⛔ **NO-GO**; not implemented and not authorized by alignment |
| Hugging Face publication | ⛔ **NO-GO**; not implemented/qualified/authorized by alignment |
| CODEOWNERS | ✅ implemented |
| Issue/PR templates | ✅ implemented |
| Hosted documentation deployment | ⏸ **NO-GO / not currently justified**; requires a concrete consumer/provider |

## Phase 8 — Final evidence synthesis / ALIGN-10

- Status: **final closeout candidate under issue #355**.
- Authorization base: `b6f26b3dedce20e559b3936e9f85f962153e826e`.
- Deliverable:
  `specs/public-repository-alignment/final-publication-go-no-go.md`.
- ALIGN-10 is a GO/NO-GO evidence synthesis, not automatic publication authority.
- It distinguishes repository implementation/qualification from external activation,
  scientific evidence readiness, training, release, publication, promotion, deployment, and
  clinical authority.
- It does not tag, release, publish to PyPI/TestPyPI/Hugging Face, configure external
  publisher trust, execute a model/training run, admit scientific evidence, deploy hosted
  documentation, or create product/clinical authority.

The final recommendation is intentionally multi-axis:

```text
PUBLIC_REPOSITORY_ALIGNMENT = GO
REPOSITORY_READY_FOR_PUBLIC_SOURCE_COLLABORATION = GO
TESTPYPI_REPOSITORY_PATH = GO / DISABLED_BY_DEFAULT
TESTPYPI_EXTERNAL_ACTIVATION = NO-GO / UNVERIFIED
PRODUCTION_PYPI_PUBLICATION = NO-GO
HUGGING_FACE_PUBLICATION = NO-GO
HOSTED_DOCUMENTATION_DEPLOYMENT = NO-GO / NOT CURRENTLY JUSTIFIED
REAL_EXPERIMENT_READY = NO-GO
TRAINING_EXECUTION_READY = NO-GO
SCIENTIFIC_RESULT_PUBLICATION = NO-GO
NEW_RELEASE_AUTHORITY = NO-GO
PRODUCT_OR_CLINICAL_DEPLOYMENT = NO-GO
```

## Release boundary

Documentation alignment, release automation, package build capability, an existing historical
tag, fixture-only plumbing qualification, clean-wheel/version-binding qualification,
documentation-source qualification, accepted governance, a fail-closed TestPyPI repository
path, and passing CI are distinct facts. None of them alone authorizes a new tag, external
publication, model promotion, training run, dataset publication, hosted documentation,
product deployment, or clinical use.

The existing `v0.2.0` annotated tag is historical and later workflow hardening must not be
projected backward onto it. The live GitHub Releases evidence reviewed for ALIGN-10
establishes the historical `v0.1.0` GitHub Release object and does not establish a `v0.2.0`
GitHub Release object.

## Scientific boundary

Canonical MRL real-preflight evidence remains separately governing. ALIGN-10 does not alter
MRL task/evidence state. At the final alignment audit, real-experiment readiness remains
false, MRL-0801..MRL-0808 remain PLANNED, and the trusted real-preflight evidence set remains
empty unless separately changed by its own canonical evidence process.

## Completion rule

Public Repository Alignment is complete only when the ALIGN-10 closeout candidate receives:

- exact allowlist and `0 behind` ancestry;
- no actual blocking post-ALIGN-24 main verification failure;
- required exact-head Python 3.11/3.12 quality jobs and CodeQL;
- fresh substantive independent semantic review;
- resolved review threads;
- final main/base/head/ruleset verification; and
- guarded expected-head merge.

After that merge, this alignment plan has no automatic successor. Any future external
publication, release, model/data access, experiment, training, promotion, hosted deployment,
product deployment, or clinical work requires separately justified scope and authority.

## Deliverables

- `specs/public-repository-alignment/spec.md`
- `specs/public-repository-alignment/plan.md`
- `specs/public-repository-alignment/tasks.md`
- `specs/public-repository-alignment/final-publication-go-no-go.md`
- Scoped issues/PRs with exact allowlists and exact-head qualification evidence
