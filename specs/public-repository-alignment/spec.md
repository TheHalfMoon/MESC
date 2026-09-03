# Public Repository Alignment — Specification

## Goal

Make `https://github.com/TheHalfMoon/MESC` the canonical truthful source for MedScale's current state, capabilities, quality evidence, and release readiness. This specification governs repository alignment, packaging, distribution readiness, and open-source readiness only. It does not itself authorize new research execution, datasets, model runs, training, promotion, publication, or deployment.

## Non-goals

- No additional architecture layer merely for alignment.
- No PHI or real-patient data.
- No external-data acquisition, model download, inference, fine-tuning, GPU execution, publication, or deployment without the separately applicable authority/evidence.
- No tag, GitHub Release, PyPI/TestPyPI/Hugging Face publication, or version bump merely because documentation/governance is aligned.
- No conversion of module/code existence into research-phase completion or execution authority.

## Scope

1. Public truth alignment — README, ROADMAP, release/history docs, citation/package metadata, and docs indexes where drift is demonstrated.
2. MESC positioning — distinguish implemented evaluation/runtime/training infrastructure from stronger research-result or execution claims.
3. Release/version strategy — SemVer, artifact identity, provenance, changelog discipline, and qualified distribution paths.
4. API stability classification — public / experimental / internal according to accepted governance and actual package exports.
5. Executable golden path — one deterministic offline fixture path, separately scoped and gated.
6. Documentation publishing — source readiness and any later hosted-doc decision are separately scoped.
7. Package distribution — wheel/sdist readiness and publication-path hardening, separately scoped.
8. CI and supply-chain hardening — reproducible CI, action pinning, coverage enforcement, install smoke, and provenance where applicable.
9. Contributor readiness — ownership/templates/onboarding without inventing governance authority.

## Current governed state

- Canonical `main` at ALIGN-24 authorization is `8a6c3bf6f51b2e6f72fcdc3ce3c14dfc5f1b4f5c`, the merge commit for PR #352 / ALIGN-23.
- ALIGN-18 is complete via PR #341 / issue #340 / merge `1f27f4128229f1c3c973355c5a14bcac2cec0dfe`.
- ALIGN-19 is complete via PR #343 / issue #342 / merge `a5df6403e9087f1c63f95eccbad9d0e2b61a96e1`.
- ALIGN-20 is complete via PR #345 / issue #344 / merge `3a632457d92bfd98075b6dc082324a9f92a89d97`.
- ALIGN-21 is complete via PR #347 / issue #346 / merge `5e8ee576ff51301ac94eb8298d7b885338dbb5f2`.
- ALIGN-22 is complete via PR #349 / issue #348 / merge `02b4ad0956aef613a792a1de853d31b4e1c41fda`. It qualified the repository documentation-source/link graph without hosted publication authority.
- ALIGN-23 is complete via PR #352 / issue #351 / merge `8a6c3bf6f51b2e6f72fcdc3ce3c14dfc5f1b4f5c`. It reconciled and accepted ADR-0010/ADR-0011 plus current release/version/licensing policy surfaces without external publication authority.
- ALIGN-24 is issue #353. It is the only active alignment unit and is limited to a fail-closed repository-side TestPyPI Trusted Publishing path, focused workflow-contract tests, and current release/alignment truth under its exact allowlist.
- Package version remains `0.2.0`; ALIGN-24 does not authorize a version bump, tag, GitHub Release, TestPyPI upload, or production PyPI publication.
- `medscale.fhirkit` contains an implemented deterministic FHIR validation/report/storage boundary. Grammar-constrained FHIR generation remains an open objective and is not a current release capability claim.
- `medscale.bench` contains deterministic benchmark contracts, scoring, artifacts, and replay/execution surfaces. Their existence does not by itself prove a research phase complete.
- ModelKit/backends and governed MESC runtime/training/evaluation infrastructure exist in canonical code. Exact model execution, training, promotion, result, and publication eligibility are controlled by their applicable canonical specifications/evidence, not by this alignment spec.
- MRL/Mission Zero canonical state outranks human-readable README/roadmap prose. ALIGN-24 must not alter MRL-0801..MRL-0808 or Mission Zero evidence state.
- `.github/workflows/release.yml` implements SHA-pinned tag-driven package quality/build/GitHub-Release automation, PR-safe wheel/sdist byte-identity self-qualification, clean installed-wheel metadata/CLI qualification over the exact built artifact, and under ALIGN-24 a disabled-by-default TestPyPI Trusted Publishing job that reuses the same qualified artifact after GitHub Release creation.
- The TestPyPI repository job references `environment: testpypi`, scopes `id-token: write` to that job, uses the SHA-pinned official PyPA publisher, and additionally requires `vars.TESTPYPI_PUBLISH_ENABLED == 'true'`. Repository code neither sets that variable nor proves the protected Environment or matching TestPyPI Trusted Publisher exists.
- Production PyPI and Hugging Face publication remain separately unimplemented and unauthorized distribution paths.
- Coverage enforcement, documentation source/link qualification, and SHA-pinned Actions are implemented in current audited workflows.
- `v0.2.0` is an existing annotated tag pointing to commit `d2e651a55c92f2218aca49acaa5b7bd18a75f096`; later workflow hardening must not be projected backward onto that historical tag.
- No standalone hosted documentation renderer/deployment is configured. The post-ALIGN-22 audit found no concrete consumer/provider, so hosted deployment is not currently justified.
- ALIGN-10 remains pending as the final evidence-backed publication GO/NO-GO recommendation after ALIGN-24.

## Phase 6 executable golden-path contract

- The user-visible command is `medscale mesc-fixture-smoke`.
- It composes the existing canonical MRL fixture loop rather than implementing a second evaluator, receipt, or decision engine.
- It runs one fixed in-memory, non-perfect fixture candidate and deterministically terminates in `REJECT`, not `EVIDENCE_CANDIDATE`.
- It emits canonical JSON content identities for proposal, observation, receipt, decision, and completed loop result, with explicit `fixture_only=true` and `non_evidence=true`.
- It performs no filesystem writes, network access, model/data access, inference, training, GPU/provider work, credentials, campaign-state update, promotion, release, deployment, or clinical action.
- The golden path qualifies repository plumbing only. It is not scientific evidence, a model result, real-experiment readiness, or publication authority.

## Phase 7 clean-wheel qualification contract

- The exact wheel produced by the existing release build is the wheel installed for qualification; the install gate must not rebuild a second candidate.
- The clean-install jobs do not check out repository source.
- Both paths create a fresh Python 3.11 environment, install the downloaded wheel with no dependencies, derive the installed package version from `importlib.metadata`, and require `medscale --version` to report that exact installed version.
- The PR-safe path self-qualifies this behavior without publishing anything and, for the current baseline, additionally requires the installed version to remain `0.2.0`.
- The tag path is version-generic and requires `GITHUB_REF_NAME` to equal `v<installed-version>` before GitHub Release creation.
- This is package qualification only. It does not create tag, release, TestPyPI/PyPI/Hugging Face, credential, trusted-publisher, deployment, or clinical authority.

## ALIGN-22 documentation source-readiness contract

- The checked public source set is the public root Markdown documents plus `docs/**/*.md`.
- The checker is Python-stdlib only and performs no network request, package installation, renderer invocation, deployment, or external mutation.
- Repository-local inline links, image targets, and reference-definition targets must resolve inside the repository and must exist.
- Links that escape the repository root fail closed.
- Markdown fragments must resolve to deterministic GitHub-style heading anchors or explicit HTML `id` anchors, including duplicate-heading suffixes.
- External URI schemes and fenced-code/comment examples are outside the repository-local target check according to the qualified checker semantics.
- Passing this contract means the documentation **source/link graph is qualified**. It does not mean a hosted documentation site exists, has been deployed, or has publication authority.

## ALIGN-23 release-governance reconciliation contract

- ADR-0010/ADR-0011 became Accepted only after their proposed 2026-07-10 wording was reconciled to canonical current implementation and historical release truth.
- Acceptance makes GitHub-canonical, CI-only, immutable-artifact, versioning, and licensing policy binding; it does not create an external publisher, credential, trusted-publisher relationship, environment, tag, release, or upload.
- Current `.github/workflows/release.yml` is the implemented package/GitHub-Release automation surface; stale `release-package.yml` future-ticket wording was not canonized as current truth.
- Mechanical licence/manifest enforcement is not claimed merely because policy requires it; implementation and qualification remain separate evidence.
- Historical execution/audit records remain historical and are not rewritten merely to remove proposed-state references.
- Hosted documentation deployment remains deferred as not currently justified absent a concrete consumer/provider.

## ALIGN-24 fail-closed TestPyPI contract

- The TestPyPI job depends on successful `github-release` completion and downloads the exact same-run `dist-${{ github.ref_name }}` artifact; it must not check out source or rebuild a second candidate.
- The job runs only on the governed `v*` tag path and only when `vars.TESTPYPI_PUBLISH_ENABLED == 'true'`.
- `id-token: write` is scoped to the TestPyPI job only. Workflow-global permissions remain least-privilege and no username/password/API-token fallback is permitted.
- The job references the governed `testpypi` GitHub Environment and uses `pypa/gh-action-pypi-publish@dc37677b2e1c63e2034f94d8a5b11f265b73ba33` with the TestPyPI repository URL.
- Required repository tests inspect these workflow invariants and fail closed if the publication contract drifts.
- PR qualification invokes no TestPyPI upload and no OIDC publishing action; the TestPyPI job is excluded by its push/tag/enable guard.
- Repository implementation and PR qualification do **not** prove external activation. A protected `testpypi` Environment, matching TestPyPI Trusted Publisher, and explicit operator enable decision require independent evidence not manufactured by this unit.
- ALIGN-24 does not set `TESTPYPI_PUBLISH_ENABLED`, create a tag/release, perform an upload, or authorize production PyPI.

## Current success criteria

- Public-facing status prose matches canonical code/governance without overstating research completion or authority.
- Historical records remain historical; current summaries are reconciled rather than rewriting old acceptance/evidence.
- Phase 5 is complete and canonical through ALIGN-19.
- Phase 6 is complete and canonical through ALIGN-20.
- Phase 7 clean-wheel/package qualification is complete and canonical through ALIGN-21.
- Documentation source/link readiness is complete and canonical through ALIGN-22.
- Release/version/licensing governance reconciliation is complete and canonical through ALIGN-23.
- ALIGN-24 closes only after its exact allowlist, fail-closed workflow contract, focused repository tests, PR-safe release-workflow qualification, full exact-head CI/CodeQL, substantive independent semantic review, diff-check verification, and review-thread reconciliation pass before guarded merge.
- Successful ALIGN-24 means the repository-side TestPyPI path is implemented and qualified while external Trusted Publisher/Environment activation remains evidence-dependent. It does not mean TestPyPI upload readiness is proven.
- Hosted documentation deployment remains deferred unless a concrete consumer/provider justifies it.
- ALIGN-10 remains the final publication GO/NO-GO evidence synthesis after ALIGN-24 and must carry any unresolved external TestPyPI activation or scientific-evidence blockers truthfully.

## Constraints

- Preserve the public `0.2.0` package/version baseline unless a separately authorized release task changes it.
- No breaking change to the v0.2.0 public surface in alignment work without separate authority.
- No hidden compute assumptions, no cloud/runtime authority, and no scientific result claims without committed executable evidence.
- Current summaries must distinguish `implemented`, `qualified`, `authorized`, `executed`, `accepted`, `released`, `published`, and `externally activated` rather than collapsing them.

## Phase skip rules

- A planned phase may be recorded `Not Applicable` or deferred when a verified audit finds no concrete eligible need; no-op churn is not required.
- A file named by a historical plan may be excluded from a later implementation allowlist when audit proves no mutation is needed.
- A no-op empty PR must not be created merely to satisfy sequence numbering.
- Functional, contract, API, schema, CLI, workflow, or architectural changes move into separately scoped units unless explicitly admitted by the current issue.
- Skipping or narrowing a phase requires recorded evidence and an explicit sequencing/scope amendment before the next governed capability PR is opened.

## Assumptions

- Public origin is `https://github.com/TheHalfMoon/MESC` on `main`.
- No uncommitted or branch-only implementation is silently treated as canonical truth.
- Every capability/result/authority claim is checked against the canonical repository evidence applicable to that claim.
