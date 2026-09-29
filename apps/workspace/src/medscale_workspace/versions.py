"""Version identities recorded by the CW-002 protected workspace store.

ADR-0039 decision 6 makes application version, workspace schema version, policy
version and encryption-format version first-class recorded state. The application
version is *supplied by the caller at store-open time* and is deliberately not
duplicated here: single-sourcing the workspace package version is Issue #464 item 2
and is not fixed inside CW-002.

CW-002 implemented store initialization only. CW-018 (Issue #520) adds the first
forward migration: the M1 additive schema migration from workspace schema 1 to 2,
which adds the migration checkpoint journal and the deletion-tombstone ledger. A
schema-1 store is migratable but is never opened in normal mode, because a
migration must not begin simply because the application version changed.
"""

from __future__ import annotations

WORKSPACE_SCHEMA_VERSION = 2
ENCRYPTION_FORMAT_VERSION = 1
KEY_DERIVATION_VERSION = 1
POLICY_VERSION = "mesc-clinical-workspace-synthetic-only/1"
PROVENANCE_FORMAT_VERSION = 1
AUDIT_CHAIN_FORMAT_VERSION = 1
DATA_CLASSIFICATION_VERSION = 1

MINIMUM_READABLE_WORKSPACE_SCHEMA = 2
MAXIMUM_READABLE_WORKSPACE_SCHEMA = 2
MIGRATABLE_WORKSPACE_SCHEMAS = (1,)
SUPPORTED_DOWNGRADE_TARGETS: tuple[int, ...] = ()

INITIALIZATION_MIGRATION_ID = "cw-002-store-initialization"
INITIALIZATION_MIGRATION_CLASS = "M1"
SCHEMA_V2_MIGRATION_ID = "cw-018-schema-v2-lifecycle-ledgers"
SCHEMA_V2_MIGRATION_CLASS = "M1"

BACKUP_FORMAT_VERSION = 1
SUPPORTED_BACKUP_FORMAT_VERSIONS = (BACKUP_FORMAT_VERSION,)


def unreadable_schema_reason(recorded: int) -> str | None:
    """Return why a recorded schema version cannot be opened in normal mode, or ``None``."""

    if recorded > MAXIMUM_READABLE_WORKSPACE_SCHEMA:
        return (
            "recorded workspace schema version is newer than this application can read; "
            "a downgrade is refused rather than attempted"
        )
    if recorded in MIGRATABLE_WORKSPACE_SCHEMAS:
        return (
            "recorded workspace schema version predates this application; the store must "
            "be migrated forward by the explicit CW-018 migration before normal use"
        )
    if recorded < MINIMUM_READABLE_WORKSPACE_SCHEMA:
        return (
            "recorded workspace schema version predates every supported migration; "
            "best-effort parsing is not attempted"
        )
    return None
