from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.models import User
from pickone.core.clock import get_clock
from pickone.core.config import get_settings
from pickone.core.errors import RateLimitedError
from pickone.core.idgen import new_uuid
from pickone.items import service
from pickone.moderation.provider import ProviderResult


async def _make_established_user(session: AsyncSession) -> User:
    now = get_clock().now()
    user = User(
        id=new_uuid(),
        email=f"{new_uuid()}@example.com",
        password_hash="x",
        is_guest=False,
        email_verified_at=now,
        created_at=now - timedelta(days=30),
        last_seen_at=now,
    )
    session.add(user)
    await session.flush()
    return user


class _StubProvider:
    async def check(self, text: str) -> ProviderResult:
        return ProviderResult(scores={}, model="stub", raw={})


async def test_hourly_limit_raises_with_retry_after_and_headers(
    db_session: AsyncSession,
) -> None:
    user = await _make_established_user(db_session)
    provider = _StubProvider()
    limit = get_settings().rl_items_per_hour_user

    for n in range(limit):
        await service.create_item(
            db_session, user=user, text=f"Hourly limit item {n}", provider=provider
        )

    with pytest.raises(RateLimitedError) as exc_info:
        await service.create_item(
            db_session, user=user, text="One past the hourly limit", provider=provider
        )
    assert exc_info.value.details["retry_after"] > 0
    assert "Retry-After" in exc_info.value.headers


async def test_per_ip_daily_limit_is_enforced_across_different_users(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PICKONE_RL_ITEMS_PER_HOUR_USER", "1000")
    monkeypatch.setenv("PICKONE_RL_ITEMS_PER_DAY_USER", "1000")
    monkeypatch.setenv("PICKONE_RL_ITEMS_PER_DAY_IP", "3")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        provider = _StubProvider()
        ip = "9.9.9.9"

        for n in range(settings.rl_items_per_day_ip):
            user = await _make_established_user(db_session)
            await service.create_item(
                db_session, user=user, text=f"Shared IP item {n}", provider=provider, ip=ip
            )

        overflow_user = await _make_established_user(db_session)
        with pytest.raises(RateLimitedError) as exc_info:
            await service.create_item(
                db_session,
                user=overflow_user,
                text="One past the IP limit",
                provider=provider,
                ip=ip,
            )
        assert exc_info.value.details["retry_after"] > 0
        assert "Retry-After" in exc_info.value.headers
    finally:
        get_settings.cache_clear()


async def test_per_ip_daily_limit_is_isolated_per_ip(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PICKONE_RL_ITEMS_PER_HOUR_USER", "1000")
    monkeypatch.setenv("PICKONE_RL_ITEMS_PER_DAY_USER", "1000")
    monkeypatch.setenv("PICKONE_RL_ITEMS_PER_DAY_IP", "1")
    get_settings.cache_clear()
    try:
        provider = _StubProvider()
        user_a = await _make_established_user(db_session)
        user_b = await _make_established_user(db_session)

        await service.create_item(
            db_session, user=user_a, text="From IP A", provider=provider, ip="1.1.1.1"
        )
        await service.create_item(
            db_session, user=user_b, text="From IP B", provider=provider, ip="2.2.2.2"
        )
    finally:
        get_settings.cache_clear()
