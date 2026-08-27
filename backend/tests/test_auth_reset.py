from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pickone.auth.errors import InvalidCredentialsError, TokenExpiredError, TokenInvalidError
from pickone.auth.service import (
    login,
    password_reset_confirm,
    password_reset_request,
    register,
    resolve_session,
)
from pickone.core.clock import FrozenClock
from pickone.core.models import OutboxJob


async def _latest_email_token(db_session: AsyncSession, to: str, marker: str) -> str:
    jobs = (
        (await db_session.execute(select(OutboxJob).order_by(OutboxJob.created_at.desc())))
        .scalars()
        .all()
    )
    job = next(j for j in jobs if j.payload.get("to") == to and marker in j.payload["body"])
    url = job.payload["body"].split("\n\n")[1].strip()
    return str(parse_qs(urlparse(url).query)["token"][0])


async def test_reset_request_enqueues_an_email_for_a_known_user(db_session: AsyncSession) -> None:
    await register(db_session, email="r1@b.com", password="correcthorse1", guest_token=None)

    await password_reset_request(db_session, email="r1@b.com")

    jobs = (await db_session.execute(select(OutboxJob))).scalars().all()
    assert any(
        j.payload.get("to") == "r1@b.com" and "reset" in j.payload["subject"].lower() for j in jobs
    )


async def test_reset_request_is_silent_for_an_unknown_email(db_session: AsyncSession) -> None:
    await password_reset_request(db_session, email="ghost@b.com")

    jobs = (await db_session.execute(select(OutboxJob))).scalars().all()
    assert not any(j.payload.get("to") == "ghost@b.com" for j in jobs)


async def test_reset_confirm_changes_the_password_and_revokes_sessions(
    db_session: AsyncSession,
) -> None:
    await register(db_session, email="r2@b.com", password="correcthorse1", guest_token=None)
    old_login = await login(db_session, email="r2@b.com", password="correcthorse1", ip="6.6.6.6")

    await password_reset_request(db_session, email="r2@b.com")
    token = await _latest_email_token(db_session, "r2@b.com", "/reset?")

    result = await password_reset_confirm(db_session, token=token, new_password="brandnewpass1")

    assert await resolve_session(db_session, old_login.raw_token) is None
    assert await resolve_session(db_session, result.raw_token) is not None

    with pytest.raises(InvalidCredentialsError):
        await login(db_session, email="r2@b.com", password="correcthorse1", ip="6.6.6.7")

    relog = await login(db_session, email="r2@b.com", password="brandnewpass1", ip="6.6.6.8")
    assert relog.user.email == "r2@b.com"


async def test_reset_confirm_rejects_a_reused_token(db_session: AsyncSession) -> None:
    await register(db_session, email="r3@b.com", password="correcthorse1", guest_token=None)
    await password_reset_request(db_session, email="r3@b.com")
    token = await _latest_email_token(db_session, "r3@b.com", "/reset?")

    await password_reset_confirm(db_session, token=token, new_password="brandnewpass1")

    with pytest.raises(TokenInvalidError):
        await password_reset_confirm(db_session, token=token, new_password="anotherpass1")


async def test_reset_confirm_rejects_an_expired_token(
    db_session: AsyncSession, frozen_clock: FrozenClock
) -> None:
    await register(db_session, email="r4@b.com", password="correcthorse1", guest_token=None)
    await password_reset_request(db_session, email="r4@b.com")
    token = await _latest_email_token(db_session, "r4@b.com", "/reset?")

    frozen_clock.advance(seconds=61 * 60)

    with pytest.raises(TokenExpiredError):
        await password_reset_confirm(db_session, token=token, new_password="brandnewpass1")
