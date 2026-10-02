# MRL-0809 successor v2 Stage-4 repository repair implementation note

Status: IMPLEMENTATION_COMPLETE_PENDING_QUALIFICATION / NO_RUNTIME_AUTHORITY

Decision: `FD-MRL-0809-SUCCESSOR-V2-STAGE4-REPAIR-1`

This note records the completed repository-side repair implementation authorized by the Founder decision. It does not authorize a hosted runtime attempt.

## Implemented repair

- fail-closed actual tensor placement audit helper;
- optional `hf_device_map` validation as additional evidence rather than the sole source of truth;
- canonical empty-string root-module key support while non-string map keys remain rejected;
- rejection of CPU, disk, meta, CUDA device 1+, ambiguous CUDA placement, malformed map targets, empty placement evidence, and actual tensor/metadata disagreement;
- versioned successor runtime-feasibility repair harness that preserves and SHA-binds the consumed v2 harness bytes;
- repaired isolated worker integration without rewriting consumed-v2 evidence history;
- repaired static prerequisite manifest with finalized SHA-256 bindings for the preserved v2 manifest, repair authorization, Founder decision, runbook, harness, worker, fail-stop driver, placement audit, and repair static gate;
- repair static gate enforcement after the preserved exact-live-main repository gate, so governed stage/probe/assemble execution cannot bypass the repair contract;
- empty repair trust root and `ABSENT` repair evidence slot before any separately authorized runtime evidence admission;
- fail-stop Stage-4 driver proving that later steps are not invoked after the first failing stage, probe, or cleanup;
- deterministic creation of a new custody directory for the documented future execution command;
- adversarial unit coverage for placement auditing, fail-stop behavior, custody creation, source-hash bindings, Founder authorization bindings, and repair-gate enforcement;
- governed runbook and PR description updated to preserve the no-runtime-authority boundary.

## Qualification still required before merge

- latest-head hosted CI must complete successfully;
- latest-head CodeQL must complete successfully;
- latest-head Optional Extras / Backends must complete successfully;
- Jev official bounded review must be executed and its exact outcome recorded;
- Alibaba Open Code Review official local lanes must be executed and their exact outcome recorded;
- exact-head qualification must bind the final PR head;
- separate Founder merge approval is required.

`Hugging Face Publication Qualification` is not triggered by this PR's repair paths. The workflow runs automatically on every push to `main`, so it remains a required post-merge fresh-main qualification gate and must not be claimed before that run exists.

## Runtime boundary

No Stage-4 retry is authorized by this implementation. No GPU allocation, model download, model load, scientific corpus access, training, weight mutation, offload, quantization change, candidate substitution, or paid compute is authorized.

A future Stage-4 retry requires a separate Founder decision bound to an exact repaired canonical merge SHA/tree/static manifest after all required fresh-main qualification is complete.
