# Clinical Workspace V1 — Data Security and Threat Model

- **Status:** Proposed planning contract
- **Date:** 2026-09-20
- **Parent:** [Clinical Workspace V1](README.md)
- **Authority:** planning only; no PHI ingestion or clinical deployment authority

## 1. Security objective

The Workspace must be safe to implement before it is safe to use with sensitive clinical data.

The primary security invariant is:

```text
Workspace clinical state is local, encrypted, policy-scoped, auditable,
and mechanically unable to flow into Research Core evidence paths.
```

Security controls must remain useful even when every model output is wrong, a document is malicious, a connector is compromised, or the network is unavailable.

## 2. Trust domains

### R — Research Core

Trusted for:
- versioned research interfaces;
- synthetic-only research artifacts;
- reproducibility and benchmark machinery.

Not trusted for:
- direct access to patient/workspace state.

### W — Workspace

Trusted only within the local product policy for:
- patient/encounter state;
- recordings/transcripts;
- drafts;
- local evidence context;
- graphs/indexes;
- audit state.

Not trusted as:
- research gold;
- training data;
- MRL evidence;
- publication evidence.

### X — Explicit export/admission staging

A quarantine boundary for user-directed exports and future research-admission workflows.

Data in X remains outside Research Core until a separate accepted source/data decision admits it.

### E — External connector/service

Any network endpoint, EHR, literature provider, model provider, sync provider, or remote store.

Default trust:
`UNTRUSTED / OPTIONAL / EXPLICITLY PERMISSIONED`.

### P — Plugin/model runtime

Local or remote extensions that can process content.

Default trust:
`UNTRUSTED INPUT PROCESSOR`.

## 3. Data-flow rules

Allowed:

```text
R -> W : versioned schemas, validators, evidence primitives, released artifacts
W -> X : explicit user export only
E -> W : explicitly configured import/retrieval under connector policy
W -> E : explicitly configured export/write under separate authority
P <-> W: capability-scoped processing
```

Forbidden:

```text
W -> R : direct patient/workspace data flow
X -> R : automatic admission
E -> R : patient-context passthrough
P -> R : model feedback/training upload from Workspace content
W -> hidden telemetry endpoint
```

## 4. Data classification

Minimum classes:

| Class | Examples | Default handling |
|---|---|---|
| PUBLIC | public research metadata, public schemas | normal local storage |
| INTERNAL | app configuration, non-sensitive operational state | local protected storage |
| SENSITIVE_CLINICAL | patient/encounter notes, FHIR resources, transcripts | encrypted local store |
| AUDIO_CLINICAL | encounter recordings/chunks | encrypted, short-retention by default |
| SECRET | encryption keys, connector tokens | platform secret store; never logs/database payload |
| AUDIT_METADATA | action/type/object IDs/timestamps | append-only logical audit; no full payload |
| RESEARCH_ARTIFACT | synthetic/evidence-governed Research Core object | governed by Research Core |
| EXPORT_QUARANTINE | explicit export awaiting policy/admission | isolated staging |

A derived embedding, graph edge, cache, thumbnail, transcript chunk, or index inherits the sensitivity of its source unless a stricter class is required.

## 5. Encryption and key lifecycle

Before PHI-capable use, implementation must prove:

- sensitive database encryption at rest;
- authenticated encryption for sensitive blobs/attachments;
- keys stored separately from encrypted payloads;
- platform-protected root secret where available;
- per-workspace data-encryption key or equivalent compartment;
- key version recorded with encrypted objects;
- key rotation without silent data loss;
- crash-safe rotation;
- revoked/retired keys cannot silently continue writes;
- backup keys separated from active store keys;
- no plaintext fallback after encryption failure.

Key material must never be:
- committed;
- logged;
- placed in model prompts;
- exported in diagnostics;
- included in backups without an explicit wrapped-key design.

Exact cryptographic libraries and database choices require a separate implementation ADR/security review.

## 6. Identity, tenancy, and authorization

Even for a single-user local V1, object ownership must be explicit.

Minimum identity layers:

```text
installation_id
workspace_id
actor_id
patient_id
encounter_id
object_id
```

Authorization rules:

- every sensitive object belongs to exactly one workspace;
- cross-workspace lookup fails closed;
- connector capability is scoped per workspace;
- model/plugin capability is scoped per invocation or policy;
- export scope is explicit;
- audit actor is never inferred solely from a UI label;
- future multi-user support must not require rewriting object ownership.

## 7. Recording and audio lifecycle

Threats:
- recording without valid consent;
- capture continuing after user believes it stopped;
- unencrypted temporary chunks;
- crash leaving orphaned audio;
- OS/cloud backup leaking recordings;
- stale audio retained after transcript acceptance.

Controls:
- persistent visible recording state;
- explicit start/stop;
- consent/policy gate before capture;
- monotonic capture session identity;
- encrypted chunk writes;
- bounded temp lifetime;
- crash recovery inventory;
- configurable retention;
- delete cascade covering chunks/caches/derived features;
- audit events for lifecycle transitions.

## 8. Transcript and note integrity

Threats:
- source text modified without provenance;
- generated note presented as source;
- model inserts unsupported facts;
- user edit loses source relationship;
- stale transcript reused after correction.

Controls:
- immutable source revision identities;
- generated draft revision identities;
- source-range links;
- human edit events;
- unsupported/uncertain state;
- content digests;
- no silent source repair;
- downstream drafts bind exact input revisions.

## 9. Prompt injection and untrusted content

Every imported document, FHIR text field, webpage/evidence snippet, transcript, and connector payload is untrusted data.

Rules:
- retrieved/imported content cannot grant tool permissions;
- model-visible source text is delimited as data;
- tool instructions come only from trusted application policy;
- URL/file content cannot silently enable network/model/plugin capabilities;
- external content cannot override consent, data-classification, or export policy;
- tool calls require typed arguments and policy checks outside the model;
- high-consequence tools remain human-confirmed.

Tests must include:
- document saying “ignore previous rules”;
- malicious FHIR narrative;
- citation page containing tool-like instructions;
- adversarial patient text that resembles system messages;
- malicious plugin result.

## 10. Model isolation

Local model/runtime rules:

- model artifact identity pinned;
- no implicit remote code;
- no automatic model upgrade;
- no silent network fallback;
- model output treated as untrusted;
- structured output validated before use;
- model cannot read arbitrary filesystem paths;
- model cannot read secrets;
- model cannot directly mutate Research Core;
- model cannot directly execute EHR writes;
- runtime crashes preserve data consistency.

Remote model connectors, if ever authorized, require an explicit egress/data contract.

## 11. Connector security

Each connector declares:

```text
connector_id
version
READ capabilities
WRITE capabilities
network destinations
credential scope
data classes
retention assumptions
retry semantics
offline behavior
```

Controls:
- least privilege;
- read-only first;
- destination allowlist;
- no credential in logs;
- explicit TLS/identity validation;
- idempotency/reconciliation identity for writes;
- stale-data metadata;
- malformed payload rejection;
- bounded retries;
- user-visible connector state.

A successful HTTP status is not proof that a clinical write is correct.

## 12. FHIR import/export threats

Threats:
- malformed resource accepted;
- reference points to wrong patient;
- version conflict overwritten;
- security label discarded;
- provenance lost;
- partial Bundle write treated as complete;
- terminology state misrepresented.

Controls:
- declared R4 subset;
- parse/schema/profile/reference stages distinguished;
- patient/workspace binding checked;
- version/ETag handling where applicable;
- security labels retained;
- provenance sidecar/FHIR Provenance mapping;
- transaction result reconciliation;
- partial failure is explicit.

## 13. Evidence retrieval threats

Threats:
- malicious or low-quality source;
- citation mismatch;
- stale guideline;
- source removed/changed;
- retrieval poisoning;
- patient context exposed to unauthorized network source;
- hallucinated citation;
- model confidence presented as evidence strength.

Controls:
- source allow/admission policy;
- retrieval snapshot identity;
- canonical source identifiers;
- claim-source link verification;
- source date/freshness;
- evidence-strength method/version;
- contradiction state;
- missing-source state;
- network egress policy before patient context leaves device;
- replay from frozen snapshot when possible.

## 14. Graph threats

Threats:
- inferred relation presented as observed fact;
- stale edge after source correction;
- graph traversal leaks another workspace;
- deleted source survives in graph/index;
- inference cycles amplify unsupported claims.

Controls:
- epistemic edge state;
- source refs on every edge;
- derived graph rebuildable from source;
- invalidation on source revision;
- workspace-scoped indexes;
- delete cascade/rebuild;
- path/explain returns provenance;
- confidence never upgrades epistemic state.

## 15. Plugin and supply-chain threats

Threats:
- compromised dependency/plugin;
- typosquatting;
- mixed donor licenses;
- plugin exfiltration;
- unsafe post-install hooks;
- stale vulnerable binary.

Controls:
- exact dependency locks;
- source/revision/license registry;
- allowlisted plugin packages;
- capability declarations;
- no implicit plugin discovery/execution;
- signature/hash verification where available;
- vulnerability review;
- sandbox/process isolation when justified;
- no source copying before provenance review.

## 16. Backup and restore

Backup contract:

- encrypted;
- integrity-protected;
- versioned manifest;
- explicit included data classes;
- no secrets in plaintext;
- restore into a quarantine/reconciliation phase;
- schema/policy version checked;
- key availability checked;
- audit event written.

Restore must not:
- overwrite newer state silently;
- resurrect deleted content without explicit policy;
- cross workspace identities;
- bypass migrations.

## 17. Deletion

Deletion must define:

- object scope;
- derived objects;
- indexes;
- graph projections;
- embeddings;
- caches;
- temp files;
- retained backups;
- audit metadata;
- connector-side copies when applicable.

The product must distinguish:
- immediate local deletion;
- cryptographic erasure;
- backup expiry;
- external-system deletion request/state.

A UI disappearing is not deletion evidence.

## 18. Logging and diagnostics

Never log:
- full transcript;
- full note;
- FHIR patient payload;
- audio;
- secret/token;
- raw external response containing sensitive context.

Prefer:
- object IDs;
- operation IDs;
- error classes;
- durations;
- byte counts;
- model/runtime IDs;
- policy decision IDs;
- redacted diagnostics.

Debug mode must not silently weaken this rule.

## 19. Threat scenarios and required tests

| Scenario | Required behavior |
|---|---|
| Malicious imported document instructs model to export data | instruction ignored as data; no export capability granted |
| Model outputs unsupported medication/order | stays draft/unsupported; no downstream write |
| Connector token appears in exception | redacted; test fails if token present |
| Database copied from disk | sensitive payload unreadable without key |
| Backup stolen | payload protected independently |
| Recording process crashes | committed encrypted chunks inventoried; no plaintext orphan |
| User deletes encounter | source + derived indexes/graph/cache follow declared deletion contract |
| Workspace export copied toward Research Core | no-backflow guard blocks direct path |
| De-identified export requested | lands only in Domain X, never Research Core |
| FHIR Bundle partially accepted by server | reconciliation records partial result; local state not marked fully synced |
| Evidence source contradicts another | contradiction surfaced |
| Graph inference conflicts with explicit source | edge remains INFERRED/AMBIGUOUS; explicit source not overwritten |
| Network disappears | local core continues or fails explicitly; no alternate cloud endpoint |
| Local model missing | named dependency error; no download unless explicit acquisition action |
| Plugin requests undeclared capability | denied and audited |

## 20. PHI-readiness gate

A future PHI-readiness packet must prove at minimum:

- accepted scope ADR;
- data-flow diagram matches implementation;
- encryption/key tests;
- backup/restore tests;
- deletion tests;
- audit tests;
- no-backflow tests;
- offline/no-hidden-egress tests;
- connector least-privilege tests;
- prompt-injection/tool-boundary tests;
- model isolation;
- dependency/source/license review;
- threat-model review;
- security review / penetration assessment appropriate to deployment;
- privacy/retention policy;
- incident/recovery runbook.

`PHI_READY` is not equivalent to `PHI_AUTHORIZED`.

A later explicit authorization must still name environment, user group, data class, connectors, retention, runtime, and stop conditions.

## 21. Non-grants

```text
PHI_INGESTION = NOT_AUTHORIZED
REAL_PATIENT_IMPORT = NOT_AUTHORIZED
CLINICAL_PRODUCTION_USE = NOT_AUTHORIZED
EHR_WRITE = NOT_AUTHORIZED
AUTONOMOUS_ACTION = NOT_AUTHORIZED
REMOTE_MODEL_EGRESS = NOT_AUTHORIZED
TRAINING_ON_WORKSPACE_DATA = NOT_AUTHORIZED
RESEARCH_ADMISSION_FROM_WORKSPACE = NOT_AUTHORIZED
```
