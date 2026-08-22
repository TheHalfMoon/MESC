# Acceptance — FD-MESC-BT-EXEC-1 Conditional Execution Authorization

Status: **DRAFT NORMATIVE CONTRACT — NO PRESENT EXECUTION AUTHORITY**

Date: 2026-08-22

Every applicable predicate is fail-closed. Unknown values, stale evidence, floating revisions, unreviewed executable code, ambiguous measurement semantics, incomplete PR replay, missing authentication, or inability to reproduce an identity => `BLOCKED`.

## A. Canonical prerequisite and Founder authentication

The authorization candidate is drafted against:

```text
AUTHORIZATION_BASE_SHA = a78bcec4cf7daccc933315df8d5ce60bca005ed9
AUTHORIZATION_BASE_TREE = a0e9b72d9535e4b0999f2a30874924896aae68c6
GH2_PREFLIGHT_RESULT_MERGE_SHA = 14a2229c184d3ef29b6032d5cb00e11ac28d1413
GH2_PREFLIGHT_ADOPTION_MERGE_SHA = a78bcec4cf7daccc933315df8d5ce60bca005ed9
GH2_ACTIVATION_RECEIPT_ID = 0454aa7f9511fa2d7a974aeae6c6153c0f56394a353c5e6675906ace26b19e94
GH2_PREFLIGHT_RESULT_MANIFEST_SHA256 = 38f6cd08c4aa650e6a110639d3a7b85297c68d454ffcc9139e518fdb3d15ef6d
GH2_R2_PROVENANCE_AUDIT_SHA256 = a8f6fd8d9c9f60c5a1a2bedc0bbb49182e635772cf50dae1e9e9028a4eb09398
GH2_CORPUS_CONFORMANCE_AUDIT_SHA256 = 842f2e0dbeaea59087223ddd94c8a95844c8f14822a16e1549e67c0c850c67f2
GH2_ADOPTION_RECORD_PATH = specs/mesc-backbone-tournament/execution-preflight-1-gh2-adoption/14a2229c184d3ef29b6032d5cb00e11ac28d1413/canonical-adoption-verification.json
GH2_ADOPTION_RECORD_GIT_BLOB_SHA = ac7d0681daa453bccffea5648d6605c119e0298d
GH2_ADOPTION_RECORD_SHA256 = 7bd7a2108b2730107a6bbcc0d8eaa915df8047c8158a2652e67b392995a33101
FOUNDER_GITHUB_LOGIN = TheHalfMoon
FOUNDER_ATTESTATION_VERSION = MESC-BT-EXEC-1-FOUNDER-ATTESTATION-V1
FOUNDER_ATTESTATION_PR = 139
```

The exact canonical GH2 adoption record above is the only record that may satisfy the preflight-adoption prerequisite. Its bytes must match both the pinned Git blob and SHA-256, and its fields must equal exactly:

```text
record_version = MESC-BT-PREFLIGHT-GH2-CANONICAL-ADOPTION-V1
decision_id = FD-MESC-BT-EXEC-1-PREFLIGHT-GH2
activation_receipt_id = 0454aa7f9511fa2d7a974aeae6c6153c0f56394a353c5e6675906ace26b19e94
result_merge_sha = 14a2229c184d3ef29b6032d5cb00e11ac28d1413
result_merge_tree = 5ba70940bc1c46e47060c3580be7645ab6f13405
reviewed_result_head_sha = d71e47742babf2bc342aae6bf0b6b27c87cef80a
preflight_result_manifest_sha256 = 38f6cd08c4aa650e6a110639d3a7b85297c68d454ffcc9139e518fdb3d15ef6d
failed_checks = []
outcome = PREFLIGHT_READY_FOR_EXECUTION_AUTHORIZATION
merge_signature_verification.verified = true
merge_signature_verification.reason = valid
```

### A.1 Exact-head Founder attestation

`founder-authorization.md` records the decision text but does not authenticate the decision by itself. After the final reviewed authorization head is stable and before Ready, require exactly one top-level PR #139 issue comment that matches all of these predicates:

```text
author.login = TheHalfMoon
created_at = updated_at
body = EXACT_FOUNDER_ATTESTATION_BODY
```

Where `EXACT_FOUNDER_ATTESTATION_BODY` is exactly five LF-separated lines, with no leading/trailing whitespace and one final LF:

```text
MESC-BT-EXEC-1-FOUNDER-ATTESTATION-V1
PR=139
HEAD_SHA=<FINAL_REVIEWED_HEAD_SHA>
DECISION=APPROVE_CONDITIONAL_CANONICAL_ADOPTION
EXECUTION_AUTHORITY=NONE_UNTIL_SEPARATE_ACTIVATION_PASS
```

`<FINAL_REVIEWED_HEAD_SHA>` must be replaced by the exact 40-lowercase-hex PR head under review. Capture the immutable GitHub numeric comment ID as `FOUNDER_ATTESTATION_COMMENT_ID`. The selected matching comment must still exist, remain authored by `TheHalfMoon`, remain unedited, and retain exact body bytes before Ready, immediately before merge, after merge, and before any later activation. A head mutation burns the prior attestation for the new head; a fresh exact-head attestation is then required. Stale attestation comments for older heads do not match and grant no authority.

Before this authorization PR may become Ready, and again immediately before merge, mechanically require:

1. `GH2_ADOPTION_RECORD_PATH` exists on canonical `main`, its Git blob equals `GH2_ADOPTION_RECORD_GIT_BLOB_SHA`, its exact bytes hash to `GH2_ADOPTION_RECORD_SHA256`, and every pinned field above matches exactly;
2. that exact adoption record has `failed_checks=[]` and `outcome=PREFLIGHT_READY_FOR_EXECUTION_AUTHORIZATION`;
3. the two pre-execution audits remain byte-identical and PASS;
4. exactly one current-head Founder attestation matches Section A.1 and its comment ID is captured;
5. canonical `main` has not moved from the PR's final-review base;
6. exact-head CI PASS;
7. exact-head CodeQL PASS;
8. fresh independent exact-head governance/security review reports no blocker;
9. unresolved blocking review threads = 0;
10. the PR delta is confined to this execution-authorization package;
11. merge uses exact expected-head protection and is followed by SHA/tree/ordered-parent/hosting-signature/path/byte/attestation verification.

Any failure => no canonical conditional authorization.

## B. Frozen scientific bindings

The following values are immutable execution inputs:

```text
CORPUS_SPEC_SHA256 = 49f554d57e29da4b1d04223d43f1630731e5f8c9b72e7a1e15f959e38c00643b
MATERIALIZED_CORPUS_ITEM_COUNT = 240
MATERIALIZED_CORPUS_SHA256 = 48fba9119f0170eb40775c75f12916e277cb3953abe22357e0b22497dadbbebd
MATERIALIZED_CORPUS_GZIP_SHA256 = 667cd68e5ccc9356321eb5857c6e9203e1320ec33d866ccf514411c211ceb632
CORPUS_MANIFEST_SHA256 = 201fa1351923a72097ff7e467b6dce2eb8bd0cfa1e88c73157788f77dd89e745
SCORING_KEYS_SHA256 = bb3524bc8dd1f05bad433c664ac3c48a5110939ac78b5ffa2ad8853f944c6318
TASK_PROMPT_BUNDLE_SHA256 = 54d9da5cf3dad58c0bf9fb28761c15d8f82568013895b8467f1cb7d532c314b7
SYSTEM_PROMPT_SHA256 = 02bb1a1fe70036c5d5299d6654618a2734aa03550506d1b023904cefc88ba867
NORMALIZED_OUTPUT_SCHEMA_SHA256 = 3e0a1523af45a61db77e3287a3333361fa26411f521321bbef0804dec7a63ed4
PARSER_CONTRACT_SHA256 = 9905096b491ddc3bce2b5d668c1f8726f638dde9dba383ac1bb755f1b6b42071
REPORT_VALIDATION_CONTRACT_SHA256 = c68fcac507e4ebc164632370d2392631b9fec9c388369eb5b8bfa495e5877c1a
SCORING_CONTRACT_SHA256 = a61471d467521b59eb62ee2825d23fa15891bb45a664360aaf2e4ef5882c7d40
PROTOCOL_CONFIG_SHA256 = 097cdd11f5389203cf432760ec316a78b12d157c0676477de69dde707e058203
PROMPT_PROTOCOL_SHA256 = a2a42aef340e27f9396b40810999d5f2c4136af467ce27ee9e3c149e3257c89c
REPORT_SCHEMA_SHA256 = cb3fc506b41cc6236959bb4a89bce249db13c99aeb0c7178ff233f6de44e026d
R2_PROVENANCE_AUDIT_SHA256 = a8f6fd8d9c9f60c5a1a2bedc0bbb49182e635772cf50dae1e9e9028a4eb09398
CORPUS_CONFORMANCE_AUDIT_SHA256 = 842f2e0dbeaea59087223ddd94c8a95844c8f14822a16e1549e67c0c850c67f2
```

No corpus substitution, rematerialization, prompt change, scoring change, parser change, post-output rule, or report-validator weakening is authorized.

## C. Candidate set, immutable revisions, and executable-code trust

The selected execution set is exactly four candidates:

### C.1 GPT-OSS 20B

```text
model_id = openai/gpt-oss-20b
model_revision = 6cee5e81ee83917806bbde320786a8fb61efebee
tokenizer_id = openai/gpt-oss-20b
tokenizer_revision = 6cee5e81ee83917806bbde320786a8fb61efebee
processor = AutoTokenizer from same pinned repository
trust_remote_code = false
precision_mode = NATIVE_MXFP4
```

### C.2 Apertus 1.5 8B

```text
model_id = swiss-ai/Apertus-v1.5-8B
model_revision = a411d838600baf0e3635a3daf66fb7c55fc97bb6
processor_id = swiss-ai/Apertus-v1.5-8B
processor_revision = a411d838600baf0e3635a3daf66fb7c55fc97bb6
trust_remote_code = false
precision_mode = BF16
transformers_compatibility_commit = 3797303dda74844e3d1f8977ff5518bb91f818b4
access = GATED
```

### C.3 Phi-4 Multimodal Instruct

```text
model_id = microsoft/Phi-4-multimodal-instruct
model_revision = 93f923e1a7727d1c4f446756212d9d3e8fcc5d81
processor_id = microsoft/Phi-4-multimodal-instruct
processor_revision = 93f923e1a7727d1c4f446756212d9d3e8fcc5d81
trust_remote_code = true
precision_mode = BF16
```

BF16 is mandatory for Phi-4 under this authorization. Activation may not substitute FP16, FP32, automatic dtype selection, or a quantized derivative.

Because `trust_remote_code=true` executes externally sourced Python, immutable revision/hash binding is necessary but not sufficient. Before activation require a canonical `PHI_REMOTE_CODE_MANIFEST` and `PHI_REMOTE_CODE_SECURITY_REVIEW`.

`PHI_REMOTE_CODE_MANIFEST` is an immutable canonical UTF-8 JSON array with no BOM and no trailing newline. The top level must be an array. Every entry must be an object with exactly the four keys `byte_length`, `git_blob_sha`, `path`, and `sha256`; duplicate JSON member names are invalid. The required scalar types and formats are:

```text
byte_length = JSON integer >= 0, serialized as plain base-10 digits
path = JSON string matching ^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$
git_blob_sha = JSON string matching ^[0-9a-f]{40}$
sha256 = JSON string matching ^[0-9a-f]{64}$
```

Each slash-separated `path` component must be neither `.` nor `..`. Because the path grammar is ASCII-only and excludes quotes and backslashes, `path`, `git_blob_sha`, and `sha256` must be serialized using their literal ASCII bytes; JSON escape sequences, non-ASCII bytes, control characters, quotes inside values, and backslashes are prohibited. Every executable/imported Phi remote-code file must have an exact Git blob SHA at the pinned `model_revision`; inability to resolve a manifest path to a Git blob is `BLOCKED` rather than represented by `null` or an omitted field. Object keys are serialized lexicographically, entries are sorted ascending by decoded `path` ASCII bytes, JSON separators are exactly `,` and `:`, insignificant whitespace is prohibited, and duplicate paths are prohibited.

Before `PHI_REMOTE_CODE_MANIFEST_SHA256` may be accepted, a duplicate-member-rejecting JSON parser must validate the top-level type, exact member set, exact scalar types/formats, path grammar, ordering, and duplicate-path prohibition. The verifier must canonically reserialize the parsed value under the rules above and require byte-for-byte equality with the supplied manifest. Only those validated canonical bytes are hashed. Malformed JSON, duplicate members, wrong scalar types, extra/missing keys, non-canonical serialization, duplicate paths, unresolved Git blobs, digest/length mismatch, or inability to reproduce the bytes => `BLOCKED`.

Every manifest `path` must also resolve in the pinned Phi Git tree as a regular-file blob whose Git tree mode is exactly `100644` or `100755`. Tree mode `120000` (symbolic link), `160000` (gitlink/submodule), `040000` (tree), any non-blob object, or any other non-regular mode => `BLOCKED`.

The trusted acquisition verifier must resolve each acquired runtime Phi code path descriptor-relatively from its approved read-only input root and open it without following symlinks, using `openat2(2)` with `RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS` plus `O_RDONLY | O_CLOEXEC | O_NOFOLLOW`, or a separately reviewed equivalent with the same atomic no-symlink guarantee. `fstat` on that exact opened descriptor must report a regular file. The verifier must compute `byte_length` and SHA-256 from that exact opened runtime object and require equality with the canonical manifest before import. The model process must import/execute that same immutable runtime object, or an object whose identity is mechanically proven to be the same verified inode/bytes on an immutable read-only mount immediately before import. Any symlink substitution, non-regular object, mutable alias, object-identity change between verification and import, or inability to prove that the executed bytes are the verified bytes => `BLOCKED`.

The remaining Phi remote-code predicates are:

- `PHI_REMOTE_CODE_MANIFEST_SHA256` is the SHA-256 of the exact validated canonical manifest bytes;
- every manifest `path` resolves at the pinned Phi `model_revision` to the exact `git_blob_sha`, and the file bytes hash to the exact `sha256` and have the exact `byte_length`;
- the executed file set equals the manifest exactly, with no additional dynamically fetched or imported remote file;
- `PHI_REMOTE_CODE_SECURITY_REVIEW` explicitly binds `PHI_REMOTE_CODE_MANIFEST_SHA256` and records an independent security-review disposition of `PASS` for every manifest file and for the complete import graph reachable from those files;
- `PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256` is the SHA-256 of the exact security-review artifact bytes;
- any executed file, import, digest, manifest, parser, or review disposition mismatch => `BLOCKED`.

Phi model execution must occur in a dedicated model process with all of these controls active before any remote-code import or model load:

```text
NETWORK_EGRESS = DENY_ALL
NETWORK_INGRESS = DENY_ALL
DNS = UNAVAILABLE_TO_MODEL_PROCESS
CREDENTIAL_ENVIRONMENT = EMPTY
CLOUD_METADATA_ACCESS = DENIED
HOST_OR_CONTAINER_CONTROL_SOCKETS = NONE
MODEL_AND_RUNTIME_INPUT_MOUNTS = READ_ONLY_ALLOWLIST_ONLY
FROZEN_GOLD_SCORING_INPUTS_VISIBLE_TO_MODEL_PROCESS = NO
WRITABLE_PATHS = ACTIVATION_SCOPED_SCRATCH_AND_OUTPUT_ONLY
REMOTE_FETCH_DURING_MODEL_PROCESS = PROHIBITED
```

Required model/runtime files must be acquired by a separately reviewed trusted acquisition step, fully identity-verified, and mounted read-only before the isolated model process starts. Hugging Face/provider tokens, GitHub credentials, cloud credentials, SSH keys, API keys, and unrelated environment secrets must not enter the model process. The activation package must bind a `PHI_SANDBOX_QUALIFICATION_SHA256` artifact proving these controls on the exact runtime. Failure to prove isolation => `BLOCKED`.

### C.4 MedGemma 1.5 4B IT

```text
model_id = google/medgemma-1.5-4b-it
model_revision = 91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b
processor_id = google/medgemma-1.5-4b-it
processor_revision = 91850547d9f0b2fdd21aa7c5f4f3d1a8a52c243b
trust_remote_code = false
precision_mode = BF16
access = GATED
```

`challenger = EMPTY`.

No candidate may be dropped, substituted, or silently replaced by a derivative/quantized checkpoint under this decision.

## D. Execution code and harness gate

`AUTHORIZATION_BASE_SHA=a78bcec4cf7daccc933315df8d5ce60bca005ed9` / tree `a0e9b72d9535e4b0999f2a30874924896aae68c6` is the exact governance/scientific baseline. It is not asserted to contain an execution-ready tournament runner.

Before activation require a separately reviewed canonical implementation that provides, at minimum:

- deterministic corpus payload projection with gold-key non-exposure;
- exact model/prompt orchestration for all four candidates;
- frozen timeout/retry semantics;
- raw response capture without mutating frozen inputs;
- strict parser/schema/scoring/report-validation invocation;
- per-attempt evidence recording;
- peak-VRAM and item-latency telemetry;
- complete artifact-manifest hashing and byte lengths;
- fail-closed behavior on runtime, identity, schema, measurement, sandbox, and remote-code-review violations;
- no tools, web, retrieval, function calls, training, or candidate-specific prompt optimization.

Define at activation:

```text
EXECUTION_CODE_SHA = <exact canonical commit containing reviewed executor>
EXECUTION_CODE_TREE = <exact tree>
EXECUTOR_PATHS_AND_BLOB_SHAS = <complete reviewed allowlist artifact>
EXECUTOR_ALLOWLIST_SHA256 = <SHA-256 of exact canonical allowlist artifact bytes>
```

`EXECUTOR_PATHS_AND_BLOB_SHAS` is an immutable canonical UTF-8 JSON array. Each entry is an object with exactly the keys `git_blob_sha` and `path`. Each decoded `path` must match `^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$`; each slash-separated component must be neither `.` nor `..`. Because this grammar is ASCII-only and excludes both `"` and `\`, every `path` must be serialized between JSON double quotes using exactly its literal ASCII bytes: JSON escape sequences (including `\uXXXX`), non-ASCII bytes, control characters, quotes, and backslashes are prohibited in `path`. Each `git_blob_sha` must match `^[0-9a-f]{40}$` and must likewise be serialized as its literal lowercase-ASCII bytes. Object keys are serialized lexicographically, entries are sorted ascending by the exact decoded `path` ASCII bytes, JSON separators are exactly `,` and `:`, insignificant whitespace is prohibited, and there is no trailing newline. Duplicate paths are prohibited. `EXECUTOR_ALLOWLIST_SHA256` is the SHA-256 of those exact canonical artifact bytes and must change whenever the executable allowlist or any allowlisted blob identity changes.

Before `EXECUTOR_ALLOWLIST_SHA256` may be accepted, parse the supplied allowlist using a JSON parser that rejects duplicate member names. Require the top level to be an array; require every entry to contain exactly one `git_blob_sha` member and exactly one `path` member; require both values to be JSON string scalars; reject extra/missing members, wrong scalar types, duplicate member names, malformed JSON, non-canonical ordering/whitespace/escaping, and duplicate decoded paths. Canonically reserialize the parsed value under the preceding rules and require byte-for-byte equality with the supplied bytes before accepting the digest. The future executor/activation conformance suite must include negative fixtures containing duplicate `path` members and duplicate `git_blob_sha` members and must prove each fixture terminates as `BLOCKED`.

Before activation, mechanically verify that `EXECUTION_CODE_SHA` resolves exactly to `EXECUTION_CODE_TREE`. Then, for every allowlist entry, resolve `path` against that exact commit/tree and require the resolved Git object to exist, be a blob, and have a Git blob SHA exactly equal to the entry's `git_blob_sha`. The independently reviewed executable/imported executor-and-harness path set must equal the allowlist exactly: no reviewed executable path may be absent, no extra allowlist entry may exist, and no executor/harness file outside the allowlist may execute or be imported. Missing paths, duplicate paths, wrong object types, Git blob mismatches, commit/tree mismatches, malformed canonical bytes, allowlist-digest mismatches, extra or omitted executable paths, or inability to reproduce any predicate => `BLOCKED`. The allowlist is therefore bound to `EXECUTION_CODE_SHA`/`EXECUTION_CODE_TREE`; it must never be accepted as independent metadata.

## E. Runtime/hardware and live telemetry binding

Target class:

```text
PROVIDER_CLASS = RunPod Secure Cloud
GPU_CLASS = NVIDIA H100 80GB HBM3
GPU_COUNT = 1
SEQUENTIAL_SINGLE_GPU_EXECUTION = REQUIRED
BASE_CONTAINER_TAG_CANDIDATE = nvcr.io/nvidia/pytorch:26.07-py3
```

The container tag is not sufficient. Before activation bind and re-attest:

```text
PROVIDER_REGION = <exact>
PROVIDER_INSTANCE_OR_POD_ID = <exact provider-visible identity>
GPU_UUID = <exact>
GPU_MODEL = NVIDIA H100 80GB HBM3
NVIDIA_DRIVER_VERSION = <exact>
CUDA_RUNTIME_VERSION = <exact>
BASE_CONTAINER_OCI_DIGEST = sha256:<exact>
PYTHON_VERSION = <exact>
PYTORCH_VERSION = <exact>
TRANSFORMERS_IDENTITY = <exact package/version or source commit>
ACCELERATION_RUNTIME_IDENTITIES = <exact>
DEPENDENCY_LOCK_SHA256 = <exact>
```

All four candidates must execute sequentially against the same activation-bound GPU identity. Provider/hardware replacement mid-run invalidates the run unless a separately reviewed recovery rule exists before execution.

No additional quantization is permitted beyond GPT-OSS's canonically recorded native MXFP4 unless separately reviewed before activation.

### E.1 Exact-instance no-model telemetry qualification

After the exact provider instance/GPU is allocated but before any candidate model-weight access or prompt serialization, run a no-model live qualification on that exact activation-bound H100. It must use the same telemetry code and container/runtime identities intended for execution and produce a deterministic evidence artifact with `RESULT=PASS`, an exact SHA-256, and raw evidence proving:

- NVML is available and identifies the exact bound `GPU_UUID` and H100 model;
- per-process GPU-memory sampling works at the configured interval and produces raw samples with monotonic timestamps;
- process-tree attribution is deterministic for a controlled non-model GPU test process;
- the co-tenant detector identifies all unexpected GPU compute processes and the qualification fails if any unexplained co-tenant process exists;
- device synchronization is executed and evidenced before terminal measurement capture;
- monotonic latency timing records non-negative finite values and can be recomputed from raw timestamps;
- raw-sample capture, serialization, hashing, and artifact-manifest inclusion all succeed.

The qualification may execute only a trivial non-model GPU workload needed to test telemetry. It must not download/load candidate weights, request/accept gated terms, serialize candidate prompts, run inference, rank candidates, or access frozen gold answers. Bind the artifact as `NO_MODEL_H100_TELEMETRY_QUALIFICATION_SHA256`. Missing or non-PASS evidence => `BLOCKED`.

## F. Measurement contract

The frozen scoring contract requires non-negative numeric `peak_vram_mb` and `median_latency_ms` but does not itself define the acquisition procedure. This authorization fixes that procedure without changing scoring.

### F.1 Peak VRAM

For each candidate:

- start monitoring immediately before model load;
- stop only after the candidate's final item reaches a terminal disposition and pending device work is synchronized;
- sample NVML per-process GPU memory for the candidate process tree at an interval no greater than 100 ms;
- aggregate all candidate-owned processes on the single bound GPU;
- `peak_vram_mb` is the maximum observed aggregate candidate-process GPU memory in MiB over that interval;
- record sampling interval, raw samples, GPU UUID, process identities, and clock source in the execution evidence;
- record framework-native peak allocated/reserved metrics when available as corroborating evidence, but NVML-derived `peak_vram_mb` is the tie-break value.

Missing NVML capability, ambiguous process attribution, co-tenant GPU workloads, missing raw samples, or a negative/non-numeric result => `BLOCKED`.

### F.2 Median latency

For every one of the 240 corpus items and each candidate:

- use a monotonic high-resolution clock;
- each generation attempt starts immediately before entering the model generation call and ends immediately when that call returns, raises, or reaches the frozen timeout;
- parser/scoring/report time is excluded;
- if one permitted infrastructure retry occurs, the item's `terminal_item_latency_ms` is the sum of generation-call elapsed times across the initial and retry attempt;
- otherwise it is the single attempt elapsed time;
- every corpus item therefore contributes exactly one non-negative numeric `terminal_item_latency_ms`, including terminal failures/timeouts;
- `median_latency_ms` is the ordinary median of the 240 terminal-item latency values after sorting numerically; for the even count 240, it is the arithmetic mean of positions 120 and 121 in one-indexed sorted order;
- store all per-attempt timings and all 240 terminal item values as raw evidence.

Any missing item latency, negative/non-finite value, wall-clock substitution, omitted retry duration, or inability to reproduce the candidate median from raw evidence => `BLOCKED`.

## G. Gated-access boundary

This package does not authorize a gated-access request or terms acceptance.

Apertus and MedGemma remain inaccessible for this execution until a separate canonical Founder decision:

`FD-MESC-BT-EXEC-1-GATED-ACCESS-1`

explicitly identifies the exact two repositories/revisions and the terms/access actions authorized.

Because `FD-MESC-BT-EXEC-1-GATED-ACCESS-1` is a separate Founder authority, its decision text must be authenticated independently from Section A.1. The future gated-access decision package must define:

```text
GATED_ACCESS_FOUNDER_GITHUB_LOGIN = TheHalfMoon
GATED_ACCESS_FOUNDER_ATTESTATION_VERSION = MESC-BT-EXEC-1-GATED-ACCESS-1-FOUNDER-ATTESTATION-V1
GATED_ACCESS_DECISION_PR_NUMBER = <exact PR number adopting the gated-access decision>
```

After that future gated-access decision's final reviewed head is stable and before that decision may become Ready, require exactly one top-level issue comment on `GATED_ACCESS_DECISION_PR_NUMBER` authored by `TheHalfMoon`, with `created_at=updated_at`, whose body is exactly five LF-separated lines with one final LF:

```text
MESC-BT-EXEC-1-GATED-ACCESS-1-FOUNDER-ATTESTATION-V1
PR=<GATED_ACCESS_DECISION_PR_NUMBER>
HEAD_SHA=<FINAL_REVIEWED_GATED_ACCESS_HEAD_SHA>
DECISION=APPROVE_GATED_ACCESS_CANONICAL_ADOPTION
GATED_ACCESS_AUTHORITY=ONLY_EXACT_REVISIONS_AND_ACTIONS_IN_DECISION
```

`<FINAL_REVIEWED_GATED_ACCESS_HEAD_SHA>` must be the exact 40-lowercase-hex head that is independently reviewed and merged. Capture the immutable numeric comment ID as `GATED_ACCESS_FOUNDER_ATTESTATION_COMMENT_ID`. A head mutation burns that attestation for the new head. Before any access/terms action is treated as authorized, immediately before the gated-access merge, after its merge, and again before execution activation, mechanically verify the comment still exists, is authored by `TheHalfMoon`, remains unedited, matches the exact body/head, and that the gated-access canonical merge's second parent equals the attested reviewed head. Missing, edited, deleted, wrong-author, wrong-head, duplicate matching attestations, or merge/head mismatch => `BLOCKED`.

Credentials, tokens, private keys, and session secrets must never be committed to the repository or copied into governance records.

The separate gated-access decision must define and canonically adopt two immutable, non-secret human access-attestation artifacts before activation. Their exact SHA-256 values remain unbound here and must be fixed only after that decision is canonical:

```text
APERTUS_ACCESS_ATTESTATION_SHA256 = <exact SHA-256 of canonical Apertus access-attestation bytes>
MEDGEMMA_ACCESS_ATTESTATION_SHA256 = <exact SHA-256 of canonical MedGemma access-attestation bytes>
```

Each attestation artifact must be included in the exact canonical `FD-MESC-BT-EXEC-1-GATED-ACCESS-1` merge and must explicitly bind the human attester identity, exact model repository and revision, repository-access state, and terms/access state authorized by that decision, without storing credentials, tokens, cookies, session material, or secret values. The gated-access decision must define the attestation artifact's exact path, canonical byte serialization, Git blob identity, and SHA-256 before the corresponding access/terms action is treated as usable evidence. The activation verifier must prove the selected gated-access decision merge contains those exact immutable bytes and that the two SHA-256 values recompute exactly. Post-hoc, mutable, external-only, or unhashed access statements do not satisfy this contract.

Before activation of this four-candidate authorization require:

```text
GATED_ACCESS_FOUNDER_DECISION = CANONICAL
GATED_ACCESS_FOUNDER_ATTESTATION = AUTHENTICATED_EXACT_HEAD
APERTUS_EXACT_REVISION_ACCESS = ATTESTED
MEDGEMMA_EXACT_REVISION_ACCESS = ATTESTED
CREDENTIAL_DISCLOSURE_IN_REPOSITORY = NONE
```

If gated access is not separately authorized, its exact-head Founder attestation is not authenticated, either attestation hash is unbound/missing, either attestation is not contained in the pinned decision merge, or the exact access/terms state cannot be verified, activation is `BLOCKED`. A smaller subset requires a separately reviewed Founder amendment; it is not an automatic fallback.

## H. Attempt bounds

Exactly one tournament execution episode may be activated under this decision.

For each candidate/item pair:

```text
PRIMARY_ATTEMPTS = 1
MAX_INFRASTRUCTURE_RETRIES = 1
MAX_TOTAL_ATTEMPTS = 2
PARSE_RETRIES = 0
SCHEMA_RETRIES = 0
SEMANTIC_RETRIES = 0
TIMEOUT_SECONDS_PER_ATTEMPT = 180
```

At most `4 * 240 * 2 = 1920` generation attempts can exist, and only infrastructure failures may trigger the second attempt under the frozen protocol. Every item has exactly one final terminal disposition.

A full tournament rerun requires a new Founder decision.

## I. Artifact destination and activation identity contract

The future execution-activation receipt must contain an `identity_preimage` object with exactly these keys, shown without leading whitespace and in lexical order:

```text
apertus_access_attestation_sha256
authorization_merge_sha
authorization_merge_tree
decision_id
execution_code_sha
execution_code_tree
executor_allowlist_sha256
founder_attestation_comment_id
gated_access_decision_merge_sha
gated_access_founder_attestation_comment_id
medgemma_access_attestation_sha256
phi_remote_code_manifest_sha256
phi_remote_code_security_review_sha256
phi_sandbox_qualification_sha256
receipt_version
runtime_binding_sha256
telemetry_qualification_sha256
```

Values must bind the exact canonical authorization merge, reviewed execution-code commit/tree, `EXECUTOR_ALLOWLIST_SHA256`, the exact current-head Founder attestation comment ID selected under Section A.1, canonical gated-access decision merge, the exact authenticated `GATED_ACCESS_FOUNDER_ATTESTATION_COMMENT_ID`, `APERTUS_ACCESS_ATTESTATION_SHA256`, `MEDGEMMA_ACCESS_ATTESTATION_SHA256`, `PHI_REMOTE_CODE_MANIFEST_SHA256`, exact Phi security-review and sandbox qualification artifact SHA-256 values, exact canonical runtime-binding artifact SHA-256, exact no-model live telemetry qualification SHA-256, `decision_id=FD-MESC-BT-EXEC-1-ACTIVATION-1`, and `receipt_version=MESC-BT-EXEC-1-ACTIVATION-RECEIPT-V1`.

The following equality is mandatory and removes any naming ambiguity:

```text
apertus_access_attestation_sha256 = APERTUS_ACCESS_ATTESTATION_SHA256
executor_allowlist_sha256 = EXECUTOR_ALLOWLIST_SHA256
gated_access_founder_attestation_comment_id = GATED_ACCESS_FOUNDER_ATTESTATION_COMMENT_ID
medgemma_access_attestation_sha256 = MEDGEMMA_ACCESS_ATTESTATION_SHA256
phi_remote_code_manifest_sha256 = PHI_REMOTE_CODE_MANIFEST_SHA256
phi_remote_code_security_review_sha256 = PHI_REMOTE_CODE_SECURITY_REVIEW_SHA256
phi_sandbox_qualification_sha256 = PHI_SANDBOX_QUALIFICATION_SHA256
telemetry_qualification_sha256 = NO_MODEL_H100_TELEMETRY_QUALIFICATION_SHA256
```

The `identity_preimage` field schema is normative and complete. No field is nullable. Required JSON scalar types and value constraints are exactly:

```text
apertus_access_attestation_sha256 = JSON string matching ^[0-9a-f]{64}$
authorization_merge_sha = JSON string matching ^[0-9a-f]{40}$
authorization_merge_tree = JSON string matching ^[0-9a-f]{40}$
decision_id = JSON string exactly FD-MESC-BT-EXEC-1-ACTIVATION-1
execution_code_sha = JSON string matching ^[0-9a-f]{40}$
execution_code_tree = JSON string matching ^[0-9a-f]{40}$
executor_allowlist_sha256 = JSON string matching ^[0-9a-f]{64}$
founder_attestation_comment_id = JSON integer >= 1
gated_access_decision_merge_sha = JSON string matching ^[0-9a-f]{40}$
gated_access_founder_attestation_comment_id = JSON integer >= 1
medgemma_access_attestation_sha256 = JSON string matching ^[0-9a-f]{64}$
phi_remote_code_manifest_sha256 = JSON string matching ^[0-9a-f]{64}$
phi_remote_code_security_review_sha256 = JSON string matching ^[0-9a-f]{64}$
phi_sandbox_qualification_sha256 = JSON string matching ^[0-9a-f]{64}$
receipt_version = JSON string exactly MESC-BT-EXEC-1-ACTIVATION-RECEIPT-V1
runtime_binding_sha256 = JSON string matching ^[0-9a-f]{64}$
telemetry_qualification_sha256 = JSON string matching ^[0-9a-f]{64}$
```

All string values above are ASCII-only and must be serialized using their literal bytes; JSON escape sequences are prohibited. Comment IDs must be serialized as plain base-10 JSON integers with no sign and no leading zero. Duplicate members, alternate scalar types, `null`, extra/missing members, or inability to reproduce the exact scalar representation => `BLOCKED`.

`runtime_binding_sha256` is the SHA-256 of an immutable canonical UTF-8 JSON object named `RUNTIME_BINDING`, with no BOM and no trailing newline. Its complete key set, shown in lexical order, is:

```text
acceleration_runtime_identities
base_container_oci_digest
cuda_runtime_version
dependency_lock_sha256
external_runtime_parent_device_id
external_runtime_parent_inode
external_runtime_parent_mount_id
external_runtime_parent_path
gpu_count
gpu_model
gpu_uuid
nvidia_driver_version
provider_class
provider_instance_or_pod_id
provider_region
python_version
pytorch_version
repository_checkout_root_device_id
repository_checkout_root_inode
repository_checkout_root_mount_id
repository_checkout_root_path
repository_checkout_sha
repository_checkout_tree
repository_result_parent_device_id
repository_result_parent_inode
repository_result_parent_mount_id
sequential_single_gpu_execution
transformers_identity
```

Required runtime-binding types and invariants are:

```text
acceleration_runtime_identities = JSON array with >= 1 unique non-empty ASCII identity strings, sorted by exact bytes
base_container_oci_digest = JSON string matching ^sha256:[0-9a-f]{64}$
cuda_runtime_version = non-empty JSON ASCII string
dependency_lock_sha256 = JSON string matching ^[0-9a-f]{64}$
external_runtime_parent_device_id = JSON integer >= 0
external_runtime_parent_inode = JSON integer >= 0
external_runtime_parent_mount_id = JSON integer >= 0
external_runtime_parent_path = JSON string exactly /workspace/mesc-bt-exec-1
gpu_count = JSON integer exactly 1
gpu_model = JSON string exactly NVIDIA H100 80GB HBM3
gpu_uuid = non-empty JSON ASCII string
nvidia_driver_version = non-empty JSON ASCII string
provider_class = JSON string exactly RunPod Secure Cloud
provider_instance_or_pod_id = non-empty JSON ASCII string
provider_region = non-empty JSON ASCII string
python_version = non-empty JSON ASCII string
pytorch_version = non-empty JSON ASCII string
repository_checkout_root_device_id = JSON integer >= 0
repository_checkout_root_inode = JSON integer >= 0
repository_checkout_root_mount_id = JSON integer >= 0
repository_checkout_root_path = JSON string matching ^/[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$
repository_checkout_sha = JSON string matching ^[0-9a-f]{40}$
repository_checkout_tree = JSON string matching ^[0-9a-f]{40}$
repository_result_parent_device_id = JSON integer >= 0
repository_result_parent_inode = JSON integer >= 0
repository_result_parent_mount_id = JSON integer >= 0
sequential_single_gpu_execution = JSON boolean true
transformers_identity = non-empty JSON ASCII string
```

For every runtime-binding string described only as non-empty ASCII, allowed bytes are `0x20` through `0x7e` except `"` and `\`; control characters, non-ASCII bytes, JSON escapes, and empty strings are prohibited. `RUNTIME_BINDING` must use lexically sorted object keys, exact `,` and `:` separators, no insignificant whitespace, and duplicate-member rejection. Its `repository_checkout_sha` must resolve exactly to `repository_checkout_tree`; all Section E runtime/hardware values must equal the corresponding runtime-binding fields.

The runtime-binding chronology is normative. Before `RUNTIME_BINDING` is finalized or hashed, the exact `external_runtime_parent_path`, `repository_checkout_root_path`, and fixed repository-result parent `specs/mesc-backbone-tournament/execution-result-1` must already exist as directories. Their provisioning, if needed, is outside the activation executor and must occur before this binding step without model-weight access or prompt serialization. The activation verifier must open all three through the descriptor-relative bootstrap in Section I.1, record their exact `(device_id,inode,mount_id)` triples, and only then construct, canonicalize, and hash `RUNTIME_BINDING`. No field in `RUNTIME_BINDING` may depend on `<ACTIVATION_ID>` or on any directory/object created after `ACTIVATION_ID` is derived. A duplicate-member-rejecting parser must validate the exact key set/types/invariants, canonically reserialize, require byte-for-byte equality, and recompute `runtime_binding_sha256`; any mismatch => `BLOCKED`.

Define canonical activation identity serialization as UTF-8 JSON with object keys sorted lexicographically, separators exactly `,` and `:`, no insignificant whitespace, and no trailing newline. A duplicate-member-rejecting parser must require exactly the key set above, the exact scalar schema above, and byte-for-byte equality after canonical reserialization; duplicate member names, extra/missing keys, alternate serialization, or any bound-artifact hash/value mismatch => `BLOCKED`. Before hashing `identity_preimage`, the verifier must independently recompute every referenced Git SHA/tree relation, SHA-256 artifact digest, Founder-attestation comment ID binding, gated-access Founder-attestation binding, and `runtime_binding_sha256` from the exact canonical bytes selected for activation. Then:

```text
ACTIVATION_ID = lowercase_hex(SHA256(canonical_json(identity_preimage)))
ACTIVATION_ID_REGEX = ^[0-9a-f]{64}$
```

The activation receipt must store that exact `identity_preimage` and exact `ACTIVATION_ID`. A supplied identifier that does not recompute exactly, does not match `ACTIVATION_ID_REGEX`, or differs by case is invalid. No operator-selected, timestamp-derived, random, path-derived, or mutable identifier is permitted.

Only after successful recomputation and regex validation may paths be derived exactly:

```text
EXTERNAL_RUNTIME_ROOT = /workspace/mesc-bt-exec-1/<ACTIVATION_ID>/
REPOSITORY_RESULT_ROOT = specs/mesc-backbone-tournament/execution-result-1/<ACTIVATION_ID>/
```

### I.1 Race-safe path confinement

The two activation roots must be bootstrapped before they may be treated as trusted. The three parent/root descriptors bound in `RUNTIME_BINDING` are prerequisites to deriving `ACTIVATION_ID`; the activation-root directories themselves do not yet exist at that stage.

Starting from a pre-opened descriptor for filesystem `/`, the activation verifier must resolve the bound `external_runtime_parent_path` and `repository_checkout_root_path` one component at a time with descriptor-relative no-symlink/no-magic-link operations. Deliberate mount transitions needed to reach the bound external parent or repository checkout root are allowed only during this bootstrap stage and only when the final opened descriptors' `(device_id,inode,mount_id)` values exactly equal `RUNTIME_BINDING`; symlinks, magic links, non-directory components, unexpected path components, missing bound directories, or descriptor-identity mismatch => `BLOCKED`.

From the verified repository checkout-root descriptor, resolve the already-existing fixed relative parent `specs/mesc-backbone-tournament/execution-result-1` one validated component at a time. Every component must already exist, be opened without following symlinks, and be a directory. Creation of this bound parent during activation bootstrap is prohibited. The resulting repository-result-parent descriptor's `(device_id,inode,mount_id)` must equal the values already bound in `RUNTIME_BINDING`. From the verified external-runtime-parent descriptor and repository-result-parent descriptor onward, `RESOLVE_NO_XDEV` is mandatory and no mount transition is permitted.

The final `<ACTIVATION_ID>` directory under each trusted parent must not pre-exist. Create each directory exactly once descriptor-relatively; `EEXIST` or any pre-existing entry => `BLOCKED`. Immediately reopen each new activation root with `openat2(2)` using `RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS | RESOLVE_NO_XDEV`, require `fstat` to report a directory on the trusted parent's mount, and retain those verified descriptors as the only roots from which descendant operations may proceed. Failure to establish either root descriptor exactly as specified => `BLOCKED` before model access.

A separate pre-open `realpath`/containment check is not sufficient. Every directory traversal, directory creation, file creation, and file open under both activation roots must be performed descriptor-relative to those verified trusted root directory descriptors using race-safe no-symlink resolution.

All generated path components under either activation root must satisfy this normative grammar before any filesystem operation:

```text
PATH_COMPONENT_REGEX = ^[a-z0-9][a-z0-9._-]{0,127}$
RELATIVE_PATH = PATH_COMPONENT ( "/" PATH_COMPONENT )*
```

`PATH_COMPONENT` validation means exact byte validation against `PATH_COMPONENT_REGEX`. Accepted components are lowercase ASCII only. `/` is the only path separator and may appear only between components. Unicode, uppercase ASCII, empty components, `.`, `..`, backslash, NUL, drive prefixes, alternate separators, and any component that fails the regex are invalid. Invalid input must be rejected; it must never be Unicode-normalized, case-folded, lowercased, separator-rewritten, or otherwise transformed into a valid path. Duplicate/collision comparison is exact byte comparison of the already validated ASCII `RELATIVE_PATH`, so no locale-dependent or Unicode case-folding/normalization algorithm participates in the security decision.

On the activation Linux runtime, the normative mechanism is `openat2(2)` with `RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS | RESOLVE_NO_XDEV` for path resolution. Crossing any mount point, bind mount, or different filesystem beneath either trusted activation root is categorically prohibited; an `EXDEV`/mount-traversal result is `BLOCKED`. File creation must additionally use no-follow/exclusive creation semantics appropriate to the operation; directory creation must operate one `PATH_COMPONENT` at a time relative to a trusted parent descriptor and reopen/verify the created directory descriptor before descending. Magic links, symlinks, mount traversal, descriptor/root mismatch, resolution outside the trusted root, a pre-existing exact-byte collision with a different activation artifact, or any race-safe resolution failure => `BLOCKED` before model access.

The filesystem mutation surface under both activation roots is closed and explicit. The only permitted path-creating mutations are descriptor-relative `mkdirat` for a single already validated `PATH_COMPONENT` under a trusted parent descriptor, and descriptor-relative `openat2` creation of a new regular file using `O_CREAT | O_EXCL | O_NOFOLLOW` together with the required `RESOLVE_BENEATH | RESOLVE_NO_SYMLINKS | RESOLVE_NO_MAGICLINKS | RESOLVE_NO_XDEV` constraints. After a file descriptor is safely opened, writes, truncation to the intended new file, synchronization, and close may operate on that descriptor; they must not perform a second pathname lookup.

`rename`, `renameat`, `renameat2`, `link`, `linkat`, `symlink`, `symlinkat`, `unlink`, `unlinkat`, hard-link creation, symbolic-link creation, `mknod*`, `mount*`, bind mounts, and pathname-based mutation fallbacks are prohibited for both activation roots. No object may be moved, linked, or renamed into either root from another location, between the two roots, or between directories after creation. Temporary-file-plus-rename publication is therefore prohibited; the final validated artifact path must be selected before exclusive creation. If an implementation requires replacement, cleanup, rename, link, unlink, symlink, or any other pathname mutation not explicitly permitted above, activation is `BLOCKED` pending a separately reviewed contract change. A failed run may leave activation-scoped partial artifacts, but those bytes grant no authority and must not be adopted as canonical results.

If the exact runtime cannot provide `openat2` with `RESOLVE_NO_XDEV` and the other resolution guarantees above, activation is `BLOCKED` unless a separately reviewed equivalent mechanism proves the same descriptor-relative atomic confinement against TOCTOU races **and** a categorical no-cross-mount invariant for both trusted roots. Any equivalent must also preserve the closed mutation surface above; an equivalent that reintroduces pathname-based rename/link/unlink/symlink or cross-mount behavior is not equivalent. The executor must never perform a security decision using a check-then-open pathname sequence.

The executor must keep frozen inputs read-only and place generated evidence only under the external runtime root during execution.

The external artifact manifest must enumerate every generated raw response, normalized record, per-attempt timing record, VRAM sample file, candidate report, validation output, and final report with:

```text
relative_path
sha256
byte_length
media_type
producer_step
candidate_id_or_null
item_id_or_null
```

Every manifest `relative_path` must satisfy the exact ASCII `RELATIVE_PATH` grammar in Section I.1 byte-for-byte and be opened/created only through that section's race-safe descriptor-relative mechanism. No normalization or case-folding is permitted. Duplicate paths or exact-byte collisions are prohibited.

No output digest may be invented before execution.

Repository promotion is a later, separately reviewed result-adoption operation. Raw/generated artifacts may be promoted only through the exact result contract defined before activation; activation itself must not mutate canonical `main`.

## J. Activation package

Canonical merge of this authorization package does not activate execution.

A separate execution-activation package is mandatory. It must bind all values left open above and include an activation receipt whose state is initially non-executing. Before that activation can authorize the first model-access operation, mechanically prove:

1. this authorization package's canonical merge SHA/tree and exact package blobs;
2. the selected Founder attestation comment still exists, is unedited, is authored by `TheHalfMoon`, and exactly binds the reviewed authorization head that became the canonical merge's second parent;
3. unchanged four-candidate set and model revisions;
4. exact tokenizer/processor/custom-code identities and exact BF16 execution precision for Phi-4, Apertus, and MedGemma plus native MXFP4 for GPT-OSS;
5. canonical executor implementation SHA/tree/blob allowlist and exact `EXECUTOR_ALLOWLIST_SHA256`, including duplicate-member-rejecting parsing, canonical reserialization equality, negative duplicate-member fixture PASS, proof that `EXECUTION_CODE_SHA` resolves to `EXECUTION_CODE_TREE`, every allowlisted path resolves at that exact commit/tree to the exact recorded Git blob SHA, and the reviewed executable/imported path set equals the allowlist exactly;
6. exact canonical `PHI_REMOTE_CODE_MANIFEST` bytes/schema/parser/reserialization, exact `PHI_REMOTE_CODE_MANIFEST_SHA256`, exact pinned-revision path→Git-blob/tree-mode/SHA-256/byte-length equality, no-symlink regular-file runtime-object verification, executed remote-code set equality, and independent `PASS` security-review artifact;
7. exact Phi offline/secretless/read-only sandbox qualification artifact `PASS` on the activation runtime;
8. exact canonical `RUNTIME_BINDING` bytes/schema/parser/reserialization, exact `runtime_binding_sha256`, exact runtime/container/dependency identities, exact repository checkout SHA/tree, and exact pre-existing descriptor/bootstrap identity bindings;
9. exact provider/GPU identity;
10. exact-instance no-model H100 telemetry qualification `PASS`, with `telemetry_qualification_sha256 = NO_MODEL_H100_TELEMETRY_QUALIFICATION_SHA256`;
11. measurement harness implementation and deterministic fixture/self-test evidence;
12. exact `identity_preimage` scalar-schema validation, recomputation of every bound Git/hash/comment/runtime value, exact `ACTIVATION_ID` recomputation, regex validation, secure two-root bootstrap, exact ASCII path-grammar/collision/no-cross-mount validation, closed filesystem-mutation-surface validation, and race-safe descriptor-relative artifact-root confinement proof;
13. canonical gated-access Founder decision, its independently authenticated exact-head `GATED_ACCESS_FOUNDER_ATTESTATION_COMMENT_ID`, exact immutable human access-attestation bytes for both gated models contained in that decision merge, and exact `APERTUS_ACCESS_ATTESTATION_SHA256` / `MEDGEMMA_ACCESS_ATTESTATION_SHA256` bindings in `identity_preimage`;
14. both preflight audits remain PASS and digest-identical;
15. frozen protocol/report/scoring/corpus digests remain unchanged;
16. exact-head CI and CodeQL PASS;
17. fresh independent exact-head governance/security review with no blocker;
18. unresolved blocking threads = 0;
19. Ready then fresh post-Ready reconciliation;
20. expected-head merge;
21. post-merge canonical SHA/tree/ordered-parent/hosting-signature/path/byte/attestation verification **and**, from the exact activation receipt and bound artifacts as stored in the canonical activation merge, duplicate-member-rejecting parsing and canonical reserialization, recomputation of `runtime_binding_sha256` and every other bound digest/value, recomputation of `ACTIVATION_ID` from the final canonical `identity_preimage` bytes, exact equality with the receipt's `ACTIVATION_ID`, and exact equality between that ID and both activation-root directory names. Any post-merge mismatch => `BLOCKED`; no model access may begin before this post-merge recomputation passes.

Only after all twenty-one pass may activation state become:

```text
MODEL_WEIGHT_ACCESS = AUTHORIZED_FOR_BOUND_EXECUTION_ONLY
PROMPT_SERIALIZATION_TO_MODEL = AUTHORIZED_FOR_BOUND_EXECUTION_ONLY
INFERENCE = AUTHORIZED_FOR_BOUND_EXECUTION_ONLY
BACKBONE_TOURNAMENT_EXECUTION = AUTHORIZED_FOR_ONE_BOUND_EPISODE
```

Training and fine-tuning remain prohibited.

## K. Authorization-package PR gates and merge authentication

This package itself is governance-only. Keep its PR Draft until the unchanged exact head passes:

```text
DELTA = exactly README.md, acceptance.md, founder-authorization.md, plan.md under this package
SOURCE_RUNTIME_WORKFLOW_CHANGES = 0
CI = PASS
CODEQL = PASS
FRESH_INDEPENDENT_REVIEW = NO_BLOCKER
UNRESOLVED_BLOCKING_THREADS = 0
FOUNDER_ATTESTATION_MATCH_COUNT_FOR_EXACT_HEAD = 1
FOUNDER_ATTESTATION_AUTHOR = TheHalfMoon
FOUNDER_ATTESTATION_EDITED = NO
CANONICAL_MAIN = unchanged final-review base
```

Then mark Ready and perform a fresh reconciliation. Merge only using the fully reviewed expected head SHA.

The GitHub hosting signature is an integrity/authenticity signal for GitHub's merge infrastructure; it is **not** treated as the Founder signature. Founder authorization is authenticated separately by Section A.1. Canonicality therefore does not depend on a specific merge actor login. After merge require all of the following:

- canonical `main` equals the merge SHA returned by GitHub;
- ordered parents equal `[PREMERGE_MAIN_SHA, REVIEWED_HEAD_SHA]`;
- merge tree/path scope matches the reviewed candidate and all four package blobs equal reviewed bytes;
- hosting `verification.verified=true` and `verification.reason=valid`;
- hosting `verification.signature` and `verification.payload` are non-null;
- the selected `FOUNDER_ATTESTATION_COMMENT_ID` still exists with exact author/body/head and remains unedited;
- no merge mechanism bypassed `expected_head_sha=REVIEWED_HEAD_SHA`.

Failure => `FD-MESC-BT-EXEC-1` remains noncanonical/non-authoritative. These checks do not alter repository branch protection and do not reinterpret the GitHub hosting signature as a Founder signature.

## L. Hard stop

Even after this authorization package becomes canonical:

```text
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
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

Do not execute the tournament from this package. Proceed only to separately reviewed executor/runtime/gated-access/activation closure.
