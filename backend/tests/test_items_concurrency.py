from __future__ import annotations

import asyncio

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from pickone.auth.models import User
from pickone.core.clock import get_clock
from pickone.core.idgen import new_uuid
from pickone.items import service
from pickone.items.errors import AlreadyExistsError
from pickone.moderation.provider import ProviderResult

CONCURRENCY = 20


class _StubProvider:
    async def check(self, text: str) -> ProviderResult:
        return ProviderResult(scores={}, model="stub", raw={})


async def test_slug_collision_race(engine: AsyncEngine) -> None:
    sessionmaker = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def _attempt() -> str:
        async with sessionmaker() as session:
            now = get_clock().now()
            user = User(
                id=new_uuid(),
                email=f"{new_uuid()}@example.com",
                password_hash="x",
                is_guest=False,
                email_verified_at=now,
                created_at=now,
                last_seen_at=now,
            )
            session.add(user)
            await session.flush()
            try:
                await service.create_item(
                    session, user=user, text="Concurrent Item", provider=_StubProvider()
                )
            except AlreadyExistsError:
                await session.rollback()
                return "conflict"
            else:
                await session.commit()
                return "success"

    results = await asyncio.gather(*[_attempt() for _ in range(CONCURRENCY)])
    assert results.count("success") == 1
    assert results.count("conflict") == CONCURRENCY - 1
