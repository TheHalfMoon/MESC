# CW-006 Real-Model Runtime-Path Qualification Evidence

- Task: CW-006 Local ASR adapter
- Activation: Issue 480 as the single active implementation unit under R4
- Contract: ADR-0040 accepted by the Founder under R6 with no amendment
- Implementation PR: 482
- Exact qualified head: c61370664488e4ad3e274ec61a233c46652ec6de
- Exact qualified tree: b1247dce54a5c74a76380f5b5309a7d65cc376e4
- Base: 75c4bbbc480e23432016ed1350e4385a774e4406
- Base tree: 4124904c76bd9ad2c037ba85dc5a0b13cdd02d55
- Branch: feat/cw-006-local-asr-adapter
- Date: 2026-09-23
- Authorization: specs/medscale-clinical-workspace-v1/cw-006-colab-qualification-authorization.md
- Runner: notebooks/CW006_ZeroCost_Colab_Qualification.ipynb
- Status: PASS for the real runtime path only

This record creates no clinical, PHI, training, publication, research admission, production, or remote runtime authority.

## 1. Live GitHub truth verified before recording

```text
PR 482 state = OPEN
PR 482 merged = false
PR 482 mergeable = MERGEABLE
PR 482 mergeStateStatus = CLEAN
PR 482 base = main
PR 482 head branch = feat/cw-006-local-asr-adapter
PR 482 exact head = c61370664488e4ad3e274ec61a233c46652ec6de
CI run 35826399366 = SUCCESS on the exact head
CodeQL run 35826399421 = SUCCESS on the exact head
CodeRabbit status = SUCCESS with manual review notice and no finding
cubic reviewer = NEUTRAL with no finding
reviews = none
review comments = none
issue comments = only automated billing and skip notices with no finding
required status checks = quality py3.11 PASS, quality py3.12 PASS, analyze python PASS
required review thread resolution = satisfied with zero threads
allowed merge methods = merge only
```

## 2. Canonical qualification result

```json
{
  "qualification": "CW-006 real-model runtime-path qualification",
  "repo": "TheHalfMoon/MESC",
  "pr": 482,
  "exact_head": "c61370664488e4ad3e274ec61a233c46652ec6de",
  "runtime": {
    "python": "3.13.15",
    "platform": "Linux-6.6.122+-x86_64-with-glibc2.39",
    "torch": "2.13.0+cu130",
    "transformers": "5.16.1",
    "colab": true,
    "gpu_available": false
  },
  "model": {
    "id": "openai/whisper-large-v3-turbo",
    "revision": "41f01f3fe87f28c78e2fbf8b568835947dd65ed9",
    "license": "mit",
    "weight_sha256": "542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1",
    "weight_size_bytes": 1617824864,
    "snapshot_verified": true,
    "local_files_only": true,
    "trust_remote_code": false,
    "allow_download": false
  },
  "fixture": {
    "dataset": "google/fleurs",
    "config": "en_us",
    "split": "validation[:1]",
    "license": "cc-by-4.0",
    "id": "1548",
    "source_audio_sha256": "048169439c0328b758349af74aeb54a82a7a476e309709eb791dced06db25d48",
    "reference_transcription": "when you call someone who is thousands of miles away you are using a satellite",
    "source_sample_rate": 16000,
    "derived_clip_start_sample_16k": 17255,
    "derived_clip_frames_16k": 32000,
    "derived_wav_bytes": 64044,
    "derived_wav_sha256": "e9bb49a16eed65887f0f9e88ddbd0eaa6c9ba6582b0b6a555ac8ed88af4d6305"
  },
  "missing_snapshot_fail_closed": true,
  "network_denial_active_for_backend_and_inference": true,
  "network_attempts_after_denial": [],
  "result": {
    "status": "success",
    "requested_language": "en",
    "detected_language": "en",
    "transcript": "when you call someone who is thousands of",
    "segments": [
      {
        "end_s": 2.0,
        "index": 0,
        "start_s": 0.0,
        "text": "when you call someone who is thousands of"
      }
    ],
    "model_id": "openai/whisper-large-v3-turbo",
    "model_revision": "41f01f3fe87f28c78e2fbf8b568835947dd65ed9",
    "runtime_name": "transformers",
    "runtime_version": "5.16.1"
  },
  "claims": {
    "accuracy": false,
    "wer": false,
    "clinical_quality": false,
    "production_authorization": false
  },
  "pass": true
}
```

## 3. Interpretation

```text
REAL_MODEL_RUNTIME_QUALIFICATION = PASS
```

This proves the real runtime path only against the exact governed source head.

Do not confuse any temporary notebook hosting commit with the governed PR head.
The governed head remains c61370664488e4ad3e274ec61a233c46652ec6de.

The transcript comes from the deterministic bounded 2 second derived FLEURS clip.
Do not compare it as a WER claim against the full FLEURS reference sentence.

## 4. Explicit non claims

```text
WER = NOT_CLAIMED
ACCURACY = NOT_CLAIMED
CLINICAL_QUALITY = NOT_CLAIMED
CLINICAL_SAFETY = NOT_CLAIMED
PRODUCTION_AUTHORIZATION = NOT_GRANTED
PHI_AUTHORIZATION = NOT_GRANTED
REMOTE_INFERENCE_AUTHORIZATION = NOT_GRANTED
```

Production remains local only and fail closed under the existing governance.
No PHI and no patient audio and no production use and no EHR write and no remote ASR.
No automatic download and no training and no weight mutation.

## 5. Colab runner repairs

The temporary qualification runner required notebook only Colab compatibility fixes:

```text
1. Normalize FLEURS license metadata when the source returns a list rather than a scalar string.
2. Remove incompatible preinstalled torchvision where the Colab runtime reported a missing operator.
3. Fail early where a contaminated runtime already imported torchvision.
```

These were qualification runner and environment fixes only.
Do not port these changes into the governed application source unless independent repository evidence proves that they belong there.

## 6. Merge gate effect

```text
EXACT_HEAD_CI = PASS
CODEQL = PASS
CODERABBIT = PASS
REAL_MODEL_RUNTIME_QUALIFICATION = PASS
EXPLICIT_PR_BLOCKER real-model qualification pending = SATISFIED
MUST_NOT_MERGE with respect to those explicit blockers = CLEARED
```

Any additional independent gate in the repository governance must still be verified before any merge.
No merge is authorized by this file alone.

## 7. Provenance and boundaries

```text
MODEL_ID = openai/whisper-large-v3-turbo
FULL_IMMUTABLE_REVISION = 41f01f3fe87f28c78e2fbf8b568835947dd65ed9
MODEL_LICENSE = mit
REFERENCE_RUNTIME = transformers 5.16.1 with torch 2.13.0
WEIGHT_SHA256 = 542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1
WEIGHT_SIZE = 1617824864 bytes
FIXTURE_LICENSE = cc-by-4.0
FIXTURE_PHI = NONE
PAID_COMPUTE = NONE
ISSUES_429_450_464 = UNTOUCHED AND SEPARATELY GOVERNED
```

This file records evidence only and changes no application behavior.