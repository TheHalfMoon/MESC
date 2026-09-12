# MESC Experiment-0 — Package Manifest

This package intentionally separates protocol preparation from real execution evidence.

## Protocol and governance

- `README.md`
- `STATUS.md`
- `plan.md`
- `tournament-contract.md`
- `runbook.md`
- `evidence-contract.md`
- `decision-contract.md`
- `experiment-config.template.json`
- `execution-window-landscape-v1.md`
- `candidate-roster-v1.json`

## Execution template

- `../../notebooks/MESC_Experiment_0_Colab.ipynb`

## Runtime qualification producer

- `mrl-0804-runtime-authorization-v1.json`
- `mrl-0804-runtime-v1.md`
- `../../scripts/mesc_mrl_0804_gpu_probe.py`
- `../../scripts/mesc_mrl_0804_runtime_qualify.py`
- `../../src/medscale/mesc/_mrl_0804_runtime_v1.py`
- `../../tests/test_mesc_mrl_0804_runtime_v1.py`

## Verification

- `../../tools/verify_mesc_experiment_0_evidence.py`
- `../../tools/verify_mesc_experiment_0_candidate_roster.py`
- `../../tests/test_verify_mesc_experiment_0_evidence.py`
- `../../tests/test_verify_mesc_experiment_0_evidence_integrity.py`
- `../../tests/test_verify_mesc_experiment_0_candidate_roster.py`
- `../../tests/test_mesc_experiment_0_frozen_identities.py`
- `../../tests/test_mesc_experiment_0_config_preflight_parity.py`
- `../../tests/test_mesc_experiment_0_protocol.py`

No file in this package is a model checkpoint, dataset, runtime receipt, training artifact, or
promotion record. The candidate roster is metadata-only and cannot satisfy MRL-0801 or grant
model acquisition, execution, or training authority.
