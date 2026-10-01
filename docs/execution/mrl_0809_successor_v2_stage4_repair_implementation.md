# MRL-0809 successor v2 Stage-4 repository repair implementation note

Status: IMPLEMENTATION_IN_PROGRESS / NO_RUNTIME_AUTHORITY

Decision: `FD-MRL-0809-SUCCESSOR-V2-STAGE4-REPAIR-1`

This note records the first repository-side implementation slice after Founder approval.

## Implemented in this slice

- fail-closed actual tensor placement audit helper;
- optional `hf_device_map` validation as additional evidence rather than the sole source of truth;
- rejection of CPU, disk, meta, CUDA device 1+, ambiguous CUDA placement, malformed map targets, empty placement evidence, and actual tensor/metadata disagreement;
- fail-stop orchestration primitive proving that later Stage-4 steps are not invoked after the first failing step;
- adversarial unit coverage for the placement and fail-stop helpers.

## Still required before this repair can be considered complete

- integrate the placement audit into a versioned successor runtime-feasibility harness without rewriting the consumed v2 evidence history;
- bind the repaired execution path in a new static prerequisite manifest / receipt contract as required;
- update the governed runbook and machine-readable authorization bindings;
- mechanically bind the fail-stop driver into the governed Stage-4 execution path;
- run local tests and regressions;
- run Jev and Alibaba Open Code Review official local lanes and record their exact outcomes;
- run hosted CI, CodeQL, Optional Extras / Backends and HF Publication Qualification;
- exact-head qualification and separate Founder merge approval.

## Runtime boundary

No Stage-4 retry is authorized by this implementation slice. No GPU allocation, model download, model load, scientific corpus access, training, weight mutation, offload, quantization change, candidate substitution, or paid compute is authorized.
