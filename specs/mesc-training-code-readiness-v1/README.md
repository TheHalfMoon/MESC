# MESC Training Code Readiness V1

Status: **IMPLEMENTATION / REPOSITORY AUDIT / NO TRAINING AUTHORIZATION**

Canonical base:

```text
BASE_MAIN_SHA = 22e5eca5473cd00874fe2ede14303d5e98140df3
BASE_MAIN_TREE = d22d39b174929a55cecb93492d0e438c489b77ea
PR_204 = CLOSED_CANONICAL
```

## Purpose

The HF local SFT backend remaining-gates list required three repository-side layers before
`TRAINING_CODE_READY`:

1. dependency-lock / optional-extra gate — closed by PR #200
2. training CLI/orchestrator — closed by PR #204
3. a final repository training-readiness audit — this package

This audit verifies that the repository training stack is present, pinned, and wired. It
does **not** authorize real training and does **not** make MedScale Spec 012 admission
ready.

## Scope

```text
specs/mesc-training-code-readiness-v1/README.md
src/medscale/mesc/_training_code_readiness_v1.py
tests/test_mesc_training_code_readiness_v1.py
```

## Disposition

```text
BLOCKED
TRAINING_CODE_READY
```

`TRAINING_CODE_READY` requires:

- every required training module importable;
- every required Spec Kit README present as a regular file;
- `project.dependencies` empty;
- exact `training-hf-sft` pins matching the dependency-lock gate; and
- `uv.lock` observable through the orchestrator lock hasher.

The report always records:

```text
real_training_authorized = false
medscale_spec_012_admission_readiness = NOT_READY
```

## Authority boundary

This package does not:

- invent runtime-qualification or training-authorization receipts;
- download models or accept gated terms;
- execute training;
- publish GitHub Release assets;
- clear MedScale `MESC_RELEASED_ARTIFACT`; or
- claim `RELEASE_READY` / MedScale Spec 012 admission.

## Next gates (external / evidence)

Receipt producers for runtime qualification and training authorization, plus the readiness
receipt-binding construction helper, now exist in-repo. Real training and a
MedScale-admissible release still require:

- authorized local model assets with `weights_sha256`;
- qualified corpus bytes;
- a runtime/GPU qualification receipt with `platform_qualified=true` (smoke evidence);
- an explicit training-authorization receipt with `authorize=true` from the founder/operator;
- successful training/evaluation evidence;
- rights/SBOM/provenance; and
- a GitHub Release with non-empty immutable assets that survive independent re-fetch and
  hash verification.
