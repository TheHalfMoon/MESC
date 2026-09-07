# MRL-0801 Active Candidate Set Evidence V1

Status: **REPOSITORY-SIDE CONTRACT ONLY / NO REAL ASSET EVIDENCE / NO EXECUTION AUTHORITY**

## Purpose

Experiment-0 freezes more than one active foundation candidate while the MRL machine-state
layer retains one canonical evidence slot for `MRL-0801`. This contract defines the
multi-candidate evidence kind admitted through that one slot without weakening the existing
single-model kind.

```text
KIND = mesc.mrl.real_preflight.model_weights_set.v1
TASK = MRL-0801
SCHEMA = MRL-REAL-PREFLIGHT-EVIDENCE-V1
```

The existing `mesc.mrl.real_preflight.model_weights.v1` kind remains valid and unchanged for
single-model programs.

## Payload

The candidate-set payload is exactly:

```text
candidate_roster_sha256
candidates
```

Every candidate record is exactly:

```text
access_authorization_sha256
artifact_identity_sha256
asset_custody_sha256
asset_present
model_id
revision
weights_sha256
```

The parser requires:

- non-empty `candidates`;
- `asset_present=true` for every candidate;
- immutable 40-character lowercase Git revisions;
- exact 64-character lowercase SHA-256 identities;
- unique `model_id` values;
- unique `(model_id, revision)` identities;
- strict `(model_id, revision)` ordering;
- no extra or missing candidate fields;
- exact canonical JSON bytes and existing outer MRL trust admission.

## Experiment-0 binding

The current Phase-0 roster freezes:

```text
Qwen/Qwen3.8-27B
revision = 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0


google/gemma-4-31B-it
revision = 842da3794eaa0b77d5f08bae87a17459d91ff475
```

This repository-side parser does not claim that any future candidate-set envelope is complete
merely because its `candidate_roster_sha256` is syntactically valid. Independent real-evidence
verification must establish that the roster digest identifies the exact canonical frozen
roster and that the candidate array contains every and only active candidate before any
production trust admission can occur.

## Authority boundary

This contract does not:

- download or inspect model weights;
- create custody or access receipts;
- populate `MRL-0801`;
- mutate `TRUSTED_MRL_REAL_PREFLIGHT_EVIDENCE_SHA256`;
- activate Google Colab or any GPU;
- run inference or Experiment-0;
- authorize training, SFT, LoRA, QLoRA, Unsloth, or weight mutation.

The next legitimate successor after this contract is canonically merged and post-merge
qualified is a separately bounded acquisition/custody authorization for the exact frozen
active candidate revisions. Real snapshot acquisition and evidence capture happen only after
that successor becomes active.
