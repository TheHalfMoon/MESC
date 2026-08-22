# Plan — FD-MESC-BT-EXEC-1 Conditional Execution Authorization

Status: **DRAFT — GOVERNANCE ONLY**

Date: 2026-08-22

## Phase 1 — Canonicalize the conditional authorization contract

1. Start from exact canonical main `a78bcec4cf7daccc933315df8d5ce60bca005ed9` / tree `a0e9b72d9535e4b0999f2a30874924896aae68c6`.
2. Publish only this four-file package.
3. Verify exact path scope and immutable preflight bindings.
4. Obtain fresh exact-head CI, CodeQL, and independent review.
5. After the final reviewed head is stable, publish the exact authenticated Founder attestation required by `acceptance.md`; any head mutation invalidates it.
6. Keep Draft until all gates, including the authenticated exact-head Founder attestation, pass.
7. After Ready, repeat all exact-head/base/review/attestation gates.
8. Merge only with expected-head protection.
9. Verify canonical merge SHA/tree/parents/hosting signature/path/blob equality and revalidate the Founder attestation against the reviewed head.

No model access or execution occurs in Phase 1.

## Phase 2 — Build and qualify the executor + measurement harness

Create a separate implementation package for the Backbone Tournament executor/evidence harness.

Requirements:

- no model-weight access during implementation qualification;
- use fixtures/mocks only for model-facing behavior;
- implement frozen payload projection, prompt construction, timeout/retry semantics, strict parser/scoring/report validation, raw/normalized evidence capture, artifact hashing, NVML VRAM collection, and monotonic latency measurement;
- test gold-key non-exposure and frozen-input read-only behavior;
- implement fail-closed process isolation for model execution: no network egress, no credentials/secrets in the model process, no host/container sockets, read-only mounts limited to reviewed model/runtime inputs, and only activation-scoped writable scratch/output;
- for Phi-4, enumerate every remotely sourced executable file, bind its path and digest, and require independent security-review coverage for every executed file before activation;
- bind exact source paths/blob SHAs and dependency lock;
- independently security/reproducibility review the exact candidate;
- canonically adopt the implementation before activation.

## Phase 3 — Runtime lock, telemetry qualification, and gated-access decision

Without accessing model weights or serializing model prompts:

1. resolve the exact RunPod Secure Cloud H100 80GB deployment identity available for activation;
2. bind immutable OCI digest for the selected container baseline;
3. freeze Python/PyTorch/Transformers/accelerator dependencies;
4. bind the Apertus compatibility commit and the exact Phi remote-code file hashes plus their independent security-review allowlist;
5. run fixture-only measurement-harness self-tests;
6. on the exact candidate H100 runtime, run a **no-model live telemetry qualification** proving NVML process-tree sampling, GPU UUID binding, co-tenant detection, raw-sample capture, CUDA/device synchronization, and monotonic timing; record exact evidence identities and require PASS;
7. verify the execution sandbox can enforce network-egress denial, secretless environment, read-only reviewed mounts, no host/container sockets, and activation-scoped writable scratch without loading model weights;
8. prepare external/repository artifact destination identities;
9. separately review Founder decision `FD-MESC-BT-EXEC-1-GATED-ACCESS-1`.

The no-model live qualification may allocate the target compute class but must not download/load candidate weights, request/accept gated terms, or serialize prompts. The gated-access decision is a separate human-governance act. Do not request or accept terms merely because this plan exists.

## Phase 4 — Execution activation

Create a separate activation package that binds all exact values required by `acceptance.md`, including the canonical executor, exact runtime, exact H100 identity, live telemetry qualification evidence, Phi security-review allowlist, sandbox enforcement evidence, Founder attestation identity, gated-access decision, and deterministic activation ID.

Keep it non-executing until exact-head CI/CodeQL, independent review, Ready/post-Ready reconciliation, expected-head merge, and post-merge canonical verification all pass.

Only the verified activation may authorize model access and the one bounded tournament episode.

## Phase 5 — One bounded tournament

Only after Phase 4 activation authority exists:

- access only the four exact pinned candidates;
- execute 240 frozen items per candidate;
- permit at most one infrastructure retry per item;
- preserve all raw/normalized/measurement evidence;
- keep Phi remote-code execution within the reviewed offline/secretless/read-only sandbox;
- do not train or fine-tune;
- do not add tools, web, retrieval, function calls, or prompt optimization;
- validate the final report using the frozen schema/validator;
- apply frozen role gates and tie-breakers only after all candidate outputs are terminal.

## Phase 6 — Result review and canonical adoption

Tournament outputs are not canonical merely because execution completed.

A separate result package must bind exact execution activation, artifact manifest, candidate reports, negative results, scoring/validation evidence, role-selection outcome, and all raw/normalized identities. Require independent review and canonical adoption before any Compact or Flagship/Reasoner winner claim becomes authoritative.

## Permanent constraints

No force-push, rebase, destructive history rewrite, corpus substitution, hidden prompt optimization, silent candidate substitution, credential disclosure, PHI, training, or fine-tuning.
