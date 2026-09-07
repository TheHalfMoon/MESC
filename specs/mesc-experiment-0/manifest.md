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
