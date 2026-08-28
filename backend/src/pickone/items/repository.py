from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.core.clock import get_clock
from pickone.core.config import get_settings
from pickone.core.idgen import new_uuid
from pickone.items.models import Item
from pickone.moderation.models import ItemReport

MAX_NUMERIC_SUFFIX_ATTEMPTS = 99


async def get_item_by_normalized_text(session: AsyncSession, normalized_text: str) -> Item | None:
    result = await session.execute(select(Item).where(Item.normalized_text == normalized_text))
    return result.scalar_one_or_none()


async def get_item_by_slug(session: AsyncSession, slug: str) -> Item | None:
    result = await session.execute(select(Item).where(Item.slug == slug))
    return result.scalar_one_or_none()


async def get_item_by_id(session: AsyncSession, item_id: str) -> Item | None:
    return await session.get(Item, item_id)


def _hash_suffix() -> str:
    return base64.b32encode(os.urandom(4)).decode("ascii").rstrip("=").lower()[:6]


class NormalizedTextCollisionError(Exception):
    pass


def _is_normalized_text_violation(exc: IntegrityError) -> bool:
    cause = exc.orig.__cause__ if exc.orig is not None else None
    return getattr(cause, "constraint_name", None) == "items_normalized_text_uq"


async def insert_item_with_unique_slug(
    session: AsyncSession,
    *,
    text: str,
    normalized_text: str,
    base_slug: str,
    created_by_user_id: str | None,
) -> Item:
    settings = get_settings()
    now = get_clock().now()

    def _build(slug: str) -> Item:
        return Item(
            text=text,
            normalized_text=normalized_text,
            slug=slug,
            created_by_user_id=created_by_user_id,
            status="PENDING_MODERATION",
            rating=settings.item_default_rating,
            rating_deviation=settings.item_default_rating_deviation,
            created_at=now,
        )

    candidates = [base_slug]
    candidates.extend(f"{base_slug}-{n}" for n in range(2, MAX_NUMERIC_SUFFIX_ATTEMPTS + 1))
    candidates.append(f"{base_slug}-{_hash_suffix()}")

    for slug in candidates:
        try:
            async with session.begin_nested():
                item = _build(slug)
                session.add(item)
                await session.flush()
        except IntegrityError as exc:
            if _is_normalized_text_violation(exc):
                raise NormalizedTextCollisionError() from exc
            continue
        else:
            return item

    raise RuntimeError("could not generate a unique slug")


async def set_item_status(
    session: AsyncSession, item: Item, *, status: str, published_at: datetime | None = None
) -> None:
    item.status = status
    if published_at is not None:
        item.published_at = published_at
    await session.flush()


async def create_report(
    session: AsyncSession, *, item_id: str, reporter_user_id: str | None, reason: str
) -> ItemReport:
    row = ItemReport(
        id=new_uuid(), item_id=item_id, reporter_user_id=reporter_user_id, reason=reason
    )
    session.add(row)
    await session.flush()
    return row


async def count_distinct_reporters(session: AsyncSession, item_id: str) -> int:
    result = await session.execute(
        select(func.count()).select_from(ItemReport).where(ItemReport.item_id == item_id)
    )
    return result.scalar_one()


async def list_moderation_queue(session: AsyncSession, *, statuses: list[str]) -> list[Item]:
    result = await session.execute(
        select(Item).where(Item.status.in_(statuses)).order_by(Item.created_at)
    )
    return list(result.scalars().all())


@dataclass(frozen=True)
class ReportGroup:
    item: Item
    reports: list[ItemReport] = field(default_factory=list)


async def list_unresolved_reports_grouped(session: AsyncSession) -> list[ReportGroup]:
    result = await session.execute(
        select(ItemReport, Item)
        .join(Item, Item.id == ItemReport.item_id)
        .where(ItemReport.resolved_at.is_(None))
        .order_by(Item.id, ItemReport.created_at)
    )
    grouped: dict[str, ReportGroup] = {}
    for report, item in result.all():
        if item.id not in grouped:
            grouped[item.id] = ReportGroup(item=item)
        grouped[item.id].reports.append(report)
    return list(grouped.values())
