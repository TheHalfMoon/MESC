# Public Repository Alignment — Specification

## Goal
Make `https://github.com/TheHalfMoon/MESC` the canonical truthful source for MedScale's
current state, capabilities, and quality evidence. This spec covers alignment, packaging,
distribution, and open-source readiness only. It does not add architecture, models,
datasets, or training execution.

## Non-goals
- No additional architecture layers.
- No model downloads, inference, fine-tuning, GPU execution, external APIs, or dataset mutation.
- No tags, releases, or pushes until founder approval after this audit.

## Scope
1. Public truth alignment — README, ROADMAP, CHANGELOG, RELEASES, CITATION.cff, pyproject.toml, docs index.
2. MESC positioning — clarify MedScale Evaluation, Sandbox, and Contracts tier experimentally where present.
3. Release/version strategy — SemVer, artifact naming, provenance, changelog discipline.
4. API stability classification — public / experimental / internal for all M17–M18 contracts.
5. Executable golden path — one deterministic end-to-end flow with a smoke command + example output.
6. Documentation publishing — hosted docs readiness and link hygiene.
7. Package distribution — TestPyPI / PyPI wheel/sdist readiness, provenance, checksums.
8. CI and supply-chain hardening — reproducible CI, action pinning, coverage enforcement, provenance attestation.
9. Contributor readiness — templates, onboarding, succession risk, good-first-issue candidates.

## Current governed state

- Canonical `main` is `ce7db4342f01bdcbc15240f1dcf8384ea22ff308`, the merge commit for PR #16.
- ALIGN-13 capability foundation is complete.
- ALIGN-14 deterministic split-assignment freeze and governance closeout are complete.
- ALIGN-15 evaluation-engine boundary audit is complete.
- ALIGN-16 model-runtime and governance audit merged via PR #15; its post-merge CI, CodeQL, and Optional Extras / Backends were green on the merge SHA `1d60f00826f7029c83706b7f97e2409b40f57d57`.
- ALIGN-17 ModelKit public surface and runtime governance ADR merged via PR #16; its post-merge CI, CodeQL, and Optional Extras / Backends are green on the merge SHA `ce7db4342f01bdcbc15240f1dcf8384ea22ff308`.
- ADR-0033 was accepted by the founder on 2026-07-15 after full semantic content review; ALIGN-17 governs ModelKit public surface and runtime exclusions.
- The canonical current evaluation boundary remains `medscale.bench`, the `Benchmark` facade, and `BenchmarkRunArtifact`.
- ALIGN-15 evaluation/runtime separation remains authoritative: evaluation consumes stable model identity and outputs; it does not own provider execution, routing, credentials, or deployment state.
- Current optional Transformers and llama.cpp adapters provide deterministic synthetic protocol-contract behavior only; they do not load model weights or perform real inference.
- `_runtime.py` and workspace orchestration remain internal.
- `REGISTRY` is an immutable governed model fact registry, not a mutable runtime or deployment registry.
- Training recipes and experiment manifests are schemas, not training or inference execution systems.
- Model promotion, model lineage, training-run, checkpoint, adapter-artifact, deployment, and infrastructure contracts do not exist on canonical `main`.
- No public export change, model runtime implementation, training execution, promotion, lineage, routing, deployment, or infrastructure work is authorized by ALIGN-16 or ALIGN-17.
- ALIGN-10 remains pending as the final publication recommendation.
- Public documentation synchronization, golden-path work, and CI/distribution hardening remain future governed phases.

## Success criteria
- The public repository gains a truthful internal alignment plan without changing public capability claims or release metadata.
- Spec Kit artifacts explicitly record verified local versus `origin/main` state, quality baseline, and civic release boundaries.
- Future PRs are sequenced with explicit public-truth freeze points and a release gate.
- One deterministic golden-path example is identified as a release prerequisite, but not executed in this PR.

## Constraints
- Additive-only changes relative to v0.2.0 baseline public API.
- No breaking changes to existing v0.2.0 public surface.
- No hidden compute assumptions, no scheduler, no cloud integration, no execution layer beyond validation and contracts.

## Phase skip rules
- A planned hygiene or formatting phase may be recorded `Not Applicable` when a verified audit finds zero tracked behavior-preserving candidates.
- A no-op empty PR must not be created merely to satisfy sequence numbering.
- Functional, contract, API, schema, CLI, or architectural changes must move into separately scoped capability PRs.
- Skipping a non-applicable phase requires recorded evidence and an explicit sequencing amendment before the next governed capability PR is opened.

## Assumptions
- Public origin is `https://github.com/TheHalfMoon/MESC` on `main`.
- No uncommitted implementation or governance material will be silently incorporated; every capability PR is reviewed against the canonical acceptance criteria before merge.
