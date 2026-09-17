# ADR-0001 — Adopt XGrammar for the bounded RQ1 grammar runtime

- **Status:** Accepted
- **Date:** 2026-09-17
- **Deciders:** Founder
- **Supersedes:** none
- **Superseded by:** none
- **Related:** ADR-0035, ADR-0036, MRL-0809 prerequisite authority, `specs/mesc-experiment-0/mrl-0806-rq1-protocol-v1.json`

## Context

The frozen RQ1 protocol requires a grammar engine, a deterministic StructureDefinition-to-GBNF compiler, a grammar-capable backend, and qualified runtime model-load feasibility before MRL-0809 may become eligible. The existing B0 Transformers backend declares that unsupported grammar requests must fail closed but does not provide the RQ1 constrained-decoding runtime.

XGrammar 0.2.7 was independently inspected at source commit `82505d0d987c36a4209fb3d8571cf6b0f28b5acd`, tag `v0.2.7`. The reviewed release identity is bounded by sdist SHA-256 `7674afeee5e6eff9672627b62d5ab0aa2347ea51674f4d78a5c160029f92bc3e` and CPython 3.11 Linux x86_64 wheel SHA-256 `e3a4cb4214b228d2fecefe46f46d2f2b0d6c8468fd448319250cae6bccb73339`. Release provenance inspection does not itself authorize scientific model execution.

## Decision

1. Admit exactly `xgrammar==0.2.7` for the bounded RQ1 grammar runtime through a dedicated optional dependency surface; do not broaden the generic B0 backend extra.
2. Use a MedScale-owned adapter around `TokenizerInfo.from_huggingface`, `GrammarCompiler.compile_grammar`, and a fresh `xgrammar.contrib.hf.LogitsProcessor` per constrained generation call.
3. Construct `GrammarCompiler` with one thread and caching disabled. Accept only the canonical generated RQ1 Patient grammar; arbitrary user/adaptive grammar text is outside this lane.
4. Keep constrained generation deterministic: greedy, single beam, frozen seed set, fixed request token ceiling, and no silent fallback. If grammar enforcement is unavailable or incompatible, block before generation.
5. Keep B0 Transformers and the llama.cpp placeholder grammar-incapable; they must raise a typed fail-closed error for `GenerationRequest.grammar`.
6. Freeze the first compiler to official HL7 FHIR R4 4.0.1 Patient and Address StructureDefinition bytes and the already-selected RQ1 Patient projection only. Unsupported profile/type/cardinality/binding drift fails closed.
7. This ADR supplies repository-side implementation authority only. Runtime model/tokenizer loading requires separately qualified feasibility evidence and does not follow from dependency admission.

## Consequences

The RQ1 constrained-decoding path is explicit, deterministic, optional, and independently reviewable. The first compiler is intentionally not a general FHIR compiler. XGrammar becomes an additional optional runtime dependency only for the RQ1 lane. Candidate tokenizer compatibility and memory capacity remain external runtime-feasibility questions.

## Alternatives considered

- **Retrofit B0 Transformers:** rejected because it would blur B0 allowlist/runtime semantics with the RQ1 scientific lane.
- **llama.cpp grammar runtime:** not selected for RQ1 because the frozen candidate path is Transformers-based and exact candidate/tokenizer identity must remain unchanged.
- **Unbounded grammar input:** rejected because it enlarges parser/cache and scientific-identity attack surfaces without RQ1 need.

## Compliance

The repository binds the exact XGrammar identity, official FHIR source digests, generated grammar digest, adapter source, compiler source, dependency lock, and runtime-feasibility validator in a static prerequisite manifest. CI may compile the frozen grammar with synthetic/local tokenizer material only. It must not load either frozen scientific candidate, download model weights, access sealed Tier-3 item content, train, mutate weights, spend money, or mark MRL-0809 complete. A separate exact trusted runtime-feasibility PASS for both candidates remains mandatory before the MRL-0809 prerequisite gate may become eligible.
