# MESC Hugging Face Publication V2

Status: repository transport implementation only. External publication is disabled.

This contract adds the successor transport to the P1 dry-run publication plan. GitHub remains the canonical source of truth. The V2 workflow may publish only when a separately committed `ACTIVE` authority record passes every live preflight; the committed record in this revision is deliberately `DISABLED`.

## Trust boundary

The transport is fixed to:

- source repository `TheHalfMoon/MESC`;
- destination owner `MedScaleAI`;
- GitHub workflow `.github/workflows/hf-publish.yml` on canonical `main`;
- GitHub Environment `huggingface-publication`;
- Hugging Face Trusted Publisher / GitHub OIDC mode `trusted-publisher-oidc-v1`;
- exact immutable GitHub Release asset bytes; no publication-time rebuild;
- exact destination parent commit and pre-publication remote inventory;
- exact transport-manifest hash over the workflow, CLI, script lock, canonical JSON implementation, P1/P2 publication modules, `pyproject.toml`, and `uv.lock`;
- post-upload readback at the returned immutable Hugging Face commit before a success receipt exists.

No stored `HF_TOKEN` is accepted. The transport rejects inherited Hugging Face token variables, uses a temporary `HF_HOME`, and obtains its token only after the live GitHub authority and Environment checks have passed.

## Environment creation hardening

GitHub can create a missing Environment when a job first references `environment:`. To avoid using that behavior as an activation path, the workflow has two jobs:

1. `preflight` has no `environment:` binding and no `id-token: write`. It has read-only `contents`, `issues`, and `actions` permissions. It verifies exact live canonical `main`, the exact authority comment actor/body, and the already-existing Environment protection/deployment-policy hash.
2. `publish` depends on successful `preflight`. Only this job references `environment: huggingface-publication` and receives `id-token: write`. The CLI repeats the live checks before materialization, before OIDC, after OIDC, and before receipt persistence.

A missing, unprotected, incomplete, or policy-drifted Environment is a hard failure. Repository code does not create or configure the Environment.

## Active authority record

A future `ACTIVE` authority is valid only when canonical JSON binds all of the following:

- the complete P1 publication plan and its SHA-256;
- the P1 artifact-manifest SHA-256;
- one exact GitHub Release asset name, byte count, SHA-256, and destination path for every P1 artifact;
- the SHA-256 of the complete release-asset mapping;
- the exact founder authority issue/comment id, actor `TheHalfMoon`, and SHA-256 of the exact UTF-8 comment body;
- the exact `huggingface-publication` Environment policy SHA-256;
- the exact Hugging Face destination parent commit and parent file-inventory SHA-256;
- publication mode `trusted-publisher-oidc-v1`;
- the exact transport-manifest SHA-256.

The P1 plan remains `external_upload_enabled=false`; V2 authority is a separate layer and never rewrites the P1 dry-run record into publication authority.

## Non-grants

This repository change does not grant or perform any of the following:

- creation or configuration of a Hugging Face repository;
- creation or configuration of the GitHub Environment;
- Trusted Publisher configuration;
- setting `HF_PUBLISH_ENABLED=true`;
- OIDC token exchange;
- external upload;
- model, dataset, or Space publication authority;
- a new release tag or GitHub Release;
- scientific result promotion;
- any MRL-0809 runtime allocation.

External activation requires a separate founder authorization naming the exact destination and artifact identity plus independently verified external configuration.
