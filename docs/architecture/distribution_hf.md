# Distribution: Hugging Face Presence

- **Status:** Recognized future distribution layer — **no governed Hugging Face artifact publication is recorded here**
- **Original date:** 2026-07-10
- **Reconciled:** 2026-09-03 under ALIGN-24
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

Hugging Face is a **future downstream distribution/window layer** for governed MedScale
artifacts. GitHub remains the only canonical source of truth. No model, dataset, Space,
or collection becomes canonical by existing on a downstream service.

Canonical package automation implements package build/qualification and an
authorized-tag GitHub Release path. ALIGN-24 additionally implements a repository-side,
disabled-by-default TestPyPI Trusted Publishing job that reuses the exact qualified
release artifact after GitHub Release creation. That repository implementation does not
prove the external `testpypi` GitHub Environment is protected, does not prove a matching
TestPyPI Trusted Publisher exists, does not set `TESTPYPI_PUBLISH_ENABLED`, and does not
perform or authorize an upload. Production PyPI and Hugging Face publication remain
separately unimplemented and unauthorized distribution paths.

## Publishing gates

Nothing ships to Hugging Face merely because an identity exists. Any future artifact
must first satisfy its applicable canonical research/release, rights/licence, evidence,
card/manifest, and publication gates. Planned phase names or code surfaces are not
publication evidence.

The fail-closed TestPyPI repository path does not weaken this boundary and does not
create Hugging Face credentials, publication automation, external rights evidence, or
model/data publication authority.

## Principle

The HF presence does not change MedScale's identity. MedScale is open research
intelligence infrastructure for medicine; downstream distribution is a mirror/window,
not the source of truth and not a substitute for canonical evidence.

## Detailed strategy

This document is the identity record. The binding publication/distribution strategy —
lifecycle, versioning, checklists, naming conventions, card requirements, CI-only
publishing, exact-artifact reuse, and external-publication boundaries — lives in
[docs/releases/](../releases/README.md) under Accepted ADR-0010 and ADR-0011.

Acceptance of those ADRs and repository-side TestPyPI qualification do not create
Hugging Face publication, credentials, model/data execution evidence, or authorization
to upload anything. External activation and distribution remain separately scoped and
evidence-gated.
