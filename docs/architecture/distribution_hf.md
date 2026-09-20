# Distribution: Hugging Face Presence

- **Status:** Governed repository transport implemented but disabled — **no governed Hugging Face artifact publication is recorded here**
- **Original date:** 2026-07-10
- **Reconciled:** 2026-09-20 under Issue #451
- **Related:** [ADR-0005](../adr/0005-research-intelligence-scope.md) (identity),
  [reference architecture](medscale_reference_architecture.md), Rules R3/R7

## Identity record

| Asset | Value |
|---|---|
| HF user | `MedScale` |
| HF organization | `MedScaleAI` |
| Space identity recorded historically | `https://huggingface.co/spaces/MedScale/MedScale` |
| GitHub (source of truth) | `https://github.com/TheHalfMoon/MESC` |

These names/URLs are an identity record. This repository document does not by itself
prove current external availability, artifact publication, mirror correctness, or
publication authority; any such claim requires separately verified external evidence.

## Role

Hugging Face is a **downstream distribution/window layer** for governed MedScale
artifacts. GitHub remains the only canonical source of truth. No model, dataset, Space,
or collection becomes canonical by existing on a downstream service.

Canonical package automation implements package build/qualification and an
authorized-tag GitHub Release path. ALIGN-24 additionally implements a repository-side,
disabled-by-default TestPyPI Trusted Publishing job that reuses the exact qualified
release artifact after GitHub Release creation. Issue #451 adds a separately governed
Hugging Face Trusted Publisher transport, also disabled by default. Neither repository
path proves its required external Environment or publisher configuration, sets its
enable variable, or authorizes an external upload.

## Publishing gates

Nothing ships to Hugging Face merely because an identity or transport exists. Any
artifact must first satisfy its applicable canonical research/release, rights/licence,
evidence, card/manifest, publication-authority, destination, and external trust-boundary
gates. Planned phase names, repository code, or successful dry-run qualification are not
publication evidence.

The Hugging Face transport cannot activate from repository code alone. Its committed
authority record is `DISABLED`, the repository does not set
`HF_PUBLISH_ENABLED=true`, and no destination repository, GitHub Environment, or
Trusted Publisher is created or configured by this implementation.

## Principle

The HF presence does not change MedScale's identity. MedScale is open research
intelligence infrastructure for medicine; downstream distribution is a mirror/window,
not the source of truth and not a substitute for canonical evidence.

## Detailed strategy

This document is the identity record. The binding publication/distribution strategy —
lifecycle, versioning, checklists, naming conventions, card requirements, CI-only
publishing, exact-artifact reuse, and external-publication boundaries — lives in
[docs/releases/](../releases/README.md) under Accepted ADR-0010 and ADR-0011.

Acceptance of those ADRs and repository-side distribution implementations do not create
Hugging Face publication authority, credentials, model/data execution evidence, or
authorization to upload anything. External activation remains separately scoped and
evidence-gated.

## Repository-side P1 dry-run qualification contract

Issue #451 introduced `specs/mesc-hf-publication-v1` as a repository-side,
external-publication-disabled qualification contract. The contract binds an exact GitHub
source SHA/tree/tag, destination allowlist, artifact manifest, card, rights, provenance,
and licence identity and may emit only a dry-run receipt with
`external_upload_performed=false`.

## Repository-side P2 Trusted Publisher transport

The V2 successor under `specs/mesc-hf-publication-v2` implements a fail-closed
Trusted Publisher/OIDC transport without activating it. A future active authority must
bind the complete P1 plan, exact GitHub Release asset bytes, founder authority
issue-comment identity and body hash, exact GitHub Environment policy, exact destination
parent commit/inventory, and exact transport-manifest hash.

The workflow deliberately separates a read-only `preflight` job from the
Environment-bound `publish` job. Preflight has no `environment:` binding and no
`id-token: write`; it must prove that the already-existing
`huggingface-publication` Environment is protected and policy-identical before GitHub
can schedule the dependent Environment-bound publication job. The publication job then
repeats live boundary checks before materialization, before OIDC exchange, after OIDC
exchange, and before preserving a receipt.

Publication reuses exact immutable GitHub Release bytes without rebuilding, requires the
authorized Hugging Face destination parent commit and file inventory, performs one
parent-bound Hub commit, and independently downloads every governed file at the returned
immutable Hugging Face commit to reproduce byte counts and SHA-256 values before a
success receipt can exist. The receipt is transferred to a separate non-OIDC admission
job, revalidated against the same workflow run/attempt, and posted with its SHA-256 to
the exact authority issue as canonical GitHub evidence. A failure after the Hub commit
is an explicit reconciliation state: no automatic rerun, deletion, rollback, or
replacement is permitted.

This repository implementation does **not** create or configure a Hugging Face
repository, GitHub Environment, or Trusted Publisher; does not set
`HF_PUBLISH_ENABLED`; does not mint a publication token; and does not perform an
external upload. Those actions require separate explicit founder authority and
independent external configuration evidence.
