from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.core.clock import Clock, get_clock
from pickone.core.errors import RateLimitedError
from pickone.core.models import RateLimit


@dataclass(frozen=True)
class RateLimitStatus:
    limit: int
    remaining: int
    retry_after_seconds: int


def _window_start(now: datetime, window_seconds: int) -> datetime:
    epoch = int(now.timestamp())
    floored = epoch - (epoch % window_seconds)
    return datetime.fromtimestamp(floored, tz=UTC)


async def increment(
    session: AsyncSession, key: str, *, window_seconds: int, clock: Clock | None = None
) -> int:
    clock = clock or get_clock()
    window = _window_start(clock.now(), window_seconds)

    stmt = (
        insert(RateLimit)
        .values(key=key, window_start=window, count=1)
        .on_conflict_do_update(
            index_elements=[RateLimit.key, RateLimit.window_start],
            set_={"count": RateLimit.count + 1},
        )
        .returning(RateLimit.count)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


def _retry_after(clock: Clock, window_seconds: int) -> int:
    window = _window_start(clock.now(), window_seconds)
    seconds = int((window + timedelta(seconds=window_seconds) - clock.now()).total_seconds())
    return max(seconds, 1)


async def enforce(
    session: AsyncSession,
    key: str,
    *,
    limit: int,
    window_seconds: int,
    clock: Clock | None = None,
) -> RateLimitStatus:
    clock = clock or get_clock()
    count = await increment(session, key, window_seconds=window_seconds, clock=clock)
    retry_after = _retry_after(clock, window_seconds)
    remaining = max(limit - count, 0)

    if count > limit:
        raise RateLimitedError(
            details={"retry_after": retry_after},
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
            },
        )

    return RateLimitStatus(limit=limit, remaining=remaining, retry_after_seconds=retry_after)


async def peek(
    session: AsyncSession, key: str, *, window_seconds: int, clock: Clock | None = None
) -> int:
    clock = clock or get_clock()
    window = _window_start(clock.now(), window_seconds)
    result = await session.execute(
        select(RateLimit.count).where(RateLimit.key == key, RateLimit.window_start == window)
    )
    return result.scalar_one_or_none() or 0
