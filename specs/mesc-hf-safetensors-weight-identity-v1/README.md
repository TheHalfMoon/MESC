# MESC Hugging Face SafeTensors Weight Identity V1

Status: **IMPLEMENTATION / LOCAL-ONLY MODEL-ARTIFACT IDENTITY / NO TRAINING EXECUTION**

Canonical base:

```text
BASE_MAIN_SHA = e72846be53129781dac2a3631366c94aaeeaffae
BASE_MAIN_TREE = d5647a940e188fb70770c7c2984ecd62fc837eaa
PR_186 = CLOSED_CANONICAL
TRAINING_EXECUTOR_V1 = CANONICAL
TRAINING_EXECUTION = NOT_PERFORMED
```

## Purpose

The canonical training contracts already bind `model_id`, immutable `revision`, and
`weights_sha256`, but intentionally left the filesystem meaning of `weights_sha256`
undefined. The local-asset attestation therefore had to inject a backend-specific verifier.

This package closes that ambiguity for the first supported concrete training family:
already-local Hugging Face **SafeTensors** model roots.

It does not download, load, deserialize, infer with, or train a model. It only inspects
already-local weight files and emits a deterministic identity compatible with
`LocalModelAssetVerifier`.

## Scope

Exactly three paths belong to this implementation:

```text
specs/mesc-hf-safetensors-weight-identity-v1/README.md
src/medscale/mesc/_training_hf_safetensors_identity_v1.py
tests/test_mesc_training_hf_safetensors_identity_v1.py
```

No dependency, lockfile, workflow, CLI, dataset, launch-plan, readiness, authorization,
model registry, or training recipe is changed.

## Canonical meaning of `weights_sha256`

For this V1 contract, `weights_sha256` is **not**:

- SHA-256 of a local directory path;
- SHA-256 of a tar/zip archive;
- SHA-256 of one arbitrarily selected shard;
- a Hugging Face cache blob id;
- a Hub ETag;
- a Git commit id; or
- an identity that depends on where a machine stores the model.

It is the deterministic `content_hash(...)` of this canonical payload:

```json
{
  "identity_version": "MESC-HF-SAFETENSORS-WEIGHT-IDENTITY-V1",
  "layout": "single|sharded",
  "files": [
    {
      "path": "<canonical root-relative basename>",
      "kind": "index|weight",
      "sha256": "<ordinary raw-byte SHA-256>",
      "byte_count": 1
    }
  ]
}
```

Canonical file ordering is:

- single layout: `model.safetensors`;
- sharded layout: `model.safetensors.index.json` first, followed by shard basenames in
  lexicographic order.

`model_id` and immutable `revision` are intentionally **not** part of `weights_sha256`.
Identical weight payloads therefore retain identical weight identity even when mirrored.
The verifier receipt separately binds:

```text
model_id
revision
weights_sha256
exact file manifest
identity_version
```

This preserves the distinction between content identity and repository provenance.

## Supported layouts

V1 supports exactly two SafeTensors layouts.

### Single file

```text
model.safetensors
```

No other root-level `*.safetensors` file may coexist with it. Extension detection is
case-insensitive for the purpose of rejecting additional payloads, so a file such as
`ORPHAN.SAFETENSORS` cannot bypass the single-layout boundary.

The canonical manifest contains exactly one `weight` entry.

### Sharded

```text
model.safetensors.index.json
model-00001-of-000NN.safetensors
...
model-000NN-of-000NN.safetensors
```

The index must be valid UTF-8 JSON and may contain only:

```text
metadata
weight_map
```

`weight_map` must be a non-empty JSON object. Every tensor key must be a non-empty
NUL-free string. Every referenced shard must use the exact
`model-NNNNN-of-NNNNN.safetensors` basename form.

All referenced shards must:

- declare the same total shard count;
- form one complete contiguous sequence from `00001` to `000NN`;
- exist as non-empty regular files;
- not be symlinks; and
- be the complete set of root-level `*.safetensors` files.

The raw index bytes participate in `weights_sha256` as an `index` file entry. This is
intentional: the index determines how the loader maps tensors to shards, so changing the
load map changes the canonical loadable weight artifact even if shard bytes are unchanged.

## SafeTensors-only boundary

V1 rejects root-level weight files ending in:

```text
.bin
.pt
.pth
```

The first concrete MESC training backend must not silently fall back to pickle-compatible
weight formats. SafeTensors is the only admitted weight serialization for this contract.

Future weight formats require their own versioned identity contract rather than widening V1.

## Filesystem rules

`model_root` must be an existing non-symlink directory.

Before any root enumeration or child-file inspection, the verifier opens `model_root` as a
retained read-only, no-follow directory descriptor. Root enumeration, child `stat`, and
child `open` operations are then performed descriptor-relatively. The original path is not
re-resolved for traversal. A concurrent replacement of the supplied path therefore cannot
redirect verification to a different directory.

V1 requires platform support for no-follow directory descriptors plus descriptor-relative
`open`, `stat`, and directory listing. A platform without those primitives fails closed
rather than falling back to path-based traversal.

Every participating file must be:

- a direct child of the pinned `model_root` descriptor;
- addressed by one canonical POSIX basename;
- non-empty;
- a regular file; and
- non-symlinked.

Hashing uses bounded streaming reads for weight files. The index is capped at 16 MiB and is
read only because it must be parsed.

For each participating file, the verifier records identity before open, from the open
descriptor, after reading, and after close. Device, inode, size, nanosecond mtime, and
nanosecond ctime must remain equal across those observations. Including ctime prevents a
same-size content mutation from being hidden by restoring mtime after the write.

The pinned root descriptor is also observed before and after successful verification using
the same device/inode/size/mtime/ctime identity tuple. Root-entry mutation or replacement
detected during verification fails closed.

The identity never contains the absolute or local filesystem path.

## Concrete local verifier

`HfSafeTensorsLocalModelVerifier` implements the existing structural
`LocalModelAssetVerifier` protocol.

Given:

```text
role
model_root
TrainingRunPlan
```

it derives the canonical SafeTensors identity and returns one
`LocalModelAssetObservation` bound to the exact run-plan `model_id` and `revision`.

It always records:

```text
network_accessed = false
remote_code_allowed = false
gated_terms_accepted = false
```

because this verifier performs no operation that can make any of those observations true.

The upstream local-asset attestation remains responsible for comparing observed
`weights_sha256` to the exact expected `TrainingRunPlan.weights_sha256`.

## Deliberate exclusions

This package does not verify or load:

- `config.json`;
- tokenizer files;
- chat templates;
- processor files;
- PEFT adapters;
- optimizer state;
- scheduler state;
- checkpoints;
- model code;
- custom kernels; or
- any remote repository object.

Those are runtime/backend concerns. The next local Hugging Face SFT backend must validate
its required non-weight local files independently and must use `local_files_only=True` or
equivalent local-only APIs.

## Security and authority boundary

This implementation performs no:

- Hub/provider access;
- network access;
- authentication or credential read;
- gated-term acceptance;
- model retrieval;
- remote-code execution;
- model/tokenizer deserialization;
- inference;
- generation;
- GPU execution; or
- training/fine-tuning.

A matching local model identity is necessary for execution but does not grant execution
authority. Runtime qualification and training authorization remain separate canonical
upstream gates.

## Default CI

Default CI uses tiny fake SafeTensors byte files and JSON fixtures only.

It does not import or execute:

```text
torch
transformers
trl
peft
accelerate
bitsandbytes
safetensors
```

and it does not require a GPU or model download.

## Acceptance

This gate is complete only when exact-head CI and review prove at least:

- path-independent deterministic identity;
- `weights_sha256` independence from `model_id` and immutable revision;
- content mutation changes identity;
- same-size mutation with restored mtime fails closed;
- concurrent `model_root` replacement cannot redirect verification and fails closed when detected;
- single-file layout acceptance;
- canonical sharded layout acceptance;
- raw index mutation changes identity;
- missing, extra, ambiguous, malformed, or non-contiguous shards fail closed;
- case-variant additional SafeTensors files fail closed;
- symlinks and non-regular files fail closed;
- pickle-compatible root weight files fail closed; and
- the concrete verifier emits an exact local-only `LocalModelAssetObservation`.

## Next repository gate

After this contract is canonical, the next planned implementation is the optional
**local-only Hugging Face SFT backend** for `TrainingBackend`.

Before that backend is merged, current official Transformers, TRL, PEFT, and Accelerate
APIs must be checked against the repository's pinned dependency surface. The backend must
remain incapable of implicit Hub access, remote-code execution, credential use, or gated
term acceptance and must consume only already-attested local assets.
