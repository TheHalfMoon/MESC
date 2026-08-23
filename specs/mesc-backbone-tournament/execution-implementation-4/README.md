# Backbone Tournament execution implementation 4 — fixture telemetry verifier

Status: **DRAFT / FIXTURE-ONLY / NO EXECUTION AUTHORITY**

This slice has been merge-forwarded onto the current canonical base:

```text
BASE_MAIN_SHA = 3f22d2e71d39c85775c6f9db7c70b69693cb9ce5
BASE_MAIN_TREE = bc5253fb0abc142abcace81eb0a9f628250172bb
FD-MESC-BT-EXEC-1 = CONDITIONAL_AUTHORIZATION_CANONICAL
PR_140 = CLOSED_CANONICAL
PR_141 = CLOSED_CANONICAL
PR_142 = CLOSED_CANONICAL
EXECUTION_ACTIVATION = REQUIRED
```

## Scope

This implementation covers only deterministic fixture validation for the
Section E.1 / F.1 telemetry and measurement contract. It does not allocate a
provider instance, import NVML, access a GPU, load a model, serialize a model
prompt, or run inference.

The pure in-memory verifier:

- requires the exact `NVIDIA H100 80GB HBM3` model identity and a non-empty
  printable-ASCII GPU UUID;
- requires the exact fixture clock source `monotonic_ns` and records it in the
  deterministic evidence bytes;
- requires configured sampling interval `<= 100 ms`;
- validates raw frame timestamps as monotonic and rejects gaps greater than
  100 ms;
- validates deterministic process-tree attribution from one controlled root
  process;
- rejects duplicate PIDs, missing parents, parent cycles, ambiguous root
  identity, and unexpected GPU compute processes;
- aggregates GPU memory over the complete controlled process tree for each
  frame and derives deterministic peak VRAM in MiB;
- requires monitoring to begin strictly before the model/probe start marker;
- requires terminal completion strictly before device synchronization,
  monitoring to continue through synchronization, and terminal telemetry
  capture strictly after synchronization;
- validates a synthetic high-resolution monotonic latency probe by exact
  timestamp recomputation;
- emits deterministic canonical JSON evidence bytes and a SHA-256 over those
  exact bytes.

The implementation has no filesystem I/O, network access, provider client,
NVML import, subprocess execution, credential handling, model loader,
tokenizer, prompt construction, inference, ranking, winner selection, or
training surface.

## Deliberate non-claims

This is not the live H100 qualification required by Section E.1. It does not
prove a real RunPod instance, real GPU UUID, NVML availability, real process
tree, live device synchronization, or real co-tenant absence.

It is also not the final tournament measurement harness and does not replace
the future activation-bound runtime verifier. The final implementation must
still consume live telemetry from the exact activation-bound H100 and bind the
result into the complete execution artifact manifest.

PRs #140, #141, and #142 are now canonical predecessors. This slice is
merge-forwarded onto their canonical main state but remains independently
bounded to the three files in this PR.

## Qualification

Historical pre-repair fixture qualification is superseded by the current-head
repair. Only fresh exact-head GitHub CI, CodeQL, scope reconciliation, and the
permitted exact-head review may qualify this revision.

## Hard boundary

```text
EXECUTION_ACTIVATION = REQUIRED
MODEL_WEIGHT_ACCESS = NOT_AUTHORIZED
GATED_ACCESS_REQUEST_OR_ACCEPTANCE = NOT_AUTHORIZED
MODEL_RETRIEVAL = NOT_AUTHORIZED
PROMPT_SERIALIZATION_TO_MODEL = NOT_AUTHORIZED
INFERENCE = NOT_AUTHORIZED
GENERATION = NOT_AUTHORIZED
RANKING = NOT_AUTHORIZED
WINNER_SELECTION = NOT_AUTHORIZED
BACKBONE_TOURNAMENT_EXECUTION = NOT_AUTHORIZED
TRAINING = NOT_AUTHORIZED
```

Keep this work Draft until exact-head CI, CodeQL, scope reconciliation, and the
permitted exact-head review are all proven. A head mutation burns prior
head-specific evidence.
