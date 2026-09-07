# MRL-0801 Acquisition and Custody Authorization V1

Status: **BOUNDED FOUNDER/OPERATOR AUTHORIZATION CONTRACT / NO ASSET ACQUIRED / NO EXECUTION AUTHORITY**

## Purpose

This package implements Issue #387, the separately bounded authorization required before any
real model-weight acquisition or custody evidence generation for Experiment-0 MRL-0801.

It authorizes only exact, revision-pinned, allowlisted SafeTensors weight acquisition and
local custody/identity evidence generation for the two frozen active candidates. It does not
authorize model or tokenizer loading, inference, generation, GPU execution, Experiment-0,
training, fine-tuning, SFT, LoRA, QLoRA, Unsloth, production evidence trust admission, or
MRL-0801 population.

## Exact canonical base

```text
AUTHORIZED_BASE_MAIN_SHA = 07b98baded530b7914dc0d1d89534cfcf6ee568a
AUTHORIZED_BASE_MAIN_TREE = 339125e96fa38c2cdab4b2f93c0a634f333f2587
POST_MERGE_CI_RUN = 34139543250
POST_MERGE_CI = SUCCESS
ISSUE = #387
```

The authorization is valid only for the repository state above. It does not silently roll
forward when canonical `main` changes.

## Canonical authorization artifact

The exact authorization artifact is:

```text
specs/mesc-experiment-0/mrl-0801-acquisition-custody-authorization-v1.json
```

Its exact canonical UTF-8 bytes include one terminal LF and have SHA-256:

```text
ACCESS_AUTHORIZATION_SHA256 = af69087c6968c3bddb28556002a2a89fcf18932506a55d1eb7d6ff318e21b9d7
```

That digest is the canonical source for each later MRL-0801 candidate record's
`access_authorization_sha256`. The digest is not embedded in its own preimage.

The parser accepts only this exact closed document. Any candidate addition, revision change,
allowlist expansion, policy relaxation, stale base mutation, or non-canonical encoding fails
closed.

## Frozen roster binding

```text
CANDIDATE_ROSTER_PATH = specs/mesc-experiment-0/candidate-roster-v1.json
CANDIDATE_ROSTER_SHA256 = 2968f2c71fd0de4a9ef9b5f6e5d4d58d75ce0f2cf5af8a56840031d85f694489
```

Authorized candidates are exactly:

```text
Qwen/Qwen3.8-27B
revision = 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0
role = PREFERRED_FOUNDATION_CANDIDATE


google/gemma-4-31B-it
revision = 842da3794eaa0b77d5f08bae87a17459d91ff475
role = PRIMARY_CHALLENGER
```

`microsoft/Phi-4-multimodal-instruct` remains deferred and is not authorized by this
contract.

## Exact acquisition allowlists

Acquisition is weight-only and allowlist-only. Mutable branch downloads, unrestricted
repository snapshots, and files outside these lists are prohibited.

### Qwen/Qwen3.8-27B

```text
model.safetensors.index.json
model-00001-of-00018.safetensors
model-00002-of-00018.safetensors
model-00003-of-00018.safetensors
model-00004-of-00018.safetensors
model-00005-of-00018.safetensors
model-00006-of-00018.safetensors
model-00007-of-00018.safetensors
model-00008-of-00018.safetensors
model-00009-of-00018.safetensors
model-00010-of-00018.safetensors
model-00011-of-00018.safetensors
model-00012-of-00018.safetensors
model-00013-of-00018.safetensors
model-00014-of-00018.safetensors
model-00015-of-00018.safetensors
model-00016-of-00018.safetensors
model-00017-of-00018.safetensors
model-00018-of-00018.safetensors
```

### google/gemma-4-31B-it

```text
model.safetensors.index.json
model-00001-of-00002.safetensors
model-00002-of-00002.safetensors
```

The lists were reverified against the exact frozen Hugging Face revisions before this unit
was opened. The acquisition executor must still query exact authoritative per-file size
metadata at those pinned revisions immediately before acquisition. Published rounded model
size labels are not custody or capacity evidence.

## Storage-capacity preflight

Before any authorized acquisition starts, exact authoritative sizes for every allowlisted
file must be known. Let `ALLOWLIST_BYTES` be their exact total raw-byte size.

The required available storage is:

```text
ALLOWLIST_BYTES + max(10 GiB, ceil(ALLOWLIST_BYTES * 10%))
```

This threshold reserves fail-closed temporary/margin space. Acquisition must not begin if
available storage is below the threshold.

The repository implementation calculates and validates the threshold but intentionally does
not manufacture remote file-size observations. The real acquisition environment must supply
the authoritative exact size total.

## Artifact identity reuse

MRL-0801 `artifact_identity_sha256` must reuse the existing canonical SafeTensors identity
receipt:

```text
HfSafeTensorsArtifactIdentity.verifier_receipt_sha256
```

The existing receipt already binds:

```text
model_id
immutable revision
identity version
layout
exact file manifest
weights_sha256
```

No competing model-artifact identity is introduced here.

MRL-0801 `weights_sha256` remains the existing SafeTensors V1 canonical content identity
derived from exact raw-byte index/shard identities.

## Canonical custody receipt

This unit gives `asset_custody_sha256` one concrete deterministic meaning without exposing
machine-local paths or secrets.

A custody receipt may be generated only by:

1. parsing the exact current authorization artifact;
2. selecting one exact authorized model ID/revision;
3. running the existing descriptor-safe full local SafeTensors byte verifier over an
   already-present local root;
4. requiring the observed SafeTensors manifest to equal the authorization allowlist exactly;
5. emitting exact canonical JSON with no local path, credential, secret, provider token, or
   mutable branch identity.

The receipt schema is:

```text
MESC-MRL-0801-ASSET-CUSTODY-RECEIPT-V1
```

Its canonical fields bind:

```text
access_authorization_sha256
artifact_identity_sha256
asset_present = true
candidate_roster_sha256
credentials_included = false
exact file manifest and raw-byte identities
layout
local_only = true
model_id
network_accessed = false
path_included = false
remote_code_allowed = false
revision
total_byte_count
verification_method
weights_sha256
```

`asset_custody_sha256` is ordinary SHA-256 over the exact canonical custody-receipt bytes,
including the terminal LF.

This design does not make invented JSON genuine custody. Genuine custody requires that the
generator actually completes the existing full-byte local SafeTensors verification against
an already-present authorized root. A hand-authored receipt or digest has no authority and
must not be added to production trust.

Parsing custody receipt bytes proves only canonical byte/schema/internal-digest consistency.
Independent validation of an existing receipt requires the actual local `model_root`, reruns
the descriptor-safe full-byte SafeTensors verifier, and requires the current file identities,
`weights_sha256`, and `artifact_identity_sha256` to match the receipt exactly. Parsing alone
must never be treated as proof of possession.

## Acquisition boundary

This authorization requires:

```text
immutable revisions only
exact allowlisted files only
raw snapshots outside Git and outside tracked repository paths
storage-capacity preflight before acquisition
no terms acceptance
no credential leakage
no remote code
```

This authorization explicitly prohibits:

```text
trust_remote_code=True
mutable branch download
unrestricted snapshot download
terms acceptance
credential logging or repository persistence
model loading
tokenizer loading
inference
generation
GPU execution
Experiment-0 execution
training
fine-tuning
SFT
LoRA
QLoRA
Unsloth
weight mutation
TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256 mutation
MRL-0801 population before genuine evidence exists
```

A connected Hugging Face account or available model metadata does not establish acquisition,
local possession, or custody.

## Trust and task-state boundary

This unit intentionally does not change:

```text
specs/mesc-research-loop-v1/real-preflight-evidence/MRL-0801.json
specs/mesc-research-loop-v1/tasks.md
TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256
MRL_REAL_EXPERIMENT_READY
TRAINING_READY
```

MRL-0801 remains unsatisfied until actual authorized asset acquisition occurs, genuine local
custody/identity receipts exist for every and only active candidate, a canonical
`mesc.mrl.real_preflight.model_weights_set.v1` envelope is assembled, independent evidence
verification succeeds, and a separate governance mutation admits that genuine evidence.

## Google Colab and Unsloth boundary

This authorization does not activate Google Colab and does not authorize Unsloth. The
canonical sequence remains:

```text
this authorization merge + post-merge qualification
→ real snapshot acquisition/custody
→ genuine MRL-0801 evidence
→ MRL-0802..MRL-0808 genuine evidence
→ MRL-0809 / MRL_REAL_EXPERIMENT_READY decision
→ real Experiment-0 on Google Colab
→ foundation selection
→ separate training authorization
→ Google Colab + Unsloth training
```

Experiment-0 remains NO-TRAINING.

## Qualification

This unit is not canonical authority until its exact final PR head passes the live repository
requirements, receives fresh independent substantive review with all material findings
resolved, merges by the active `main` ruleset using `merge` with expected-head protection,
and then passes fresh post-merge qualification on canonical `main`.

Real acquisition must not begin before that post-merge qualification succeeds.
