# CW-006 One-Time Zero-Cost Colab Qualification Authorization

- Date: 2026-09-23
- Founder: Abdulaziz M. Alshehri
- Scope: CW-006 only, one-time, zero-cost Google Colab qualification
- Purpose: verify already-ratified ADR-0040 model and runtime path with synthetic or explicitly permitted non-PHI fixtures only

## Verbatim authorization

```text
I, Abdulaziz M. Alshehri, Founder, authorize a one-time zero-cost Google Colab
qualification environment for CW-006 solely to verify the already-ratified
ADR-0040 model/runtime path using synthetic or explicitly permitted non-PHI
fixtures.
```

## Allowed

```text
CW006_ZERO_COST_COLAB_QUALIFICATION = AUTHORIZED
GOOGLE_COLAB_FREE_TIER = AUTHORIZED
REMOTE_QUALIFICATION_COMPUTE = AUTHORIZED
PINNED_MODEL_DOWNLOAD_INTO_EPHEMERAL_COLAB_VM = AUTHORIZED
```

## Denied

```text
REMOTE_ASR_PRODUCT_RUNTIME = NOT_AUTHORIZED
REMOTE_PATIENT_AUDIO = NOT_AUTHORIZED
PHI = NOT_AUTHORIZED
CLINICAL_PRODUCTION_USE = NOT_AUTHORIZED
PAID_COMPUTE = NOT_AUTHORIZED
TRAINING = NOT_AUTHORIZED
FINE_TUNING = NOT_AUTHORIZED
WEIGHT_MUTATION = NOT_AUTHORIZED
REMOTE_MODEL_API_FALLBACK = NOT_AUTHORIZED
EHR_WRITE = NOT_AUTHORIZED
NEW_MRL_STAGE4_ATTEMPT = NOT_AUTHORIZED
```

## Standing contract

- PRODUCTION_REMOTE_ASR = NOT_AUTHORIZED
- PRODUCTION_RUNTIME = LOCAL_ONLY, fail-closed
- ADR-0040 remains the binding model and runtime contract
- PR 482 head: c61370664488e4ad3e274ec61a233c46652ec6de
- Model: openai/whisper-large-v3-turbo at 41f01f3fe87f28c78e2fbf8b568835947dd65ed9
- Runtime: transformers==5.16.1 with torch==2.13.0
- Sign-in: Alshehriofficial@gmail.com, interactive Google UI only
- No Google password, 2FA code, recovery code, cookie, token, or credential material is requested, stored, printed, transmitted, or committed
- MUST_NOT_MERGE PR 482 until real-model Colab qualification passes
