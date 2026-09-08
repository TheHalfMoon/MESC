# MESC MRL-0801 Public Hugging Face Acquisition Provenance V1

Status: **IMPLEMENTATION CONTRACT / NO REAL ASSET EVIDENCE GENERATED**

## Purpose

This contract defines the only repository-provided network executor for the already-authorized MRL-0801 model-weight acquisition scope. It bridges two identities that must not be conflated:

1. immutable remote Hugging Face file identity at the authorized revision; and
2. the existing descriptor-safe local SafeTensors artifact/custody identity.

A successful network transfer without both identities is not MRL-0801 evidence.

## Canonical implementation unit

```text
ISSUE = #389
IMPLEMENTATION_BASE_MAIN_SHA = 8a051ed4cc91a4b74b516cfeaf9e7cbc3b7d90a3
IMPLEMENTATION_BASE_MAIN_TREE = 311388e408ac14f9a3c72898f903099d2713403a
BASE_POST_MERGE_CI_RUN = 34157078622 / SUCCESS
BASE_POST_MERGE_CODEQL_RUN = 34157078595 / SUCCESS
ACCESS_AUTHORIZATION_SHA256 = af69087c6968c3bddb28556002a2a89fcf18932506a55d1eb7d6ff318e21b9d7
CANDIDATE_ROSTER_SHA256 = 2968f2c71fd0de4a9ef9b5f6e5d4d58d75ce0f2cf5af8a56840031d85f694489
```

This implementation unit is derived from the exact canonical authorization merge above. It does not silently roll forward to a different authorization, roster, candidate revision, or file allowlist.

## Authority boundary

The executor accepts only an exact runtime `MRL0801AcquisitionAuthorization` instance parsed from the canonical authorization artifact. Duck-typed or look-alike authorization objects are rejected before repository identity inspection or network access. Independent provenance revalidation likewise requires exact canonical acquisition-provenance and custody receipt runtime types before reading receipt properties. The executor cannot broaden candidates, revisions, files, credential use, terms acceptance, remote-code policy, model loading, inference, GPU use, Experiment-0 execution, training, trust admission, or MRL-0801 population.

## Executor repository identity

Before the first Hub request, the executor itself—not its caller—must establish:

```text
repository_root is the exact Git work-tree root
Git-visible tracked and untracked work-tree state is clean
executor_code_commit = git rev-parse HEAD
executor_code_tree = git rev-parse HEAD^{tree}
executor source path = src/medscale/mesc/_mrl_0801_hf_acquisition_v1.py
current executor source bytes = Git object bytes at HEAD
executor_source_sha256 = SHA-256(current exact source bytes)
```

The CLI rejects every preloaded `medscale` or `medscale.*` module before exact-source import. After import, it verifies every loaded `medscale` module has a real source file under the exact checked-out `src` root and that each source file's bytes equal the corresponding `HEAD` Git object bytes. This prevents stale or foreign transitive canonicalization/custody modules from silently participating in acquisition.

The execution commit/tree/source identities are written into the supporting provenance receipt. A later independent validator resolves the recorded historical commit, requires its tree to equal the receipt tree, requires that commit to be an ancestor of the review checkout, and hashes the executor source bytes from Git history. Caller-supplied SHA strings are not accepted as execution identity.

## Public transport boundary

All remote access is public and unauthenticated. The implementation does not read or send Hugging Face tokens, cookies, netrc credentials, Git credentials, provider credentials, or environment proxy credentials. The urllib transport installs an empty `ProxyHandler` rather than inheriting credential-bearing environment proxies.

The transport timeout is a per-open/socket-operation bound, not a total transfer deadline. It must be finite, positive, and no greater than `3600` seconds. Values outside that range are rejected before transport use, and platform timeout-conversion `OverflowError` failures are normalized into the same fail-closed acquisition transport errors as other network failures.

The initial source is always an exact revision-pinned:

```text
https://huggingface.co/<model>/resolve/<revision>/<authorized-file>
```

Metadata must establish the exact remote commit, exact byte count, immutable content etag, and current download location.

Hub-internal redirects are followed with their query strings preserved. An external/CDN redirect is admissible only when the redirect response itself supplies all of:

```text
X-Repo-Commit
X-Linked-Etag
X-Linked-Size
```

`Content-Length` on a 3xx response is never accepted as the target object size because it can describe the redirect body rather than the model file. On a final HTTP 200 response, `Content-Length` is the exact response-object size and may be used with the final immutable etag and repository commit headers.

Every redirect/download location must remain credential-free HTTPS under the bounded Hugging Face domains. Localhost, `.local`, literal IP locations, unapproved domains, and embedded user information are rejected.

Signed or CDN locations are ephemeral transport data and never enter a canonical receipt or user-visible executor output.

## Two-pass metadata rule

Before any remote metadata request or model byte download, the executor must first prove that unnamed-file atomic publication actually works on the bound destination filesystem. Under accepted ADR-0037, the operator supplies a dedicated pre-existing external capability-witness root on the same filesystem device. The executor opens the unnamed witness from the bound transaction directory, atomically links it into that dedicated witness root with `linkat(..., AT_EMPTY_PATH)`, verifies the linked inode identity, and retains the zero-byte witness permanently. The model destination therefore remains empty and unchanged by capability proof. The CLI performs the same source-filesystem proof for each bound receipt-output parent using a dedicated receipt witness root. A successful `O_TMPFILE` open or exported `linkat` symbol alone is insufficient.

After successful retained-witness proof, the operational two-pass metadata sequence is authorized:

1. retrieve metadata for every and only authorized file;
2. require every metadata record to resolve to the exact authorized revision;
3. compute the exact allowlist byte count;
4. execute the canonical storage-capacity preflight.

Metadata is retrieved again immediately before each file download. Its `(path, commit_sha, byte_count, etag, etag_algorithm)` identity must exactly equal the preflight record. Only the ephemeral download location may change. This rule prevents expired signed locations from weakening immutable remote identity binding.

## Remote content identities

The executor accepts only the immutable identities returned by the pinned Hub file metadata surface:

```text
64 lowercase hex -> sha256
40 lowercase hex -> git_blob_sha1
```

For `sha256`, downloaded raw bytes must hash to the remote identity.

For `git_blob_sha1`, the executor verifies the Git object identity over:

```text
b"blob " + decimal_byte_count + b"\0" + raw_bytes
```

Every acquired file additionally receives an ordinary raw-byte SHA-256 for supporting provenance.

## Destination and transaction semantics

Raw model roots must be outside the MESC repository and outside any discovered Git work tree. The destination must already exist as a real empty directory. The raw input path and every existing path component are checked before symlink resolution; an existing symlink anywhere in the destination path is rejected. The resolved destination is checked again against repository/Git boundaries.

The executor requires no-follow directory-descriptor support and opens the destination once. The opened device/inode identity is bound for the transaction. Authorized V1 file paths are one canonical POSIX basename each. Public namespace mutation is intentionally limited to atomic descriptor publication; the executor performs no automatic public-entry unlink cleanup or rollback.

The executor never overwrites existing asset files. Capability proof opens an unnamed `O_TMPFILE` through the already-bound destination descriptor but publishes the random hidden zero-byte witness only into the separately bound same-filesystem witness root. The witness is verified and retained; the destination is rechecked as empty before remote metadata begins. Each authorized model file is then streamed into a same-filesystem unnamed file, byte-counted and content-verified, and atomically linked no-replace to its final authorized basename.

Before and after the canonical SafeTensors custody handoff, the destination pathname must still resolve to the exact opened device/inode. If the pathname is concurrently removed, replaced, redirected, or changed to another directory, the transaction fails. Published model files may retain an internal transaction identity for verification, but that identity is never used to justify a non-atomic `stat`-then-`unlink` sequence.

Receipt publication follows the same ADR-0037 rule. Each already-bound receipt-output parent proves its source-filesystem publication capability by creating an unnamed file there and atomically linking the witness into the dedicated same-filesystem receipt witness root. The receipt target remains unused during proof. Receipt bytes are later published atomically no-replace.

Once any model or receipt name is publicly published, automatic deletion, replacement, exchange, repair, resume, or reuse is prohibited. Any later failure remains `BLOCKED`; already-published transaction residue is retained for operator inspection and no success receipt is returned. A subsequent attempt requires a separately inspected empty model destination and unused receipt names.

## Storage preflight

The exact byte count is the sum of authoritative metadata for every authorized file, and available storage is read from the opened destination directory descriptor rather than by re-resolving its pathname. The canonical condition is:

```text
AVAILABLE_BYTES >= ALLOWLIST_BYTES + max(10 GiB, ceil(ALLOWLIST_BYTES * 10%))
```

Rounded model-card size labels are never used for this decision.

## Local custody handoff

After every authorized remote file is verified and atomically present, the executor calls:

```text
generate_mrl_0801_asset_custody_receipt(...)
```

That existing path performs descriptor-safe full local SafeTensors verification, requires the observed manifest to equal the exact authorization allowlist, and derives the canonical:

```text
artifact_identity_sha256
weights_sha256
asset_custody_sha256
```

The network executor does not introduce a competing artifact identity.

Supporting acquisition file identities must be reconciled against the custody receipt's exact local SHA-256 and byte-count manifest before success can be returned.

## Supporting acquisition provenance

A successful operational execution emits one deterministic canonical supporting receipt binding remote identities, storage preflight, exact executor code identity, and resulting local custody identities. It contains no local path, hostname, signed URL, or query string.

The receipt contract records:

```text
public_unauthenticated = true
network_accessed = true
credentials_used = false
terms_accepted = false
remote_code_allowed = false
model_loading_performed = false
tokenizer_loading_performed = false
inference_performed = false
gpu_execution_performed = false
training_performed = false
weight_mutation_performed = false
trust_registry_mutation_performed = false
mrl_0801_population_performed = false
```

These fields document bounded activity only. They do not grant later authority.

This receipt is not `mesc.mrl.real_preflight.model_weights_set.v1`; it is only an input to later independent verification of that envelope.

## Independent revalidation

`validate_mrl_0801_hf_acquisition_provenance(...)` must, without downloading weights again:

1. require exact canonical acquisition-provenance, custody, and authorization runtime types;
2. bind the receipt to an exact currently authorized candidate;
3. verify the recorded historical executor commit/tree/source against Git history;
4. rerun the canonical local custody validator over the currently present model root;
5. reconcile acquisition file identities with the reverified custody manifest; and
6. re-query every pinned Hub file and require current `(path, revision, byte_count, etag, algorithm)` metadata to equal the acquisition record.

Parsing a canonical supporting receipt without these external/local checks is never possession or trust evidence.

## CLI boundary

The acquisition entrypoint performs a full Git-visible clean-work-tree precheck before importing repository acquisition code, rejects all preloaded `medscale*` modules, prepends only the exact repository `src` root, and verifies every loaded `medscale` source file against the exact `HEAD` Git object bytes. Snapshot and receipt output paths are outside the MESC repository, receipts are outside the raw snapshot root, and existing symlink path components are rejected.

Each receipt output parent directory must already exist as a real directory; the CLI never creates missing receipt-output directories. The parent is resolved, opened once with no-follow directory flags, and bound to its exact device/inode identity. A separately supplied pre-existing receipt witness root is bound outside the repository and raw snapshot. Each receipt-output parent proves same-filesystem `O_TMPFILE` publication by linking a retained witness into that dedicated witness root before model acquisition begins.

Receipt outputs are created and published exclusively through their bound parent descriptors. Automatic deletion of a published receipt name is prohibited because an identity check followed by `unlink` cannot atomically prove that the removed name still denotes the transaction-created inode. Late receipt/finalizer failure retains published receipt and model residue and returns `BLOCKED`.

User-visible failure emits a generic blocked message and must not print signed URLs, local paths, credentials, or provider error bodies. Success output is constrained to stable subject/digest fields only.

## CI boundary

Repository tests inject fake Hub transports. CI must never download model weights or depend on live Hub availability. Transport tests synthesize redirect/metadata responses, including the external-redirect `Content-Length` ambiguity case, timeout-boundary rejection, and fail-closed metadata/download `OverflowError` conversion. CLI tests verify an oversized finite timeout exits with status `2`, emits only the generic blocked stderr message, and emits no traceback. Security tests cover exact runtime receipt types, preloaded transitive module rejection, untracked-work-tree rejection, descriptor-relative publication, concurrent destination replacement, missing receipt-parent no-mutation, receipt-output parent replacement, foreign receipt-entry preservation, dedicated same-filesystem retained model/receipt witnesses, foreign witness replacement preservation, successful proof reaching the metadata phase, racing target preservation, late-failure retained residue, and retry rejection against non-empty failed destinations.

## Non-authority statement

A successful acquisition receipt does not mean:

```text
MRL_0801_TRUSTED
MRL_0801_CLOSED
MRL_REAL_EXPERIMENT_READY
MODEL_LOADING_AUTHORIZED
INFERENCE_AUTHORIZED
GPU_AUTHORIZED
TRAINING_AUTHORIZED
TRAINING_READY
```

Repository qualification emits no real asset evidence. A later genuine operational acquisition may emit a supporting receipt only after canonical merge and post-merge qualification. The production real-preflight trust registry remains unchanged until a separately reviewed genuine-evidence admission mutation occurs.