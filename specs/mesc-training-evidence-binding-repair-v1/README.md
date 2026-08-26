# MESC Training Evidence Binding Repair V1

Status: **IMPLEMENTATION / FAIL-CLOSED AUTHORITY REPAIR / NO TRAINING AUTHORIZATION**

## Purpose

Repair the canonical post-`TRAINING_CODE_READY` evidence chain after live review exposed three unsafe properties:

1. a syntactically valid 64-hex smoke digest could mint `platform_qualified=true` without validating the smoke artifact or its runtime bindings;
2. the authorization receipt attempted to bind the final readiness-manifest hash that itself contains the authorization-receipt hash; and
3. readiness admitted `READY_TO_LAUNCH` from the presence of runtime/authorization hashes without validating the typed receipts.

A second circular edge was also identified: authorization referenced local-asset attestation, while local-asset attestation is produced from a launch plan that already contains authorization identity.

## Canonical acyclic order

```text
training dataset qualification
  -> canonical corpus binding
  -> parser-validated runtime smoke evidence
  -> platform-qualified runtime receipt
  -> pre-authorization readiness subject
  -> explicit training authorization receipt
  -> final semantic readiness assessment
  -> launch plan
  -> local asset attestation
  -> executor
  -> real training (separately authorized; not performed by this repair)
```

## Runtime smoke evidence

`TrainingRuntimeSmokeEvidence` is constructed from exact canonical JSON bytes. The parser:

- rejects duplicate keys, extra/missing keys, malformed UTF-8/JSON, wrong primitive types, and non-canonical bytes;
- computes the artifact SHA-256 itself;
- binds disposition, runner class, Python, OS, GPU, dependency lock, repository commit/tree, probe id/version, network access, and remote-code allowance.

A runtime receipt with no smoke evidence is `OBSERVED`, never platform-qualified. A `PASS` receipt requires validated `PASS` smoke evidence whose facts exactly equal the observed runtime and whose network/remote-code flags are false.

## Authorization subject

`TrainingReadinessManifest.authorization_subject_sha256` is derived from every canonical readiness identity **except** `training_authorization_receipt_sha256`, plus an explicit subject-kind marker. The subject therefore remains stable before and after the authorization receipt is attached.

The authorization receipt binds:

- the stable authorization subject;
- the exact platform-qualified runtime receipt hash; and
- the exact canonical corpus-binding hash.

It deliberately does **not** bind local-asset attestation because that artifact is post-launch.

## Semantic readiness

Hash presence is not authority. `READY_TO_LAUNCH` requires the manifest to carry exact typed receipts whose content hashes equal the manifest hashes and whose semantics satisfy all of these:

- runtime receipt is canonical `PASS`, platform-qualified, carries validated PASS smoke evidence, has no blockers, and records no network/remote-code access;
- authorization receipt is canonical `AUTHORIZED`, has `real_training_authorized=true`, has no blockers, targets the manifest authorization subject, and binds the same runtime and corpus identities;
- corpus binding identity is present.

Presence-only hashes remain `READY_FOR_AUTHORIZATION`; mismatched or contradictory evidence is `BLOCKED`.

## Launch and post-launch evidence

Each launch run must match the qualified runtime's runner class, Python version, OS, GPU, dependency lock, repository commit, and repository tree. The launch plan also carries the canonical corpus-binding identity. Local-asset attestation remains post-launch and must be checked against that identity before executor admission.

## Authority boundary

This repair:

- does not execute a GPU smoke test;
- does not download or load a model;
- does not access providers or the network;
- does not create real founder/operator authorization;
- does not run training.

All CI evidence is synthetic contract validation only. Real training remains separately and explicitly authorized.