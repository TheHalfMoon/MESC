# ADR-0040 -- Founder Ratification Record

```text
Status:
FOUNDER RATIFICATION RECORDED WITH NO AMENDMENT

ADR-0040:
ACCEPTED BY FOUNDER UNDER R6 ON 2026-09-22

CW-006:
ALREADY ACTIVATED UNDER ISSUE 480 -- THIS RECORD ADDS NO NEW ACTIVATION

IMPLEMENTATION OF CW-006:
AUTHORIZED ONLY WITHIN THE ADR-0040 PROTECTED CONTRACT UNDER ISSUE 480

PHI INGESTION / REAL PATIENT AUDIO / CLINICAL PRODUCTION USE /
EHR WRITE / REMOTE ASR / AUTOMATIC MODEL DOWNLOAD /
TRAINING / FINE TUNING / WEIGHT MUTATION / RESEARCH ADMISSION FROM WORKSPACE /
NEW MRL STAGE 4 ATTEMPT / PAID COMPUTE:
NOT AUTHORIZED
```

- **Founder / Product Owner / Roadmap Owner:** Abdulaziz M. Alshehri
- **Decision date:** 2026-09-22
- **Authority cited:** Rule R6 ([rules R1-R7](../../docs/governance/rules.md)), [roles and authority](../../docs/governance/roles_and_authority.md)
- **Governing issue:** [#480](https://github.com/TheHalfMoon/MESC/issues/480) -- CW-006 Local ASR adapter activation
- **Proposal PR:** [#481](https://github.com/TheHalfMoon/MESC/pull/481) -- docs propose ADR-0040 local ASR model and reference runtime -- OPEN at head 0173f81c05ad83c0812f120dfcb4c1a0002295e6 on base ab29ca613cd1ec19460809a2708d2c315d191b9f at decision time
- **Canonical main at the moment of the decision:** ab29ca613cd1ec19460809a2708d2c315d191b9f with tree 8b94e4f5fb7da3e7faba24c6e4044010c3f3f56f
- **Subject ADR:** [ADR-0040 -- Local ASR model and reference runtime for Clinical Workspace](../../docs/adr/0040-local-asr-model-and-reference-runtime.md)
- **Related contracts:** [task ledger](tasks.md) CW-006, [capability map](capability_map.md), [model registry](../../docs/models/model_registry.md)

This record is the canonical ratification artifact for ADR-0040. On any conflict between
this record and the proposal text of ADR-0040 as it stood before ratification, this record
controls for ratification facts. No model, revision, digest, license, version, contract, manifest, or scope value is changed by ratification.

---

## 1. Live state entering the decision

Verified directly against live repository and GitHub state on 2026-09-22, not from memory:

```text
canonical main = ab29ca613cd1ec19460809a2708d2c315d191b9f
canonical tree = 8b94e4f5fb7da3e7faba24c6e4044010c3f3f56f
default branch = main
PR 481 state = OPEN
PR 481 head = 0173f81c05ad83c0812f120dfcb4c1a0002295e6
PR 481 base = ab29ca613cd1ec19460809a2708d2c315d191b9f
PR 481 mergeable = MERGEABLE
PR 481 mergeStateStatus = CLEAN
PR 481 checks = all SUCCESS with one NEUTRAL review lane
Issue 480 state = OPEN -- CW-006 IN_PROGRESS as the single active unit under R4
CW-007 = BLOCKED_DEPENDENCY on CW-006
CW-009 CW-011 CW-013 CW-016 CW-017 = ELIGIBLE_NOT_ACTIVATED
ADR-0040 status before this record = Proposed -- awaiting Founder ratification under R6
tasks.md CW-006 on canonical main = ELIGIBLE not activated -- stale relative to Issue 480 and reserved for later closeout reconciliation
Issues 429 450 464 = separately governed and OPEN
MRL-0809 authority = INDEPENDENT
```

Hugging Face live check on 2026-09-22 for openai/whisper-large-v3-turbo returns sha 41f01f3fe87f28c78e2fbf8b568835947dd65ed9, license mit in tags and cardData, author openai, pipeline automatic-speech-recognition, library transformers, parameters 808878080, base model openai/whisper-large-v3, last modified 2024-10-04, gated false, disabled false, visibility public, languages include en and ar. The values match ADR-0040 Section 4 and Section 5 with no drift blocking ratification.

---

## 2. Prior canonical ratification check

Issue 480 comments were listed live and the result was empty. PR 481 comments were listed live and the result contained only automated entries from qodo-code-review for billing status and from coderabbitai for skip review configuration, with no Founder decision text. Therefore no canonical Founder ratification of ADR-0040 was recorded in Issue 480 or PR 481 before this session. The decision in Section 3, supplied in this session by the Founder, is the ratification authority recorded here.

---

## 3. Ratification decision

The Founder ratifies ADR-0040 under R6 as the implementation contract for the governed CW-006 unit, subject to all existing MESC governance, evidence, security, licensing, synthetic-only, and no-PHI constraints.

```text
ADR_0040 = ACCEPTED BY FOUNDER ON 2026-09-22 UNDER R6 WITH NO AMENDMENT
ADR_0040_REJECTION = NOT EXERCISED
ADR_0040_AS_PROPOSED_IDENTITIES = ACCEPTED UNCHANGED
AMENDMENT = NOT APPLICABLE
```

Exact Founder decision sentence recorded verbatim:

```text
I, Abdulaziz M. Alshehri, Founder, hereby ratify ADR-0040 (Local ASR model and reference runtime for Clinical Workspace), adopting openai/whisper-large-v3-turbo at revision 41f01f3fe87f28c78e2fbf8b568835947dd65ed9 (MIT) with reference runtime transformers 5.16.1 and torch 2.13.0 under the local-only fail-closed contract, with no implementation authority beyond governed CW-006 execution and no PHI, clinical production, remote ASR, training, or MRL authority.
```

---

## 4. Immutable identities bound by this ratification

Ratification changes no identity. The following values are restated from ADR-0040 Sections 4, 5, 7, and 9 for binding clarity:

```text
MODEL_ID = openai/whisper-large-v3-turbo
FULL_IMMUTABLE_REVISION = 41f01f3fe87f28c78e2fbf8b568835947dd65ed9
MODEL_LICENSE = mit
REFERENCE_RUNTIME = transformers 5.16.1 with torch 2.13.0
WEIGHT_FILE = model.safetensors
WEIGHT_SHA256 = 542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1
WEIGHT_SIZE = 1617824864 bytes
CONFIG = config.json blob ad2f44ff1ed66e12765b2392dc041469db91a462
PROCESSOR = preprocessor_config.json blob 931c77a740890c46365c7ae0c9d350ba3cca908f
TOKENIZER = tokenizer.json blob 17456db595adc78a973f97d69d8cb50bc87c0b1c
RUNTIME_CONTRACT = trust_remote_code false with local_files_only true, no runtime download, no Hub acquisition, no network fallback, no remote inference, no cloud fallback, no audio or transcript telemetry
```

Do not use mutable main. Do not modify frozen root pyproject.toml or uv.lock for Workspace ASR. The optional Workspace dependency surface remains scoped as asr-local only after ratification and only under CW-006 authority, with the basic Workspace shell installable and testable without ASR dependencies.

---

## 5. Scope and explicit non-grants

This ratification authorizes governed CW-006 execution only under Issue 480 and within the ADR-0040 protected execution contract. It grants no additional authority.

```text
PHI_INGESTION = NOT_AUTHORIZED
REAL_PATIENT_AUDIO = NOT_AUTHORIZED
CLINICAL_PRODUCTION_USE = NOT_AUTHORIZED
EHR_WRITE = NOT_AUTHORIZED
REMOTE_ASR = NOT_AUTHORIZED
AUTOMATIC_MODEL_DOWNLOAD = NOT_AUTHORIZED
TRAINING = NOT_AUTHORIZED
FINE_TUNING = NOT_AUTHORIZED
WEIGHT_MUTATION = NOT_AUTHORIZED
RESEARCH_ADMISSION_FROM_WORKSPACE = NOT_AUTHORIZED
NEW_MRL_STAGE4_ATTEMPT = NOT_AUTHORIZED
PAID_COMPUTE = NOT_AUTHORIZED
ARABIC_QUALITY_CLAIM = NOT_AUTHORIZED WITHOUT MEASUREMENT
ENGLISH_QUALITY_CLAIM = NOT_AUTHORIZED WITHOUT MEASUREMENT
CLINICAL_ASR_QUALITY_CLAIM = NOT_AUTHORIZED WITHOUT MEASUREMENT
```

Issues 429, 450, and 464 remain separately governed. Frozen MRL evidence remains untouched. No Arabic, English, WER, or clinical transcription quality claim is granted by this record.

---

## 6. Effect

ADR-0040 is Accepted by the Founder under R6 as of 2026-09-22 with no amendment. CW-006 implementation may proceed only under Issue 480 within the protected local-only fail-closed contract, with manifest verification before model load, explicit SUCCESS versus PARTIAL versus FAILED typing with workspace, session, input, model, revision, runtime, language, segment, and timestamp binding, and with exact-head plus fresh-main qualification for every merge. Proposal alone granted no implementation authority. This record closes the R6 ratification gate and opens only the governed CW-006 path described above.
