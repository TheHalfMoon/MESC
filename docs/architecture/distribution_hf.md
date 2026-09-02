# Distribution: Hugging Face Presence

- **Status:** Recognized future distribution layer — **nothing is published yet**
- **Date:** 2026-07-10
- **Related:** [ADR-0005](../adr/0005-research-intelligence-scope.md) (identity),
  [reference architecture](medscale_reference_architecture.md), Rules R3/R7

## Identity (secured 2026-07-10)

| Asset | Value |
|---|---|
| HF user | `MedScale` |
| HF organization | `MedScaleAI` |
| Space (placeholder) | https://huggingface.co/spaces/MedScale/MedScale |
| GitHub (source of truth) | https://github.com/TheHalfMoon/MESC |

## Role

Hugging Face is MedScale's **public window**: project identity, future demos
(MedScale Demo, Evidence Explorer, Benchmark Viewer), released adapters, benchmark and
evidence datasets. The GitHub repository remains the only source of truth; HF hosts
*released artifacts*, never development state.

## Publishing gates (nothing ships before its gate)

| Artifact | Gate |
|---|---|
| Evidence/litdb dataset export | T1 corpus populated + R3 licence review of exported fields (see `data/litdb/LICENSE.md` — e.g. PubMed abstracts are excluded from any export) |
| Benchmark dataset | T3 green + benchmark spec + R7 result artifacts |
| Model adapters | T6/T7 + model card (not-a-medical-device, synthetic-only, seeds + CI) |
| Demo Spaces | The artifact they demonstrate exists and is reproducible |

## Principle

The HF presence does not change MedScale's identity. MedScale is not another medical AI
chatbot; it is **open research intelligence infrastructure for medicine**, and the
competitive advantage remains evidence objects, provenance, verification, and
reproducibility. A Space is a window onto that infrastructure — never the product itself.

## Detailed strategy

This document is the *identity record*. The full publication and distribution strategy
— lifecycle, versioning, checklists, naming conventions, card requirements, CI-only
publishing — lives in [docs/releases/](../releases/README.md) (ADR-0010/0011, Proposed).
