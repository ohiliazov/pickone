from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.service import register, verify_resend
from pickone.core.config import get_settings
from pickone.core.errors import RateLimitedError


async def test_register_enforces_the_per_ip_hourly_limit(db_session: AsyncSession) -> None:
    settings = get_settings()
    for i in range(settings.rl_register_per_hour_ip):
        await register(
            db_session,
            email=f"rl{i}@b.com",
            password="correcthorse1",
            guest_token=None,
            ip="3.1.1.1",
        )

    with pytest.raises(RateLimitedError) as exc_info:
        await register(
            db_session,
            email="rl-over@b.com",
            password="correcthorse1",
            guest_token=None,
            ip="3.1.1.1",
        )
    assert exc_info.value.details["retry_after"] > 0
    assert "Retry-After" in exc_info.value.headers


async def test_register_isolates_limits_per_ip(db_session: AsyncSession) -> None:
    settings = get_settings()
    for i in range(settings.rl_register_per_hour_ip):
        await register(
            db_session,
            email=f"iso{i}@b.com",
            password="correcthorse1",
            guest_token=None,
            ip="3.1.1.2",
        )

    await register(
        db_session,
        email="iso-other-ip@b.com",
        password="correcthorse1",
        guest_token=None,
        ip="3.1.1.3",
    )


async def test_verify_resend_enforces_the_per_user_hourly_limit(db_session: AsyncSession) -> None:
    settings = get_settings()
    reg = await register(db_session, email="vr1@b.com", password="correcthorse1", guest_token=None)

    for _ in range(settings.rl_verify_resend_per_hour_user):
        await verify_resend(db_session, user_id=reg.user.id)

    with pytest.raises(RateLimitedError):
        await verify_resend(db_session, user_id=reg.user.id)


async def test_password_reset_request_enforces_the_per_email_hourly_limit(
    db_session: AsyncSession,
) -> None:
    from pickone.auth.service import password_reset_request

    settings = get_settings()
    await register(db_session, email="pr1@b.com", password="correcthorse1", guest_token=None)

    for _ in range(settings.rl_reset_request_per_hour_email):
        await password_reset_request(db_session, email="pr1@b.com")

    with pytest.raises(RateLimitedError):
        await password_reset_request(db_session, email="pr1@b.com")
