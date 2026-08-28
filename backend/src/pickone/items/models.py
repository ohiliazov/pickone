from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, Text
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from pickone.core.idgen import new_uuid
from pickone.db.base import Base

ItemStatus = ENUM(
    "PENDING_MODERATION",
    "APPROVED",
    "REVIEW",
    "REJECTED",
    "HIDDEN",
    name="item_status",
    create_type=False,
)


class Item(Base):
    __tablename__ = "items"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=new_uuid)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(ItemStatus, nullable=False, default="PENDING_MODERATION")
    rating: Mapped[float] = mapped_column(
        Numeric(10, 4), nullable=False, server_default=sql_text("0.0000")
    )
    rating_deviation: Mapped[float] = mapped_column(
        Numeric(10, 4), nullable=False, server_default=sql_text("350.0000")
    )
    battle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    win_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    loss_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skip_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rating_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint("char_length(text) BETWEEN 2 AND 64", name="text_len"),
        CheckConstraint("win_count + loss_count <= battle_count", name="counts"),
        CheckConstraint("rating > -100000 AND rating < 100000", name="rating"),
        CheckConstraint("rating_deviation > 0 AND rating_deviation <= 350", name="rd"),
        Index("items_normalized_text_uq", "normalized_text", unique=True),
        Index("items_slug_uq", "slug", unique=True),
        Index("items_ranking_idx", "rating", "id", postgresql_where=(status == "APPROVED")),
        Index("items_pool_idx", "rating", postgresql_where=(status == "APPROVED")),
        Index(
            "items_coldstart_idx",
            "rating_deviation",
            "battle_count",
            postgresql_where=(status == "APPROVED"),
        ),
        Index(
            "items_moderation_idx",
            "status",
            "created_at",
            postgresql_where=status.in_(["PENDING_MODERATION", "REVIEW"]),
        ),
    )
