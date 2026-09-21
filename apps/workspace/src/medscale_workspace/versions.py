"""Version identities recorded by the CW-002 protected workspace store.

ADR-0039 decision 6 makes application version, workspace schema version, policy
version and encryption-format version first-class recorded state. The application
version is *supplied by the caller at store-open time* and is deliberately not
duplicated here: single-sourcing the workspace package version is Issue #464 item 2
and is not fixed inside CW-002.

CW-002 implements store initialization only. The remaining migration classes and
their manifest/preflight/rollback machinery belong to CW-018.
"""

from __future__ import annotations

WORKSPACE_SCHEMA_VERSION = 1
ENCRYPTION_FORMAT_VERSION = 1
KEY_DERIVATION_VERSION = 1
POLICY_VERSION = "mesc-clinical-workspace-synthetic-only/1"

MINIMUM_READABLE_WORKSPACE_SCHEMA = 1
MAXIMUM_READABLE_WORKSPACE_SCHEMA = 1

INITIALIZATION_MIGRATION_ID = "cw-002-store-initialization"
INITIALIZATION_MIGRATION_CLASS = "M1"


def unreadable_schema_reason(recorded: int) -> str | None:
    """Return why a recorded schema version cannot be opened, or ``None``."""

    if recorded > MAXIMUM_READABLE_WORKSPACE_SCHEMA:
        return (
            "recorded workspace schema version is newer than this application can read; "
            "a downgrade is refused rather than attempted"
        )
    if recorded < MINIMUM_READABLE_WORKSPACE_SCHEMA:
        return (
            "recorded workspace schema version predates this application; forward "
            "migration classes belong to CW-018 and best-effort parsing is not attempted"
        )
    return None
