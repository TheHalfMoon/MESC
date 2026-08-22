# FD-MESC-BT-EXEC-1 — Conditional Backbone Tournament Execution Authorization

Status: **DRAFT GOVERNANCE PACKAGE — CONDITIONAL AUTHORIZATION CANDIDATE — EXECUTION INACTIVE**

Date: 2026-08-22

## Purpose

This package stages the separate Founder decision required after canonical GH2 preflight closure. It defines the bounded conditions under which one MESC Backbone Tournament execution may later be activated.

Canonical preflight state at drafting:

```text
AUTHORIZATION_BASE_SHA = a78bcec4cf7daccc933315df8d5ce60bca005ed9
AUTHORIZATION_BASE_TREE = a0e9b72d9535e4b0999f2a30874924896aae68c6
GH2_PREFLIGHT_RESULT_MERGE_SHA = 14a2229c184d3ef29b6032d5cb00e11ac28d1413
GH2_PREFLIGHT_ADOPTION_MERGE_SHA = a78bcec4cf7daccc933315df8d5ce60bca005ed9
GH2_ACTIVATION_RECEIPT_ID = 0454aa7f9511fa2d7a974aeae6c6153c0f56394a353c5e6675906ace26b19e94
GH2_PREFLIGHT_RESULT_MANIFEST_SHA256 = 38f6cd08c4aa650e6a110639d3a7b85297c68d454ffcc9139e518fdb3d15ef6d
GH2_R2_PROVENANCE_AUDIT_SHA256 = a8f6fd8d9c9f60c5a1a2bedc0bbb49182e635772cf50dae1e9e9028a4eb09398
GH2_CORPUS_CONFORMANCE_AUDIT_SHA256 = 842f2e0dbeaea59087223ddd94c8a95844c8f14822a16e1549e67c0c850c67f2
PREFLIGHT_STATE = PREFLIGHT_READY_FOR_EXECUTION_AUTHORIZATION
```

## Intended tournament scope

The intended selected candidate set is all four canonically admitted non-empty candidates, preserving the canonical empty challenger:

1. `openai/gpt-oss-20b@6cee5e81ee83917806bbde320786a8fb61efebee`
2. `swiss-ai/Apertus-v1.5-8B@a411d838600baf0e3635a3daf66fb7c55fc97bb6`
3. `microsoft/Phi-4-multimodal-instruct@93f923e1a7727d1c4f446756212d9d3e8fcc5d81`
4. `google/medgemma-1.5-4b-it@91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b`

`challenger = EMPTY`.

No candidate may be silently removed, replaced, quantized differently, or moved to a floating revision.

## Target execution environment class

The target compute class for later activation is:

```text
PROVIDER_CLASS = RunPod Secure Cloud
GPU_CLASS = NVIDIA H100 80GB HBM3
GPU_COUNT = 1
EXECUTION_MODE = candidates run sequentially on one activation-bound GPU identity
BASE_CONTAINER_TAG_CANDIDATE = nvcr.io/nvidia/pytorch:26.07-py3
BASE_CONTAINER_IDENTITY = UNBOUND_UNTIL_IMMUTABLE_OCI_DIGEST
```

The tag above is planning metadata only. It is not an executable runtime identity. Activation must bind the immutable OCI digest, region, pod/host identity where exposed, GPU UUID/model, driver/CUDA/runtime versions, dependency lock, and every model-specific compatibility/custom-code identity.

## Deliberately unresolved activation prerequisites

Canonical preflight proved corpus/provenance readiness but did not prove the executable harness or runtime. Activation therefore remains blocked until all of the following are canonical and independently reviewed:

- an actual Backbone Tournament executor/evidence harness exists and is bound by exact commit/tree/blob identities;
- exact runtime/container/dependency identities are frozen;
- peak-VRAM and latency measurement implementation is proven against the measurement contract;
- exact external and repository artifact destinations are bound;
- gated access for Apertus and MedGemma is separately authorized by Founder decision `FD-MESC-BT-EXEC-1-GATED-ACCESS-1` and then explicitly accepted by the human operator, or a separately reviewed roster amendment supersedes this four-candidate selection before any model access;
- a separate execution-activation package binds all remaining values and passes its own exact-head and post-merge verification gates.

## Hard boundary

Canonical merge of this package, if it later occurs, authorizes only the **conditional execution contract**. It does not activate execution.

```text
MODEL_WEIGHT_ACCESS = NOT_AUTHORIZED
GATED_ACCESS_REQUEST_OR_ACCEPTANCE = NOT_AUTHORIZED
PROMPT_SERIALIZATION_TO_MODEL = NOT_AUTHORIZED
INFERENCE = NOT_AUTHORIZED
GENERATION = NOT_AUTHORIZED
TRAINING = NOT_AUTHORIZED
MODEL_RETRIEVAL = NOT_AUTHORIZED
RANKING = NOT_AUTHORIZED
WINNER_SELECTION = NOT_AUTHORIZED
BACKBONE_TOURNAMENT_EXECUTION = NOT_AUTHORIZED
```
