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

Before any model byte download:

1. retrieve metadata for every and only authorized file;
2. require every metadata record to resolve to the exact authorized revision;
3. compute the exact allowlist byte count;
4. execute the canonical storage-capacity preflight.

Immediately before downloading each file, retrieve fresh metadata again. Its `(path, commit_sha, byte_count, etag, etag_algorithm)` identity must exactly equal the preflight record. Only the ephemeral download location may change.

This rule prevents expired signed locations from forcing a weaker metadata policy and fails closed if immutable remote identity changes unexpectedly.

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

The executor requires no-follow directory-descriptor support and opens the destination once. The opened device/inode identity is bound for the transaction. File existence checks, exclusive partial-file creation, atomic publication, cleanup, and rollback operate descriptor-relative to that opened directory rather than by resolving the destination pathname again. Authorized V1 file paths are one canonical POSIX basename each.

The executor never overwrites existing asset files. Every file is streamed to an exclusive no-follow partial file with restrictive mode, fully hashed and size-checked, then atomically published with a same-directory no-replace hard link. The partial link is removed only after the target link exists. If a racing target appears, publication fails without modifying that target.

Before and after the path-based canonical SafeTensors custody handoff, the destination pathname must still resolve to the exact opened device/inode. If the pathname is concurrently removed, replaced, redirected, or changed to another directory, the transaction fails. Published model files carry an internal transaction-owned `(device, inode)` identity that is not serialized into provenance; rollback attempts deletion only while the directory entry still resolves to that exact regular-file identity.

Receipt publication by the CLI is supplied as the acquisition transaction finalizer. Therefore a late custody/provenance reconciliation error or receipt-output write failure occurs while the destination descriptor remains open and triggers the same descriptor-relative model-file rollback. No path-based post-return snapshot rollback is trusted.

If any later file, metadata refresh, remote-content check, SafeTensors custody verification, provenance reconciliation, destination-identity check, or transaction finalizer fails, rollback removes each published model file only while its name still resolves to the exact transaction-owned regular-file identity captured at publication. A name that has been replaced or rebound by another actor is preserved rather than deleted. Transaction partials are likewise removed only while their captured identity still matches. The core executor does not delete arbitrary entries merely because they appeared during a finalizer; finalizer-owned outputs must use their own ownership-bound cleanup, as the CLI receipt publisher already does. A cleanup race therefore remains `BLOCKED` and may require operator inspection; it never converts into success. No resume, mutable overwrite, or partial-snapshot acceptance exists in V1.

## Storage preflight

The exact byte count is the sum of authoritative metadata for every authorized file. Available storage is read from the opened destination directory descriptor rather than by re-resolving its pathname. Before acquisition, the executor calls the existing canonical MRL-0801 storage preflight:

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

The supporting acquisition file identities are reconciled against the custody receipt's exact local SHA-256 and byte-count manifest before success is returned.

## Supporting acquisition provenance

A successful execution emits one deterministic canonical supporting receipt that binds remote identities, storage preflight, exact executor code identity, and the resulting local custody identities. It contains no local path, hostname, signed URL, or query string.

The receipt explicitly records:

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

These fields document this executor's bounded activity. They do not grant later authority.

This receipt is not `mesc.mrl.real_preflight.model_weights_set.v1`; it is an input to later independent verification of that envelope.

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

Each receipt output parent directory must already exist as a real directory; the CLI never creates missing receipt-output directories. The parent is resolved, opened once with no-follow directory flags, and bound to its exact device/inode identity. Receipt existence checks, exclusive creation, and failure cleanup are descriptor-relative to that bound parent. Parent pathname identity is rechecked before and after publication, so replacing the validated parent cannot redirect a receipt into the repository or raw snapshot.

Every receipt file created by the transaction is also bound to its exact device/inode identity. Finalizer reconciliation requires the published name to continue referencing that exact regular file, and rollback removes a receipt only while the name still references the transaction-created inode. A racing or replacement entry owned by another actor is never deleted as transaction cleanup.

Receipt outputs are created exclusively and are published through the executor transaction finalizer. If receipt publication fails, the executor rolls back the model files through the still-open destination descriptor; the CLI removes only transaction-owned receipt outputs through their bound parent descriptors.

User-visible success output contains stable subject/digest fields only. Failures emit one generic blocked message and do not print signed URLs, local paths, credentials, or provider error bodies.

## CI boundary

Repository tests inject fake Hub transports. CI must never download model weights or depend on live Hub availability. Transport tests synthesize redirect/metadata responses, including the external-redirect `Content-Length` ambiguity case. Security tests cover exact runtime receipt types, preloaded transitive module rejection, untracked-work-tree rejection, descriptor-relative publication, concurrent destination replacement, missing receipt-parent no-mutation, receipt-output parent replacement, foreign receipt-entry preservation, and late transaction-finalizer rollback.

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

The production real-preflight trust registry remains unchanged until a separately reviewed genuine-evidence admission mutation occurs.
