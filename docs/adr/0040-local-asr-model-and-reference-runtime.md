# ADR-0040 — Local ASR model and reference runtime for Clinical Workspace

- **Status:** Proposed
- **Date:** 2026-09-22
- **Deciders:** Founder
- **Supersedes:** none
- **Superseded by:** none
- **Related:** Issue #480, ADR-0006, ADR-0012, ADR-0015, ADR-0035, ADR-0038, ADR-0039, R1, R2, R3, R4, R5, R6, R7, specs/medscale-clinical-workspace-v1/tasks.md, specs/medscale-clinical-workspace-v1/capability_map.md, docs/models/model_registry.md, apps/workspace/pyproject.toml, root pyproject.toml

## 1. Live verification basis

All facts below were reverified live on 2026-09-22 before drafting. Live repository, GitHub, Hugging Face, dependency, review tool, and governance truth override any handoff text.

### 1.1 Canonical repository

- Canonical main: ab29ca613cd1ec19460809a2708d2c315d191b9f, verified via git ls-remote origin HEAD and git fetch origin main.
- Canonical tree: 8b94e4f5fb7da3e7faba24c6e4044010c3f3f56f, verified via git show origin/main format %T.
- Default branch: main, verified via gh api repos/TheHalfMoon/MESC default branch.
- Recent canonical history includes merge PR #479 at ab29ca6, which merged the CW-005 closeout reconciliation. Local checkout tree matches canonical tree.

### 1.2 Workstream state

- CW-000 = CLOSED_CANONICAL, CW-001 = CLOSED_CANONICAL, CW-002 = CLOSED_CANONICAL, CW-003 = CLOSED_CANONICAL, CW-004 = CLOSED_CANONICAL, CW-005 = CLOSED_CANONICAL, per specs/medscale-clinical-workspace-v1/tasks.md and closeout records cw-000 through cw-005, consistent with Issue #480 activation record.
- CW-006: tasks.md text states ELIGIBLE not activated, while Issue #480 (OPEN, titled CW-006 Local ASR adapter activation) states CW-006 = IN_PROGRESS and names CW-006 as the single active implementation unit under R4 with CW-007 = BLOCKED_DEPENDENCY and CW-009, CW-011, CW-013, CW-016, CW-017 = ELIGIBLE_NOT_ACTIVATED. The activation issue governs per R4. This ADR records both live facts and treats Issue #480 as the governing activation. The tasks.md wording is stale relative to the activation and must be reconciled forward only by a later closeout, not by editing history.
- CW-007 = BLOCKED_DEPENDENCY, per tasks.md dependency graph (depends on CW-003, CW-004, CW-006).
- CW-009, CW-011, CW-013, CW-016, CW-017 = ELIGIBLE not activated, per tasks.md. No implementation authority exists for any of them.
- Issues #429 (MRL-0809 qualify exact-head RQ1 execution prerequisites, OPEN), #450 (MRL-0809 successor capacity blocker, OPEN), #464 (CW-001 follow-ups, OPEN) remain separately governed, verified via gh issue view. MRL-0809 authority remains independent.
- Open implementation PRs for CW-006: none. Verified via gh pr list state open returning an empty set.

### 1.3 ADR numbering

- Highest canonical ADR is 0039 (docs/adr/0039-local-protected-storage-and-key-management.md), verified via git ls-tree on docs/adr. The next number is 0040. This proposal is ADR-0040.

### 1.4 Dependency contracts

- Root pyproject.toml on origin/main records transformers == 5.16.1 and torch == 2.13.0 inside rq1-grammar, rq1-runtime-feasibility, and training-hf-sft optional dependency sets. Verified via git show origin/main:pyproject.toml. Root pyproject.toml participates in frozen MRL evidence and is not modified by this proposal.
- transformers 5.16.1 verified live on PyPI on 2026-09-22: release 5.16.1 uploaded 2026-08-26, license Apache 2.0, requires Python 3.10 or later.
- torch 2.13.0 verified live on PyPI on 2026-09-22: release 2.13.0 uploaded 2026-07-08 with wheels for Windows amd64, manylinux x86_64 and aarch64, and macOS arm64 across Python 3.10 through 3.14.
- apps/workspace/pyproject.toml on canonical main declares exactly one runtime dependency: cryptography == 50.0.1, with a comment binding it to ADR-0039 decisions 5 and 7 as amended by A1.8. Verified via git show HEAD:apps/workspace/pyproject.toml. No ASR dependency exists yet.
- No ASR adapter module exists under apps/workspace/src/medscale_workspace, verified via git ls-tree on apps/workspace. No audio fixture files exist in the canonical tree, verified via full git ls-tree scan. fixtures.py provides synthetic patient and encounter fixtures only.

### 1.5 Capability and registry

- Capability map (specs/medscale-clinical-workspace-v1/capability_map.md) records Medical ASR as BUILD adapter with V1 acceptance idea of local adapter, exact runtime identity, no silent cloud. Disposition is planning only and is not implementation authority.
- Model registry (docs/models/model_registry.md) contains zero ASR entries. Verified by reading the canonical file.
- CW-006 ledger acceptance (tasks.md): exact model and runtime revision recorded, local path runs with network blocked, missing model fails explicitly, timestamps preserved, partial and failure outputs represented, Arabic and English capability only claimed if separately measured, no automatic model download during protected offline execution. Stop conditions: only available backend requires sending audio remotely, or model and license cannot support intended distribution and use.

## 2. Context

CW-006 requires an offline ASR adapter with synthetic or permitted fixtures, but the exact model, runtime, revision, and license are not canonically determined anywhere in live governance. ADRs 0006, 0015, 0038, and 0039 are silent on ASR models. The model registry has no ASR row. The capability map requires exact runtime identity but names no model and confers no implementation authority. Issue #480 therefore determines that model, runtime, and license selection requires a new ADR with Founder ratification and an explicit license decision before any model artifact is admitted or any capability claim is made.

The Founder selects the following direction for this proposal: MODEL_FAMILY = OpenAI Whisper, PRIMARY_MODEL_ID = openai/whisper-large-v3-turbo, REFERENCE_RUNTIME = Hugging Face Transformers plus PyTorch, with INTENDED_RUNTIME_VERSIONS transformers == 5.16.1 and torch == 2.13.0. This direction is a proposal input only. It is not implementation authority until this ADR is ratified under R6.

R6 applies because a model and runtime choice costs more than one day to reverse once fixtures, manifests, adapters, and qualification evidence bind to it. R1 applies to every identity below. R2 keeps development synthetic only. R3 requires permissive licensing for anything shipped. R4 makes CW-006 the single active unit. R5 and R7 forbid quality claims without executed runs and committed artifacts.

## 3. Decision

1. Adopt openai/whisper-large-v3-turbo at immutable revision 41f01f3fe87f28c78e2fbf8b568835947dd65ed9 as the single intended local ASR model for CW-006 v1, subject to Founder ratification of this ADR and to the protected execution contract in section 8.
2. Adopt Hugging Face Transformers == 5.16.1 with PyTorch == 2.13.0 as the single reference runtime for CW-006 v1, subject to Founder ratification and to qualification proving the load path operates with permitted fixtures.
3. Authorize a Workspace scoped optional dependency surface named asr-local only after ratification and only under CW-006 authority. Do not convert ASR into an unconditional dependency of the basic Workspace shell. Do not modify root pyproject.toml or uv.lock in this proposal.
4. Require a deterministic local ASR artifact manifest that binds the identities in section 4 and section 7, verified by the adapter before model use. No mutable main identity satisfies the manifest.
5. Require the protected inference path to be local only with trust_remote_code = false and local_files_only = true, no runtime model download, no implicit Hub acquisition, no network fallback, no remote inference provider, no cloud ASR fallback, and no telemetry containing audio or transcript content. Fail closed on absent artifact, revision mismatch, manifest mismatch, or network access attempt.
6. Require CPU as a supported local execution path. Permit GPU acceleration only as an explicit local capability when the required local runtime exists. Forbid remote execution fallback and silent model identity alteration on device fallback.
7. Plan a typed adapter contract distinguishing SUCCESS, PARTIAL, and FAILED, with transcript text, segment identity, start timestamp, end timestamp, detected and requested language state, model ID, model revision, runtime identity, input and session identity, and failure or partial reason. Model output remains untrusted data subject to validation.
8. Define the qualification fixture policy in section 12: no fabricated speech fixtures, no PHI, no patient derived content, synthetic or mock outputs for unit tests, and permitted real audio with exact source, license, digest, language, declared expected content, and no PHI for actual model load qualification. Record the current absence of canonically available Arabic and English fixtures as a separate qualification input requirement.
9. Record faster-whisper and CTranslate2 as a future separately qualified optimization backend, not the v1 reference runtime, for the reasons in section 13.
10. Make no Arabic quality claim, no English quality claim, and no clinical ASR quality claim without measurement under R5 and R7.

## 4. Exact model identity

All identities below were resolved live on 2026-09-22 against the Hugging Face Hub and are bound to the immutable revision. Do not use main as a reproducibility identity.

| Field | Value |
|---|---|
| MODEL_ID | openai/whisper-large-v3-turbo |
| FULL_IMMUTABLE_REVISION | 41f01f3fe87f28c78e2fbf8b568835947dd65ed9 |
| REVISION_SOURCE | Hugging Face Hub commit SHA returned as sha for the model at query time and confirmed at the revision endpoint |
| MODEL_ARCHITECTURE | WhisperForConditionalGeneration |
| MODEL_TYPE | whisper |
| AUTO_MODEL | AutoModelForSpeechSeq2Seq |
| PROCESSOR_CLASS | WhisperProcessor |
| FEATURE_EXTRACTOR_TYPE | WhisperFeatureExtractor |
| TOKENIZER_CLASS | WhisperTokenizer |
| PARAMETER_COUNT | 808878080 total, F16 safetensors parameters total 808878080 |
| MODEL_LICENSE | mit |
| PIPELINE_TAG | automatic-speech-recognition |
| LIBRARY_NAME | transformers |
| BASE_MODEL | openai/whisper-large-v3 |
| MODEL_CARD_IDENTITY | README.md, blob 0bbe30273338d7e19f779c1343808e32617e64d1, size 21196 bytes at the pinned revision |
| MODEL_CONFIG_IDENTITY | config.json, blob ad2f44ff1ed66e12765b2392dc041469db91a462, size 1256 bytes at the pinned revision |
| GENERATION_CONFIG_IDENTITY | generation_config.json, blob cbe752958dc3e4671b0e0220aa1c545423a6d5f5, size 3772 bytes at the pinned revision |
| PROCESSOR_IDENTITY | preprocessor_config.json, blob 931c77a740890c46365c7ae0c9d350ba3cca908f, size 340 bytes at the pinned revision |
| TOKENIZER_IDENTITY | tokenizer.json, blob 17456db595adc78a973f97d69d8cb50bc87c0b1c, size 2710337 bytes at the pinned revision |
| TOKENIZER_CONFIG_IDENTITY | tokenizer_config.json, blob 06ffdc8308eae6bb7bd1fdd81e94b0a881a539ab, size 282843 bytes at the pinned revision |
| VOCAB_IDENTITY | vocab.json, blob 0f3456460629e21d559c6daa23ab6ce3644e8271, size 1036558 bytes at the pinned revision |
| MERGES_IDENTITY | merges.txt, blob 6038932a2a1f09a66991b1c2adae0d14066fa29e, size 493869 bytes at the pinned revision |
| WEIGHT_FILE_IDENTITY | model.safetensors, blob d31c58c2bcd43b726463567df91f9a2b0581dd8e, size 1617824864 bytes at the pinned revision |
| WEIGHT_SHA256 | 542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1, LFS sha256 for model.safetensors at the pinned revision |
| EXPECTED_ARTIFACT_SIZE | 1617824864 bytes for model.safetensors, LFS size 1617824864, pointer size 135 |
| CONFIG_TORCH_DTYPE | float16 |
| CONFIG_VOCAB_SIZE | 51866 |
| CONFIG_ENCODER_LAYERS | 32 |
| CONFIG_DECODER_LAYERS | 4 |
| CONFIG_D_MODEL | 1280 |
| CONFIG_TRANSFORMERS_VERSION_AT_AUTHORING | 4.46.0.dev0 as recorded in config.json transformers_version |
| TOKENIZER_TRUST_REMOTE_CODE | false as recorded in tokenizer_config.json |

Config highlights at the pinned revision, verified via resolve endpoints: d model 1280, encoder attention heads 20, encoder layers 32, decoder attention heads 20, decoder layers 4, decoder FFN dim 5120, encoder FFN dim 5120, max source positions 1500, max target positions 448, num mel bins 128, sampling rate 16000, chunk length 30, n samples 480000, feature size 128, bos token id 50257, eos token id 50257, pad token id 50257, decoder start token id 50258. Preprocessor processor class WhisperProcessor. Tokenizer processor class WhisperProcessor and tokenizer class WhisperTokenizer. Language tokens in the pinned tokenizer include tokens for en and ar among the multilingual set, recorded descriptively only with no quality implication.

If any Hugging Face metadata, file, license, or revision differs from the table at ratification or qualification time, record the live result and stop before ratification or admission. Do not guess any value.

## 5. License and provenance review

Upstream license evidence, verified live at the pinned revision on 2026-09-22:

- Hugging Face model API tags include license:mit.
- Hugging Face model API cardData license is mit.
- Pinned README.md frontmatter license is mit.
- No gated flag is set. Gated is false. Disabled is false. Visibility is public.

License compatibility assessment for MedScale Apache-2.0 project distribution:

- MIT permits derivatives and commercial use with no copyleft and no terms passthrough beyond preserving the MIT notice. It satisfies R3 and the Tier 1 criterion in docs/models/model_registry.md.
- MIT is compatible with Apache-2.0 project distribution for the planned use: local optional adapter dependency plus separately acquired model artifact, with attribution and notice handling recorded at implementation time. No upstream use policy passthrough was observed in the verified card and API metadata.
- Compatibility is not inferred from repository visibility. It rests on the three MIT declarations above, all verified at the pinned revision.
- Training data lineage for the model weights is not fully stated in the verified card beyond base model openai/whisper-large-v3 and the paper reference arXiv 2212.04356. No additional rights claim is made here. The model is treated as an inference artifact under the protected contract, with no training, fine tuning, weight mutation, or data extraction authority.

Provenance chain recorded: author openai, modelId openai/whisper-large-v3-turbo, created 2024-10-01, last modified 2024-10-04T14:51:11Z, base model openai/whisper-large-v3, paper Robust Speech Recognition via Large-Scale Weak Supervision. Any future admission must reverify that the pinned revision still resolves and that the license declarations are unchanged.

## 6. Language claim boundary

Upstream model metadata indicates multilingual support and includes Arabic and English:

- Hugging Face tags include ar and en among the language list.
- cardData language list includes en and ar among 99 entries.
- Pinned README frontmatter language list includes en and ar.
- Pinned tokenizer added tokens include the ar token and the en token.

MESC must not convert upstream metadata into a measured product quality claim. Therefore:

- ARABIC_SUPPORTED_BY_UPSTREAM_METADATA may be recorded descriptively.
- ENGLISH_SUPPORTED_BY_UPSTREAM_METADATA may be recorded descriptively.
- ARABIC_QUALITY_CLAIM is NOT AUTHORIZED WITHOUT MEASUREMENT.
- ENGLISH_QUALITY_CLAIM is NOT AUTHORIZED WITHOUT MEASUREMENT.
- CLINICAL_ASR_QUALITY_CLAIM is NOT AUTHORIZED WITHOUT MEASUREMENT.

No WER, no latency, no accuracy, no intelligibility, and no clinical utility claim is made in this ADR. Any such claim requires a separate measured qualification under R5 and R7 with committed scripts and artifacts, using permitted fixtures only.

## 7. Runtime decision and Workspace dependency plan

Reference runtime: transformers == 5.16.1 with torch == 2.13.0.

Why these versions:

- Both versions are already represented in canonical MESC dependency contracts (rq1-grammar, rq1-runtime-feasibility, training-hf-sft), verified in section 1.4.
- Both versions were verified live on PyPI on 2026-09-22.
- Reusing the canonical versions avoids introducing a second Transformers and PyTorch lineage for Workspace ASR v1.

Important qualification notes:

- The pinned model config records transformers_version 4.46.0.dev0 at authoring time. The reference runtime pins the newer canonical 5.16.1. Compatibility of the pinned artifact with 5.16.1 for the exact load and transcribe path is a qualification requirement, not an assumption. Qualification must prove the runtime path operates with permitted fixtures. If qualification fails, record the failure and stop rather than silently changing versions or loosening the manifest.
- No claim is made here that CPU and GPU numerical outputs are identical or that performance is identical across devices. See section 9.

Dependency plan:

- This proposal modifies no root pyproject.toml, no uv.lock, and no other frozen MRL artifact. The proposal diff is limited to this ADR file until ratification.
- After ratification, and only under CW-006 authority, authorize a Workspace scoped optional dependency surface such as asr-local, for example an optional group in apps/workspace/pyproject.toml binding transformers == 5.16.1 and torch == 2.13.0 for the ASR adapter path.
- Prefer an optional group rather than converting ASR into an unconditional dependency of the basic Workspace shell, unless repository architecture proves otherwise at implementation time. CW-005 must remain independently functional without CW-006. The basic shell without the asr-local group must install, import, and test without the ASR runtime.
- Any dependency change occurs after ADR acceptance under CW-006 authority, with its own exact head qualification, license review, boundary guard update if required, and fresh main qualification. If the proposed Workspace dependency design requires mutation of frozen MRL evidence, redesign the Workspace surface or stop and report the conflict. Issues #429 and #450 remain untouched. MRL-0809 authority remains independent.

## 8. Protected execution contract

The CW-006 production and protected inference path is local only.

Required behavior:

- trust_remote_code = false.
- local_files_only = true.
- No runtime model download.
- No implicit Hugging Face Hub acquisition.
- No network fallback.
- No remote inference provider.
- No cloud ASR fallback.
- No telemetry containing audio or transcript content.
- The protected adapter receives a previously acquired, verified local model snapshot path.
- Model acquisition is a separate explicit setup or acquisition operation and must not occur silently during protected transcription.

Fail closed conditions:

- If the local artifact is absent, fail closed.
- If the revision or manifest does not match, fail closed.
- If the runtime attempts network access, fail closed.
- If trust_remote_code would be required, fail closed.
- If the caller requests a remote backend, fail closed.

The pinned tokenizer records trust_remote_code false, consistent with the required behavior. The adapter must pass trust_remote_code false and local_files_only true explicitly in code rather than relying on defaults, and tests must assert the fail closed behavior with network blocked, missing artifact, and mismatched manifest fixtures.

## 9. Artifact manifest

Define a deterministic local ASR artifact manifest that binds at minimum:

- model_id: openai/whisper-large-v3-turbo
- model_revision: 41f01f3fe87f28c78e2fbf8b568835947dd65ed9
- model_license: mit with source references to the pinned README frontmatter and Hub API cardData
- runtime_name: transformers
- runtime_version: 5.16.1
- torch_version: 2.13.0
- model config digest: config.json blob ad2f44ff1ed66e12765b2392dc041469db91a462
- processor digest: preprocessor_config.json blob 931c77a740890c46365c7ae0c9d350ba3cca908f
- tokenizer digests: tokenizer.json blob 17456db595adc78a973f97d69d8cb50bc87c0b1c, tokenizer_config.json blob 06ffdc8308eae6bb7bd1fdd81e94b0a881a539ab, vocab.json blob 0f3456460629e21d559c6daa23ab6ce3644e8271, merges.txt blob 6038932a2a1f09a66991b1c2adae0d14066fa29e
- generation config digest: generation_config.json blob cbe752958dc3e4671b0e0220aa1c545423a6d5f5
- weight digest: model.safetensors blob d31c58c2bcd43b726463567df91f9a2b0581dd8e with LFS sha256 542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1 and size 1617824864
- fixture identity policy reference per section 12
- supported adapter contract version

The adapter must verify the manifest before model use. Verification includes model ID equality, revision equality, digest equality for config, processor, tokenizer, and weight artifacts, license string equality, and runtime version equality. No mutable main identity satisfies the manifest. Any mismatch fails closed with an explicit error that carries no audio or transcript content.

## 10. Runtime and device policy

- CPU is a supported local execution path for the reference runtime.
- GPU acceleration may be supported only as an explicit local capability when the required local runtime exists on the machine. GPU presence is never required for correctness of the CPU path.
- No GPU absence triggers remote execution. No device fallback silently alters model identity. Device selection is explicit and recorded in the output per section 11.
- Do not claim identical performance or identical numerical output across CPU and GPU unless measured under R5 and R7.
- Do not make bitwise determinism claims that are not proven. If determinism is later required, it needs its own measured contract.
- Windows and Linux support follows from the verified torch 2.13.0 wheels (Windows amd64 present) and the pure Python Transformers distribution, but actual Workspace qualification must still execute on the governed runners and record the result. No platform claim beyond the verified artifact availability is made here.

## 11. ASR adapter contract

Plan a typed adapter whose output distinguishes at least:

- SUCCESS: complete transcript produced and validated.
- PARTIAL: partial transcript produced with an explicit reason, for example truncated input, low confidence handling per runtime semantics, or interrupted decoding, without implying completeness.
- FAILED: no usable transcript, with an explicit reason, for example missing artifact, manifest mismatch, unsupported input, malformed runtime output, or validation failure.

Output carries, where produced by the runtime:

- transcript text
- segment identity
- start timestamp per segment
- end timestamp per segment
- detected and requested language state
- model ID
- model revision
- runtime identity including transformers version and torch version
- input identity and session identity for Workspace binding
- failure or partial reason

Validation rules:

- Model output remains untrusted data.
- Malformed timestamps fail validation.
- Impossible segment ordering fails validation.
- Non finite values fail validation.
- Output bound to the wrong session or workspace fails validation.
- Missing required identity fields fail validation.
- Partial output must be labeled PARTIAL and must not be presented as SUCCESS.
- Timestamps are preserved from the runtime through the adapter without silent rewriting. Any normalization is explicit, versioned, and tested.

The adapter contract version is part of the artifact manifest in section 9. Contract changes require their own review and version bump.

## 12. Scope restrictions

CW-006 does not authorize:

- live microphone capture
- device capture
- remote ASR
- diarization unless separately governed
- speaker identity
- clinical finalization
- EHR writes
- PHI ingestion
- real patient audio
- training
- fine tuning
- weight mutation
- automatic model download
- remote model egress
- paid inference
- research admission

Additional non grants for this turn:

- PHI_INGESTION = NOT_AUTHORIZED
- REAL_PATIENT_AUDIO = NOT_AUTHORIZED
- CLINICAL_PRODUCTION_USE = NOT_AUTHORIZED
- EHR_WRITE = NOT_AUTHORIZED
- REMOTE_ASR = NOT_AUTHORIZED
- AUTOMATIC_MODEL_DOWNLOAD = NOT_AUTHORIZED
- TRAINING = NOT_AUTHORIZED
- WEIGHT_MUTATION = NOT_AUTHORIZED
- RESEARCH_ADMISSION_FROM_WORKSPACE = NOT_AUTHORIZED
- NEW_MRL_STAGE4_ATTEMPT = NOT_AUTHORIZED
- PAID_COMPUTE = NOT_AUTHORIZED

CW-005 remains independently functional without CW-006. The CW-004 no backflow guard and data classification, the CW-003 provenance and audit spine, and the CW-002 protected storage remain binding and are not weakened by this ADR.

## 13. Fixture decision

Fixture policy:

- Do not fabricate speech fixtures.
- Any real speech fixture used for model qualification must have exact source, license and permission, immutable identity, digest, language, declared expected content, no PHI, and no patient derived content.
- Adapter unit tests may use synthetic or mock runtime outputs that do not exercise the real model weights.
- Actual model load qualification must use permitted real audio sufficient to prove the runtime path operates, but one or two fixtures must not be converted into a general WER or clinical quality claim.

Live fixture availability on 2026-09-22:

- No canonical Arabic audio fixture is available in the repository.
- No canonical English audio fixture is available in the repository.
- The full canonical file listing contains no wav, flac, or mp3 fixture for ASR qualification.
- fixtures.py provides synthetic patient and encounter objects only.

Therefore the absence of suitable Arabic and English fixtures is recorded as a separate qualification input requirement. Implementation must not begin model load qualification until permitted fixtures with the provenance fields above are admitted under CW-006 authority, or must explicitly record that model load qualification is blocked pending those inputs. Synthetic unit tests for manifest verification, fail closed behavior, timestamp validation, and contract typing may proceed without real audio, but they do not qualify the model path.

## 14. Why faster-whisper is not the reference runtime for CW-006 v1

faster-whisper was evaluated live on 2026-09-22: PyPI package faster-whisper, latest 1.2.1, license MIT, description Faster Whisper transcription with CTranslate2, requiring ctranslate2, huggingface-hub, tokenizers, onnxruntime, av, tqdm. Its documented behavior includes automatically downloading the corresponding CTranslate2 model from the Hugging Face Hub when loading by size name, plus a conversion script from Transformers checkpoints.

Record faster-whisper as a future separately qualified optimization backend, not the v1 reference, because the initial reference must avoid introducing:

- CTranslate2 specific runtime semantics in addition to Transformers and PyTorch
- a second transformed weight identity in addition to the verified safetensors artifact
- third party converted model artifacts with separate conversion provenance
- extra conversion provenance and quantization semantics that would need their own manifest and qualification

Do not reject faster-whisper permanently. It may be valuable later as an optimized backend after the Transformers reference path is qualified, with its own exact version, converted artifact digests, license review, offline behavior proof, and manifest extension. Unless live evidence strongly contradicts this approach at implementation time, the optimization path stays open but separate.

## 15. Alternatives considered

Comparison without marketing language and without measured accuracy claims. No alternative below was measured in this ADR. Any performance or quality ordering would require separate measured qualification.

| Dimension | whisper-large-v3-turbo plus Transformers and PyTorch (selected reference) | whisper-large-v3 plus Transformers and PyTorch | faster-whisper and CTranslate2 | whisper.cpp |
|---|---|---|---|---|
| Live identity verified | openai/whisper-large-v3-turbo, revision 41f01f3fe87f28c78e2fbf8b568835947dd65ed9, 808878080 params, MIT | openai/whisper-large-v3, revision 06f233fe06e710322aca913c1bc4249a0d71fce1 at query time, 1543490560 params, Apache-2.0 | PyPI faster-whisper 1.2.1, MIT, requires ctranslate2 4 or later | repository ggerganov/whisper.cpp, license MIT via API |
| License | MIT, Tier 1, no passthrough observed | Apache-2.0, Tier 1 | MIT for the wrapper, but converted weight provenance separate | MIT for the engine, but model file provenance separate |
| Artifact provenance | Single verified safetensors artifact with LFS sha256 recorded in section 4 | Multiple weight formats observed in siblings including safetensors shards and pytorch bins, larger provenance surface | Converted CTranslate2 artifacts, auto download by default, second weight identity | Converted ggml style weights with separate conversion step, second weight identity |
| Runtime complexity | Transformers plus PyTorch, already in canonical contracts | Same runtime family, larger model cost | Adds CTranslate2 plus onnxruntime plus av plus conversion tooling | Adds native build, model conversion, and platform specific binaries |
| Offline behavior | Qualifiable to local files only with fail closed contract | Same contract shape, larger artifact | Auto download default contradicts the no download contract unless separately constrained and qualified | Local capable, but conversion and build provenance need separate qualification |
| Windows and Linux support | torch 2.13.0 wheels verified for Windows amd64 and Linux, Transformers pure Python | Same runtime availability, larger memory and compute demand | GPU path needs CUDA 12 plus cuDNN 9 per upstream notes, Windows path needs separate library handling | Cross platform native builds exist, but Workspace integration would need its own build and test matrix |
| CPU feasibility | CPU supported path required in section 10, smaller decoder stack than large-v3 (4 decoder layers versus 32) | CPU path possible but larger cost with 1550M class params and deeper decoder | CPU capable with quantization options, but that adds quantization semantics to qualify | CPU oriented design, but still needs conversion qualification and integration work |
| GPU feasibility | Explicit local GPU only, no remote fallback | Same policy, larger VRAM demand | GPU capable, but CUDA and cuDNN prerequisites expand the install surface | GPU paths exist per platform, with separate backend qualification |
| Dependency footprint | Reuses canonical 5.16.1 and 2.13.0, optional asr-local group | Same footprint, larger artifact size and cost | New required dependencies ctranslate2, onnxruntime, av, plus conversion dependencies | New native toolchain and converted artifact lineage |
| Model conversion requirements | None, direct safetensors use | None for safetensors path, but multiple formats invite selection risk | Conversion required for any custom checkpoint, with copy files handling for tokenizer and preprocessor | Conversion required from source weights to engine format |
| Reproducibility | Pinned revision plus blob digests plus manifest in sections 4 and 9 | Same mechanism, different digests and larger size | Would need pinned wrapper version plus pinned converted artifact digests plus conversion procedure | Would need pinned engine revision plus pinned converted artifact digests plus conversion procedure |
| Arabic and English upstream support | Both listed descriptively, no quality claim | Both listed descriptively, no quality claim | Inherits upstream model support through conversion, no independent quality claim | Inherits upstream model support through conversion, no independent quality claim |
| Future optimization path | faster-whisper and whisper.cpp remain open as separately qualified backends | Same, but starting from a larger baseline weakens the efficiency case | Candidate optimization backend after reference qualification | Candidate optimization backend for constrained devices after reference qualification |
| Verdict | Selected as v1 reference for provenance simplicity, canonical version reuse, and offline contract clarity | Rejected as v1 reference because it is larger in parameter count and artifact size with no governance benefit over turbo for the adapter v1 | Deferred as future optimization backend for the reasons in section 14 | Deferred as future constrained device backend, not the v1 reference |

Additional rejected direction: selecting main or any floating tag as the model identity. Rejected because mutable identities cannot satisfy the manifest in section 9 and violate R1 and R5.

## 16. Consequences

Positive:

- Exact model, revision, config, processor, tokenizer, weight digest, license, and runtime versions are bound before any implementation, closing the CW-006 blocker identified in Issue #480.
- Reuse of canonical transformers 5.16.1 and torch 2.13.0 avoids a second dependency lineage and keeps the basic Workspace shell independent of ASR until the optional asr-local group is explicitly installed.
- Local only contract with fail closed behavior preserves ADR-0038 trust boundaries, CW-002 storage guarantees, CW-003 provenance and audit separation, and CW-004 no backflow and classification.
- Deterministic manifest gives implementation, review, and qualification a single verification target.
- Deferring faster-whisper and whisper.cpp avoids conversion provenance and second weight identities in v1 while keeping measured optimization paths open.

Negative and costs:

- The pinned artifact is about 1.6 GB for model.safetensors alone. Local acquisition, storage, verification time, and test runtime must account for that size. No size based shortcut may bypass manifest verification.
- Qualification is blocked until permitted Arabic and English fixtures with full provenance are admitted. Synthetic unit tests alone do not qualify the model path.
- Transformers 5.16.1 compatibility with the pinned artifact for the exact load path must be proven, not assumed, given the authoring time transformers_version 4.46.0.dev0 recorded in config.json.
- One more optional dependency surface enters the Workspace package after ratification, with its own license review, boundary guard review, and test matrix.
- No quality, latency, or clinical utility claim is granted by this ADR. Any such claim needs separate measured work.

## 17. Compliance

Enforcement:

- No CW-006 implementation begins until the Founder ratifies this ADR under R6 with an explicit decision sentence. Proposal alone grants no implementation authority.
- After ratification, CW-006 implementation must demonstrate the manifest verification, local files only behavior with network blocked, missing artifact failure, revision mismatch failure, timestamp preservation, SUCCESS versus PARTIAL versus FAILED typing, and no automatic download behavior, all bound to the exact qualified head.
- The Workspace boundary guard, classification vocabulary, provenance and audit spine, and storage envelope remain binding. Any required guard change needs its own reviewed diff and cannot be slipped in silently.
- Dependency changes occur only in apps/workspace scope under CW-006 authority after ratification. Root pyproject.toml, uv.lock, and other frozen MRL artifacts are not modified to enable Workspace ASR. If a conflict arises, the Workspace surface is redesigned or work stops with a conflict report.
- Fixture admission follows section 13. No PHI, no patient derived content, no fabricated fixtures.
- Language and quality claims follow section 6. Any measured claim needs committed scripts and artifacts under R5 and R7.
- Follow-up items owned by CW-006 implementation, not by this ADR: adapter module, manifest verifier, optional asr-local group definition, synthetic unit tests, permitted fixture admission, model load qualification with network blocked, and closeout evidence.

R6 lifecycle for this ADR:

- Propose: this file on a governed ADR branch with exact head qualification, independent review lanes, and a PR that qualifies on fresh main without merging into main until ratification.
- Wait for approval: stop at the Founder ratification gate. Do not merge an ADR that repository governance requires the Founder to ratify before merge or acceptance.
- Implement: only after explicit Founder ratification, under the separately activated CW-006 unit, with forward only corrections and no force push, no rebase of shared history, no protection bypass, and no mutation of frozen MRL evidence.

## 18. Review lanes

Three lanes are required by the tasking for this ADR. Each tool was verified live before use. Results are recorded here and in the PR evidence. No lane is skipped.

- Alibaba Open Code Review: version open-code-review v1.12.9 windows amd64, verified live via ocr version on 2026-09-22. Only actual supported paths are used. Markdown and ADR files excluded by default are reviewed manually. No OCR LLM reasoning is claimed unless an LLM endpoint performed it.
- Jev bounded review: version 0.3.2 via the skill script absolute path with Python 3.11 and TypeSafe provider auto configured, verified live via auth status on 2026-09-22. Bounded architecture, model, runtime, and license screening only. No PHI, secrets, credentials, sealed MRL material, or patient content is sent. Jev results are screening only and every material finding is independently verified.
- Host agent architecture, security, and license review: challenges license compatibility, model provenance, revision immutability, silent downloads, network fallback, trust_remote_code, dependency expansion, Windows and Linux feasibility, CPU and GPU behavior, fixture provenance, timestamp semantics, cross workspace and session binding, and MRL evidence drift.

Review evidence status: lane runs completed on 2026-09-22 after the initial draft. Results are recorded in section 21. No lane was skipped.

## 19. Verification and review run record

Completed forward only in section 21 before opening the governed ADR PR. The checklist below was the pre-run plan and is superseded by section 21. No result is written from memory.

- Canonical main and tree reverification: recorded in section 1.1.
- Hugging Face identities: recorded in section 4 with blob IDs, sizes, LFS sha256, and config highlights.
- License and provenance: recorded in section 5.
- PyPI runtime identities: recorded in sections 1.4 and 7.
- Alternative identities: recorded in sections 14 and 15.
- OCR run: pending entry with exact version, executable, paths, and findings.
- Jev run: pending entry with exact version, spec or questions, inputs, and screening outputs.
- Host review: pending entry with challenges and dispositions.
- Repair: pending entry listing every file change made in response to review, with reasons.

## 20. Explicit non grants restated

This ADR alone grants no PHI ingestion, no real patient audio, no clinical production use, no EHR write, no remote ASR, no automatic model download, no training, no weight mutation, no research admission from Workspace state, no new MRL Stage 4 attempt, and no paid compute. Implementation authority, if ever granted, comes only from explicit Founder ratification of this ADR followed by governed CW-006 implementation under Issue #480, with its own exact head and fresh main qualification.

## 21. Repair log and completed review evidence

### 21.1 OCR lane

- Tool: open-code-review v1.12.9 windows amd64, build 2026-09-22T11:06:41Z, verified live via ocr version.
- Preview command: ocr review --preview --audience agent
- Preview result: 1 file changed, plus 415 minus 0. Excluded from review (1): A docs/adr/0040-local-asr-model-and-reference-runtime.md (unsupported_ext).
- Review command: ocr review --audience agent --format json
- Review result: exit non-zero with Error: resolve LLM endpoint: no valid LLM endpoint configured; one of OCR_LLM_URL slash OCR_LLM_TOKEN slash OCR_LLM_MODEL, config file, or ANTHROPIC variables must be set.
- Disposition: no OCR LLM reasoning was performed and none is claimed. The ADR markdown exclusion is expected per the tasking. The ADR was reviewed manually under the host lane. No code change was required for OCR because there is no reviewable code in this proposal.

### 21.2 Jev lane

- Tool: jev 0.3.2 via absolute skill script path with Python 3.11, provider TypeSafe auto via environment, model jev-1.13.0, verified live via version and auth status on 2026-09-22.
- Scope: bounded architecture, model, runtime, and license screening only. Input was the public ADR draft only. No PHI, secrets, credentials, sealed MRL material, or patient content was sent.
- All four screens used yes with explicit true and false criteria, stdin from the ADR file, and JSON output. Exit 1 means no, per the CLI contract. All material findings were independently verified against the file and the live sources in section 1.

Screen 1, remote authorization:

    command: python scripts/jev yes [remote or cloud ASR authorization question] -s @docs/adr/0040-local-asr-model-and-reference-runtime.md --json
    result: noul 0.01, yes false, exit 1
    independent verification: confirmed, section 8 requires local only and forbids remote inference.

Screen 2, mutable identity:

    result: noul 0.01, yes false, exit 1
    independent verification: confirmed, section 4 binds immutable revision 41f01f3fe87f28c78e2fbf8b568835947dd65ed9 and section 9 rejects mutable main.

Screen 3, measured quality claim:

    result: noul 0.02, yes false, exit 1
    independent verification: confirmed, section 6 authorizes no quality claim without measurement and the file contains no WER or accuracy claim.

Screen 4, frozen evidence modification:

    result: noul 0.02, yes false, exit 1
    independent verification: confirmed via git status showing only the new ADR file, with no modification to root pyproject.toml or uv.lock.

- Disposition: Jev results are screening only. No ADR change was required by Jev. The four screens agree with independent verification.

### 21.3 Host review

Challenges and dispositions:

- License compatibility: challenged. Disposition: pass. MIT declarations verified at three points at the pinned revision, Tier 1 assessment recorded, no passthrough observed, attribution handling deferred to implementation.
- Model provenance: challenged. Disposition: pass. Author, base model, paper reference, creation and modification dates, and full blob identities recorded with revision binding.
- Revision immutability: challenged. Disposition: pass. Full 40 character SHA bound in decision, manifest, and contract. Mutable main explicitly rejected with stop rule on drift.
- Silent downloads: challenged. Disposition: pass. No runtime download, no implicit Hub acquisition, explicit snapshot path, fail closed tests required.
- Network fallback: challenged. Disposition: pass. No network fallback, no remote provider, no cloud fallback, network access attempt fails closed.
- trust_remote_code: challenged. Disposition: pass. Required false in contract and adapter, consistent with pinned tokenizer value false, explicit in code rather than by default.
- Dependency expansion: challenged. Disposition: pass with repair. Optional asr-local group only after ratification under CW-006 authority, basic shell stays independent, frozen MRL files untouched in this proposal.
- Windows and Linux feasibility: challenged. Disposition: pass with qualification note. Wheel availability verified live, actual runner qualification still required, no platform claim beyond verified artifact availability.
- CPU and GPU behavior: challenged. Disposition: pass. CPU required, GPU explicit local only, no remote fallback, no identical output or determinism claim without measurement.
- Fixture provenance: challenged. Disposition: pass. No fabricated fixtures, full provenance fields required, current absence of canonical Arabic and English fixtures recorded as blocking input for model load qualification.
- Timestamp semantics: challenged. Disposition: pass. Preservation required, malformed or impossible ordering or non finite values fail validation, no silent rewriting.
- Cross workspace and session binding: challenged. Disposition: pass. Wrong session or workspace binding fails validation, CW-004 and CW-003 boundaries preserved.
- MRL evidence drift: challenged. Disposition: pass. No root pyproject.toml or lock change, Issues 429 and 450 untouched, MRL-0809 independent, tasks.md staleness recorded without rewriting history.
- Language hygiene: challenged. Disposition: pass. File contains English only and zero apostrophe characters, verified via pattern search returning count 0.

### 21.4 Repairs applied forward only

- Section 18 status sentence replaced to record completed runs and point to section 21. Reason: the proposal time wording was stale after the runs.
- Section 19 intro replaced to mark the checklist as superseded by section 21. Reason: avoid leaving pending language in a reviewed proposal.
- Alternatives verdict wording changed from larger and costlier to larger in parameter count and artifact size. Reason: host review flagged costlier as potentially reading as measured. The comparison now rests only on verified parameter counts and byte sizes, consistent with the no measurement statement in section 15.
- This section 21 appended with the complete run record. Reason: R5 requires executed commands with observed outputs, not claims.
- No model identity, revision, digest, license, version, contract, manifest, or scope value was changed by repair. All identities remain as verified in sections 1, 4, 5, and 7.
