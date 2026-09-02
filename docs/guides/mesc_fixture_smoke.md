# MESC Fixture Smoke

`medscale mesc-fixture-smoke` is the Phase 6 executable golden path for repository plumbing qualification.

It runs one fixed, deterministic MRL fixture scenario entirely in memory and prints one canonical JSON object to stdout.

```bash
uv run medscale mesc-fixture-smoke
```

The output contains content identities for the proposal, observation, receipt, decision, and completed loop result. The canonical decision is intentionally `REJECT`: the fixture is non-perfect by design so the smoke cannot be mistaken for a positive research result.

Example shape:

```json
{"clinical_authority":false,"decision_sha256":"<sha256>","decision_state":"REJECT","deployment_authorized":false,"filesystem_writes":false,"fixture_only":true,"format":"MESC-FIXTURE-SMOKE-V1","model_execution":false,"network_access":false,"non_evidence":true,"observation_sha256":"<sha256>","promotion_authorized":false,"proposal_sha256":"<sha256>","receipt_sha256":"<sha256>","release_authorized":false,"result_sha256":"<sha256>","training_authorized":false}
```

## Boundary

This command is **fixture-only** and **non-evidence**. It performs no filesystem writes, network access, model/tokenizer download, inference, retrieval, GPU/provider work, credential use, training, fine-tuning, campaign-state mutation, promotion, release, deployment, or clinical action.

It proves only that the already-governed MRL fixture contracts can be composed end to end through a user-visible CLI path with deterministic content identities. It does not prove model quality, research validity, real-experiment readiness, publication readiness, or any MRL-0801..MRL-0808 evidence requirement.

Run the command twice on the same software state to verify byte-identical stdout. Any stronger scientific or operational claim must come from the separate canonical evidence and authority gates that govern that claim.
