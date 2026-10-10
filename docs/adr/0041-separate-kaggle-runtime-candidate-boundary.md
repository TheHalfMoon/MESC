# ADR-0041 — Separate Kaggle runtime candidate boundary

Status: accepted for the explicitly authorized engineering scope (2026-10-09).
Hosted execution remains NOT AUTHORIZED.

## Context

The Founder directed additive zero-paid-compute Kaggle engineering alongside the
existing one-shot Colab Recovery-3 process in [Issue #545](https://github.com/TheHalfMoon/MESC/issues/545).
That direction grants implementation and offline qualification, not a second
scientific campaign. The frozen protocol, ADR-0035 authority boundary and R2/R7
remain controlling. Provider convenience cannot change the scientific ruler.

## Decision

Keep Kaggle provider identity, source lineage, evidence, consumption and future
authority separate from Recovery-3. Implement a private read-only official SDK
observer, an untrusted environment-candidate validator and an explicitly offline
single-use custody simulator. No GPU launch, kernel push, model import, authority
writer or trust-admission path is included. All observations remain candidates.

Inventory T4 x2 as two independent devices. The comparable frozen workload is
sequential single-device cuda:0 placement, with no offload or automatic device
map. Real tensor placement and per-device memory must be proven during a future
authorized probe; inventory metadata cannot prove model fit or CUDA compatibility.

## Consequences

- Provider planning and deterministic local failure tests proceed without GPU use.
- A supported official quota query may supply private observations; missing,
  rejected or malformed quota stays UNKNOWN. Quota never guarantees capacity.
- Simulated receipts and ACKs cannot become hosted evidence or Founder approval.
- A real adapter/controller requires separate bounded authority, exact-source
  qualification, independently proven hosted preservation/termination and an
  authenticated fixed-account consumption store before its launch path is added.
- This additive, removable engineering module changes no accepted experiment,
  Colab source manifest, trust root, clinical authority or MRL completion state.
