from __future__ import annotations

from datetime import timedelta

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.models import User
from pickone.core.clock import get_clock
from pickone.core.config import get_settings


async def run_once(session: AsyncSession) -> int:
    settings = get_settings()
    cutoff = get_clock().now() - timedelta(days=settings.guest_empty_ttl_days)

    result = await session.execute(
        delete(User).where(User.is_guest.is_(True), User.last_seen_at < cutoff).returning(User.id)
    )
    reaped = result.scalars().all()
    return len(reaped)
