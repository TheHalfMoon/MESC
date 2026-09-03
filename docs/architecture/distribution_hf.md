# Distribution: Hugging Face Presence

- **Status:** Recognized future distribution layer — **no governed artifact publication is recorded here**
- **Original date:** 2026-07-10
- **Reconciled:** 2026-09-03 under ALIGN-23
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

Canonical package automation currently implements package build/qualification and an
authorized-tag GitHub Release path. It does **not** currently implement TestPyPI/PyPI or
Hugging Face publication.

## Publishing gates

Nothing ships to Hugging Face merely because an identity exists. Any future artifact
must first satisfy its applicable canonical research/release, rights/licence, evidence,
card/manifest, and publication gates. Planned phase names or code surfaces are not
publication evidence.

## Principle

The HF presence does not change MedScale's identity. MedScale is open research
intelligence infrastructure for medicine; downstream distribution is a mirror/window,
not the source of truth and not a substitute for canonical evidence.

## Detailed strategy

This document is the identity record. The binding publication/distribution strategy —
lifecycle, versioning, checklists, naming conventions, card requirements, CI-only
publishing, exact-artifact reuse, and external-publication boundaries — lives in
[docs/releases/](../releases/README.md) under Accepted ADR-0010 and ADR-0011.

Acceptance of those ADRs does not create Hugging Face publication, credentials,
trusted-publisher configuration, model/data execution evidence, or authorization to
upload anything. External distribution remains separately scoped and evidence-gated.
