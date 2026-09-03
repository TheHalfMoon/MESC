# Public Repository Alignment — Specification

## Goal

Make `https://github.com/TheHalfMoon/MESC` the canonical truthful source for MedScale's current state, capabilities, quality evidence, and release readiness. This specification governs repository alignment, packaging, distribution readiness, and open-source readiness only. It does not itself authorize new research execution, datasets, model runs, training, promotion, publication, or deployment.

## Non-goals

- No additional architecture layer merely for alignment.
- No PHI or real-patient data.
- No external-data acquisition, model download, inference, fine-tuning, GPU execution, publication, or deployment without the separately applicable authority/evidence.
- No tag, GitHub Release, PyPI/TestPyPI/Hugging Face publication, or version bump merely because documentation is aligned.
- No conversion of module/code existence into research-phase completion or execution authority.

## Scope

1. Public truth alignment — README, ROADMAP, release/history docs, citation/package metadata, and docs indexes where drift is demonstrated.
2. MESC positioning — distinguish implemented evaluation/runtime/training infrastructure from stronger research-result or execution claims.
3. Release/version strategy — SemVer, artifact identity, provenance, changelog discipline, and qualified distribution paths.
4. API stability classification — public / experimental / internal according to accepted governance and actual package exports.
5. Executable golden path — one deterministic offline fixture path, separately scoped and gated.
6. Documentation publishing — hosted-docs readiness and link hygiene, separately scoped.
7. Package distribution — wheel/sdist readiness and publication-path hardening, separately scoped.
8. CI and supply-chain hardening — reproducible CI, action pinning, coverage enforcement, install smoke, and provenance where applicable.
9. Contributor readiness — ownership/templates/onboarding without inventing governance authority.

## Current governed state

- Canonical `main` at ALIGN-21 authorization is `3a632457d92bfd98075b6dc082324a9f92a89d97`, the merge commit for PR #345 / ALIGN-20.
- ALIGN-13 through ALIGN-17 historical capability/governance work is complete according to its merged records; later repository work has materially expanded the implementation beyond those early snapshots.
- ALIGN-18 is complete via PR #341 / issue #340. It reconciled the live repository identity to `TheHalfMoon/MESC`, current review ownership, and the ADR index without rewriting historical evidence.
- ALIGN-19 is complete via PR #343 / issue #342 / merge `a5df6403e9087f1c63f95eccbad9d0e2b61a96e1`. It reconciled current public status, roadmap, release, execution, ecosystem, and alignment-control documentation without creating execution or publication authority.
- ALIGN-20 is complete via PR #345 / issue #344 / merge `3a632457d92bfd98075b6dc082324a9f92a89d97`. It added the deterministic offline fixture-only golden path and preserved explicit non-evidence/non-authority semantics.
- ALIGN-21 is issue #346. It is the only active Phase 7 unit and is limited to the exact six-file allowlist recorded there.
- Package version remains `0.2.0`; ALIGN-21 does not authorize a version bump, tag, release, or external publication.
- `medscale.fhirkit` contains an implemented deterministic FHIR validation/report/storage boundary. Grammar-constrained FHIR generation remains an open objective and is not a current release capability claim.
- `medscale.bench` contains deterministic benchmark contracts, scoring, artifacts, and replay/execution surfaces. Their existence does not by itself prove the legacy T3 research phase complete.
- ModelKit/backends and governed MESC runtime/training/evaluation infrastructure exist in canonical code. Exact model execution, training, promotion, result, and publication eligibility are controlled by their applicable canonical specifications/evidence, not by this alignment spec.
- MRL/Mission Zero canonical state outranks human-readable README/roadmap prose. ALIGN-21 must preserve that precedence and must not alter MRL-0801..MRL-0808 or Mission Zero evidence state.
- `.github/workflows/release.yml` already implements SHA-pinned tag-driven package quality/build/GitHub-Release automation plus PR-safe wheel/sdist byte-identity self-qualification. ALIGN-21 adds clean installed-wheel qualification over the exact built artifact without creating publication authority.
- Coverage enforcement and SHA-pinned Actions are already implemented; ALIGN-21 must not reimplement them.
- `v0.2.0` is an existing annotated tag pointing to commit `d2e651a55c92f2218aca49acaa5b7bd18a75f096`. ALIGN-21 does not move or recreate it.
- TestPyPI/PyPI trusted publishing remains a separate future gate and is not implemented or authorized by ALIGN-21.
- ALIGN-10 remains pending as the final evidence-backed publication GO/NO-GO recommendation.

## Phase 6 executable golden-path contract

- The user-visible command is `medscale mesc-fixture-smoke`.
- It composes the existing canonical MRL fixture loop rather than implementing a second evaluator, receipt, or decision engine.
- It runs one fixed in-memory, non-perfect fixture candidate and deterministically terminates in `REJECT`, not `EVIDENCE_CANDIDATE`.
- It emits canonical JSON content identities for proposal, observation, receipt, decision, and completed loop result, with explicit `fixture_only=true` and `non_evidence=true`.
- It performs no filesystem writes, network access, model/data access, inference, training, GPU/provider work, credentials, campaign-state update, promotion, release, deployment, or clinical action.
- The golden path qualifies repository plumbing only. It is not scientific evidence, a model result, real-experiment readiness, or publication authority.

## Phase 7 clean-wheel qualification contract

- The exact wheel produced by the existing release build is the wheel installed for qualification; the install gate must not rebuild a second candidate.
- The clean-install job does not check out repository source.
- It creates a fresh Python 3.11 environment, installs the downloaded wheel with no dependencies, and requires the installed CLI to report exactly `medscale 0.2.0`.
- The PR-safe path self-qualifies this behavior without publishing anything.
- The tag path requires the clean-install gate before GitHub Release creation.
- This is package qualification only. It does not create tag, release, TestPyPI/PyPI/Hugging Face, credential, trusted-publisher, deployment, or clinical authority.

## Current success criteria

- Public-facing status prose matches canonical code/governance without overstating research completion or authority.
- Historical records remain historical; current summaries are reconciled rather than rewriting old acceptance/evidence.
- Phase 5 is complete and canonical through ALIGN-19.
- Phase 6 is complete and canonical through ALIGN-20.
- ALIGN-21 closes only after its exact allowlist, PR-safe build/byte-identity/clean-wheel workflow qualification, full exact-head CI/CodeQL, substantive independent semantic review, diff-check verification, and review-thread reconciliation all pass before guarded merge.
- TestPyPI trusted-publishing qualification and hosted-doc readiness remain separately scoped successor work.
- Final publication recommendation remains blocked until the required later alignment/release-readiness work is itself complete and evidenced.

## Constraints

- Preserve the public `0.2.0` package/version baseline unless a separately authorized release task changes it.
- No breaking change to the v0.2.0 public surface in alignment work without separate authority.
- No hidden compute assumptions, no cloud/runtime authority, and no scientific result claims without committed executable evidence.
- Current summaries must distinguish `implemented`, `qualified`, `authorized`, `executed`, `accepted`, `released`, and `published` rather than collapsing them.

## Phase skip rules

- A planned hygiene or formatting phase may be recorded `Not Applicable` when a verified audit finds zero eligible candidates.
- A file named by a historical plan may be excluded from a later implementation allowlist when audit proves no mutation is needed; no-op churn is not required.
- A no-op empty PR must not be created merely to satisfy sequence numbering.
- Functional, contract, API, schema, CLI, workflow, or architectural changes move into separately scoped units unless explicitly admitted by the current issue.
- Skipping or narrowing a phase requires recorded evidence and an explicit sequencing/scope amendment before the next governed capability PR is opened.

## Assumptions

- Public origin is `https://github.com/TheHalfMoon/MESC` on `main`.
- No uncommitted or branch-only implementation is silently treated as canonical truth.
- Every capability/result/authority claim is checked against the canonical repository evidence applicable to that claim.
