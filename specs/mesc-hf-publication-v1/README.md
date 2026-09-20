# MESC Hugging Face Publication Contract v1

Status: IMPLEMENTATION CANDIDATE / EXTERNAL PUBLICATION DISABLED

Issue: #451

## Purpose

This contract introduces the first repository-owned Hugging Face distribution boundary.
It qualifies a deterministic publication plan and emits a dry-run receipt. It does not
upload, create, mutate, or delete any Hugging Face repository.

GitHub remains the canonical source of truth.

## Supported artifact classes

The v1 dry-run contract recognizes three distinct downstream classes:

- space
- model
- dataset

Collection publication remains outside this first executable slice.

## Required bindings

Every plan binds:

- exact canonical GitHub repository;
- exact source commit SHA and tree;
- governed source tag/release identity;
- exact Hugging Face destination owner/repository;
- deterministic artifact manifest;
- card identity;
- rights identity;
- provenance identity;
- evidence-backed licence identifier.

The current destination owner allowlist is exactly MedScaleAI.

## Fail-closed boundary

Repository qualification requires external_upload_enabled=false.

Qualification is blocked for:

- source repository/SHA/tree drift;
- destination-owner drift;
- unsafe or duplicate artifact paths;
- missing README.md card;
- malformed hashes or destination names;
- noncanonical JSON;
- unknown/extra plan fields, including credential-like fields;
- any attempt to enable external upload during repository qualification.

No credential is represented in the plan or dry-run receipt schema.

## Dry-run receipt

A successful dry-run receipt records source identity, destination identity, plan hash,
artifact-manifest hash, and external_upload_performed=false.

The receipt is evidence of repository-side planning/qualification only. It is not
publication evidence.

## Non-grants

This slice does not grant or implement external upload, Hugging Face repository creation,
token/OAuth use, model/dataset/Space promotion, release authority, or scientific-result
promotion.

A successor implementation must add protected credential/trust boundaries, immutable
artifact reuse, external destination verification, publication receipt generation, and
independent readback before external publication may be authorized.
