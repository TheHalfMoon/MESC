# MESC Backbone Tournament — Execution Implementation 1

Status: **DRAFT IMPLEMENTATION SLICE — NO EXECUTION AUTHORITY**

Date: 2026-08-22

## Exact canonical base

```text
IMPLEMENTATION_BASE_SHA = ab4d64f8708f649d33e494a4bed0272a2a526d9c
IMPLEMENTATION_BASE_TREE = 8fb0ccb9377a97b024e674b99f4d5ff89e34099e
AUTHORIZATION_DECISION = FD-MESC-BT-EXEC-1
AUTHORIZATION_STATE = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

## Slice 1 scope

This first implementation slice addresses only the canonical executor/harness allowlist primitive required by Section D of `execution-authorization-1/acceptance.md`.

It adds:

- `src/medscale/mesc/_bt_executor_allowlist_v1.py`
- `tests/test_mesc_bt_executor_allowlist_v1.py`

The implementation:

1. parses `EXECUTOR_PATHS_AND_BLOB_SHAS` with duplicate-member rejection;
2. requires the exact closed entry schema (`git_blob_sha`, `path`);
3. enforces ASCII path grammar, dot-component prohibition, lowercase 40-hex Git blob identities, path uniqueness, and canonical path order;
4. canonically reserializes and requires byte-for-byte equality, including the Section D requirement of no trailing newline;
5. computes SHA-256 only over accepted exact bytes;
6. verifies injected Git object metadata is a `blob` with mode exactly `100644` or `100755` and the exact allowlisted Git blob SHA;
7. fails closed on resolver failures, non-blobs, symlink/gitlink/tree/unapproved modes, and blob mismatches.

Git resolution is injected. This slice does not fetch, checkout, import, execute, or mutate allowlisted paths.

## Deliberately not implemented or authorized by this slice

This slice does **not** claim Section D complete. It does not yet implement or authorize:

- the Backbone Tournament model executor;
- real-model adapters or model loading;
- model-weight access or retrieval;
- gated-access request or terms acceptance;
- prompt serialization to a model;
- inference or generation;
- scoring, ranking, or winner selection;
- live NVML telemetry qualification;
- RunPod allocation or runtime binding;
- Phi remote-code acquisition/import/execution;
- activation receipt creation;
- Backbone Tournament execution;
- training or fine-tuning.

Later implementation slices must separately supply and qualify the remaining Section D executor/evidence harness, exact runtime and telemetry controls, Phi remote-code manifest/security/sandbox evidence, gated-access decision, artifact destinations, and the separate execution-activation package.

## Qualification boundary

Qualification for this slice is fixture-only. Tests may use deterministic in-memory JSON bytes and injected fake Git-object metadata. They must not contact model providers, Hugging Face, RunPod, external networks, or model runtimes.

Canonical adoption of this slice, if it later occurs after exact-head review, grants **no model-access or execution authority**. It only makes the reviewed allowlist primitive available to a future, separately activated executor.
