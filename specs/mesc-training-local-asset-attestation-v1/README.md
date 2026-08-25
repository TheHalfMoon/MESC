# MESC Local Training Asset Attestation V1

Status: **IMPLEMENTATION / LOCAL-ONLY PREFLIGHT / NO TRAINING EXECUTION**

Canonical base:

```text
BASE_MAIN_SHA = 18e85d8d01a8341dcaaa14fc4edec78650ccc9e7
PR_184 = CLOSED_CANONICAL
TRAINING_CORPUS_BINDING = CANONICAL
TRAINING_EXECUTION = NOT_PERFORMED
```

## Purpose

The launch plan binds exact model, revision, weight, dataset, runtime-qualification, and
training-authorization identities. The corpus binding freezes the exact canonical training
JSONL bytes. Neither proves that the machine about to run training actually has matching
local assets.

This package closes that boundary without downloading anything. It verifies the corpus
file directly and requires an explicitly injected local model verifier to return an exact,
content-addressed model identity receipt.

## Why model verification is injected

The existing canonical field is `weights_sha256`, but previous contracts do not define it
as a hash of one file, a Hugging Face directory tree, a sharded SafeTensors manifest, or an
archive. This package therefore does **not** silently invent a new hash algorithm and call
it canonical.

A backend-specific verifier must prove that the already-local model asset corresponds to
the exact `model_id`, immutable revision, and `weights_sha256` in the selected
`TrainingRunPlan`. The later Hugging Face adapter can implement that verifier according to
the acquisition/tournament artifact semantics while keeping this core backend-neutral.

## Scope

Exactly three paths are introduced:

```text
specs/mesc-training-local-asset-attestation-v1/README.md
src/medscale/mesc/_training_local_asset_attestation_v1.py
tests/test_mesc_training_local_asset_attestation_v1.py
```

No dependency, workflow, CLI, model registry, launch-plan, readiness, or dataset contract
is changed.

## Canonical inputs

`attest_local_training_assets(...)` requires:

- an exact `TrainingLaunchPlan`;
- an exact PASS `TrainingCorpusBindingReport`;
- the selected role (`compact` or `reasoner`);
- an already-existing local model directory;
- an already-existing local corpus file; and
- an explicitly injected `LocalModelAssetVerifier`.

Subclasses of canonical plan/binding inputs are rejected.

## Corpus verification

The core reads the local corpus file in bounded chunks and computes ordinary raw-byte
SHA-256 plus byte count. PASS requires exact equality with the canonical corpus binding:

```text
observed_corpus_sha256 == binding.canonical_jsonl_sha256
observed_corpus_byte_count == binding.canonical_jsonl_byte_count
```

The corpus path must be an existing regular file and must not be a symlink.

Filesystem paths do not participate in the attestation scientific identity. Two machines
may store the same verified assets at different paths and produce the same attestation.

## Model-verifier receipt

`LocalModelAssetObservation` records:

- exact role;
- model id;
- immutable revision;
- observed canonical weight identity;
- verifier id and version;
- verifier receipt SHA-256;
- whether verification accessed a network;
- whether remote code was allowed; and
- whether gated terms were accepted during verification.

The observation must be the exact canonical class, not a subclass.

PASS requires exact equality with the selected run plan for role, model id, revision, and
`weights_sha256`.

PASS also requires all of these to remain false:

```text
network_accessed = false
remote_code_allowed = false
gated_terms_accepted = false
```

Thus a verifier that silently contacts a Hub, executes remote repository code, or accepts
terms cannot produce an executable attestation.

## Dataset binding

The selected run's `training_dataset_sha256` must equal the corpus binding's exact T5
training-dataset identity. A valid corpus from a different training dataset cannot be
substituted.

## Attestation report

`TrainingLocalAssetAttestationReport` records the exact launch-plan/run-plan/corpus-binding
identities, expected and observed model identities, expected and observed corpus bytes,
verifier receipt, security observations, blockers, and version.

`attestation_sha256` is deterministic and excludes machine-specific paths.

`can_execute_training` is true only for PASS with no blockers. It means only that the next
executor may consume this proof. It does not create training authorization; authorization
must already exist upstream in the canonical launch plan.

## Fail-closed behavior

Attestation is BLOCKED when, among other cases:

- corpus binding is not PASS;
- the run and corpus binding name different training datasets;
- corpus path is missing, not a regular file, or a symlink;
- local corpus SHA or byte count differs;
- model root is missing, not a directory, or a symlink;
- the injected verifier fails;
- the verifier returns a non-canonical observation;
- model role/id/revision/weight identity differs;
- verification accessed a network;
- remote code was allowed; or
- gated terms were accepted.

A directly constructed PASS report also rejects mismatched model/corpus identities,
incomplete verifier receipts, forbidden security observations, or blockers.

## Security boundary

This package itself performs no:

- network or provider access;
- model download or model-weight retrieval;
- license/gated-term acceptance;
- model/tokenizer loading;
- remote-code loading;
- inference or generation;
- GPU execution; or
- training.

Tests use temporary fixture files and fake local verifier receipts only.

## Next gate

After this package is canonical, the next repository-only gate is **Training Executor V1**.
It must recompute upstream readiness/launch authority, require this exact PASS attestation,
materialize the experiment manifest, enforce output namespaces, and invoke only an
explicitly injected backend.

A later optional Hugging Face adapter will implement the concrete local model verifier and
SFT backend without turning a model id into implicit Hub access.
