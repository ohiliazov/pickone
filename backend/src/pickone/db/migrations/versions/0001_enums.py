"""M0: the four domain enums. No tables yet.

Revision ID: 0001_enums
Revises:
Create Date: 2026-08-26

These are created as standalone Postgres types rather than inline on a column,
so that M1/M2/M4 can reference them without the create/drop churn Alembic
generates when an enum is owned by the first table that happens to use it.

Autogenerate does not see standalone types, so this migration produces no diff.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_enums"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUMS: dict[str, tuple[str, ...]] = {
    # [SPEC §7.1]
    "item_status": ("PENDING_MODERATION", "APPROVED", "REVIEW", "REJECTED", "HIDDEN"),
    "battle_status": ("PENDING", "COMPLETED", "SKIPPED", "EXPIRED"),
    "moderation_decision": ("APPROVED", "REVIEW", "REJECTED", "ERROR"),
    "email_token_purpose": ("VERIFY_EMAIL", "RESET_PASSWORD"),
}


def upgrade() -> None:
    for name, values in ENUMS.items():
        labels = ", ".join(f"'{v}'" for v in values)
        op.execute(f"CREATE TYPE {name} AS ENUM ({labels})")


def downgrade() -> None:
    for name in reversed(list(ENUMS)):
        op.execute(f"DROP TYPE IF EXISTS {name}")
