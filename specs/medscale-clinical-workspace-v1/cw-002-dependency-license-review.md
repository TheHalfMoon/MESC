# CW-002 Dependency and Source License Review

- **Status:** Recorded evidence for CW-002 acceptance item "dependency/source license review"
- **Date:** 2026-09-21
- **Scope:** the single runtime dependency admitted by [ADR-0039](../../docs/adr/0039-local-protected-storage-and-key-management.md) decision 5 and reconciled by amendment A1.8
- **Rule applied:** R3 (everything shipped must permit derivative models and commercial use)

This record lists what was actually resolved and installed, not what a package is assumed to
be licensed under. License data below was read from the installed distribution metadata and
from the locked wheel identity.

## 1. Direct runtime dependency of the Workspace package

```text
package            cryptography
version            50.0.1
declared in        apps/workspace/pyproject.toml (pin: cryptography==50.0.1)
license expression Apache-2.0 OR BSD-3-Clause
license files      LICENSE, LICENSE.APACHE, LICENSE.BSD
source             https://pypi.org/simple (registry)
windows wheel      cryptography-50.0.1-cp311-abi3-win_amd64.whl
wheel sha256       aed8db4f6d71c51efb89530e12d9464e7bf2923d46c3205dc794a2a93f8c0648
role               AES-256-GCM AEAD primitive only
runtime service    none — a local wheel, no network, no paid service, no cloud dependency
```

Permissive and dual-licensed against a permissive alternative, so derivative use and
commercial use are permitted. The package ships prebuilt wheels for the supported platforms,
so no build toolchain is required at install time.

## 2. Transitive dependencies introduced by that resolution

```text
package            cffi
version            2.1.1
license expression MIT-0
windows wheel      cffi-2.1.1-cp311-cp311-win_amd64.whl
wheel sha256       42f6930c31dc7f50732c9ae793c2786c7b6b044195967bbdde40bb9be81c4cc0

package            pycparser
version            3.0
license expression BSD-3-Clause
wheel              pycparser-3.0-py3-none-any.whl
wheel sha256       b727414169a36b7d524c1c3e31839a521725078d7b2ff038656844266160a992
```

Both are permissive. Neither adds a runtime service, a network requirement, or a paid
component.

## 3. What the dependency is not

```text
additional cryptography surface     none — AEAD primitive only
password-hashing dependency         none
keyring / secret-service dependency none
network / telemetry dependency      none
paid service or cloud runtime       none
```

Key derivation (HKDF-SHA-256), envelope encoding, header validation, key-version handling,
the rotation state machine and the store path rule remain reviewed code inside
`apps/workspace/src/medscale_workspace`.

## 4. Why the Research Core lock file changes

`uv.lock` and the root `[dependency-groups] dev` list carry the same three packages so the
authoritative CI environment can run the CW-002 Workspace tests. That is a test-environment
installation path only:

```text
src/medscale runtime dependencies   unchanged (still none)
Workspace runtime dependencies      cryptography==50.0.1
```

The Research Core package remains importable and testable without the Workspace, exactly as
CW-001 required.

## 5. Limits of this record

This is a license and identity record for the packages the repository resolves. It is not a
vulnerability assessment, not a supply-chain attestation, not a reproducibility proof for
third-party build infrastructure beyond the recorded wheel hashes, and not acceptance of
CW-002. The independent security lane at CW-019 remains responsible for attacking the
storage, key-management and supply-chain surface.

```text
DEPENDENCY LICENSE REVIEW = RECORDED EVIDENCE
DEPENDENCY LICENSE REVIEW != CW-002 ACCEPTANCE
```
