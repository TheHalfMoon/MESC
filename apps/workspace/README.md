# MedScale Clinical Workspace

CW-001 establishes a Python-only, zero-dependency application boundary for the future local Clinical Workspace.

Current scope is intentionally narrow:

- synthetic patient and encounter fixtures only;
- deterministic local object identity;
- no microphone or ambient capture;
- no EHR/FHIR connector;
- no model execution;
- no credentials;
- no network requirement;
- no persistent writes.

The Research Core remains independently packaged from `src/medscale`. The Workspace is a separate package under `apps/workspace` and currently imports no Research Core modules. `scripts/check_clinical_workspace_boundary.py` enforces that fail-closed boundary.

Later tasks may introduce carefully governed storage and versioned Research Core interfaces. CW-001 does not authorize PHI, clinical production use, EHR writes, external model execution, training, publication, paid compute, or MRL changes.
