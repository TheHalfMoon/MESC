# MESC Training Authorization Receipt V1

Status: **IMPLEMENTATION / FAIL-CLOSED VALIDATOR / NO AUTHORITY MINTED**

Canonical base:

```text
BASE_MAIN_SHA = 9f7e8db2b47bad0e497edacfb00b749c4940a0c8
BASE_MAIN_TREE = 493c6b972c5bb482b20f5248bd4f3cc9385beac0
```

## Purpose

Emit `training_authorization_receipt_sha256` only by validating an already-supplied
founder/operator authorization artifact. Scalar function arguments and `authorize=true`
are never sufficient to mint `AUTHORIZED`.

Authorization binds a **stable pre-authorization subject identity**
(`authorization_subject_sha256`) so the receipt is not circular with the final
readiness manifest that will later include this receipt digest. Post-launch local-asset
attestation is deliberately **not** an authorization input.

## Scope

```text
specs/mesc-training-authorization-receipt-v1/README.md
src/medscale/mesc/_training_authorization_trust_v1.py
src/medscale/mesc/_training_authorization_receipt_v1.py
src/medscale/mesc/_training_executor_v1.py
tests/_training_authorization_test_support.py
tests/test_mesc_training_authorization_receipt_v1.py
tests/test_mesc_training_authorization_admission_guard_v1.py
```

## Canonical authorization artifact

`AUTHORIZED` requires non-empty canonical JSON bytes with exactly one terminal LF and
exactly this closed field set:

```text
kind
  = mesc.training_authorization.v1

authorization_scope
  = TRAINING_EXECUTION

authorizer_id
  = non-empty NUL-free text with no surrounding whitespace

authorization_subject_sha256
  = 64 lowercase hex

runtime_qualification_sha256
  = 64 lowercase hex

corpus_binding_sha256
  = 64 lowercase hex

authorization_statement
  = non-empty NUL-free text with no surrounding whitespace

authorize
  = exact JSON boolean
```

The validator rejects malformed UTF-8, duplicate keys, non-standard JSON constants,
extra or missing fields, non-canonical serialization, and any semantic mismatch between
the supplied artifact and the scalar bindings passed to the receipt builder.

The exact artifact bytes are SHA-256 addressed as `authorization_artifact_sha256` and
that digest is included in the content-addressed receipt identity.

## Required bindings

- `authorization_scope = TRAINING_EXECUTION`
- `authorizer_id`
- `authorization_subject_sha256` (from `TrainingReadinessManifest.authorization_subject_sha256`)
- `runtime_qualification_sha256`
- `corpus_binding_sha256`
- `authorization_statement`
- canonical out-of-band authorization artifact bytes
- artifact field `authorize=true` for `AUTHORIZED`

`AUTHORIZED` implies `real_training_authorized=true` and requires a validated typed
artifact object. `authorize=false` always yields `BLOCKED` with
`real_training_authorized=false`; this negative/fixture path may omit an artifact.

## Authority boundary

- Does not invent founder authorization.
- Does not construct authorization artifact bytes for callers.
- Does not execute training.
- Does not download models or accept gated terms.
- Does not clear MedScale Spec 012.
- Does not bind post-launch `local_asset_attestation_sha256`.
- Fixture/CI paths must use `authorize=false` unless canonical authorization artifact
  bytes are explicitly supplied by the test fixture.

## Next gate

Receipt producers bind through `mesc-training-readiness-receipt-binding-v1`. Remaining
work is external/evidence: authorized local model assets, qualified corpus bytes,
platform-qualified runtime smoke, a real founder/operator authorization artifact,
training/evaluation, rights/SBOM/provenance, and a non-empty qualifying GitHub Release.

## Canonical trust registry

Canonical JSON and SHA-256 prove artifact identity, not who authorized it. Therefore an
`authorize=true` artifact is necessary but not sufficient for `AUTHORIZED`.

The validator additionally requires the artifact SHA-256 to be present in the
repository-controlled registry implemented by:

```text
src/medscale/mesc/_training_authorization_trust_v1.py
```

The production registry is intentionally empty in this implementation. No repository
caller can mint real training authority from scalars or self-authored canonical bytes.
Provisioning a real artifact digest is a separate governance mutation: it must bind the
exact artifact, be independently reviewed, and be authenticated by the repository's
Founder-attestation process before canonical adoption. Test code may temporarily replace
the private in-process registry only to exercise positive paths; no synthetic digest is
shipped as a production trust root.

An `AUTHORIZED` receipt content-addresses the exact trust-registry identity used when the
artifact was admitted. Registry identity and artifact membership are derived from one
immutable validated snapshot, never from separate live reads. Missing, malformed, or
unregistered authority evidence fails closed as the authorization domain error rather
than escaping as a raw registry implementation error. This package does not provision a
Founder key, fabricate a Founder attestation, or grant current real-world training
authority.

## Use-time trust and revocation

Trust admission is not a one-time construction check. Every `AUTHORIZED` receipt must
still match the exact current repository-controlled trust-registry identity, and its
authorization-artifact digest must remain admitted, whenever the receipt is bound into
readiness or used to recompute launch authority.

Any trust-registry mutation therefore invalidates previously admitted receipts
fail-closed, including explicit digest removal. A caller must obtain a newly admitted
receipt under the new canonical registry snapshot before training can become
`READY_TO_LAUNCH` again.

The executor performs a final trust admission immediately around `backend.execute()`. The
same registry lock serializes that final admission with the repository-supported
in-process test mutation path, so revocation cannot interleave between the final canonical
trust check and backend invocation. The lock establishes admission ordering only; it does
not create a training-cancellation authority or mint any real authorization digest.
