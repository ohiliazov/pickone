"""M2: items, moderation_results, item_reports.

Revision ID: 0003_m2_items
Revises: 0002_m1_auth
Create Date: 2026-08-28
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_m2_items"
down_revision: str | None = "0002_m1_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ITEM_STATUS = postgresql.ENUM(
    "PENDING_MODERATION",
    "APPROVED",
    "REVIEW",
    "REJECTED",
    "HIDDEN",
    name="item_status",
    create_type=False,
)
MODERATION_DECISION = postgresql.ENUM(
    "APPROVED",
    "REVIEW",
    "REJECTED",
    "ERROR",
    name="moderation_decision",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "items",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.Column("status", ITEM_STATUS, nullable=False),
        sa.Column(
            "rating",
            sa.Numeric(precision=10, scale=4),
            nullable=False,
            server_default=sa.text("0.0000"),
        ),
        sa.Column(
            "rating_deviation",
            sa.Numeric(precision=10, scale=4),
            nullable=False,
            server_default=sa.text("350.0000"),
        ),
        sa.Column("battle_count", sa.Integer(), nullable=False),
        sa.Column("win_count", sa.Integer(), nullable=False),
        sa.Column("loss_count", sa.Integer(), nullable=False),
        sa.Column("skip_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rating_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("char_length(text) BETWEEN 2 AND 64", name=op.f("items_text_len_ck")),
        sa.CheckConstraint("rating > -100000 AND rating < 100000", name=op.f("items_rating_ck")),
        sa.CheckConstraint(
            "rating_deviation > 0 AND rating_deviation <= 350", name=op.f("items_rd_ck")
        ),
        sa.CheckConstraint("win_count + loss_count <= battle_count", name=op.f("items_counts_ck")),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=op.f("items_created_by_user_id_fkey"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("items_pkey")),
    )
    op.create_index(
        "items_coldstart_idx",
        "items",
        ["rating_deviation", "battle_count"],
        unique=False,
        postgresql_where=sa.text("status = 'APPROVED'"),
    )
    op.create_index(
        "items_moderation_idx",
        "items",
        ["status", "created_at"],
        unique=False,
        postgresql_where=sa.text("status IN ('PENDING_MODERATION', 'REVIEW')"),
    )
    op.create_index("items_normalized_text_uq", "items", ["normalized_text"], unique=True)
    op.create_index(
        "items_pool_idx",
        "items",
        ["rating"],
        unique=False,
        postgresql_where=sa.text("status = 'APPROVED'"),
    )
    op.create_index(
        "items_ranking_idx",
        "items",
        ["rating", "id"],
        unique=False,
        postgresql_where=sa.text("status = 'APPROVED'"),
    )
    op.create_index("items_slug_uq", "items", ["slug"], unique=True)
    op.create_table(
        "item_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("reporter_user_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["item_id"], ["items.id"], name=op.f("item_reports_item_id_fkey"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["reporter_user_id"],
            ["users.id"],
            name=op.f("item_reports_reporter_user_id_fkey"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("item_reports_pkey")),
    )
    op.create_index(
        "item_reports_once_uq",
        "item_reports",
        ["item_id", "reporter_user_id"],
        unique=True,
        postgresql_where=sa.text("reporter_user_id IS NOT NULL"),
    )
    op.create_table(
        "moderation_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("item_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=True),
        sa.Column("decision", MODERATION_DECISION, nullable=False),
        sa.Column("scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("raw_response", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("policy_version", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("reviewed_by_user_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            name=op.f("moderation_results_item_id_fkey"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_user_id"],
            ["users.id"],
            name=op.f("moderation_results_reviewed_by_user_id_fkey"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("moderation_results_pkey")),
    )
    op.create_index(
        "moderation_results_item_idx", "moderation_results", ["item_id", "created_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index("moderation_results_item_idx", table_name="moderation_results")
    op.drop_table("moderation_results")
    op.drop_index(
        "item_reports_once_uq",
        table_name="item_reports",
        postgresql_where=sa.text("reporter_user_id IS NOT NULL"),
    )
    op.drop_table("item_reports")
    op.drop_index("items_slug_uq", table_name="items")
    op.drop_index(
        "items_ranking_idx", table_name="items", postgresql_where=sa.text("status = 'APPROVED'")
    )
    op.drop_index(
        "items_pool_idx", table_name="items", postgresql_where=sa.text("status = 'APPROVED'")
    )
    op.drop_index("items_normalized_text_uq", table_name="items")
    op.drop_index(
        "items_moderation_idx",
        table_name="items",
        postgresql_where=sa.text("status IN ('PENDING_MODERATION', 'REVIEW')"),
    )
    op.drop_index(
        "items_coldstart_idx", table_name="items", postgresql_where=sa.text("status = 'APPROVED'")
    )
    op.drop_table("items")
