from __future__ import annotations

import pytest
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

EXPECTED_ENUMS = {
    "item_status": {"PENDING_MODERATION", "APPROVED", "REVIEW", "REJECTED", "HIDDEN"},
    "battle_status": {"PENDING", "COMPLETED", "SKIPPED", "EXPIRED"},
    "moderation_decision": {"APPROVED", "REVIEW", "REJECTED", "ERROR"},
    "email_token_purpose": {"VERIFY_EMAIL", "RESET_PASSWORD"},
}


async def test_migrations_created_the_enums(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text(
                "SELECT t.typname, e.enumlabel FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid"
            )
        )
    found: dict[str, set[str]] = {}
    for name, label in rows:
        found.setdefault(name, set()).add(label)
    for name, labels in EXPECTED_ENUMS.items():
        assert found.get(name) == labels, f"enum {name} mismatch"


async def test_migrations_create_exactly_the_expected_tables(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        rows = await conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        )
    tables = {r[0] for r in rows}
    expected = {
        "alembic_version",
        "users",
        "sessions",
        "email_tokens",
        "rate_limits",
        "outbox_jobs",
        "items",
        "moderation_results",
        "item_reports",
    }
    assert tables == expected, f"unexpected: {tables - expected}, missing: {expected - tables}"


def test_migration_history_is_linear(alembic_config: Config) -> None:
    script = ScriptDirectory.from_config(alembic_config)
    assert len(script.get_heads()) == 1, "multiple alembic heads"


def test_every_migration_has_a_downgrade(alembic_config: Config) -> None:
    script = ScriptDirectory.from_config(alembic_config)
    for rev in script.walk_revisions():
        assert rev.module.downgrade is not None, f"{rev.revision} has no downgrade"


@pytest.mark.usefixtures("_migrated")
def test_autogenerate_diff_is_empty(alembic_config: Config) -> None:
    command.check(alembic_config)
